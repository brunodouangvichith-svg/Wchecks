"""
Agent "Joe" : lecture autonome des articles sources via un LLM (Google Gemini).

Contrairement au reste du projet — VOLONTAIREMENT SANS LLM ailleurs, voir
qa/engine.py et clients/article_scraper.py (gratuit, déterministe, résultat
qui s'explique trivialement) — Joe utilise un vrai modèle de langage pour
"lire" un article comme le ferait un humain et en extraire une catégorisation
libre (pas une liste fixe de catégories), en COMPLÉMENT du classement par
mots-clés existant (conflit énergétique / tension sociale / activité
militaire), sans le remplacer.

COÛT : Gemini nécessite une clé API (config.GEMINI_API_KEY) et n'est pas
gratuit au-delà du tier gratuit de Google AI Studio — volontairement limité à
un sous-ensemble borné d'articles par cycle de collecte
(config.JOE_MAX_ARTICLES_PER_RUN), voir collectors/collect_joe_analysis.py.

Tolérant par nature (même philosophie que clients/article_scraper.py) : une
erreur API (clé absente, quota dépassé, réponse malformée, timeout) est
loggée et traitée comme "pas d'analyse Joe pour cet article", jamais une
exception qui interromprait la collecte.
"""

import json
import logging

from google import genai
from google.genai import types

import config

logger = logging.getLogger(__name__)

MODEL_NAME = "gemini-3.1-flash-lite"
TIMEOUT_MS = 30_000
MAX_INPUT_CHARS = 8000

_PROMPT_TEMPLATE = """Tu es un analyste qui lit un article de presse et en extrait les informations essentielles, comme le ferait un humain.

Voici le texte de l'article :
\"\"\"
{text}
\"\"\"

Réponds UNIQUEMENT avec un objet JSON de cette forme exacte, sans aucun texte autour :
{{
  "categorie": "ta propre catégorisation libre et précise du type d'événement décrit (en français, quelques mots, ex. 'frappe sur infrastructure pétrolière', 'sanction économique', 'négociation diplomatique', 'grève dans le secteur énergétique') — choisis la catégorie la plus pertinente, tu n'es pas limité à une liste prédéfinie",
  "gravite": "un seul mot parmi : faible, moderee, elevee, critique",
  "acteurs": "les pays/organisations/personnes clés mentionnés, séparés par des virgules",
  "resume": "un résumé de 2 à 3 phrases de l'essentiel de l'article, en français"
}}
"""

_DISCOVER_SOURCES_PROMPT_TEMPLATE = """Pour le pays {country}, liste :
1. Les 2-3 principaux journaux nationaux (presse généraliste, grande diffusion)
2. Le site officiel du gouvernement/institution de référence

Réponds UNIQUEMENT en JSON, sans texte autour, sous cette forme exacte :
[{{"nom": "...", "type": "journal ou officiel", "url": "https://..."}}]

Donne des URL de HOMEPAGE réelles et stables."""


def analyze_article(text: str | None) -> dict | None:
    """
    Envoie le texte d'un article à Gemini pour extraction + catégorisation
    autonome.

    Retourne un dict {categorie, gravite, acteurs, resume_ia, modele}, ou None
    si la clé API est absente, l'article est vide, ou l'appel échoue/renvoie
    une réponse inexploitable.
    """
    if not config.GEMINI_API_KEY or not text:
        return None
    try:
        client = genai.Client(api_key=config.GEMINI_API_KEY)
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=_PROMPT_TEMPLATE.format(text=text[:MAX_INPUT_CHARS]),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                http_options=types.HttpOptions(timeout=TIMEOUT_MS),
            ),
        )
        data = json.loads(response.text)
        categorie = data.get("categorie")
        if not categorie:
            return None
        return {
            "categorie": categorie,
            "gravite": data.get("gravite"),
            "acteurs": data.get("acteurs"),
            "resume_ia": data.get("resume"),
            "modele": MODEL_NAME,
        }
    except Exception as exc:
        logger.info("joe_agent: échec d'analyse (%s)", exc)
        return None


def discover_country_sources(country_name: str) -> list[dict] | None:
    """
    Demande à Gemini de lister les principaux journaux nationaux et le site
    officiel de référence d'un pays.

    LIMITE : s'appuie sur les CONNAISSANCES du modèle (entraînement), PAS une
    recherche web réelle — un site peut avoir changé d'URL ou disparu depuis.
    Les URL renvoyées sont vérifiées séparément par le scraping habituel
    (clients/article_scraper.py) avant d'être considérées fiables ; celles qui
    ne répondent pas sont simplement ignorées (voir collectors/collect_country_sources.py),
    pas une raison de bloquer les autres pays.

    Retourne une liste de dicts {"nom", "type", "url"}, ou None si la clé API
    est absente ou l'appel échoue/renvoie une réponse inexploitable.
    """
    if not config.GEMINI_API_KEY:
        return None
    try:
        client = genai.Client(api_key=config.GEMINI_API_KEY)
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=_DISCOVER_SOURCES_PROMPT_TEMPLATE.format(country=country_name),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                http_options=types.HttpOptions(timeout=TIMEOUT_MS),
            ),
        )
        data = json.loads(response.text)
        if not isinstance(data, list):
            return None
        sources = [
            {"nom": d.get("nom"), "type": d.get("type"), "url": d.get("url")}
            for d in data
            if d.get("nom") and d.get("url")
        ]
        return sources or None
    except Exception as exc:
        logger.info("joe_agent: échec de découverte de sources pour '%s' (%s)", country_name, exc)
        return None
