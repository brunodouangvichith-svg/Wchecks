"""
Sous-agent "organisations internationales" de Joe (chef d'orchestre) : lit
international_organizations, scrape la page d'accueil de chaque organisation,
et enregistre un résumé + thème (intégrité vérifiée par Joe) dans
international_organizations_contents. Logique commune factorisée dans
collectors/_joe_subagent.py — voir ce module pour le détail (orchestration
autonome du volume par exécution, contrôle d'intégrité anti-hallucination).
"""

import logging

from collectors._joe_subagent import run_subagent

logger = logging.getLogger(__name__)

_DIRECTORY_COLUMNS = ["name", "category", "role", "key_resources", "region", "website_url"]


def run() -> int:
    return run_subagent(
        name="international_organizations",
        directory_table="international_organizations",
        contents_table="international_organizations_contents",
        directory_columns=_DIRECTORY_COLUMNS,
    )


if __name__ == "__main__":
    from logging_config import configure_logging

    configure_logging()
    n = run()
    print(f"{n} ligne(s) envoyée(s) vers international_organizations_contents")
