"""
state.py — J.O.S.E-O v3.0
Capa de abstracción sobre st.session_state.

Contrato: ningún otro módulo lee ni escribe st.session_state directamente.
Toda persistencia de datos de sesión pasa por las funciones de este módulo.
"""
import streamlit as st

# Claves internas: un único punto de cambio si se renombran
_KEY_RESULTADO = "resultado"
_KEY_DESTINO   = "destino"
_KEY_CUARTELES = "cuarteles"


def guardar_calculo(resultado: dict, destino, cuarteles: list) -> None:
    """Persiste el resultado completo de un cálculo en la sesión actual."""
    st.session_state[_KEY_RESULTADO] = resultado
    st.session_state[_KEY_DESTINO]   = destino
    st.session_state[_KEY_CUARTELES] = cuarteles


def tiene_calculo() -> bool:
    """True si existe un resultado válido en sesión; False en caso contrario."""
    return _KEY_RESULTADO in st.session_state


def leer_resultado() -> dict:
    """Retorna el dict con cuartel, rutas y costo A* del último cálculo."""
    return st.session_state[_KEY_RESULTADO]


def leer_destino():
    """Retorna el objeto Location (geopy) del destino geocodificado."""
    return st.session_state[_KEY_DESTINO]


def leer_cuarteles() -> list:
    """Retorna la lista de cuarteles usada en el último cálculo."""
    return st.session_state[_KEY_CUARTELES]
