"""
Collecte de la production mondiale de pétrole et de gaz naturel par pays — EIA
(catégorie "international", endpoint /international/data/).

Codes découverts par exploration des facets (voir clients.eia_client.list_facet_values) :
- activityId=1 : "Production"
- productId=53 : "Total petroleum and other liquids" (pétrole, mesure utilisée par EIA
  pour ses classements pays — inclut NGPL et gains de raffinage, pas seulement le brut),
  renvoyé dans une seule unité : TBPD (milliers de barils/jour, cohérent avec le nom de
  colonne `valeur_barils_jour`).
- productId=26 : "Dry natural gas" (gaz naturel), renvoyé en 5 unités simultanément
  (BCF/BCM/MTOE/QBTU/TJ) — on fixe unit="BCM" (milliards de m³, unité la plus
  répandue dans les comparaisons internationales) pour éviter la multiplication des
  lignes par unité.
- countryRegionId correspond directement aux codes ISO3 (vérifié : tous les pays de
  config.MONITORED_COUNTRIES existent tels quels comme countryRegionId).

LIMITE : l'endpoint /international/facet/productId/ ne liste que 18 valeurs et
n'inclut NI le pétrole détaillé par sous-catégorie NI le gaz naturel — ces codes
(53 et 26) n'ont été trouvés qu'en observant les productId réellement présents dans
les données retournées par /international/data/ sans filtre productId. Documentation
EIA incomplète sur ce point, comme anticipé dans le plan de développement.
"""

import logging

import config
from clients.eia_client import get_international_data
from clients.neon_client import upsert_generic

logger = logging.getLogger(__name__)

ACTIVITY_ID_PRODUCTION = "1"
PRODUCT_ID_OIL = "53"
PRODUCT_ID_GAS = "26"
OIL_UNIT = "TBPD"  # milliers de barils/jour — voir docstring du module
GAS_UNIT = "BCM"  # milliards de m³ — voir docstring du module


def _safe_float(value) -> float | None:
    """EIA renvoie parfois '--' ou 'NA' pour une donnée manquante/non publiée."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def run() -> tuple[int, int]:
    oil_raw = get_international_data(
        ACTIVITY_ID_PRODUCTION, PRODUCT_ID_OIL, config.MONITORED_COUNTRIES,
        frequency="annual", unit=OIL_UNIT,
    )
    oil_rows = []
    for r in oil_raw:
        value = _safe_float(r["value"])
        if value is None or not r["country_region_id"]:
            continue
        oil_rows.append(
            {"pays_code": r["country_region_id"], "periode": r["period"], "valeur_barils_jour": value}
        )
    n_oil = upsert_generic("oil_production", oil_rows)

    gas_raw = get_international_data(
        ACTIVITY_ID_PRODUCTION, PRODUCT_ID_GAS, config.MONITORED_COUNTRIES,
        frequency="annual", unit=GAS_UNIT,
    )
    gas_rows = []
    for r in gas_raw:
        value = _safe_float(r["value"])
        if value is None or not r["country_region_id"]:
            continue
        gas_rows.append(
            {"pays_code": r["country_region_id"], "periode": r["period"], "valeur_production_gaz": value}
        )
    n_gas = upsert_generic("gas_production", gas_rows)

    return n_oil, n_gas


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    n_oil, n_gas = run()
    print(f"{n_oil} ligne(s) envoyée(s) vers oil_production")
    print(f"{n_gas} ligne(s) envoyée(s) vers gas_production")
