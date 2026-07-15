"""Collecte des notations de crédit souveraines (S&P, Fitch, Moody's) — Wikipédia."""

import logging

from clients.neon_client import upsert_generic
from clients.wikipedia_client import get_credit_ratings

logger = logging.getLogger(__name__)


def run() -> int:
    rows = get_credit_ratings()
    return upsert_generic("credit_ratings", rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    n = run()
    print(f"{n} ligne(s) envoyée(s) vers credit_ratings")
