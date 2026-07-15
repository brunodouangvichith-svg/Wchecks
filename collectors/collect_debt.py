"""Collecte de la dette publique des pays (% du PIB) — World Bank GC.DOD.TOTL.GD.ZS."""

import logging

import config
from clients.neon_client import upsert_generic
from clients.worldbank_client import get_indicator

logger = logging.getLogger(__name__)


def run() -> int:
    data = get_indicator(config.WORLDBANK_INDICATORS["country_debt"])
    rows = [
        {"pays_code": d["pays_code"], "annee": d["annee"], "dette_pct_pib": d["valeur"]}
        for d in data
    ]
    return upsert_generic("country_debt", rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    n = run()
    print(f"{n} ligne(s) envoyée(s) vers country_debt")
