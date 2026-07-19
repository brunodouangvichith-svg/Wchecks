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
import re
import time

from google import genai
from google.genai import types
from google.genai.errors import ClientError

import config

logger = logging.getLogger(__name__)

MODEL_NAME = "gemini-3.1-flash-lite"
TIMEOUT_MS = 30_000
MAX_INPUT_CHARS = 8000

# Tier gratuit de Google AI Studio pour gemini-3.1-flash-lite : plafonné à 15
# requêtes/minute (constaté en pratique via l'erreur 429 RESOURCE_EXHAUSTED,
# quotaId GenerateRequestsPerMinutePerProjectPerModel-FreeTier, quotaValue 15).
# Traduire un article à la fois y serait totalement impraticable au volume de
# ce projet (jusqu'à ~1500 articles/cycle country_news) — voir translate_batch()
# qui regroupe plusieurs textes par appel pour multiplier le débit utile dans
# cette même limite.
MAX_RETRIES = 3
RETRY_FALLBACK_SECONDS = 20
TRANSLATE_BATCH_SIZE = 20
# Les rapports journaliers (generate_themed_report) agrègent des extraits de
# PLUSIEURS tables sources en un seul appel Gemini (2 sous-agents dédiés, voir
# collectors/collect_report_hotspots.py et collect_report_financial.py) — un
# contexte bien plus large qu'un article individuel (MAX_INPUT_CHARS).
REPORT_MAX_INPUT_CHARS = 25_000


def _generate_with_retry(contents: str, response_mime_type: str | None = None):
    """
    Appel Gemini générique avec retry/backoff sur 429 (quota par minute
    dépassé) — respecte le `retryDelay` suggéré par l'API quand présent,
    sinon un délai fixe. Lève la dernière exception si toutes les tentatives
    échouent (à la charge de l'appelant, qui traite déjà ça comme "pas de
    résultat" plutôt qu'un crash).
    """
    client = genai.Client(api_key=config.GEMINI_API_KEY)
    gen_config = types.GenerateContentConfig(http_options=types.HttpOptions(timeout=TIMEOUT_MS))
    if response_mime_type:
        gen_config.response_mime_type = response_mime_type

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return client.models.generate_content(model=MODEL_NAME, contents=contents, config=gen_config)
        except ClientError as exc:
            last_error = exc
            if exc.code != 429:
                raise
            delay = RETRY_FALLBACK_SECONDS
            match = re.search(r"retryDelay['\"]?:\s*['\"]?(\d+)", str(exc))
            if match:
                delay = int(match.group(1)) + 1
            logger.info(
                "joe_agent: quota atteint (429), tentative %d/%d, pause %ds",
                attempt, MAX_RETRIES, delay,
            )
            time.sleep(delay)
    raise last_error

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

_TRANSLATE_PROMPT_TEMPLATE = """Traduis ce texte en anglais. Réponds UNIQUEMENT avec la traduction, sans commentaire ni guillemets. Si le texte est déjà en anglais, renvoie-le tel quel.

\"\"\"
{text}
\"\"\""""

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
        response = _generate_with_retry(
            _PROMPT_TEMPLATE.format(text=text[:MAX_INPUT_CHARS]), response_mime_type="application/json"
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


def translate_to_english(text: str | None) -> str | None:
    """
    Traduit un texte court en anglais via Gemini. Pour traduire PLUSIEURS
    textes (le cas normal en collecte), préférer translate_batch() — un appel
    par texte est trop lent face au plafond de 15 requêtes/minute du tier
    gratuit (voir MAX_RETRIES/_generate_with_retry).

    Retourne le texte traduit, ou None si la clé API est absente, le texte est
    vide, ou l'appel échoue/renvoie une réponse inexploitable (dans ce cas,
    l'appelant garde le texte original plutôt que de perdre le résumé).
    """
    if not config.GEMINI_API_KEY or not text:
        return None
    try:
        response = _generate_with_retry(_TRANSLATE_PROMPT_TEMPLATE.format(text=text))
        translated = (response.text or "").strip()
        return translated or None
    except Exception as exc:
        logger.info("joe_agent: échec de traduction (%s)", exc)
        return None


def translate_batch(texts: list[str | None]) -> list[str | None]:
    """
    Traduit plusieurs textes courts en anglais en UN SEUL appel Gemini (au
    lieu d'un appel par texte) — le tier gratuit de Gemini plafonne à 15
    requêtes/minute (constaté en pratique, voir MAX_RETRIES en tête de
    module), ce qui rendrait un appel par article totalement impraticable au
    volume de ce projet (jusqu'à ~1500 articles/cycle country_news). Découpé
    automatiquement en lots de TRANSLATE_BATCH_SIZE pour garder une taille de
    prompt raisonnable et limiter la casse si un lot échoue.

    Appliqué au résumé DÉJÀ EXTRAIT (voir clients/article_scraper.summarize(),
    quelques phrases), pas au texte complet de l'article — même résultat
    utile pour l'affichage, en une fraction du coût en tokens.

    Retourne une liste de MÊME LONGUEUR que `texts` (alignée par position) :
    la traduction pour chaque texte non vide, ou None si ce texte était vide,
    la clé API est absente, ou le lot correspondant a échoué.
    """
    results: list[str | None] = [None] * len(texts)
    if not config.GEMINI_API_KEY:
        return results

    indexed_non_empty = [(i, t) for i, t in enumerate(texts) if t]
    for batch_start in range(0, len(indexed_non_empty), TRANSLATE_BATCH_SIZE):
        batch = indexed_non_empty[batch_start : batch_start + TRANSLATE_BATCH_SIZE]
        numbered = "\n".join(f"{n}: {t}" for n, (_, t) in enumerate(batch))
        prompt = (
            "Traduis chacun des textes numérotés suivants en anglais (garde tel "
            "quel un texte déjà en anglais). Réponds UNIQUEMENT avec un objet "
            'JSON associant chaque numéro (en chaîne) à sa traduction, ex. '
            '{"0": "...", "1": "..."}, sans commentaire ni texte autour.\n\n'
            f"{numbered}"
        )
        try:
            response = _generate_with_retry(prompt, response_mime_type="application/json")
            data = json.loads(response.text)
            for n, (original_index, _) in enumerate(batch):
                results[original_index] = data.get(str(n))
        except Exception as exc:
            logger.info(
                "joe_agent: échec de traduction groupée (lot de %d textes) (%s)", len(batch), exc
            )
    return results


_HOMEPAGE_BATCH_PROMPT_TEMPLATE = """Voici des extraits de la page d'accueil de plusieurs journaux, numérotés. Pour CHACUN, donne :
- un court résumé (2-3 phrases, en français) de l'actualité mise en avant sur cette page ;
- un thème principal (quelques mots, libre, ex. "politique intérieure", "conflit international", "économie") ;
- un contrôle d'intégrité : "fiable": true UNIQUEMENT si ton résumé se fonde STRICTEMENT sur des informations présentes dans l'extrait fourni, sans rien inventer ni ajouter qui n'y figure pas ; "fiable": false si tu as dû déduire, extrapoler, ou si l'extrait est trop pauvre/confus pour un résumé fiable.

{numbered}

Réponds UNIQUEMENT avec un objet JSON associant chaque numéro (en chaîne) à un objet {{"content": "...", "theme": "...", "fiable": true|false}}, sans commentaire ni texte autour."""


def analyze_homepages_batch(texts: list[str | None]) -> list[dict | None]:
    """
    Analyse plusieurs pages d'accueil de journaux (voir
    collectors/collect_national_newspapers_contents.py) en appels Gemini
    groupés — même rationnel que translate_batch() : le tier gratuit plafonne
    à 15 requêtes/minute, un appel par journal serait inutilement lent pour
    ~30 journaux traités une fois par jour.

    CONTRÔLE D'INTÉGRITÉ : Joe s'auto-évalue dans le même appel ("fiable",
    voir _HOMEPAGE_BATCH_PROMPT_TEMPLATE) — un résultat marqué "fiable": false
    (résumé jugé par Joe lui-même comme non strictement fondé sur le texte
    fourni) est REJETÉ ici et traité comme un échec d'analyse, jamais stocké.
    Pas un second appel Gemini séparé (doublerait le coût, déjà contraint par
    le plafond quotidien) : l'auto-évaluation fait partie de la même requête
    que la production du résumé.

    Retourne une liste de MÊME LONGUEUR que `texts` (alignée par position) :
    {"content", "theme"} pour chaque texte non vide, analysé avec succès ET
    jugé fiable par Joe, ou None si ce texte était vide, la clé API est
    absente, le lot a échoué, ou l'auto-évaluation a rejeté le résultat.
    """
    results: list[dict | None] = [None] * len(texts)
    if not config.GEMINI_API_KEY:
        return results

    indexed_non_empty = [(i, t) for i, t in enumerate(texts) if t]
    rejected = 0
    for batch_start in range(0, len(indexed_non_empty), TRANSLATE_BATCH_SIZE):
        batch = indexed_non_empty[batch_start : batch_start + TRANSLATE_BATCH_SIZE]
        numbered = "\n\n".join(f"{n}: {t[:2000]}" for n, (_, t) in enumerate(batch))
        prompt = _HOMEPAGE_BATCH_PROMPT_TEMPLATE.format(numbered=numbered)
        try:
            response = _generate_with_retry(prompt, response_mime_type="application/json")
            data = json.loads(response.text)
            for n, (original_index, _) in enumerate(batch):
                item = data.get(str(n))
                if not item or not item.get("content"):
                    continue
                if not item.get("fiable", False):
                    rejected += 1
                    continue
                results[original_index] = {"content": item.get("content"), "theme": item.get("theme")}
        except Exception as exc:
            logger.info(
                "joe_agent: échec d'analyse de pages d'accueil (lot de %d) (%s)", len(batch), exc
            )
    if rejected:
        logger.info("joe_agent: %d résultat(s) rejeté(s) par le contrôle d'intégrité (fiable=false)", rejected)
    return results


_ORCHESTRATE_PROMPT_TEMPLATE = """Tu es le "chef d'orchestre" d'un sous-agent de veille qui scrape et résume des pages d'accueil de sites web.

Sous-agent : "{name}"
Éléments en attente d'analyse (jamais encore traités, ou dont le contenu est le plus ancien) : {pending}
Total d'éléments suivis par ce sous-agent : {total}
Plafond dur pour cette exécution (ne jamais dépasser) : {hard_cap}

Décide combien d'éléments ce sous-agent doit traiter lors de cette exécution, en autonomie (aucune supervision humaine) : privilégie un traitement complet si le nombre en attente est raisonnable, mais reste prudent si le volume est important pour ne pas monopoliser le quota Gemini partagé avec les autres sous-agents.

Réponds UNIQUEMENT avec un objet JSON {{"batch_size": <entier>}}, sans commentaire ni texte autour."""


def orchestrate_subagent_batch(name: str, pending: int, total: int, hard_cap: int) -> int:
    """
    Joe, en "chef d'orchestre", décide de manière autonome combien d'éléments
    le sous-agent `name` doit traiter lors de cette exécution — plutôt qu'une
    règle fixe codée en dur, un appel Gemini léger arbitre le compromis entre
    "tout traiter tant que c'est raisonnable" et "ne pas épuiser le quota
    quotidien partagé avec les autres sous-agents" (voir _generate_with_retry).

    Repli tolérant : si la clé API est absente, l'appel échoue, ou la réponse
    est inexploitable, retourne simplement `min(pending, hard_cap)` — le
    sous-agent continue de fonctionner (avec une règle simple) plutôt que de
    bloquer sur l'échec d'une décision d'orchestration.
    """
    fallback = min(pending, hard_cap)
    if not config.GEMINI_API_KEY or pending <= 0:
        return fallback
    try:
        response = _generate_with_retry(
            _ORCHESTRATE_PROMPT_TEMPLATE.format(name=name, pending=pending, total=total, hard_cap=hard_cap),
            response_mime_type="application/json",
        )
        data = json.loads(response.text)
        batch_size = int(data.get("batch_size", fallback))
        return max(0, min(batch_size, hard_cap, pending))
    except Exception as exc:
        logger.info("joe_agent: échec d'orchestration pour '%s' (%s), repli sur %d", name, exc, fallback)
        return fallback


_REPORT_PROMPT_TEMPLATE = """Tu es Joe, un analyste de veille qui rédige un rapport journalier de synthèse pour le sujet suivant : {label}.

Extraits collectés (une source par ligne, format "[table] texte") :
\"\"\"
{context}
\"\"\"

Rédige une synthèse organisée PAR THÈME : regroupe les extraits par thématique commune (ne fais surtout pas une liste plate, un thème doit rassembler plusieurs extraits liés quand c'est possible). Pour chaque thème identifié, donne :
- "theme" : un titre de thème court (quelques mots, en français) ;
- "summary" : une synthèse de plusieurs phrases (en français) des informations pertinentes à ce thème ;
- "fiable" : un contrôle d'intégrité — true UNIQUEMENT si la synthèse se fonde STRICTEMENT sur les extraits fournis, sans rien inventer ni compléter avec des connaissances externes ; false si tu as dû déduire, extrapoler, ou si les extraits disponibles sont trop pauvres pour un thème donné.

Réponds UNIQUEMENT avec un tableau JSON de cette forme exacte, sans texte autour :
[{{"theme": "...", "summary": "...", "fiable": true|false}}]"""


def generate_themed_report(label: str, context: str) -> list[dict] | None:
    """
    Demande à Joe une synthèse d'un rapport journalier, organisée par thème,
    à partir d'un contexte texte déjà rassemblé par le sous-agent appelant
    (voir collectors/collect_report_hotspots.py et collect_report_financial.py
    — respectivement "points chauds de l'actualité mondiale" et "données
    financières internationales et par pays", les 2 rapports demandés).

    CONTRÔLE D'INTÉGRITÉ : même principe que analyze_homepages_batch — Joe
    s'auto-évalue par thème dans le même appel ("fiable"), un thème jugé non
    strictement fondé sur le contexte fourni est REJETÉ ici plutôt que stocké.

    Retourne une liste de {"theme", "summary"}, ou None si la clé API est
    absente, le contexte est vide, l'appel échoue, ou aucun thème ne survit au
    contrôle d'intégrité.
    """
    if not config.GEMINI_API_KEY or not context:
        return None
    try:
        response = _generate_with_retry(
            _REPORT_PROMPT_TEMPLATE.format(label=label, context=context[:REPORT_MAX_INPUT_CHARS]),
            response_mime_type="application/json",
        )
        data = json.loads(response.text)
        if not isinstance(data, list):
            return None
        themes = []
        rejected = 0
        for item in data:
            if not item.get("theme") or not item.get("summary"):
                continue
            if not item.get("fiable", False):
                rejected += 1
                continue
            themes.append({"theme": item["theme"], "summary": item["summary"]})
        if rejected:
            logger.info("joe_agent: %d thème(s) rejeté(s) par le contrôle d'intégrité (fiable=false)", rejected)
        return themes or None
    except Exception as exc:
        logger.info("joe_agent: échec de génération du rapport '%s' (%s)", label, exc)
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
        response = _generate_with_retry(
            _DISCOVER_SOURCES_PROMPT_TEMPLATE.format(country=country_name),
            response_mime_type="application/json",
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
