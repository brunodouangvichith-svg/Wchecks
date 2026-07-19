"""
Collecte de la production de minerais et métaux stratégiques par pays — USGS,
fichiers Excel statiques déposés manuellement dans data/usgs/.

Déclenchement manuel uniquement (`python cli.py --minerals-refresh`), pas de
fréquence dans le scheduler — voir config.FREQUENCIES_MINUTES.

LIMITE : "rang_mondial" (prévu au schéma initial) n'est PAS renseigné ici. Les
fichiers déposés sont des synthèses RÉGIONALES (Afrique, Asie, Europe, Amérique
latine) : calculer un rang à partir de leur seule union donnerait un classement
partiel présenté à tort comme mondial. Plutôt que d'approximer, le champ est
omis — voir la même logique déjà appliquée à la tonalité GDELT et aux prix de
l'énergie par pays (dimension 10, non intégrée).
"""

import logging
from pathlib import Path

import config
from clients.neon_client import upsert_generic
from clients.usgs_client import parse_yearbook_file

logger = logging.getLogger(__name__)

USGS_DIR = config.DATA_DIR / "usgs"


def run() -> int:
    files = sorted(USGS_DIR.glob("*.xlsx"))
    if not files:
        logger.warning("collect_minerals: aucun fichier .xlsx trouvé dans %s", USGS_DIR)
        return 0

    rows = []
    for path in files:
        rows += parse_yearbook_file(path)

    rows = [r for r in rows if r["matiere_premiere"] in config.STRATEGIC_MINERALS]
    return upsert_generic("minerals_production", rows)


if __name__ == "__main__":
    from logging_config import configure_logging

    configure_logging()
    n = run()
    print(f"{n} ligne(s) envoyée(s) vers minerals_production")
