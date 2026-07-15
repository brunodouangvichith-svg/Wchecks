"""
Client générique pour l'API World Bank (gratuite, sans clé).

Un seul point d'entrée, `get_indicator()`, réutilisé par tous les collectors
World Bank (économie, budget défense, industrie — la dette utilise désormais
le FMI, voir clients/imf_client.py) : seul l'indicateur demandé change d'un
collector à l'autre.

Documentation : https://datahelpdesk.worldbank.org/knowledgebase/articles/889392

Par défaut (aucune liste de pays fournie), interroge TOUS les pays
("country/all/...") plutôt que la seule sélection config.MONITORED_COUNTRIES :
la source est gratuite et couvre ~217 pays réels sans coût ni limite
supplémentaire, donc pas de raison de restreindre à la sélection de pays "à
risque" pensée pour les dimensions géopolitiques/énergétiques. Le endpoint
`country/all` renvoie aussi ~78 agrégats régionaux (ex. "World", "OECD
members") sous des codes qui ressemblent à des ISO3 — exclus via le endpoint
`/country`, qui distingue les vrais pays des agrégats par `region.value`.
"""

import logging
import time

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.worldbank.org/v2"
TIMEOUT_SECONDS = 30
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 5


def _get_with_retry(url: str, params: dict) -> dict:
    """Requête GET avec retry/backoff sur erreur transitoire.

    Interroger `country/all` (~7 pages par indicateur, contre 1 page pour la
    courte liste MONITORED_COUNTRIES d'origine) s'est révélé occasionnellement
    lent/instable côté serveur World Bank (timeouts, et même un 400 Bad Request
    isolé observé sur une requête identique à une requête qui venait de réussir
    quelques secondes avant) — traité comme transitoire plutôt que comme une
    requête réellement malformée, un simple retry suffisant en pratique.
    """
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, params=params, timeout=TIMEOUT_SECONDS)
            response.raise_for_status()
            return response.json()
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as exc:
            last_error = exc
            logger.warning(
                "World Bank : erreur transitoire (tentative %d/%d) : %s",
                attempt, MAX_RETRIES, exc,
            )
            time.sleep(RETRY_BACKOFF_SECONDS)
    raise last_error


def _get_real_country_codes() -> set[str]:
    """Codes ISO3 des vrais pays (exclut les agrégats régionaux du endpoint
    `/country`, identifiés par `region.value == "Aggregates"`)."""
    payload = _get_with_retry(f"{BASE_URL}/country", {"format": "json", "per_page": 400})
    data = payload[1] if isinstance(payload, list) and len(payload) > 1 and payload[1] else []
    return {c["id"] for c in data if c.get("region", {}).get("value") != "Aggregates"}


def get_indicator(
    indicator_code: str,
    countries: list[str] | None = None,
    date_range: str = "2000:2025",
) -> list[dict]:
    """
    Récupère les valeurs d'un indicateur World Bank pour une liste de pays (tous
    les pays réels si `countries` est omis — voir docstring du module).

    Retourne une liste de dicts {"pays_code": str, "annee": int, "valeur": float | None},
    en ignorant les entrées sans valeur numérique (pays sans donnée publiée pour l'année).
    """
    country_path = ";".join(countries) if countries else "all"
    url = f"{BASE_URL}/country/{country_path}/indicator/{indicator_code}"

    records: list[dict] = []
    page = 1
    while True:
        params = {"format": "json", "per_page": 1000, "date": date_range, "page": page}
        payload = _get_with_retry(url, params)

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

    if countries is None:
        real_countries = _get_real_country_codes()
        before = len(records)
        records = [r for r in records if r["pays_code"] in real_countries]
        logger.info(
            "get_indicator('%s') : %d agrégat(s) régional/régionaux exclus",
            indicator_code, before - len(records),
        )

    logger.info("get_indicator('%s') : %d valeurs récupérées", indicator_code, len(records))
    return records
