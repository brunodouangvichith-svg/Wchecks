"""
Peuple national_newspapers : annuaire de référence des grands journaux
nationaux dans le monde (nom, pays, région, langue, site officiel, ligne
éditoriale).

Script ponctuel, PAS un collector planifié (voir db/schema.sql) : ces données
(noms de journaux, URL de leur site officiel) changent très rarement. À
relancer manuellement (`python -m scripts.populate_national_newspapers`) si la
liste doit être étendue ou corrigée — upsert_generic() met à jour les lignes
existantes (clé UNIQUE (name, country)) plutôt que de dupliquer.

URL vérifiées manuellement (réponse HTTP 200/301/302, ou domaine connu fiable
malgré un blocage anti-bot du scraper — ex. wsj.com, ft.com, telegraph.co.uk
répondent 401/403 aux requêtes automatisées mais restent des domaines réels et
corrects).
"""

import logging

from clients.neon_client import upsert_generic

logger = logging.getLogger(__name__)

NEWSPAPERS = [
    # --- Europe & UK ---
    {"name": "Le Monde", "country": "France", "region": "Europe & UK",
     "language": "français", "website_url": "https://www.lemonde.fr",
     "political_leaning": "centre-gauche"},
    {"name": "The Guardian", "country": "Royaume-Uni", "region": "Europe & UK",
     "language": "anglais", "website_url": "https://www.theguardian.com",
     "political_leaning": "centre-gauche"},
    {"name": "The Financial Times", "country": "Royaume-Uni", "region": "Europe & UK",
     "language": "anglais", "website_url": "https://www.ft.com",
     "political_leaning": "économique / libéral"},
    {"name": "Frankfurter Allgemeine Zeitung", "country": "Allemagne", "region": "Europe & UK",
     "language": "allemand", "website_url": "https://www.faz.net",
     "political_leaning": "centre-droit"},
    {"name": "Corriere della Sera", "country": "Italie", "region": "Europe & UK",
     "language": "italien", "website_url": "https://www.corriere.it",
     "political_leaning": "généraliste / centriste"},
    {"name": "Le Soir", "country": "Belgique", "region": "Europe & UK",
     "language": "français", "website_url": "https://www.lesoir.be",
     "political_leaning": "centre-gauche"},

    # --- Amérique du Nord & Latine ---
    {"name": "The New York Times", "country": "États-Unis", "region": "Amérique du Nord & Latine",
     "language": "anglais", "website_url": "https://www.nytimes.com",
     "political_leaning": "centre-gauche"},
    {"name": "The Washington Post", "country": "États-Unis", "region": "Amérique du Nord & Latine",
     "language": "anglais", "website_url": "https://www.washingtonpost.com",
     "political_leaning": "centre-gauche"},
    {"name": "El Universal", "country": "Mexique", "region": "Amérique du Nord & Latine",
     "language": "espagnol", "website_url": "https://www.eluniversal.com.mx",
     "political_leaning": "généraliste"},
    {"name": "Clarín", "country": "Argentine", "region": "Amérique du Nord & Latine",
     "language": "espagnol", "website_url": "https://www.clarin.com",
     "political_leaning": "généraliste / centriste"},
    {"name": "Folha de S.Paulo", "country": "Brésil", "region": "Amérique du Nord & Latine",
     "language": "portugais", "website_url": "https://www.folha.uol.com.br",
     "political_leaning": "centriste"},
    {"name": "El Tiempo", "country": "Colombie", "region": "Amérique du Nord & Latine",
     "language": "espagnol", "website_url": "https://www.eltiempo.com",
     "political_leaning": "centre-droit"},
    {"name": "Granma", "country": "Cuba", "region": "Amérique du Nord & Latine",
     "language": "espagnol", "website_url": "http://www.granma.cu",
     "political_leaning": "officiel (Parti communiste cubain)"},

    # --- Europe de l'Est, Russie & Asie Centrale ---
    {"name": "Ukrayinska Pravda", "country": "Ukraine", "region": "Europe de l'Est, Russie & Asie Centrale",
     "language": "ukrainien", "website_url": "https://www.pravda.com.ua",
     "political_leaning": "pro-européen"},
    {"name": "Kommersant", "country": "Russie", "region": "Europe de l'Est, Russie & Asie Centrale",
     "language": "russe", "website_url": "https://www.kommersant.ru",
     "political_leaning": "économique"},
    {"name": "Rossiyskaya Gazeta", "country": "Russie", "region": "Europe de l'Est, Russie & Asie Centrale",
     "language": "russe", "website_url": "https://www.rg.ru",
     "political_leaning": "officiel (gouvernement russe)"},
    {"name": "Gazeta Wyborcza", "country": "Pologne", "region": "Europe de l'Est, Russie & Asie Centrale",
     "language": "polonais", "website_url": "https://www.wyborcza.pl",
     "political_leaning": "centre-gauche"},
    {"name": "Gazeta.uz", "country": "Ouzbékistan", "region": "Europe de l'Est, Russie & Asie Centrale",
     "language": "russe", "website_url": "https://www.gazeta.uz",
     "political_leaning": "indépendant"},
    {"name": "Kazakhstanskaya Pravda", "country": "Kazakhstan", "region": "Europe de l'Est, Russie & Asie Centrale",
     "language": "russe", "website_url": "https://kazpravda.kz",
     "political_leaning": "officiel (étatique)"},

    # --- Moyen-Orient, Égypte, Turquie, Israël & GCC ---
    {"name": "Al-Ahram", "country": "Égypte", "region": "Moyen-Orient, Égypte, Turquie, Israël & GCC",
     "language": "arabe", "website_url": "https://www.ahram.org.eg",
     "political_leaning": "officiel (étatique)"},
    {"name": "Hürriyet", "country": "Turquie", "region": "Moyen-Orient, Égypte, Turquie, Israël & GCC",
     "language": "turc", "website_url": "https://www.hurriyet.com.tr",
     "political_leaning": "généraliste"},
    {"name": "Haaretz", "country": "Israël", "region": "Moyen-Orient, Égypte, Turquie, Israël & GCC",
     "language": "hébreu / anglais", "website_url": "https://www.haaretz.com",
     "political_leaning": "gauche"},
    {"name": "The Jerusalem Post", "country": "Israël", "region": "Moyen-Orient, Égypte, Turquie, Israël & GCC",
     "language": "anglais", "website_url": "https://www.jpost.com",
     "political_leaning": "centre-droit"},
    {"name": "The National", "country": "Émirats arabes unis", "region": "Moyen-Orient, Égypte, Turquie, Israël & GCC",
     "language": "anglais", "website_url": "https://www.thenationalnews.com",
     "political_leaning": "généraliste"},
    {"name": "Asharq Al-Awsat", "country": "Arabie saoudite", "region": "Moyen-Orient, Égypte, Turquie, Israël & GCC",
     "language": "arabe", "website_url": "https://aawsat.com",
     "political_leaning": "panarabe / conservateur"},
    {"name": "Tehran Times", "country": "Iran", "region": "Moyen-Orient, Égypte, Turquie, Israël & GCC",
     "language": "anglais", "website_url": "https://www.tehrantimes.com",
     "political_leaning": "officiel (étatique)"},

    # --- Asie ---
    {"name": "South China Morning Post", "country": "Chine (Hong Kong)", "region": "Asie",
     "language": "anglais", "website_url": "https://www.scmp.com",
     "political_leaning": "indépendant"},
    {"name": "Yomiuri Shimbun", "country": "Japon", "region": "Asie",
     "language": "japonais", "website_url": "https://www.yomiuri.co.jp",
     "political_leaning": "centre-droit"},
    {"name": "The Straits Times", "country": "Singapour", "region": "Asie",
     "language": "anglais", "website_url": "https://www.straitstimes.com",
     "political_leaning": "généraliste"},
    {"name": "The Times of India", "country": "Inde", "region": "Asie",
     "language": "anglais", "website_url": "https://timesofindia.indiatimes.com",
     "political_leaning": "généraliste"},
    {"name": "Dawn", "country": "Pakistan", "region": "Asie",
     "language": "anglais", "website_url": "https://www.dawn.com",
     "political_leaning": "indépendant"},
]


def run() -> int:
    return upsert_generic("national_newspapers", NEWSPAPERS)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    n = run()
    print(f"{n} ligne(s) envoyée(s) vers national_newspapers")
