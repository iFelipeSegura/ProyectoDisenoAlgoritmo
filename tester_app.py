import streamlit as st
import joseo  # Importamos tu archivo principal para usar sus funciones

st.set_page_config(page_title="Dashboard de Testing J.O.S.E-O", layout="wide")

st.title("🧪 Dashboard de Pruebas de Software")
st.write("Probando la lógica de `joseo.py` sin alterar su código fuente.")

# --- DEFINICIÓN DE LOS TESTS ---

def test_caja_blanca():
    st.subheader("1. Prueba de Caja Blanca (Control de Errores)")
    # Simulamos datos para forzar la lógica interna
    cuarteles_con_error = [
        {"nombre": "Cuartel Invalido", "lat": 0, "lon": 0},
        {"nombre": "1ra Compañía (Real)", "lat": -29.9015, "lon": -71.2519}
    ]
    
    # Mock del objeto destino
    class Destino:
        latitude = -29.9045
        longitude = -71.2519
        
    try:
        # Llamamos a la función que vive en joseo.py
        with st.spinner("Ejecutando lógica interna de A*..."):
            resultado = joseo.mejor_cuartel_astar(cuarteles_con_error, Destino())
        
        if resultado['cuartel']['nombre'] == "1ra Compañía (Real)":
            st.success("✅ PASADO: El algoritmo detectó el error interno y seleccionó el camino válido.")
        else:
            st.error("❌ FALLADO: El algoritmo devolvió un resultado inesperado.")
    except Exception as e:
        st.error(f"❌ FALLADO: La lógica de caja blanca se rompió: {e}")

def test_caja_gris():
    st.subheader("2. Prueba de Caja Gris (Validación de Datos API)")
    try:
        # Probamos la comunicación con OpenRouteService usando la función de joseo.py
        cuartel_test = {"nombre": "Test", "lat": -29.9015, "lon": -71.2519}
        class DestinoTest:
            latitude = -29.9100
            longitude = -71.2600
            
        with st.spinner("Consultando servidor externo de rutas..."):
            rutas = joseo.obtener_rutas_api(cuartel_test, DestinoTest())
        
        if rutas and 'tiempo' in rutas[0]:
            st.success(f"✅ PASADO: La API externa entregó datos compatibles. Tiempo: {rutas[0]['tiempo']}ms")
            st.json(rutas[0]) # Mostramos los datos que vienen de la "caja gris"
        else:
            st.error("❌ FALLADO: La estructura de la API ha cambiado o no devolvió datos.")
    except Exception as e:
        st.error(f"❌ FALLADO: Error de integración: {e}")

# --- INTERFAZ DEL TESTER ---

col1, col2 = st.columns(2)

if col1.button("Ejecutar Test Caja Blanca"):
    test_caja_blanca()

if col2.button("Ejecutar Test Caja Gris"):
    test_caja_gris()