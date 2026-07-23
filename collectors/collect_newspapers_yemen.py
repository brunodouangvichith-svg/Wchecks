"""
Sous-agent dédié "journaux du Yémen" de Joe — pays ajouté à la whitelist
(data/whitelist/whitelist_journaux.md), traité individuellement plutôt que via
le sous-agent générique (voir collectors/_joe_country_subagent.py).
"""

from collectors._joe_country_subagent import run_country_subagent

COUNTRY = "Yémen"
REGION = "Moyen-Orient, Égypte, Turquie, Israël & GCC"
NEWSPAPERS = [
    {"name": "Al-Masdar Online", "language": "arabe", "website_url": "https://www.almasdaronline.com"},
    {"name": "Saba", "language": "arabe", "website_url": "https://www.sabanews.net"},
]


def run() -> int:
    return run_country_subagent(name="newspapers_yemen", country=COUNTRY, region=REGION, newspapers=NEWSPAPERS)


if __name__ == "__main__":
    from logging_config import configure_logging

    configure_logging()
    n = run()
    print(f"{n} ligne(s) envoyée(s) vers national_newspapers_contents ({COUNTRY})")
