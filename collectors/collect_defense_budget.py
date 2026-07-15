"""Collecte du budget défense des pays (% du PIB) — World Bank MS.MIL.XPND.GD.ZS."""

import logging

import config
from clients.neon_client import upsert_generic
from clients.worldbank_client import get_indicator

logger = logging.getLogger(__name__)


def run() -> int:
    data = get_indicator(config.WORLDBANK_INDICATORS["defense_budget_pct_gdp"])
    rows = [
        {"pays_code": d["pays_code"], "annee": d["annee"], "budget_pct_pib": d["valeur"]}
        for d in data
    ]
    return upsert_generic("defense_budget", rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    n = run()
    print(f"{n} ligne(s) envoyée(s) vers defense_budget")
