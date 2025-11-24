// Espera a que el DOM esté completamente cargado
document.addEventListener("DOMContentLoaded", function() {

    // --- 1. Variables Globales y Contextos ---
    const ctxModal = document.getElementById('modal-chart-canvas')?.getContext('2d');
    const modalTitle = document.getElementById('modal-title');
    const modalDescription = document.getElementById('modal-description');
    const chartModal = new bootstrap.Modal(document.getElementById('chartModal'));
    
    // Almacena las instancias de Chart.js para actualizarlas/destruirlas
    let nacionalChartInstances = {}; 
    let modalChartInstance;
    let estatalChartInstance;
    
    // Variables de la vista estatal
    const variableSelect = document.getElementById('variable-select');
    const listaEstadosDiv = document.getElementById('lista-estados-seleccionados');
    const ayudaEstatal = document.getElementById('ayuda-estatal');
    let map, geoJsonLayer, mapLegend;
    let selectedVariable = ''; // Variable actual
    let selectedStates = [];   // Estados seleccionados para comparar
    let estatalDataCache = {}; // Cache para datos del mapa
    
    // Paleta de colores para la gráfica comparativa
    const CHART_COLORS = [
        '#0d6efd', '#dc3545', '#198754', '#ffc107', '#0dcaf0', 
        '#6f42c1', '#fd7e14', '#20c997', '#d63384', '#6c757d'
    ];

    // --- 2. Lógica de Pestañas (Nacional/Estatal) ---
    const btnEstatal = document.getElementById('btn-estatal');
    btnEstatal.addEventListener('shown.bs.tab', () => {
        // Inicializa la vista estatal solo la primera vez que se muestra
        if (!map) {
            initEstatalView();
        } else {
            // Si la pestaña estaba oculta, el mapa puede necesitar
            // recalcular su tamaño al volver a mostrarse.
            setTimeout(() => map.invalidateSize(), 10);
        }
    });

    // --- 3. VISTA NACIONAL: Galería y Modal ---

    /**
     * Carga los datos para la galería nacional y los renderiza.
     */
    async function initNacionalView() {
        try {
            const response = await fetch('/api/nacional/all');
            const chartsData = await response.json();
            
            const galeriaNacional = document.getElementById('galeria-nacional');
            galeriaNacional.innerHTML = ''; // Limpiar el spinner de carga

            // Itera sobre cada gráfica definida en el backend
            for (const [key, config] of Object.entries(chartsData)) {
                
                // 1. Crear la tarjeta (card) de Bootstrap
                const col = document.createElement('div');
                col.className = 'col-lg-4 col-md-6';
                
                const card = document.createElement('div');
                card.className = 'card shadow-sm chart-card';
                // Añadir atributos 'data-*' para el modal
                card.dataset.bsToggle = 'modal';
                card.dataset.bsTarget = '#chartModal';
                card.dataset.chartKey = key; // Usamos la clave para encontrar los datos
                
                const cardBody = document.createElement('div');
                cardBody.className = 'card-body';
                
                // 2. Crear el título y el canvas
                const title = document.createElement('h6');
                title.className = 'card-title';
                title.textContent = config.title;
                
                const canvasContainer = document.createElement('div');
                canvasContainer.className = 'chart-container-nacional';
                
                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d');
                
                // 3. Renderizar la gráfica pequeña
                nacionalChartInstances[key] = new Chart(ctx, {
                    type: config.datasets[0].type || 'line', // Tipo por defecto (line)
                    data: {
                        labels: config.labels,
                        datasets: config.datasets
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false } }, // Sin leyenda en las tarjetas
                        scales: {
                            x: { ticks: { display: false } }, // Sin ejes en las tarjetas
                            y: { ticks: { display: false } }
                        }
                    }
                });
                
                // 4. Guardar datos para el modal
                card.dataset.modalTitle = config.title;
                card.dataset.modalDescription = config.description;

                // 5. Ensamblar la tarjeta
                canvasContainer.appendChild(canvas);
                cardBody.appendChild(title);
                cardBody.appendChild(canvasContainer);
                card.appendChild(cardBody);
                col.appendChild(card);
                galeriaNacional.appendChild(col);
            }

        } catch (error) {
            console.error('Error al cargar datos nacionales:', error);
            galeriaNacional.innerHTML = '<p class="text-danger">Error al cargar gráficas nacionales.</p>';
        }
    }

    /**
     * Event Listener para cuando el Modal se está abriendo.
     */
    document.getElementById('chartModal').addEventListener('show.bs.modal', (event) => {
        const card = event.relatedTarget; // La tarjeta que activó el modal
        const chartKey = card.dataset.chartKey;
        
        // Configurar título y descripción del modal
        modalTitle.textContent = card.dataset.modalTitle;
        modalDescription.textContent = card.dataset.modalDescription;
        
        // Obtener la configuración de la gráfica pequeña
        const smallChartConfig = nacionalChartInstances[chartKey].config;
        
        // Destruir la instancia anterior del modal (si existe)
        if (modalChartInstance) {
            modalChartInstance.destroy();
        }

        // Crear una nueva gráfica en el canvas del modal
        modalChartInstance = new Chart(ctxModal, {
            type: smallChartConfig.type,
            data: smallChartConfig.data, // Usa los mismos datos
            options: { // Opciones completas para el modal
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: true, position: 'bottom' },
                    tooltip: { mode: 'index', intersect: false }
                },
                scales: { // Mostrar ejes en el modal
                    x: { ticks: { display: true }, grid: { display: false } },
                    y: { ticks: { display: true } }
                }
            }
        });
    });

    // --- 4. VISTA ESTATAL: Mapa, Menú y Gráfica ---

    /**
     * Inicializa toda la lógica de la vista estatal (mapa, menú, etc.)
     */
    async function initEstatalView() {
        initMap();
        await populateVariableSelect();
        // Carga el mapa con la primera variable de la lista
        if (selectedVariable) {
            updateMapColors();
        }
    }

    /**
     * Rellena el menú <select> con las variables del endpoint.
     */
    async function populateVariableSelect() {
        try {
            const response = await fetch('/api/estatal/variables');
            const variables = await response.json();
            
            variableSelect.innerHTML = ''; // Limpiar 'Cargando...'
            
            variables.forEach((v, index) => {
                const option = document.createElement('option');
                option.value = v.id;
                option.textContent = v.nombre;
                variableSelect.appendChild(option);
                
                // Selecciona la primera variable por defecto
                if (index === 0) {
                    selectedVariable = v.id;
                }
            });
            
            // Añadir listener al select
            variableSelect.addEventListener('change', (e) => {
                selectedVariable = e.target.value;
                updateMapColors();
                updateEstatalChart(); // Actualiza la gráfica con la nueva variable
            });

        } catch (error) {
            console.error('Error al cargar variables:', error);
            variableSelect.innerHTML = '<option>Error al cargar</option>';
        }
    }

    /**
     * Inicializa el mapa Leaflet y carga el GeoJSON.
     */
    function initMap() {
        map = L.map('map').setView([23.63, -102.55], 5); // Centrado en México
        L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
            subdomains: 'abcd',
            maxZoom: 10
        }).addTo(map);

        // Crear la leyenda
        mapLegend = L.control({ position: 'bottomright' });
        mapLegend.onAdd = function (map) {
            return L.DomUtil.get('map-legend');
        };
        mapLegend.addTo(map);

        // Cargar el GeoJSON
        fetch('/static/data/mexico_estados.json')
            .then(res => res.json())
            .then(data => {
                geoJsonLayer = L.geoJson(data, {
                    style: styleDefault,
                    onEachFeature: onEachFeature
                }).addTo(map);
            })
            .catch(err => console.error("Error cargando GeoJSON:", err));
    }

    /**
     * Estilo por defecto para los estados (antes de cargar datos).
     */
    function styleDefault() {
        return {
            fillColor: '#6c757d', // Gris
            fillOpacity: 0.5,
            weight: 1,
            color: 'white',
            dashArray: '3'
        };
    }

    /**
     * Vincula eventos a cada polígono estatal.
     */
    function onEachFeature(feature, layer) {
        // IMPORTANTE: Asegúrate que tu GeoJSON tenga esta propiedad
        const nombreEstado = feature.properties.name; 
        
        layer.on({
            mouseover: (e) => highlightFeature(e, nombreEstado),
            mouseout: (e) => resetHighlight(e),
            click: (e) => toggleEstadoSeleccionado(e, nombreEstado)
        });
    }

    /**
     * Resalta el estado al pasar el mouse.
     */
    function highlightFeature(e, nombreEstado) {
        const layer = e.target;
        layer.setStyle({
            weight: 3,
            color: '#333',
            fillOpacity: 0.7
        });
        layer.bringToFront();
        // Opcional: mostrar tooltip
        layer.bindTooltip(nombreEstado).openTooltip();
    }

    /**
     * Quita el resaltado al quitar el mouse.
     */
    function resetHighlight(e) {
        geoJsonLayer.resetStyle(e.target);
    }

    /**
     * Añade o quita un estado de la lista de comparación al hacer clic.
     */
    function toggleEstadoSeleccionado(e, nombreEstado) {
        const index = selectedStates.indexOf(nombreEstado);
        
        if (index > -1) {
            // Si ya está, lo quita
            selectedStates.splice(index, 1);
        } else {
            // Si no está, lo añade (con un límite, ej. 5)
            if (selectedStates.length < 5) {
                selectedStates.push(nombreEstado);
            } else {
                alert("Puedes comparar un máximo de 5 estados a la vez.");
            }
        }
        
        updateSelectedStatesList(); // Actualiza los "tags"
        updateEstatalChart();      // Actualiza la gráfica
    }

    /**
     * Actualiza la lista de "tags" de estados seleccionados.
     */
    function updateSelectedStatesList() {
        listaEstadosDiv.innerHTML = '';
        if (selectedStates.length === 0) {
            ayudaEstatal.style.display = 'block';
            return;
        }
        
        ayudaEstatal.style.display = 'none';
        
        selectedStates.forEach((estado, index) => {
            const tag = document.createElement('span');
            tag.className = 'estado-tag';
            // Asigna un color de la paleta
            const color = CHART_COLORS[index % CHART_COLORS.length];
            tag.style.borderColor = color;
            tag.style.color = color;
            
            tag.innerHTML = `${estado} <span class="remove-tag" data-estado="${estado}">×</span>`;
            
            // Evento para quitar el estado al hacer clic en la 'X'
            tag.querySelector('.remove-tag').addEventListener('click', (e) => {
                e.stopPropagation(); // Evita que se active el click del mapa
                toggleEstadoSeleccionado(null, estado);
            });
            
            listaEstadosDiv.appendChild(tag);
        });
    }

    /**
     * Actualiza la gráfica de serie de tiempo estatal.
     */
    async function updateEstatalChart() {
        // Destruye la gráfica anterior si existe
        if (estatalChartInstance) {
            estatalChartInstance.destroy();
        }
        
        if (selectedStates.length === 0) {
            // No hay estados, no hacer nada (canvas vacío)
            return;
        }

        const estadosQuery = selectedStates.join(',');
        
        try {
            const response = await fetch(`/api/estatal/timeseries?variable=${selectedVariable}&estados=${estadosQuery}`);
            const data = await response.json();
            
            // Asigna colores dinámicamente
            data.datasets.forEach((ds, index) => {
                const color = CHART_COLORS[index % CHART_COLORS.length];
                ds.borderColor = color;
                ds.backgroundColor = `${color}33`; // Añade transparencia
            });

            const ctx = document.getElementById('estatal-chart-timeseries').getContext('2d');
            estatalChartInstance = new Chart(ctx, {
                type: 'line',
                data: data,
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { 
                        legend: { display: false } // La lista de tags actúa como leyenda
                    },
                    scales: { 
                        x: { 
                            type: 'time', 
                            time: { unit: 'year' },
                            grid: { display: false } 
                        } 
                    },
                    interaction: {
                        mode: 'index',
                        intersect: false
                    }
                }
            });

        } catch (error) {
            console.error('Error al actualizar gráfica estatal:', error);
        }
    }

    /**
     * Obtiene los datos más recientes y actualiza los colores del mapa.
     */
    async function updateMapColors() {
        try {
            const response = await fetch(`/api/estatal/latest?variable=${selectedVariable}`);
            estatalDataCache = await response.json(); // {Aguascalientes: 1053965, ...}
            
            const values = Object.values(estatalDataCache).filter(v => v != null);
            if (values.length === 0) return;

            // Calcula 5 cuantiles para la leyenda (simple)
            const quantiles = getQuantiles(values, 5);
            
            // Actualiza la leyenda del mapa
            updateMapLegend(quantiles, quantiles.colores);
            
            // Actualiza el estilo de cada capa del mapa
            geoJsonLayer.eachLayer(layer => {
                const nombreEstado = layer.feature.properties.name;
                const value = estatalDataCache[nombreEstado];
                layer.setStyle({
                    fillColor: getColorForValue(value, quantiles.limites, quantiles.colores),
                    fillOpacity: 0.7,
                    weight: 1,
                    color: 'white'
                });
            });

        } catch (error) {
            console.error('Error al actualizar colores del mapa:', error);
        }
    }
    
    // --- 5. Funciones de Utilidad (Color, Cuantiles) ---

    function getQuantiles(data, numQuantiles) {
        const sorted = data.sort((a, b) => a - b);
        const step = 1 / numQuantiles;
        let limites = [];
        for (let i = 1; i < numQuantiles; i++) {
            const index = Math.floor(sorted.length * (step * i));
            limites.push(sorted[index]);
        }
        // Paleta de colores (ej. Azul)
        const colores = ['#eff3ff', '#bdd7e7', '#6baed6', '#3182bd', '#08519c'];
        return { limites, colores };
    }

    function getColorForValue(value, limites, colores) {
        if (value == null) return '#ccc'; // Color para datos nulos
        for (let i = 0; i < limites.length; i++) {
            if (value <= limites[i]) return colores[i];
        }
        return colores[colores.length - 1]; // El cuantil más alto
    }

    function updateMapLegend(quantiles, colores) {
        const legendDiv = document.getElementById('map-legend');
        let html = `<div class="legend-title">${variableSelect.options[variableSelect.selectedIndex].text}</div>`;
        
        let from = 0;
        for (let i = 0; i < quantiles.limites.length; i++) {
            const to = quantiles.limites[i];
            html += `<div class="legend-item"><span class="legend-color-box" style="background:${colores[i]}"></span> `;
            html += `${from.toLocaleString()} &ndash; ${to.toLocaleString()}</div>`;
            from = to;
        }
        // Último rango
        html += `<div class="legend-item"><span class="legend-color-box" style="background:${colores[colores.length-1]}"></span> `;
        html += `> ${from.toLocaleString()}</div>`;
        
        legendDiv.innerHTML = html;
    }


    // --- INICIALIZACIÓN ---
    initNacionalView();

});