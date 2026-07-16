"""
Table de correspondance pays, construite incrémentalement au fil des phases
(voir plan de développement) plutôt que d'un bloc.

Couverture mondiale (pas seulement config.MONITORED_COUNTRIES) : la recherche par
mots-clés GDELT remonte des articles datés dans n'importe quel pays couvert par la
presse mondiale, pas seulement les pays surveillés pour les indicateurs World Bank.
Une table limitée aux 40 pays surveillés laissait la majorité des articles sans
lat/lon (voir logs de collect_conflicts) — élargie ici après ce constat.

Contient :
- COUNTRY_NAME_TO_ISO3 : nom de pays tel que renvoyé par GDELT (anglais) -> ISO3
- COUNTRY_CENTROIDS : ISO3 -> (lat, lon) approximatif (capitale), utilisé UNIQUEMENT
  pour donner une position indicative de niveau pays aux événements GDELT — la
  Doc API 2.0 de GDELT ne fournit pas de lat/lon précis par article, seulement le
  pays source. C'est une approximation documentée, pas une géolocalisation d'événement.

D'autres clés (codes EIA, codes USGS, clés GeoJSON) seront ajoutées au fil des
phases qui en ont besoin (production internationale EIA, choroplèthes, minerais).

LIMITE CONNUE : les noms de pays utilisés par GDELT peuvent varier légèrement
(ex. graphies alternatives, territoires disputés). Un nom non reconnu est loggé en
warning par resolve_country() plutôt que de faire planter la collecte — la table
est destinée à être complétée au fil des logs observés en production.
"""

import logging

logger = logging.getLogger(__name__)

# name -> (iso3, lat, lon capitale approximative). Source unique dont dérivent
# COUNTRY_NAME_TO_ISO3 et COUNTRY_CENTROIDS ci-dessous.
_COUNTRIES: dict[str, tuple[str, float, float]] = {
    # --- Amériques ---
    "United States": ("USA", 38.9072, -77.0369),
    "Canada": ("CAN", 45.4215, -75.6972),
    "Mexico": ("MEX", 19.4326, -99.1332),
    "Brazil": ("BRA", -15.7975, -47.8919),
    "Argentina": ("ARG", -34.6037, -58.3816),
    "Chile": ("CHL", -33.4489, -70.6693),
    "Colombia": ("COL", 4.7110, -74.0721),
    "Venezuela": ("VEN", 10.4806, -66.9036),
    "Peru": ("PER", -12.0464, -77.0428),
    "Ecuador": ("ECU", -0.1807, -78.4678),
    "Bolivia": ("BOL", -16.4897, -68.1193),
    "Paraguay": ("PRY", -25.2637, -57.5759),
    "Uruguay": ("URY", -34.9011, -56.1645),
    "Guyana": ("GUY", 6.8013, -58.1551),
    "Suriname": ("SUR", 5.8520, -55.2038),
    "Panama": ("PAN", 8.9824, -79.5199),
    "Costa Rica": ("CRI", 9.9281, -84.0907),
    "Nicaragua": ("NIC", 12.1150, -86.2362),
    "Honduras": ("HND", 14.0723, -87.1921),
    "El Salvador": ("SLV", 13.6929, -89.2182),
    "Guatemala": ("GTM", 14.6349, -90.5069),
    "Belize": ("BLZ", 17.1899, -88.4976),
    "Cuba": ("CUB", 23.1136, -82.3666),
    "Jamaica": ("JAM", 18.0179, -76.8099),
    "Haiti": ("HTI", 18.5944, -72.3074),
    "Dominican Republic": ("DOM", 18.4861, -69.9312),
    "Trinidad and Tobago": ("TTO", 10.6596, -61.5019),
    "Bahamas": ("BHS", 25.0343, -77.3963),
    # --- Europe ---
    "United Kingdom": ("GBR", 51.5072, -0.1276),
    "Ireland": ("IRL", 53.3498, -6.2603),
    "France": ("FRA", 48.8566, 2.3522),
    "Germany": ("DEU", 52.5200, 13.4050),
    "Italy": ("ITA", 41.9028, 12.4964),
    "Spain": ("ESP", 40.4168, -3.7038),
    "Portugal": ("PRT", 38.7223, -9.1393),
    "Netherlands": ("NLD", 52.3676, 4.9041),
    "Belgium": ("BEL", 50.8503, 4.3517),
    "Luxembourg": ("LUX", 49.6116, 6.1319),
    "Switzerland": ("CHE", 46.9480, 7.4474),
    "Austria": ("AUT", 48.2082, 16.3738),
    "Norway": ("NOR", 59.9139, 10.7522),
    "Sweden": ("SWE", 59.3293, 18.0686),
    "Denmark": ("DNK", 55.6761, 12.5683),
    "Finland": ("FIN", 60.1699, 24.9384),
    "Iceland": ("ISL", 64.1466, -21.9426),
    "Poland": ("POL", 52.2297, 21.0122),
    "Czech Republic": ("CZE", 50.0755, 14.4378),
    "Slovakia": ("SVK", 48.1486, 17.1077),
    "Slovak Republic": ("SVK", 48.1486, 17.1077),  # alias observé dans les données GDELT réelles
    "Hungary": ("HUN", 47.4979, 19.0402),
    "Romania": ("ROU", 44.4268, 26.1025),
    "Bulgaria": ("BGR", 42.6977, 23.3219),
    "Greece": ("GRC", 37.9838, 23.7275),
    "Ukraine": ("UKR", 50.4501, 30.5234),
    "Belarus": ("BLR", 53.9006, 27.5590),
    "Russia": ("RUS", 55.7558, 37.6173),
    "Moldova": ("MDA", 47.0105, 28.8638),
    "Lithuania": ("LTU", 54.6872, 25.2797),
    "Latvia": ("LVA", 56.9496, 24.1052),
    "Estonia": ("EST", 59.4370, 24.7536),
    "Croatia": ("HRV", 45.8150, 15.9819),
    "Slovenia": ("SVN", 46.0569, 14.5058),
    "Serbia": ("SRB", 44.7866, 20.4489),
    "Bosnia and Herzegovina": ("BIH", 43.8563, 18.4131),
    "Montenegro": ("MNE", 42.4304, 19.2594),
    "North Macedonia": ("MKD", 41.9981, 21.4254),
    "Albania": ("ALB", 41.3275, 19.8187),
    "Kosovo": ("XKX", 42.6629, 21.1655),
    "Cyprus": ("CYP", 35.1856, 33.3823),
    "Malta": ("MLT", 35.8989, 14.5146),
    "Turkey": ("TUR", 39.9334, 32.8597),
    "Georgia": ("GEO", 41.7151, 44.8271),
    "Armenia": ("ARM", 40.1792, 44.4991),
    "Azerbaijan": ("AZE", 40.4093, 49.8671),
    # --- Moyen-Orient ---
    "Saudi Arabia": ("SAU", 24.7136, 46.6753),
    "Iran": ("IRN", 35.6892, 51.3890),
    "Iraq": ("IRQ", 33.3152, 44.3661),
    "United Arab Emirates": ("ARE", 24.4539, 54.3773),
    "Qatar": ("QAT", 25.2854, 51.5310),
    "Kuwait": ("KWT", 29.3759, 47.9774),
    "Bahrain": ("BHR", 26.2285, 50.5860),
    "Oman": ("OMN", 23.5859, 58.4059),
    "Yemen": ("YEM", 15.3694, 44.1910),
    "Israel": ("ISR", 31.7683, 35.2137),
    "Palestinian Territories": ("PSE", 31.9038, 35.2034),
    "Jordan": ("JOR", 31.9454, 35.9284),
    "Lebanon": ("LBN", 33.8938, 35.5018),
    "Syria": ("SYR", 33.5138, 36.2765),
    # --- Asie centrale ---
    "Kazakhstan": ("KAZ", 51.1605, 71.4704),
    "Turkmenistan": ("TKM", 37.9601, 58.3261),
    "Uzbekistan": ("UZB", 41.2995, 69.2401),
    "Tajikistan": ("TJK", 38.5598, 68.7870),
    "Kyrgyzstan": ("KGZ", 42.8746, 74.5698),
    "Afghanistan": ("AFG", 34.5553, 69.2075),
    "Mongolia": ("MNG", 47.8864, 106.9057),
    # --- Asie du Sud et de l'Est ---
    "India": ("IND", 28.6139, 77.2090),
    "Pakistan": ("PAK", 33.6844, 73.0479),
    "Bangladesh": ("BGD", 23.8103, 90.4125),
    "Sri Lanka": ("LKA", 6.9271, 79.8612),
    "Nepal": ("NPL", 27.7172, 85.3240),
    "Bhutan": ("BTN", 27.4728, 89.6390),
    "Myanmar": ("MMR", 19.7633, 96.0785),
    "China": ("CHN", 39.9042, 116.4074),
    "Japan": ("JPN", 35.6762, 139.6503),
    "South Korea": ("KOR", 37.5665, 126.9780),
    "North Korea": ("PRK", 39.0392, 125.7625),
    "Taiwan": ("TWN", 25.0330, 121.5654),
    "Vietnam": ("VNM", 21.0278, 105.8342),
    "Laos": ("LAO", 17.9757, 102.6331),
    "Cambodia": ("KHM", 11.5564, 104.9282),
    "Thailand": ("THA", 13.7563, 100.5018),
    "Malaysia": ("MYS", 3.1390, 101.6869),
    "Singapore": ("SGP", 1.3521, 103.8198),
    "Indonesia": ("IDN", -6.2088, 106.8456),
    "Philippines": ("PHL", 14.5995, 120.9842),
    "Brunei": ("BRN", 4.9031, 114.9398),
    "East Timor": ("TLS", -8.5569, 125.5603),
    # --- Océanie ---
    "Australia": ("AUS", -35.2809, 149.1300),
    "New Zealand": ("NZL", -41.2865, 174.7762),
    "Papua New Guinea": ("PNG", -9.4438, 147.1803),
    "Fiji": ("FJI", -18.1416, 178.4419),
    # --- Afrique ---
    "Egypt": ("EGY", 30.0444, 31.2357),
    "Libya": ("LBY", 32.8872, 13.1913),
    "Algeria": ("DZA", 36.7538, 3.0588),
    "Tunisia": ("TUN", 36.8065, 10.1815),
    "Morocco": ("MAR", 34.0209, -6.8416),
    "Mauritania": ("MRT", 18.0735, -15.9582),
    "Mali": ("MLI", 12.6392, -8.0029),
    "Niger": ("NER", 13.5127, 2.1126),
    "Chad": ("TCD", 12.1348, 15.0557),
    "Sudan": ("SDN", 15.5007, 32.5599),
    "South Sudan": ("SSD", 4.8517, 31.5825),
    "Eritrea": ("ERI", 15.3229, 38.9251),
    "Djibouti": ("DJI", 11.5721, 43.1456),
    "Ethiopia": ("ETH", 9.0250, 38.7469),
    "Somalia": ("SOM", 2.0469, 45.3182),
    "Kenya": ("KEN", -1.2921, 36.8219),
    "Uganda": ("UGA", 0.3476, 32.5825),
    "Rwanda": ("RWA", -1.9403, 29.8739),
    "Burundi": ("BDI", -3.3731, 29.9189),
    "Tanzania": ("TZA", -6.1630, 35.7516),
    "Nigeria": ("NGA", 9.0765, 7.3986),
    "Benin": ("BEN", 6.3703, 2.3912),
    "Togo": ("TGO", 6.1725, 1.2314),
    "Ghana": ("GHA", 5.6037, -0.1870),
    "Ivory Coast": ("CIV", 6.8276, -5.2893),
    "Liberia": ("LBR", 6.3004, -10.7969),
    "Sierra Leone": ("SLE", 8.4657, -13.2317),
    "Guinea": ("GIN", 9.6412, -13.5784),
    "Guinea-Bissau": ("GNB", 11.8636, -15.5977),
    "Senegal": ("SEN", 14.7167, -17.4677),
    "Gambia": ("GMB", 13.4549, -16.5790),
    "Cape Verde": ("CPV", 14.9330, -23.5133),
    "Cameroon": ("CMR", 3.8480, 11.5021),
    "Central African Republic": ("CAF", 4.3947, 18.5582),
    "Gabon": ("GAB", 0.4162, 9.4673),
    "Republic of Congo": ("COG", -4.2634, 15.2429),
    "Democratic Republic of Congo": ("COD", -4.4419, 15.2663),
    "Angola": ("AGO", -8.8390, 13.2894),
    "Zambia": ("ZMB", -15.3875, 28.3228),
    "Malawi": ("MWI", -13.9626, 33.7741),
    "Mozambique": ("MOZ", -25.9692, 32.5732),
    "Zimbabwe": ("ZWE", -17.8292, 31.0522),
    "Botswana": ("BWA", -24.6282, 25.9231),
    "Namibia": ("NAM", -22.5609, 17.0658),
    "South Africa": ("ZAF", -25.7479, 28.2293),
    "Lesotho": ("LSO", -29.3167, 27.4833),
    "Eswatini": ("SWZ", -26.3054, 31.1367),
    "Madagascar": ("MDG", -18.8792, 47.5079),
    "Equatorial Guinea": ("GNQ", 3.7504, 8.7371),
    "Andorra": ("AND", 42.5063, 1.5218),
    "Liechtenstein": ("LIE", 47.1660, 9.5554),
    "San Marino": ("SMR", 43.9424, 12.4578),
    "Comoros": ("COM", -11.7172, 43.2473),
    "Seychelles": ("SYC", -4.6191, 55.4513),
    # --- Petits États insulaires / manquants, découverts en parsant les données SIPRI ---
    "Antigua and Barbuda": ("ATG", 17.1274, -61.8468),
    "Barbados": ("BRB", 13.1132, -59.5988),
    "Burkina Faso": ("BFA", 12.3714, -1.5197),
    "Grenada": ("GRD", 12.0561, -61.7486),
    "Maldives": ("MDV", 4.1755, 73.5093),
    "Mauritius": ("MUS", -20.1609, 57.5012),
    "Saint Kitts and Nevis": ("KNA", 17.3026, -62.7177),
    "Saint Vincent and the Grenadines": ("VCT", 13.1587, -61.2248),
    "Saint Vincent": ("VCT", 13.1587, -61.2248),  # alias observé dans les données SIPRI
    "Solomon Islands": ("SLB", -9.4456, 159.9729),
    "Tonga": ("TON", -21.1789, -175.1982),
    "Vanuatu": ("VUT", -17.7404, 168.3126),
    "Western Sahara": ("ESH", 27.1418, -13.1873),
}

# Alias de noms observés dans des sources réelles (SIPRI notamment) qui désignent le
# même pays qu'une entrée ci-dessus sous un autre nom/orthographe.
_ALIASES: dict[str, str] = {
    "Turkiye": "Turkey",
    "Viet Nam": "Vietnam",
    "Cote d'Ivoire": "Ivory Coast",
    "Czechia": "Czech Republic",
    "DR Congo": "Democratic Republic of Congo",
    "Congo": "Republic of Congo",
    "Cabo Verde": "Cape Verde",
    "Timor-Leste": "East Timor",
    "eSwatini": "Eswatini",
    "Palestine": "Palestinian Territories",
    "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "Côte d'Ivoire": "Ivory Coast",  # alias observé dans les données Wikipédia (avec accent)
    "Congo (Brazzaville)": "Republic of Congo",  # alias observé dans les données USGS
    "Congo (Kinshasa)": "Democratic Republic of Congo",
    "Korea, North": "North Korea",
    "Korea, Republic of": "South Korea",
    "Burma": "Myanmar",
    # --- Alias observés dans le GeoJSON de frontières (viz/data/world_countries.geojson) ---
    "United States of America": "United States",
    "Democratic Republic of the Congo": "Democratic Republic of Congo",
    "Republic of the Congo": "Republic of Congo",
    "Republic of Serbia": "Serbia",
    "Guinea Bissau": "Guinea-Bissau",
    "United Republic of Tanzania": "Tanzania",
    "Swaziland": "Eswatini",
    "The Bahamas": "Bahamas",
    "Macedonia": "North Macedonia",
    "West Bank": "Palestinian Territories",
    # --- Noms français des pays surveillés (config.MONITORED_COUNTRIES), pour le
    # moteur de questions/réponses (qa/engine.py) — variantes avec et sans accent. ---
    "Etats-Unis": "United States",
    "États-Unis": "United States",
    "Chine": "China",
    "Russie": "Russia",
    "Arabie Saoudite": "Saudi Arabia",
    "Arabie saoudite": "Saudi Arabia",
    "Irak": "Iraq",
    "Emirats arabes unis": "United Arab Emirates",
    "Émirats arabes unis": "United Arab Emirates",
    "Koweit": "Kuwait",
    "Koweït": "Kuwait",
    "Libye": "Libya",
    "Algerie": "Algeria",
    "Algérie": "Algeria",
    "Bresil": "Brazil",
    "Brésil": "Brazil",
    "Mexique": "Mexico",
    "Norvege": "Norway",
    "Norvège": "Norway",
    "Royaume-Uni": "United Kingdom",
    "Allemagne": "Germany",
    "Italie": "Italy",
    "Espagne": "Spain",
    "Turquie": "Turkey",
    "Egypte": "Egypt",
    "Égypte": "Egypt",
    "Israël": "Israel",
    "Inde": "India",
    "Japon": "Japan",
    "Coree du Sud": "South Korea",
    "Corée du Sud": "South Korea",
    "Indonesie": "Indonesia",
    "Indonésie": "Indonesia",
    "Australie": "Australia",
    "Afrique du Sud": "South Africa",
    "Syrie": "Syria",
    "Yémen": "Yemen",
    "Soudan": "Sudan",
    "Azerbaidjan": "Azerbaijan",
    "Azerbaïdjan": "Azerbaijan",
    "Turkménistan": "Turkmenistan",
    "Nigéria": "Nigeria",
    "Grece": "Greece",
    "Grèce": "Greece",
}

COUNTRY_NAME_TO_ISO3: dict[str, str] = {name: iso3 for name, (iso3, _, _) in _COUNTRIES.items()}
for _alias, _canonical in _ALIASES.items():
    COUNTRY_NAME_TO_ISO3[_alias] = COUNTRY_NAME_TO_ISO3[_canonical]
COUNTRY_CENTROIDS: dict[str, tuple[float, float]] = {
    iso3: (lat, lon) for _, (iso3, lat, lon) in _COUNTRIES.items()
}

# Extension de domaine (dernier label, ex. "uk" dans "co.uk") -> code ISO3.
# Construit incrémentalement à partir des sources réellement découvertes
# (collectors/collect_country_sources.py), même philosophie que _ALIASES :
# pas une liste mondiale exhaustive, étendue au fur et à mesure des cas
# rencontrés. La plupart des ccTLD correspondent au code ISO 3166-1 alpha-2,
# SAUF le Royaume-Uni (".uk", pas ".gb").
TLD_TO_ISO3: dict[str, str] = {
    "ao": "AGO", "ae": "ARE", "au": "AUS", "az": "AZE", "br": "BRA",
    "ca": "CAN", "cn": "CHN", "de": "DEU", "dz": "DZA", "eg": "EGY",
    "es": "ESP", "fr": "FRA", "uk": "GBR", "gr": "GRC", "id": "IDN",
    "in": "IND", "ir": "IRN", "iq": "IRQ", "il": "ISR", "it": "ITA",
    "jp": "JPN", "kz": "KAZ", "kr": "KOR", "kw": "KWT", "ly": "LBY",
    "mx": "MEX", "ng": "NGA", "no": "NOR", "pk": "PAK", "qa": "QAT",
    "ru": "RUS", "sa": "SAU", "sy": "SYR", "tm": "TKM", "tr": "TUR",
    "ua": "UKR", "ve": "VEN", "ye": "YEM", "za": "ZAF",
}


def country_from_domain(domain: str | None) -> str | None:
    """
    Déduit un pays (ISO3) à partir de l'extension d'un nom de domaine (ex.
    "india.gov.in" -> IND via le suffixe ".in", "telegraph.co.uk" -> GBR via
    ".uk") — voir TLD_TO_ISO3. Retourne None si le domaine se termine par un
    TLD générique (.com, .net, .org...) sans signal pays, ou par un TLD pas
    encore recensé.
    """
    if not domain:
        return None
    last_label = domain.rsplit(".", 1)[-1].lower()
    return TLD_TO_ISO3.get(last_label)


def resolve_country(gdelt_country_name: str) -> tuple[str | None, float | None, float | None]:
    """
    Résout un nom de pays GDELT en (iso3, lat, lon) approximatif.
    Retourne (None, None, None) si le pays n'est pas dans la table de correspondance,
    et logue l'échec pour permettre d'étendre la table par la suite.
    """
    iso3 = COUNTRY_NAME_TO_ISO3.get(gdelt_country_name)
    if iso3 is None:
        logger.warning("country_mapping: pays GDELT non reconnu : '%s'", gdelt_country_name)
        return None, None, None
    lat, lon = COUNTRY_CENTROIDS.get(iso3, (None, None))
    return iso3, lat, lon
