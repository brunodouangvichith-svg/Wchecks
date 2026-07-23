"""
Sous-agent dédié "journaux de Libye" de Joe — pays ajouté à la whitelist
(data/whitelist/whitelist_journaux.md), traité individuellement plutôt que via
le sous-agent générique (voir collectors/_joe_country_subagent.py).
"""

from collectors._joe_country_subagent import run_country_subagent

COUNTRY = "Libye"
REGION = "Afrique"
NEWSPAPERS = [
    {"name": "Libya Observer", "language": "anglais", "website_url": "https://www.libyaobserver.ly"},
    {"name": "Libya Herald", "language": "anglais", "website_url": "https://www.libyaherald.com"},
]


def run() -> int:
    return run_country_subagent(name="newspapers_libye", country=COUNTRY, region=REGION, newspapers=NEWSPAPERS)


if __name__ == "__main__":
    from logging_config import configure_logging

    configure_logging()
    n = run()
    print(f"{n} ligne(s) envoyée(s) vers national_newspapers_contents ({COUNTRY})")
