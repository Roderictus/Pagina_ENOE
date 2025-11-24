import pandas as pd
from flask import Flask, render_template, jsonify, request

# --- 1. Configuración Inicial de Flask y Pandas ---

app = Flask(__name__)

# Cargar los CSV en memoria UNA SOLA VEZ al iniciar la aplicación.
# Esto es mucho más rápido que leerlos en cada petición.
try:
    # Usamos index_col=0 para el CSV Nacional por esa primera columna sin nombre
    df_nacional = pd.read_csv(
        'database/Nacional_deflactado.csv', 
        index_col=0
    )
    df_estatal = pd.read_csv(
        'database/20251031_Estados.csv'
    )

    # --- Pre-procesamiento de Datos ---
    # Convertir 'fecha' a datetime para un manejo correcto
    df_nacional['fecha'] = pd.to_datetime(df_nacional['fecha'])
    
    # Crear una columna 'fecha' unificada en los datos estatales
    df_estatal['fecha'] = pd.to_datetime(
        df_estatal['year'].astype(str) + 'Q' + df_estatal['quarter'].astype(str)
    )
    
    print(">>> Bases de datos cargadas y pre-procesadas exitosamente.")

except FileNotFoundError as e:
    print(f"Error: No se pudo encontrar el archivo CSV. {e}")
    print("Asegúrate de que los archivos están en la carpeta /database")
    # En producción, querrías manejar esto de forma más elegante
    df_nacional = pd.DataFrame()
    df_estatal = pd.DataFrame()


# --- 2. Ruta Principal (Sirve la página HTML) ---

@app.route('/')
def index():
    """Sirve la plantilla principal del dashboard."""
    return render_template('index.html')


# --- 3. Endpoints de la API (Sirven datos JSON) ---

@app.route('/api/nacional/all')
def api_nacional_all():
    """
    Endpoint para las gráficas de la galería nacional.
    Devuelve datos pre-seleccionados para las tarjetas.
    """
    if df_nacional.empty:
        return jsonify({"error": "Datos nacionales no disponibles"}), 500

    # Ordenar por fecha para las gráficas de líneas
    df_nac_sorted = df_nacional.sort_values(by='fecha')
    labels = df_nac_sorted['fecha'].dt.strftime('%Y-%m-%d').tolist()

    # Define las gráficas que quieres mostrar en la galería
    charts_data = {
        "ingreso_real_vs_nominal": {
            "title": "Ingreso Real vs. Nominal (Mensual)",
            "description": "Análisis del ingreso promedio mensual, comparando el valor nominal (corriente) contra el valor real (constante, base T1 2005), ajustado por el deflactor.",
            "labels": labels,
            "datasets": [
                {
                    "label": "Ingreso Real",
                    "data": df_nac_sorted['ing_prom_mes_real'].tolist(),
                    "borderColor": "#198754", # Verde Bootstrap
                    "backgroundColor": "rgba(25, 135, 84, 0.2)",
                    "fill": True,
                    "tension": 0.1
                },
                {
                    "label": "Ingreso Nominal",
                    "data": df_nac_sorted['ing_prom_mes_total'].tolist(),
                    "borderColor": "#6c757d", # Gris Bootstrap
                    "backgroundColor": "rgba(108, 117, 125, 0.1)",
                    "fill": False,
                    "tension": 0.1
                }
            ]
        },
        "ocupacion_vs_desocupacion": {
            "title": "Población Ocupada vs. Desocupada",
            "description": "Evolución de la población ocupada total frente a la población desocupada. Muestra la dinámica del mercado laboral a nivel nacional.",
            "labels": labels,
            "datasets": [
                {
                    "label": "Ocupados",
                    "data": df_nac_sorted['ocupada_total'].tolist(),
                    "borderColor": "#0d6efd", # Azul Bootstrap
                    "backgroundColor": "rgba(13, 110, 253, 0.1)",
                    "fill": True
                },
                {
                    "label": "Desocupados",
                    "data": df_nac_sorted['desocupada_total'].tolist(),
                    "borderColor": "#dc3545", # Rojo Bootstrap
                    "backgroundColor": "rgba(220, 53, 69, 0.1)",
                    "fill": True
                }
            ]
        },
        "formal_vs_informal": {
            "title": "Ocupación Formal vs. Informal",
            "description": "Comparativa del número de personas en la ocupación formal contra la informal. Este es un indicador clave de la estructura del empleo en México.",
            "labels": labels,
            "datasets": [
                {
                    "label": "Ocupación Informal",
                    "data": df_nac_sorted['ocupacion_informal'].tolist(),
                    "borderColor": "#ffc107", # Amarillo Bootstrap
                    "backgroundColor": "rgba(255, 193, 7, 0.2)",
                    "type": "bar"
                },
                {
                    "label": "Ocupación Formal",
                    "data": df_nac_sorted['ocupacion_formal'].tolist(),
                    "borderColor": "#0dcaf0", # Cyan Bootstrap
                    "backgroundColor": "rgba(13, 202, 240, 0.2)",
                    "type": "bar"
                }
            ]
        }
    }
    
    return jsonify(charts_data)


@app.route('/api/estatal/latest')
def api_estatal_latest():
    """
    Devuelve el valor más reciente de una variable para TODOS los estados.
    Usado para colorear el mapa (coroplético).
    """
    variable = request.args.get('variable', 'pob_total') # Variable por defecto
    if df_estatal.empty:
        return jsonify({"error": "Datos estatales no disponibles"}), 500
        
    try:
        # 1. Encontrar la fecha más reciente en la base de datos
        fecha_reciente = df_estatal['fecha'].max()
        
        # 2. Filtrar los datos para esa fecha
        df_latest = df_estatal[df_estatal['fecha'] == fecha_reciente]
        
        # 3. Seleccionar solo las columnas necesarias y renombrar
        df_result = df_latest[['ent_nombre', variable]].rename(
            columns={variable: 'value'}
        )
        
        # 4. Convertir a un diccionario {Estado: valor} para un lookup fácil
        data_dict = df_result.set_index('ent_nombre')['value'].to_dict()
        
        return jsonify(data_dict)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/estatal/timeseries')
def api_estatal_timeseries():
    """
    Devuelve la serie de tiempo para una variable y una lista de estados.
    Usado para la gráfica comparativa estatal.
    """
    variable = request.args.get('variable', 'pob_total')
    # Los estados vienen como 'Aguascalientes,Jalisco,Colima'
    estados_str = request.args.get('estados', '')
    
    if not estados_str:
        return jsonify({"error": "No se seleccionaron estados"}), 400
        
    estados_list = estados_str.split(',')
    
    if df_estatal.empty:
        return jsonify({"error": "Datos estatales no disponibles"}), 500

    try:
        # Prepara los labels (todas las fechas únicas, ordenadas)
        all_labels = sorted(df_estatal['fecha'].unique())
        labels_str = [pd.to_datetime(d).strftime('%Y-%m-%d') for d in all_labels]
        
        response_data = {"labels": labels_str, "datasets": []}
        
        # Filtra el DF completo una sola vez
        df_filtered = df_estatal[
            df_estatal['ent_nombre'].isin(estados_list)
        ].sort_values(by='fecha')

        # Itera sobre los estados seleccionados para construir los datasets
        for estado in estados_list:
            # Filtra el DF ya filtrado (muy rápido)
            df_estado = df_filtered[df_filtered['ent_nombre'] == estado]
            
            # Asegura que los datos coincidan con todos los labels
            # Rellena con 'None' (null en JSON) si faltan datos
            data_map = pd.Series(
                df_estado[variable].values, 
                index=df_estado['fecha']
            ).reindex(all_labels)
            
            response_data['datasets'].append({
                "label": estado,
                "data": data_map.where(pd.notnull(data_map), None).tolist(), # Reemplaza NaN con None
                "fill": False,
                "tension": 0.1
            })
            
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- 4. Variables Disponibles (para el menú dropdown) ---
@app.route('/api/estatal/variables')
def api_estatal_variables():
    """Devuelve una lista de variables numéricas para el dropdown."""
    if df_estatal.empty:
        return jsonify({"error": "Datos estatales no disponibles"}), 500
        
    # Excluir columnas no numéricas o de identificación
    excluded_cols = ['year', 'quarter', 'ent_code', 'ent_nombre', 'periodo', 'fecha']
    numeric_cols = df_estatal.select_dtypes(include='number').columns
    variables = [col for col in numeric_cols if col not in excluded_cols]
    
    # Podrías "embellecer" los nombres aquí si quisieras
    # Ej: {'id': 'pob_total', 'nombre': 'Población Total'}
    variables_formatted = [
        {"id": v, "nombre": v.replace("_", " ").replace("pob ", "población ").capitalize()}
        for v in variables
    ]
    
    return jsonify(variables_formatted)


# --- 5. Ejecutar la aplicación ---
if __name__ == '__main__':
    app.run(debug=True)