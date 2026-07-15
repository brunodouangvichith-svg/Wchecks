"""
Collecte de la situation économique des pays — World Bank :
impôts (% PIB), chômage (%), inflation (%).

Les trois indicateurs sont récupérés séparément puis fusionnés par
(pays_code, annee) car ils vivent dans la même ligne côté Postgres.
"""

import logging
from collections import defaultdict

import config
from clients.neon_client import upsert_generic
from clients.worldbank_client import get_indicator

logger = logging.getLogger(__name__)


def run() -> int:
    merged: dict[tuple[str, int], dict] = defaultdict(dict)

    tax = get_indicator(config.WORLDBANK_INDICATORS["tax_pct_gdp"])
    for d in tax:
        merged[(d["pays_code"], d["annee"])]["impots_pct_pib"] = d["valeur"]

    unemployment = get_indicator(config.WORLDBANK_INDICATORS["unemployment_pct"])
    for d in unemployment:
        merged[(d["pays_code"], d["annee"])]["chomage_pct"] = d["valeur"]

    inflation = get_indicator(config.WORLDBANK_INDICATORS["inflation_pct"])
    for d in inflation:
        merged[(d["pays_code"], d["annee"])]["inflation_pct"] = d["valeur"]

    rows = [
        {"pays_code": pays_code, "annee": annee, **values}
        for (pays_code, annee), values in merged.items()
    ]
    return upsert_generic("country_economy", rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    n = run()
    print(f"{n} ligne(s) envoyée(s) vers country_economy")
