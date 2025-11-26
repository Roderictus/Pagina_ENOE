# app.py
# ----------------------------------------
# Panel ENOE: estadísticas nacionales y estatales para México
# ----------------------------------------

from flask import Flask, render_template, jsonify, redirect, url_for
import pandas as pd
import json
import os

app = Flask(__name__)

# ----------------------------
# Rutas a los archivos de datos
# (ajusta si tu estructura cambia)
# ----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PATH_NACIONAL = os.path.join(BASE_DIR, "database", "Nacional_deflactado.csv")
PATH_ESTADOS = os.path.join(BASE_DIR, "database", "20251031_Estados.csv")
PATH_GEOJSON = os.path.join(BASE_DIR, "static", "data", "mexico_estados.json")

# ----------------------------
# Carga de datos en memoria
# ----------------------------

# Cargamos la base nacional
nacional_df = pd.read_csv(PATH_NACIONAL)

# Cargamos la base estatal
estados_df = pd.read_csv(PATH_ESTADOS)

# Orden temporal por año y trimestre
nacional_df = nacional_df.sort_values(["year", "quarter"])
estados_df = estados_df.sort_values(["year", "quarter"])

# Cargamos el GeoJSON de estados
with open(PATH_GEOJSON, encoding="utf-8") as f:
    mexico_geojson = json.load(f)

# ----------------------------
# Mapeo entre nombres del GeoJSON y nombres de la base estatal
# (para unir el mapa con tus datos)
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


# Diccionario: ent_nombre -> ent_code (de la base estatal)
ent_code_por_nombre = estados_df.groupby("ent_nombre")["ent_code"].first().to_dict()

# ----------------------------
# Enriquecer GeoJSON con:
#   - ent_code (clave numérica)
#   - ent_nombre (como en la base)
#   - tasa_desocupacion (último periodo, para el choropleth)
# ----------------------------

# Tomamos el último periodo disponible en la base estatal
ultimo_year = estados_df["year"].max()
ultimo_quarter = estados_df[estados_df["year"] == ultimo_year]["quarter"].max()

ult_periodo_df = estados_df[
    (estados_df["year"] == ultimo_year) &
    (estados_df["quarter"] == ultimo_quarter)
].copy()

# Tasa de desocupación = desocupada_total / pea_total * 100
ult_periodo_df["tasa_desocupacion"] = (
    ult_periodo_df["desocupada_total"] / ult_periodo_df["pea_total"] * 100
)

tasa_por_ent_code = (
    ult_periodo_df
    .set_index("ent_code")["tasa_desocupacion"]
    .to_dict()
)

for feature in mexico_geojson["features"]:
    shape_name = feature["properties"].get("shapeName")
    ent_nombre = STATE_NAME_MAPPING.get(shape_name)
    ent_code = ent_code_por_nombre.get(ent_nombre)

    feature["properties"]["ent_nombre"] = ent_nombre
    feature["properties"]["ent_code"] = int(ent_code) if ent_code is not None else None

    if ent_code in tasa_por_ent_code:
        feature["properties"]["tasa_desocupacion"] = float(
            round(tasa_por_ent_code[ent_code], 2)
        )
    else:
        feature["properties"]["tasa_desocupacion"] = None


# ------------------------------------------------
# RUTAS
# ------------------------------------------------

@app.route("/")
def index():
    """
    Ruta raíz: redirige a la página principal de estadísticas.
    Así, acceder a http://localhost:5000/ no da 404.
    """
    return redirect(url_for("estadisticas"))

@app.route("/estadisticas")
def estadisticas():
    """
    PAgina principal del panel (vista Nacional + vista Estatal).
    AquA- calculamos la tasa de ocupaciA3n nacional anual
    y la pasamos al template para el grAfico Plotly.
    """
    df = nacional_df.copy()

    # Tasa de ocupaciA3n nacional (%):
    # ocupada_total / pob_15_y_mas * 100
    df["tasa_ocupacion"] = df["ocupada_total"] / df["pob_15_y_mas"] * 100.0
    # Porcentajes adicionales sobre poblaciA3n ocupada
    df["ocupacion_formal_pct"] = df["ocupacion_formal"] / df["ocupada_total"] * 100.0
    df["ocupacion_informal_pct"] = df["ocupacion_informal"] / df["ocupada_total"] * 100.0

    # Eje temporal trimestral (sin agrupar)
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

    # Renderizamos el template con los datos para el grAfico nacional
    return render_template(
        "estadisticas.html",
        labels=labels,
        percent_variables=percent_variables
    )


# ---------- Endpoints JSON para parte estatal ----------

@app.route("/api/estados/geojson")
def api_estados_geojson():
    """
    Devuelve el GeoJSON de los estados de México, ya enriquecido con:
    - ent_code
    - ent_nombre
    - tasa_desocupacion (último periodo disponible)
    """
    return jsonify(mexico_geojson)


@app.route("/api/estado/<int:ent_code>/series")
def api_estado_series(ent_code):
    """
    Devuelve series de tiempo para un estado específico.

    Devuelve:
    {
      "ent_code": ...,
      "ent_nombre": "...",
      "labels": [...],  # periodo
      "series": {
          "ocupada_total": [...],
          "desocupada_total": [...],
          "ing_prom_mes_total": [...],
          "ing_prom_hora_total": [...],
          "tasa_desocupacion": [...]
      }
    }
    """
    df = estados_df[estados_df["ent_code"] == ent_code].copy()
    if df.empty:
        return jsonify({"error": "Estado no encontrado"}), 404

    df = df.sort_values(["year", "quarter"])

    labels = df["periodo"].tolist()

    # Tasa de desocupación histórica por estado
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
    # Ejecutar app para pruebas
    app.run(debug=True)
