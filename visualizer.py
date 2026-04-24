# visualizer.py
import folium

def extraer_coords(G, ruta):
    coords_finales = []
    if not ruta: return coords_finales

    # Rango de seguridad para La Serena / Coquimbo
    # Latitudes entre -31 y -29 | Longitudes entre -72 y -70
    def es_valido(lat, lon):
        return -31.5 < lat < -29.0 and -72.0 < lon < -70.0

    for u, v in zip(ruta[:-1], ruta[1:]):
        try:
            data = G.get_edge_data(u, v)
            
            # Extraer puntos según geometría o nodos
            puntos_tramo = []
            if data and "geometry" in data:
                ys, xs = data["geometry"].xy
                puntos_tramo = list(zip(ys, xs))
            else:
                puntos_tramo = [
                    (G.nodes[u]['y'], G.nodes[u]['x']),
                    (G.nodes[v]['y'], G.nodes[v]['x'])
                ]
            
            # SOLO añadir puntos que estén dentro del rango de La Serena
            for lat, lon in puntos_tramo:
                if es_valido(lat, lon):
                    coords_finales.append((lat, lon))
                    
        except KeyError:
            continue

    return coords_finales

def render_mapa(G, lista_rutas, cuarteles, origen_coords, destino_loc):
    """Crea el mapa de Folium centrado en el destino."""
    m = folium.Map(
        location=[destino_loc.latitude, destino_loc.longitude], 
        zoom_start=15,
        tiles="cartodbpositron" # Mapa más limpio para ver las rutas
    )
    
    colores = ["red", "blue", "green"]
    
    for i, r in enumerate(lista_rutas):
        pts = extraer_coords(G, r["ruta"])
        if pts:
            folium.PolyLine(
                pts, 
                color=colores[i % len(colores)], 
                weight=6 if i==0 else 4,
                opacity=0.8,
                tooltip=f"Ruta {i+1}"
            ).add_to(m)

    # Marcadores de Cuarteles
    for c in cuarteles:
        folium.Marker(
            [c["lat"], c["lon"]], 
            icon=folium.Icon(color="blue", icon="fire", prefix="fa"),
            tooltip=c["nombre"]
        ).add_to(m)
    
    # Marcador de Siniestro
    folium.Marker(
        [destino_loc.latitude, destino_loc.longitude], 
        icon=folium.Icon(color="red", icon="exclamation-triangle", prefix="fa"),
        tooltip="Siniestro"
    ).add_to(m)
    
    return m