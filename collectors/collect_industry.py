"""Collecte de la production industrielle par pays (% du PIB) — World Bank NV.IND.TOTL.ZS."""

import logging

import config
from clients.neon_client import upsert_generic
from clients.worldbank_client import get_indicator

logger = logging.getLogger(__name__)


def run() -> int:
    data = get_indicator(config.WORLDBANK_INDICATORS["industry_pct_gdp"])
    rows = [
        {
            "pays_code": d["pays_code"],
            "annee": d["annee"],
            "production_industrielle_pct_pib": d["valeur"],
        }
        for d in data
    ]
    return upsert_generic("country_industry", rows)


if __name__ == "__main__":
    from logging_config import configure_logging

    configure_logging()
    n = run()
    print(f"{n} ligne(s) envoyée(s) vers country_industry")
