"""
Moteur de questions/réponses en langage naturel simple, à partir des données
réellement collectées dans Neon.

VOLONTAIREMENT SANS LLM : reconnaissance par mots-clés (pays + dimension), pas
d'appel à un modèle de langage. Reste gratuit, déterministe, et transparent sur
ce qu'il peut couvrir (voir DIMENSION_KEYWORDS) — si le pays ou la dimension ne
sont pas reconnus, le moteur le dit explicitement plutôt que d'inventer une
réponse plausible.
"""

import logging

from clients.neon_client import get_connection
from mapping.country_mapping import COUNTRY_NAME_TO_ISO3

logger = logging.getLogger(__name__)


def _find_country(question: str) -> tuple[str, str] | None:
    """Retourne (iso3, nom matché) du premier pays reconnu dans la question.

    Tri par longueur de nom décroissante pour préférer un match plus spécifique
    (ex. "Corée du Sud" avant un éventuel "Corée" seul).
    """
    q_lower = question.lower()
    for name, iso3 in sorted(COUNTRY_NAME_TO_ISO3.items(), key=lambda kv: -len(kv[0])):
        if name.lower() in q_lower:
            return iso3, name
    return None


def _handle_debt(cur, iso3: str) -> str | None:
    cur.execute(
        "SELECT annee, dette_pct_pib FROM country_debt "
        "WHERE pays_code=%s AND dette_pct_pib IS NOT NULL ORDER BY annee DESC LIMIT 1",
        (iso3,),
    )
    row = cur.fetchone()
    if not row:
        return None
    annee, valeur = row
    return f"la dette publique était de {float(valeur):g}% du PIB en {annee}"


def _handle_economy(cur, iso3: str) -> str | None:
    parts = []
    for col, label in [
        ("chomage_pct", "le taux de chômage était de {v:g}% en {a}"),
        ("inflation_pct", "l'inflation était de {v:g}% en {a}"),
        ("impots_pct_pib", "les recettes fiscales représentaient {v:g}% du PIB en {a}"),
    ]:
        cur.execute(
            f"SELECT annee, {col} FROM country_economy "
            f"WHERE pays_code=%s AND {col} IS NOT NULL ORDER BY annee DESC LIMIT 1",
            (iso3,),
        )
        row = cur.fetchone()
        if row:
            parts.append(label.format(v=float(row[1]), a=row[0]))
    return ", ".join(parts) if parts else None


def _handle_defense(cur, iso3: str) -> str | None:
    cur.execute(
        "SELECT annee, budget_pct_pib FROM defense_budget "
        "WHERE pays_code=%s AND budget_pct_pib IS NOT NULL ORDER BY annee DESC LIMIT 1",
        (iso3,),
    )
    row = cur.fetchone()
    if not row:
        return None
    return f"le budget défense était de {float(row[1]):g}% du PIB en {row[0]}"


def _handle_industry(cur, iso3: str) -> str | None:
    cur.execute(
        "SELECT annee, production_industrielle_pct_pib FROM country_industry "
        "WHERE pays_code=%s AND production_industrielle_pct_pib IS NOT NULL ORDER BY annee DESC LIMIT 1",
        (iso3,),
    )
    row = cur.fetchone()
    if not row:
        return None
    return f"la production industrielle représentait {float(row[1]):g}% du PIB en {row[0]}"


def _handle_risk(cur, iso3: str) -> str | None:
    cur.execute(
        "SELECT score_global, date_calcul FROM risk_scores "
        "WHERE pays_code=%s ORDER BY date_calcul DESC LIMIT 1",
        (iso3,),
    )
    row = cur.fetchone()
    if not row:
        return None
    return f"le score de risque calculé est de {float(row[0]):g}/100 (au {row[1].strftime('%d/%m/%Y')})"


def _handle_conflicts(cur, iso3: str) -> str | None:
    cur.execute("SELECT COUNT(*) FROM energy_conflicts WHERE pays=%s", (iso3,))
    n_conflicts = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM social_tensions WHERE pays=%s", (iso3,))
    n_tensions = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM military_activity WHERE pays=%s", (iso3,))
    n_military = cur.fetchone()[0]
    if n_conflicts == 0 and n_tensions == 0 and n_military == 0:
        return None
    return (
        f"{n_conflicts} conflit(s) énergétique(s), {n_tensions} tension(s) sociale(s) "
        f"et {n_military} événement(s) d'activité militaire recensés (couverture presse GDELT, "
        "pas un décompte exhaustif)"
    )


def _handle_global_synthesis(cur) -> str:
    """Aperçu agrégé tous pays confondus (pas un résumé par pays)."""
    cur.execute(
        """
        SELECT DISTINCT ON (pays_code) pays_code, score_global
        FROM risk_scores
        ORDER BY pays_code, date_calcul DESC
        """
    )
    latest_scores = cur.fetchall()
    top5 = sorted(latest_scores, key=lambda r: -float(r[1]))[:5]
    top5_str = ", ".join(f"{pays} ({float(score):.1f}/100)" for pays, score in top5)

    cur.execute(
        "SELECT AVG(v) FROM (SELECT DISTINCT ON (pays_code) dette_pct_pib AS v FROM country_debt "
        "WHERE dette_pct_pib IS NOT NULL ORDER BY pays_code, annee DESC) t"
    )
    avg_debt = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM energy_conflicts")
    n_conflicts = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM social_tensions")
    n_tensions = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM military_activity")
    n_military = cur.fetchone()[0]

    parts = [
        f"{n_conflicts} conflit(s) énergétique(s), {n_tensions} tension(s) sociale(s) et "
        f"{n_military} événement(s) d'activité militaire recensés au total (couverture presse GDELT, "
        "pas un décompte exhaustif)"
    ]
    if avg_debt is not None:
        parts.append(f"dette publique moyenne des pays surveillés : {float(avg_debt):.1f}% du PIB")
    if top5:
        parts.append(f"pays au score de risque le plus élevé actuellement : {top5_str}")

    return "Synthèse mondiale : " + ", ".join(parts) + "."


# Mots-clés déclenchant l'aperçu global (tous pays confondus) plutôt qu'une
# réponse pays par pays — vérifiés AVANT la recherche de pays dans la question.
GLOBAL_KEYWORDS = [
    "mondial", "mondiale", "monde", "global", "globale", "ensemble des pays",
    "tous les pays", "synthese", "synthèse", "vue d'ensemble", "vue d ensemble",
    "situation generale", "situation générale",
]


# (mots-clés déclencheurs, fonction de réponse) — la question par défaut (aucun mot-clé
# reconnu) déclenche un aperçu combinant économie + dette + risque.
DIMENSION_KEYWORDS: list[tuple[list[str], object]] = [
    (["dette"], _handle_debt),
    (["economie", "économie", "économique", "chomage", "chômage", "inflation", "impot", "impôt"], _handle_economy),
    (["defense", "défense", "militaire", "armee", "armée"], _handle_defense),
    (["industrie", "industriel"], _handle_industry),
    (["risque"], _handle_risk),
    (["conflit", "tension", "guerre", "attaque"], _handle_conflicts),
]

_DEFAULT_HANDLERS = [_handle_economy, _handle_debt, _handle_risk]


def answer_question(question: str) -> str:
    """
    Répond à une question en langage naturel simple à partir des données Neon.

    Reconnaît soit une demande de synthèse mondiale (GLOBAL_KEYWORDS, ex. "vue
    d'ensemble", "situation mondiale") — auquel cas aucun pays n'est requis —, soit
    un pays (nom français/anglais, via mapping.country_mapping) combiné à un
    mot-clé de dimension (dette, économie, défense, industrie, risque, conflits).
    Si aucun mot-clé de dimension n'est reconnu pour un pays donné, renvoie un
    aperçu combiné (économie + dette + risque). Si ni synthèse globale ni pays ne
    sont reconnus, le dit explicitement plutôt que d'inventer une réponse.
    """
    q_lower = question.lower()
    if any(kw in q_lower for kw in GLOBAL_KEYWORDS):
        with get_connection() as conn:
            with conn.cursor() as cur:
                return _handle_global_synthesis(cur)

    country_match = _find_country(question)
    if country_match is None:
        return (
            "Je n'ai pas reconnu de pays dans votre question. "
            'Essayez par exemple : "quelle est la dette de la France ?"'
        )

    iso3, country_name = country_match

    matched_handlers = [
        handler for keywords, handler in DIMENSION_KEYWORDS if any(kw in q_lower for kw in keywords)
    ]
    if not matched_handlers:
        matched_handlers = _DEFAULT_HANDLERS

    answers = []
    with get_connection() as conn:
        with conn.cursor() as cur:
            for handler in matched_handlers:
                result = handler(cur, iso3)
                if result:
                    answers.append(result)

    if not answers:
        return f"Aucune donnée trouvée pour {country_name} sur cette question."

    return f"Pour {country_name} : " + ", ".join(answers) + "."
