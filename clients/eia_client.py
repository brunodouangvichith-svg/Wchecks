"""
Client pour l'API EIA v2 (clé gratuite : https://www.eia.gov/opendata/register.php).

Un seul client pour :
- les séries simples et documentées (SPR, Brent) via `get_series()` ;
- la production internationale pétrole/gaz, dont les facets (activityId,
  productId, countryRegionId) doivent être découverts dynamiquement via
  `list_facet_values()` avant de construire la requête finale (voir Phase 5b).

Documentation : https://www.eia.gov/opendata/documentation.php
"""

import logging

import requests

import config

logger = logging.getLogger(__name__)

BASE_URL = "https://api.eia.gov/v2"
TIMEOUT_SECONDS = 30


def _require_api_key() -> str:
    if not config.EIA_API_KEY:
        raise RuntimeError(
            "EIA_API_KEY manquant : renseignez le fichier .env (voir .env.example). "
            "Clé gratuite : https://www.eia.gov/opendata/register.php"
        )
    return config.EIA_API_KEY


def get_series(route: str, series_id: str, frequency: str, length: int = 5000) -> list[dict]:
    """
    Récupère une série EIA simple identifiée par `series_id` sur un `route` donné
    (ex. route="petroleum/stoc/wstk", series_id="WCSSTUS1", frequency="weekly").

    Retourne une liste de dicts {"period": str, "value": float | None}, la plus
    récente en premier (tel que renvoyé par l'API triée sur `period` desc).
    """
    url = f"{BASE_URL}/{route.strip('/')}/data/"
    params = {
        "api_key": _require_api_key(),
        "frequency": frequency,
        "data[0]": "value",
        "facets[series][]": series_id,
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "length": length,
    }
    response = requests.get(url, params=params, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    payload = response.json()

    records = payload.get("response", {}).get("data", [])
    rows = [{"period": r.get("period"), "value": r.get("value")} for r in records]
    logger.info("get_series('%s', '%s') : %d valeurs récupérées", route, series_id, len(rows))
    return rows


def list_facet_values(route: str, facet_id: str) -> list[dict]:
    """
    Explore les valeurs possibles d'un facet (ex. facet_id="activityId",
    "productId" ou "countryRegionId") pour un `route` donné (ex. "international").

    À utiliser manuellement/en exploration avant d'écrire les requêtes finales de
    la Phase 5b — voir le facet "activityId"/"productId"/"countryRegionId" de la
    documentation EIA international.
    """
    url = f"{BASE_URL}/{route.strip('/')}/facet/{facet_id}/"
    params = {"api_key": _require_api_key()}
    response = requests.get(url, params=params, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    payload = response.json()

    facets = payload.get("response", {}).get("facets", [])
    logger.info("list_facet_values('%s', '%s') : %d valeur(s)", route, facet_id, len(facets))
    return facets


def get_international_data(
    activity_id: str,
    product_id: str,
    country_region_ids: list[str],
    frequency: str = "monthly",
    unit: str | None = None,
    length: int = 5000,
) -> list[dict]:
    """
    Récupère la production internationale (pétrole ou gaz selon `product_id`) pour
    une liste de countryRegionId, une fois les facets connus (voir list_facet_values).

    IMPORTANT : l'API renvoie une ligne par UNITÉ disponible pour un même
    (period, pays) — ex. le gaz est renvoyé en BCF, BCM, MTOE, QBTU et TJ à la fois.
    Sans filtre `unit`, les lignes se multiplient et la pagination (`length`) peut
    tronquer silencieusement le résultat. Toujours préciser `unit` (voir le champ
    "unit" des lignes retournées par une requête exploratoire sans filtre).

    Retourne une liste de dicts {"period": str, "country_region_id": str, "value": float | None}.
    """
    url = f"{BASE_URL}/international/data/"
    params_list = [
        ("api_key", _require_api_key()),
        ("frequency", frequency),
        ("data[0]", "value"),
        ("facets[activityId][]", activity_id),
        ("facets[productId][]", product_id),
        ("sort[0][column]", "period"),
        ("sort[0][direction]", "desc"),
        ("length", length),
    ]
    if unit:
        params_list.append(("facets[unit][]", unit))
    params_list += [("facets[countryRegionId][]", region_id) for region_id in country_region_ids]

    response = requests.get(url, params=params_list, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    payload = response.json()

    records = payload.get("response", {}).get("data", [])
    rows = [
        {
            "period": r.get("period"),
            "country_region_id": r.get("countryRegionId") or r.get("country-name") or r.get("countryRegion"),
            "value": r.get("value"),
        }
        for r in records
    ]
    logger.info(
        "get_international_data(activity=%s, product=%s) : %d valeurs récupérées",
        activity_id, product_id, len(rows),
    )
    return rows
