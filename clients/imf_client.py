"""
Client pour l'API IMF DataMapper (gratuite, sans clé).

Utilisée en remplacement de l'indicateur World Bank GC.DOD.TOTL.GD.ZS pour la
dette publique : sa couverture s'est révélée très incomplète pour les économies
avancées (France, Allemagne, Japon absentes — confirmé en interrogeant
directement l'API World Bank, qui renvoie `value: None` pour toutes les années).
L'indicateur WEO du FMI GGXWDG_NGDP ("General government gross debt", % du PIB)
couvre 226 entrées et correspond à la mesure standard de la dette publique
(définition proche des critères de Maastricht), plus large que la seule dette
du gouvernement central utilisée initialement.

Documentation : https://www.imf.org/external/datamapper/api/help

LIMITE : le jeu de données WEO inclut des projections pour les années à venir
(l'édition consultée ici projette plusieurs années dans le futur). Seules les
années jusqu'à l'année civile précédente sont conservées pour éviter de
présenter une prévision comme une donnée réalisée.

Dette publique NON restreinte à `config.MONITORED_COUNTRIES` (contrairement aux
autres dimensions World Bank) : la source est gratuite et couvre la quasi-
totalité des pays du monde sans coût ni limite supplémentaire, donc pas de
raison de se limiter à la sélection restreinte de pays "à risque" faite pour
les autres dimensions — voir get_general_government_debt(). Le jeu de données
WEO mélange cependant vrais pays et agrégats régionaux (ex. "WEOWORLD",
"EURO", "SSA" pour Afrique subsaharienne...) sous la même clé que les codes
ISO3 ; ces agrégats sont exclus via l'endpoint /countries de l'API, qui ne
liste que les 241 pays/territoires réels.
"""

import logging
from datetime import date

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://www.imf.org/external/datamapper/api/v1"
TIMEOUT_SECONDS = 30
DEBT_INDICATOR = "GGXWDG_NGDP"  # General government gross debt, % of GDP (WEO)
GDP_INDICATOR = "NGDPD"  # GDP, current prices, en milliards de USD (WEO)


def _get_real_country_codes() -> set[str]:
    """Codes ISO3 des pays/territoires réels (exclut les agrégats régionaux du
    WEO comme WEOWORLD/EURO/SSA, qui partagent le même espace de clés que les
    codes pays dans les indicateurs)."""
    response = requests.get(f"{BASE_URL}/countries", timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return set(response.json().get("countries", {}).keys())


def _get_indicator(indicator: str) -> dict[str, dict[str, float]]:
    """Retourne {iso3: {année (str): valeur}} pour un indicateur WEO, années de
    projection (postérieures à l'année civile précédente) exclues."""
    response = requests.get(f"{BASE_URL}/{indicator}", timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    payload = response.json()

    last_actual_year = date.today().year - 1
    country_values = payload.get("values", {}).get(indicator, {})

    result = {}
    for iso3, year_values in country_values.items():
        cleaned = {
            year_str: float(value)
            for year_str, value in year_values.items()
            if value is not None and int(year_str) <= last_actual_year
        }
        if cleaned:
            result[iso3] = cleaned
    return result


def get_general_government_debt() -> list[dict]:
    """
    Récupère la dette publique générale (% du PIB, indicateur GGXWDG_NGDP) et le
    PIB nominal (milliards de USD, indicateur NGDPD) pour tous les pays couverts
    par le WEO du FMI, et calcule le montant de dette correspondant.

    L'API DataMapper ne fournit la dette publique qu'en % du PIB (aucun
    indicateur WEO en valeur absolue) — le montant est donc dérivé par année :
    montant_milliards_usd = pct_pib / 100 * pib_nominal_milliards_usd, calculé
    pour CHAQUE année où les deux séries ont une valeur (conserve l'historique
    complet par pays, pas seulement la dernière année, comme avant l'ajout du
    montant) ; `None` si le PIB de cette année précise manque pour ce pays.

    Retourne une liste de dicts {"pays_code", "annee", "valeur" (dette % PIB),
    "montant_milliards_usd"}, restreinte aux vrais pays/territoires (les
    agrégats régionaux du WEO, ex. WEOWORLD/EURO/SSA, sont exclus).
    """
    debt_by_country = _get_indicator(DEBT_INDICATOR)
    gdp_by_country = _get_indicator(GDP_INDICATOR)
    real_countries = _get_real_country_codes()

    records = []
    for iso3, year_values in debt_by_country.items():
        if iso3 not in real_countries:
            continue
        gdp_years = gdp_by_country.get(iso3, {})
        for year_str, pct_pib in year_values.items():
            gdp_usd_milliards = gdp_years.get(year_str)
            montant = pct_pib / 100 * gdp_usd_milliards if gdp_usd_milliards is not None else None
            records.append(
                {
                    "pays_code": iso3,
                    "annee": int(year_str),
                    "valeur": pct_pib,
                    "montant_milliards_usd": montant,
                }
            )

    logger.info(
        "get_general_government_debt : %d valeurs récupérées (%d pays réels, "
        "agrégats régionaux exclus), montant calculé pour %d ligne(s) "
        "(PIB manquant pour les autres)",
        len(records), len({r["pays_code"] for r in records}),
        sum(1 for r in records if r["montant_milliards_usd"] is not None),
    )
    return records
