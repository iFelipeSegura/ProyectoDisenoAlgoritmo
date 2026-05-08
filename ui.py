import streamlit as st

def cargar_estilos():
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');

html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
.stApp { background-color: #0d0f14; color: #e2e8f0; }

.joseo-header {
    display: flex; align-items: center; gap: 12px;
    padding: 18px 0 8px 0; border-bottom: 2px solid #ff3b30; margin-bottom: 20px;
}
.joseo-title {
    font-family: 'IBM Plex Mono', monospace; font-size: 1.6rem;
    font-weight: 600; color: #ffffff; letter-spacing: 0.02em; margin: 0;
}
.joseo-subtitle {
    font-size: 0.75rem; color: #64748b; letter-spacing: 0.08em;
    text-transform: uppercase; margin: 2px 0 0 0;
}
.cuarteles-grid { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 18px; }
.cuartel-chip {
    background: #1a1f2e; border: 1px solid #2d3748; color: #94a3b8;
    padding: 5px 12px; border-radius: 4px; font-size: 0.78rem;
    font-family: 'IBM Plex Mono', monospace; display: inline-flex; align-items: center; gap: 6px;
}
.cuartel-chip::before { content: "▪"; color: #3b82f6; }

.resultado-banner {
    background: linear-gradient(90deg, #0f2010 0%, #1a1f2e 100%);
    border-left: 3px solid #22c55e; padding: 10px 14px;
    border-radius: 0 6px 6px 0; margin-bottom: 12px;
    display: flex; align-items: center; gap: 10px;
}
.resultado-banner-label {
    font-size: 0.7rem; color: #64748b; text-transform: uppercase;
    letter-spacing: 0.1em; font-family: 'IBM Plex Mono', monospace;
}
.resultado-banner-value {
    font-size: 1rem; font-weight: 600; color: #22c55e; font-family: 'IBM Plex Mono', monospace;
}

.stTextInput > div > div > input {
    background-color: #1a1f2e !important; border: 1px solid #2d3748 !important;
    color: #e2e8f0 !important; font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.9rem !important; border-radius: 4px !important;
}
.stButton > button {
    background-color: #ff3b30 !important; color: white !important; border: none !important;
    font-family: 'IBM Plex Mono', monospace !important; font-size: 0.82rem !important;
    letter-spacing: 0.05em !important; padding: 8px 20px !important;
    border-radius: 4px !important; font-weight: 600 !important;
}
.stButton > button:hover { background-color: #cc2f25 !important; }
#MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

def mostrar_header():
    st.markdown("""
<div class="joseo-header">
    <div>
        <p class="joseo-title">🚒 J.O.S.E-O</p>
        <p class="joseo-subtitle">Jerarquía Optimizada de Salidas en Emergencias · La Serena, Chile</p>
    </div>
</div>
""", unsafe_allow_html=True)
