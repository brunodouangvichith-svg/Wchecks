"""
Sous-agent "rapport hotspots" de Joe (chef d'orchestre) : rassemble les
analyses les plus récentes des autres sous-agents (country_news,
national_newspapers_contents, international_organizations_contents,
agences_presses_contents) et des déclarations officielles, puis demande à Joe
(clients.joe_agent.generate_themed_report) une synthèse classée par thème des
points chauds de l'actualité mondiale, tous domaines confondus. Les tables
GDELT brutes (energy_conflicts, social_tensions, military_activity) sont
délibérément EXCLUES — ce rapport synthétise ce que les sous-agents de Joe ont
déjà lu et vérifié, pas les événements bruts.

Enregistré dans daily_reports sous report_type='hotspots' (une ligne, écrasée
à chaque exécution — reflète le rapport du jour, pas un historique).
"""

import json
from datetime import datetime, timezone

from clients import joe_agent
from clients.neon_client import get_connection, upsert_generic
from logging_config import get_subagent_logger

REPORT_TYPE = "hotspots"
LABEL = "points chauds de l'actualité mondiale, tous domaines"
logger = get_subagent_logger(REPORT_TYPE)

# (table, colonne texte, colonne de tri "plus récent d'abord")
_SOURCES = [
    ("country_news", "resume", "date"),
    ("national_newspapers_contents", "content", "created_at"),
    ("international_organizations_contents", "content", "created_at"),
    ("agences_presses_contents", "content", "created_at"),
    ("official_statements", "resume", "date"),
]
ROWS_PER_SOURCE = 25


def _gather_context() -> str:
    blocks = []
    with get_connection() as conn:
        with conn.cursor() as cur:
            for table, text_col, order_col in _SOURCES:
                cur.execute(
                    f"SELECT {text_col} FROM {table} "
                    f"WHERE {text_col} IS NOT NULL AND {text_col} != '' "
                    f"ORDER BY {order_col} DESC NULLS LAST LIMIT %s",
                    (ROWS_PER_SOURCE,),
                )
                blocks.extend(f"[{table}] {row[0]}" for row in cur.fetchall())
    return "\n".join(blocks)


def run() -> int:
    context = _gather_context()
    if not context:
        logger.info("report '%s' : aucune donnée source disponible, rapport non généré", REPORT_TYPE)
        return 0

    themes = joe_agent.generate_themed_report(LABEL, context)
    if not themes:
        logger.info("report '%s' : échec de génération ou rejet par le contrôle d'intégrité", REPORT_TYPE)
        return 0

    generated_at = datetime.now(timezone.utc).isoformat()
    n = upsert_generic(
        "daily_reports", [{"report_type": REPORT_TYPE, "themes": json.dumps(themes), "created_at": generated_at}]
    )
    logger.info("report '%s' : %d thème(s) généré(s) et enregistré(s)", REPORT_TYPE, len(themes))
    return n


if __name__ == "__main__":
    from logging_config import configure_logging

    configure_logging()
    n = run()
    print(f"{n} ligne(s) envoyée(s) vers daily_reports (report_type='{REPORT_TYPE}')")
