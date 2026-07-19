"""Collecte des transferts d'armes (volumes TIV par pays/année) — SIPRI, fichiers statiques."""

import logging

import config
from clients.neon_client import upsert_generic
from clients.sipri_client import parse_top_list

logger = logging.getLogger(__name__)

SIPRI_DIR = config.DATA_DIR / "sipri"


def _find_file(pattern: str):
    matches = sorted(SIPRI_DIR.glob(pattern))
    if not matches:
        logger.warning("collect_arms_transfers: aucun fichier '%s' trouvé dans %s", pattern, SIPRI_DIR)
        return None
    if len(matches) > 1:
        logger.warning(
            "collect_arms_transfers: plusieurs fichiers '%s' trouvés, utilisation du plus récent : %s",
            pattern, matches[-1].name,
        )
    return matches[-1]


def run() -> int:
    rows = []

    export_file = _find_file("export-top*.csv")
    if export_file:
        rows += parse_top_list(export_file, "export")

    import_file = _find_file("import-top*.csv")
    if import_file:
        rows += parse_top_list(import_file, "import")

    return upsert_generic("arms_transfers", rows)


if __name__ == "__main__":
    from logging_config import configure_logging

    configure_logging()
    n = run()
    print(f"{n} ligne(s) envoyée(s) vers arms_transfers")
