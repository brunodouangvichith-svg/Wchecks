-- Schéma PostgreSQL (Neon) de l'agent de veille énergétique et géopolitique.
-- Source de vérité du schéma : à exécuter dans l'éditeur SQL du dashboard Neon
-- (ou via psql/n'importe quel client Postgres connecté à DATABASE_URL).
-- Chaque table porte une contrainte UNIQUE dédiée, utilisée par upsert_generic()
-- (INSERT ... ON CONFLICT (...) DO UPDATE) pour l'anti-doublons.

-- 1. Réserve stratégique de pétrole US (EIA, série WCSSTUS1)
CREATE TABLE IF NOT EXISTS spr_stocks (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    valeur_milliers_barils NUMERIC NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (date)
);

-- 2. Prix du Brent spot (EIA, série RBRTE)
CREATE TABLE IF NOT EXISTS brent_prices (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    prix_usd_baril NUMERIC NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (date)
);

-- 3a. Production mondiale de pétrole par pays/région (EIA international)
CREATE TABLE IF NOT EXISTS oil_production (
    id BIGSERIAL PRIMARY KEY,
    pays_code TEXT NOT NULL,
    periode TEXT NOT NULL,
    valeur_barils_jour NUMERIC,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (pays_code, periode)
);

-- 3b. Production mondiale de gaz naturel par pays/région (EIA international)
CREATE TABLE IF NOT EXISTS gas_production (
    id BIGSERIAL PRIMARY KEY,
    pays_code TEXT NOT NULL,
    periode TEXT NOT NULL,
    valeur_production_gaz NUMERIC,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (pays_code, periode)
);

-- 4. Conflits géolocalisés liés à l'énergie (GDELT)
CREATE TABLE IF NOT EXISTS energy_conflicts (
    id BIGSERIAL PRIMARY KEY,
    event_id TEXT NOT NULL,
    date TIMESTAMPTZ,
    pays TEXT,
    lat DOUBLE PRECISION,
    lon DOUBLE PRECISION,
    titre TEXT,
    ton NUMERIC,
    url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (event_id)
);

-- Tensions sociales / manifestations (GDELT)
CREATE TABLE IF NOT EXISTS social_tensions (
    id BIGSERIAL PRIMARY KEY,
    event_id TEXT NOT NULL,
    date TIMESTAMPTZ,
    pays TEXT,
    lat DOUBLE PRECISION,
    lon DOUBLE PRECISION,
    titre TEXT,
    ton NUMERIC,
    url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (event_id)
);

-- Activité militaire (proxy GDELT)
CREATE TABLE IF NOT EXISTS military_activity (
    id BIGSERIAL PRIMARY KEY,
    event_id TEXT NOT NULL,
    date TIMESTAMPTZ,
    pays TEXT,
    lat DOUBLE PRECISION,
    lon DOUBLE PRECISION,
    titre TEXT,
    ton NUMERIC,
    url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (event_id)
);

-- 5. Dette publique des pays (% du PIB) (World Bank GC.DOD.TOTL.GD.ZS)
CREATE TABLE IF NOT EXISTS country_debt (
    id BIGSERIAL PRIMARY KEY,
    pays_code TEXT NOT NULL,
    annee INTEGER NOT NULL,
    dette_pct_pib NUMERIC,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (pays_code, annee)
);

-- 6. Situation économique (World Bank : impôts, chômage, inflation)
CREATE TABLE IF NOT EXISTS country_economy (
    id BIGSERIAL PRIMARY KEY,
    pays_code TEXT NOT NULL,
    annee INTEGER NOT NULL,
    impots_pct_pib NUMERIC,
    chomage_pct NUMERIC,
    inflation_pct NUMERIC,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (pays_code, annee)
);

-- 7. Budget défense (% PIB) (World Bank MS.MIL.XPND.GD.ZS)
CREATE TABLE IF NOT EXISTS defense_budget (
    id BIGSERIAL PRIMARY KEY,
    pays_code TEXT NOT NULL,
    annee INTEGER NOT NULL,
    budget_pct_pib NUMERIC,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (pays_code, annee)
);

-- Transferts d'armes (SIPRI "Top List" exports — agrégé par pays/année/direction,
-- pas de détail bilatéral ni par type d'arme : voir clients/sipri_client.py)
CREATE TABLE IF NOT EXISTS arms_transfers (
    id BIGSERIAL PRIMARY KEY,
    pays_code TEXT NOT NULL,
    annee INTEGER NOT NULL,
    direction TEXT NOT NULL,  -- "export" ou "import"
    valeur_tiv NUMERIC,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (pays_code, annee, direction)
);

-- 8. Trafic maritime mondial (AISstream, snapshot tankers)
CREATE TABLE IF NOT EXISTS maritime_traffic (
    id BIGSERIAL PRIMARY KEY,
    mmsi TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    lat DOUBLE PRECISION,
    lon DOUBLE PRECISION,
    vitesse NUMERIC,
    cap NUMERIC,
    zone_strategique TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (mmsi, timestamp)
);

-- 9. Déclarations officielles des chancelleries/institutions (RSS)
CREATE TABLE IF NOT EXISTS official_statements (
    id BIGSERIAL PRIMARY KEY,
    url TEXT NOT NULL,
    date TIMESTAMPTZ,
    institution TEXT,
    titre TEXT,
    extrait TEXT,
    langue TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (url)
);

-- 10. Production industrielle par pays (World Bank NV.IND.TOTL.ZS)
CREATE TABLE IF NOT EXISTS country_industry (
    id BIGSERIAL PRIMARY KEY,
    pays_code TEXT NOT NULL,
    annee INTEGER NOT NULL,
    production_industrielle_pct_pib NUMERIC,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (pays_code, annee)
);

-- 11. Production de minerais et métaux stratégiques (USGS, fichiers statiques)
-- rang_mondial non renseigné (fichiers régionaux, pas de vrai classement mondial
-- disponible sans fabriquer une fausse précision — voir collectors/collect_minerals.py)
CREATE TABLE IF NOT EXISTS minerals_production (
    id BIGSERIAL PRIMARY KEY,
    pays_code TEXT NOT NULL,
    annee INTEGER NOT NULL,
    matiere_premiere TEXT NOT NULL,
    volume_tonnes NUMERIC,
    rang_mondial INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (pays_code, annee, matiere_premiere)
);

-- Score de risque global, calculé par croisement des dimensions ci-dessus
CREATE TABLE IF NOT EXISTS risk_scores (
    id BIGSERIAL PRIMARY KEY,
    pays_code TEXT NOT NULL,
    date_calcul TIMESTAMPTZ NOT NULL,
    score_global NUMERIC NOT NULL,
    details_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (pays_code, date_calcul)
);
