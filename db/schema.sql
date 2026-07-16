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
    source_verifiee BOOLEAN,
    resume TEXT,
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
    source_verifiee BOOLEAN,
    resume TEXT,
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
    source_verifiee BOOLEAN,
    resume TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (event_id)
);

-- 5. Dette publique des pays (% du PIB, et montant dérivé) (IMF WEO GGXWDG_NGDP + NGDPD)
CREATE TABLE IF NOT EXISTS country_debt (
    id BIGSERIAL PRIMARY KEY,
    pays_code TEXT NOT NULL,
    annee INTEGER NOT NULL,
    dette_pct_pib NUMERIC,
    dette_montant_milliards_usd NUMERIC,
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
    source_verifiee BOOLEAN,
    resume TEXT,
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

-- Notations de crédit souveraines (S&P, Fitch, Moody's) — scrapées depuis Wikipédia
-- (Liste of countries by credit rating), pas d'API gratuite fiable disponible.
-- Une ligne par (pays, agence) : reflète la notation ACTUELLE, pas un historique —
-- réécrite à chaque collecte si elle a changé.
CREATE TABLE IF NOT EXISTS credit_ratings (
    id BIGSERIAL PRIMARY KEY,
    pays_code TEXT NOT NULL,
    agence TEXT NOT NULL,
    note TEXT,
    perspective TEXT,
    date_notation DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (pays_code, agence)
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

-- Analyse "Joe" (LLM Gemini) des articles sources — dimension complémentaire
-- au classement par mots-clés (energy_conflicts/social_tensions/military_activity/
-- official_statements), pas un remplacement. Voir clients/joe_agent.py.
-- Volontairement borné à un sous-ensemble d'articles par cycle (coût API),
-- donc PAS toutes les lignes des tables sources ont une analyse Joe.
CREATE TABLE IF NOT EXISTS joe_analysis (
    id BIGSERIAL PRIMARY KEY,
    source_table TEXT NOT NULL,
    url TEXT NOT NULL,
    categorie TEXT,
    gravite TEXT,
    acteurs TEXT,
    resume_ia TEXT,
    modele TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_table, url)
);

-- Annuaire des journaux nationaux et sites officiels par pays, découvert par
-- l'agent Joe (LLM Gemini, connaissances du modèle — PAS une recherche web
-- réelle, voir clients/joe_agent.discover_country_sources). feed_url est le
-- flux RSS découvert pour cette source (clients/rss_client.discover_feed_url),
-- NULL si aucun flux exploitable n'a été trouvé (fréquent pour les sites
-- officiels/gouvernementaux) — ces sources restent dans l'annuaire mais ne
-- sont pas lues automatiquement (voir country_news).
CREATE TABLE IF NOT EXISTS country_sources (
    id BIGSERIAL PRIMARY KEY,
    pays_code TEXT NOT NULL,
    nom_source TEXT NOT NULL,
    type_source TEXT,
    url TEXT NOT NULL,
    feed_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (pays_code, nom_source)
);

-- Articles lus depuis les flux RSS découverts dans country_sources — même
-- structure/traitement que official_statements (scraping + résumé extractif
-- via clients/article_scraper.py), mais par pays plutôt que par institution.
CREATE TABLE IF NOT EXISTS country_news (
    id BIGSERIAL PRIMARY KEY,
    pays_code TEXT NOT NULL,
    source_nom TEXT,
    url TEXT NOT NULL,
    date TIMESTAMPTZ,
    titre TEXT,
    resume TEXT,
    source_verifiee BOOLEAN,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (url)
);

-- Annuaire de référence des grands journaux nationaux dans le monde (nom,
-- pays, région, langue, site officiel, ligne éditoriale) — peuplé une fois via
-- scripts/populate_national_newspapers.py, pas un collector planifié (données
-- statiques, pas d'actualité à rafraîchir). Distinct de country_sources : celui-ci
-- est un annuaire de référence généraliste (couverture mondiale), country_sources
-- est spécifique au pipeline de lecture RSS de l'agent Joe (limité à
-- config.MONITORED_COUNTRIES).
CREATE TABLE IF NOT EXISTS national_newspapers (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    country TEXT NOT NULL,
    region TEXT NOT NULL,
    language TEXT NOT NULL,
    website_url TEXT NOT NULL,
    political_leaning TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (name, country)
);

-- Résumé + thème du jour de la page d'accueil de chaque journal de
-- national_newspapers, produit par l'agent Joe (scraping + analyse groupée,
-- voir clients/joe_agent.analyze_homepages_batch et
-- collectors/collect_national_newspapers_contents.py). Une ligne par journal
-- (UNIQUE website_url) : ÉCRASÉE chaque jour par la collecte planifiée, ce
-- n'est pas un historique — reflète l'état du jour, comme credit_ratings.
CREATE TABLE IF NOT EXISTS national_newspapers_contents (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    country TEXT NOT NULL,
    region TEXT NOT NULL,
    language TEXT NOT NULL,
    website_url TEXT NOT NULL,
    content TEXT,
    theme TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (website_url)
);

-- Annuaire de référence des grandes organisations internationales et
-- institutions financières mondiales (FMI, Banque mondiale, ONU, OMC...) —
-- peuplé une fois via scripts/populate_international_organizations.py, même
-- philosophie que national_newspapers (données statiques, pas de collector
-- planifié). `category` distingue les 4 grandes familles décrites (IFI,
-- banque de développement régionale, organisation politique/judiciaire,
-- institution régionale européenne) ; `key_resources` résume les données/
-- rapports publics notables disponibles sur le site (WEO, WDI, Eurostat...).
CREATE TABLE IF NOT EXISTS international_organizations (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    role TEXT,
    key_resources TEXT,
    website_url TEXT NOT NULL,
    region TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (name)
);
