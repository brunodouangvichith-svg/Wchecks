"""Collecte des déclarations officielles des chancelleries/institutions — flux RSS."""

import logging

import config
from clients.rss_client import fetch_statements
from clients.neon_client import upsert_generic

logger = logging.getLogger(__name__)


def run() -> int:
    rows = fetch_statements(config.RSS_FEEDS, config.RSS_KEYWORDS)
    return upsert_generic("official_statements", rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    n = run()
    print(f"{n} ligne(s) envoyée(s) vers official_statements")
