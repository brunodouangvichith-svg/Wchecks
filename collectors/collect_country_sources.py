"""
Découvre, via l'agent Joe (LLM Gemini), les principaux journaux nationaux et
le site officiel de référence de chaque pays surveillé
(config.MONITORED_COUNTRIES), puis tente de localiser un flux RSS pour
chaque source (clients/rss_client.discover_feed_url).

Rafraîchi peu fréquemment (voir config.FREQUENCIES_MINUTES["country_sources"]) :
ces informations (noms/URL de journaux et sites gouvernementaux) changent très
rarement, contrairement aux articles eux-mêmes (voir collect_country_news.py).
"""

import logging

import config
from clients.joe_agent import discover_country_sources
from clients.neon_client import upsert_generic
from clients.rss_client import discover_feed_url
from mapping.country_mapping import COUNTRY_NAME_TO_ISO3

logger = logging.getLogger(__name__)

# ISO3 -> nom de pays lisible pour le prompt Gemini. COUNTRY_NAME_TO_ISO3 est
# construit nom anglais d'abord, puis alias (français, variantes GDELT/USGS...)
# ajoutés ensuite sans écraser les entrées existantes — setdefault() en
# itérant dans l'ordre garantit de garder le nom anglais canonique plutôt
# qu'un alias arbitraire.
_ISO3_TO_NAME: dict[str, str] = {}
for _name, _iso3 in COUNTRY_NAME_TO_ISO3.items():
    _ISO3_TO_NAME.setdefault(_iso3, _name)


def run() -> int:
    rows = []
    for iso3 in config.MONITORED_COUNTRIES:
        country_name = _ISO3_TO_NAME.get(iso3, iso3)
        sources = discover_country_sources(country_name)
        if not sources:
            logger.info("collect_country_sources: aucune source découverte pour %s (%s)", country_name, iso3)
            continue
        for src in sources:
            feed_url = discover_feed_url(src["url"])
            rows.append(
                {
                    "pays_code": iso3,
                    "nom_source": src["nom"],
                    "type_source": src.get("type"),
                    "url": src["url"],
                    "feed_url": feed_url,
                }
            )

    logger.info(
        "collect_country_sources : %d source(s) découverte(s) pour %d pays surveillé(s)",
        len(rows), len(config.MONITORED_COUNTRIES),
    )
    return upsert_generic("country_sources", rows)


if __name__ == "__main__":
    from logging_config import configure_logging

    configure_logging()
    n = run()
    print(f"{n} ligne(s) envoyée(s) vers country_sources")
