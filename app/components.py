"""Elementos compartidos de presentación; no acceden a datos ni modelos."""

import streamlit as st


def mostrar_contexto_sidebar(manifest):
    """Mantiene el alcance científico visible desde cualquier página."""
    with st.sidebar:
        st.divider()
        st.markdown("**TFM · BiciMAD**")
        st.caption("Demostración histórica. No es un servicio en tiempo real.")
        st.caption("Modelo y resultados congelados. Sin reentrenamiento ni ajuste de umbrales.")
        st.caption("2022: test final de noviembre-diciembre. 2023: solo viajes descriptivos.")
        st.caption(f"Datos preparados y verificados · {len(manifest['tablas'])} tablas.")
