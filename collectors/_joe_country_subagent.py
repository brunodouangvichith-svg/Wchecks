"""
Sous-agent dédié "1 pays" de Joe (chef d'orchestre) — variante allégée de
_joe_subagent.py pour les pays traités individuellement plutôt que via le
répertoire partagé (voir collectors/collect_newspapers_<pays>.py, un par pays
ajouté depuis data/whitelist/whitelist_journaux.md) : chaque exécution ne
couvre qu'une poignée de journaux fixes (2-3), donc pas d'arbitrage de volume
nécessaire (contrairement à _joe_subagent.run_subagent) — toujours traités en
une fois. Même contrôle d'intégrité anti-hallucination que les autres
sous-agents (clients.joe_agent.analyze_homepages_batch).

Ces pays restent listés dans national_newspapers (annuaire/affichage), mais
sont explicitement EXCLUS du sous-agent générique
(collect_national_newspapers_contents, voir _EXCLUDED_COUNTRIES dans
_joe_subagent.py) pour ne pas les traiter deux fois (double scraping, double
coût Gemini sur un quota quotidien déjà partagé).
"""

from datetime import datetime, timezone

from clients.article_scraper import verify_and_extract
from clients.joe_agent import analyze_homepages_batch
from clients.neon_client import upsert_generic
from logging_config import get_subagent_logger


def run_country_subagent(name: str, country: str, region: str, newspapers: list[dict]) -> int:
    """
    `newspapers` : liste de {"name", "language", "website_url"} pour UN seul
    pays (voir data/whitelist/whitelist_journaux.md).

    Scrape chaque URL, analyse par lot (contrôle d'intégrité "fiable" inclus),
    et enregistre dans national_newspapers_contents — même table que le
    sous-agent générique, donc le panneau "Articles analysés par Joe" et sa
    recherche fonctionnent sans changement, quel que soit le sous-agent qui a
    produit la ligne.

    Retourne le nombre de lignes effectivement enregistrées.
    """
    logger = get_subagent_logger(name)

    texts = []
    for newspaper in newspapers:
        verified, text = verify_and_extract(newspaper["website_url"])
        texts.append(text if verified else None)

    analyses = analyze_homepages_batch(texts)

    refreshed_at = datetime.now(timezone.utc).isoformat()
    rows = []
    for newspaper, analysis in zip(newspapers, analyses):
        if not analysis:
            continue
        rows.append(
            {
                "name": newspaper["name"],
                "country": country,
                "region": region,
                "language": newspaper["language"],
                "website_url": newspaper["website_url"],
                "content": analysis["content"],
                "theme": analysis["theme"],
                "updated_at": refreshed_at,
            }
        )

    logger.info(
        "%s : %d/%d journal(aux) analysé(s) avec succès (intégrité vérifiée)", name, len(rows), len(newspapers)
    )
    return upsert_generic("national_newspapers_contents", rows)
