"""
Sous-agent "journaux nationaux" de Joe (chef d'orchestre) : lit
national_newspapers, scrape la page d'accueil de chaque journal, et enregistre
un résumé + thème (intégrité vérifiée par Joe) dans
national_newspapers_contents. Logique commune factorisée dans
collectors/_joe_subagent.py — voir ce module pour le détail (orchestration
autonome du volume par exécution, contrôle d'intégrité anti-hallucination).
"""

import logging

from collectors._joe_subagent import run_subagent

logger = logging.getLogger(__name__)

_DIRECTORY_COLUMNS = ["name", "country", "region", "language", "website_url"]


def run() -> int:
    return run_subagent(
        name="national_newspapers",
        directory_table="national_newspapers",
        contents_table="national_newspapers_contents",
        directory_columns=_DIRECTORY_COLUMNS,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    n = run()
    print(f"{n} ligne(s) envoyée(s) vers national_newspapers_contents")
