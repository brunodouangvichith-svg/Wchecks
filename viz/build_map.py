"""
Génère la carte interactive `carte_mondiale.html` (Folium/Leaflet, tuiles
OpenStreetMap) à partir des données stockées dans Neon.

Couches par points : conflits énergétiques (rouge), tensions sociales (orange).

Couches choroplèthes par pays (une sélectionnable à la fois via LayerControl) :
dette, chômage, inflation, budget défense, production pétrolière/gazière,
production industrielle. (Les minerais stratégiques et les couches activité
militaire/trafic maritime/déclarations officielles restent retirés de
l'affichage carte à la demande — les données sous-jacentes restent
collectées et utilisées par le QA/l'agent Joe.)

GeoJSON des frontières : viz/data/world_countries.geojson — dérivé de Natural
Earth (domaine public), redistribué via github.com/johan/world.geo.json.

Widgets flottants : questions/réponses (bas, centré), articles analysés par
l'agent Joe (gauche) et 2 boutons de rapport journalier classé par thème
(haut droite : points chauds de l'actualité / données financières).
"""

import copy
import html
import json
import logging
from pathlib import Path

import folium
import pandas as pd
from branca.element import MacroElement
from folium.plugins import MarkerCluster
from jinja2 import Template

import config
from clients.neon_client import ORDER_FIELD, get_connection
from mapping.country_mapping import COUNTRY_NAME_TO_ISO3

logger = logging.getLogger(__name__)

GEOJSON_PATH = config.BASE_DIR / "viz" / "data" / "world_countries.geojson"
OUTPUT_PATH = config.BASE_DIR / "carte_mondiale.html"

# Backend interrogé par le widget vocal/texte (endpoint /ask de scheduler.py, déployé
# sur Render). La carte étant un fichier statique (GitHub Pages), toute logique de
# question/réponse doit passer par ce service distant — voir qa/engine.py.
QA_BACKEND_URL = "https://globalchecks-scheduler.onrender.com/ask"

# Backend du panneau "articles analysés par Joe" (endpoint /joe-articles de
# scheduler.py, voir qa/engine.get_joe_articles).
JOE_BACKEND_URL = "https://globalchecks-scheduler.onrender.com/joe-articles"

# Backend des 2 boutons de rapport journalier (endpoint /daily-report de
# scheduler.py, voir qa/engine.get_daily_report — sous-agents dédiés
# collectors/collect_report_hotspots.py et collect_report_financial.py).
REPORTS_BACKEND_URL = "https://globalchecks-scheduler.onrender.com/daily-report"

POINT_LAYERS = [
    ("energy_conflicts", "red", "Conflits énergétiques"),
    ("social_tensions", "orange", "Tensions sociales"),
]

# (table, colonne, légende, palette de couleurs branca)
CHOROPLETH_SPECS = [
    ("country_economy", "chomage_pct", "Chômage (%)", "OrRd"),
    ("country_economy", "inflation_pct", "Inflation (%)", "YlOrRd"),
    ("defense_budget", "budget_pct_pib", "Budget défense (% du PIB)", "Purples"),
    ("oil_production", "valeur_barils_jour", "Production pétrolière (milliers de barils/jour)", "Blues"),
    ("gas_production", "valeur_production_gaz", "Production de gaz naturel (milliards de m³)", "Greens"),
    ("country_industry", "production_industrielle_pct_pib", "Production industrielle (% du PIB)", "BuPu"),
]


def _neutralize_template_syntax(text: str) -> str:
    """
    Certains sites scrapés laissent fuiter tels quels leurs propres artefacts
    de template non rendus côté serveur (ex. `{{hitsCtrl.values.hits}}`, un
    widget de compteur de vues) dans le texte de l'article — une chaîne
    parfaitement inerte pour nous, MAIS folium/Jinja2 re-parse l'intégralité
    du HTML de la carte au moment du rendu (`m.save()`), et une séquence
    `{{ ... }}` littérale dans un résumé scrapé est alors interprétée comme une
    VRAIE expression Jinja — ce qui fait planter `build_map()` (constaté en
    pratique sur un article Dailymirror contenant un tel artefact). On casse
    la séquence en insérant un espace de largeur nulle entre les accolades
    consécutives, sans changer l'affichage visible.
    """
    return text.replace("{{", "{​{").replace("}}", "}​}")


def _load_enriched_geojson() -> dict:
    data = json.loads(GEOJSON_PATH.read_text(encoding="utf-8"))
    unmatched = set()
    for feature in data["features"]:
        name = feature["properties"].get("name")
        iso3 = COUNTRY_NAME_TO_ISO3.get(name)
        # folium traite une valeur de clé `None` comme une erreur fatale ("key_on not
        # found"), pas comme une donnée manquante à griser — on utilise donc une chaîne
        # vide (qui ne correspondra jamais à un vrai code ISO3) pour les entités sans
        # pays connu (territoires, zones disputées).
        feature["properties"]["iso3"] = iso3 or ""
        if iso3 is None:
            unmatched.add(name)
    if unmatched:
        logger.info(
            "build_map: %d entité(s) du GeoJSON sans correspondance pays "
            "(territoires/zones disputées, attendu) : %s",
            len(unmatched), sorted(unmatched),
        )
    return data


def _add_point_layer(m: folium.Map, cur, table: str, color: str, label: str) -> None:
    # MarkerCluster : de nombreux événements GDELT partagent la même position (le
    # centroïde du pays, faute de géolocalisation précise par article — jusqu'à 105
    # marqueurs empilés au même point pour les USA). Le clustering les regroupe en
    # une bulle avec un compteur, qui se déplie au clic/zoom plutôt que de rester
    # illisible. Note : le clustering Leaflet ne fonctionne qu'avec de vrais Marker
    # (icônes), pas les CircleMarker (calques vectoriels) — d'où le changement de type.
    fg = folium.FeatureGroup(name=label, show=(table == "energy_conflicts"))
    cluster = MarkerCluster().add_to(fg)
    cur.execute(
        f"SELECT s.lat, s.lon, s.titre, s.url, s.date, s.source_verifiee, s.resume, j.categorie, j.gravite "
        f"FROM {table} s LEFT JOIN joe_analysis j ON j.source_table = %s AND j.url = s.url "
        f"WHERE s.lat IS NOT NULL AND s.lon IS NOT NULL",
        (table,),
    )
    rows = cur.fetchall()
    for lat, lon, titre, url, date, verifiee, resume, categorie, gravite in rows:
        titre_safe = _neutralize_template_syntax(titre or "(sans titre)")
        popup_html = f"<b>{html.escape(titre_safe)}</b><br>{date or ''}"
        if resume:
            popup_html += f"<br>{html.escape(_neutralize_template_syntax(resume))}"
        if categorie:
            gravite_safe = _neutralize_template_syntax(gravite or "?")
            popup_html += f"<br>🤖 Joe : {html.escape(_neutralize_template_syntax(categorie))} ({html.escape(gravite_safe)})"
        if verifiee:
            popup_html += "<br>✅ source vérifiée (scraping)"
        if url:
            popup_html += f'<br><a href="{html.escape(url)}" target="_blank">source</a>'
        folium.Marker(
            location=[lat, lon],
            icon=folium.Icon(color=color),
            popup=folium.Popup(popup_html, max_width=300),
        ).add_to(cluster)
    fg.add_to(m)
    logger.info("build_map: %s -> %d point(s)", table, len(rows))


def _add_choropleth(
    m: folium.Map, cur, table: str, value_col: str, legend_name: str, color_scheme: str,
    geojson_data: dict, mineral: str | None = None,
    tooltip_cols: list[tuple[str, str]] | None = None,
) -> None:
    """
    `tooltip_cols` : liste ordonnée (colonne, libellé) affichée dans l'info-bulle
    au survol — par défaut juste `[(value_col, legend_name)]` (comportement
    d'origine). La couleur de la choroplèthe reste TOUJOURS pilotée par
    `value_col` seul, quel que soit `tooltip_cols` — ça permet de fondre deux
    métriques liées (ex. dette en % du PIB + montant en milliards de USD) dans
    une seule couche/légende au lieu d'une couche par métrique, avec un ordre
    d'affichage dans l'info-bulle indépendant de celle qui colore la carte.
    """
    tooltip_cols = tooltip_cols or [(value_col, legend_name)]
    fetch_cols = [value_col] + [c for c, _ in tooltip_cols if c != value_col]
    select_cols = ", ".join(fetch_cols)
    if mineral:
        cur.execute(
            f"""
            SELECT DISTINCT ON (pays_code) pays_code, {select_cols}
            FROM {table}
            WHERE matiere_premiere = %s AND {value_col} IS NOT NULL
            ORDER BY pays_code, annee DESC
            """,
            (mineral,),
        )
    else:
        order_col = ORDER_FIELD[table]
        cur.execute(
            f"""
            SELECT DISTINCT ON (pays_code) pays_code, {select_cols}
            FROM {table}
            WHERE {value_col} IS NOT NULL
            ORDER BY pays_code, {order_col} DESC
            """
        )
    rows = cur.fetchall()
    if not rows:
        logger.info("build_map: aucune donnée pour la choroplèthe '%s'", legend_name)
        return

    col_index = {col: i + 1 for i, col in enumerate(fetch_cols)}  # +1 : index 0 = pays_code
    row_by_iso3 = {row[0]: row for row in rows}

    # Copie propre à cette couche : chaque choroplèthe a sa propre valeur par pays,
    # injectée dans les properties pour alimenter l'info-bulle au survol/clic
    # (sans ça, cliquer un pays coloré ne montre rien — voir les marqueurs GDELT
    # empilés au centroïde du pays, qui eux ont un popup, d'où la confusion).
    layer_geojson = copy.deepcopy(geojson_data)
    for feature in layer_geojson["features"]:
        iso3 = feature["properties"].get("iso3")
        row = row_by_iso3.get(iso3)
        for col, _label in tooltip_cols:
            val = row[col_index[col]] if row else None
            feature["properties"][f"tt_{col}"] = f"{float(val):g}" if val is not None else "Pas de donnée"

    df = pd.DataFrame(
        [(row[0], row[col_index[value_col]]) for row in rows], columns=["iso3", "value"]
    ).astype({"value": float})
    choropleth = folium.Choropleth(
        geo_data=layer_geojson,
        name=legend_name,
        data=df,
        columns=["iso3", "value"],
        key_on="feature.properties.iso3",
        fill_color=color_scheme,
        fill_opacity=0.7,
        line_opacity=0.2,
        legend_name=legend_name,
        nan_fill_color="white",
        show=False,
    ).add_to(m)
    # folium ajoute la bannière de légende (échelle de couleurs) comme un
    # enfant du Choropleth indépendant du LayerControl (self.add_child(self.color_scale)
    # dans folium/features.py) — elle resterait donc affichée en permanence sur
    # l'écran principal, peu importe la couche sélectionnée dans le menu
    # OpenStreetMap. On la retire ici : la couche reste sélectionnable dans le
    # menu, seule la bannière visuelle sur la carte est supprimée.
    if choropleth.color_scale is not None:
        choropleth._children.pop(choropleth.color_scale.get_name(), None)
    folium.GeoJsonTooltip(
        fields=["name"] + [f"tt_{col}" for col, _ in tooltip_cols],
        aliases=["Pays :"] + [f"{label} :" for _, label in tooltip_cols],
    ).add_to(choropleth.geojson)
    logger.info("build_map: choroplèthe '%s' -> %d pays", legend_name, len(rows))


class _QaWidget(MacroElement):
    """
    Widget flottant (texte + voix) qui interroge le backend /ask (scheduler.py
    déployé sur Render) et lit la réponse à voix haute.

    Implémenté comme un vrai `MacroElement` Folium (comme `LayerControl`,
    `Choropleth`...) ajouté via `.add_to(m)`, PAS via une manipulation directe de
    `m.get_root().script` : cette dernière approche ajoute le contenu au moment de
    la construction Python, avant que la carte n'ait injecté son propre code de
    création (qui n'arrive qu'au moment du rendu) — le script référençant la
    carte s'exécutait alors AVANT que celle-ci n'existe. Un `MacroElement` ajouté
    à la carte se rend dans le bon ordre, comme n'importe quel autre plugin.

Positionné en bas, centré horizontalement sur la carte. Deux pièges déjà
    rencontrés en construisant ce positionnement :
    1. `<div style="position: fixed">` se recale sur le premier ancêtre avec un
       `transform` CSS à l'intérieur d'une carte Leaflet (ses panneaux internes en
       ont, pour le pan/zoom) plutôt que sur la fenêtre — le widget apparaissait
       centré en bas au lieu du coin bas-droit demandé initialement.
    2. Un `L.Control` Leaflet standard ne permet pas non plus un vrai centrage
       horizontal : ses conteneurs de coin (`.leaflet-bottom.leaflet-left/right`)
       ne font pas la largeur de la carte, donc `left: 50%` à l'intérieur ne
       centre pas sur la carte entière. Le widget est donc attaché directement à
       `map.getContainer()` (pleine largeur/hauteur, `position: relative`) avec
       un `position: absolute; left: 50%; transform: translateX(-50%)` dessus.

    Reconnaissance vocale (Web Speech API `SpeechRecognition`) : disponible sur
    Chrome/Edge, absente sur Firefox et limitée sur Safari — le bouton micro se
    masque automatiquement si l'API n'existe pas dans le navigateur, l'entrée
    texte restant utilisable partout. La synthèse vocale (`speechSynthesis`) a
    une compatibilité plus large.

    Compatibilité mobile : largeur en `min(280px, calc(100vw - 24px))` (une
    largeur fixe déborderait sur un écran de téléphone, souvent 320-390px),
    boutons avec cible tactile ≥36px, police d'entrée à 16px (en-dessous, Safari/
    Chrome iOS zoome automatiquement la page au focus d'un champ texte), et
    `env(safe-area-inset-bottom)` pour ne pas passer sous la barre gestuelle.
    """

    _template = Template(
        """
        {% macro script(this, kwargs) %}
        (function() {
            // Pas de L.Control ici : Leaflet ne propose que les 4 coins pour ses
            // contrôles natifs (leurs conteneurs de coin ne font pas la largeur de
            // la carte, donc un `left: 50%` à l'intérieur ne centre pas sur la
            // carte entière). On attache directement au conteneur de la carte
            // (pleine largeur/hauteur, position relative) avec un positionnement
            // absolute centré horizontalement — évite aussi le bug initial de
            // `position: fixed`, qui se recale sur le premier ancêtre avec un
            // `transform` CSS (les panneaux internes de Leaflet en ont).
            var map = {{ this._parent.get_name() }};
            var container = L.DomUtil.create('div', 'qa-widget-control', map.getContainer());
            container.style.position = 'absolute';
            // env(safe-area-inset-bottom) : évite que la barre gestuelle des
            // téléphones (iOS notamment) ne recouvre le bas du widget.
            container.style.bottom = 'calc(20px + env(safe-area-inset-bottom, 0px))';
            container.style.left = '50%';
            container.style.transform = 'translateX(-50%)';
            container.style.zIndex = 1000;
            container.style.background = 'white';
            container.style.borderRadius = '10px';
            container.style.boxShadow = '0 2px 10px rgba(0,0,0,0.35)';
            container.style.padding = '12px';
            // width: min(...) plutôt qu'une largeur fixe — un téléphone (souvent
            // 320-390px de large) ne peut pas afficher 280px + marges sans
            // déborder ; sur desktop la carte reste à 280px.
            container.style.width = 'min(280px, calc(100vw - 24px))';
            container.style.maxWidth = 'calc(100vw - 24px)';
            container.style.boxSizing = 'border-box';
            container.style.fontFamily = 'sans-serif';
            container.style.fontSize = '13px';
            container.style.color = '#222';
            container.innerHTML =
                '<div style="font-weight:bold; margin-bottom:6px;">🎙️ Ask Joe</div>' +
                '<div style="display:flex; gap:6px; margin-bottom:8px;">' +
                // font-size 16px sur l'input : en-dessous, Safari/Chrome iOS zoome
                // automatiquement la page au focus, ce qui casse la mise en page.
                // min-height 36px sur les boutons : cible tactile confortable au doigt.
                '<input id="qa-input" type="text" placeholder="ex : dette de la France ?" ' +
                'style="flex:1; padding:6px; min-width:0; font-size:16px; box-sizing:border-box;">' +
                '<button id="qa-mic-btn" title="Question vocale" ' +
                'style="cursor:pointer; min-width:36px; min-height:36px; font-size:16px;">🎤</button>' +
                '<button id="qa-send-btn" title="Envoyer" ' +
                'style="cursor:pointer; min-width:36px; min-height:36px; font-size:16px;">➤</button>' +
                '</div>' +
                '<div id="qa-answer" style="max-height:160px; overflow-y:auto; margin-bottom:8px;"></div>' +
                '<div style="display:flex; gap:6px;">' +
                '<button id="qa-copy-btn" style="cursor:pointer; flex:1; min-height:36px; font-size:14px;">📋 Copier</button>' +
                '<button id="qa-clear-btn" style="cursor:pointer; flex:1; min-height:36px; font-size:14px;">🗑️ Effacer</button>' +
                '</div>';
            L.DomEvent.disableClickPropagation(container);
            L.DomEvent.disableScrollPropagation(container);

            const BACKEND_URL = "{{ this.backend_url }}";
            const input = document.getElementById("qa-input");
            const micBtn = document.getElementById("qa-mic-btn");
            const sendBtn = document.getElementById("qa-send-btn");
            const answerDiv = document.getElementById("qa-answer");
            const copyBtn = document.getElementById("qa-copy-btn");
            const clearBtn = document.getElementById("qa-clear-btn");

            function ask(question) {
                question = (question || "").trim();
                if (!question) return;
                answerDiv.textContent = "…";
                fetch(BACKEND_URL + "?q=" + encodeURIComponent(question))
                    .then(function(r) { return r.json(); })
                    .then(function(data) {
                        answerDiv.textContent = data.answer;
                        if ("speechSynthesis" in window) {
                            const utter = new SpeechSynthesisUtterance(data.answer);
                            utter.lang = "fr-FR";
                            window.speechSynthesis.speak(utter);
                        }
                    })
                    .catch(function() {
                        answerDiv.textContent = "Service indisponible (le service Render peut mettre "
                            + "30-60s à se réveiller s'il était endormi — réessayez).";
                    });
            }

            sendBtn.addEventListener("click", function() { ask(input.value); });
            input.addEventListener("keydown", function(e) { if (e.key === "Enter") ask(input.value); });

            copyBtn.addEventListener("click", function() {
                const text = answerDiv.textContent || "";
                if (!text) return;
                if (navigator.clipboard) {
                    navigator.clipboard.writeText(text).then(function() {
                        const original = copyBtn.textContent;
                        copyBtn.textContent = "✅ Copié";
                        setTimeout(function() { copyBtn.textContent = original; }, 1500);
                    });
                }
            });

            clearBtn.addEventListener("click", function() {
                input.value = "";
                answerDiv.textContent = "";
                if ("speechSynthesis" in window) window.speechSynthesis.cancel();
            });

            const SpeechRecognitionImpl = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (SpeechRecognitionImpl) {
                const recognition = new SpeechRecognitionImpl();
                recognition.lang = "fr-FR";
                recognition.interimResults = false;
                micBtn.addEventListener("click", function() {
                    micBtn.textContent = "🔴";
                    recognition.start();
                });
                recognition.addEventListener("result", function(event) {
                    const transcript = event.results[0][0].transcript;
                    input.value = transcript;
                    ask(transcript);
                });
                recognition.addEventListener("end", function() { micBtn.textContent = "🎤"; });
                recognition.addEventListener("error", function() { micBtn.textContent = "🎤"; });
            } else {
                micBtn.style.display = "none";
            }
        })();
        {% endmacro %}
        """
    )

    def __init__(self, backend_url: str):
        super().__init__()
        self._name = "QaWidget"
        self.backend_url = backend_url


class _JoeWidget(MacroElement):
    """
    Panneau flottant à gauche de la carte, toujours ouvert (pas de repli),
    listant les articles analysés par l'agent Joe (clients/joe_agent.py) :
    date/heure, pays, nom de domaine de la source, thème, résumé — via
    l'endpoint /joe-articles de scheduler.py (voir qa/engine.get_joe_articles).
    Chargé au rendu de la carte.

    Inclut un champ de recherche (sous le titre) qui interroge le même
    endpoint avec `?q=...` (voir qa/engine.get_joe_articles(search=...)) —
    recherche sur TOUS les articles analysés en base (thème, résumé, acteurs,
    pays), pas seulement les 30 plus récents chargés par défaut.
    """

    _template = Template(
        """
        {% macro script(this, kwargs) %}
        (function() {
            var map = {{ this._parent.get_name() }};
            var container = L.DomUtil.create('div', 'joe-widget-control', map.getContainer());
            container.style.position = 'absolute';
            container.style.top = '20px';
            container.style.left = '10px';
            container.style.zIndex = 1000;
            container.style.background = 'white';
            container.style.borderRadius = '10px';
            container.style.boxShadow = '0 2px 10px rgba(0,0,0,0.35)';
            container.style.width = 'min(500px, calc(100vw - 24px))';
            container.style.maxWidth = 'calc(100vw - 24px)';
            container.style.boxSizing = 'border-box';
            container.style.fontFamily = 'sans-serif';
            container.style.fontSize = '13px';
            container.style.color = '#222';
            container.style.overflow = 'hidden';
            container.innerHTML =
                '<div style="padding:10px 12px 6px; min-height:36px; font-size:14px; font-weight:bold;">' +
                '🤖 Articles analysés par Joe</div>' +
                '<div style="padding:0 12px 8px;">' +
                '<input id="joe-search" type="text" placeholder="Rechercher (thème, pays, mot-clé...)" ' +
                'style="width:100%; padding:6px; font-size:16px; box-sizing:border-box;">' +
                '</div>' +
                '<div id="joe-panel" style="max-height:85vh; overflow-y:auto; padding:0 12px 12px;">' +
                '<div id="joe-list">Chargement…</div>' +
                '</div>';
            L.DomEvent.disableClickPropagation(container);
            L.DomEvent.disableScrollPropagation(container);

            const BACKEND_URL = "{{ this.backend_url }}";
            const list = document.getElementById("joe-list");
            const searchInput = document.getElementById("joe-search");

            // Fenêtre de "fraîcheur" : une fiche (journal/organisation/agence de
            // presse) dont updated_at tombe dans cette fenêtre vient d'être
            // rafraîchie par un sous-agent de Joe en tâche de fond (voir
            // collectors/_joe_subagent.py) — mise en avant visuellement le
            // temps qu'elle reste "fraîche", pas une durée arbitraire au sens
            // strict : ~2h laisse le temps de la remarquer entre deux passages
            // sur la carte, sans rester allumée jusqu'au prochain cycle (le
            // plus court des 3 sous-agents tourne toutes les 8h).
            const HIGHLIGHT_WINDOW_MS = 2 * 60 * 60 * 1000;

            function renderArticles(articles) {
                if (!articles.length) {
                    list.textContent = "Aucun article trouvé.";
                    return;
                }
                const now = Date.now();
                list.innerHTML = articles.map(function(a) {
                    const d = a.date ? new Date(a.date) : null;
                    const dateStr = d ? d.toLocaleString("fr-FR", {
                        day: "2-digit", month: "2-digit", year: "numeric",
                        hour: "2-digit", minute: "2-digit"
                    }) : "date inconnue";
                    const pays = a.pays || "?";
                    const source = a.source || "?";
                    const theme = a.categorie || "?";
                    const resume = a.resume || "(pas de résumé)";
                    const link = a.url ? '<a href="' + a.url + '" target="_blank" style="font-size:11px;">source</a>' : "";
                    const justRefreshed = a.updated_at && (now - new Date(a.updated_at).getTime()) < HIGHLIGHT_WINDOW_MS;
                    const rowStyle = justRefreshed
                        ? 'padding:8px; margin:2px 0; border-radius:6px; background:#fff8d6; border:1px solid #f0d878;'
                        : 'padding:8px 0; border-bottom:1px solid #eee;';
                    const badge = justRefreshed
                        ? ' <span style="background:#f0c419; color:#5a4600; border-radius:4px; padding:1px 5px; font-size:10px;">🔄 rafraîchi</span>'
                        : '';
                    return '<div style="' + rowStyle + '">' +
                        '<div style="font-size:11px; color:#666;">' + dateStr + ' · ' + pays + ' · ' + source + badge + '</div>' +
                        '<div style="font-size:11px; font-weight:bold; margin-top:2px;">🤖 ' + theme + '</div>' +
                        '<div style="margin-top:2px;">' + resume + '</div>' +
                        '<div style="margin-top:2px;">' + link + '</div>' +
                        '</div>';
                }).join("");
            }

            function loadArticles(searchTerm) {
                list.textContent = "Chargement…";
                var url = BACKEND_URL + "?limit=30";
                if (searchTerm) url += "&q=" + encodeURIComponent(searchTerm);
                fetch(url)
                    .then(function(r) { return r.json(); })
                    .then(function(data) { renderArticles(data.articles || []); })
                    .catch(function() {
                        list.textContent = "Service indisponible (le service Render peut mettre "
                            + "30-60s à se réveiller s'il était endormi — réessayez).";
                    });
            }

            // debounce : évite un appel réseau à chaque frappe, attend une pause
            // de 400ms dans la saisie avant de lancer la recherche.
            let debounceTimer = null;
            searchInput.addEventListener("input", function() {
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(function() {
                    loadArticles(searchInput.value.trim());
                }, 400);
            });

            loadArticles(null);
        })();
        {% endmacro %}
        """
    )

    def __init__(self, backend_url: str):
        super().__init__()
        self._name = "JoeWidget"
        self.backend_url = backend_url


class _ReportsWidget(MacroElement):
    """
    2 boutons flottants en haut à droite de la carte donnant accès aux
    rapports journaliers générés par les 2 sous-agents "rapport" de Joe
    (collectors/collect_report_hotspots.py : points chauds de l'actualité
    mondiale, tous domaines ; collect_report_financial.py : données
    financières internationales et par pays). Chaque rapport est déjà classé
    par thème par Joe (voir clients/joe_agent.generate_themed_report) — affiché
    tel quel, une section par thème, dans une fenêtre modale plutôt qu'un bloc
    de texte plat.
    """

    _template = Template(
        """
        {% macro script(this, kwargs) %}
        (function() {
            var map = {{ this._parent.get_name() }};
            var container = L.DomUtil.create('div', 'reports-widget-control', map.getContainer());
            container.style.position = 'absolute';
            // top droite, décalé sous l'icône du LayerControl (repliée/collapsed,
            // toujours en haut à droite) plutôt que juste en dessous d'elle —
            // "bottom" plaçait les boutons au milieu de l'écran dans certains
            // environnements (probablement la hauteur réelle du conteneur de
            // carte, pas du viewport), alors que "top" (comme le panneau Joe,
            // confirmé fonctionnel) est fiable.
            container.style.top = '70px';
            container.style.right = '10px';
            container.style.zIndex = 1000;
            container.style.display = 'flex';
            container.style.flexDirection = 'column';
            container.style.gap = '6px';
            container.style.fontFamily = 'sans-serif';
            var btnStyle = 'padding:8px 12px; font-size:13px; font-family:sans-serif; border-radius:8px; ' +
                'border:none; box-shadow:0 2px 10px rgba(0,0,0,0.35); background:white; cursor:pointer; ' +
                'text-align:left;';
            container.innerHTML =
                '<button id="report-btn-hotspots" style="' + btnStyle + '">🌍 Rapport hotspots</button>' +
                '<button id="report-btn-financial" style="' + btnStyle + '">💰 Rapport financier</button>';
            L.DomEvent.disableClickPropagation(container);

            var modal = L.DomUtil.create('div', 'reports-modal', map.getContainer());
            modal.style.display = 'none';
            modal.style.position = 'absolute';
            modal.style.top = '0'; modal.style.left = '0'; modal.style.right = '0'; modal.style.bottom = '0';
            modal.style.zIndex = 2000;
            modal.style.background = 'rgba(0,0,0,0.5)';
            modal.innerHTML =
                '<div id="reports-modal-box" style="background:white; width:min(700px, calc(100vw - 40px)); ' +
                'max-height:85vh; overflow-y:auto; margin:5vh auto; border-radius:10px; padding:16px 20px; ' +
                'font-family:sans-serif; font-size:13px; color:#222; position:relative; box-sizing:border-box;">' +
                '<button id="reports-modal-close" style="position:absolute; top:10px; right:12px; border:none; ' +
                'background:none; font-size:20px; cursor:pointer; line-height:1;">✕</button>' +
                '<div id="reports-modal-title" style="font-size:16px; font-weight:bold; margin:0 24px 10px 0;"></div>' +
                '<div id="reports-modal-content"></div>' +
                '</div>';
            L.DomEvent.disableClickPropagation(modal);
            L.DomEvent.disableScrollPropagation(modal);

            const BACKEND_URL = "{{ this.backend_url }}";
            const titleEl = document.getElementById("reports-modal-title");
            const contentEl = document.getElementById("reports-modal-content");

            function renderReport(label, report) {
                titleEl.textContent = label;
                if (!report || !report.themes || !report.themes.length) {
                    contentEl.textContent = "Aucun rapport disponible pour le moment (le sous-agent n'a "
                        + "peut-être pas encore tourné).";
                    return;
                }
                const d = report.created_at ? new Date(report.created_at) : null;
                const dateStr = d ? d.toLocaleString("fr-FR", {
                    day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit"
                }) : "";
                contentEl.innerHTML =
                    (dateStr ? '<div style="font-size:11px; color:#666; margin-bottom:10px;">Généré le ' + dateStr + '</div>' : '') +
                    report.themes.map(function(t) {
                        return '<div style="padding:8px 0; border-bottom:1px solid #eee;">' +
                            '<div style="font-weight:bold; margin-bottom:4px;">🗂️ ' + (t.theme || "?") + '</div>' +
                            '<div>' + (t.summary || "") + '</div>' +
                            '</div>';
                    }).join("");
            }

            function openReport(type, label) {
                modal.style.display = 'block';
                titleEl.textContent = label;
                contentEl.textContent = "Chargement…";
                fetch(BACKEND_URL + "?type=" + encodeURIComponent(type))
                    .then(function(r) { return r.json(); })
                    .then(function(data) { renderReport(label, data.report); })
                    .catch(function() {
                        contentEl.textContent = "Service indisponible (le service Render peut mettre "
                            + "30-60s à se réveiller s'il était endormi — réessayez).";
                    });
            }

            document.getElementById("report-btn-hotspots").addEventListener("click", function() {
                openReport("hotspots", "🌍 Points chauds de l'actualité mondiale");
            });
            document.getElementById("report-btn-financial").addEventListener("click", function() {
                openReport("financial", "💰 Données financières internationales");
            });
            document.getElementById("reports-modal-close").addEventListener("click", function() {
                modal.style.display = 'none';
            });
            modal.addEventListener("click", function(e) {
                if (e.target === modal) modal.style.display = 'none';
            });
        })();
        {% endmacro %}
        """
    )

    def __init__(self, backend_url: str):
        super().__init__()
        self._name = "ReportsWidget"
        self.backend_url = backend_url


def _add_qa_widget(m: folium.Map) -> None:
    _QaWidget(QA_BACKEND_URL).add_to(m)


def _add_joe_widget(m: folium.Map) -> None:
    _JoeWidget(JOE_BACKEND_URL).add_to(m)


def _add_reports_widget(m: folium.Map) -> None:
    _ReportsWidget(REPORTS_BACKEND_URL).add_to(m)


def build_map(output_path: Path = OUTPUT_PATH) -> Path:
    geojson_data = _load_enriched_geojson()
    m = folium.Map(location=[20, 10], zoom_start=2, tiles="OpenStreetMap")

    with get_connection() as conn:
        with conn.cursor() as cur:
            for table, color, label in POINT_LAYERS:
                _add_point_layer(m, cur, table, color, label)

            # Dette publique : une seule couche/légende "Dette publique" (coloration
            # pilotée par le % du PIB, plus comparable entre pays que le montant
            # nominal qui écraserait tout sur les seules grandes économies),
            # l'info-bulle affichant les deux métriques (montant en premier).
            _add_choropleth(
                m, cur, "country_debt", "dette_pct_pib", "Dette publique", "Reds", geojson_data,
                tooltip_cols=[
                    ("dette_montant_milliards_usd", "Dette publique (milliards de USD)"),
                    ("dette_pct_pib", "Dette publique (% du PIB)"),
                ],
            )

            for table, col, legend, scheme in CHOROPLETH_SPECS:
                _add_choropleth(m, cur, table, col, legend, scheme, geojson_data)

    # collapsed=True (icône repliée, dépliée au tap/hover) plutôt qu'ouvert en
    # permanence : sur un écran de téléphone, la liste dépliée de toutes les
    # couches recouvrirait la quasi-totalité de la carte.
    folium.LayerControl(collapsed=True).add_to(m)
    _add_qa_widget(m)
    _add_joe_widget(m)
    _add_reports_widget(m)
    m.save(str(output_path))
    logger.info("build_map: carte générée -> %s", output_path)
    return output_path


if __name__ == "__main__":
    from logging_config import configure_logging

    configure_logging()
    build_map()
