"""
Peuple international_organizations : annuaire de référence des grandes
organisations internationales et institutions financières mondiales (rôle,
ressources de données publiques notables, site officiel).

Script ponctuel, PAS un collector planifié (voir db/schema.sql) : ces données
changent très rarement. À relancer manuellement
(`python -m scripts.populate_international_organizations`) si la liste doit
être étendue ou corrigée — upsert_generic() met à jour les lignes existantes
(clé UNIQUE name) plutôt que de dupliquer.

URL vérifiées manuellement (réponse HTTP 200/301/302, ou domaine connu fiable
malgré un blocage anti-bot du scraper — ex. imf.org, oecd.org, afdb.org,
iadb.org répondent 403 aux requêtes automatisées mais restent des domaines
réels et corrects).
"""

import logging

from clients.neon_client import upsert_generic

logger = logging.getLogger(__name__)

ORGANIZATIONS = [
    # --- Institutions financières internationales (IFI) ---
    {"name": "FMI (Fonds Monétaire International)", "category": "Institution financière internationale",
     "role": "Stabilité financière mondiale, prévention des crises et prêts d'urgence aux États.",
     "key_resources": "Rapports Perspectives de l'économie mondiale (WEO), base de statistiques financières nationales et internationales.",
     "website_url": "https://www.imf.org", "region": "Mondial"},
    {"name": "Groupe de la Banque mondiale", "category": "Institution financière internationale",
     "role": "Financement de projets de développement à long terme et réduction de la pauvreté.",
     "key_resources": "Base World Development Indicators (WDI).",
     "website_url": "https://www.worldbank.org", "region": "Mondial"},
    {"name": "BRI (Banque des Règlements Internationaux)", "category": "Institution financière internationale",
     "role": "Banque des banques centrales ; héberge le Comité de Bâle sur le contrôle bancaire.",
     "key_resources": "Statistiques bancaires internationales, rapports sur les marchés des changes et produits dérivés.",
     "website_url": "https://www.bis.org", "region": "Mondial"},
    {"name": "OCDE", "category": "Institution financière internationale",
     "role": "Analyse économique et harmonisation des politiques publiques (fiscalité, impôt minimum mondial...).",
     "key_resources": "Portail OECD iLibrary (PIB, emploi, éducation, inflation, fiscalité).",
     "website_url": "https://www.oecd.org", "region": "Mondial"},

    # --- Banques de développement régionales ---
    {"name": "Banque européenne d'investissement (BEI)", "category": "Banque de développement régionale",
     "role": "Institution de financement de l'Union européenne, axée transition écologique et innovation.",
     "key_resources": None, "website_url": "https://www.eib.org", "region": "Europe"},
    {"name": "Banque africaine de développement (BAD)", "category": "Banque de développement régionale",
     "role": "Financement de projets d'infrastructure, d'énergie et d'agriculture en Afrique.",
     "key_resources": None, "website_url": "https://www.afdb.org", "region": "Afrique"},
    {"name": "Banque asiatique de développement (AsDB)", "category": "Banque de développement régionale",
     "role": "Réduction de la pauvreté en Asie et dans le Pacifique.",
     "key_resources": None, "website_url": "https://www.adb.org", "region": "Asie"},
    {"name": "Banque interaméricaine de développement (BID)", "category": "Banque de développement régionale",
     "role": "Principal bailleur de fonds pour le développement économique et social en Amérique latine et Caraïbes.",
     "key_resources": None, "website_url": "https://www.iadb.org", "region": "Amérique latine"},
    {"name": "Banque européenne pour la reconstruction et le développement (BERD)",
     "category": "Banque de développement régionale",
     "role": "Aide à la transition vers l'économie de marché dans les anciens pays du bloc de l'Est.",
     "key_resources": None, "website_url": "https://www.ebrd.com", "region": "Europe de l'Est"},

    # --- Organisations politiques et judiciaires mondiales ---
    {"name": "ONU (Organisation des Nations Unies)", "category": "Organisation politique/judiciaire",
     "role": "Pivot de la diplomatie mondiale.",
     "key_resources": "Résolutions du Conseil de sécurité, traités internationaux, bases UN Data.",
     "website_url": "https://www.un.org", "region": "Mondial"},
    {"name": "OMC (Organisation mondiale du commerce)", "category": "Organisation politique/judiciaire",
     "role": "Régule les règles du commerce transfrontalier entre nations.",
     "key_resources": "Bases de données sur les tarifs douaniers et les litiges commerciaux.",
     "website_url": "https://www.wto.org", "region": "Mondial"},
    {"name": "CPI (Cour pénale internationale)", "category": "Organisation politique/judiciaire",
     "role": "Juge les individus pour crimes graves (génocide, crimes de guerre...).",
     "key_resources": "Arrêts et conclusions de plaidoiries.",
     "website_url": "https://www.icc-cpi.int", "region": "Mondial"},
    {"name": "CIJ (Cour internationale de justice)", "category": "Organisation politique/judiciaire",
     "role": "Règle les différends juridiques entre États.",
     "key_resources": "Arrêts et conclusions de plaidoiries.",
     "website_url": "https://www.icj-cij.org", "region": "Mondial"},

    # --- Institutions régionales majeures (Europe) ---
    {"name": "Union européenne (Europa)", "category": "Institution régionale européenne",
     "role": "Portail officiel unifiant l'accès à toutes les agences de l'UE.",
     "key_resources": "Eurostat (statistiques européennes), Eur-Lex (Journal officiel de l'UE, recherche juridique).",
     "website_url": "https://www.europa.eu", "region": "Europe"},
    {"name": "BCE (Banque centrale européenne)", "category": "Institution régionale européenne",
     "role": "Gère la politique monétaire de la zone euro.",
     "key_resources": "Historique des taux directeurs, statistiques monétaires, rapports de conjoncture.",
     "website_url": "https://www.ecb.europa.eu", "region": "Europe"},
]


def run() -> int:
    return upsert_generic("international_organizations", ORGANIZATIONS)


if __name__ == "__main__":
    from logging_config import configure_logging

    configure_logging()
    n = run()
    print(f"{n} ligne(s) envoyée(s) vers international_organizations")
