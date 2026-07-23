"""
Sous-agent dédié "journaux du Soudan" de Joe — pays ajouté à la whitelist
(data/whitelist/whitelist_journaux.md), traité individuellement plutôt que via
le sous-agent générique (voir collectors/_joe_country_subagent.py).
"""

from collectors._joe_country_subagent import run_country_subagent

COUNTRY = "Soudan"
REGION = "Afrique"
NEWSPAPERS = [
    {"name": "Sudan Tribune", "language": "anglais", "website_url": "https://www.sudantribune.com"},
    {"name": "Al-Sudani", "language": "arabe", "website_url": "https://www.alsudani.sd"},
]


def run() -> int:
    return run_country_subagent(name="newspapers_soudan", country=COUNTRY, region=REGION, newspapers=NEWSPAPERS)


if __name__ == "__main__":
    from logging_config import configure_logging

    configure_logging()
    n = run()
    print(f"{n} ligne(s) envoyée(s) vers national_newspapers_contents ({COUNTRY})")
