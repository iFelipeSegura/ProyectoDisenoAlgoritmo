# =========================================================
# 🚒 J.O.S.E-O FINAL PRO - ESTABLE Y FUNCIONAL
# =========================================================

import os
import osmnx as ox
import networkx as nx
import folium
import streamlit as st
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from datetime import datetime

LUGAR = "La Serena, Coquimbo, Chile"
ARCHIVO = "mapa.graphml"

st.set_page_config(layout="wide")
st.title("🚒 Sistema Inteligente de Rutas (A*)")

# =========================================================
# MAPA
# =========================================================
@st.cache_resource
def cargar_mapa():
    if os.path.exists(ARCHIVO):
        G = ox.load_graphml(ARCHIVO)
    else:
        G = ox.graph_from_place(LUGAR, network_type="drive")
        ox.save_graphml(G, ARCHIVO)

    velocidades = {
        "motorway": 90,
        "trunk": 70,
        "primary": 50,
        "secondary": 40,
        "tertiary": 35,
        "residential": 25,
        "living_street": 15
    }

    for u, v, k, data in G.edges(keys=True, data=True):

        highway = data.get("highway", "residential")
        if isinstance(highway, list):
            highway = highway[0]

        speed = velocidades.get(highway, 25)
        data["speed_kph"] = speed

        length = data.get("length", 1)
        speed_mps = speed * 1000 / 3600

        tiempo = length / speed_mps

        # tráfico simulado
        hora = datetime.now().hour
        factor = 1.0

        if 7 <= hora <= 9 or 18 <= hora <= 21:
            factor = 1.5
        elif 13 <= hora <= 15:
            factor = 1.2

        if highway in ["primary", "secondary"]:
            factor *= 1.1

        data["travel_time"] = tiempo * factor

    # 🔥 CLAVE
    G = ox.convert.to_digraph(G, weight="travel_time")

    return G

# =========================================================
# CUARTELES
# =========================================================
@st.cache_data
def obtener_cuarteles():
    gdf = ox.features_from_place(LUGAR, {"amenity": "fire_station"})
    lista = []

    for _, row in gdf.iterrows():
        if row.geometry:
            p = row.geometry.centroid
            lista.append({
                "nombre": row.get("name", "Cuartel"),
                "lat": p.y,
                "lon": p.x
            })
    return lista

# =========================================================
# HEURÍSTICA A*
# =========================================================
def heuristica(G, u, v):
    y1, x1 = G.nodes[u]['y'], G.nodes[u]['x']
    y2, x2 = G.nodes[v]['y'], G.nodes[v]['x']

    dist = ox.distance.euclidean_dist_vec(y1, x1, y2, x2)
    return dist / 10  # m/s

# =========================================================
# A*
# =========================================================
def ruta_astar(G, origen, destino):

    o = ox.distance.nearest_nodes(G, origen["lon"], origen["lat"])
    d = ox.distance.nearest_nodes(G, destino.longitude, destino.latitude)

    ruta = nx.astar_path(
        G, o, d,
        heuristic=lambda u, v: heuristica(G, u, v),
        weight="travel_time"
    )

    tiempo = sum(G[u][v][0]["travel_time"] for u, v in zip(ruta[:-1], ruta[1:]))

    return {"ruta": ruta, "tiempo": tiempo}

# =========================================================
# RUTAS ALTERNATIVAS
# =========================================================
def rutas_alternativas(G, origen, destino, k=3):

    o = ox.distance.nearest_nodes(G, origen["lon"], origen["lat"])
    d = ox.distance.nearest_nodes(G, destino.longitude, destino.latitude)

    rutas = []

    try:
        gen = nx.shortest_simple_paths(G, o, d, weight="travel_time")

        for i, ruta in enumerate(gen):
            if i >= k:
                break

            tiempo = sum(G[u][v][0]["travel_time"] for u, v in zip(ruta[:-1], ruta[1:]))

            rutas.append({"ruta": ruta, "tiempo": tiempo})

    except:
        pass

    return rutas

# =========================================================
# MEJOR CUARTEL
# =========================================================
def mejor_cuartel(G, cuarteles, destino):
    mejor = None
    mejor_t = float("inf")

    for c in cuarteles:
        try:
            r = ruta_astar(G, c, destino)
            if r["tiempo"] < mejor_t:
                mejor = c
                mejor_t = r["tiempo"]
        except:
            continue

    return mejor

# =========================================================
# GEOMETRÍA ROBUSTA
# =========================================================
def obtener_coords_ruta(G, ruta):
    coords = []

    for u, v in zip(ruta[:-1], ruta[1:]):
        data = G.get_edge_data(u, v)

        if not data:
            continue

        edge = list(data.values())[0]

        if "geometry" in edge:
            xs, ys = edge["geometry"].xy
            coords.extend(list(zip(ys, xs)))
        else:
            coords.append((G.nodes[u]['y'], G.nodes[u]['x']))
            coords.append((G.nodes[v]['y'], G.nodes[v]['x']))

    if len(coords) == 0:
        return None

    return coords

# =========================================================
# MAPA
# =========================================================
def crear_mapa(G, rutas, cuarteles, origen, destino):

    m = folium.Map(
        location=[destino.latitude, destino.longitude],
        zoom_start=14,
        control_scale=True
    )

    # 🔴 A*
    coords = obtener_coords_ruta(G, rutas[0]["ruta"])
    tiempo_main = rutas[0]["tiempo"] / 60

    if coords:
        folium.PolyLine(
            coords,
            color="red",
            weight=8,
            tooltip=f"A* - {tiempo_main:.1f} min"
        ).add_to(m)

    # 🔵 alternativas
    for r in rutas[1:]:
        coords = obtener_coords_ruta(G, r["ruta"])

        if coords:
            folium.PolyLine(
                coords,
                color="blue",
                weight=4,
                opacity=0.6,
                tooltip=f"Alt - {r['tiempo']/60:.1f} min"
            ).add_to(m)

    # 📍 cuarteles
    for c in cuarteles:
        folium.Marker(
            [c["lat"], c["lon"]],
            tooltip=c["nombre"],
            icon=folium.Icon(color="blue", icon="fire")
        ).add_to(m)

    # origen
    folium.Marker(
        [origen["lat"], origen["lon"]],
        tooltip="Origen",
        icon=folium.Icon(color="green")
    ).add_to(m)

    # destino
    folium.Marker(
        [destino.latitude, destino.longitude],
        tooltip="Destino",
        icon=folium.Icon(color="red")
    ).add_to(m)

    folium.LayerControl().add_to(m)

    return m

# =========================================================
# APP
# =========================================================
G = cargar_mapa()
cuarteles = obtener_cuarteles()

st.subheader("🚒 Cuarteles")
for c in cuarteles:
    st.write(f"• {c['nombre']}")

direccion = st.text_input("📍 Dirección")

if direccion:
    geolocator = Nominatim(user_agent="app")
    loc = geolocator.geocode(direccion)

    if loc:
        st.success(loc.address)

        if st.button("🚒 Calcular rutas"):

            mejor = mejor_cuartel(G, cuarteles, loc)

            if mejor:
                ruta_main = ruta_astar(G, mejor, loc)
                rutas = rutas_alternativas(G, mejor, loc, k=3)

                rutas.insert(0, ruta_main)

                st.session_state["rutas"] = rutas
                st.session_state["origen"] = mejor
                st.session_state["destino"] = loc
            else:
                st.error("No se encontró ruta válida")

# =========================================================
# RESULTADOS
# =========================================================
if "rutas" in st.session_state:

    rutas = st.session_state["rutas"]

    st.subheader("⏱️ Comparación de rutas")

    for i, r in enumerate(rutas):
        minutos = max(r["tiempo"] / 60, 0.1)
        if i == 0:
            st.success(f"🔥 A* (mejor): {minutos:.2f} min")
        else:
            st.info(f"Alternativa {i}: {minutos:.2f} min")

    mapa = crear_mapa(
        G,
        rutas,
        cuarteles,
        st.session_state["origen"],
        st.session_state["destino"]
    )

    st_folium(mapa, width=1200, height=600)