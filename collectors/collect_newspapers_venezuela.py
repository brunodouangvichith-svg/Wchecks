"""
Sous-agent dédié "journaux du Venezuela" de Joe — pays ajouté à la whitelist
(data/whitelist/whitelist_journaux.md), traité individuellement plutôt que via
le sous-agent générique (voir collectors/_joe_country_subagent.py).
"""

from collectors._joe_country_subagent import run_country_subagent

COUNTRY = "Venezuela"
REGION = "Amérique du Nord & Latine"
NEWSPAPERS = [
    {"name": "El Universal", "language": "espagnol", "website_url": "https://www.eluniversal.com"},
    {"name": "El Nacional", "language": "espagnol", "website_url": "https://www.elnacional.com"},
    {"name": "Últimas Noticias", "language": "espagnol", "website_url": "https://www.ultimasnoticias.com.ve"},
]


def run() -> int:
    return run_country_subagent(name="newspapers_venezuela", country=COUNTRY, region=REGION, newspapers=NEWSPAPERS)


if __name__ == "__main__":
    from logging_config import configure_logging

    configure_logging()
    n = run()
    print(f"{n} ligne(s) envoyée(s) vers national_newspapers_contents ({COUNTRY})")
