"""
Peuple `skills` avec des connaissances de référence utiles à l'agent
conversationnel (voir qa/engine.py, _handle_add_skill/_search_skills) —
fournies au déploiement plutôt que d'attendre qu'un utilisateur les tape une
par une via le chat ("ajoute à tes skills cette information : ...").

Script ponctuel, PAS un collector planifié — même principe que
national_newspapers/agences_presses : connaissances statiques, changent très
rarement. À relancer manuellement (`python -m scripts.populate_skills`) si la
liste doit être étendue ou corrigée — upsert_generic() dédoublonne par
content_hash (clé UNIQUE, sha256 du contenu) plutôt que de dupliquer.
"""

import hashlib
import logging

from clients.neon_client import upsert_generic

logger = logging.getLogger(__name__)

SKILLS = [
    "Pour une analyse macro-économique, sources de référence : BCE (Banque centrale "
    "européenne, politique monétaire et statistiques de la zone euro), INSEE (Institut "
    "national de la statistique et des études économiques, statistiques macroéconomiques "
    "et sectorielles françaises), Eurostat (office statistique de l'Union européenne, "
    "statistiques macroéconomiques harmonisées à l'échelle européenne).",
]


def run() -> int:
    rows = [
        {"content": content, "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest()}
        for content in SKILLS
    ]
    return upsert_generic("skills", rows)


if __name__ == "__main__":
    from logging_config import configure_logging

    configure_logging()
    n = run()
    print(f"{n} skill(s) envoyée(s) vers skills")
