"""
Collecte de la dette publique des pays (% du PIB) — IMF DataMapper, indicateur
WEO GGXWDG_NGDP (dette publique générale).

Remplace l'indicateur World Bank GC.DOD.TOTL.GD.ZS initialement prévu : sa
couverture s'est révélée trop incomplète pour les économies avancées (voir
clients/imf_client.py pour le détail).
"""

import logging

import config
from clients.imf_client import get_general_government_debt
from clients.neon_client import upsert_generic

logger = logging.getLogger(__name__)


def run() -> int:
    data = get_general_government_debt()
    rows = [
        {"pays_code": d["pays_code"], "annee": d["annee"], "dette_pct_pib": d["valeur"]}
        for d in data
        if d["pays_code"] in config.MONITORED_COUNTRIES
    ]
    return upsert_generic("country_debt", rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    n = run()
    print(f"{n} ligne(s) envoyée(s) vers country_debt")
