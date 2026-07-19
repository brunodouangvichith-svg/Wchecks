"""
Collecteur de l'agent "Joe" (voir clients/joe_agent.py) : sélectionne un
sous-ensemble borné d'articles déjà scrapés/vérifiés (voir
clients/article_scraper.py) sans analyse Joe existante, et les fait analyser
par le LLM (catégorisation autonome + résumé), en complément — pas en
remplacement — du classement par mots-clés existant.

Volontairement borné à config.JOE_MAX_ARTICLES_PER_RUN : Gemini n'est pas
gratuit au-delà du tier gratuit de Google AI Studio, donc pas question de
faire lire à Joe les ~750 articles scrapés par cycle GDELT — un sous-ensemble
régulier suffit à enrichir progressivement les événements les plus récents.
"""

import logging

import config
from clients.article_scraper import verify_and_extract
from clients.joe_agent import analyze_article
from clients.neon_client import get_connection, upsert_generic

logger = logging.getLogger(__name__)

SOURCE_TABLES = [
    "energy_conflicts", "social_tensions", "military_activity", "official_statements",
    "country_news",
]


def _pending_articles(cur, limit_per_table: int) -> list[tuple[str, str]]:
    """
    Retourne [(source_table, url)] pour les articles déjà vérifiés (scraping
    réussi) sans analyse Joe existante, les plus récents d'abord.

    `limit_per_table` est appliqué À CHAQUE TABLE, pas globalement : une table
    à fort volume (energy_conflicts, social_tensions) a presque toujours un
    backlog qui dépasse le budget total à elle seule — sans répartition par
    table, un simple `candidates[:budget]` pris sur la liste concaténée finit
    par ne traiter QUE la première table de SOURCE_TABLES à chaque cycle,
    privant les autres (dont official_statements) d'analyse Joe indéfiniment.
    """
    pending = []
    for table in SOURCE_TABLES:
        cur.execute(
            f"""
            SELECT s.url FROM {table} s
            LEFT JOIN joe_analysis j ON j.source_table = %s AND j.url = s.url
            WHERE s.source_verifiee = TRUE AND j.id IS NULL
            ORDER BY s.date DESC NULLS LAST
            LIMIT %s
            """,
            (table, limit_per_table),
        )
        pending.extend((table, url) for (url,) in cur.fetchall())
    return pending


def run() -> int:
    per_table_limit = max(1, config.JOE_MAX_ARTICLES_PER_RUN // len(SOURCE_TABLES))

    with get_connection() as conn:
        with conn.cursor() as cur:
            candidates = _pending_articles(cur, per_table_limit)

    rows = []
    for table, url in candidates:
        verified, text = verify_and_extract(url)
        if not verified or not text:
            continue
        analysis = analyze_article(text)
        if analysis is None:
            continue
        rows.append({"source_table": table, "url": url, **analysis})

    logger.info(
        "collect_joe_analysis : %d candidat(s), %d analysé(s) avec succès",
        len(candidates), len(rows),
    )
    return upsert_generic("joe_analysis", rows)


if __name__ == "__main__":
    from logging_config import configure_logging

    configure_logging()
    n = run()
    print(f"{n} ligne(s) envoyée(s) vers joe_analysis")
