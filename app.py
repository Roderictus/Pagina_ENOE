# source /home/anaphwto/virtualenv/mexico_flask/3.6/bin/activate && cd /home/anaphwto/mexico_flask

# app.py
# ----------------------------------------
# Panel ENOE: estadísticas nacionales y estatales para México
# ----------------------------------------

from flask import Flask, render_template, jsonify, redirect, url_for, request
import pandas as pd
import json
import os
import unicodedata
import markdown
try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None
from datetime import datetime
import os

app = Flask(__name__)

# ----------------------------
# Rutas a los archivos de datos
# ----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

#Ruta a la carpeta de blog
PATH_BLOG = os.path.join(BASE_DIR, "content", "blog")

#################BASES DE DATOS#################
PATH_NACIONAL = os.path.join(BASE_DIR, "database", "20251205_Nacional_deflactado.csv")
PATH_ESTADOS = os.path.join(BASE_DIR, "database", "20251205_Estados_deflactado.csv")
#################GEOJSON#################
PATH_GEOJSON = os.path.join(BASE_DIR, "static", "data", "mexico_estados.json")

#################VARIABLE PARA MAPA ESTATAL#################
MAP_VARIABLE = "def_masa_salarial_total"
MAP_VARIABLE_LABEL = "Masa salarial total deflactada"
COLORS_QUINTILES = ["#ffedc0", "#fcd571", "#f4b04d", "#e7812a", "#c84c1b"]



# --- UTILIDAD: leer Markdown con frontmatter YAML (sin dependencia externa) ---
def load_markdown_post(file_obj):
    """
    Devuelve un dict con metadatos (YAML frontmatter) y `content`.
    Formato esperado:
    ---
    title: ...
    date: ...
    ---
    markdown...
    """
    raw = file_obj.read()
    if not raw:
        return {"content": ""}

    text = raw.lstrip("\ufeff")
    if not text.startswith("---"):
        return {"content": text}

    if yaml is None:
        raise RuntimeError(
            "Falta PyYAML para leer frontmatter. Instala dependencias desde requirements.txt."
        )

    parts = text.split("\n---", 1)
    if len(parts) < 2:
        return {"content": text}

    header = parts[0]
    rest = parts[1]
    if rest.startswith("\n"):
        rest = rest[1:]

    meta_text = header[len("---") :].lstrip("\n")
    try:
        meta = yaml.safe_load(meta_text) or {}
    except Exception:
        meta = {}

    if not isinstance(meta, dict):
        meta = {}

    meta["content"] = rest
    return meta

# --- NUEVA FUNCIÓN PARA LEER EL BLOG ---
def get_blog_posts():
    """Lee todos los archivos .md, extrae metadatos y los ordena por fecha."""
    posts = []
    if not os.path.exists(PATH_BLOG):
        return posts

    for filename in os.listdir(PATH_BLOG):
        if filename.endswith(".md"):
            filepath = os.path.join(PATH_BLOG, filename)
            with open(filepath, "r", encoding="utf-8") as file:
                post = load_markdown_post(file)
                
                # Creamos el diccionario para la tarjeta
                posts.append({
                    "slug": filename[:-3], # Quita el ".md" para usarlo en la URL
                    "title": post.get("title", "Sin título"),
                    "date": post.get("date", "1970-01-01"),
                    "summary": post.get("summary", ""),
                    "thumbnail": post.get("thumbnail", "https://via.placeholder.com/400x200?text=Sin+Imagen"),
                    "content": post.get("content", "")
                })
    
    # Ordenar por fecha de más reciente a más antiguo
    posts.sort(key=lambda x: x["date"], reverse=True)
    return posts

# ----------------------------
# Carga de datos en memoria
# ----------------------------
# Load National Data (Keep existing logic if file exists, otherwise handle gracefully)
try:
    nacional_df = pd.read_csv(PATH_NACIONAL, encoding="utf-8")
    nacional_df = nacional_df.sort_values(["year", "quarter"])
except FileNotFoundError:
    print(f"Warning: {PATH_NACIONAL} not found.")
    nacional_df = pd.DataFrame()

# Load State Data
estados_df = pd.read_csv(PATH_ESTADOS, encoding="utf-8")

# Paleta para cuantiles en mapas (Yellow to Red/Brown)
COLOR_SCALE = ["#ffedc0", "#fcd571", "#f4b04d", "#e7812a", "#c84c1b"]
QUANTILES = [0, 0.2, 0.4, 0.6, 0.8, 1.0]

# Normalizamos nombres de entidades
NOMBRE_ENTIDAD_LIMPIO = {
    "Ciudad de México": "Ciudad de México", "México": "México", "Michoacán": "Michoacán",
    "Nuevo León": "Nuevo León", "Querétaro": "Querétaro", "San Luis Potosí": "San Luis Potosí",
    "Yucatán": "Yucatán", "Ciudad de M?xico": "Ciudad de México", "M?xico": "México",
    "Michoac?n": "Michoacán", "Nuevo Le?n": "Nuevo León", "Quer?taro": "Querétaro",
    "San Luis Potos?": "San Luis Potosí", "Yucat?n": "Yucatán",
}
estados_df["ent_nombre"] = estados_df["ent_nombre"].replace(NOMBRE_ENTIDAD_LIMPIO)
estados_df = estados_df.sort_values(["year", "quarter"])

# Load GeoJSON
with open(PATH_GEOJSON, encoding="utf-8") as f:
    mexico_geojson = json.load(f)

# Helper for State Matching
STATE_NAME_MAPPING = {
    'Aguascalientes': 'Aguascalientes', 'Baja California': 'Baja California',
    'Baja California Sur': 'Baja California Sur', 'Campeche': 'Campeche',
    'Chiapas': 'Chiapas', 'Chihuahua': 'Chihuahua', 'Coahuila de Zaragoza': 'Coahuila',
    'Colima': 'Colima', 'Distrito Federal': 'Ciudad de México', 'Durango': 'Durango',
    'Guanajuato': 'Guanajuato', 'Guerrero': 'Guerrero', 'Hidalgo': 'Hidalgo',
    'Jalisco': 'Jalisco', 'Mexico': 'México', 'Michoacan de Ocampo': 'Michoacán',
    'Morelos': 'Morelos', 'Nayarit': 'Nayarit', 'Nuevo Leon': 'Nuevo León',
    'Oaxaca': 'Oaxaca', 'Puebla': 'Puebla', 'Queretaro de Arteaga': 'Querétaro',
    'Quintana Roo': 'Quintana Roo', 'San Luis Potosi': 'San Luis Potosí',
    'Sinaloa': 'Sinaloa', 'Sonora': 'Sonora', 'Tabasco': 'Tabasco',
    'Tamaulipas': 'Tamaulipas', 'Tlaxcala': 'Tlaxcala',
    'Veracruz de Ignacio de la Llave': 'Veracruz', 'Yucatan': 'Yucatán',
    'Zacatecas': 'Zacatecas'
}

ent_code_por_nombre = estados_df.groupby("ent_nombre")["ent_code"].first().to_dict()
ent_nombre_por_code = estados_df.groupby("ent_code")["ent_nombre"].first().to_dict()

def _normalize(nombre: str) -> str:
    if not isinstance(nombre, str): return ""
    nfkd = unicodedata.normalize("NFKD", nombre)
    sin_acentos = "".join(ch for ch in nfkd if ch.isalnum() or ch.isspace())
    return " ".join(sin_acentos.lower().split())

ent_code_por_nombre_norm = {_normalize(n): c for n, c in ent_code_por_nombre.items()}

# Inject IDs into GeoJSON strictly for matching
for feature in mexico_geojson["features"]:
    shape_name = feature["properties"].get("shapeName")
    ent_nombre = STATE_NAME_MAPPING.get(shape_name)
    ent_code = ent_code_por_nombre.get(ent_nombre)
    
    if ent_code is None:
        ent_code = ent_code_por_nombre_norm.get(_normalize(ent_nombre or shape_name))
    
    # Store standard properties
    feature["properties"]["ent_nombre"] = ent_nombre
    feature["properties"]["ent_code"] = int(ent_code) if ent_code is not None else None


# ------------------------------------------------
# LOGIC FOR MAP VARIABLES AND SLIDER
# ------------------------------------------------

# The 4 requested variables
TARGET_VARS = [
    "def_ing_prim_comp_hombres",
    "def_ing_prim_comp_mujeres",
    "def_ing_secundaria_hombres",
    "def_ing_secundaria_mujeres"
]

def prepare_map_data():
    """
    Organizes data for the frontend:
    1. A list of all periods (Year TQ)
    2. A dictionary: data[period_index][ent_code] = { var1: val, var2: val ... }
    3. Global min/max for scaling consistency.
    """
    
    # Ensure variables exist (fill NaN with 0 or drop)
    df = estados_df.copy()
    for var in TARGET_VARS:
        if var not in df.columns:
            df[var] = 0 # Fallback if column missing
            
    # Create a period label "2005 T1"
    df["period_label"] = df["year"].astype(int).astype(str) + " T" + df["quarter"].astype(int).astype(str)
    
    # Get unique periods sorted
    periods = df["period_label"].unique().tolist()
    
    # Create the data lookup structure
    # Structure: { "2005 T1": { "1": {vars...}, "2": {vars...} } }
    map_data = {}
    
    for period in periods:
        period_subset = df[df["period_label"] == period]
        period_data = {}
        for _, row in period_subset.iterrows():
            ent_code = str(int(row["ent_code"]))
            vals = {}
            for var in TARGET_VARS:
                vals[var] = row[var]
            period_data[ent_code] = vals
        map_data[period] = period_data

    # Calculate Global Max for Income Variables to share the scale
    # This allows comparing Men vs Women on the same color ramp.
    global_values = []
    for var in TARGET_VARS:
        global_values.extend(df[var].dropna().tolist())
    
    # Simple quantiles on the global dataset for breaks
    import numpy as np
    g_vals = np.array(global_values)
    g_vals = g_vals[g_vals > 0] # Ignore zeros for quantile calc if desired
    
    breaks = []
    if len(g_vals) > 0:
        thresholds = [np.percentile(g_vals, q * 100) for q in QUANTILES]
        # Build breaks object matching your original format
        for i in range(len(COLOR_SCALE)):
            low = thresholds[i]
            high = thresholds[i + 1]
            breaks.append({
                "min": float(low),
                "max": float(high),
                "color": COLOR_SCALE[i],
                "label": f"${low:,.0f} - ${high:,.0f}"
            })

    return periods, map_data, breaks

# Pre-calculate this once (or cache it)
GLOBAL_PERIODS, GLOBAL_MAP_DATA, GLOBAL_BREAKS = prepare_map_data()

MAP_VARIABLES_CONFIG = [
    {
        "id": "def_ing_prim_comp_hombres",
        "label": "Ingreso Real - Primaria Completa (Hombres)",
        "property": "def_ing_prim_comp_hombres",
        "legend_title": "Ingreso Real (Hombres - Prim. Comp.)"
    },
    {
        "id": "def_ing_prim_comp_mujeres",
        "label": "Ingreso Real - Primaria Completa (Mujeres)",
        "property": "def_ing_prim_comp_mujeres",
        "legend_title": "Ingreso Real (Mujeres - Prim. Comp.)"
    },
    {
        "id": "def_ing_secundaria_hombres",
        "label": "Ingreso Real - Secundaria (Hombres)",
        "property": "def_ing_secundaria_hombres",
        "legend_title": "Ingreso Real (Hombres - Sec.)"
    },
    {
        "id": "def_ing_secundaria_mujeres",
        "label": "Ingreso Real - Secundaria (Mujeres)",
        "property": "def_ing_secundaria_mujeres",
        "legend_title": "Ingreso Real (Mujeres - Sec.)"
    }
]

# ------------------------------------------------
# RUTAS
# ------------------------------------------------
@app.route("/")
def index():
    # Obtenemos los últimos 3 artículos para la portada
    all_posts = get_blog_posts()
    recent_posts = all_posts[:3] 
    return render_template("index.html", posts=recent_posts)

# --- NUEVA RUTA PARA LEER UN ARTÍCULO ---
@app.route("/blog/<slug>")
def blog_post(slug):
    filepath = os.path.join(PATH_BLOG, f"{slug}.md")
    if not os.path.exists(filepath):
        return "Artículo no encontrado", 404

    with open(filepath, "r", encoding="utf-8") as file:
        post = load_markdown_post(file)
        
        # Convertimos el contenido Markdown a HTML (habilitando soporte para tablas)
        html_content = markdown.markdown(post.get("content", ""), extensions=['tables', 'fenced_code'])

    return render_template(
        "blog_post.html", 
        title=post.get("title"), 
        date=post.get("date"), 
        thumbnail=post.get("thumbnail"),
        content=html_content
    )


@app.route("/mapa-estados")
def mapa_estados():
    """Mapa estatal con Slider Temporal."""
    return render_template(
        "estadisticas_estatales.html",
        periods=GLOBAL_PERIODS,
        map_data=GLOBAL_MAP_DATA,
        global_breaks=GLOBAL_BREAKS,
        map_variables=MAP_VARIABLES_CONFIG,
        default_var_id=MAP_VARIABLES_CONFIG[0]["id"]
    )

@app.route("/estatales")
def estatales():
    """Backwards compatibility redirect."""
    return redirect(url_for("mapa_estados"))

@app.route("/estados-panel")
def estados_panel():
    """Panel de datos por estado."""
    return render_template(
        "estadisticas_estados_panel.html",
        map_variables=MAP_VARIABLES_CONFIG,
        default_var_id=MAP_VARIABLES_CONFIG[0]["id"]
    )

@app.route("/api/estados/geojson")
def api_estados_geojson():
    return jsonify(mexico_geojson)

@app.route("/api/estados/panel-data")
def api_estados_panel_data():
    """API endpoint to get panel data for selected states and variable."""
    variable = request.args.get('variable')
    state_codes = request.args.getlist('states')  # Can pass multiple states
    
    if not variable or variable not in TARGET_VARS:
        return jsonify({"error": "Invalid variable"}), 400
    
    if not state_codes:
        return jsonify({"error": "No states selected"}), 400
    
    # Convert state codes to integers
    try:
        state_codes_int = [int(code) for code in state_codes]
    except ValueError:
        return jsonify({"error": "Invalid state codes"}), 400
    
    # Filter data for selected states
    df = estados_df[estados_df["ent_code"].isin(state_codes_int)].copy()
    df = df.sort_values(["year", "quarter", "ent_code"])
    
    # Create period labels
    df["period_label"] = df["year"].astype(int).astype(str) + " T" + df["quarter"].astype(int).astype(str)
    
    # Get unique periods from all available data (not just filtered) to ensure consistency
    all_periods_df = estados_df.copy()
    all_periods_df["period_label"] = all_periods_df["year"].astype(int).astype(str) + " T" + all_periods_df["quarter"].astype(int).astype(str)
    periods = sorted(all_periods_df["period_label"].unique().tolist())
    
    # Build response: data organized by state
    response_data = {
        "variable": variable,
        "variable_label": next((v["label"] for v in MAP_VARIABLES_CONFIG if v["id"] == variable), variable),
        "periods": periods,
        "states": []
    }
    
    for ent_code in state_codes_int:
        state_df = df[df["ent_code"] == ent_code].copy()
        state_df = state_df.sort_values(["year", "quarter"])
        
        if state_df.empty:
            continue
        
        ent_nombre = state_df["ent_nombre"].iloc[0]
        
        # Get values for this variable, ensuring alignment with periods
        values = []
        for period in periods:
            period_row = state_df[state_df["period_label"] == period]
            if not period_row.empty:
                val = period_row[variable].iloc[0]
                values.append(float(val) if pd.notna(val) else None)
            else:
                values.append(None)
        
        response_data["states"].append({
            "ent_code": int(ent_code),
            "ent_nombre": ent_nombre,
            "data": values
        })
    
    return jsonify(response_data)

@app.route("/api/estados/top-bottom-states")
def api_estados_top_bottom():
    """API endpoint to get top 3 and bottom 3 states for a variable in the last period."""
    variable = request.args.get('variable')
    
    if not variable or variable not in TARGET_VARS:
        return jsonify({"error": "Invalid variable"}), 400
    
    # Get last period
    last_period = GLOBAL_PERIODS[-1]
    
    # Get data for last period
    period_data = GLOBAL_MAP_DATA.get(last_period, {})
    
    # Collect all states with their values
    state_values = []
    for ent_code_str, state_data in period_data.items():
        value = state_data.get(variable)
        if value is not None and pd.notna(value):
            ent_code = int(ent_code_str)
            ent_nombre = ent_nombre_por_code.get(ent_code, f"Estado {ent_code}")
            state_values.append({
                "ent_code": ent_code,
                "ent_nombre": ent_nombre,
                "value": float(value)
            })
    
    # Sort by value
    state_values.sort(key=lambda x: x["value"], reverse=True)
    
    # Get top 3 and bottom 3
    top_3 = state_values[:3]
    bottom_3 = state_values[-3:] if len(state_values) >= 3 else state_values
    
    return jsonify({
        "variable": variable,
        "period": last_period,
        "top_3": top_3,
        "bottom_3": bottom_3
    })

    
@app.route("/nacionales")
def nacionales():
    """Página nacional con pestañas temáticas y selección múltiple."""
    df = nacional_df.copy().sort_values(["year", "quarter"])

    labels = [f"{int(y)} T{int(q)}" for y, q in zip(df["year"], df["quarter"])]

    color_scale = [
        "#2563eb", "#16a34a", "#f97316", "#0ea5e9", "#9333ea", "#22c55e",
        "#f59e0b", "#6366f1", "#ef4444", "#14b8a6", "#a855f7", "#0f766e",
        "#f43f5e", "#84cc16", "#ea580c", "#0891b2", "#7c3aed", "#64748b",
        "#d97706"
    ]

    def serie(col_name, decimals=2):
        serie = df[col_name].round(decimals)
        return serie.where(serie.notna(), None).tolist()

    def build_group(group_id, title, variables, selection="multi", description=""):
        built_vars = []
        for idx, item in enumerate(variables):
            col, label, decimals, checked = item
            built_vars.append({
                "id": col,
                "label": label,
                "color": color_scale[idx % len(color_scale)],
                "decimals": decimals,
                "checked": checked,
                "data": serie(col, decimals),
            })
        return {
            "id": group_id,
            "title": title,
            "description": description,
            "selection": selection,
            "variables": built_vars,
        }

    grupos = [
        build_group(
            "poblacion",
            "Población",
            [
                ("pob_total", "Población total", 0, True),
                ("pea_total", "Población económicamente activa", 0, True),
                ("ocupada_total", "Población ocupada", 0, True),
                ("desocupada_total", "Población desocupada", 0, False),
                ("pob_15ymas_total", "Población de 15 años y más", 0, False),
                ("pob_15ymas_hombres", "15 años y más - hombres", 0, False),
                ("pob_15ymas_mujeres", "15 años y más - mujeres", 0, False),
                ("formal_total", "Formal - total", 0, False),
                ("formal_hombres", "Formal - hombres", 0, False),
                ("formal_mujeres", "Formal - mujeres", 0, False),
                ("informal_total", "Informal - total", 0, False),
                ("informal_hombres", "Informal - hombres", 0, False),
                ("informal_mujeres", "Informal - mujeres", 0, False),
                ("no_remunerados_total", "No remunerados - total", 0, False),
                ("no_remunerados_hombres", "No remunerados - hombres", 0, False),
                ("no_remunerados_mujeres", "No remunerados - mujeres", 0, False),
                ("pob_con_salud", "Población con acceso a salud", 0, False),
                ("pob_sin_salud", "Población sin acceso a salud", 0, False),
            ],
            selection="multi",
            description="Niveles de población y condición de ocupación/formalidad.",
        ),
        build_group(
            "porcentajes",
            "Porcentajes",
            [
                ("pct_15ymas_sobre_total", "% población 15+ sobre total", 2, True),
                ("pct_formal_total_15ymas", "% formal total (15+)", 2, True),
                ("pct_formal_hombres_15ymas", "% formal hombres (15+)", 2, False),
                ("pct_formal_mujeres_15ymas", "% formal mujeres (15+)", 2, False),
                ("pct_informal_total_15ymas", "% informal total (15+)", 2, False),
                ("pct_informal_hombres_15ymas", "% informal hombres (15+)", 2, False),
                ("pct_informal_mujeres_15ymas", "% informal mujeres (15+)", 2, False),
                ("pct_no_remunerados_total_15ymas", "% no remunerados total (15+)", 2, False),
                ("pct_no_remunerados_hombres_15ymas", "% no remunerados hombres (15+)", 2, False),
                ("pct_no_remunerados_mujeres_15ymas", "% no remunerados mujeres (15+)", 2, False),
                ("pct_con_salud", "% con acceso a salud", 2, False),
            ],
            selection="multi",
            description="Indicadores porcentuales sobre población de 15 años y más.",
        ),
        build_group(
            "corriente",
            "Variables monetarias (valores corrientes)",
            [
                ("masa_salarial_total", "Masa salarial total", 0, True),
                ("masa_salarial_hombres", "Masa salarial hombres", 0, False),
                ("masa_salarial_mujeres", "Masa salarial mujeres", 0, False),
                ("ing_hora_hombres", "Ingreso por hora - hombres", 2, False),
                ("ing_hora_mujeres", "Ingreso por hora - mujeres", 2, False),
                ("ing_mensual_hombres", "Ingreso mensual - hombres", 2, True),
                ("ing_mensual_mujeres", "Ingreso mensual - mujeres", 2, False),
            ],
            selection="multi",
            description="Montos corrientes de ingreso y masa salarial.",
        ),
        build_group(
            "real",
            "Variables monetarias (valores reales)",
            [
                ("def_masa_salarial_total", "Masa salarial real total", 0, True),
                ("def_masa_salarial_hombres", "Masa salarial real hombres", 0, False),
                ("def_masa_salarial_mujeres", "Masa salarial real mujeres", 0, False),
                ("def_ing_hora_hombres", "Ingreso real por hora - hombres", 2, False),
                ("def_ing_hora_mujeres", "Ingreso real por hora - mujeres", 2, False),
                ("def_ing_mensual_hombres", "Ingreso real mensual - hombres", 2, True),
                ("def_ing_mensual_mujeres", "Ingreso real mensual - mujeres", 2, False),
                ("def_ing_prim_inc_hombres", "Ing. real primaria incompleta - hombres", 2, False),
                ("def_ing_prim_inc_mujeres", "Ing. real primaria incompleta - mujeres", 2, False),
                ("def_ing_prim_comp_hombres", "Ing. real primaria completa - hombres", 2, False),
                ("def_ing_prim_comp_mujeres", "Ing. real primaria completa - mujeres", 2, False),
                ("def_ing_secundaria_hombres", "Ing. real secundaria - hombres", 2, False),
                ("def_ing_secundaria_mujeres", "Ing. real secundaria - mujeres", 2, False),
                ("def_ing_sup_y_mas_hombres", "Ing. real superior y más - hombres", 2, False),
                ("def_ing_sup_y_mas_mujeres", "Ing. real superior y más - mujeres", 2, False),
                ("def_ing_hora_primaria_hombres", "Ing. real por hora primaria - hombres", 2, False),
                ("def_ing_hora_primaria_mujeres", "Ing. real por hora primaria - mujeres", 2, False),
                ("def_ing_hora_secundaria_hombres", "Ing. real por hora secundaria - hombres", 2, False),
                ("def_ing_hora_secundaria_mujeres", "Ing. real por hora secundaria - mujeres", 2, False),
                ("def_ing_hora_superior_hombres", "Ing. real por hora superior - hombres", 2, False),
                ("def_ing_hora_superior_mujeres", "Ing. real por hora superior - mujeres", 2, False),
            ],
            selection="multi",
            description="Series deflactadas (precios constantes).",
        ),
        build_group(
            "otras",
            "Otras variables",
            [
                ("horas_sem_hombres", "Horas semanales trabajadas - hombres", 2, True),
                ("horas_sem_mujeres", "Horas semanales trabajadas - mujeres", 2, False),
                ("anios_esc_total", "Años de escolaridad - total", 2, False),
                ("anios_esc_hombres", "Años de escolaridad - hombres", 2, False),
                ("anios_esc_mujeres", "Años de escolaridad - mujeres", 2, False),
                ("deflactor", "Deflactor", 4, False),
            ],
            selection="single",
            description="Variables heterogéneas (una a la vez para leer mejor el eje).",
        ),
    ]

    return render_template(
        "estadisticas_nacionales.html",
        labels=labels,
        grupos=grupos,
    )


@app.route("/api/estados/<int:ent_code>/series")
def api_estado_series(ent_code):
    df = estados_df[estados_df["ent_code"] == ent_code].copy()
    if df.empty:
        return jsonify({"error": "Estado no encontrado"}), 404

    df = df.sort_values(["year", "quarter"])
    # Create periodo column from year and quarter
    df["periodo"] = df["year"].astype(int).astype(str) + " T" + df["quarter"].astype(int).astype(str)
    labels = df["periodo"].tolist()
    df["tasa_desocupacion"] = (
        df["desocupada_total"] / df["pea_total"] * 100
    )

    ent_nombre = df["ent_nombre"].iloc[0]

    data = {
        "ent_code": int(ent_code),
        "ent_nombre": ent_nombre,
        "labels": labels,
        "series": {
            "ocupada_total": df["ocupada_total"].round(0).astype(int).tolist(),
            "desocupada_total": df["desocupada_total"].round(0).astype(int).tolist(),
            "ing_prom_mes_total": df["ing_prom_mes_total"].round(2).tolist(),
            "ing_prom_hora_total": df["ing_prom_hora_total"].round(2).tolist(),
            "tasa_desocupacion": df["tasa_desocupacion"].round(2).tolist(),
        }
    }
    return jsonify(data)

if __name__ == "__main__":
    app.run(debug=True)
