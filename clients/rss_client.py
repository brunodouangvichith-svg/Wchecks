"""
Client d'agrégation de flux RSS officiels (gratuit, sans clé).

Chaque flux est traité isolément : un flux cassé (URL changée, format non
standard) est loggé et ignoré, sans empêcher la collecte des autres flux.
"""

import logging
from calendar import timegm
from datetime import datetime, timezone
from urllib.parse import urljoin

import feedparser
import requests
from bs4 import BeautifulSoup

from clients.article_scraper import summarize, verify_and_extract

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 20


def fetch_feed_entries(feed_url: str) -> list[dict]:
    """
    Récupère toutes les entrées d'un flux RSS/Atom, chacune vérifiée/résumée
    via clients/article_scraper.py (comme pour les déclarations officielles).

    Retourne une liste de dicts {url, date, titre, extrait, langue,
    source_verifiee, resume}. Peut lever une exception si le flux est
    inaccessible/invalide — à la charge de l'appelant de l'attraper (voir
    fetch_statements et collectors/collect_country_news.py pour l'isolation
    par flux).
    """
    entries = _parse_feed(feed_url)
    rows = []
    for entry in entries:
        url = entry.get("link")
        if not url:
            continue
        title = entry.get("title", "")
        summary = entry.get("summary", "")

        # Scraping best-effort de la page (voir clients/article_scraper.py) :
        # confirme que l'article est bien accessible (pas un lien mort/retiré
        # depuis) plutôt que de faire confiance aveuglément au flux RSS, et
        # fournit un résumé du texte complet (potentiellement plus complet que
        # le résumé RSS lui-même).
        verified, article_text = verify_and_extract(url)

        rows.append(
            {
                "url": url,
                "date": _parse_entry_date(entry),
                "titre": title,
                "extrait": summary[:1000] if summary else None,
                "langue": entry.get("language"),
                "source_verifiee": verified,
                "resume": summarize(article_text),
            }
        )
    return rows


def fetch_statements(feeds: dict[str, str], keywords: list[str] | None = None) -> list[dict]:
    """
    Parcourt chaque flux RSS de `feeds` ({institution: url}) et retourne toutes
    ses entrées (aucun filtre par mot-clé : les flux suivis sont déjà une
    sélection restreinte de 2-3 institutions, voir config.RSS_FEEDS — filtrer
    en plus par mot-clé sur des titres institutionnels/diplomatiques, souvent
    formulés sans vocabulaire énergie/conflit explicite, ne laissait passer que
    de rares correspondances, voir historique du projet).

    `keywords` est gardé en paramètre (inutilisé si None/omis) pour compatibilité
    ascendante avec un éventuel appelant qui voudrait filtrer explicitement.

    Retourne une liste de dicts {url, date, institution, titre, extrait, langue}.
    """
    keywords_lower = [kw.lower() for kw in keywords] if keywords else None
    rows: list[dict] = []

    for institution, feed_url in feeds.items():
        try:
            entries = fetch_feed_entries(feed_url)
        except Exception:
            logger.exception("rss_client: échec de lecture du flux '%s' (%s)", institution, feed_url)
            continue

        for entry in entries:
            if keywords_lower:
                haystack = f"{entry['titre']} {entry.get('extrait') or ''}".lower()
                if not any(kw in haystack for kw in keywords_lower):
                    continue
            rows.append({**entry, "institution": institution})

    logger.info("fetch_statements : %d déclaration(s) retenue(s) sur %d flux", len(rows), len(feeds))
    return rows


# Chemins RSS conventionnels essayés en repli si la page n'annonce aucun flux
# via <link rel="alternate"> (beaucoup de sites d'actualité en exposent un sans
# l'annoncer explicitement dans le <head>).
_COMMON_FEED_PATHS = ["/feed", "/feed/", "/rss", "/rss.xml", "/rss/index.xml"]


def _is_real_feed(candidate_url: str) -> bool:
    """
    Vérifie que `candidate_url` répond avec un VRAI flux RSS/Atom exploitable,
    pas juste un statut 200 — constaté que certains sites (SPA, pages
    catch-all) renvoient 200 avec la page d'accueil HTML pour n'importe quelle
    URL, y compris des chemins RSS inventés qui n'existent pas réellement.
    """
    try:
        response = requests.get(candidate_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        parsed = feedparser.parse(response.content)
        return bool(parsed.entries)
    except Exception:
        return False


def discover_feed_url(homepage_url: str) -> str | None:
    """
    Cherche un flux RSS/Atom pour `homepage_url` : d'abord via la balise
    <link rel="alternate" type="application/rss+xml|atom+xml"> annoncée dans
    le <head> (technique standard), puis en repli via une liste de chemins
    RSS conventionnels (_COMMON_FEED_PATHS) — utilisé pour les sources
    découvertes par l'agent Joe (voir collectors/collect_country_sources.py).
    Chaque candidat est validé comme un VRAI flux exploitable (voir
    _is_real_feed) avant d'être retourné, pas seulement un statut 200.

    Retourne l'URL absolue du flux, ou None si non trouvé ou en cas d'erreur
    (site inaccessible, HTML non exploitable) — tolérant par nature, comme le
    reste de ce client. La plupart des sites institutionnels n'ont pas de flux
    du tout ; ce n'est pas une erreur, juste une source non lisible ainsi.
    """
    try:
        response = requests.get(homepage_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")
        link = soup.find("link", rel="alternate", type=lambda t: t and ("rss" in t or "atom" in t))
        if link and link.get("href"):
            candidate = urljoin(homepage_url, link["href"])
            if _is_real_feed(candidate):
                return candidate
    except Exception as exc:
        logger.info("rss_client: échec de lecture de '%s' pour la découverte de flux (%s)", homepage_url, exc)

    for path in _COMMON_FEED_PATHS:
        candidate = urljoin(homepage_url, path)
        if _is_real_feed(candidate):
            return candidate

    return None


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
