"""
Configuration de logging centralisée, utilisée par TOUS les points d'entrée du
projet (scheduler.py, cli.py, chaque collector lancé en `__main__`,
scripts/*) — remplace les `logging.basicConfig(level=logging.INFO)` dispersés
et incohérents entre modules (console uniquement, rien de persistant) qui
existaient avant.

Deux fichiers, dans logs/ :
- scheduler.log : tout (INFO et plus), le journal complet d'activité.
- errors.log : UNIQUEMENT WARNING et plus — un fichier dédié pour pouvoir
  tracer/grep tous les échecs (collectors, agent Joe, endpoints HTTP du
  scheduler, calcul du score de risque...) sans les noyer dans le bruit des
  logs INFO de routine du fichier complet.

`configure_logging()` est idempotent (un seul jeu de handlers même si appelé
plusieurs fois, ex. import d'un module qui l'appelle alors qu'un autre l'a
déjà fait dans le même process) via le flag module-level `_configured`.
"""

import logging

import config

_configured = False
_subagent_loggers: dict[str, logging.Logger] = {}


def get_subagent_logger(name: str) -> logging.Logger:
    """
    Logger dédié à un sous-agent de Joe (national_newspapers_contents,
    international_organizations_contents, agences_presses_contents,
    report_hotspots, report_financial — voir collectors/_joe_subagent.py et
    collectors/collect_report_*.py) : en plus des fichiers communs
    (scheduler.log / errors.log, voir configure_logging ci-dessous), chaque
    sous-agent écrit AUSSI dans son propre logs/subagents/<name>.log.

    Avant ce module, les 3 sous-agents "page d'accueil" partageaient tous le
    même logger générique de collectors/_joe_subagent.py (`__name__` de ce
    module, identique pour les 3) — impossible de distinguer dans
    scheduler.log lequel des trois avait produit une ligne donnée.

    Le handler dédié s'ajoute à un logger propre (propagate reste activé par
    défaut) : les messages continuent aussi de remonter vers
    scheduler.log/errors.log, ce fichier par sous-agent est un complément, pas
    un remplacement du journal complet.

    Idempotent : un seul FileHandler créé par nom, même si appelé plusieurs
    fois dans le même process (ex. plusieurs runs successifs).
    """
    if name in _subagent_loggers:
        return _subagent_loggers[name]

    subagent_dir = config.LOG_DIR / "subagents"
    subagent_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    handler = logging.FileHandler(subagent_dir / f"{name}.log", encoding="utf-8")
    handler.setFormatter(formatter)

    logger = logging.getLogger(f"subagent.{name}")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    _subagent_loggers[name] = logger
    return logger


def configure_logging(level: int = logging.INFO) -> None:
    global _configured
    if _configured:
        return
    _configured = True

    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    full_handler = logging.FileHandler(config.LOG_DIR / "scheduler.log", encoding="utf-8")
    full_handler.setFormatter(formatter)

    error_handler = logging.FileHandler(config.LOG_DIR / "errors.log", encoding="utf-8")
    error_handler.setLevel(logging.WARNING)
    error_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(console_handler)
    root.addHandler(full_handler)
    root.addHandler(error_handler)
