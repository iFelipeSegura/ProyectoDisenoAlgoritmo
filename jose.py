# =========================================================
# 🚒 SISTEMA RUTAS BOMBEROS - FIX TOTAL
# =========================================================

import os
import osmnx as ox
import networkx as nx
import folium
import streamlit as st
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim

LUGAR = "La Serena, Chile"
ARCHIVO = "mapa.graphml"

st.set_page_config(layout="wide")
st.title("🚒 J.O.S.E-O ||Jerarquía Optimizada de Salidas en Emergencias")

# =========================================================
# MAPA (CON TIEMPOS REALES + FALLBACK)
# =========================================================
@st.cache_resource
def cargar_mapa():

    if os.path.exists(ARCHIVO):
        G = ox.load_graphml(ARCHIVO)
    else:
        G = ox.graph_from_place(LUGAR, network_type="drive")

        # 🔥 agregar velocidad y tiempo
        G = ox.add_edge_speeds(G)
        G = ox.add_edge_travel_times(G)

        # 🔥 FIX CRÍTICO: evitar tiempos 0
        for u, v, k, data in G.edges(keys=True, data=True):

            length = data.get("length", 10)  # mínimo 10m
            speed = data.get("speed_kph", 30)  # fallback

            speed_mps = max(speed * 1000 / 3600, 5)  # mínimo 5 m/s

            tiempo = length / speed_mps

            # penalización urbana
            tiempo += 5
            tiempo *= 1.3

            data["travel_time"] = max(tiempo, 1)  # 🔥 nunca 0

        ox.save_graphml(G, ARCHIVO)

    # grafo conectado
    largest = max(nx.strongly_connected_components(G), key=len)
    G = G.subgraph(largest).copy()

    return G


# =========================================================
# CUARTELES (CON FALLBACK REAL)
# =========================================================
@st.cache_data
def obtener_cuarteles():

    try:
        gdf = ox.features_from_place(LUGAR, {"amenity": "fire_station"})
    except:
        gdf = None

    lista = []

    if gdf is not None and len(gdf) > 0:
        for _, row in gdf.iterrows():
            if row.geometry:
                p = row.geometry.centroid
                lista.append({
                    "nombre": row.get("name", "Cuartel"),
                    "lat": p.y,
                    "lon": p.x
                })

    # 🔥 fallback manual (La Serena real)
    if not lista:
        lista = [
            {"nombre": "1ra Compañía", "lat": -29.9045, "lon": -71.2519},
            {"nombre": "2da Compañía", "lat": -29.9070, "lon": -71.2600},
            {"nombre": "3ra Compañía", "lat": -29.9200, "lon": -71.2500},
            {"nombre": "4ta Compañía", "lat": -29.8800, "lon": -71.2400},
        ]

    return lista


# =========================================================
# HEURÍSTICA
# =========================================================
def heuristica(G, u, v):
    y1, x1 = G.nodes[u]['y'], G.nodes[u]['x']
    y2, x2 = G.nodes[v]['y'], G.nodes[v]['x']

    dist = ox.distance.euclidean_dist_vec(y1, x1, y2, x2)
    return dist / (60 * 1000 / 3600)


# =========================================================
# A*
# =========================================================
def ruta_astar(G, origen, destino):

    o = ox.distance.nearest_nodes(G, origen["lon"], origen["lat"])
    d = ox.distance.nearest_nodes(G, destino.longitude, destino.latitude)

    ruta = nx.astar_path(G, o, d,
                         heuristic=lambda u, v: heuristica(G, u, v),
                         weight="travel_time")

    tiempo = nx.path_weight(G, ruta, weight="travel_time")

    return ruta, tiempo


# =========================================================
# ALTERNATIVAS FORZADAS
# =========================================================
def rutas_alternativas(G, ruta_base, origen, destino):

    rutas = []
    G_temp = G.copy()

    for i in range(3):

        # penalizar ruta anterior
        for u, v in zip(ruta_base[:-1], ruta_base[1:]):
            if G_temp.has_edge(u, v):
                for k in G_temp[u][v]:
                    G_temp[u][v][k]["travel_time"] *= 2

        try:
            ruta, tiempo = ruta_astar(G_temp, origen, destino)
            rutas.append({"ruta": ruta, "tiempo": tiempo})
            ruta_base = ruta
        except:
            break

    return rutas


# =========================================================
# MAPA
# =========================================================
def crear_mapa(G, rutas, cuarteles, destino):

    m = folium.Map(
        location=[destino.latitude, destino.longitude],
        zoom_start=14
    )

    colores = ["red", "blue", "green", "purple"]

    for i, r in enumerate(rutas):
        coords = [(G.nodes[n]['y'], G.nodes[n]['x']) for n in r["ruta"]]

        folium.PolyLine(
            coords,
            color=colores[i],
            weight=6 if i == 0 else 3,
            tooltip=f"{r['tiempo']/60:.1f} min"
        ).add_to(m)

    # 🚒 cuarteles SIEMPRE visibles
    for c in cuarteles:
        folium.Marker(
            [c["lat"], c["lon"]],
            tooltip=c["nombre"],
            icon=folium.Icon(color="blue", icon="fire")
        ).add_to(m)

    # destino
    folium.Marker(
        [destino.latitude, destino.longitude],
        icon=folium.Icon(color="red"),
        tooltip="Emergencia"
    ).add_to(m)

    return m


# =========================================================
# APP
# =========================================================
G = cargar_mapa()
cuarteles = obtener_cuarteles()

st.subheader("🚒 Cuarteles disponibles:")
for c in cuarteles:
    st.write("•", c["nombre"])

direccion = st.text_input("📍 Dirección")

if direccion:
    geolocator = Nominatim(user_agent="app")
    loc = geolocator.geocode(direccion)

    if loc:

        if st.button("🚒 Calcular"):

            mejor = min(
                cuarteles,
                key=lambda c: ((c["lat"] - loc.latitude)**2 + (c["lon"] - loc.longitude)**2)
            )

            ruta_main, tiempo_main = ruta_astar(G, mejor, loc)

            rutas = [{"ruta": ruta_main, "tiempo": tiempo_main}]

            rutas.extend(rutas_alternativas(G, ruta_main, mejor, loc))

            st.session_state["rutas"] = rutas
            st.session_state["destino"] = loc
            st.session_state["cuarteles"] = cuarteles


# =========================================================
# RESULTADOS
# =========================================================
if "rutas" in st.session_state:

    rutas = st.session_state["rutas"]

    for i, r in enumerate(rutas):
        if i == 0:
            st.success(f"🔥 Mejor: {r['tiempo']/60:.2f} min")
        else:
            st.info(f"Alt {i}: {r['tiempo']/60:.2f} min")

    mapa = crear_mapa(
        G,
        rutas,
        st.session_state["cuarteles"],
        st.session_state["destino"]
    )

    st_folium(mapa, width=1200, height=600)