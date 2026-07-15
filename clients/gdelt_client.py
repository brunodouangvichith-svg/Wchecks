"""
Client pour l'API GDELT v2 DOC (gratuite, sans clé).

Documentation : https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/

LIMITE CONNUE : le mode ArtList de la DOC API renvoie le titre, l'URL, la date et
le pays source d'un article, mais ni coordonnées précises ni tonalité par article
(seul un agrégat par requête existe via le mode ToneChart, pas exploitable par
événement individuel). Pour rester honnête sur la précision des données :
- le lat/lon renvoyé ici est par défaut une approximation au niveau PAYS
  (centroïde), pas une géolocalisation de l'événement (voir
  mapping/country_mapping.py). CAS PARTICULIER : le "pays source" GDELT est celui
  du MÉDIA qui publie l'article, pas celui de l'événement — un article sur le
  détroit d'Ormuz publié par un média américain se retrouvait donc plaqué sur
  Washington. Pour les zones stratégiques (détroits, mers) qui ne sont pas des
  pays, on détecte leur mention dans le TITRE de l'article (voir ZONE_KEYWORDS)
  et on utilise alors le centre de la zone (config.STRATEGIC_ZONES) à la place du
  centroïde pays — toujours une approximation (centre de zone, pas coordonnées
  exactes de l'événement), mais nettement plus proche de la réalité ;
- la tonalité ("ton") n'est pas disponible via cette API gratuite et reste `None` —
  documenté comme limite connue plutôt que remplacé par un proxy inventé.
"""

import logging
import time

import requests

import config
from mapping.country_mapping import resolve_country

logger = logging.getLogger(__name__)

# Mots-clés (titre d'article, en minuscule) -> zone stratégique de
# config.STRATEGIC_ZONES. Vérifié avant le centroïde pays : un détroit ou une mer
# n'est pas un pays, GDELT ne peut de toute façon pas le renvoyer comme tel.
ZONE_KEYWORDS = {
    "detroit_ormuz": ["hormuz", "ormuz"],
    "detroit_malacca": ["malacca"],
    "suez": ["suez"],
    "bab_el_mandeb": ["bab-el-mandeb", "bab el mandeb", "mandeb"],
    "mer_rouge": ["red sea", "mer rouge"],
    "golfe_mexique": ["gulf of mexico", "golfe du mexique"],
}


def _zone_center(zone_name: str) -> tuple[float, float]:
    zone = config.STRATEGIC_ZONES[zone_name]
    return (zone["lat_min"] + zone["lat_max"]) / 2, (zone["lon_min"] + zone["lon_max"]) / 2


def _detect_zone(title: str | None) -> str | None:
    title_lower = (title or "").lower()
    for zone_name, keywords in ZONE_KEYWORDS.items():
        if any(kw in title_lower for kw in keywords):
            return zone_name
    return None

BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
TIMEOUT_SECONDS = 30
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 8


def search_articles(
    keywords: list[str], timespan: str = "1d", max_records: int = 250, source_lang: str = "english",
) -> list[dict]:
    """
    Recherche des articles GDELT correspondant à l'un des mots-clés donnés.

    `source_lang` (défaut "english") restreint aux sources dans cette langue via le
    modificateur `sourcelang:` de la Doc API — évite d'avoir des titres dans des
    langues variées à traduire après coup. Passer `None` pour désactiver le filtre
    (toutes langues, comme avant l'ajout de ce paramètre).

    Retourne une liste de dicts prêts pour la base :
    {event_id, date, pays, lat, lon, titre, ton, url}
    (event_id = url, car la Doc API ne fournit pas d'identifiant d'événement stable ;
    ton = None, voir limite documentée en tête de module).
    """
    query = "(" + " OR ".join(f'"{kw}"' if " " in kw else kw for kw in keywords) + ")"
    if source_lang:
        query += f" sourcelang:{source_lang}"
    params = {
        "query": query,
        "mode": "ArtList",
        "format": "json",
        "maxrecords": max_records,
        "timespan": timespan,
    }

    payload = _get_with_retry(params)
    if payload is None:
        return []

    articles = payload.get("articles", [])
    rows = []
    for article in articles:
        url = article.get("url")
        if not url:
            continue
        title = article.get("title")
        iso3, lat, lon = resolve_country(article.get("sourcecountry", ""))

        zone_name = _detect_zone(title)
        if zone_name is not None:
            lat, lon = _zone_center(zone_name)

        rows.append(
            {
                "event_id": url,
                "date": _parse_seendate(article.get("seendate")),
                "pays": iso3,
                "lat": lat,
                "lon": lon,
                "titre": title,
                "ton": None,
                "url": url,
            }
        )

    logger.info("search_articles(%s) : %d article(s) récupéré(s)", keywords, len(rows))
    return rows


def _get_with_retry(params: dict) -> dict | None:
    for attempt in range(1, MAX_RETRIES + 1):
        response = requests.get(BASE_URL, params=params, timeout=TIMEOUT_SECONDS)
        if response.status_code == 429:
            logger.warning(
                "GDELT rate-limit (429), tentative %d/%d, pause %ds",
                attempt, MAX_RETRIES, RETRY_BACKOFF_SECONDS,
            )
            time.sleep(RETRY_BACKOFF_SECONDS)
            continue
        response.raise_for_status()
        try:
            return response.json()
        except ValueError:
            logger.error("Réponse GDELT non-JSON (probablement vide) : %s", response.text[:200])
            return None
    logger.error("GDELT injoignable après %d tentatives (rate-limit persistant).", MAX_RETRIES)
    return None


def _parse_seendate(seendate: str | None) -> str | None:
    """Convertit '20240115T120000Z' en '2024-01-15T12:00:00Z' (ISO 8601), ou None."""
    if not seendate or len(seendate) < 15:
        return None
    return f"{seendate[0:4]}-{seendate[4:6]}-{seendate[6:8]}T{seendate[9:11]}:{seendate[11:13]}:{seendate[13:15]}Z"
