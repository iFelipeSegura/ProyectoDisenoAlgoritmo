"""
app.py — J.O.S.E-O v3.0
Ruteo híbrido ORS + A* para vehículos de emergencia en La Serena.

Correcciones QA-Report-2026-Q2 (primera ronda):
  D1: toda la UI encapsulada en main().
  D2: acceso a session_state delegado a state.py.
  D3: cliente ORS creado bajo demanda vía crear_cliente_ors().

Correcciones QA-Report-2026-Q2 v2 (esta ronda):
  D1: timeout=10s en cliente ORS — RNF-02 (Rendimiento).
  D2: st.warning() eliminado de lógica de negocio — RF-02 (Resiliencia Silenciosa).
      Errores individuales de cuartel → logging.warning(), nunca a la UI.
  D3: error HTTP 400 de ORS → DireccionFueraDeCobertura (excepción semántica propia).
      La UI intercepta y muestra mensaje amigable, no JSON crudo.
  ARQ: main() protegido con if __name__ == "__main__" para testabilidad.
       NOTA: en Streamlit, __name__ SÍ es "__main__" al ejecutar con
       'streamlit run app.py', por lo que el guard es válido y funciona.
       Su beneficio real: importar app.py en un test NO dispara main().
"""
import logging
import math

import folium
import networkx as nx
import openrouteservice
import streamlit as st
from geopy.geocoders import Nominatim
from streamlit_folium import st_folium

from ui import cargar_estilos, mostrar_header
from state import (
    guardar_calculo,
    tiene_calculo,
    leer_resultado,
    leer_destino,
    leer_cuarteles,
)

logging.basicConfig(level=logging.WARNING)
_log = logging.getLogger(__name__)

# =========================================================
# CONFIG
# =========================================================
LUGAR       = "La Serena, Chile"
API_KEY     = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImFjZGMxNzczOThmYzUyZGRhNDFmNTZhNjNkNGJjMTA0OTRkNzdjMTIxYjhmNjE1MmQ0NDg2YjViIiwiaCI6Im11cm11cjY0In0="
ORS_TIMEOUT = 10  # segundos — RNF-02


# =========================================================
# EXCEPCIÓN SEMÁNTICA PROPIA — D3 v2
# Separar "destino fuera de cobertura" de errores genéricos.
# La UI reacciona distinto: cobertura → mensaje de negocio.
# =========================================================
class DireccionFueraDeCobertura(Exception):
    """ORS rechazó la ruta porque la distancia supera los 100 km."""


# =========================================================
# CLIENTE ORS — factory con timeout (D1 v2)
# =========================================================
def crear_cliente_ors(api_key: str, timeout: int = ORS_TIMEOUT) -> openrouteservice.Client:
    """
    Factory del cliente ORS.
    - Creado bajo demanda en main(), no en scope global.
    - timeout evita bloqueos indefinidos bajo red adversa (RNF-02).
    """
    return openrouteservice.Client(key=api_key, timeout=timeout)


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
# ORS: OBTENER RUTAS — manejo explícito HTTP 400 (D3 v2)
# =========================================================
def obtener_rutas_api(
    origen: dict,
    destino,
    ors_client: openrouteservice.Client,
) -> list:
    """
    Llama a ORS y retorna hasta 3 rutas alternativas.
    Inyección de dependencias: recibe ors_client como parámetro.

    Manejo de errores ORS:
      HTTP 400 → DireccionFueraDeCobertura (distancia > 100 km).
      Otros ApiError → se re-lanzan para que el caller los maneje.
    """
    coords = [
        (origen["lon"], origen["lat"]),
        (destino.longitude, destino.latitude),
    ]
    try:
        res = ors_client.directions(
            coordinates=coords,
            profile="driving-car",
            format="geojson",
            alternative_routes={"target_count": 3, "weight_factor": 1.6},
        )
    except openrouteservice.exceptions.ApiError as e:
        if e.args[0] == 400:
            raise DireccionFueraDeCobertura(
                "La dirección ingresada supera el límite de 100 km "
                "permitido por el servicio de rutas. "
                "Ingrese una dirección dentro de La Serena o sus alrededores."
            ) from e
        raise

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
# HEURÍSTICA EUCLIDIANA
# =========================================================
def heuristica_euclidiana(coord_nodo: tuple, coord_destino: tuple) -> float:
    """
    Tiempo estimado desde un nodo hasta el destino.
    Calibrada a 50 km/h (13.9 m/s). Admisible → A* garantiza óptimo.
    """
    lon_u, lat_u = coord_nodo
    lon_d, lat_d = coord_destino
    dx     = (lon_u - lon_d) * 111_000 * math.cos(math.radians(lat_u))
    dy     = (lat_u - lat_d) * 111_000
    dist_m = math.sqrt(dx**2 + dy**2)
    return dist_m / 13.9


# =========================================================
# CONSTRUIR GRAFO DESDE WAYPOINTS ORS
# =========================================================
def construir_grafo_desde_ruta(ruta_coords: list, tiempo_total: float) -> nx.DiGraph:
    """
    Waypoints ORS → grafo dirigido.
    Aristas ponderadas por tiempo proporcional a longitud de segmento.
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
        G.add_edge(i, i + 1, weight=tiempo_total * proporcion)

    return G


# =========================================================
# A* SOBRE GRAFO DE WAYPOINTS
# =========================================================
def astar_sobre_ruta(G: nx.DiGraph, coord_destino: tuple) -> tuple:
    """A* nodo 0 → nodo N. f(n) = g(n) + h(n), heurística euclidiana."""
    nodo_inicio  = 0
    nodo_destino = max(G.nodes())

    def h(u, _v):
        return heuristica_euclidiana(G.nodes[u]["coords"], coord_destino)

    path  = nx.astar_path(G, nodo_inicio, nodo_destino, heuristic=h, weight="weight")
    costo = nx.path_weight(G, path, weight="weight")
    return path, costo


# =========================================================
# NÚCLEO HÍBRIDO — resiliencia silenciosa (D2 v2)
# =========================================================
def mejor_cuartel_hibrido(
    cuarteles: list,
    destino,
    ors_client: openrouteservice.Client,
) -> dict:
    """
    ORS → grafo → A* por cada cuartel. Selecciona el de menor costo.

    Política de errores (RF-02 Resiliencia Silenciosa):
      DireccionFueraDeCobertura → se propaga (error de negocio, la UI lo muestra).
      Cualquier otro error por cuartel → logging interno, cuartel omitido
      silenciosamente, SIN tocar la UI.
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

        except DireccionFueraDeCobertura:
            raise  # error de negocio: la UI decide cómo mostrarlo

        except Exception as e:
            # D2 v2: silencioso — omitir cuartel sin contaminar la UI
            _log.warning("Cuartel %s omitido: %s", c["nombre"], e)

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

    m.fit_bounds([(lat, lon) for lon, lat in rutas[0]["ruta"]])
    return m


# =========================================================
# UI — PANEL IZQUIERDO
# =========================================================
def renderizar_panel_izquierdo(
    cuarteles: list,
    ors_client: openrouteservice.Client,
) -> None:
    """
    Panel de control izquierdo.
    Único lugar donde DireccionFueraDeCobertura se convierte
    en mensaje amigable para el usuario (D3 v2).
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
                        st.error("No se encontró la dirección. Verifique el nombre e intente nuevamente.")
                    else:
                        resultado = mejor_cuartel_hibrido(cuarteles, destino, ors_client)
                        guardar_calculo(resultado, destino, cuarteles)

                except DireccionFueraDeCobertura as e:
                    # D3 v2: aquí y solo aquí se traduce el error de ORS a lenguaje de usuario
                    st.error(f"⚠️ {e}")

                except Exception as e:
                    st.error(f"Error al calcular la ruta: {e}")

    if tiene_calculo():
        _renderizar_resultado(leer_resultado())


def _renderizar_resultado(r: dict) -> None:
    """Solo presentación — sin lógica de negocio."""
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
            <div style="background:{bg_color};border:1px solid {border_color};
                 border-radius:6px;padding:10px 14px;margin-bottom:8px;
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
    """Renderiza el mapa o el placeholder vacío."""
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
# PUNTO DE ENTRADA — Sugerencia ARQ v2
# =========================================================
def main() -> None:
    """
    Punto de entrada único de J.O.S.E-O.
    Guard if __name__ == "__main__": válido en Streamlit —
    'streamlit run app.py' establece __name__ = "__main__".
    Beneficio: importar app.py en tests no dispara main().
    """
    st.set_page_config(layout="wide", page_title="J.O.S.E-O", page_icon="🚒")
    cargar_estilos()
    mostrar_header()

    ors_client = crear_cliente_ors(API_KEY)
    cuarteles  = obtener_cuarteles()

    col_left, col_right = st.columns([1, 2.2], gap="large")

    with col_left:
        renderizar_panel_izquierdo(cuarteles, ors_client)

    with col_right:
        renderizar_panel_derecho()


if __name__ == "__main__":
    main()
