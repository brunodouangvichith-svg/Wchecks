"""
Scraping best-effort des articles cités comme sources (GDELT, RSS officiels).

Confirme que le lien existe réellement (statut HTTP 200, contenu HTML
exploitable) et extrait le texte visible de la page — utilisé pour :
- marquer une source comme "vérifiée" plutôt que de faire confiance
  aveuglément au titre/URL renvoyé par la source d'origine (lien mort,
  paywall, page vide) ;
- mieux détecter les mots-clés de zone stratégique (Hormuz, Malacca...) sur le
  texte complet de l'article, le titre GDELT étant parfois tronqué à un
  fragment de la vraie manchette (voir gdelt_client.py) ;
- produire un court résumé stocké en base et affiché par le moteur QA
  (qa/engine.py) au lieu du seul titre — voir `summarize()`.

Tolérant par nature (même philosophie que sipri_client.py/usgs_client.py) :
un site inaccessible, lent, bloquant les robots (403/CAPTCHA), ou renvoyant du
contenu non-HTML est loggé et traité comme "non vérifié" — jamais une
exception qui interromprait la collecte. Timeout volontairement court et SANS
retry (contrairement aux clients d'API comme worldbank_client.py) : une page
web individuelle qui échoue une fois a peu de chances de réussir en
ré-essayant immédiatement, et ce n'est qu'une confirmation "best effort", pas
une source de données critique.
"""

import logging
import re

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 8
MAX_TEXT_CHARS = 20000
SUMMARY_MAX_SENTENCES = 3
SUMMARY_MAX_CHARS = 400
USER_AGENT = (
    "Mozilla/5.0 (compatible; GlobalChecksBot/1.0; "
    "+https://github.com/brunodouangvichith-svg/Wchecks)"
)

# Marqueurs de page anti-bot (Cloudflare et équivalents) : ces pages répondent
# souvent en HTTP 200 avec un contenu HTML normal, donc indiscernables d'un
# vrai article sans regarder le texte — constaté sur press.un.org, qui renvoie
# "Client Challenge [...] couldn't load" au lieu du communiqué demandé. Notre
# scraper (requests + BeautifulSoup, sans exécution JS) ne peut pas passer ce
# type de challenge ; le détecter évite de faire analyser une page vide/fausse
# par Joe (clients/joe_agent.py) ou de marquer `source_verifiee=True` à tort.
_BOT_CHALLENGE_MARKERS = [
    "client challenge",
    "checking your browser",
    "verify you are human",
    "enable javascript and cookies",
]


def _extract_main_text(soup: BeautifulSoup) -> str:
    """
    Isole le texte de l'ARTICLE plutôt que la page entière : `soup.get_text()`
    brut inclut la navigation/en-tête/pied de page (constaté sur un article dont
    le "résumé" produit était en réalité "Advertise Forum Jobs Subscribe...",
    du texte de menu, pas le contenu réel). Stratégie par ordre de préférence,
    sans dépendance supplémentaire (ex. readability/trafilatura) :
    1. la balise <article> (utilisée par la plupart des sites de presse) ;
    2. à défaut, la concaténation des <p> (les blocs de nav/footer utilisent
       rarement des <p> pour leurs liens, contrairement au corps d'un article) ;
    3. en dernier recours, tout le texte visible de la page.

    LIMITE CONNUE : certains sites glissent encore un bandeau d'abonnement/
    accroche ("Subscribe now...") en tête de leur <article>/premiers <p> — pas
    de scoring de densité de texte façon readability/trafilatura (dépendance
    supplémentaire pour un gain marginal sur un résumé volontairement best-
    effort, pas une extraction critique).
    """
    article_tag = soup.find("article")
    if article_tag is not None:
        text = " ".join(article_tag.get_text(separator=" ").split())
        if text:
            return text

    paragraphs = soup.find_all("p")
    if paragraphs:
        text = " ".join(p.get_text(separator=" ").strip() for p in paragraphs)
        text = " ".join(text.split())
        if text:
            return text

    return " ".join(soup.get_text(separator=" ").split())


def verify_and_extract(url: str) -> tuple[bool, str | None]:
    """
    Tente de récupérer et parser la page à `url`.

    Retourne (verifie, texte) : `verifie=True` si la page a répondu 200 avec du
    contenu HTML exploitable, `texte` le contenu de l'article (voir
    _extract_main_text, tronqué à MAX_TEXT_CHARS) ; (False, None) si la page
    est inaccessible, bloquée, vide, ou si une erreur survient.
    """
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_SECONDS)
        if response.status_code != 200 or not response.text:
            return False, None
        soup = BeautifulSoup(response.text, "lxml")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = _extract_main_text(soup)
        if not text:
            return False, None
        if any(marker in text.lower() for marker in _BOT_CHALLENGE_MARKERS):
            return False, None
        return True, text[:MAX_TEXT_CHARS]
    except Exception as exc:
        logger.info("article_scraper: échec de vérification pour '%s' (%s)", url, exc)
        return False, None


def summarize(text: str | None) -> str | None:
    """
    Résumé extractif simple : les premières phrases du texte scrapé (le "lede"
    d'un article de presse contient généralement l'essentiel du qui/quoi/quand/
    où). VOLONTAIREMENT SANS LLM/modèle de résumé automatique — même philosophie
    que qa/engine.py : gratuit, déterministe, et le résultat s'explique
    trivialement ("ce sont les 3 premières phrases"), pas une boîte noire.
    """
    if not text:
        return None
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    summary = " ".join(sentences[:SUMMARY_MAX_SENTENCES]).strip()
    if not summary:
        return None
    if len(summary) > SUMMARY_MAX_CHARS:
        summary = summary[:SUMMARY_MAX_CHARS].rsplit(" ", 1)[0] + "…"
    return summary
