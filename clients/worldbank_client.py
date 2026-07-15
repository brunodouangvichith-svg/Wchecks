"""
Client générique pour l'API World Bank (gratuite, sans clé).

Un seul point d'entrée, `get_indicator()`, réutilisé par tous les collectors
World Bank (dette, économie, budget défense, industrie) : seul l'indicateur
demandé change d'un collector à l'autre.

Documentation : https://datahelpdesk.worldbank.org/knowledgebase/articles/889392
"""

import logging

import requests

import config

logger = logging.getLogger(__name__)

BASE_URL = "https://api.worldbank.org/v2"
TIMEOUT_SECONDS = 30


def get_indicator(
    indicator_code: str,
    countries: list[str] | None = None,
    date_range: str = "2000:2025",
) -> list[dict]:
    """
    Récupère les valeurs d'un indicateur World Bank pour une liste de pays.

    Retourne une liste de dicts {"pays_code": str, "annee": int, "valeur": float | None},
    en ignorant les entrées sans valeur numérique (pays sans donnée publiée pour l'année).
    """
    countries = countries or config.MONITORED_COUNTRIES
    country_path = ";".join(countries)
    url = f"{BASE_URL}/country/{country_path}/indicator/{indicator_code}"

    records: list[dict] = []
    page = 1
    while True:
        params = {"format": "json", "per_page": 1000, "date": date_range, "page": page}
        response = requests.get(url, params=params, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()

        if not isinstance(payload, list) or len(payload) < 2 or payload[1] is None:
            logger.warning("Réponse World Bank inattendue pour '%s' (page %d) : %s", indicator_code, page, payload)
            break

        metadata, data = payload[0], payload[1]
        for entry in data:
            value = entry.get("value")
            iso3 = entry.get("countryiso3code")
            year = entry.get("date")
            if value is None or not iso3 or not year:
                continue
            records.append({"pays_code": iso3, "annee": int(year), "valeur": float(value)})

        if page >= metadata.get("pages", 1):
            break
        page += 1

    logger.info("get_indicator('%s') : %d valeurs récupérées", indicator_code, len(records))
    return records
