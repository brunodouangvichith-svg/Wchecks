"""Collecte des conflits énergétiques géolocalisés — GDELT DOC API."""

import logging

import config
from clients.gdelt_client import search_articles
from clients.neon_client import upsert_generic

logger = logging.getLogger(__name__)


def run() -> int:
    rows = search_articles(config.GDELT_KEYWORDS_CONFLICTS)
    return upsert_generic("energy_conflicts", rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    n = run()
    print(f"{n} ligne(s) envoyée(s) vers energy_conflicts")
