"""Collecte du prix du Brent crude spot — EIA, série RBRTE."""

import logging

from clients.eia_client import get_series
from clients.neon_client import upsert_generic

logger = logging.getLogger(__name__)


def run() -> int:
    data = get_series("petroleum/pri/spt", "RBRTE", frequency="daily")
    rows = [
        {"date": d["period"], "prix_usd_baril": float(d["value"])}
        for d in data
        if d["value"] is not None
    ]
    return upsert_generic("brent_prices", rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    n = run()
    print(f"{n} ligne(s) envoyée(s) vers brent_prices")
