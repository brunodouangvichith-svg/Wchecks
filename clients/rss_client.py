"""
Client d'agrégation de flux RSS officiels (gratuit, sans clé).

Chaque flux est traité isolément : un flux cassé (URL changée, format non
standard) est loggé et ignoré, sans empêcher la collecte des autres flux.
"""

import logging
from calendar import timegm
from datetime import datetime, timezone

import feedparser
import requests

from clients.article_scraper import summarize, verify_and_extract

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 20


def fetch_statements(feeds: dict[str, str], keywords: list[str]) -> list[dict]:
    """
    Parcourt chaque flux RSS de `feeds` ({institution: url}) et retourne les entrées
    dont le titre ou le résumé contient au moins un mot-clé de `keywords`.

    Retourne une liste de dicts {url, date, institution, titre, extrait, langue}.
    """
    keywords_lower = [kw.lower() for kw in keywords]
    rows: list[dict] = []

    for institution, feed_url in feeds.items():
        try:
            entries = _parse_feed(feed_url)
        except Exception:
            logger.exception("rss_client: échec de lecture du flux '%s' (%s)", institution, feed_url)
            continue

        for entry in entries:
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            haystack = f"{title} {summary}".lower()
            if not any(kw in haystack for kw in keywords_lower):
                continue

            url = entry.get("link")
            if not url:
                continue

            # Scraping best-effort de la page (voir clients/article_scraper.py) :
            # confirme que la déclaration officielle est bien accessible (pas un
            # lien mort/retiré depuis) plutôt que de faire confiance aveuglément
            # au flux RSS, et fournit un résumé du texte complet de la page
            # (potentiellement plus complet que le résumé RSS lui-même).
            verified, article_text = verify_and_extract(url)

            rows.append(
                {
                    "url": url,
                    "date": _parse_entry_date(entry),
                    "institution": institution,
                    "titre": title,
                    "extrait": summary[:1000] if summary else None,
                    "langue": entry.get("language"),
                    "source_verifiee": verified,
                    "resume": summarize(article_text),
                }
            )

    logger.info("fetch_statements : %d déclaration(s) retenue(s) sur %d flux", len(rows), len(feeds))
    return rows


def _parse_feed(feed_url: str):
    # Récupéré via requests (timeout explicite) plutôt que de laisser feedparser.parse()
    # ouvrir la connexion lui-même : feedparser n'applique aucun timeout par défaut et
    # peut bloquer indéfiniment sur un flux lent/muet (constaté en pratique).
    response = requests.get(feed_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    parsed = feedparser.parse(response.content)
    if parsed.bozo and not parsed.entries:
        raise ValueError(f"Flux invalide ou vide : {parsed.bozo_exception}")
    return parsed.entries


def _parse_entry_date(entry) -> str | None:
    struct = entry.get("published_parsed") or entry.get("updated_parsed")
    if not struct:
        return None
    dt = datetime.fromtimestamp(timegm(struct), tz=timezone.utc)
    return dt.isoformat()
