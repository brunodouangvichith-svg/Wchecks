# Nice2Have — todo

Idées d'amélioration explorées mais non prioritaires. Rien ici n'est planifié
tant que la case n'est pas cochée.

## Notifications / automatisation de workflow

- [ ] ~~Installer le plugin Claude **Zapier**~~ — en pause (skip explicite le
      2026-08-23)
- [ ] ~~Connecter **n8n**~~ — en pause avec Zapier

Repris plus tard, dans cet ordre :
1. Décider quelle direction : Claude pilote n8n (via le serveur MCP
   `n8n-mcp`, nécessite une instance n8n + clé API) vs. un workflow n8n
   existant exposé comme outil MCP (node "MCP Server Trigger", nécessite
   un workflow déjà conçu et une URL webhook publique)
2. Choisir le déclencheur métier réel : ex. `brent_prices` dépasse un seuil,
   ou `energy_conflicts` remonte un nouvel événement dans une zone
   surveillée (Moyen-Orient, Mer Noire, Venezuela, Nigeria, Mer Rouge)
3. Câbler la notification (email, Slack, Sheet) — via Zapier si réactivé,
   sinon directement dans le collector concerné

## RAG sur les données collectées

- [ ] Installer/activer le plugin Claude **Qdrant** (carte d'installation
      déjà affichée, gratuit)
- [ ] Self-héberger Qdrant :
      `docker run -p 6333:6333 -p 6334:6334 -v "$(pwd)/qdrant_storage:/qdrant/storage:z" qdrant/qdrant`
      — ou créer le tier cloud gratuit permanent (0.5 vCPU / 1 GB RAM / 4 GB
      disque) si pas envie de gérer l'hébergement
- [ ] Choisir le modèle d'embedding (dimension du vecteur à fixer dans
      `create_collection` — ex. 1536 pour `text-embedding-3-small`)
- [ ] Écrire le script d'indexation : lire les tables de `db/schema.sql` via
      `neon_client.py`, transformer chaque ligne (ou un résumé) en texte,
      générer l'embedding, l'upsert dans une collection Qdrant
- [ ] Décider du déclenchement de la réindexation : après chaque run de
      collector (`scheduler.py`) ou par un job séparé
- [ ] Écrire la fonction de recherche (question en langage naturel → vecteur
      → top-k résultats Qdrant → injectés dans le prompt Claude)

But : poser des questions en langage naturel sur l'historique collecté (prix,
dette, conflits, minerais...) sans écrire de requête SQL.

## AEO/GEO — visibilité du contenu dans les réponses IA

- [ ] Installer/activer le plugin Claude **SearchFit SEO** (carte
      d'installation déjà affichée, gratuit)
- [ ] Lancer `seo-audit` sur `README.md` et `docs/index.html`
- [ ] Lancer `ai-visibility` pour vérifier comment ces pages sont
      comprises/citées par les IA de recherche (ChatGPT, Perplexity, Gemini)
- [ ] Générer le `schema-markup` adapté si `docs/index.html` est publié
      publiquement

Pertinence limitée pour Wchecks aujourd'hui (pas de site de contenu à
proprement parler) — condition de reprise : publication plus large de
`docs/index.html` ou de la carte générée.

## LLM Ops / Observabilité

- [ ] Installer/activer le plugin Claude **Langfuse** (carte d'installation
      déjà affichée, gratuit)
- [ ] Self-héberger Langfuse ou créer un compte cloud (tier gratuit)
- [ ] Instrumenter les appels LLM ajoutés au projet (tracing + gestion de
      prompts + évaluation) une fois qu'il y en a

Condition de reprise : Wchecks ajoute une couche LLM en production (ex. le
chatbot RAG ci-dessus, ou une génération de résumés). Sans objet tant que le
projet reste un pipeline de collecte de données sans LLM.

## Sans suite

- [x] Agents IA génériques (LangGraph / CrewAI / LangChain / AgentKit) — pas
      de skill Claude Code dédié, et pas de besoin identifié : l'orchestration
      multi-agents est déjà native à Claude Code (`Agent`, `Workflow`, MCP)
- [x] AI Tool Stacking (Notion/ClickUp/Highlevel) — pas de plugin dédié
      packagé ; Airtable a un plugin officiel si le besoin se précise
- [x] Analyse de données social/web (Google Analytics, Search Console,
      Socialblade, Analisa.io...) — pas d'équivalent packagé côté Claude,
      catégorie "lecture de dashboards" plutôt que MCP pilotable
