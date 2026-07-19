"""
Sous-agent "agences de presse" de Joe (chef d'orchestre) : lit
agences_presses, scrape la page d'accueil de chaque agence, et enregistre un
résumé + thème (intégrité vérifiée par Joe) dans agences_presses_contents.
Logique commune factorisée dans collectors/_joe_subagent.py — voir ce module
pour le détail (orchestration autonome du volume par exécution, contrôle
d'intégrité anti-hallucination).
"""

import logging

from collectors._joe_subagent import run_subagent

logger = logging.getLogger(__name__)

_DIRECTORY_COLUMNS = ["name", "category", "country", "specialty", "region", "website_url"]


def run() -> int:
    return run_subagent(
        name="agences_presses",
        directory_table="agences_presses",
        contents_table="agences_presses_contents",
        directory_columns=_DIRECTORY_COLUMNS,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    n = run()
    print(f"{n} ligne(s) envoyée(s) vers agences_presses_contents")
