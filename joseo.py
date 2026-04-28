import streamlit as st
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
import openrouteservice
import networkx as nx

# =========================================================
# CONFIG
# =========================================================
LUGAR = "La Serena, Chile"
API_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImFjZGMxNzczOThmYzUyZGRhNDFmNTZhNjNkNGJjMTA0OTRkNzdjMTIxYjhmNjE1MmQ0NDg2YjViIiwiaCI6Im11cm11cjY0In0="

client = openrouteservice.Client(key=API_KEY)

st.set_page_config(layout="wide")
st.title("🚒 J.O.S.E-O | Jerarquía Optimizada de Salidas en Emergencias")

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
# ORS: RUTAS REALES + ALTERNATIVAS
# =========================================================
def obtener_rutas_api(origen, destino):
    coords = [
        (origen["lon"], origen["lat"]),
        (destino.longitude, destino.latitude)
    ]

    res = client.directions(
        coordinates=coords,
        profile="driving-car",
        format="geojson",
        alternative_routes={
            "target_count": 3,
            "weight_factor": 1.6
        }
    )

    rutas = []

    for feature in res["features"]:
        geometry = feature["geometry"]["coordinates"]
        summary = feature["properties"]["summary"]

        rutas.append({
            "ruta": geometry,
            "dist": summary["distance"],
            "tiempo": summary["duration"]
        })

    return rutas

# =========================================================
# A*: ELEGIR MEJOR CUARTEL
# =========================================================
def mejor_cuartel_astar(cuarteles, destino):
    G = nx.Graph()
    G.add_node("DESTINO")

    datos = {}

    for c in cuarteles:
        try:
            rutas = obtener_rutas_api(c, destino)
            mejor_ruta = rutas[0]

            G.add_node(c["nombre"])
            G.add_edge(
                c["nombre"],
                "DESTINO",
                weight=mejor_ruta["tiempo"]
            )

            datos[c["nombre"]] = {
                "cuartel": c,
                "rutas": rutas
            }

        except:
            pass

    mejor = None
    mejor_costo = float("inf")

    for nodo in datos.keys():
        try:
            path = nx.astar_path(
                G,
                nodo,
                "DESTINO",
                heuristic=lambda u, v: 0,
                weight="weight"
            )

            costo = nx.path_weight(G, path, weight="weight")

            if costo < mejor_costo:
                mejor_costo = costo
                mejor = nodo

        except:
            pass

    return datos[mejor]

# =========================================================
# MAPA
# =========================================================
def crear_mapa(rutas, cuarteles, destino, origen):
    m = folium.Map(
        location=[destino.latitude, destino.longitude],
        zoom_start=14
    )

    colores = ["red", "blue", "green"]

    for i, r in enumerate(rutas):
        puntos = [(lat, lon) for lon, lat in r["ruta"]]

        folium.PolyLine(
            puntos,
            color=colores[i],
            weight=8 if i == 0 else 5,
            opacity=0.85,
            tooltip=f"Ruta {i+1}"
        ).add_to(m)

    # cuarteles
    for c in cuarteles:
        if c["nombre"] == origen["nombre"]:
            folium.Marker(
                [c["lat"], c["lon"]],
                tooltip=f"🚒 Sale desde {c['nombre']}",
                popup=f"Origen: {c['nombre']}",
                icon=folium.Icon(color="green", icon="home")
            ).add_to(m)
        else:
            folium.Marker(
                [c["lat"], c["lon"]],
                tooltip=c["nombre"],
                icon=folium.Icon(color="blue", icon="fire")
            ).add_to(m)

    # destino
    folium.Marker(
        [destino.latitude, destino.longitude],
        tooltip="🚨 Emergencia",
        popup="Destino",
        icon=folium.Icon(color="red", icon="info-sign")
    ).add_to(m)

    puntos_total = [(lat, lon) for lon, lat in rutas[0]["ruta"]]
    m.fit_bounds(puntos_total)

    return m

# =========================================================
# APP
# =========================================================
cuarteles = obtener_cuarteles()

st.subheader("🚒 Cuarteles disponibles:")
for c in cuarteles:
    st.write("•", c["nombre"])

direccion = st.text_input("📍 Dirección")

if st.button("🚒 Calcular"):
    if direccion.strip() == "":
        st.warning("Ingrese una dirección.")
    else:
        try:
            geo = Nominatim(user_agent="app")
            destino = geo.geocode(direccion + ", La Serena, Chile")

            if destino is None:
                st.error("No se encontró la dirección.")
            else:
                resultado = mejor_cuartel_astar(cuarteles, destino)

                st.session_state["resultado"] = resultado
                st.session_state["destino"] = destino
                st.session_state["cuarteles"] = cuarteles

        except Exception as e:
            st.error(f"Error: {e}")

# =========================================================
# RESULTADOS
# =========================================================
if "resultado" in st.session_state:
    r = st.session_state["resultado"]
    destino = st.session_state["destino"]
    cuarteles = st.session_state["cuarteles"]

    st.success(f"🚒 Sale desde: {r['cuartel']['nombre']}")
    st.info("🧠 Mejor ruta elegida con A* usando tiempos reales")

    for i, ruta in enumerate(r["rutas"]):
        minutos = int(ruta["tiempo"] // 60)
        segundos = int(ruta["tiempo"] % 60)

        if i == 0:
            st.success(
                f"🔥 Ruta {i+1}: {minutos} min {segundos} s | {ruta['dist']/1000:.2f} km"
            )
        else:
            st.info(
                f"Alternativa {i+1}: {minutos} min {segundos} s | {ruta['dist']/1000:.2f} km"
            )

    st.write("🔴 Roja = Mejor ruta | 🔵 Azul = Alternativa | 🟢 Verde = Alternativa")

    mapa = crear_mapa(
        r["rutas"],
        cuarteles,
        destino,
        r["cuartel"]
    )

    st_folium(mapa, width=1200, height=650)