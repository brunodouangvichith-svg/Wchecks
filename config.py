"""
Configuration centrale du projet : fréquences de mise à jour, mots-clés de
recherche, zones stratégiques et pays surveillés.

Ce module ne contient aucune logique métier, uniquement des constantes
réutilisées par les collectors et le scheduler.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- Répertoires du projet ---
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"

# --- Variables d'environnement (clés API et accès Neon/Postgres) ---
# DATABASE_URL : chaîne de connexion Postgres fournie par Neon (dashboard du projet,
# onglet "Connection Details" — utiliser l'URL avec pooler pour un usage serverless).
DATABASE_URL = os.getenv("DATABASE_URL")
EIA_API_KEY = os.getenv("EIA_API_KEY")
AISSTREAM_API_KEY = os.getenv("AISSTREAM_API_KEY")
# GEMINI_API_KEY : clé Google AI Studio pour l'agent "Joe" (voir clients/joe_agent.py).
# Contrairement au reste du projet, Joe utilise un LLM (Gemini) — PAS gratuit au-delà
# du tier gratuit de Google AI Studio, donc volontairement borné (JOE_MAX_ARTICLES_PER_RUN)
# plutôt qu'appliqué à tous les articles scrapés.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
JOE_MAX_ARTICLES_PER_RUN = 15

# --- Fréquences de mise à jour (en minutes) pour le scheduler ---
FREQUENCIES_MINUTES = {
    "spr": 7 * 24 * 60,  # hebdomadaire
    "brent": 24 * 60,  # quotidien
    "oil_gas_production": 30 * 24 * 60,  # mensuel
    "conflicts": 6 * 60,
    "social_tensions": 6 * 60,
    "military_activity": 6 * 60,
    "worldbank_indicators": 30 * 24 * 60,  # dette, économie, défense, industrie
    "maritime_traffic": 6 * 60,  # 4x/jour
    "official_statements": 90,  # toutes les 1h30
    "joe_analysis": 6 * 60,  # aligné sur le cycle GDELT (conflicts/social_tensions/military)
    # country_sources : annuaire journaux/sites officiels par pays (agent Joe),
    # change très rarement -> rafraîchi mensuellement comme les indicateurs World Bank.
    "country_sources": 30 * 24 * 60,
    # country_news : lecture des flux RSS découverts, volume potentiellement
    # important (jusqu'à ~150 sources) -> cadence quotidienne plutôt que le
    # cycle 6h des autres flux, pour rester raisonnable en temps d'exécution.
    "country_news": 24 * 60,
    "risk_score": 6 * 60,
    # Minerais (USGS) : pas de fréquence -> déclenchement manuel uniquement
    # (voir cli.py --minerals-refresh)
}

# --- GDELT : mots-clés par dimension ---
GDELT_KEYWORDS_CONFLICTS = [
    "oil", "pipeline", "OPEC", "sanctions", "war", "attack on infrastructure",
]
# NB : volontairement pas de synonymes trop génériques (crise, désaccord,
# dissension, division, friction/frottement, malaise, tiraillement, trouble) —
# ce sont des mots-clés de recherche GDELT (correspondance de texte, pas de
# concept), et ces termes matcheraient massivement des articles sans rapport
# (une "division" militaire/corporate/sportive, un "trouble" médical/juridique,
# une "friction" mécanique...), noyant le signal réel sous du bruit.
GDELT_KEYWORDS_SOCIAL_TENSIONS = [
    "protest", "strike", "riot", "social unrest", "manifestation", "manifestations",
    "grève générale", "grèves", "troubles sociaux", "agitation sociale",
    "perturbations sociales", "désordre social", "conflits sociaux",
]
GDELT_KEYWORDS_MILITARY = [
    "drone strike", "missile test", "hypersonic missile", "military drill",
]

# --- Zones stratégiques surveillées (nom -> bbox approximative lat/lon) ---
STRATEGIC_ZONES = {
    "moyen_orient": {"lat_min": 12.0, "lat_max": 42.0, "lon_min": 25.0, "lon_max": 63.0},
    "russie_mer_noire": {"lat_min": 40.0, "lat_max": 55.0, "lon_min": 27.0, "lon_max": 42.0},
    "venezuela": {"lat_min": 0.0, "lat_max": 13.0, "lon_min": -74.0, "lon_max": -59.0},
    "nigeria": {"lat_min": 4.0, "lat_max": 14.0, "lon_min": 2.0, "lon_max": 15.0},
    "mer_rouge": {"lat_min": 12.0, "lat_max": 30.0, "lon_min": 32.0, "lon_max": 44.0},
    "detroit_ormuz": {"lat_min": 24.5, "lat_max": 27.5, "lon_min": 54.5, "lon_max": 57.5},
    "detroit_malacca": {"lat_min": 1.0, "lat_max": 6.5, "lon_min": 98.0, "lon_max": 104.5},
    "suez": {"lat_min": 29.5, "lat_max": 31.5, "lon_min": 32.0, "lon_max": 33.0},
    "bab_el_mandeb": {"lat_min": 11.5, "lat_max": 13.5, "lon_min": 42.5, "lon_max": 44.0},
    "golfe_mexique": {"lat_min": 18.0, "lat_max": 30.0, "lon_min": -98.0, "lon_max": -80.0},
}

# --- Pays surveillés (codes ISO3), utilisés par les clients World Bank/EIA/mapping ---
# Sélection : grands producteurs pétrole/gaz, puissances militaires/économiques, zones à risque.
MONITORED_COUNTRIES = [
    "USA", "CHN", "RUS", "SAU", "IRN", "IRQ", "ARE", "QAT", "KWT", "VEN",
    "NGA", "LBY", "DZA", "AGO", "BRA", "MEX", "CAN", "NOR", "GBR", "FRA",
    "DEU", "ITA", "ESP", "UKR", "TUR", "EGY", "ISR", "IND", "JPN", "KOR",
    "IDN", "AUS", "ZAF", "PAK", "SYR", "YEM", "SDN", "KAZ", "AZE", "TKM",
    "GRC",
]

# --- World Bank : indicateurs suivis ---
WORLDBANK_INDICATORS = {
    "country_debt": "GC.DOD.TOTL.GD.ZS",
    "tax_pct_gdp": "GC.TAX.TOTL.GD.ZS",
    "unemployment_pct": "SL.UEM.TOTL.ZS",
    "inflation_pct": "FP.CPI.TOTL.ZG",
    "defense_budget_pct_gdp": "MS.MIL.XPND.GD.ZS",
    "industry_pct_gdp": "NV.IND.TOTL.ZS",
}

# --- Minerais stratégiques suivis (USGS) ---
STRATEGIC_MINERALS = ["copper", "lithium", "uranium", "rare_earths", "gold", "cobalt"]

# --- Flux RSS officiels (démarrage volontairement restreint, voir README) ---
# Pas de filtre par mot-clé (toutes les entrées de ces flux sont conservées,
# voir clients/rss_client.py) : la sélection restreinte à 2-3 institutions
# fait déjà office de filtre de pertinence.
RSS_FEEDS = {
    "onu": "https://press.un.org/en/rss.xml",
    "us_state_dept": "https://www.state.gov/rss-feed/press-releases/feed/",
    "commission_europeenne": "https://ec.europa.eu/commission/presscorner/api/rss?language=en",
}

# --- AISstream : filtre type de navire (tankers = 80-89) ---
AIS_TANKER_SHIP_TYPES = list(range(80, 90))
AIS_SNAPSHOT_DURATION_SECONDS = 45
