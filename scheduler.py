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
import json
import logging
import os
import signal
import sys
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

import config
from collectors import (
    collect_brent,
    collect_conflicts,
    collect_country_news,
    collect_country_sources,
    collect_credit_ratings,
    collect_debt,
    collect_defense_budget,
    collect_economy,
    collect_industry,
    collect_joe_analysis,
    collect_maritime_traffic,
    collect_military_activity,
    collect_national_newspapers_contents,
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
    ("credit_ratings", config.FREQUENCIES_MINUTES["worldbank_indicators"], collect_credit_ratings.run),
    ("risk_score", config.FREQUENCIES_MINUTES["risk_score"], risk_score.run),
    # frequency_minutes ignoré pour ce job : planifié via CRON_JOBS ci-dessous (2x/jour à heures fixes).
    ("joe_analysis", config.FREQUENCIES_MINUTES["joe_analysis"], collect_joe_analysis.run),
    ("country_sources", config.FREQUENCIES_MINUTES["country_sources"], collect_country_sources.run),
    ("country_news", config.FREQUENCIES_MINUTES["country_news"], collect_country_news.run),
    (
        "national_newspapers_contents",
        config.FREQUENCIES_MINUTES["national_newspapers_contents"],
        collect_national_newspapers_contents.run,
    ),
]

# Jobs planifiés à heures fixes (vraie expression cron) plutôt qu'à intervalle
# glissant depuis le dernier redémarrage — utile pour un job qu'on veut voir
# tourner à des heures prévisibles (ex. Joe, 2x/jour à 06h00 et 18h00 UTC),
# plutôt qu'"toutes les 12h depuis que le service a redémarré".
CRON_JOBS = {
    "joe_analysis": "0 6,18 * * *",
}

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
        if job_id in CRON_JOBS:
            trigger = CronTrigger.from_crontab(CRON_JOBS[job_id], timezone="UTC")
            scheduler.add_job(
                _run_job,
                trigger,
                args=[job_id, run_func],
                id=job_id,
                next_run_time=datetime.now(timezone.utc),  # exécution immédiate au démarrage, puis suit le cron
                max_instances=1,
                coalesce=True,
            )
            logger.info("job '%s' planifié via cron '%s' (UTC)", job_id, CRON_JOBS[job_id])
            continue

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
    """
    Sert deux rôles :
    - toute requête GET satisfait Render (Web Service) et le ping externe qui
      maintient le service éveillé (voir docstring du module) ;
    - GET /ask?q=<question> répond en JSON à partir des données réelles de Neon
      (voir qa/engine.py), pour l'interface vocale de la carte (viz/build_map.py).
    - GET /joe-articles?limit=N renvoie les articles analysés par l'agent Joe
      (voir qa/engine.get_joe_articles), pour le panneau dédié de la carte.
      Accès autorisé cross-origin (Access-Control-Allow-Origin: *) : la carte est
      servie depuis GitHub Pages, un domaine différent de celui de ce service.
    """

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/ask":
            self._handle_ask(parsed)
            return
        if parsed.path == "/joe-articles":
            self._handle_joe_articles(parsed)
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"OK - scheduler actif")

    def _handle_ask(self, parsed) -> None:
        question = parse_qs(parsed.query).get("q", [""])[0]
        try:
            from qa.engine import answer_question

            answer = answer_question(question) if question.strip() else "Question vide."
        except Exception:
            logger.exception("/ask : échec pour la question '%s'", question)
            answer = "Erreur interne en traitant la question."

        body = json.dumps({"question": question, "answer": answer}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _handle_joe_articles(self, parsed) -> None:
        query_params = parse_qs(parsed.query)
        limit_param = query_params.get("limit", ["50"])[0]
        search_param = query_params.get("q", [""])[0].strip() or None
        try:
            from qa.engine import get_joe_articles

            limit = max(1, min(int(limit_param), 200))
            articles = get_joe_articles(limit=limit, search=search_param)
        except Exception:
            logger.exception("/joe-articles : échec")
            articles = []

        body = json.dumps({"articles": articles}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

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
