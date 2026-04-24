# =========================================================
# SISTEMA DE RUTAS PARA BOMBEROS - A* CON MAPA REAL
# Ciudad: La Serena / Coquimbo, Chile
# Librerías: OSMnx + NetworkX
# Version: 1.0
# Autor: [Tu Nombre]
# =========================================================

"""
Introducción:
Este sistema permite a los bomberos calcular la ruta más rápida hacia un sitio de emergencia a partir de la dirección ingresada por el usuario. 
Utiliza OSMnx para obtener datos de mapas, NetworkX para calcular la ruta y Folium para visualización.
"""

import osmnx as ox
import networkx as nx
import folium
from geopy.geocoders import Nominatim
from datetime import timedelta

def cargar_mapa(lugar):
    """
    Carga el mapa vial de la ciudad especificada y agrega velocidades y tiempos de viaje.

    :param lugar: Cadena con el nombre de la ciudad.
    :return: Grafo de la ciudad.
    """
    print("📥 Descargando mapa vial de La Serena y Coquimbo...")
    grafo = ox.graph_from_place(lugar, network_type="drive")
    grafo = ox.add_edge_speeds(grafo)
    grafo = ox.add_edge_travel_times(grafo)
    print("✅ Mapa cargado y procesado.")
    return grafo

def obtener_geolocalizacion(direccion):
    """
    Obtiene la localización geográfica de una dirección dada.

    :param direccion: Cadena con la dirección.
    :return: Objeto de ubicación o None si no se encuentra.
    """
    geolocator = Nominatim(user_agent="bomberos_app")
    return geolocator.geocode(direccion)

def calcular_ruta(grafo, origen_node, destino_node):
    """
    Calcula la ruta más rápida entre dos nodos usando el algoritmo A*.

    :param grafo: Grafo de la ciudad.
    :param origen_node: Nodo de origen.
    :param destino_node: Nodo de destino.
    :return: Lista de nodos que conforman la ruta.
    """
    def heuristica_tiempo(u, v):
        pos_u = (grafo.nodes[u]['y'], grafo.nodes[u]['x'])
        pos_v = (grafo.nodes[v]['y'], grafo.nodes[v]['x'])
        dist = ox.distance.euclidean_dist_vec(pos_u[0], pos_u[1], pos_v[0], pos_v[1])
        return dist / 13.8  # Estimación a 50km/h

    return nx.astar_path(grafo, origen_node, destino_node, 
                          weight='travel_time', 
                          heuristic=heuristica_tiempo)

def guardar_mapa_interactivo(ruta, loc_origen, loc_destino, eta):
    """
    Guarda un archivo HTML con un mapa interactivo que muestra la ruta.

    :param ruta: Lista de coordenadas de la ruta.
    :param loc_origen: Localización de origen.
    :param loc_destino: Localización de destino.
    :param eta: Tiempo estimado de llegada.
    """
    ruta_coords = [(grafo.nodes[n]['y'], grafo.nodes[n]['x']) for n in ruta]
    mapa = folium.Map(location=[loc_origen.latitude, loc_origen.longitude], zoom_start=13)
    
    folium.PolyLine(ruta_coords, color="red", weight=6, opacity=0.8).add_to(mapa)
    folium.Marker([loc_origen.latitude, loc_origen.longitude], 
                  popup="Cuartel", icon=folium.Icon(color='blue', icon='home')).add_to(mapa)
    folium.Marker([loc_destino.latitude, loc_destino.longitude], 
                  popup=f"INCENDIO - ETA: {eta}", icon=folium.Icon(color='red', icon='fire')).add_to(mapa)
    
    mapa.save("emergencia_real.html")
    print("🗺️ Archivo 'emergencia_real.html' generado. Ábrelo en tu navegador.")

# =========================================================
# 1. CARGAR MAPA
# =========================================================
grafo = cargar_mapa("La Serena, Coquimbo, Chile")

# =========================================================
# 2. OBTENCIÓN DE DIRECCIONES
# =========================================================
dir_cuartel = "Avenida Francisco de Aguirre 100, La Serena, Chile"
loc_origen = obtener_geolocalizacion(dir_cuartel)

dir_incendio = input("📍 Ingresa la dirección del destino (incendio): ")
loc_destino = obtener_geolocalizacion(dir_incendio)

if loc_destino is None:
    print("❌ No se pudo encontrar la dirección. Por favor, verifica e intenta de nuevo.")
else:
    origen_node = ox.distance.nearest_nodes(grafo, loc_origen.longitude, loc_origen.latitude)
    destino_node = ox.distance.nearest_nodes(grafo, loc_destino.longitude, loc_destino.latitude)

    # =========================================================
    # 3. CÁLCULO DE RUTA
    # =========================================================
    print("🚒 Calculando la ruta más rápida con A*...")
    ruta = calcular_ruta(grafo, origen_node, destino_node)

    # Calcular métricas finales
    segundos = int(sum(ox.utils_graph.get_route_edge_attributes(grafo, ruta, 'travel_time')))
    distancia_metros = int(sum(ox.utils_graph.get_route_edge_attributes(grafo, ruta, 'length')))
    eta = str(timedelta(seconds=segundos))

    print(f"✅ ¡Ruta encontrada!")
    print(f"📊 Resumen: {distancia_metros/1000:.2f} km | ETA: {eta} min:seg")

    # =========================================================
    # 4. VISUALIZACIÓN DEL MAPA
    # =========================================================
    guardar_mapa_interactivo(ruta, loc_origen, loc_destino, eta)
