"""
Client PostgreSQL (Neon) générique : connexion, upsert anti-doublons et lecture.

Tous les collectors passent par ce module pour persister leurs données —
aucun collector n'importe `psycopg` directement.

Contrairement à Firestore, Postgres a de vraies contraintes UNIQUE (voir
db/schema.sql) : l'anti-doublons passe par un INSERT ... ON CONFLICT (...)
DO UPDATE natif, pas par un ID de document dérivé/haché.

CONCURRENCE : le service Render fait tourner le scheduler (jobs dans des threads
APScheduler) ET le serveur HTTP /ask (qa/engine.py) dans le même process. Une
connexion psycopg unique et partagée entre threads n'est PAS sûre — deux threads
qui exécutent des requêtes en même temps sur la même connexion corrompent le
protocole (constaté en pratique : le endpoint /ask échouait par intermittence en
production alors qu'il fonctionnait toujours en local, seul environnement où le
scheduler restait généralement inactif au moment du test). D'où l'usage d'un vrai
pool de connexions (`psycopg_pool.ConnectionPool`) : chaque opération récupère sa
propre connexion via `get_connection()`, utilisée dans un `with get_connection()
as conn:` — jamais de connexion globale partagée sans retour au pool.
"""

import logging

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

import config

logger = logging.getLogger(__name__)

# Colonnes de chaque table (hors id/created_at), dans l'ordre d'insertion.
TABLE_COLUMNS = {
    "spr_stocks": ["date", "valeur_milliers_barils"],
    "brent_prices": ["date", "prix_usd_baril"],
    "oil_production": ["pays_code", "periode", "valeur_barils_jour"],
    "gas_production": ["pays_code", "periode", "valeur_production_gaz"],
    "energy_conflicts": ["event_id", "date", "pays", "lat", "lon", "titre", "ton", "url", "source_verifiee", "resume"],
    "social_tensions": ["event_id", "date", "pays", "lat", "lon", "titre", "ton", "url", "source_verifiee", "resume"],
    "military_activity": ["event_id", "date", "pays", "lat", "lon", "titre", "ton", "url", "source_verifiee", "resume"],
    "country_debt": ["pays_code", "annee", "dette_pct_pib", "dette_montant_milliards_usd"],
    "country_economy": ["pays_code", "annee", "impots_pct_pib", "chomage_pct", "inflation_pct"],
    "defense_budget": ["pays_code", "annee", "budget_pct_pib"],
    "arms_transfers": ["pays_code", "annee", "direction", "valeur_tiv"],
    "maritime_traffic": ["mmsi", "timestamp", "lat", "lon", "vitesse", "cap", "zone_strategique"],
    "official_statements": ["url", "date", "institution", "titre", "extrait", "langue", "source_verifiee", "resume"],
    "country_industry": ["pays_code", "annee", "production_industrielle_pct_pib"],
    "minerals_production": ["pays_code", "annee", "matiere_premiere", "volume_tonnes", "rang_mondial"],
    "risk_scores": ["pays_code", "date_calcul", "score_global", "details_json"],
    "credit_ratings": ["pays_code", "agence", "note", "perspective", "date_notation"],
    "joe_analysis": ["source_table", "url", "categorie", "gravite", "acteurs", "resume_ia", "modele"],
    "country_sources": ["pays_code", "nom_source", "type_source", "url", "feed_url"],
    "country_news": ["pays_code", "source_nom", "url", "date", "titre", "resume", "source_verifiee"],
    "national_newspapers": ["name", "country", "region", "language", "website_url", "political_leaning"],
}

# Colonnes formant la contrainte UNIQUE de chaque table (voir db/schema.sql).
TABLE_CONFLICT_KEYS = {
    "spr_stocks": ["date"],
    "brent_prices": ["date"],
    "oil_production": ["pays_code", "periode"],
    "gas_production": ["pays_code", "periode"],
    "energy_conflicts": ["event_id"],
    "social_tensions": ["event_id"],
    "military_activity": ["event_id"],
    "country_debt": ["pays_code", "annee"],
    "country_economy": ["pays_code", "annee"],
    "defense_budget": ["pays_code", "annee"],
    "arms_transfers": ["pays_code", "annee", "direction"],
    "maritime_traffic": ["mmsi", "timestamp"],
    "official_statements": ["url"],
    "country_industry": ["pays_code", "annee"],
    "minerals_production": ["pays_code", "annee", "matiere_premiere"],
    "risk_scores": ["pays_code", "date_calcul"],
    "credit_ratings": ["pays_code", "agence"],
    "joe_analysis": ["source_table", "url"],
    "country_sources": ["pays_code", "nom_source"],
    "country_news": ["url"],
    "national_newspapers": ["name", "country"],
}

# Champ utilisé pour trier "le plus récent d'abord" dans get_latest()/get_history().
ORDER_FIELD = {
    "spr_stocks": "date",
    "brent_prices": "date",
    "oil_production": "periode",
    "gas_production": "periode",
    "energy_conflicts": "date",
    "social_tensions": "date",
    "military_activity": "date",
    "country_debt": "annee",
    "country_economy": "annee",
    "defense_budget": "annee",
    "arms_transfers": "annee",
    "maritime_traffic": "timestamp",
    "official_statements": "date",
    "country_industry": "annee",
    "minerals_production": "annee",
    "risk_scores": "date_calcul",
    "credit_ratings": "date_notation",
    "joe_analysis": "created_at",
    "country_sources": "created_at",
    "country_news": "date",
    "national_newspapers": "created_at",
}

_pool: ConnectionPool | None = None


def _get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        if not config.DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL manquant : renseignez le fichier .env (voir .env.example). "
                "Projet gratuit : https://neon.tech"
            )
        _pool = ConnectionPool(config.DATABASE_URL, min_size=1, max_size=10, open=True)
    return _pool


def get_connection():
    """
    Context manager retournant une connexion issue du pool (thread-safe) : à
    utiliser dans un `with get_connection() as conn:` par tout module ayant
    besoin d'un accès direct au curseur (scoring/risk_score.py, viz/build_map.py,
    qa/engine.py). Ne jamais garder une connexion en dehors de ce `with`.
    """
    return _get_pool().connection()


def upsert_generic(table_name: str, rows: list[dict]) -> int:
    """
    Insère ou met à jour une liste de lignes dans `table_name` via
    INSERT ... ON CONFLICT (...) DO UPDATE, en s'appuyant sur la contrainte UNIQUE
    déclarée dans TABLE_CONFLICT_KEYS.

    Retourne le nombre de lignes envoyées (0 si `rows` est vide, aucune requête
    n'est faite dans ce cas).
    """
    if not rows:
        return 0

    columns = TABLE_COLUMNS.get(table_name)
    conflict_cols = TABLE_CONFLICT_KEYS.get(table_name)
    if columns is None or conflict_cols is None:
        raise ValueError(
            f"Table '{table_name}' inconnue (ajoutez-la dans TABLE_COLUMNS/TABLE_CONFLICT_KEYS "
            "après avoir créé la table et sa contrainte UNIQUE dans db/schema.sql)."
        )

    update_cols = [c for c in columns if c not in conflict_cols]
    col_list = ", ".join(columns)
    placeholders = ", ".join(f"%({c})s" for c in columns)
    conflict_list = ", ".join(conflict_cols)

    if update_cols:
        update_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
        sql = (
            f"INSERT INTO {table_name} ({col_list}) VALUES ({placeholders}) "
            f"ON CONFLICT ({conflict_list}) DO UPDATE SET {update_clause}"
        )
    else:
        sql = (
            f"INSERT INTO {table_name} ({col_list}) VALUES ({placeholders}) "
            f"ON CONFLICT ({conflict_list}) DO NOTHING"
        )

    params_seq = [{c: row.get(c) for c in columns} for row in rows]

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, params_seq)
        conn.commit()

    logger.info("upsert_generic: %d ligne(s) envoyée(s) vers '%s'", len(rows), table_name)
    return len(rows)


def get_latest(table_name: str) -> dict | None:
    """Retourne la ligne la plus récente de `table_name` (par son champ de date/période), ou None."""
    order_col = ORDER_FIELD[table_name]
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(f"SELECT * FROM {table_name} ORDER BY {order_col} DESC NULLS LAST LIMIT 1")
            return cur.fetchone()


def get_history(table_name: str, n: int) -> list[dict]:
    """Retourne les N lignes les plus récentes de `table_name`, plus récentes en premier."""
    order_col = ORDER_FIELD[table_name]
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(f"SELECT * FROM {table_name} ORDER BY {order_col} DESC NULLS LAST LIMIT %s", (n,))
            return cur.fetchall()
