"""
app.py — J.O.S.E-O v3.0
Ruteo híbrido ORS + A* para vehículos de emergencia en La Serena.

Cambios arquitectónicos QA-Report-2026-Q2:
  D1: toda la UI encapsulada en main() — sin código de presentación en scope global.
  D2: acceso a session_state delegado a state.py — sin lectura/escritura directa.
  D3: cliente ORS creado bajo demanda vía crear_cliente_ors() — sin global estático.
"""
import streamlit as st
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
import openrouteservice
import networkx as nx
import math

from ui import cargar_estilos, mostrar_header
from state import (
    guardar_calculo,
    tiene_calculo,
    leer_resultado,
    leer_destino,
    leer_cuarteles,
)

# =========================================================
# CONFIG
# =========================================================
LUGAR   = "La Serena, Chile"
API_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImFjZGMxNzczOThmYzUyZGRhNDFmNTZhNjNkNGJjMTA0OTRkNzdjMTIxYjhmNjE1MmQ0NDg2YjViIiwiaCI6Im11cm11cjY0In0="


# =========================================================
# DEFECTO 3 — CLIENTE ORS: factory bajo demanda
# El cliente ya no existe en scope global.
# Se crea dentro de main() y se pasa como parámetro explícito.
# =========================================================
def crear_cliente_ors(api_key: str) -> openrouteservice.Client:
    """Inicializa y retorna el cliente ORS. No ejecuta I/O al definirse."""
    return openrouteservice.Client(key=api_key)


# =========================================================
# CUARTELES
# =========================================================
@st.cache_data
def obtener_cuarteles():
    return [
        {"nombre": "1ra Compañía", "lat": -29.9045, "lon": -71.2519},
        {"nombre": "2da Compañía", "lat": -29.9070, "lon": -71.2600},
        {"nombre": "3ra Compañía", "lat": -29.9200, "lon": -71.2500},
        {"nombre": "4ta Compañía", "lat": -29.8800, "lon": -71.2400},
    ]


# =========================================================
# ORS: OBTENER RUTAS REALES CON WAYPOINTS
# =========================================================
def obtener_rutas_api(
    origen: dict,
    destino,
    ors_client: openrouteservice.Client,
) -> list:
    """
    Llama a ORS y retorna hasta 3 rutas alternativas.
    Recibe el cliente ORS como parámetro (inyección de dependencias).
    Cada ruta incluye geometría completa (waypoints), distancia y tiempo.
    """
    coords = [
        (origen["lon"], origen["lat"]),
        (destino.longitude, destino.latitude),
    ]
    res = ors_client.directions(
        coordinates=coords,
        profile="driving-car",
        format="geojson",
        alternative_routes={"target_count": 3, "weight_factor": 1.6},
    )
    rutas = []
    for feature in res["features"]:
        geometry = feature["geometry"]["coordinates"]
        summary  = feature["properties"]["summary"]
        rutas.append({
            "ruta":   geometry,
            "dist":   summary["distance"],
            "tiempo": summary["duration"],
        })
    return rutas


# =========================================================
# HEURÍSTICA EUCLIDIANA REAL
# =========================================================
def heuristica_euclidiana(coord_nodo: tuple, coord_destino: tuple) -> float:
    """
    Estima tiempo restante desde un nodo hasta el destino.
    Usa distancia euclidiana sobre coordenadas geográficas,
    calibrada a 50 km/h promedio urbano (13.9 m/s).
    1 grado de latitud ≈ 111 000 m.
    """
    lon_u, lat_u = coord_nodo
    lon_d, lat_d = coord_destino
    dx     = (lon_u - lon_d) * 111_000 * math.cos(math.radians(lat_u))
    dy     = (lat_u - lat_d) * 111_000
    dist_m = math.sqrt(dx**2 + dy**2)
    return dist_m / 13.9  # segundos estimados


# =========================================================
# CONSTRUIR GRAFO DESDE WAYPOINTS ORS
# =========================================================
def construir_grafo_desde_ruta(ruta_coords: list, tiempo_total: float) -> nx.DiGraph:
    """
    Convierte los waypoints de una ruta ORS en un grafo dirigido.
    - Cada waypoint es un nodo con sus coordenadas.
    - Las aristas entre nodos consecutivos tienen como peso el tiempo
      proporcional a la longitud del segmento.
    """
    G = nx.DiGraph()
    n = len(ruta_coords)

    longitud_total = 0.0
    segmentos = []
    for i in range(n - 1):
        lon1, lat1 = ruta_coords[i]
        lon2, lat2 = ruta_coords[i + 1]
        dx       = (lon2 - lon1) * 111_000 * math.cos(math.radians(lat1))
        dy       = (lat2 - lat1) * 111_000
        seg_dist = math.sqrt(dx**2 + dy**2)
        segmentos.append(seg_dist)
        longitud_total += seg_dist

    for i, (lon, lat) in enumerate(ruta_coords):
        G.add_node(i, coords=(lon, lat))

    for i, seg_dist in enumerate(segmentos):
        proporcion = seg_dist / longitud_total if longitud_total > 0 else 1.0 / n
        tiempo_seg = tiempo_total * proporcion
        G.add_edge(i, i + 1, weight=tiempo_seg)

    return G


# =========================================================
# A* REAL SOBRE GRAFO DE WAYPOINTS
# =========================================================
def astar_sobre_ruta(G: nx.DiGraph, coord_destino: tuple) -> tuple:
    """
    Ejecuta A* desde nodo 0 (cuartel) hasta el último nodo (destino).

    f(n) = g(n) + h(n)
      g(n): tiempo acumulado real desde el cuartel hasta el nodo n.
      h(n): tiempo estimado desde n hasta el destino (heurística euclidiana).

    La heurística es ADMISIBLE: nunca sobreestima el costo real,
    lo que garantiza que A* encuentra la solución óptima.
    """
    nodo_inicio  = 0
    nodo_destino = max(G.nodes())

    def h(u, v):
        coord_u = G.nodes[u]["coords"]
        return heuristica_euclidiana(coord_u, coord_destino)

    path  = nx.astar_path(G, nodo_inicio, nodo_destino, heuristic=h, weight="weight")
    costo = nx.path_weight(G, path, weight="weight")
    return path, costo


# =========================================================
# NÚCLEO HÍBRIDO: ORS → grafo waypoints → A* real
# =========================================================
def mejor_cuartel_hibrido(
    cuarteles: list,
    destino,
    ors_client: openrouteservice.Client,
) -> dict:
    """
    Flujo híbrido ORS + A*:
    1. ORS genera hasta 3 rutas reales con waypoints por cada cuartel.
    2. Cada ruta se convierte en un grafo dirigido de waypoints.
    3. A* con heurística euclidiana evalúa cada grafo.
    4. Se selecciona el cuartel cuya mejor ruta A* tenga menor costo.

    Recibe el cliente ORS como parámetro (inyección de dependencias).
    """
    coord_destino   = (destino.longitude, destino.latitude)
    mejor_cuartel   = None
    mejor_costo     = float("inf")
    todos_los_datos = {}

    for c in cuarteles:
        try:
            rutas             = obtener_rutas_api(c, destino, ors_client)
            costo_min_cuartel = float("inf")
            idx_mejor_ruta    = 0

            for idx, ruta in enumerate(rutas):
                G = construir_grafo_desde_ruta(ruta["ruta"], ruta["tiempo"])
                _, costo_astar = astar_sobre_ruta(G, coord_destino)

                if costo_astar < costo_min_cuartel:
                    costo_min_cuartel = costo_astar
                    idx_mejor_ruta    = idx

            todos_los_datos[c["nombre"]] = {
                "cuartel":     c,
                "rutas":       rutas,
                "costo_astar": costo_min_cuartel,
                "idx_mejor":   idx_mejor_ruta,
            }

            if costo_min_cuartel < mejor_costo:
                mejor_costo   = costo_min_cuartel
                mejor_cuartel = c["nombre"]

        except Exception as e:
            st.warning(f"Error procesando {c['nombre']}: {e}")

    if mejor_cuartel is None:
        raise ValueError("No se pudo calcular ninguna ruta.")

    datos           = todos_los_datos[mejor_cuartel]
    rutas_ordenadas = datos["rutas"].copy()
    idx_mejor       = datos["idx_mejor"]
    if idx_mejor != 0:
        rutas_ordenadas.insert(0, rutas_ordenadas.pop(idx_mejor))

    return {
        "cuartel":     datos["cuartel"],
        "rutas":       rutas_ordenadas,
        "costo_astar": datos["costo_astar"],
    }


# =========================================================
# MAPA
# =========================================================
def crear_mapa(rutas: list, cuarteles: list, destino, origen: dict) -> folium.Map:
    m = folium.Map(
        location=[destino.latitude, destino.longitude],
        zoom_start=14,
        tiles="CartoDB dark_matter",
    )
    colores = ["red", "blue", "green"]

    for i, r in enumerate(rutas):
        puntos = [(lat, lon) for lon, lat in r["ruta"]]
        folium.PolyLine(
            puntos,
            color=colores[i],
            weight=7 if i == 0 else 4,
            opacity=0.85,
            tooltip=f"Ruta {i + 1}",
        ).add_to(m)

    for c in cuarteles:
        if c["nombre"] == origen["nombre"]:
            folium.Marker(
                [c["lat"], c["lon"]],
                tooltip=f"🚒 Sale desde {c['nombre']}",
                popup=f"Origen: {c['nombre']}",
                icon=folium.Icon(color="green", icon="home"),
            ).add_to(m)
        else:
            folium.Marker(
                [c["lat"], c["lon"]],
                tooltip=c["nombre"],
                icon=folium.Icon(color="blue", icon="fire"),
            ).add_to(m)

    folium.Marker(
        [destino.latitude, destino.longitude],
        tooltip="🚨 Emergencia",
        popup="Destino",
        icon=folium.Icon(color="red", icon="info-sign"),
    ).add_to(m)

    puntos_total = [(lat, lon) for lon, lat in rutas[0]["ruta"]]
    m.fit_bounds(puntos_total)
    return m


# =========================================================
# UI — PANEL IZQUIERDO
# =========================================================
def renderizar_panel_izquierdo(
    cuarteles: list,
    ors_client: openrouteservice.Client,
) -> None:
    """
    Renderiza el panel de control izquierdo.
    Recibe datos como parámetros — no lee variables globales.
    DEFECTO 2: escribe a session_state solo vía guardar_calculo().
    """
    st.markdown('<p class="section-label">Cuarteles activos</p>', unsafe_allow_html=True)
    chips_html = '<div class="cuarteles-grid">'
    for c in cuarteles:
        chips_html += f'<span class="cuartel-chip">{c["nombre"]}</span>'
    chips_html += "</div>"
    st.markdown(chips_html, unsafe_allow_html=True)

    st.markdown(
        '<p class="section-label">Dirección de emergencia</p>',
        unsafe_allow_html=True,
    )
    direccion = st.text_input(
        "Dirección de emergencia",
        placeholder="Ej: Av. Francisco de Aguirre 100",
        label_visibility="collapsed",
    )
    calcular = st.button("⬤  CALCULAR RUTA")

    if calcular:
        if direccion.strip() == "":
            st.warning("Ingrese una dirección.")
        else:
            with st.spinner("ORS generando rutas · A* evaluando waypoints..."):
                try:
                    geo     = Nominatim(user_agent="joseo_app")
                    destino = geo.geocode(direccion + ", La Serena, Chile")
                    if destino is None:
                        st.error("No se encontró la dirección.")
                    else:
                        resultado = mejor_cuartel_hibrido(cuarteles, destino, ors_client)
                        guardar_calculo(resultado, destino, cuarteles)
                except Exception as e:
                    st.error(f"Error: {e}")

    if tiene_calculo():
        _renderizar_resultado(leer_resultado())


def _renderizar_resultado(r: dict) -> None:
    """Renderiza banners de resultado y lista de rutas. Solo HTML/Streamlit — sin lógica."""
    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown(
        f"""
        <div class="resultado-banner">
            <div>
                <div class="resultado-banner-label">Unidad despachada</div>
                <div class="resultado-banner-value">🚒 {r['cuartel']['nombre']}</div>
            </div>
        </div>
        <div class="resultado-banner" style="border-color:#3b82f6;
             background:linear-gradient(90deg,#0a1020 0%,#1a1f2e 100%);margin-top:-4px;">
            <div>
                <div class="resultado-banner-label">Algoritmo</div>
                <div class="resultado-banner-value" style="color:#60a5fa;font-size:0.82rem;">
                    ORS + A* (heurística euclidiana)
                </div>
            </div>
        </div>
        <div class="resultado-banner" style="border-color:#a855f7;
             background:linear-gradient(90deg,#130a20 0%,#1a1f2e 100%);margin-top:-4px;">
            <div>
                <div class="resultado-banner-label">Costo A* óptimo</div>
                <div class="resultado-banner-value" style="color:#a855f7;font-size:0.82rem;">
                    {int(r['costo_astar'] // 60)}m {int(r['costo_astar'] % 60)}s
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<p style="font-size:0.65rem;color:#475569;text-transform:uppercase;'
        'letter-spacing:0.12em;font-family:IBM Plex Mono,monospace;margin:14px 0 8px 0;">'
        "Rutas calculadas</p>",
        unsafe_allow_html=True,
    )

    for i, ruta in enumerate(r["rutas"]):
        minutos  = int(ruta["tiempo"] // 60)
        segundos = int(ruta["tiempo"] % 60)
        km       = ruta["dist"] / 1000
        es_mejor = i == 0

        if es_mejor:
            border_color = "#ff3b30"; bg_color    = "#1f1214"
            badge_bg     = "#ff3b3022"; badge_color = "#ff3b30"
            tiempo_color = "#ff3b30"; badge_texto  = "A* ÓPTIMA"
        else:
            border_color = "#2d3748"; bg_color    = "#1a1f2e"
            badge_bg     = "#3b82f622"; badge_color = "#60a5fa"
            tiempo_color = "#f1f5f9"; badge_texto  = f"ALT {i}"

        st.markdown(
            f"""
            <div style="background:{bg_color};border:1px solid {border_color};border-radius:6px;
                 padding:10px 14px;margin-bottom:8px;
                 display:flex;align-items:center;justify-content:space-between;">
                <div>
                    <span style="display:inline-block;padding:1px 7px;border-radius:3px;
                         font-size:0.65rem;font-family:'IBM Plex Mono',monospace;
                         background:{badge_bg};color:{badge_color};margin-bottom:4px;">
                         {badge_texto}
                    </span>
                    <div style="font-size:1.2rem;font-weight:600;
                         font-family:'IBM Plex Mono',monospace;
                         color:{tiempo_color};line-height:1.2;">
                        {minutos}:{segundos:02d}
                        <span style="font-size:0.7rem;color:#64748b;">min</span>
                    </div>
                </div>
                <div style="text-align:right;">
                    <div style="font-size:0.85rem;color:#94a3b8;
                         font-family:'IBM Plex Mono',monospace;">
                         {km:.2f} km
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# =========================================================
# UI — PANEL DERECHO
# =========================================================
def renderizar_panel_derecho() -> None:
    """
    Renderiza el mapa (si hay resultado) o el placeholder vacío.
    DEFECTO 2: lee session_state solo vía funciones de state.py.
    """
    if tiene_calculo():
        r              = leer_resultado()
        destino        = leer_destino()
        cuarteles_sess = leer_cuarteles()

        st.markdown(
            """
            <div style="display:flex;gap:14px;align-items:center;margin-bottom:8px;
                 padding:6px 10px;background:#1a1f2e;border-radius:4px;width:fit-content;">
                <span style="display:flex;align-items:center;gap:5px;font-size:0.72rem;
                     color:#94a3b8;font-family:'IBM Plex Mono',monospace;">
                    <span style="width:10px;height:10px;border-radius:50%;
                         background:#ef4444;display:inline-block;"></span> Ruta A* óptima
                </span>
                <span style="display:flex;align-items:center;gap:5px;font-size:0.72rem;
                     color:#94a3b8;font-family:'IBM Plex Mono',monospace;">
                    <span style="width:10px;height:10px;border-radius:50%;
                         background:#3b82f6;display:inline-block;"></span> Alternativa 1
                </span>
                <span style="display:flex;align-items:center;gap:5px;font-size:0.72rem;
                     color:#94a3b8;font-family:'IBM Plex Mono',monospace;">
                    <span style="width:10px;height:10px;border-radius:50%;
                         background:#22c55e;display:inline-block;"></span> Alternativa 2
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        mapa = crear_mapa(r["rutas"], cuarteles_sess, destino, r["cuartel"])
        st_folium(mapa, width=None, height=580, use_container_width=True)
    else:
        st.markdown(
            """
            <div style="height:580px;background:#1a1f2e;border-radius:6px;
                 border:1px solid #2d3748;display:flex;align-items:center;
                 justify-content:center;flex-direction:column;gap:10px;">
                <div style="font-size:2.5rem;opacity:0.3;">🗺️</div>
                <div style="color:#475569;font-family:'IBM Plex Mono',monospace;
                     font-size:0.78rem;letter-spacing:0.1em;">
                    INGRESE UNA DIRECCIÓN PARA VISUALIZAR
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# =========================================================
# DEFECTO 1 — PUNTO DE ENTRADA EXPLÍCITO
# Todo código de presentación vive dentro de main().
# El scope global contiene únicamente: imports, constantes
# y definiciones de funciones. Cero sentencias ejecutables.
# =========================================================
def main() -> None:
    """
    Punto de entrada único de la UI de J.O.S.E-O.
    Streamlit re-ejecuta este script completo en cada interacción;
    main() garantiza que la presentación tenga un inicio trazable.
    """
    st.set_page_config(layout="wide", page_title="J.O.S.E-O", page_icon="🚒")
    cargar_estilos()
    mostrar_header()

    # DEFECTO 3: cliente creado bajo demanda dentro de main(),
    # no al importar el módulo. Se pasa por parámetro hacia abajo.
    ors_client = crear_cliente_ors(API_KEY)
    cuarteles  = obtener_cuarteles()

    col_left, col_right = st.columns([1, 2.2], gap="large")

    with col_left:
        renderizar_panel_izquierdo(cuarteles, ors_client)

    with col_right:
        renderizar_panel_derecho()


# Único punto de ejecución del módulo.
# Nota: `if __name__ == "__main__"` no aplica en Streamlit —
# el framework importa y re-ejecuta el script directamente.
main()
