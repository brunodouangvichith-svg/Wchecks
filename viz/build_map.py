"""
Génère la carte interactive `carte_mondiale.html` (Folium/Leaflet, tuiles
OpenStreetMap) à partir des données stockées dans Neon.

Couches par points : conflits énergétiques (rouge), tensions sociales (orange),
activité militaire (violet), trafic maritime (icône bateau, bleu), déclarations
officielles (positionnées sur la capitale/siège de l'institution émettrice).

Couches choroplèthes par pays (une sélectionnable à la fois via LayerControl) :
dette, chômage, inflation, budget défense, production pétrolière/gazière,
production industrielle, minerais stratégiques (une couche par matière).

GeoJSON des frontières : viz/data/world_countries.geojson — dérivé de Natural
Earth (domaine public), redistribué via github.com/johan/world.geo.json.
"""

import copy
import html
import json
import logging
from pathlib import Path

import folium
import pandas as pd
from folium.plugins import MarkerCluster

import config
from clients.neon_client import ORDER_FIELD, get_client
from mapping.country_mapping import COUNTRY_NAME_TO_ISO3

logger = logging.getLogger(__name__)

GEOJSON_PATH = config.BASE_DIR / "viz" / "data" / "world_countries.geojson"
OUTPUT_PATH = config.BASE_DIR / "carte_mondiale.html"

# Backend interrogé par le widget vocal/texte (endpoint /ask de scheduler.py, déployé
# sur Render). La carte étant un fichier statique (GitHub Pages), toute logique de
# question/réponse doit passer par ce service distant — voir qa/engine.py.
QA_BACKEND_URL = "https://globalchecks-scheduler.onrender.com/ask"

POINT_LAYERS = [
    ("energy_conflicts", "red", "Conflits énergétiques"),
    ("social_tensions", "orange", "Tensions sociales"),
    ("military_activity", "purple", "Activité militaire"),
]

# (table, colonne, légende, palette de couleurs branca)
CHOROPLETH_SPECS = [
    ("country_debt", "dette_pct_pib", "Dette publique (% du PIB)", "Reds"),
    ("country_economy", "chomage_pct", "Chômage (%)", "OrRd"),
    ("country_economy", "inflation_pct", "Inflation (%)", "YlOrRd"),
    ("defense_budget", "budget_pct_pib", "Budget défense (% du PIB)", "Purples"),
    ("oil_production", "valeur_barils_jour", "Production pétrolière (milliers de barils/jour)", "Blues"),
    ("gas_production", "valeur_production_gaz", "Production de gaz naturel (milliards de m³)", "Greens"),
    ("country_industry", "production_industrielle_pct_pib", "Production industrielle (% du PIB)", "BuPu"),
]

# Position approximative du siège/de la capitale de chaque institution suivie en RSS.
INSTITUTION_LOCATIONS = {
    "onu": (40.7489, -73.9680),  # siège des Nations Unies, New York
    "us_state_dept": (38.8951, -77.0364),  # Washington D.C.
    "commission_europeenne": (50.8503, 4.3517),  # Bruxelles
}


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
    cur.execute(f"SELECT lat, lon, titre, url, date FROM {table} WHERE lat IS NOT NULL AND lon IS NOT NULL")
    rows = cur.fetchall()
    for lat, lon, titre, url, date in rows:
        popup_html = f"<b>{html.escape(titre or '(sans titre)')}</b><br>{date or ''}"
        if url:
            popup_html += f'<br><a href="{html.escape(url)}" target="_blank">source</a>'
        folium.Marker(
            location=[lat, lon],
            icon=folium.Icon(color=color),
            popup=folium.Popup(popup_html, max_width=300),
        ).add_to(cluster)
    fg.add_to(m)
    logger.info("build_map: %s -> %d point(s)", table, len(rows))


def _add_maritime_layer(m: folium.Map, cur) -> None:
    fg = folium.FeatureGroup(name="Trafic maritime (tankers)", show=False)
    cluster = MarkerCluster().add_to(fg)
    cur.execute(
        "SELECT lat, lon, mmsi, zone_strategique, vitesse, cap FROM maritime_traffic "
        "WHERE lat IS NOT NULL AND lon IS NOT NULL"
    )
    rows = cur.fetchall()
    for lat, lon, mmsi, zone, vitesse, cap in rows:
        popup_html = (
            f"MMSI {html.escape(str(mmsi))}<br>Zone : {html.escape(zone or '?')}"
            f"<br>Vitesse : {vitesse if vitesse is not None else '?'} nœuds"
            f"<br>Cap : {cap if cap is not None else '?'}°"
        )
        folium.Marker(
            location=[lat, lon],
            icon=folium.Icon(color="blue", icon="ship", prefix="fa"),
            popup=folium.Popup(popup_html, max_width=250),
        ).add_to(cluster)
    fg.add_to(m)
    logger.info("build_map: maritime_traffic -> %d point(s)", len(rows))


def _add_statements_layer(m: folium.Map, cur) -> None:
    fg = folium.FeatureGroup(name="Déclarations officielles", show=False)
    cur.execute("SELECT institution, titre, url, date FROM official_statements")
    rows = cur.fetchall()
    n = 0
    for institution, titre, url, date in rows:
        location = INSTITUTION_LOCATIONS.get(institution)
        if location is None:
            continue
        popup_html = f"<b>{html.escape(titre or '(sans titre)')}</b><br>{date or ''}"
        if url:
            popup_html += f'<br><a href="{html.escape(url)}" target="_blank">source</a>'
        folium.CircleMarker(
            location=location, radius=5, color="green", fill=True, fill_opacity=0.6,
            popup=folium.Popup(popup_html, max_width=300),
        ).add_to(fg)
        n += 1
    fg.add_to(m)
    logger.info("build_map: official_statements -> %d point(s)", n)


def _add_choropleth(
    m: folium.Map, cur, table: str, value_col: str, legend_name: str, color_scheme: str,
    geojson_data: dict, mineral: str | None = None,
) -> None:
    if mineral:
        cur.execute(
            f"""
            SELECT DISTINCT ON (pays_code) pays_code, {value_col}
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
            SELECT DISTINCT ON (pays_code) pays_code, {value_col}
            FROM {table}
            WHERE {value_col} IS NOT NULL
            ORDER BY pays_code, {order_col} DESC
            """
        )
    rows = cur.fetchall()
    if not rows:
        logger.info("build_map: aucune donnée pour la choroplèthe '%s'", legend_name)
        return

    values_by_iso3 = {iso3: float(value) for iso3, value in rows}

    # Copie propre à cette couche : chaque choroplèthe a sa propre valeur par pays,
    # injectée dans les properties pour alimenter l'info-bulle au survol/clic
    # (sans ça, cliquer un pays coloré ne montre rien — voir les marqueurs GDELT
    # empilés au centroïde du pays, qui eux ont un popup, d'où la confusion).
    layer_geojson = copy.deepcopy(geojson_data)
    for feature in layer_geojson["features"]:
        iso3 = feature["properties"].get("iso3")
        value = values_by_iso3.get(iso3)
        feature["properties"]["valeur_affichee"] = f"{value:g}" if value is not None else "Pas de donnée"

    df = pd.DataFrame(rows, columns=["iso3", "value"]).astype({"value": float})
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
    folium.GeoJsonTooltip(
        fields=["name", "valeur_affichee"],
        aliases=["Pays :", f"{legend_name} :"],
    ).add_to(choropleth.geojson)
    logger.info("build_map: choroplèthe '%s' -> %d pays", legend_name, len(rows))


def _add_qa_widget(m: folium.Map) -> None:
    """
    Ajoute un widget flottant (texte + voix) qui interroge le backend /ask
    (scheduler.py déployé sur Render) et lit la réponse à voix haute.

    Reconnaissance vocale (Web Speech API `SpeechRecognition`) : disponible sur
    Chrome/Edge, absente sur Firefox et limitée sur Safari — le bouton micro se
    masque automatiquement si l'API n'existe pas dans le navigateur, l'entrée
    texte restant utilisable partout. La synthèse vocale (`speechSynthesis`) a
    une compatibilité plus large.
    """
    widget_html = f"""
    <div id="qa-widget" style="position: fixed; bottom: 20px; right: 20px; z-index: 9999;
         background: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.35);
         padding: 12px; width: 300px; font-family: sans-serif; font-size: 13px; color: #222;">
      <div style="font-weight: bold; margin-bottom: 6px;">🎙️ Poser une question sur un pays</div>
      <div style="display: flex; gap: 6px; margin-bottom: 8px;">
        <input id="qa-input" type="text" placeholder="ex : dette de la France ?"
               style="flex:1; padding:4px; min-width:0;">
        <button id="qa-mic-btn" title="Question vocale" style="cursor:pointer;">🎤</button>
        <button id="qa-send-btn" title="Envoyer" style="cursor:pointer;">➤</button>
      </div>
      <div id="qa-answer" style="max-height:160px; overflow-y:auto;"></div>
    </div>
    <script>
    (function() {{
        const BACKEND_URL = "{QA_BACKEND_URL}";
        const input = document.getElementById("qa-input");
        const micBtn = document.getElementById("qa-mic-btn");
        const sendBtn = document.getElementById("qa-send-btn");
        const answerDiv = document.getElementById("qa-answer");

        function ask(question) {{
            question = (question || "").trim();
            if (!question) return;
            answerDiv.textContent = "…";
            fetch(BACKEND_URL + "?q=" + encodeURIComponent(question))
                .then(function(r) {{ return r.json(); }})
                .then(function(data) {{
                    answerDiv.textContent = data.answer;
                    if ("speechSynthesis" in window) {{
                        const utter = new SpeechSynthesisUtterance(data.answer);
                        utter.lang = "fr-FR";
                        window.speechSynthesis.speak(utter);
                    }}
                }})
                .catch(function() {{
                    answerDiv.textContent = "Service indisponible (le service Render peut mettre "
                        + "30-60s à se réveiller s'il était endormi — réessayez).";
                }});
        }}

        sendBtn.addEventListener("click", function() {{ ask(input.value); }});
        input.addEventListener("keydown", function(e) {{ if (e.key === "Enter") ask(input.value); }});

        const SpeechRecognitionImpl = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (SpeechRecognitionImpl) {{
            const recognition = new SpeechRecognitionImpl();
            recognition.lang = "fr-FR";
            recognition.interimResults = false;
            micBtn.addEventListener("click", function() {{
                micBtn.textContent = "🔴";
                recognition.start();
            }});
            recognition.addEventListener("result", function(event) {{
                const transcript = event.results[0][0].transcript;
                input.value = transcript;
                ask(transcript);
            }});
            recognition.addEventListener("end", function() {{ micBtn.textContent = "🎤"; }});
            recognition.addEventListener("error", function() {{ micBtn.textContent = "🎤"; }});
        }} else {{
            micBtn.style.display = "none";
        }}
    }})();
    </script>
    """
    m.get_root().html.add_child(folium.Element(widget_html))


def build_map(output_path: Path = OUTPUT_PATH) -> Path:
    conn = get_client()
    geojson_data = _load_enriched_geojson()
    m = folium.Map(location=[20, 10], zoom_start=2, tiles="OpenStreetMap")

    with conn.cursor() as cur:
        for table, color, label in POINT_LAYERS:
            _add_point_layer(m, cur, table, color, label)
        _add_maritime_layer(m, cur)
        _add_statements_layer(m, cur)

        for table, col, legend, scheme in CHOROPLETH_SPECS:
            _add_choropleth(m, cur, table, col, legend, scheme, geojson_data)

        for mineral in config.STRATEGIC_MINERALS:
            _add_choropleth(
                m, cur, "minerals_production", "volume_tonnes",
                f"Production de {mineral} (tonnes)", "YlOrBr", geojson_data, mineral=mineral,
            )

    folium.LayerControl(collapsed=False).add_to(m)
    _add_qa_widget(m)
    m.save(str(output_path))
    logger.info("build_map: carte générée -> %s", output_path)
    return output_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    build_map()
