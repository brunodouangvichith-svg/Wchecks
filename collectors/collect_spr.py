"""Collecte de la réserve stratégique de pétrole US (SPR) — EIA, série WCSSTUS1."""

import logging

from clients.eia_client import get_series
from clients.neon_client import upsert_generic

logger = logging.getLogger(__name__)


def run() -> int:
    data = get_series("petroleum/stoc/wstk", "WCSSTUS1", frequency="weekly")
    rows = [
        {"date": d["period"], "valeur_milliers_barils": float(d["value"])}
        for d in data
        if d["value"] is not None
    ]
    return upsert_generic("spr_stocks", rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    n = run()
    print(f"{n} ligne(s) envoyée(s) vers spr_stocks")
