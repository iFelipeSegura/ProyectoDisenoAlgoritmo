import streamlit as st
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
import osmnx as ox

import map_engine
import navigation
import visualizer
from config import LUGAR

st.set_page_config(layout="wide", page_title="J.O.S.E-O")

# --- MEMORIA DEL SISTEMA ---
# Usamos una sola llave para evitar desincronización
if "emergencia_activa" not in st.session_state:
    st.session_state.emergencia_activa = {
        "mapa": None,
        "tiempo": 0,
        "unidad": "",
        "listo": False
    }

# --- CARGA DE DATOS ---
@st.cache_resource
def cargar_recursos_pesados():
    return map_engine.cargar_mapa()

G = cargar_recursos_pesados()

@st.cache_data
def cargar_cuarteles_fijos():
    try:
        gdf = ox.features_from_place(LUGAR, {"amenity": "fire_station"})
        return [{"nombre": r.get("name", "Cuartel"), 
                 "lat": r.geometry.centroid.y, "lon": r.geometry.centroid.x} 
                for _, r in gdf.iterrows() if r.geometry]
    except: return []

cuarteles = cargar_cuarteles_fijos()

# --- BARRA LATERAL ---
with st.sidebar:
    st.title("🚒 Panel J.O.S.E-O")
    direccion = st.text_input("Dirección del siniestro:")
    
    if st.button("🔥 DESPACHAR"):
        if direccion:
            with st.spinner("Trazando ruta óptima..."):
                geolocator = Nominatim(user_agent="joseo_final_v4")
                loc = geolocator.geocode(f"{direccion}, {LUGAR}")
                
                if loc:
                    d_node = ox.distance.nearest_nodes(G, loc.longitude, loc.latitude)
                    mejor_c = min(cuarteles, key=lambda c: navigation.calcular_ruta_astar(G, c, d_node)["tiempo"])
                    ruta_top = navigation.calcular_ruta_astar(G, mejor_c, d_node)
                    
                    # GUARDAMOS TODO EN EL ESTADO
                    st.session_state.emergencia_activa = {
                        "mapa": visualizer.render_mapa(G, [ruta_top], cuarteles, mejor_c, loc),
                        "tiempo": ruta_top['tiempo'] / 60,
                        "unidad": mejor_c['nombre'],
                        "listo": True
                    }
                else:
                    st.error("Dirección no válida.")

# --- ÁREA DE VISUALIZACIÓN ---
st.title("Centro de Monitoreo La Serena")

# Creamos un contenedor vacío que mantendrá el mapa en su lugar
contenedor_mapa = st.container()

# ... (Todo el inicio, cargas y session_state se mantienen igual)

if st.session_state.emergencia_activa["listo"]:
    with contenedor_mapa:
        col1, col2 = st.columns([3, 1])
        with col1:
            # 🔥 LA CLAVE ESTÁ AQUÍ:
            st_folium(
                st.session_state.emergencia_activa["mapa"],
                width=900,
                height=550,
                key="mapa_estacionario",
                # Esto evita que el mapa mande datos a Python cada vez que lo tocas
                returned_objects=[] 
            )
        with col2:
            st.metric("Tiempo estimado", f"{st.session_state.emergencia_activa['tiempo']:.2f} min")
            st.info(f"Unidad: {st.session_state.emergencia_activa['unidad']}")
            if st.button("Finalizar Emergencia"):
                st.session_state.emergencia_activa["listo"] = False
                st.rerun()
else:
    st.info("Sistema en espera. Ingrese datos en el panel izquierdo.")