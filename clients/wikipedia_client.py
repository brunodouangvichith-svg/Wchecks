"""
Parsing de la page Wikipédia "List of countries by credit rating" (gratuite,
pas de clé, pas de compte requis).

LIMITE / CHOIX DE SOURCE : Alphacast propose bien un jeu de données "Sovereign
Credit Ratings", mais l'obtention d'une clé API nécessite de contacter
hello@alphacast.io directement (pas d'auto-inscription confirmée), sans tier
gratuit garanti — trop de friction pour ce projet. Wikipédia agrège S&P, Fitch
et Moody's dans des tableaux structurés, mis à jour par la communauté ; moins
"officiel" qu'une API d'agence, mais gratuit, instantané, et suffisant pour un
outil de veille (voir avertissement du README).

Chaque page/tableau ne donne QUE la notation ACTUELLE par pays (pas d'historique) :
la table `credit_ratings` est donc mise à jour par upsert sur (pays_code, agence),
pas accumulée dans le temps comme les autres dimensions.
"""

import logging
from datetime import datetime
from io import StringIO

import pandas as pd
import requests

from mapping.country_mapping import COUNTRY_NAME_TO_ISO3

logger = logging.getLogger(__name__)

WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/List_of_countries_by_credit_rating"
TIMEOUT_SECONDS = 30

# Nom de la section Wikipédia (heading h2/h3) -> nom d'agence normalisé.
AGENCIES = {
    "Standard & Poor's": "S&P",
    "Fitch": "Fitch",
    "Moody's": "Moody's",
}


def _find_tables_by_heading(html: str) -> dict[str, "pd.DataFrame"]:
    """Associe chaque table wikitable à la section (h2/h3) qui la précède."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    wiki_tables = soup.find_all("table", class_="wikitable")

    tables_by_heading = {}
    for wiki_table in wiki_tables:
        heading_el = wiki_table.find_previous(["h2", "h3"])
        heading = heading_el.get_text(strip=True) if heading_el else None
        if heading in AGENCIES:
            df = pd.read_html(StringIO(str(wiki_table)))[0]
            tables_by_heading[AGENCIES[heading]] = df
    return tables_by_heading


def _parse_date(raw: str) -> str | None:
    try:
        return datetime.strptime(raw.strip(), "%d %B %Y").date().isoformat()
    except (ValueError, AttributeError):
        return None


def get_credit_ratings() -> list[dict]:
    """
    Scrape les notations souveraines S&P/Fitch/Moody's depuis Wikipédia.

    Retourne une liste de dicts {pays_code, agence, note, perspective, date_notation}.
    Les pays non reconnus dans country_mapping (territoires, graphies inhabituelles)
    sont ignorés et loggués plutôt que de faire planter le parsing.
    """
    response = requests.get(WIKIPEDIA_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()

    tables = _find_tables_by_heading(response.text)
    if not tables:
        logger.warning("wikipedia_client: aucune table de notation trouvée (structure de page modifiée ?)")
        return []

    rows = []
    unmatched: set[str] = set()
    for agence, df in tables.items():
        name_col = "Country/Territory" if "Country/Territory" in df.columns else "Country"
        for _, record in df.iterrows():
            country_name = str(record.get(name_col, "")).strip()
            iso3 = COUNTRY_NAME_TO_ISO3.get(country_name)
            if iso3 is None:
                unmatched.add(country_name)
                continue

            note = str(record.get("Rating", "")).strip().replace("−", "-") or None
            perspective = str(record.get("Outlook", "")).strip() or None
            date_notation = _parse_date(str(record.get("Date", "")))

            rows.append(
                {
                    "pays_code": iso3,
                    "agence": agence,
                    "note": note,
                    "perspective": perspective,
                    "date_notation": date_notation,
                }
            )

    if unmatched:
        logger.warning(
            "wikipedia_client: %d entité(s) non reconnue(s) comme pays, ignorée(s) : %s",
            len(unmatched), sorted(unmatched),
        )

    logger.info("get_credit_ratings : %d notation(s) récupérée(s) (%d agences)", len(rows), len(tables))
    return rows
