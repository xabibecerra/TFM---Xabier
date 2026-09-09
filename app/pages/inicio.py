"""Inicio del TFM: objetivo, protocolo temporal y alcance del prototipo.

Solo consulta el manifiesto mediante app.data. No calcula métricas del modelo
ni carga tablas grandes. La guía se consulta durante el desarrollo, no al abrir
la aplicación; su propuesta inicial de test 2023 se documenta como sustituida.
"""

from datetime import datetime

import streamlit as st

from app.data import DatosAppError, cargar_manifiesto


def numero(value: int) -> str:
    return f"{value:,}".replace(",", ".")


try:
    manifest = cargar_manifiesto()
    periods = manifest["periodos"]
    counts = manifest["recuentos"]
    policy = manifest["politica_operativa"]
    first_trip, last_trip = (
        datetime.fromisoformat(value) for value in periods["viajes_2023_observados"]
    )
    # Preparar el contenido antes de dibujar la página para no mostrar una portada parcial.
    indicators = [
        ("Observaciones estación-hora", numero(counts["predicciones"]),
         "Filas del test final; una estación aparece en distintas horas."),
        ("Candidatos técnicos", numero(counts["candidatos"]),
         "Señales críticas del modelo, no transferencias garantizadas."),
        ("Transferencias propuestas", numero(counts["transferencias"]),
         "Emparejamientos factibles agregados por escenario horario; no movimientos ejecutados."),
    ]
    units_text = numero(counts["unidades_por_escenarios"])
    policy_text = (
        f"La política del notebook 10 usa una banda de referencia del "
        f"{policy['operational_min_ratio']:.0%}–{policy['operational_max_ratio']:.0%}, "
        f"una distancia máxima de {policy['max_pair_distance_km']:g} km "
        f"y un máximo de {policy['max_units_per_transfer']:g} bicicletas por transferencia. "
        "Son restricciones del escenario, no valores optimizados con el test."
    )
    stages = [
        {"Etapa": "Entrenamiento", "Periodo": periods["entrenamiento"],
         "Uso": "Aprender patrones con datos anteriores al periodo de evaluación."},
        {"Etapa": "Validación", "Periodo": periods["validacion"],
         "Uso": "Comparar y seleccionar antes de abrir el test final."},
        {"Etapa": "Test final", "Periodo": periods["test"],
         "Uso": "Evaluar el modelo congelado; no ajustar con estos resultados."},
        {"Etapa": "Descriptivo independiente", "Periodo": "enero-febrero de 2023 (febrero parcial)",
         "Uso": "Describir viajes observados, sin estados, etiquetas de riesgo ni predicciones."},
    ]
    model_name = manifest["modelo_final"]
except (DatosAppError, OSError, KeyError, TypeError, ValueError) as error:
    st.error(f"No se puede mostrar el resumen metodológico: {error}")
    st.info("Comprueba el manifiesto de la fase 7 y ejecuta python -m app.data antes de continuar.")
    st.stop()

st.title("BiciMAD — Riesgo y apoyo operativo")
st.caption("Trabajo Fin de Máster · Xabi")
st.write(
    "Este proyecto estudia cómo anticipar situaciones críticas en las estaciones de BiciMAD "
    "y convertir las predicciones en propuestas de redistribución explicables. "
    "La aplicación presenta los resultados históricos del TFM para apoyar su consulta y evaluación."
)
st.info(
    "Prototipo histórico de solo lectura. No realiza predicciones en tiempo real, "
    "no entrena el modelo y no recalibra probabilidades ni umbrales."
)

st.subheader("Objetivo y caso de uso")
st.write(
    "Una estación con riesgo de vaciado puede dejar a los usuarios sin bicicletas; "
    "una estación con riesgo de saturación puede dificultar las devoluciones. "
    "El objetivo es identificar estaciones que requieren atención y estudiar si existe "
    "una redistribución compatible con su capacidad, disponibilidad y proximidad a otras estaciones."
)
st.write(
    "El análisis combina viajes históricos, estados de estaciones, información geográfica, "
    "meteorología y calendario en una base estación-hora. Se compararon modelos mediante "
    "validación temporal y se seleccionó XGBoost como modelo final."
)
st.caption(f"Identificador del modelo congelado: {model_name}. No se carga el modelo al abrir esta página.")

for column, (label, value, help_text) in zip(st.columns(3), indicators):
    column.metric(label, value, help=help_text)
st.caption(
    f"Recuentos del manifiesto de resultados. Las {units_text} unidades propuestas se suman "
    "sobre escenarios horarios independientes: no son bicicletas únicas ni redistribuciones ejecutadas."
)

st.subheader("Periodos del experimento")
st.table(stages)
st.caption("2020 queda fuera del entrenamiento principal por su carácter atípico durante la pandemia.")
st.warning(
    "No existen datos de estados de estaciones para enero-febrero de 2023 en este proyecto. "
    "Por eso el test final se sitúa en noviembre-diciembre de 2022 y 2023 se reserva "
    "al análisis descriptivo de viajes. Febrero tiene cobertura parcial."
)
st.caption(
    f"Viajes de 2023 observados desde {first_trip:%d/%m/%Y %H:%M:%S} "
    f"hasta {last_trip:%d/%m/%Y %H:%M:%S}. "
    "Los totales mensuales deben interpretarse teniendo en cuenta esa cobertura desigual."
)

st.subheader("Cómo interpretar el sistema")
signal, logistics, explanation = st.columns(3)
with signal:
    st.markdown("**1. Señal predictiva**")
    st.write("Clasifica el riesgo como estable, vaciado o saturación. Una señal crítica es una candidata técnica, no una orden de intervención.")
with logistics:
    st.markdown("**2. Factibilidad logística**")
    st.write("Contrasta la señal con capacidad, bicicletas, anclajes, reservas y estaciones próximas. Puede asignar una transferencia, cubrir solo parte de la necesidad o dejarla sin resolver.")
with explanation:
    st.markdown("**3. Explicación operativa**")
    st.write("Relaciona la propuesta con el contexto y los factores SHAP globales de su clase. Describe señales del modelo, no causas ni efectos demostrados.")

with st.expander("Reglas de lectura y limitaciones", expanded=False):
    st.markdown(
        "- **Modelo congelado:** no se vuelve a ejecutar el notebook 08 para ajustar el modelo; "
        "el test no se usa para recalibrar ni elegir nuevos umbrales.\n"
        "- **Estaciones estables:** se comprueba `prediction` o `model_action_signal` antes de considerar "
        "una intervención. `critical_risk_type` no activa una acción estable; solo indica el mayor "
        "riesgo relativo. Una estación estable sí puede prestar apoyo logístico compatible.\n"
        "- **Prioridad:** `critical_risk_score` sirve solo para ordenar, no para decidir cantidades "
        "ni crear nuevos umbrales.\n"
        "- **Interpretabilidad:** se comparan ganancia y SHAP y se documentan sus discrepancias. "
        "Los factores globales por clase no sustituyen a explicaciones SHAP locales.\n"
        "- **Errores:** horas y estaciones sensibles se muestran con soporte, falsos negativos y tasa. "
        "Las 08:00, 18:00 y 19:00 son indicadores de cautela, no correcciones del modelo.\n"
        "- **Meteorología:** se consulta el contexto observado. Esta versión no modifica el tiempo "
        "meteorológico para producir nuevas predicciones.\n"
        "- **Alcance operativo:** los emparejamientos no constituyen rutas optimizadas con vehículos, "
        "turnos, tiempos y costes. No se ha demostrado una reducción real de incidencias o costes."
    )
    st.write(policy_text)

st.subheader("Explorar la aplicación")
st.caption("Las cinco páginas ya están disponibles: Inicio, Riesgo 2022, Recomendaciones, Interpretabilidad y Viajes 2023. "
           "El conjunto sigue siendo un prototipo histórico de consulta, no un sistema operativo en producción.")
left, right = st.columns(2)
with left:
    st.page_link("pages/riesgo_2022.py", label="Riesgo 2022", icon="🗺️")
    st.write("Mapa y consulta de predicciones, disponibilidad y contexto por estación y hora del test final.")
    st.page_link("pages/recomendaciones.py", label="Recomendaciones", icon="🚲")
    st.write("Consulta de transferencias propuestas, coberturas parciales y candidatos no resueltos, con explicación operativa.")
with right:
    st.page_link("pages/interpretabilidad.py", label="Interpretabilidad", icon="🔎")
    st.write("Comparación de importancia por ganancia, SHAP global y por clase, y errores con sus denominadores.")
    st.page_link("pages/viajes_2023.py", label="Viajes 2023", icon="📊")
    st.write("Exploración descriptiva de cobertura, actividad, flujos y duración, sin predicciones de riesgo.")

with st.expander("Relación con la Guía TFM Xabi y procedencia", expanded=False):
    st.write(
        "La aplicación desarrolla el apartado «Desarrollo de la aplicación interactiva» de la guía "
        "y conecta la modelización predictiva, la interpretabilidad, el análisis de errores y "
        "el sistema de recomendación operativa. Su finalidad es hacer consultables los resultados "
        "y sus limitaciones desde una perspectiva de operación."
    )
    st.write(
        "Actualización metodológica respecto a la propuesta inicial de la guía: enero-febrero "
        "de 2023 deja de ser el test predictivo por ausencia de estados de estaciones. "
        "El test final pasa a noviembre-diciembre de 2022. Esta decisión evita inventar "
        "disponibilidad o etiquetas de riesgo."
    )
    st.markdown(
        "- **Notebook 08:** evaluación final congelada de noviembre-diciembre de 2022.\n"
        "- **Notebook 09:** importancia, SHAP y análisis de errores.\n"
        "- **Notebook 10:** candidatos y transferencias bajo restricciones operativas.\n"
        "- **Notebook 11:** viajes de 2023, exclusivamente descriptivos.\n"
        "- **Fases 7 y 8 de la aplicación:** preparación y carga de los resultados, sin ejecutar los notebooks."
    )
    st.caption("Los periodos, recuentos, cobertura observada y política de esta portada se leen de manifiesto_app.json.")
