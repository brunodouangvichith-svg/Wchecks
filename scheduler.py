"""
Scheduler d'arrière-plan : exécute chaque collector à la fréquence définie dans
config.FREQUENCIES_MINUTES, en isolant les échecs (un collector qui plante n'arrête
pas les autres) et en alertant en cas d'échecs répétés d'une même source.

Point d'entrée du service Render : `python scheduler.py`.

DÉPLOIEMENT RENDER : le tier gratuit ne propose PAS de Background Worker (erreur
"service type is not available for this plan" constatée en pratique — l'hypothèse
initiale du projet était fausse sur ce point). Ce module tourne donc comme un
**Web Service** gratuit : APScheduler s'exécute dans des threads d'arrière-plan
(BackgroundScheduler, pas BlockingScheduler) pendant qu'un serveur HTTP minimal
répond sur le port fourni par Render (nécessaire pour qu'un Web Service soit
considéré "vivant"). Conséquence : Render endort le service après ~15 min sans
requête HTTP entrante, ce qui arrêterait aussi le scheduler — un ping externe
gratuit (cron-job.org, UptimeRobot...) doit appeler l'URL du service toutes les
10-14 minutes pour le maintenir éveillé. Voir README, section déploiement.

Les collectors "à la demande" (minerais USGS) ne sont pas planifiés ici — voir
cli.py pour un déclenchement manuel.
"""

import http.server
import logging
import os
import signal
import sys
from datetime import datetime, timezone

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler

import config
from collectors import (
    collect_brent,
    collect_conflicts,
    collect_debt,
    collect_defense_budget,
    collect_economy,
    collect_industry,
    collect_maritime_traffic,
    collect_military_activity,
    collect_official_statements,
    collect_oil_gas_production,
    collect_social_tensions,
    collect_spr,
)
from scoring import risk_score

logger = logging.getLogger("scheduler")

# Nombre d'échecs consécutifs d'une même source avant de logguer une alerte critique.
ALERT_THRESHOLD = 3

# (job_id, fréquence en minutes, fonction run() du collector)
JOBS = [
    ("spr", config.FREQUENCIES_MINUTES["spr"], collect_spr.run),
    ("brent", config.FREQUENCIES_MINUTES["brent"], collect_brent.run),
    ("oil_gas_production", config.FREQUENCIES_MINUTES["oil_gas_production"], collect_oil_gas_production.run),
    ("conflicts", config.FREQUENCIES_MINUTES["conflicts"], collect_conflicts.run),
    ("social_tensions", config.FREQUENCIES_MINUTES["social_tensions"], collect_social_tensions.run),
    ("military_activity", config.FREQUENCIES_MINUTES["military_activity"], collect_military_activity.run),
    ("country_debt", config.FREQUENCIES_MINUTES["worldbank_indicators"], collect_debt.run),
    ("country_economy", config.FREQUENCIES_MINUTES["worldbank_indicators"], collect_economy.run),
    ("defense_budget", config.FREQUENCIES_MINUTES["worldbank_indicators"], collect_defense_budget.run),
    ("country_industry", config.FREQUENCIES_MINUTES["worldbank_indicators"], collect_industry.run),
    ("official_statements", config.FREQUENCIES_MINUTES["official_statements"], collect_official_statements.run),
    ("maritime_traffic", config.FREQUENCIES_MINUTES["maritime_traffic"], collect_maritime_traffic.run),
    ("risk_score", config.FREQUENCIES_MINUTES["risk_score"], risk_score.run),
]

_consecutive_failures: dict[str, int] = {}


def _configure_logging() -> None:
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    file_handler = logging.FileHandler(config.LOG_DIR / "scheduler.log", encoding="utf-8")
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(console_handler)


def _run_job(job_id: str, run_func) -> None:
    """Exécute un collector, logue le résultat, isole l'échec et alerte si répété."""
    logger.info("job '%s' : démarrage", job_id)
    try:
        result = run_func()
        logger.info("job '%s' : succès (%s)", job_id, result)
        _consecutive_failures[job_id] = 0
    except Exception:
        _consecutive_failures[job_id] = _consecutive_failures.get(job_id, 0) + 1
        logger.exception("job '%s' : échec (%d consécutif(s))", job_id, _consecutive_failures[job_id])
        if _consecutive_failures[job_id] >= ALERT_THRESHOLD:
            logger.critical(
                "ALERTE : la source '%s' échoue depuis %d exécutions consécutives",
                job_id, _consecutive_failures[job_id],
            )


def build_scheduler() -> BackgroundScheduler:
    # Pool de threads dimensionné au-delà du nombre de jobs : par défaut APScheduler
    # n'en alloue que 10, ce qui suffit à faire "manquer" (misfire) le démarrage
    # immédiat d'un job si plus de 10 se déclenchent au même instant (ex. tous les
    # next_run_time=now au démarrage du process) — constaté en pratique avec
    # 'official_statements' silencieusement sauté faute de thread disponible à temps.
    executors = {"default": ThreadPoolExecutor(max_workers=max(20, len(JOBS) * 2))}
    # misfire_grace_time généreux : un job en retard (thread occupé, machine chargée)
    # doit quand même s'exécuter plutôt que d'être sauté silencieusement.
    job_defaults = {"misfire_grace_time": 3600}

    scheduler = BackgroundScheduler(timezone="UTC", executors=executors, job_defaults=job_defaults)
    for job_id, frequency_minutes, run_func in JOBS:
        scheduler.add_job(
            _run_job,
            "interval",
            minutes=frequency_minutes,
            args=[job_id, run_func],
            id=job_id,
            next_run_time=datetime.now(timezone.utc),  # exécution immédiate, en UTC (scheduler configuré timezone="UTC")
            max_instances=1,
            coalesce=True,
        )
        logger.info("job '%s' planifié toutes les %d minutes", job_id, frequency_minutes)
    return scheduler


def _handle_sigterm(signum, frame) -> None:
    logger.info("signal %s reçu, arrêt du scheduler", signum)
    sys.exit(0)


class _HealthHandler(http.server.BaseHTTPRequestHandler):
    """Répond OK à toute requête — sert uniquement à satisfaire Render (Web Service)
    et le ping externe qui maintient le service éveillé (voir docstring du module)."""

    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"OK - scheduler actif")

    def log_message(self, format, *args) -> None:
        pass  # évite de polluer scheduler.log avec chaque requête de ping


def main() -> None:
    _configure_logging()
    signal.signal(signal.SIGTERM, _handle_sigterm)

    logger.info("démarrage du scheduler (%d job(s) planifié(s))", len(JOBS))
    scheduler = build_scheduler()
    scheduler.start()

    port = int(os.environ.get("PORT", 10000))
    server = http.server.HTTPServer(("0.0.0.0", port), _HealthHandler)
    logger.info("serveur de health-check démarré sur le port %d (requis par Render Web Service)", port)
    try:
        server.serve_forever()
    except (KeyboardInterrupt, SystemExit):
        logger.info("arrêt du scheduler")
    finally:
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    main()
