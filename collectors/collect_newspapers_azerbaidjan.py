"""
Sous-agent dédié "journaux d'Azerbaïdjan" de Joe — pays ajouté à la whitelist
(data/whitelist/whitelist_journaux.md), traité individuellement plutôt que via
le sous-agent générique (voir collectors/_joe_country_subagent.py).
"""

from collectors._joe_country_subagent import run_country_subagent

COUNTRY = "Azerbaïdjan"
REGION = "Europe de l'Est, Russie & Asie Centrale"
NEWSPAPERS = [
    {"name": "Azernews", "language": "anglais", "website_url": "https://www.azernews.az"},
    {"name": "APA", "language": "azéri", "website_url": "https://apa.az"},
    {"name": "Turan", "language": "russe", "website_url": "https://www.turan.az"},
]


def run() -> int:
    return run_country_subagent(name="newspapers_azerbaidjan", country=COUNTRY, region=REGION, newspapers=NEWSPAPERS)


if __name__ == "__main__":
    from logging_config import configure_logging

    configure_logging()
    n = run()
    print(f"{n} ligne(s) envoyée(s) vers national_newspapers_contents ({COUNTRY})")
