"""
Sous-agent générique partagé par les 3 collecteurs "contenu de page d'accueil"
(national_newspapers_contents, international_organizations_contents,
agences_presses_contents) — Joe agit comme "chef d'orchestre" : chaque
sous-agent lui délègue en autonomie (aucune supervision humaine) la décision
du volume à traiter à chaque exécution (voir clients.joe_agent.
orchestrate_subagent_batch), et garantit l'intégrité des résumés produits
(voir clients.joe_agent.analyze_homepages_batch — un résumé jugé non fondé
sur le texte réel par l'auto-contrôle de Joe est rejeté, jamais stocké).

Les 3 collecteurs restent des scripts indépendants avec leur propre
planification (voir scheduler.py, config.FREQUENCIES_MINUTES) — ce module
factorise uniquement la logique commune (lire l'annuaire, prioriser les
éléments jamais traités ou les plus anciens, scraper, faire arbitrer le
volume par Joe, analyser par lots, enregistrer), pas le planning.
"""

import logging

from clients.article_scraper import verify_and_extract
from clients.joe_agent import analyze_homepages_batch, orchestrate_subagent_batch
from clients.neon_client import get_connection, upsert_generic

logger = logging.getLogger(__name__)

# Plafond dur par exécution, indépendant de la décision de Joe — protection
# de dernier recours pour ne jamais soumettre un lot déraisonnable au tier
# gratuit de Gemini (voir clients.joe_agent, plafonné à 15 req/min et 500/jour).
HARD_CAP_PER_RUN = 40


def run_subagent(name: str, directory_table: str, contents_table: str, directory_columns: list[str]) -> int:
    """
    Exécute un cycle complet du sous-agent `name` :
    1. lit `directory_columns` (dont le dernier doit être `website_url`) depuis
       `directory_table` ;
    2. priorise les entrées de `contents_table` jamais traitées, puis les plus
       anciennes (LEFT JOIN sur website_url, ORDER BY created_at le plus
       ancien/absent en premier) ;
    3. demande à Joe (orchestrate_subagent_batch) combien traiter cette fois ;
    4. scrape (clients.article_scraper) puis analyse par lots
       (clients.joe_agent.analyze_homepages_batch, intègre le contrôle
       d'intégrité "fiable") ;
    5. enregistre le résultat dans `contents_table` (upsert sur website_url).

    Retourne le nombre de lignes effectivement enregistrées.
    """
    # Les 3 tables d'annuaire (national_newspapers, international_organizations,
    # agences_presses) utilisent toutes littéralement "website_url" comme nom
    # de colonne — pas de correspondance à établir, `directory_columns` la
    # contient déjà telle quelle.
    select_cols = ", ".join(f"d.{col}" for col in directory_columns)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT {select_cols}
                FROM {directory_table} d
                LEFT JOIN {contents_table} c ON c.website_url = d.website_url
                ORDER BY c.created_at ASC NULLS FIRST
                """
            )
            entries = cur.fetchall()
            cur.execute(f"SELECT COUNT(*) FROM {directory_table}")
            total = cur.fetchone()[0]

    pending = len(entries)
    batch_size = orchestrate_subagent_batch(name, pending=pending, total=total, hard_cap=HARD_CAP_PER_RUN)
    logger.info(
        "%s : %d élément(s) en attente sur %d au total, Joe alloue %d pour cette exécution",
        name, pending, total, batch_size,
    )
    entries = entries[:batch_size]

    texts = []
    for entry in entries:
        url = entry[-1]
        verified, text = verify_and_extract(url)
        texts.append(text if verified else None)

    analyses = analyze_homepages_batch(texts)

    rows = []
    for entry, analysis in zip(entries, analyses):
        if not analysis:
            continue
        row = dict(zip(directory_columns, entry))
        row["content"] = analysis["content"]
        row["theme"] = analysis["theme"]
        rows.append(row)

    logger.info("%s : %d/%d élément(s) analysé(s) avec succès (intégrité vérifiée)", name, len(rows), len(entries))
    return upsert_generic(contents_table, rows)
