# 🚒 J.O.S.E-O
**Jerarquía Optimizada de Salidas en Emergencias**  
La Serena, Chile — v0.7.0

---

## Estructura del proyecto

```
joseo/
│
├── app.py              # Archivo principal — corre esto
├── ui.py               # Estilos visuales — no se ejecuta directamente
├── requirements.txt    # Lista de dependencias
└── INSTRUCCIONES.txt   # Este archivo
```

`app.py` importa funciones de `ui.py` automáticamente. Ambos archivos deben estar en la misma carpeta.

---

## Instalación

**Instalar dependencias**

Opción rápida con el archivo incluido:

```bash
pip install -r requirements.txt
```

O instalar cada librería por separado:

```bash
pip install streamlit
pip install folium
pip install streamlit-folium
pip install geopy
pip install openrouteservice
pip install networkx
```

---

## Ejecutar la aplicación

```bash
streamlit run app.py
```

Streamlit abrirá automáticamente el navegador en `http://localhost:8501`.  
Si no abre solo, copiar esa URL y pegarla en el navegador.

---

## Uso

1. Ingresar la dirección del siniestro en el campo de texto  
   *(ejemplo: `Av. Francisco de Aguirre 100`)*
2. Presionar **CALCULAR RUTA**
3. El sistema muestra:
   - El cuartel más cercano en tiempo real
   - El tiempo estimado de llegada
   - La ruta óptima (roja) y hasta 2 alternativas sobre el mapa

> No es necesario escribir "La Serena" — el sistema lo agrega automáticamente.  
> Si la dirección no existe o está fuera de La Serena, aparecerá un mensaje de error.

---

## Cuarteles registrados

| Compañía | Latitud | Longitud |
|---|---|---|
| 1ra Compañía | -29.9045 | -71.2519 |
| 2da Compañía | -29.9070 | -71.2600 |
| 3ra Compañía | -29.9200 | -71.2500 |
| 4ta Compañía | -29.8800 | -71.2400 |

---

## API Key

La aplicación ya viene configurada con una API Key funcional de OpenRouteService.  
En caso de querer reemplazarla, se edita directamente en `app.py`:

```python
API_KEY = "..."
```

---

## Errores comunes

| Error | Causa probable | Solución |
|---|---|---|
| `AuthorizationError` | API Key incorrecta o vencida | Reemplazar la key en `app.py` |
| `No se encontró la dirección` | Dirección fuera de La Serena o mal escrita | Revisar la dirección ingresada |
| `ModuleNotFoundError` | Dependencias no instaladas | Correr `pip install -r requirements.txt` |
| El mapa no carga | Sin conexión o límite diario de ORS alcanzado | Verificar conexión o esperar reset de la API |

---

## Equipo

José Calderón · Eduardo Manzano · Felipe Segura · Ignacio Araya · Benjamín Molina  
**Profesor:** Cristian Cubillos — Universidad de La Serena  
**Cliente:** Cuerpos de Bomberos de La Serena
