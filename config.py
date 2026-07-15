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
    "risk_score": 6 * 60,
    # Minerais (USGS) : pas de fréquence -> déclenchement manuel uniquement
    # (voir cli.py --minerals-refresh)
}

# --- GDELT : mots-clés par dimension ---
GDELT_KEYWORDS_CONFLICTS = [
    "oil", "pipeline", "OPEC", "sanctions", "war", "attack on infrastructure",
]
GDELT_KEYWORDS_SOCIAL_TENSIONS = [
    "protest", "strike", "riot", "social unrest", "manifestation", "grève générale",
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
RSS_FEEDS = {
    "onu": "https://press.un.org/en/rss.xml",
    "us_state_dept": "https://www.state.gov/rss-feed/press-releases/feed/",
    "commission_europeenne": "https://ec.europa.eu/commission/presscorner/api/rss?language=en",
}
RSS_KEYWORDS = [
    "sanctions", "oil", "energy", "military", "OPEC", "pipeline", "strait",
]

# --- AISstream : filtre type de navire (tankers = 80-89) ---
AIS_TANKER_SHIP_TYPES = list(range(80, 90))
AIS_SNAPSHOT_DURATION_SECONDS = 45
