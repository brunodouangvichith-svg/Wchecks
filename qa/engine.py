"""
Moteur de questions/réponses en langage naturel simple, à partir des données
réellement collectées dans Neon.

VOLONTAIREMENT SANS LLM : reconnaissance par mots-clés (pays + dimension), pas
d'appel à un modèle de langage. Reste gratuit, déterministe, et transparent sur
ce qu'il peut couvrir (voir DIMENSION_KEYWORDS) — si le pays ou la dimension ne
sont pas reconnus, le moteur le dit explicitement plutôt que d'inventer une
réponse plausible.
"""

import logging
from urllib.parse import urlparse

from clients.neon_client import get_connection
from mapping.country_mapping import COUNTRY_NAME_TO_ISO3, country_from_domain

logger = logging.getLogger(__name__)

# (table, colonne représentant le "pays" pour l'affichage) — official_statements
# n'a pas de colonne pays, l'institution en tient lieu (ONU, Commission
# européenne...).
_JOE_SOURCE_TABLES = [
    ("energy_conflicts", "pays"),
    ("social_tensions", "pays"),
    ("military_activity", "pays"),
    ("official_statements", "institution"),
    ("country_news", "pays_code"),
]


def get_joe_articles(limit: int = 50) -> list[dict]:
    """
    Retourne les articles ayant une analyse Joe (clients/joe_agent.py), du plus
    récent au plus ancien — alimente le panneau dédié de la carte
    (viz/build_map.py) : date/heure, pays (ou institution), nom de domaine de
    la source, catégorie/gravité et résumé Joe.

    Ne couvre qu'un sous-ensemble des articles collectés : Joe est
    volontairement borné par cycle (coût API, voir config.JOE_MAX_ARTICLES_PER_RUN).
    """
    selects = [
        f"SELECT s.date, s.{pays_col} AS pays, s.url, j.categorie, j.gravite, j.resume_ia "
        f"FROM {table} s JOIN joe_analysis j ON j.source_table = '{table}' AND j.url = s.url"
        for table, pays_col in _JOE_SOURCE_TABLES
    ]
    query = " UNION ALL ".join(selects) + " ORDER BY date DESC NULLS LAST LIMIT %s"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (limit,))
            rows = cur.fetchall()

    articles = []
    for date, pays, url, categorie, gravite, resume in rows:
        domain = urlparse(url).netloc.removeprefix("www.") if url else None
        # Repli sur l'extension de domaine (voir mapping.country_mapping.TLD_TO_ISO3)
        # quand le pays est inconnu — arrive pour les événements GDELT dont le
        # pays a été effacé (zone stratégique détectée, voir gdelt_client.py)
        # ou jamais résolu. N'écrase jamais une valeur déjà connue (institution
        # pour official_statements, pays_code toujours renseigné pour country_news).
        pays = pays or country_from_domain(domain)
        articles.append(
            {
                "date": date.isoformat() if date else None,
                "pays": pays,
                "source": domain,
                "categorie": categorie,
                "gravite": gravite,
                "resume": resume,
                "url": url,
            }
        )
    return articles


def _find_country(question: str) -> tuple[str, str] | None:
    """Retourne (iso3, nom matché) du premier pays reconnu dans la question.

    Tri par longueur de nom décroissante pour préférer un match plus spécifique
    (ex. "Corée du Sud" avant un éventuel "Corée" seul).
    """
    q_lower = question.lower()
    for name, iso3 in sorted(COUNTRY_NAME_TO_ISO3.items(), key=lambda kv: -len(kv[0])):
        if name.lower() in q_lower:
            return iso3, name
    return None


def _handle_debt(cur, iso3: str) -> str | None:
    cur.execute(
        "SELECT annee, dette_pct_pib, dette_montant_milliards_usd FROM country_debt "
        "WHERE pays_code=%s AND dette_pct_pib IS NOT NULL ORDER BY annee DESC LIMIT 1",
        (iso3,),
    )
    row = cur.fetchone()
    if not row:
        return None
    annee, pct, montant = row
    result = f"la dette publique était de {float(pct):g}% du PIB en {annee}"
    if montant is not None:
        montant_str = f"{float(montant):,.0f}".replace(",", " ")
        result += f", soit environ {montant_str} milliards de USD"
    return result


def _handle_economy(cur, iso3: str) -> str | None:
    parts = []
    for col, label in [
        ("chomage_pct", "le taux de chômage était de {v:g}% en {a}"),
        ("inflation_pct", "l'inflation était de {v:g}% en {a}"),
        ("impots_pct_pib", "les recettes fiscales représentaient {v:g}% du PIB en {a}"),
    ]:
        cur.execute(
            f"SELECT annee, {col} FROM country_economy "
            f"WHERE pays_code=%s AND {col} IS NOT NULL ORDER BY annee DESC LIMIT 1",
            (iso3,),
        )
        row = cur.fetchone()
        if row:
            parts.append(label.format(v=float(row[1]), a=row[0]))
    return ", ".join(parts) if parts else None


def _handle_defense(cur, iso3: str) -> str | None:
    cur.execute(
        "SELECT annee, budget_pct_pib FROM defense_budget "
        "WHERE pays_code=%s AND budget_pct_pib IS NOT NULL ORDER BY annee DESC LIMIT 1",
        (iso3,),
    )
    row = cur.fetchone()
    if not row:
        return None
    return f"le budget défense était de {float(row[1]):g}% du PIB en {row[0]}"


def _handle_industry(cur, iso3: str) -> str | None:
    cur.execute(
        "SELECT annee, production_industrielle_pct_pib FROM country_industry "
        "WHERE pays_code=%s AND production_industrielle_pct_pib IS NOT NULL ORDER BY annee DESC LIMIT 1",
        (iso3,),
    )
    row = cur.fetchone()
    if not row:
        return None
    return f"la production industrielle représentait {float(row[1]):g}% du PIB en {row[0]}"


def _handle_credit_rating(cur, iso3: str) -> str | None:
    cur.execute(
        "SELECT agence, note, perspective, date_notation FROM credit_ratings "
        "WHERE pays_code=%s ORDER BY agence",
        (iso3,),
    )
    ratings = cur.fetchall()
    if not ratings:
        return None
    parts = [
        f"{agence} : {note or '?'} (perspective {perspective or '?'}, "
        f"dernière mise à jour de cette notation : "
        f"{date_n.strftime('%d/%m/%Y') if date_n else 'date inconnue'})"
        for agence, note, perspective, date_n in ratings
    ]
    return "notations de crédit souveraines — " + "; ".join(parts)


def _handle_risk(cur, iso3: str) -> str | None:
    cur.execute(
        "SELECT score_global, date_calcul FROM risk_scores "
        "WHERE pays_code=%s ORDER BY date_calcul DESC LIMIT 1",
        (iso3,),
    )
    row = cur.fetchone()
    if not row:
        return None
    return f"le score de risque calculé est de {float(row[0]):g}/100 (au {row[1].strftime('%d/%m/%Y')})"


def _handle_conflicts(cur, iso3: str) -> str | None:
    cur.execute("SELECT COUNT(*) FROM energy_conflicts WHERE pays=%s", (iso3,))
    n_conflicts = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM social_tensions WHERE pays=%s", (iso3,))
    n_tensions = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM military_activity WHERE pays=%s", (iso3,))
    n_military = cur.fetchone()[0]
    if n_conflicts == 0 and n_tensions == 0 and n_military == 0:
        return None
    return (
        f"{n_conflicts} conflit(s) énergétique(s), {n_tensions} tension(s) sociale(s) "
        f"et {n_military} événement(s) d'activité militaire recensés (couverture presse GDELT, "
        "pas un décompte exhaustif)"
    )


def _handle_conflicts_list(cur, iso3: str) -> str | None:
    """Liste les événements récents (titre, date, source) plutôt qu'un simple
    comptage — le moteur va chercher les sources réelles au lieu d'agréger.
    """
    events = []
    for table, label in [
        ("energy_conflicts", "conflit énergétique"),
        ("social_tensions", "tension sociale"),
        ("military_activity", "activité militaire"),
    ]:
        cur.execute(
            f"SELECT s.date, s.titre, s.url, s.source_verifiee, s.resume, j.categorie, j.gravite "
            f"FROM {table} s LEFT JOIN joe_analysis j "
            f"  ON j.source_table = %s AND j.url = s.url "
            f"WHERE s.pays=%s AND s.titre IS NOT NULL ORDER BY s.date DESC LIMIT 5",
            (table, iso3),
        )
        events.extend(
            (label, date, titre, url, verifiee, resume, categorie, gravite)
            for date, titre, url, verifiee, resume, categorie, gravite in cur.fetchall()
        )

    if not events:
        return None

    events.sort(key=lambda e: e[1] or "", reverse=True)
    events = events[:8]

    # source_verifiee : la page a été scrapée avec succès au moment de la
    # collecte (voir clients/article_scraper.py) — confirme que le lien est
    # réel, pas mort/bloqué, plutôt que de faire confiance aveuglément à GDELT.
    # resume : extrait des premières phrases de la page scrapée (voir
    # article_scraper.summarize()), affiché à la place du seul titre quand
    # disponible — plus informatif qu'un titre parfois tronqué par GDELT.
    # categorie/gravite : analyse complémentaire de l'agent "Joe" (LLM Gemini,
    # voir clients/joe_agent.py) — dimension optionnelle, seul un sous-ensemble
    # borné d'articles en dispose (coût API), absente pour la plupart.
    lines = [
        f"[{label}, {date.strftime('%d/%m/%Y') if date else 'date inconnue'}"
        f"{', source vérifiée' if verifiee else ''}"
        f"{f', Joe : {categorie} ({gravite})' if categorie else ''}] {resume or titre} ({url})"
        for label, date, titre, url, verifiee, resume, categorie, gravite in events
    ]
    return (
        "derniers événements recensés (couverture presse GDELT, pas un décompte exhaustif) :\n- "
        + "\n- ".join(lines)
    )


def _handle_global_synthesis(cur) -> str:
    """Aperçu agrégé tous pays confondus (pas un résumé par pays)."""
    cur.execute(
        """
        SELECT DISTINCT ON (pays_code) pays_code, score_global
        FROM risk_scores
        ORDER BY pays_code, date_calcul DESC
        """
    )
    latest_scores = cur.fetchall()
    top5 = sorted(latest_scores, key=lambda r: -float(r[1]))[:5]
    top5_str = ", ".join(f"{pays} ({float(score):.1f}/100)" for pays, score in top5)

    cur.execute(
        "SELECT AVG(v) FROM (SELECT DISTINCT ON (pays_code) dette_pct_pib AS v FROM country_debt "
        "WHERE dette_pct_pib IS NOT NULL ORDER BY pays_code, annee DESC) t"
    )
    avg_debt = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM energy_conflicts")
    n_conflicts = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM social_tensions")
    n_tensions = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM military_activity")
    n_military = cur.fetchone()[0]

    parts = [
        f"{n_conflicts} conflit(s) énergétique(s), {n_tensions} tension(s) sociale(s) et "
        f"{n_military} événement(s) d'activité militaire recensés au total (couverture presse GDELT, "
        "pas un décompte exhaustif)"
    ]
    if avg_debt is not None:
        parts.append(f"dette publique moyenne des pays surveillés : {float(avg_debt):.1f}% du PIB")
    if top5:
        parts.append(f"pays au score de risque le plus élevé actuellement : {top5_str}")

    return "Synthèse mondiale : " + ", ".join(parts) + "."


# Mots-clés déclenchant l'aperçu global (tous pays confondus) plutôt qu'une
# réponse pays par pays — vérifiés AVANT la recherche de pays dans la question.
GLOBAL_KEYWORDS = [
    "mondial", "mondiale", "monde", "global", "globale", "ensemble des pays",
    "tous les pays", "synthese", "synthèse", "vue d'ensemble", "vue d ensemble",
    "situation generale", "situation générale",
]


# (mots-clés déclencheurs, fonction de réponse) — la question par défaut (aucun mot-clé
# reconnu) déclenche un aperçu combinant économie + dette + risque.
DIMENSION_KEYWORDS: list[tuple[list[str], object]] = [
    (["dette"], _handle_debt),
    (["economie", "économie", "économique", "chomage", "chômage", "inflation", "impot", "impôt"], _handle_economy),
    (["defense", "défense", "militaire", "armee", "armée"], _handle_defense),
    (["industrie", "industriel"], _handle_industry),
    (["risque"], _handle_risk),
    (["conflit", "tension", "guerre", "attaque"], _handle_conflicts),
    (["notation", "credit", "crédit", "s&p", "moody", "fitch"], _handle_credit_rating),
]

# Mots-clés reconnaissant une demande de LISTE/DÉTAIL (sources individuelles) plutôt
# qu'un simple comptage agrégé — combinés à un mot-clé "conflit" ci-dessus, ils
# font basculer vers _handle_conflicts_list (titre, date, url par événement).
CONFLICT_KEYWORDS = ["conflit", "tension", "guerre", "attaque", "militaire"]
LIST_KEYWORDS = [
    "liste", "lister", "listes", "detail", "détail", "details", "détails",
    "quels sont", "quelles sont", "sources", "source d'information", "sources d'information",
]

_DEFAULT_HANDLERS = [_handle_economy, _handle_debt, _handle_credit_rating, _handle_risk]


def answer_question(question: str) -> str:
    """
    Répond à une question en langage naturel simple à partir des données Neon.

    Un PAYS reconnu dans la question (nom français/anglais, via
    mapping.country_mapping) a toujours priorité : combiné à un mot-clé de
    dimension (dette, économie, défense, industrie, risque, conflits), ou, si
    aucune dimension précise n'est reconnue, un aperçu combiné par pays (économie +
    dette + risque) — c'est la "synthèse par pays". Un mot-clé de conflit
    (CONFLICT_KEYWORDS) combiné à un mot-clé de liste/détail (LIST_KEYWORDS, ex.
    "liste des conflits", "quels sont les conflits") déclenche une recherche
    autonome des SOURCES individuelles (titre, date, url par événement) plutôt
    qu'un simple comptage. Seulement si AUCUN pays n'est reconnu, les mots-clés de
    synthèse mondiale (GLOBAL_KEYWORDS, ex. "vue d'ensemble", "situation
    mondiale") déclenchent un aperçu agrégé tous pays confondus. Si ni pays ni
    synthèse globale ne sont reconnus, le dit explicitement plutôt que d'inventer
    une réponse.
    """
    q_lower = question.lower()
    country_match = _find_country(question)

    if country_match is None:
        if any(kw in q_lower for kw in GLOBAL_KEYWORDS):
            with get_connection() as conn:
                with conn.cursor() as cur:
                    return _handle_global_synthesis(cur)
        return (
            "Je n'ai pas reconnu de pays dans votre question. "
            'Essayez par exemple : "quelle est la dette de la France ?" '
            'ou "donne-moi une vue d\'ensemble".'
        )

    iso3, country_name = country_match

    if any(kw in q_lower for kw in CONFLICT_KEYWORDS) and any(kw in q_lower for kw in LIST_KEYWORDS):
        matched_handlers = [_handle_conflicts_list]
    else:
        matched_handlers = [
            handler for keywords, handler in DIMENSION_KEYWORDS if any(kw in q_lower for kw in keywords)
        ]
        if not matched_handlers:
            matched_handlers = _DEFAULT_HANDLERS

    answers = []
    with get_connection() as conn:
        with conn.cursor() as cur:
            for handler in matched_handlers:
                result = handler(cur, iso3)
                if result:
                    answers.append(result)

    if not answers:
        return f"Aucune donnée trouvée pour {country_name} sur cette question."

    return f"Pour {country_name} : " + ", ".join(answers) + "."
