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

#PATH_NACIONAL = os.path.join(BASE_DIR, "database", "Nacional_deflactado.csv")
PATH_NACIONAL = os.path.join(BASE_DIR, "database", "20251126_Nacional_deflactado.csv")
PATH_ESTADOS = os.path.join(BASE_DIR, "database", "20251031_Estados.csv")
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
    """Página para gráfica nacional."""
    df = nacional_df.copy()
    df["tasa_ocupacion"] = df["ocupada_total"] / df["pob_15_y_mas"] * 100.0
    df["ocupacion_formal_pct"] = df["ocupacion_formal"] / df["ocupada_total"] * 100.0
    df["ocupacion_informal_pct"] = df["ocupacion_informal"] / df["ocupada_total"] * 100.0

    labels = [f"{int(y)} T{int(q)}" for y, q in zip(df["year"], df["quarter"])]

    percent_variables = [
        {
            "id": "tasa_ocupacion",
            "label": "Tasa de ocupación nacional",
            "color": "#0d6efd",
            "data": df["tasa_ocupacion"].round(2).tolist(),
            "checked": True,
        },
        {
            "id": "ocupacion_formal_pct",
            "label": "Ocupación formal / Población ocupada",
            "color": "#20c997",
            "data": df["ocupacion_formal_pct"].round(2).tolist(),
            "checked": True,
        },
        {
            "id": "ocupacion_informal_pct",
            "label": "Ocupación informal / Población ocupada",
            "color": "#f59e0b",
            "data": df["ocupacion_informal_pct"].round(2).tolist(),
            "checked": False,
        },
    ]

    return render_template(
        "estadisticas_nacionales.html",
        labels=labels,
        percent_variables=percent_variables,
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
