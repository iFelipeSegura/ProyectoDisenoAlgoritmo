# navigation.py
import networkx as nx
import osmnx as ox

def heuristica(G, u, v):
    """Calcula la distancia de círculo máximo para A*."""
    y1, x1 = G.nodes[u]['y'], G.nodes[u]['x']
    y2, x2 = G.nodes[v]['y'], G.nodes[v]['x']
    
    try:
        dist = ox.distance.great_circle(y1, x1, y2, x2)
    except AttributeError:
        dist = ox.distance.great_circle_vec(y1, x1, y2, x2)
        
    return dist / 25 

def calcular_ruta_astar(G, origen_coords, destino_node):
    """Calcula la ruta óptima."""
    o_node = ox.distance.nearest_nodes(G, origen_coords["lon"], origen_coords["lat"])
    
    try:
        ruta = nx.astar_path(
            G, o_node, destino_node,
            heuristic=lambda u, v: heuristica(G, u, v),
            weight="travel_time"
        )
        
        # CORRECCIÓN AQUÍ: Para DiGraph usamos G[u][v] directamente
        tiempo = sum(G[u][v]["travel_time"] for u, v in zip(ruta[:-1], ruta[1:]))
        
        return {"ruta": ruta, "tiempo": tiempo}
    except (nx.NetworkXNoPath, nx.NodeNotFound, KeyError):
        return {"ruta": [], "tiempo": float('inf')}

def obtener_alternativas(G, origen_coords, destino_node, k=3):
    """Busca rutas alternativas."""
    o_node = ox.distance.nearest_nodes(G, origen_coords["lon"], origen_coords["lat"])
    rutas_encontradas = []
    
    try:
        gen = nx.shortest_simple_paths(G, o_node, destino_node, weight="travel_time")
        for i, r in enumerate(gen):
            if i >= k: break
            # CORRECCIÓN AQUÍ TAMBIÉN
            t = sum(G[u][v]["travel_time"] for u, v in zip(r[:-1], r[1:]))
            rutas_encontradas.append({"ruta": r, "tiempo": t})
    except:
        pass
    return rutas_encontradas