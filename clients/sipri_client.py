"""
Parsing des exports CSV "Top List" de la base SIPRI Arms Transfers (gratuite,
téléchargement manuel — https://www.sipri.org/databases/armstransfers).

LIMITE / AJUSTEMENT DE SCHÉMA : les exports CSV librement téléchargeables depuis le
site SIPRI ("Volume of exports/imports of major arms by the top suppliers/recipients")
sont agrégés PAR PAYS ET PAR ANNÉE (valeur TIV totale, toutes destinations/origines et
tous types d'armes confondus) — ils ne contiennent NI le détail bilatéral
exportateur/importateur, NI le type d'arme. Le registre bilatéral détaillé de SIPRI
n'est pas exportable en masse gratuitement (uniquement consultable via leur outil de
recherche en ligne, transfert par transfert). Le schéma `arms_transfers` a donc été
adapté en conséquence : {pays_code, annee, direction, valeur_tiv} plutôt que
{pays_exportateur, pays_importateur, annee, type_arme, quantite} — voir
db/schema.sql.
"""

import csv
import logging
from pathlib import Path

from mapping.country_mapping import COUNTRY_NAME_TO_ISO3

logger = logging.getLogger(__name__)

NAME_COLUMN_INDEX = 3  # colonne "Supplier" ou "Recipient" selon le fichier


def _find_header_row(rows: list[list[str]]) -> int:
    for i, row in enumerate(rows):
        if len(row) > 1 and row[1].strip().startswith("Rank"):
            return i
    raise ValueError("Ligne d'en-tête SIPRI introuvable (colonne 'Rank ...' absente).")


def _year_columns(header_row: list[str]) -> dict[int, int]:
    """col_index -> année, pour les colonnes dont l'en-tête est une année à 4 chiffres."""
    return {
        idx: int(cell.strip())
        for idx, cell in enumerate(header_row)
        if cell.strip().isdigit() and len(cell.strip()) == 4
    }


def parse_top_list(path: Path, direction: str) -> list[dict]:
    """
    Parse un fichier "export-top" ou "import-top" du site SIPRI.

    `direction` : "export" ou "import" — stocké tel quel, sert de discriminant dans
    la base (un même pays apparaît dans les deux classements).

    Retourne une liste de dicts {pays_code, annee, direction, valeur_tiv}. Les lignes
    dont le nom ne correspond à aucun pays connu (organisations internationales,
    entités historiques disparues, acteurs non étatiques...) sont ignorées et
    logguées plutôt que de faire planter le parsing (tolérance demandée pour ce
    module, cf. plan de développement).
    """
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))

    header_idx = _find_header_row(rows)
    year_cols = _year_columns(rows[header_idx])

    results: list[dict] = []
    unmatched: set[str] = set()

    for row in rows[header_idx + 1 :]:
        if len(row) <= NAME_COLUMN_INDEX:
            continue
        name = row[NAME_COLUMN_INDEX].strip()
        if not name or name in ("Others", "Total"):
            continue

        clean_name = name.rstrip("*").strip()
        pays_code = COUNTRY_NAME_TO_ISO3.get(clean_name)
        if pays_code is None:
            unmatched.add(name)
            continue

        for col_idx, year in year_cols.items():
            if col_idx >= len(row):
                continue
            raw_value = row[col_idx].strip()
            if raw_value == "":
                continue  # "" = aucune livraison identifiée (distinct de "0", une vraie donnée)
            try:
                value = float(raw_value)
            except ValueError:
                logger.warning(
                    "sipri_client: valeur non numérique ignorée ('%s', %s, %d) : '%s'",
                    name, direction, year, raw_value,
                )
                continue
            results.append(
                {"pays_code": pays_code, "annee": year, "direction": direction, "valeur_tiv": value}
            )

    if unmatched:
        logger.warning(
            "sipri_client: %d entité(s) non reconnue(s) comme pays, ignorée(s) : %s",
            len(unmatched), sorted(unmatched),
        )

    logger.info(
        "parse_top_list('%s', direction=%s) : %d ligne(s) extraite(s)",
        path.name, direction, len(results),
    )
    return results
