# GlobalChecks — Agent de veille énergétique et géopolitique mondiale

Agent Python qui collecte 11 dimensions de risque énergétique et géopolitique via
des sources 100% gratuites, les stocke dans une base PostgreSQL (Neon), les met à
jour automatiquement en tâche de fond (Render, Web Service + ping externe — voir
plus bas), calcule un score de risque synthétique par pays, et les visualise sur
une carte mondiale interactive.

## ⚠️ Avertissement

Ce projet est un **outil de veille informative**, pas un outil de décision.

- Ce n'est **pas** un conseil en investissement, ni un signal d'achat/vente.
- Ce n'est **pas** une prédiction de prix de l'énergie ou des matières premières.
- Ce n'est **pas** un outil d'analyse militaire opérationnelle.
- Le score de risque (voir plus bas) est une pondération simple et transparente de
  quelques indicateurs disponibles gratuitement — pas un modèle prédictif validé.

Toutes les données et scores produits doivent être recoupés avec des sources
officielles avant toute décision.

## Architecture

```
GlobalChecks/
├── config.py                # fréquences, mots-clés, zones, pays surveillés, indicateurs
├── cli.py                   # consultation (--latest/--history) et déclenchement manuel
├── scheduler.py              # APScheduler + serveur HTTP minimal — point d'entrée Render
├── clients/                  # accès brut à chaque source externe
│   ├── neon_client.py         # connexion Postgres, upsert générique, lecture
│   ├── eia_client.py          # SPR, Brent, production pétrole/gaz internationale
│   ├── gdelt_client.py        # conflits/tensions/activité militaire (GDELT DOC 2.0)
│   ├── worldbank_client.py    # dette, économie, défense, industrie
│   ├── aisstream_client.py    # trafic maritime (WebSocket, snapshot)
│   ├── rss_client.py          # flux RSS officiels
│   ├── sipri_client.py        # parsing SIPRI (arms transfers)
│   └── usgs_client.py         # parsing USGS (minerais stratégiques)
├── collectors/                # logique métier : client -> transformation -> upsert
├── scoring/risk_score.py       # score de risque global par pays
├── mapping/
│   ├── country_mapping.py     # correspondance noms de pays -> ISO3 -> centroïde
│   └── zones.py                # (réservé) zones stratégiques
├── viz/
│   ├── build_map.py           # génère carte_mondiale.html (Folium)
│   └── data/world_countries.geojson
├── data/{sipri,usgs}/         # fichiers statiques téléchargés manuellement
├── db/schema.sql              # schéma PostgreSQL (source de vérité)
└── render.yaml                 # déploiement Render (Web Service)
```

## Installation locale

```bash
python -m venv .venv
.venv/Scripts/activate   # ou source .venv/bin/activate sous Linux/Mac
pip install -r requirements.txt
cp .env.example .env      # puis renseigner les variables (voir ci-dessous)
```

### Variables d'environnement (`.env`)

| Variable | Description |
|---|---|
| `DATABASE_URL` | Chaîne de connexion PostgreSQL Neon (voir ci-dessous) |
| `EIA_API_KEY` | Clé gratuite : https://www.eia.gov/opendata/register.php |
| `AISSTREAM_API_KEY` | Clé gratuite : https://aisstream.io |

**Ne jamais committer `.env`** (déjà exclu par `.gitignore`).

### Base de données : Neon (PostgreSQL serverless)

1. Créer un projet gratuit sur https://neon.tech
2. Copier la chaîne de connexion **avec pooler** (dashboard > Connection Details >
   case "Pooled connection", hôte contenant `-pooler`) dans `DATABASE_URL`. ⚠️
   **Obligatoire, pas juste recommandé** : `clients/neon_client.py` ouvre un pool
   de connexions concurrentes (jusqu'à 10) — utiliser l'endpoint direct (sans
   `-pooler`) épuise rapidement la limite de connexions de Neon et provoque des
   `PoolTimeout` en production (constaté en pratique lors du déploiement Render).
3. Exécuter `db/schema.sql` dans l'éditeur SQL du dashboard (ou via `psql`/tout
   client Postgres connecté à `DATABASE_URL`) — crée les 16 tables et leurs
   contraintes UNIQUE (anti-doublons via `INSERT ... ON CONFLICT ... DO UPDATE`)

**Pourquoi Neon plutôt que Firestore/Supabase** : le projet a testé les deux autres
options en cours de route. Firestore (plan Spark) limite à ~20 000 écritures/jour,
un plafond atteint dès le premier backfill historique complet (plusieurs dizaines de
milliers de lignes en un seul run). Neon (comme Supabase) limite par taille de
stockage/bande passante, pas par nombre d'écritures — mieux adapté à ce cas d'usage.

## Utilisation

```bash
# Déclencher un collector manuellement
python -m collectors.collect_debt
python -m collectors.collect_spr
python cli.py --minerals-refresh          # collecte USGS (annuelle, à la demande)

# Consulter les données collectées
python cli.py --latest brent_prices
python cli.py --history 10 energy_conflicts

# Lancer le scheduler en local (tourne en continu, Ctrl+C pour arrêter)
python scheduler.py

# Générer la carte interactive
python -m viz.build_map     # produit carte_mondiale.html
```

## Déploiement Render (scheduler en arrière-plan)

⚠️ **Le tier gratuit de Render ne propose pas de Background Worker** ("service type
is not available for this plan" — constaté en pratique, l'hypothèse initiale du
projet était fausse sur ce point). `scheduler.py` est donc déployé comme **Web
Service** : APScheduler tourne en arrière-plan (`BackgroundScheduler`) pendant
qu'un serveur HTTP minimal répond sur le port fourni par Render, pour satisfaire
le contrat "Web Service".

1. Connecter le dépôt GitHub à Render (https://render.com)
2. **New +** → **Blueprint** → Render détecte `render.yaml` → propose un **Web
   Service** nommé `globalchecks-scheduler`
3. Renseigner les variables d'environnement dans le dashboard Render (Settings >
   Environment) : `DATABASE_URL`, `EIA_API_KEY`, `AISSTREAM_API_KEY`
4. Chaque push sur la branche déployée redéclenche automatiquement le build

**Garder le service éveillé** : Render endort un Web Service gratuit après ~15 min
sans requête HTTP entrante — ce qui arrêterait aussi le scheduler. Configurer un
ping externe gratuit (par ex. https://cron-job.org ou UptimeRobot) pour appeler
l'URL du service (`https://<nom-du-service>.onrender.com/`) toutes les 10-14
minutes.

Le scheduler est résilient à un redémarrage (aucun état critique en mémoire — tout
ce qui doit persister va dans Neon). Pas de garantie 24/7 parfaite (redémarrages
du tier gratuit, éventuel délai de réveil si le ping externe manque un cycle),
mais suffisant pour un outil de veille, pas un système critique temps réel.

Le CLI reste utilisable en local, connecté à la même base Neon que le scheduler
déployé — les données collectées en arrière-plan sont immédiatement consultables
sans redéploiement.

## Les 11 dimensions suivies

| # | Dimension | Source | Fréquence |
|---|---|---|---|
| 1 | Réserve stratégique de pétrole US (SPR) | EIA | hebdomadaire |
| 2 | Prix du Brent crude (spot) | EIA | quotidien |
| 3 | Production mondiale pétrole/gaz par pays | EIA (international) | mensuel |
| 4 | Conflits énergétiques géolocalisés | GDELT | toutes les 6h |
| 5 | Dette publique par pays | IMF DataMapper (WEO) | mensuel |
| 6 | Économie (impôts, chômage, inflation) + tensions sociales | World Bank + GDELT | mensuel / 6h |
| 7 | Budget défense + activité militaire (proxy) + transferts d'armes | World Bank + GDELT + SIPRI | mensuel / 6h / manuel |
| 8 | Trafic maritime (tankers, zones stratégiques) | AISstream.io | 4x/jour |
| 9 | Déclarations officielles (chancelleries/institutions) | RSS | ~1h30 |
| 10 | Production industrielle par pays | World Bank | mensuel |
| 11 | Production de minerais stratégiques | USGS | annuel / manuel |

## Limites connues (par source)

- **Dette publique** : l'indicateur World Bank initialement prévu
  (`GC.DOD.TOTL.GD.ZS`, dette du gouvernement central) s'est révélé avoir une
  couverture très incomplète pour les économies avancées — France, Allemagne,
  Japon renvoyaient `None` sur toute la période 2000-2025 (confirmé en
  interrogeant directement l'API World Bank). Remplacé par l'API **IMF
  DataMapper** (indicateur WEO `GGXWDG_NGDP`, dette publique générale, 226
  économies couvertes). Les années au-delà de l'année civile précédente sont
  exclues (ce sont des projections WEO, pas des données réalisées). Sur les 40
  pays surveillés, seuls la Libye et le Yémen restent sans donnée — plausible
  compte tenu des difficultés de collecte statistique dans ces pays.
- **Prix de l'énergie par pays** : dimension explicitement **non intégrée**. Aucune
  API gratuite fiable et à jour ne couvre les prix consommateur par pays (indicateur
  World Bank discontinué ; l'API complète IEA est payante). Construire un proxy
  approximatif donnerait une fausse impression de précision — délibérément omis.
- **GDELT (conflits/tensions/activité militaire)** : la Doc API 2.0 ne fournit ni
  coordonnées précises par article (le lat/lon stocké est le centroïde du PAYS
  source, pas la géolocalisation de l'événement), ni tonalité par article (`ton`
  reste `None`, seul un agrégat par requête existe côté GDELT, pas exploitable par
  événement). Le nombre d'événements recensés reflète la **couverture presse
  anglophone**, pas nécessairement le niveau de risque réel — un biais qui se
  répercute dans le score de risque (voir plus bas).
- **SIPRI (transferts d'armes)** : les exports CSV librement téléchargeables sont
  agrégés par pays et par année (`direction` export/import), sans détail bilatéral
  ni par type d'arme — le registre bilatéral complet de SIPRI n'est pas exportable
  en masse gratuitement.
- **USGS (minerais)** : chaque fichier régional empile plusieurs sections (une table
  "—Continued" plus loin réutilise les mêmes colonnes pour d'autres matières) ; le
  parsing s'arrête à la fin de la première section pour éviter une mauvaise
  attribution — le lithium et l'uranium, présents dans une section ultérieure de
  certains fichiers, ne sont donc pas remontés avec les fichiers actuellement
  déposés. `rang_mondial` n'est pas renseigné : les fichiers sont des synthèses
  régionales, pas mondiales — un classement calculé sur leur seule union serait
  trompeur.
- **AISstream (trafic maritime)** : pas de cargaison précise, "going dark" possible
  en zone de conflit (déjà anticipé). Limite supplémentaire constatée : le type de
  navire ne vient que des messages `ShipStaticData`, beaucoup plus rares que les
  positions — sur une fenêtre de capture de 30-60s, la plupart des navires suivis
  n'ont pas encore émis leur `ShipStaticData` et sont donc exclus. Le nombre de
  tankers retourné est un **sous-ensemble probable**, pas un recensement exhaustif.
- **RSS (déclarations officielles)** : flux individuellement fragiles (le flux du
  Département d'État US renvoie un XML invalide au moment de l'écriture). Chaque
  flux est isolé (un flux cassé n'empêche pas la collecte des autres).
- **Score de risque global** : moyenne non pondérée de quelques dimensions
  normalisées (dette, chômage, inflation, budget défense, + comptages d'événements
  GDELT) — une pondération arbitraire et documentée, pas calibrée empiriquement.
  Hérite du biais de couverture média de GDELT (voir plus haut).

## Attribution des sources

- **EIA** (U.S. Energy Information Administration) — https://www.eia.gov/opendata/
- **GDELT Project** — https://www.gdeltproject.org (DOC API 2.0)
- **World Bank Open Data** — https://data.worldbank.org
- **IMF DataMapper** (World Economic Outlook) — https://www.imf.org/external/datamapper/
- **AISstream.io** — https://aisstream.io
- **SIPRI Arms Transfers Database** — https://www.sipri.org/databases/armstransfers
- **USGS National Minerals Information Center** — https://www.usgs.gov/centers/national-minerals-information-center
- **GeoJSON des frontières mondiales** — dérivé de Natural Earth (domaine public),
  redistribué via https://github.com/johan/world.geo.json

## Schéma de base de données

Voir `db/schema.sql` pour la définition complète (16 tables, contraintes UNIQUE
pour l'anti-doublons via upsert).
