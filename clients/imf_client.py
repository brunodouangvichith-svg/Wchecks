"""
Client pour l'API IMF DataMapper (gratuite, sans clé).

Utilisée en remplacement de l'indicateur World Bank GC.DOD.TOTL.GD.ZS pour la
dette publique : sa couverture s'est révélée très incomplète pour les économies
avancées (France, Allemagne, Japon absentes — confirmé en interrogeant
directement l'API World Bank, qui renvoie `value: None` pour toutes les années).
L'indicateur WEO du FMI GGXWDG_NGDP ("General government gross debt", % du PIB)
couvre 226 économies et correspond à la mesure standard de la dette publique
(définition proche des critères de Maastricht), plus large que la seule dette
du gouvernement central utilisée initialement.

Documentation : https://www.imf.org/external/datamapper/api/help

LIMITE : le jeu de données WEO inclut des projections pour les années à venir
(l'édition consultée ici projette plusieurs années dans le futur). Seules les
années jusqu'à l'année civile précédente sont conservées pour éviter de
présenter une prévision comme une donnée réalisée.
"""

import logging
from datetime import date

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://www.imf.org/external/datamapper/api/v1"
TIMEOUT_SECONDS = 30
DEBT_INDICATOR = "GGXWDG_NGDP"  # General government gross debt, % of GDP (WEO)


def get_general_government_debt() -> list[dict]:
    """
    Récupère la dette publique générale (% du PIB) pour tous les pays couverts
    par le WEO du FMI.

    Retourne une liste de dicts {"pays_code": str, "annee": int, "valeur": float},
    en excluant les années de projection (postérieures à l'année civile précédente).
    """
    response = requests.get(f"{BASE_URL}/{DEBT_INDICATOR}", timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    payload = response.json()

    last_actual_year = date.today().year - 1
    country_values = payload.get("values", {}).get(DEBT_INDICATOR, {})

    records = []
    for iso3, year_values in country_values.items():
        for year_str, value in year_values.items():
            if value is None:
                continue
            year = int(year_str)
            if year > last_actual_year:
                continue
            records.append({"pays_code": iso3, "annee": year, "valeur": float(value)})

    logger.info(
        "get_general_government_debt : %d valeurs récupérées (%d pays)",
        len(records), len(country_values),
    )
    return records
