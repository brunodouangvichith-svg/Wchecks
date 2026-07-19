"""Collecte du trafic maritime (tankers) dans les zones stratégiques — AISstream.io."""

import logging

from clients.aisstream_client import capture_tanker_snapshot
from clients.neon_client import upsert_generic

logger = logging.getLogger(__name__)


def run() -> int:
    rows = capture_tanker_snapshot()
    return upsert_generic("maritime_traffic", rows)


if __name__ == "__main__":
    from logging_config import configure_logging

    configure_logging()
    n = run()
    print(f"{n} ligne(s) envoyée(s) vers maritime_traffic")
