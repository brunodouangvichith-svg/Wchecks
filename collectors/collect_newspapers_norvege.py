"""
Sous-agent dédié "journaux de Norvège" de Joe — pays ajouté à la whitelist
(data/whitelist/whitelist_journaux.md), traité individuellement plutôt que via
le sous-agent générique (voir collectors/_joe_country_subagent.py).
"""

from collectors._joe_country_subagent import run_country_subagent

COUNTRY = "Norvège"
REGION = "Europe & UK"
NEWSPAPERS = [
    {"name": "Aftenposten", "language": "norvégien", "website_url": "https://www.aftenposten.no"},
    {"name": "VG", "language": "norvégien", "website_url": "https://www.vg.no"},
    {"name": "Dagens Næringsliv", "language": "norvégien", "website_url": "https://www.dn.no"},
]


def run() -> int:
    return run_country_subagent(name="newspapers_norvege", country=COUNTRY, region=REGION, newspapers=NEWSPAPERS)


if __name__ == "__main__":
    from logging_config import configure_logging

    configure_logging()
    n = run()
    print(f"{n} ligne(s) envoyée(s) vers national_newspapers_contents ({COUNTRY})")
