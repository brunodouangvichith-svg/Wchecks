"""
Lit les flux RSS découverts pour les sources par pays (country_sources, voir
collect_country_sources.py) et stocke leurs articles dans country_news —
même traitement que les déclarations officielles (scraping + vérification +
résumé extractif, voir clients/rss_client.py et clients/article_scraper.py).

LIMITE : ne couvre que les sources où un flux RSS a pu être découvert
(country_sources.feed_url IS NOT NULL) — beaucoup de sites institutionnels
(portails gouvernementaux notamment) n'en exposent aucun et restent dans
l'annuaire sans lecture automatisée.
"""

import logging

from clients.neon_client import get_connection, upsert_generic
from clients.rss_client import fetch_feed_entries

logger = logging.getLogger(__name__)


def _sources_with_feed(cur) -> list[tuple[str, str, str]]:
    cur.execute(
        "SELECT pays_code, nom_source, feed_url FROM country_sources WHERE feed_url IS NOT NULL"
    )
    return cur.fetchall()


def run() -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            sources = _sources_with_feed(cur)

    rows = []
    for pays_code, source_nom, feed_url in sources:
        try:
            entries = fetch_feed_entries(feed_url)
        except Exception:
            logger.exception(
                "collect_country_news: échec de lecture du flux '%s' (%s, %s)",
                source_nom, pays_code, feed_url,
            )
            continue

        for entry in entries:
            rows.append(
                {
                    "pays_code": pays_code,
                    "source_nom": source_nom,
                    "url": entry["url"],
                    "date": entry["date"],
                    "titre": entry["titre"],
                    "resume": entry["resume"],
                    "source_verifiee": entry["source_verifiee"],
                }
            )

    logger.info(
        "collect_country_news : %d article(s) sur %d source(s) avec flux RSS",
        len(rows), len(sources),
    )
    return upsert_generic("country_news", rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    n = run()
    print(f"{n} ligne(s) envoyée(s) vers country_news")
