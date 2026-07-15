"""
Calcul du score de risque global par pays, croisant les dimensions déjà collectées.

MÉTHODE (volontairement simple et transparente, pas un modèle prédictif) :
- Pour chaque dimension retenue, on prend la dernière valeur connue par pays
  (indicateurs World Bank) ou le nombre d'événements GDELT recensés pour ce pays
  (conflits, tensions sociales, activité militaire).
- Chaque dimension est normalisée en min-max sur [0, 1] à travers les pays disponibles.
- Le score global est la MOYENNE NON PONDÉRÉE des dimensions disponibles pour un pays
  (pas de dimension = pas de pénalité pour donnée manquante), ramenée sur 100.
- `details_json` conserve la valeur brute et normalisée de chaque dimension : la
  décomposition du score est toujours consultable, rien n'est caché dans un score
  composite opaque.

LIMITE ASSUMÉE : la pondération égale entre dimensions est un choix arbitraire et
documenté, pas une estimation calibrée empiriquement — voir README, section limites.
Ce score est un indicateur de veille, pas un outil de prédiction.

BIAIS CONSTATÉ À L'USAGE : les dimensions dérivées de GDELT (conflits_energetiques,
tensions_sociales, activite_militaire) comptent des ARTICLES DE PRESSE, pas des
événements réels — un pays très couvert par la presse anglophone (ex. États-Unis)
score donc mécaniquement plus haut sur ces dimensions qu'un pays au niveau de risque
réel comparable mais moins médiatisé. Ce n'est pas un biais de risque réel, c'est un
biais de couverture média — à garder en tête dans l'interprétation du score.
"""

import json
import logging
from datetime import datetime, timezone

from clients.neon_client import get_client, upsert_generic

logger = logging.getLogger(__name__)

# (table, colonne valeur) pour les indicateurs "dernière valeur connue par pays"
LATEST_VALUE_DIMENSIONS = {
    "dette_pct_pib": ("country_debt", "dette_pct_pib"),
    "chomage_pct": ("country_economy", "chomage_pct"),
    "inflation_pct": ("country_economy", "inflation_pct"),
    "budget_defense_pct_pib": ("defense_budget", "budget_pct_pib"),
}

# tables d'événements GDELT géolocalisés : le "risque" est approximé par le nombre
# d'événements recensés pour le pays (toute la période collectée à date)
EVENT_COUNT_DIMENSIONS = {
    "conflits_energetiques": "energy_conflicts",
    "tensions_sociales": "social_tensions",
    "activite_militaire": "military_activity",
}


def _latest_per_country(cur, table: str, value_col: str) -> dict[str, float]:
    cur.execute(
        f"""
        SELECT DISTINCT ON (pays_code) pays_code, {value_col}
        FROM {table}
        WHERE {value_col} IS NOT NULL
        ORDER BY pays_code, annee DESC
        """
    )
    return {row[0]: float(row[1]) for row in cur.fetchall()}


def _event_counts(cur, table: str) -> dict[str, int]:
    cur.execute(f"SELECT pays, COUNT(*) FROM {table} WHERE pays IS NOT NULL GROUP BY pays")
    return {row[0]: row[1] for row in cur.fetchall()}


def _normalize(values: dict[str, float]) -> dict[str, float]:
    """Min-max vers [0, 1]. Si toutes les valeurs sont égales, renvoie 0.5 partout."""
    if not values:
        return {}
    lo, hi = min(values.values()), max(values.values())
    if hi == lo:
        return {k: 0.5 for k in values}
    return {k: (v - lo) / (hi - lo) for k, v in values.items()}


def compute_scores() -> list[dict]:
    """Calcule le score de risque de chaque pays ayant au moins une dimension disponible."""
    conn = get_client()
    raw_dimensions: dict[str, dict[str, float]] = {}
    with conn.cursor() as cur:
        for dim, (table, col) in LATEST_VALUE_DIMENSIONS.items():
            raw_dimensions[dim] = _latest_per_country(cur, table, col)
        for dim, table in EVENT_COUNT_DIMENSIONS.items():
            raw_dimensions[dim] = _event_counts(cur, table)

    normalized = {dim: _normalize(vals) for dim, vals in raw_dimensions.items()}

    all_countries: set[str] = set()
    for vals in raw_dimensions.values():
        all_countries.update(vals.keys())

    date_calcul = datetime.now(timezone.utc).isoformat()
    rows = []
    for pays_code in sorted(all_countries):
        contributions = {}
        for dim in raw_dimensions:
            if pays_code in normalized[dim]:
                contributions[dim] = {
                    "valeur_brute": raw_dimensions[dim][pays_code],
                    "valeur_normalisee": round(normalized[dim][pays_code], 4),
                }
        if not contributions:
            continue

        score_global = round(
            100 * sum(c["valeur_normalisee"] for c in contributions.values()) / len(contributions), 2
        )
        rows.append(
            {
                "pays_code": pays_code,
                "date_calcul": date_calcul,
                "score_global": score_global,
                "details_json": json.dumps(
                    {
                        "dimensions": contributions,
                        "methode": "moyenne non pondérée des dimensions normalisées (min-max), échelle 0-100",
                    }
                ),
            }
        )

    logger.info("compute_scores : %d pays scorés", len(rows))
    return rows


def run() -> int:
    rows = compute_scores()
    return upsert_generic("risk_scores", rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    n = run()
    print(f"{n} ligne(s) envoyée(s) vers risk_scores")
