"""Collecte des tensions sociales / manifestations géolocalisées — GDELT DOC API."""

import logging

import config
from clients.gdelt_client import search_articles
from clients.neon_client import upsert_generic

logger = logging.getLogger(__name__)


def run() -> int:
    rows = search_articles(config.GDELT_KEYWORDS_SOCIAL_TENSIONS)
    return upsert_generic("social_tensions", rows)


if __name__ == "__main__":
    from logging_config import configure_logging

    configure_logging()
    n = run()
    print(f"{n} ligne(s) envoyée(s) vers social_tensions")
