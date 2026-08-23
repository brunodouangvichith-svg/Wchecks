# Nice2Have

Idées d'amélioration explorées mais non prioritaires — pas de dette technique,
juste des pistes pour plus tard. Rien ici n'est planifié ni implémenté.

## Notifications / automatisation de workflow

**Zapier** — plugin Claude officiel (gratuit à installer, MCP + skills
`zapier-onboard`/`zapier-explore`/`zapier-status`/`zapier-demo`). Permettrait
de déclencher une action externe (email, Slack, Sheet...) quand un collector
détecte un événement notable, par exemple : `brent_prices` dépasse un seuil,
ou `energy_conflicts` remonte un nouvel événement dans une zone surveillée.

**n8n** — pas de plugin marketplace, mais open source et gratuit
(self-hosted). Deux directions possibles si on y revient :
- Claude pilote n8n via le serveur MCP `n8n-mcp` (créer/déclencher des
  workflows depuis une conversation).
- Un workflow n8n existant s'expose comme outil MCP (node "MCP Server
  Trigger") que Claude peut appeler.

Statut : évalué, mis en pause (skip explicite le 2026-08-23).

## RAG sur les données collectées (Qdrant)

Permettrait de poser des questions en langage naturel sur l'historique
collecté (prix, dette, conflits, minerais...) sans écrire de requête SQL —
Claude récupérant les lignes pertinentes de Neon via recherche vectorielle
avant de répondre.

- Plugin Claude **Qdrant** proposé (gratuit à installer, skills sur hybrid
  search, qualité de recherche, SDK clients, options de déploiement).
- Qdrant lui-même : open source (Apache-2.0), self-hosted gratuit
  (`docker run qdrant/qdrant`) ou tier cloud gratuit permanent
  (0.5 vCPU / 1 GB RAM / 4 GB disque) — pas de coût obligatoire pour tester.
- Prérequis pour une vraie intégration RAG : pipeline d'embedding des lignes
  de `db/schema.sql` (ou de leurs résumés) + réindexation après chaque run
  de collector.

Statut : évalué, pas encore installé côté utilisateur.

## Agents IA génériques (LangGraph / CrewAI / LangChain / AgentKit)

Pas de skill Claude Code dédié trouvé pour ces frameworks — l'orchestration
multi-agents est déjà native à Claude Code (outils `Agent`, `Workflow`,
MCP), donc pas de besoin identifié de les ajouter à ce projet pour l'instant.
