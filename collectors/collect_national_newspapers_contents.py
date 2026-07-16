"""
Lit l'annuaire national_newspapers et scrape la page d'accueil de chaque
journal une fois par jour, pour en tirer un court résumé + thème via l'agent
Joe (analyse groupée, voir clients/joe_agent.analyze_homepages_batch).

Le résultat ÉCRASE la ligne existante pour ce journal (contrainte UNIQUE
website_url sur national_newspapers_contents) — ne garde que l'état du jour,
pas un historique (voir db/schema.sql).
"""

import logging

from clients.article_scraper import verify_and_extract
from clients.joe_agent import analyze_homepages_batch
from clients.neon_client import get_connection, upsert_generic

logger = logging.getLogger(__name__)


def run() -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name, country, region, language, website_url FROM national_newspapers")
            newspapers = cur.fetchall()

    texts = []
    for _name, _country, _region, _language, url in newspapers:
        verified, text = verify_and_extract(url)
        texts.append(text if verified else None)

    analyses = analyze_homepages_batch(texts)

    rows = []
    for (name, country, region, language, url), analysis in zip(newspapers, analyses):
        if not analysis:
            continue
        rows.append(
            {
                "name": name,
                "country": country,
                "region": region,
                "language": language,
                "website_url": url,
                "content": analysis["content"],
                "theme": analysis["theme"],
            }
        )

    logger.info(
        "collect_national_newspapers_contents : %d/%d journal(aux) analysé(s) avec succès",
        len(rows), len(newspapers),
    )
    return upsert_generic("national_newspapers_contents", rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    n = run()
    print(f"{n} ligne(s) envoyée(s) vers national_newspapers_contents")
