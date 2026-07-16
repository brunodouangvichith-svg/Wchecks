"""
Lit l'annuaire international_organizations et scrape la page d'accueil de
chaque organisation une fois par jour, pour en tirer un court résumé + thème
via l'agent Joe (analyse groupée par lots, voir
clients/joe_agent.analyze_homepages_batch — le tier gratuit de Gemini
plafonne à 15 requêtes/minute et 500/jour, d'où le découpage en plusieurs
groupes de requêtes plutôt qu'un appel par organisation).

Le résultat ÉCRASE la ligne existante pour cette organisation (contrainte
UNIQUE website_url sur international_organizations_contents) — ne garde que
l'état du jour, pas un historique (voir db/schema.sql).
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
                "SELECT name, category, role, key_resources, website_url, region "
                "FROM international_organizations"
            )
            organizations = cur.fetchall()

    texts = []
    for _name, _category, _role, _key_resources, url, _region in organizations:
        verified, text = verify_and_extract(url)
        texts.append(text if verified else None)

    # Découpage en plusieurs groupes de requêtes Gemini (voir
    # clients.joe_agent.TRANSLATE_BATCH_SIZE), pas un appel par organisation.
    analyses = analyze_homepages_batch(texts)

    rows = []
    for (name, category, role, key_resources, url, region), analysis in zip(organizations, analyses):
        if not analysis:
            continue
        rows.append(
            {
                "name": name,
                "category": category,
                "role": role,
                "key_resources": key_resources,
                "website_url": url,
                "region": region,
                "content": analysis["content"],
                "theme": analysis["theme"],
            }
        )

    logger.info(
        "collect_international_organizations_contents : %d/%d organisation(s) analysée(s) avec succès",
        len(rows), len(organizations),
    )
    return upsert_generic("international_organizations_contents", rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    n = run()
    print(f"{n} ligne(s) envoyée(s) vers international_organizations_contents")
