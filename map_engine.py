# map_engine.py
import os
import osmnx as ox
from datetime import datetime
from config import LUGAR, ARCHIVO_MAPA, VELOCIDADES

def cargar_mapa():
    if os.path.exists(ARCHIVO_MAPA):
        G = ox.load_graphml(ARCHIVO_MAPA)
    else:
        G = ox.graph_from_place(LUGAR, network_type="drive")
        ox.save_graphml(G, ARCHIVO_MAPA)

    for u, v, k, data in G.edges(keys=True, data=True):
        highway = data.get("highway", "residential")
        if isinstance(highway, list): highway = highway[0]

        speed = VELOCIDADES.get(highway, 25)
        data["speed_kph"] = speed
        
        length = data.get("length", 1)
        speed_mps = speed * 1000 / 3600
        tiempo_base = length / speed_mps

        # Cálculo de tráfico
        hora = datetime.now().hour
        factor = 1.0
        if 7 <= hora <= 9 or 18 <= hora <= 21: factor = 1.5
        elif 13 <= hora <= 15: factor = 1.2
        
        data["travel_time"] = tiempo_base * factor

    return ox.convert.to_digraph(G, weight="travel_time")