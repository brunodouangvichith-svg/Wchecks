"""
Sous-agent "rapport financier" de Joe (chef d'orchestre) : rassemble la
dernière valeur connue par pays sur TOUTES les dimensions financières suivies
(dette, économie, budget défense, notations de crédit, score de risque
global — voir demande utilisateur), puis demande à Joe
(clients.joe_agent.generate_themed_report) une synthèse classée par thème des
données financières internationales et par pays.

Enregistré dans daily_reports sous report_type='financial' (une ligne, écrasée
à chaque exécution — reflète le rapport du jour, pas un historique).
"""

import json
from datetime import datetime, timezone

from clients import joe_agent
from clients.neon_client import get_connection, upsert_generic
from logging_config import get_subagent_logger

REPORT_TYPE = "financial"
LABEL = "données financières internationales et par pays"
logger = get_subagent_logger(REPORT_TYPE)


def _gather_context() -> str:
    lines = []
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT ON (pays_code) pays_code, dette_pct_pib, dette_montant_milliards_usd "
                "FROM country_debt ORDER BY pays_code, annee DESC"
            )
            for pays, pct, montant in cur.fetchall():
                lines.append(f"[country_debt] {pays}: dette {pct}% du PIB, {montant} Md USD")

            cur.execute(
                "SELECT DISTINCT ON (pays_code) pays_code, impots_pct_pib, chomage_pct, inflation_pct "
                "FROM country_economy ORDER BY pays_code, annee DESC"
            )
            for pays, impots, chomage, inflation in cur.fetchall():
                lines.append(
                    f"[country_economy] {pays}: impôts {impots}% du PIB, chômage {chomage}%, inflation {inflation}%"
                )

            cur.execute(
                "SELECT DISTINCT ON (pays_code) pays_code, budget_pct_pib "
                "FROM defense_budget ORDER BY pays_code, annee DESC"
            )
            for pays, budget in cur.fetchall():
                lines.append(f"[defense_budget] {pays}: budget défense {budget}% du PIB")

            cur.execute(
                "SELECT pays_code, agence, note, perspective FROM credit_ratings ORDER BY pays_code, agence"
            )
            for pays, agence, note, perspective in cur.fetchall():
                lines.append(f"[credit_ratings] {pays}: notation {agence} {note}, perspective {perspective}")

            cur.execute(
                "SELECT DISTINCT ON (pays_code) pays_code, score_global "
                "FROM risk_scores ORDER BY pays_code, date_calcul DESC"
            )
            for pays, score in cur.fetchall():
                lines.append(f"[risk_scores] {pays}: score de risque global {score}/100")
    return "\n".join(lines)


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
