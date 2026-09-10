"""
Sous-agent "découverte" de George : capacité d'apprentissage au fil de l'eau,
sur le modèle de collect_country_sources.py, mais pour élargir
national_newspapers — la liste vue par les autres sous-agents de George
(collect_national_newspapers_contents.py, collect_newspapers_<pays>.py) —
au lieu de la laisser figée sur data/whitelist/whitelist_journaux.md /
scripts/populate_national_newspapers.py.

Pour chaque pays déjà présent dans national_newspapers, demande au LLM
(clients.joe_agent.discover_national_newspapers) des journaux nationaux
majeurs qui n'y figurent pas encore. Chaque URL découverte est vérifiée
(clients.article_scraper.verify_and_extract) avant d'être enregistrée — même
garde-fou anti-hallucination que le reste de George/Joe (voir
_joe_subagent.py) : un journal halluciné ou dont le site ne répond pas n'est
jamais ajouté.
"""

import logging

from clients.article_scraper import verify_and_extract
from clients.joe_agent import discover_national_newspapers
from clients.neon_client import get_grouped, upsert_generic

logger = logging.getLogger(__name__)


def run() -> int:
    names_by_country = get_grouped("national_newspapers", "country", "name")
    region_by_country = get_grouped("national_newspapers", "country", "region")

    rows = []
    for country, known_names in names_by_country.items():
        candidates = discover_national_newspapers(country, known_names)
        if not candidates:
            continue
        region = region_by_country[country][0]
        for candidate in candidates:
            verified, _ = verify_and_extract(candidate["website_url"])
            if not verified:
                logger.info(
                    "collect_newspaper_discovery: '%s' (%s) ignoré, site inaccessible",
                    candidate["name"], country,
                )
                continue
            rows.append(
                {
                    "name": candidate["name"],
                    "country": country,
                    "region": region,
                    "language": candidate["language"],
                    "website_url": candidate["website_url"],
                    "political_leaning": candidate["political_leaning"],
                }
            )

    logger.info(
        "collect_newspaper_discovery : %d nouveau(x) journal(aux) découvert(s) et vérifié(s) sur %d pays",
        len(rows), len(names_by_country),
    )
    return upsert_generic("national_newspapers", rows)


if __name__ == "__main__":
    from logging_config import configure_logging

    configure_logging()
    n = run()
    print(f"{n} nouveau(x) journal(aux) ajouté(s) à national_newspapers")
