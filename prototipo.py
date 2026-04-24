#pip install osmnx networkx folium geopy // Librerias requeridas OJO
# =========================================================
# SISTEMA DE RUTAS PARA BOMBEROS - A* CON MAPA REAL
# Ciudad: La Serena / Coquimbo, Chile
# Librerías: OSMnx + NetworkX
# =========================================================
import osmnx as ox
import networkx as nx
import folium
from geopy.geocoders import Nominatim
from datetime import timedelta

# =========================================================
# 1. CONFIGURACIÓN Y CARGA DE DATOS REALES
# =========================================================
print("📥 Descargando mapa vial de La Serena y Coquimbo...")
lugar = "La Serena, Coquimbo, Chile"
# Descargamos el grafo y configuramos velocidades y tiempos
grafo = ox.graph_from_place(lugar, network_type="drive")
grafo = ox.add_edge_speeds(grafo)        # Agrega límites de velocidad (km/h)
grafo = ox.add_edge_travel_times(grafo)  # Calcula tiempo de viaje por calle
print("✅ Mapa cargado y procesado.")

# =========================================================
# 2. GEOLOCALIZACIÓN DE DIRECCIONES
# =========================================================
geolocator = Nominatim(user_agent="bomberos_app")

# Ingresa direcciones reales de la zona
dir_cuartel = "Avenida Francisco de Aguirre 100, La Serena, Chile"
dir_incendio = "Calle Los Clarines 800, Coquimbo, Chile"

print(f"🔍 Localizando: {dir_cuartel}")
loc_origen = geolocator.geocode(dir_cuartel)
print(f"🔍 Localizando: {dir_incendio}")
loc_destino = geolocator.geocode(dir_incendio)

# Convertir a nodos del grafo
origen_node = ox.distance.nearest_nodes(grafo, loc_origen.longitude, loc_origen.latitude)
destino_node = ox.distance.nearest_nodes(grafo, loc_destino.longitude, loc_destino.latitude)

# =========================================================
# 3. ALGORITMO A* OPTIMIZADO POR TIEMPO
# =========================================================
print("🚒 Calculando la ruta más rápida con A*...")

# Heurística: estima el tiempo restante basado en distancia euclidiana
def heuristica_tiempo(u, v):
    pos_u = (grafo.nodes[u]['y'], grafo.nodes[u]['x'])
    pos_v = (grafo.nodes[v]['y'], grafo.nodes[v]['x'])
    dist = ox.distance.euclidean_dist_vec(pos_u[0], pos_u[1], pos_v[0], pos_v[1])
    return dist / 13.8  # Estimación a 50km/h (13.8 m/s)

ruta = nx.astar_path(grafo, origen_node, destino_node, 
                     weight='travel_time', 
                     heuristic=heuristica_tiempo)

# Calcular métricas finales
segundos = int(sum(ox.utils_graph.get_route_edge_attributes(grafo, ruta, 'travel_time')))
distancia_metros = int(sum(ox.utils_graph.get_route_edge_attributes(grafo, ruta, 'length')))
eta = str(timedelta(seconds=segundos))

print(f"✅ ¡Ruta encontrada!")
print(f"📊 Resumen: {distancia_metros/1000:.2f} km | ETA: {eta} min:seg")

# =========================================================
# 4. VISUALIZACIÓN INTERACTIVA (FOLIUM)
# =========================================================
ruta_coords = [(grafo.nodes[n]['y'], grafo.nodes[n]['x']) for n in ruta]
mapa = folium.Map(location=[loc_origen.latitude, loc_origen.longitude], zoom_start=13)

# Dibujar la ruta
folium.PolyLine(ruta_coords, color="red", weight=6, opacity=0.8).add_to(mapa)

# Marcadores
folium.Marker([loc_origen.latitude, loc_origen.longitude], 
              popup="Cuartel", icon=folium.Icon(color='blue', icon='home')).add_to(mapa)
folium.Marker([loc_destino.latitude, loc_destino.longitude], 
              popup=f"INCENDIO - ETA: {eta}", icon=folium.Icon(color='red', icon='fire')).add_to(mapa)

# Guardar el resultado
mapa.save("emergencia_real.html")
print("🗺️ Archivo 'emergencia_real.html' generado. Ábrelo en tu navegador.")