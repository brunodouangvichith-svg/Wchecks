# Nice2Have — todo

Idées d'amélioration explorées mais non prioritaires. Rien ici n'est planifié
tant que la case n'est pas cochée.

## Notifications / automatisation de workflow

- [ ] ~~Installer le plugin Claude **Zapier**~~ — en pause (skip explicite le
      2026-08-23)
- [ ] ~~Connecter **n8n**~~ — en pause avec Zapier. Pas de plugin marketplace,
      mais open source/gratuit (self-hosted). Deux pistes si on y revient :
      Claude pilote n8n via le serveur MCP `n8n-mcp`, ou un workflow n8n
      existant s'expose comme outil MCP ("MCP Server Trigger").

Cas d'usage visé : déclencher une action externe (email, Slack, Sheet...)
quand un collector détecte un événement notable — ex. `brent_prices` dépasse
un seuil, ou `energy_conflicts` remonte un nouvel événement dans une zone
surveillée.

## RAG sur les données collectées

- [ ] Installer/activer le plugin Claude **Qdrant** (carte d'installation
      déjà affichée, gratuit)
- [ ] Self-héberger Qdrant (`docker run qdrant/qdrant`) ou créer le tier
      cloud gratuit permanent
- [ ] Construire le pipeline d'embedding des lignes de `db/schema.sql` (ou de
      leurs résumés) + réindexation après chaque run de collector

But : poser des questions en langage naturel sur l'historique collecté (prix,
dette, conflits, minerais...) sans écrire de requête SQL.

## AEO/GEO — visibilité du contenu dans les réponses IA

- [ ] Installer/activer le plugin Claude **SearchFit SEO** (carte
      d'installation déjà affichée, gratuit)
- [ ] Auditer `README.md`, `docs/index.html` et la carte générée par
      `viz/build_map.py` avec le skill `ai-visibility` si ces pages sont un
      jour publiées plus largement

Pertinence limitée pour Wchecks aujourd'hui (pas de site de contenu à
proprement parler) — à revisiter seulement si publication plus large.

## LLM Ops / Observabilité

- [ ] Installer/activer le plugin Claude **Langfuse** (carte d'installation
      déjà affichée, gratuit)
- [ ] Self-héberger Langfuse ou créer un compte cloud (tier gratuit)

Sans objet pour Wchecks tant qu'il n'y a pas de couche LLM en production —
utile pour n'importe quel autre projet qui appelle des LLM (tracing, gestion
de prompts, évaluation, coût/latence/erreurs). À réévaluer si Wchecks ajoute
un jour une génération de résumés ou un chatbot RAG.

## Sans suite

- [x] Agents IA génériques (LangGraph / CrewAI / LangChain / AgentKit) — pas
      de skill Claude Code dédié, et pas de besoin identifié : l'orchestration
      multi-agents est déjà native à Claude Code (`Agent`, `Workflow`, MCP)
- [x] AI Tool Stacking (Notion/ClickUp/Highlevel) — pas de plugin dédié
      packagé ; Airtable a un plugin officiel si le besoin se précise
- [x] Analyse de données social/web (Google Analytics, Search Console,
      Socialblade, Analisa.io...) — pas d'équivalent packagé côté Claude,
      catégorie "lecture de dashboards" plutôt que MCP pilotable
