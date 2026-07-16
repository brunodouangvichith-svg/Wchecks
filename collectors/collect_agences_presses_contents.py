"""
Lit l'annuaire agences_presses et scrape la page d'accueil de chaque agence
2 à 3 fois par jour, pour en tirer un court résumé + thème via l'agent Joe
(analyse groupée par lots, voir clients/joe_agent.analyze_homepages_batch —
le tier gratuit de Gemini plafonne à 15 requêtes/minute et 500/jour, d'où le
découpage en plusieurs groupes de requêtes plutôt qu'un appel par agence).

Le résultat ÉCRASE la ligne existante pour cette agence (contrainte UNIQUE
website_url sur agences_presses_contents) — ne garde que le dernier état
collecté, pas un historique (voir db/schema.sql).
"""

import logging

from clients.article_scraper import verify_and_extract
from clients.joe_agent import analyze_homepages_batch
from clients.neon_client import get_connection, upsert_generic

logger = logging.getLogger(__name__)


def run() -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT name, category, country, specialty, website_url, region FROM agences_presses"
            )
            agencies = cur.fetchall()

    texts = []
    for _name, _category, _country, _specialty, url, _region in agencies:
        verified, text = verify_and_extract(url)
        texts.append(text if verified else None)

    # Découpage en plusieurs groupes de requêtes Gemini (voir
    # clients.joe_agent.TRANSLATE_BATCH_SIZE), pas un appel par agence.
    analyses = analyze_homepages_batch(texts)

    rows = []
    for (name, category, country, specialty, url, region), analysis in zip(agencies, analyses):
        if not analysis:
            continue
        rows.append(
            {
                "name": name,
                "category": category,
                "country": country,
                "specialty": specialty,
                "website_url": url,
                "region": region,
                "content": analysis["content"],
                "theme": analysis["theme"],
            }
        )

    logger.info(
        "collect_agences_presses_contents : %d/%d agence(s) analysée(s) avec succès",
        len(rows), len(agencies),
    )
    return upsert_generic("agences_presses_contents", rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    n = run()
    print(f"{n} ligne(s) envoyée(s) vers agences_presses_contents")
