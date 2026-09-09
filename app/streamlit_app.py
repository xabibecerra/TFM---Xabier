"""Entrada de Streamlit. Ejecutar desde la raíz: python -m streamlit run app/streamlit_app.py."""

from pathlib import Path
import sys

import streamlit as st


# Permite importar app.data también si Streamlit se inicia desde otra carpeta.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.data import DatosAppError, cargar_manifiesto
from app.components import mostrar_contexto_sidebar


st.set_page_config(
    page_title="BiciMAD — TFM Xabi",
    page_icon="🚲",
    layout="wide",
    initial_sidebar_state="expanded",
)

pages = {
    "Proyecto": [
        st.Page("pages/inicio.py", title="Inicio", icon="🏠", default=True),
    ],
    "Test final · 2022": [
        st.Page("pages/riesgo_2022.py", title="Riesgo 2022", icon="🗺️"),
        st.Page("pages/recomendaciones.py", title="Recomendaciones", icon="🚲"),
        st.Page("pages/interpretabilidad.py", title="Interpretabilidad", icon="🔎"),
    ],
    "Descriptivo · 2023": [
        st.Page("pages/viajes_2023.py", title="Viajes 2023", icon="📊"),
    ],
}

selected_page = st.navigation(pages, position="sidebar", expanded=True)

try:
    # Solo lee el manifiesto. Las tablas se cargarán cuando las páginas las necesiten.
    manifest = cargar_manifiesto()
except (DatosAppError, OSError) as error:
    st.error(f"No se puede iniciar la aplicación con los datos preparados: {error}")
    st.info("Comprueba la fase 8 desde Terminal con: python -m app.data")
    st.stop()

mostrar_contexto_sidebar(manifest)
selected_page.run()
