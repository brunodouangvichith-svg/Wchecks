"""Collecte des déclarations officielles des chancelleries/institutions — flux RSS.

Pas de filtre par mot-clé (voir clients/rss_client.py) : les flux suivis sont
déjà une sélection restreinte de 2-3 institutions, filtrer en plus par
vocabulaire énergie/conflit ne laissait passer presque aucune entrée (les
titres institutionnels/diplomatiques n'utilisent que rarement ces mots
explicitement).
"""

import logging

import config
from clients.rss_client import fetch_statements
from clients.neon_client import upsert_generic

logger = logging.getLogger(__name__)


def run() -> int:
    rows = fetch_statements(config.RSS_FEEDS)
    return upsert_generic("official_statements", rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    n = run()
    print(f"{n} ligne(s) envoyée(s) vers official_statements")
