# app.py
# ----------------------------------------
# Panel ENOE: estadísticas nacionales y estatales para México
# ----------------------------------------

from flask import Flask, render_template, jsonify, redirect, url_for
import pandas as pd
import json
import os
import unicodedata

app = Flask(__name__)

# ----------------------------
# Rutas a los archivos de datos
# ----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

#################BASES DE DATOS#################
#PATH_NACIONAL = os.path.join(BASE_DIR, "database", "Nacional_deflactado.csv")
PATH_NACIONAL = os.path.join(BASE_DIR, "database", "20251205_Nacional_deflactado.csv")
PATH_ESTADOS = os.path.join(BASE_DIR, "database", "20251031_Estados.csv")

#################GEOJSON#################
PATH_GEOJSON = os.path.join(BASE_DIR, "static", "data", "mexico_estados.json")

# ----------------------------
# Carga de datos en memoria
# ----------------------------

nacional_df = pd.read_csv(PATH_NACIONAL, encoding="utf-8")
estados_df = pd.read_csv(PATH_ESTADOS, encoding="utf-8")

# Normalizamos nombres de entidades con acentos correctos
NOMBRE_ENTIDAD_LIMPIO = {
    "Ciudad de México": "Ciudad de México",
    "México": "México",
    "Michoacán": "Michoacán",
    "Nuevo León": "Nuevo León",
    "Querétaro": "Querétaro",
    "San Luis Potosí": "San Luis Potosí",
    "Yucatán": "Yucatán",
    # Entradas con caracteres mal codificados que pueden llegar en el CSV
    "Ciudad de M?xico": "Ciudad de México",
    "M?xico": "México",
    "Michoac?n": "Michoacán",
    "Nuevo Le?n": "Nuevo León",
    "Quer?taro": "Querétaro",
    "San Luis Potos?": "San Luis Potosí",
    "Yucat?n": "Yucatán",
}
estados_df["ent_nombre"] = estados_df["ent_nombre"].replace(NOMBRE_ENTIDAD_LIMPIO)

# Orden temporal por año y trimestre
nacional_df = nacional_df.sort_values(["year", "quarter"])
estados_df = estados_df.sort_values(["year", "quarter"])

# Cargamos el GeoJSON de estados
with open(PATH_GEOJSON, encoding="utf-8") as f:
    mexico_geojson = json.load(f)

# ----------------------------
# Mapeo entre nombres del GeoJSON y nombres de la base estatal
# ----------------------------
STATE_NAME_MAPPING = {
    'Aguascalientes': 'Aguascalientes',
    'Baja California': 'Baja California',
    'Baja California Sur': 'Baja California Sur',
    'Campeche': 'Campeche',
    'Chiapas': 'Chiapas',
    'Chihuahua': 'Chihuahua',
    'Coahuila de Zaragoza': 'Coahuila',
    'Colima': 'Colima',
    'Distrito Federal': 'Ciudad de México',
    'Durango': 'Durango',
    'Guanajuato': 'Guanajuato',
    'Guerrero': 'Guerrero',
    'Hidalgo': 'Hidalgo',
    'Jalisco': 'Jalisco',
    'Mexico': 'México',
    'Michoacan de Ocampo': 'Michoacán',
    'Morelos': 'Morelos',
    'Nayarit': 'Nayarit',
    'Nuevo Leon': 'Nuevo León',
    'Oaxaca': 'Oaxaca',
    'Puebla': 'Puebla',
    'Queretaro de Arteaga': 'Querétaro',
    'Quintana Roo': 'Quintana Roo',
    'San Luis Potosi': 'San Luis Potosí',
    'Sinaloa': 'Sinaloa',
    'Sonora': 'Sonora',
    'Tabasco': 'Tabasco',
    'Tamaulipas': 'Tamaulipas',
    'Tlaxcala': 'Tlaxcala',
    'Veracruz de Ignacio de la Llave': 'Veracruz',
    'Yucatan': 'Yucatán',
    'Zacatecas': 'Zacatecas'
}


# Diccionarios auxiliares
ent_code_por_nombre = estados_df.groupby("ent_nombre")["ent_code"].first().to_dict()
ent_nombre_por_code = estados_df.groupby("ent_code")["ent_nombre"].first().to_dict()


def _normalize(nombre: str) -> str:
    """Devuelve una versión sin acentos/espacios extra para emparejar nombres."""
    if not isinstance(nombre, str):
        return ""
    nfkd = unicodedata.normalize("NFKD", nombre)
    sin_acentos = "".join(ch for ch in nfkd if ch.isalnum() or ch.isspace())
    return " ".join(sin_acentos.lower().split())


ent_code_por_nombre_norm = {
    _normalize(nombre): code for nombre, code in ent_code_por_nombre.items()
}

# ----------------------------
# Enriquecer GeoJSON con último periodo (tasa_desocupacion)
# ----------------------------
ultimo_year = estados_df["year"].max()
ultimo_quarter = estados_df[estados_df["year"] == ultimo_year]["quarter"].max()

ult_periodo_df = estados_df[
    (estados_df["year"] == ultimo_year)
    & (estados_df["quarter"] == ultimo_quarter)
].copy()
ult_periodo_df["tasa_desocupacion"] = (
    ult_periodo_df["desocupada_total"] / ult_periodo_df["pea_total"] * 100
)
ult_periodo_df["ingreso_prom_mensual"] = ult_periodo_df["ing_prom_mes_total"]

tasa_por_ent_code = (
    ult_periodo_df.set_index("ent_code")["tasa_desocupacion"].to_dict()
)
ingreso_por_ent_code = (
    ult_periodo_df.set_index("ent_code")["ingreso_prom_mensual"].to_dict()
)

# Quintiles para el ingreso promedio mensual (legend)
ing_series = ult_periodo_df["ingreso_prom_mensual"].dropna().sort_values()
quantiles = [0, 0.2, 0.4, 0.6, 0.8, 1.0]
thresholds = [ing_series.quantile(q) for q in quantiles]
colors_legend = ["#ffedc0", "#fcd571", "#f4b04d", "#e7812a", "#c84c1b"]
legend_breaks = []
for i in range(5):
    low = thresholds[i]
    high = thresholds[i + 1]
    legend_breaks.append(
        {
            "min": round(low, 2),
            "max": round(high, 2),
            "color": colors_legend[i],
            "label": f"{low:,.0f} - {high:,.0f}"
        }
    )

for idx, feature in enumerate(mexico_geojson["features"]):
    shape_name = feature["properties"].get("shapeName")
    ent_nombre = STATE_NAME_MAPPING.get(shape_name)
    ent_code = ent_code_por_nombre.get(ent_nombre)
    if ent_code is None:
        ent_code = ent_code_por_nombre_norm.get(_normalize(ent_nombre or shape_name))
        if ent_code and ent_nombre is None:
            ent_nombre = ent_nombre_por_code.get(ent_code)

    feature["properties"]["ent_nombre"] = ent_nombre
    feature["properties"]["ent_code"] = int(ent_code) if ent_code is not None else None
    feature["properties"]["tasa_desocupacion"] = (
        float(round(tasa_por_ent_code.get(ent_code, None), 2))
        if ent_code in tasa_por_ent_code
        else None
    )
    feature["properties"]["ingreso_prom_mensual"] = (
        float(round(ingreso_por_ent_code.get(ent_code, None), 2))
        if ent_code in ingreso_por_ent_code
        else None
    )
    # Datos imputados artificiales (para visualizar algo en el mapa)
    base_code = ent_code if ent_code is not None else idx + 1
    feature["properties"]["datos_imputados"] = round(3 + (base_code * 0.37) % 7, 2)


# ------------------------------------------------
# RUTAS
# ------------------------------------------------

@app.route("/")
def index():
    return redirect(url_for("estatales"))


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


@app.route("/estatales")
def estatales():
    """Mapa estatal simple con Leaflet."""
    return render_template(
        "estadisticas_estatales.html",
        ultimo_year=int(ultimo_year),
        ultimo_quarter=int(ultimo_quarter),
        legend_title="Ingreso Promedio Mensual",
        legend_breaks=legend_breaks,
    )


# ---------- Endpoints JSON para parte estatal ----------

@app.route("/api/estados/geojson")
def api_estados_geojson():
    return jsonify(mexico_geojson)


@app.route("/api/estado/<int:ent_code>/series")
def api_estado_series(ent_code):
    df = estados_df[estados_df["ent_code"] == ent_code].copy()
    if df.empty:
        return jsonify({"error": "Estado no encontrado"}), 404

    df = df.sort_values(["year", "quarter"])
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
