"""
Peuple agences_presses : annuaire de référence des grandes agences de presse
mondiales (Big Three généralistes, agences financières, agences nationales/
régionales à portée internationale).

Script ponctuel, PAS un collector planifié (voir db/schema.sql) — même
principe que national_newspapers : données statiques, changent très rarement.
À relancer manuellement (`python -m scripts.populate_agences_presses`) si la
liste doit être étendue ou corrigée — upsert_generic() met à jour les lignes
existantes (clé UNIQUE name) plutôt que de dupliquer.

URL vérifiées manuellement (réponse HTTP 200/301/302/307, ou domaine connu
fiable malgré un blocage anti-bot du scraper — ex. reuters.com, bloomberg.com
répondent 401/403 aux requêtes automatisées mais restent des domaines réels
et corrects). telam.com.ar n'a pas répondu depuis cet environnement au moment
de la vérification (connexion refusée) — domaine conservé car c'est
l'agence argentine de référence bien connue, à re-vérifier si besoin.
"""

import logging

from clients.neon_client import upsert_generic

logger = logging.getLogger(__name__)

AGENCIES = [
    # --- Les "Big Three" (agences mondiales généralistes) ---
    {"name": "Associated Press (AP)", "category": "Big Three (généraliste mondiale)",
     "country": "États-Unis",
     "specialty": "Coopérative de médias fondée en 1846 ; dépêches et flux vidéo en direct, portail AP News.",
     "website_url": "https://apnews.com", "region": "Mondial"},
    {"name": "Reuters", "category": "Big Three (généraliste mondiale)",
     "country": "Royaume-Uni",
     "specialty": "Division d'information de Thomson Reuters ; actualité générale et information financière ultra-rapide.",
     "website_url": "https://www.reuters.com", "region": "Mondial"},
    {"name": "Agence France-Presse (AFP)", "category": "Big Three (généraliste mondiale)",
     "country": "France",
     "specialty": "Fondée en 1835 (Havas), plus ancienne agence de presse au monde ; dépêches en 6 langues, réseau photo, AFP Live.",
     "website_url": "https://www.afp.com", "region": "Mondial"},

    # --- Information financière et économique en continu ---
    {"name": "Bloomberg News", "category": "Financière/économique",
     "country": "États-Unis",
     "specialty": "Flux financiers mondiaux en temps réel et analyses macroéconomiques (écosystème Bloomberg Terminal).",
     "website_url": "https://www.bloomberg.com", "region": "Mondial"},
    {"name": "Dow Jones Newswires", "category": "Financière/économique",
     "country": "États-Unis",
     "specialty": "Filiale de News Corp (Wall Street Journal) ; un des plus anciens flux de dépêches financières en direct.",
     "website_url": "https://www.dowjones.com", "region": "Mondial"},

    # --- Grandes agences nationales et régionales à portée internationale ---
    {"name": "Xinhua", "category": "Régionale/nationale",
     "country": "Chine",
     "specialty": "Agence de presse officielle de l'État chinois ; flux massifs en plusieurs langues.",
     "website_url": "https://english.news.cn", "region": "Asie & Pacifique"},
    {"name": "Deutsche Presse-Agentur (DPA)", "category": "Régionale/nationale",
     "country": "Allemagne",
     "specialty": "Agence allemande de référence, très présente sur le web européen, flux extrêmement rapides.",
     "website_url": "https://www.dpa.com", "region": "Europe"},
    {"name": "ANSA", "category": "Régionale/nationale", "country": "Italie",
     "specialty": None, "website_url": "https://www.ansa.it", "region": "Europe"},
    {"name": "EFE", "category": "Régionale/nationale", "country": "Espagne",
     "specialty": None, "website_url": "https://www.efe.com", "region": "Europe"},
    {"name": "TASS", "category": "Régionale/nationale", "country": "Russie",
     "specialty": None, "website_url": "https://tass.com", "region": "Europe"},
    {"name": "Interfax", "category": "Régionale/nationale", "country": "Russie",
     "specialty": None, "website_url": "https://www.interfax.com", "region": "Europe"},
    {"name": "Anadolu Agency", "category": "Régionale/nationale",
     "country": "Turquie",
     "specialty": "Forte croissance internationale récente ; couvre Moyen-Orient, Afrique et Europe de l'Est en une douzaine de langues.",
     "website_url": "https://www.aa.com.tr", "region": "Moyen-Orient & Afrique"},
    {"name": "Emirates News Agency (WAM)", "category": "Régionale/nationale",
     "country": "Émirats arabes unis",
     "specialty": None, "website_url": "https://www.wam.ae", "region": "Moyen-Orient & Afrique"},
    {"name": "Kyodo News", "category": "Régionale/nationale",
     "country": "Japon",
     "specialty": "Principale agence d'information du Japon ; référence pour l'actualité économique et technologique d'Asie de l'Est.",
     "website_url": "https://english.kyodonews.net", "region": "Asie & Pacifique"},
    {"name": "Press Trust of India (PTI)", "category": "Régionale/nationale",
     "country": "Inde",
     "specialty": None, "website_url": "https://www.ptinews.com", "region": "Asie & Pacifique"},
    {"name": "Yonhap News Agency", "category": "Régionale/nationale",
     "country": "Corée du Sud",
     "specialty": None, "website_url": "https://en.yna.co.kr", "region": "Asie & Pacifique"},
    {"name": "The Canadian Press", "category": "Régionale/nationale",
     "country": "Canada",
     "specialty": None, "website_url": "https://www.thecanadianpress.com", "region": "Amériques"},
    {"name": "Télam", "category": "Régionale/nationale",
     "country": "Argentine",
     "specialty": None, "website_url": "https://www.telam.com.ar", "region": "Amériques"},
]


def run() -> int:
    return upsert_generic("agences_presses", AGENCIES)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    n = run()
    print(f"{n} ligne(s) envoyée(s) vers agences_presses")
