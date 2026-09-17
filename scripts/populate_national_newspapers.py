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

    # --- 9 pays ajoutés depuis data/whitelist/whitelist_journaux.md, chacun
    # traité par son propre sous-agent dédié (voir collectors/collect_newspapers_*.py)
    # plutôt que par le sous-agent générique — présents ici pour l'annuaire/
    # affichage uniquement (voir _EXCLUDED_COUNTRIES dans _joe_subagent.py).
    {"name": "Jornal de Angola", "country": "Angola", "region": "Afrique",
     "language": "portugais", "website_url": "https://www.jornaldeangola.ao",
     "political_leaning": "officiel (gouvernemental)"},
    {"name": "Azernews", "country": "Azerbaïdjan", "region": "Europe de l'Est, Russie & Asie Centrale",
     "language": "anglais", "website_url": "https://www.azernews.az",
     "political_leaning": "semi-officiel"},
    {"name": "Kathimerini", "country": "Grèce", "region": "Europe & UK",
     "language": "grec", "website_url": "https://www.kathimerini.gr",
     "political_leaning": "centre-droit"},
    {"name": "Libya Observer", "country": "Libye", "region": "Afrique",
     "language": "anglais", "website_url": "https://www.libyaobserver.ly",
     "political_leaning": "indépendant"},
    {"name": "Aftenposten", "country": "Norvège", "region": "Europe & UK",
     "language": "norvégien", "website_url": "https://www.aftenposten.no",
     "political_leaning": "centriste"},
    {"name": "Sudan Tribune", "country": "Soudan", "region": "Afrique",
     "language": "anglais", "website_url": "https://www.sudantribune.com",
     "political_leaning": "indépendant (diaspora)"},
    {"name": "SANA", "country": "Syrie", "region": "Moyen-Orient, Égypte, Turquie, Israël & GCC",
     "language": "arabe", "website_url": "https://www.sana.sy",
     "political_leaning": "officiel (étatique)"},
    {"name": "El Universal", "country": "Venezuela", "region": "Amérique du Nord & Latine",
     "language": "espagnol", "website_url": "https://www.eluniversal.com",
     "political_leaning": "indépendant"},
    {"name": "Al-Masdar Online", "country": "Yémen", "region": "Moyen-Orient, Égypte, Turquie, Israël & GCC",
     "language": "arabe", "website_url": "https://www.almasdaronline.com",
     "political_leaning": "indépendant"},

    # --- 41 pays complétant la couverture de data/whitelist/whitelist_journaux.md
    # (77 pays/territoires au total) : jusqu'ici seuls 36 pays de la whitelist
    # étaient seedés ici, ce qui limitait d'autant collect_newspaper_discovery.py
    # (n'élargit que les pays DÉJÀ présents dans national_newspapers). Un seul
    # journal retenu par pays (le premier/le plus représentatif de la
    # whitelist) ; à étoffer au besoin comme le reste de ce fichier.

    # --- Afrique ---
    {"name": "News24", "country": "Afrique du Sud", "region": "Afrique",
     "language": "anglais", "website_url": "https://www.news24.com",
     "political_leaning": "continu, référence"},
    {"name": "El Watan", "country": "Algérie", "region": "Afrique",
     "language": "français", "website_url": "https://www.elwatan.com",
     "political_leaning": "indépendant, francophone"},
    {"name": "Cameroon Tribune", "country": "Cameroun", "region": "Afrique",
     "language": "français / anglais", "website_url": "https://www.cameroon-tribune.cm",
     "political_leaning": "gouvernemental, bilingue"},
    {"name": "Fraternité Matin", "country": "Côte d'Ivoire", "region": "Afrique",
     "language": "français", "website_url": "https://www.fratmat.info",
     "political_leaning": "gouvernemental"},
    {"name": "Daily Nation", "country": "Kenya", "region": "Afrique",
     "language": "anglais", "website_url": "https://www.nation.africa",
     "political_leaning": "majeur, généraliste"},
    {"name": "Le Matin", "country": "Maroc", "region": "Afrique",
     "language": "français / arabe", "website_url": "https://www.lematin.ma",
     "political_leaning": "proche des institutions"},
    {"name": "The Punch", "country": "Nigeria", "region": "Afrique",
     "language": "anglais", "website_url": "https://www.punchng.com",
     "political_leaning": "généraliste"},
    {"name": "Le Soleil", "country": "Sénégal", "region": "Afrique",
     "language": "français", "website_url": "https://www.lesoleil.sn",
     "political_leaning": "national, généraliste"},
    {"name": "La Presse de Tunisie", "country": "Tunisie", "region": "Afrique",
     "language": "français / arabe", "website_url": "https://www.lapresse.tn",
     "political_leaning": "national, français"},

    # --- Amérique du Nord & Latine ---
    {"name": "The Globe and Mail", "country": "Canada", "region": "Amérique du Nord & Latine",
     "language": "anglais", "website_url": "https://www.theglobeandmail.com",
     "political_leaning": "centre / libéral-modéré"},
    {"name": "El Mercurio", "country": "Chili", "region": "Amérique du Nord & Latine",
     "language": "espagnol", "website_url": "https://www.emol.com",
     "political_leaning": "conservateur"},
    {"name": "La Nación", "country": "Costa Rica", "region": "Amérique du Nord & Latine",
     "language": "espagnol", "website_url": "https://www.nacion.com",
     "political_leaning": "centre droit, référence"},
    {"name": "Amigoe", "country": "Curaçao / Aruba / Saint-Martin", "region": "Amérique du Nord & Latine",
     "language": "néerlandais", "website_url": "https://www.amigoe.com",
     "political_leaning": "référence néerlandophone"},
    {"name": "Prensa Libre", "country": "Guatemala", "region": "Amérique du Nord & Latine",
     "language": "espagnol", "website_url": "https://www.prensalibre.com",
     "political_leaning": "plus grand quotidien national"},
    {"name": "The Gleaner", "country": "Jamaïque", "region": "Amérique du Nord & Latine",
     "language": "anglais", "website_url": "https://www.jamaica-gleaner.com",
     "political_leaning": "historique, référence"},
    {"name": "La Prensa", "country": "Panama", "region": "Amérique du Nord & Latine",
     "language": "espagnol", "website_url": "https://www.prensa.com",
     "political_leaning": "indépendant, majeur"},
    {"name": "El Comercio", "country": "Pérou", "region": "Amérique du Nord & Latine",
     "language": "espagnol", "website_url": "https://www.elcomercio.pe",
     "political_leaning": "centre droit"},
    {"name": "El Nuevo Día", "country": "Porto Rico", "region": "Amérique du Nord & Latine",
     "language": "espagnol", "website_url": "https://www.elnuevodia.com",
     "political_leaning": "principal quotidien"},
    {"name": "Listín Diario", "country": "République dominicaine", "region": "Amérique du Nord & Latine",
     "language": "espagnol", "website_url": "https://www.listindiario.com",
     "political_leaning": "le plus ancien"},
    {"name": "La Prensa Gráfica", "country": "Salvador", "region": "Amérique du Nord & Latine",
     "language": "espagnol", "website_url": "https://www.laprensagrafica.com",
     "political_leaning": "généraliste"},
    {"name": "El País", "country": "Uruguay", "region": "Amérique du Nord & Latine",
     "language": "espagnol", "website_url": "https://www.elpais.com.uy",
     "political_leaning": "centre droit"},

    # --- Europe & UK ---
    {"name": "El País", "country": "Espagne", "region": "Europe & UK",
     "language": "espagnol", "website_url": "https://www.elpais.com",
     "political_leaning": "centre gauche"},
    {"name": "De Volkskrant", "country": "Pays-Bas", "region": "Europe & UK",
     "language": "néerlandais", "website_url": "https://www.volkskrant.nl",
     "political_leaning": "centre gauche"},
    {"name": "Público", "country": "Portugal", "region": "Europe & UK",
     "language": "portugais", "website_url": "https://www.publico.pt",
     "political_leaning": "centre gauche"},
    {"name": "NZZ", "country": "Suisse", "region": "Europe & UK",
     "language": "français / allemand", "website_url": "https://www.nzz.ch",
     "political_leaning": "libéral-conservateur, allemand"},

    # --- Europe de l'Est, Russie & Asie Centrale ---
    {"name": "Vecherny Bishkek", "country": "Kirghizistan", "region": "Europe de l'Est, Russie & Asie Centrale",
     "language": "russe / kirghiz / anglais", "website_url": "https://www.vb.kg",
     "political_leaning": "généraliste, russe"},
    {"name": "Asia-Plus", "country": "Tadjikistan", "region": "Europe de l'Est, Russie & Asie Centrale",
     "language": "tadjik / russe / anglais", "website_url": "https://www.asiaplustj.info",
     "political_leaning": "indépendant, principal réseau d'info"},
    {
        "name": "Neutralny Turkmenistan", "country": "Turkménistan",
        "region": "Europe de l'Est, Russie & Asie Centrale",
        "language": "russe / turkmène / anglais", "website_url": "https://neutralturkmenistan.gov.tm",
        "political_leaning": "officiel, russophone",
    },

    # --- Moyen-Orient, Égypte, Turquie, Israël & GCC ---
    {"name": "L'Orient-Le Jour", "country": "Liban", "region": "Moyen-Orient, Égypte, Turquie, Israël & GCC",
     "language": "français / arabe", "website_url": "https://www.lorientlejour.com",
     "political_leaning": "francophone, référence régionale"},

    # --- Asie ---
    {"name": "Prothom Alo", "country": "Bangladesh", "region": "Asie",
     "language": "bengali", "website_url": "https://www.prothomalo.com",
     "political_leaning": "le plus influent, bengali"},
    {"name": "People's Daily", "country": "Chine (officiel)", "region": "Asie",
     "language": "anglais / chinois", "website_url": "https://en.people.cn",
     "political_leaning": "organe du PCC"},
    {"name": "Rodong Sinmun", "country": "Corée du Nord", "region": "Asie",
     "language": "coréen", "website_url": "https://www.rodong.rep.kp",
     "political_leaning": "organe officiel du Parti"},
    {"name": "Chosun Ilbo", "country": "Corée du Sud", "region": "Asie",
     "language": "coréen / anglais", "website_url": "https://www.chosun.com",
     "political_leaning": "conservateur"},
    {"name": "The Jakarta Post", "country": "Indonésie", "region": "Asie",
     "language": "anglais / indonésien", "website_url": "https://www.thejakartapost.com",
     "political_leaning": "indépendant, anglophone"},
    {"name": "Philippine Daily Inquirer", "country": "Philippines", "region": "Asie",
     "language": "anglais", "website_url": "https://www.inquirer.net",
     "political_leaning": "influent"},
    {"name": "Daily Mirror", "country": "Sri Lanka", "region": "Asie",
     "language": "anglais", "website_url": "https://www.dailymirror.lk",
     "political_leaning": "information générale"},
    {"name": "Taipei Times", "country": "Taïwan", "region": "Asie",
     "language": "anglais / chinois", "website_url": "https://www.taipeitimes.com",
     "political_leaning": "anglophone"},
    {"name": "Bangkok Post", "country": "Thaïlande", "region": "Asie",
     "language": "anglais", "website_url": "https://www.bangkokpost.com",
     "political_leaning": "historique, référence"},
    {"name": "Tuoi Tre News", "country": "Vietnam", "region": "Asie",
     "language": "vietnamien / anglais", "website_url": "https://www.tuoitrenews.vn",
     "political_leaning": "édition anglaise, grand public"},

    # --- Océanie (nouvelle région, absente jusqu'ici de ce fichier) ---
    {"name": "The Australian", "country": "Australie", "region": "Océanie",
     "language": "anglais", "website_url": "https://www.theaustralian.com.au",
     "political_leaning": "centre droit"},
    {"name": "NZ Herald", "country": "Nouvelle-Zélande", "region": "Océanie",
     "language": "anglais", "website_url": "https://www.nzherald.co.nz",
     "political_leaning": "principal, Auckland"},
]


def run() -> int:
    return upsert_generic("national_newspapers", NEWSPAPERS)


if __name__ == "__main__":
    from logging_config import configure_logging

    configure_logging()
    n = run()
    print(f"{n} ligne(s) envoyée(s) vers national_newspapers")
