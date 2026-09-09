"""Importancias y diagnóstico retrospectivo del modelo congelado (fase 13)."""

import pandas as pd
import plotly.express as px
import streamlit as st

from app.data import (DatosAppError, cargar_estaciones_sensibles, cargar_factores_por_clase,
                      cargar_horas_sensibles, cargar_manifiesto, cargar_predicciones, cargar_tabla)
from app.interpretacion import (comparar_importancias, errores_clase, grafico_comparacion,
                                grafico_errores_hora, union_top)
from app.riesgo import CLASES, tabla_falsos_negativos


st.title("Interpretabilidad")
st.caption("Modelo final congelado · test de noviembre-diciembre de 2022")
st.warning("SHAP e importancia identifican señales utilizadas por el modelo, no causas. "
           "Las explicaciones exportadas son factores globales por clase, no explicaciones locales de cada observación.")
st.info("Diagnóstico retrospectivo: no entrena el modelo, no recalcula SHAP y no utiliza probabilidades del test "
        "para recalibrar ni elegir nuevos umbrales. Los filtros solo cambian la presentación.")
try:
    manifest = cargar_manifiesto()
    comparison = cargar_tabla("comparacion_gain_vs_shap")
    by_class = cargar_tabla("shap_importancia_por_clase")
    factors = cargar_factores_por_clase()
    hours = cargar_horas_sensibles()
    months = cargar_tabla("errores_por_mes_2022")
    stations = cargar_estaciones_sensibles()
    catalog = cargar_predicciones(columnas=["station_id", "station_number", "station_name"]).drop_duplicates("station_id")
    metrics = cargar_tabla("metricas_test_2022")
    reports = cargar_tabla("informe_por_clase_test_2022")
except (DatosAppError, OSError) as error:
    st.error(f"No se pueden cargar los resultados de interpretabilidad: {error}")
    st.stop()

model = manifest["modelo_final"]
model_metrics = metrics.loc[metrics.model.eq(model)]
if model_metrics.empty or comparison.empty or by_class.empty:
    st.error("Faltan resultados del modelo congelado o tablas de importancia; no se generan sustitutos.")
    st.stop()
metric = model_metrics.iloc[0]
a, b, c = st.columns(3)
a.metric("F1 macro · test final", f"{metric.f1_macro:.4f}")
b.metric("Exactitud equilibrada", f"{metric.balanced_accuracy:.4f}")
c.metric("Observaciones evaluadas", f"{int(metric.test_rows):,}".replace(",", "."))
with st.expander("Resultados por clase del XGBoost congelado"):
    report = reports.loc[reports.model.eq(model) & reports['class'].isin(['estable', 'riesgo_vaciado', 'riesgo_saturacion'])]
    st.dataframe(report.drop(columns="model").rename(columns={"class": "Clase", "precision": "Precisión", "recall": "Recall",
                 "f1-score": "F1", "support": "Soporte real"}), hide_index=True, use_container_width=True)
    st.caption("El soporte corresponde a etiquetas reales, no al número de predicciones de cada clase. "
               "Estas métricas no se usan para volver a seleccionar el modelo.")

st.subheader("1. Ganancia y SHAP · coincidencias y discrepancias")
with st.expander("Cómo se calcularon estas importancias", expanded=False):
    st.write("El notebook 09 calculó TreeSHAP nativo sobre 12.000 observaciones: 4.000 por clase real. "
             "Las variables transformadas se agruparon por variable original. La aplicación solo lee las tablas exportadas.")
    st.write("Ganancia: proporción de total_gain acumulada en los árboles, no ganancia media por división. "
             "SHAP macro: media de las importancias absolutas de las tres salidas de clase. "
             "SHAP ponderado: combina esas salidas según las frecuencias reales de las clases en el test.")
    st.caption("Cada salida de clase se explica sobre la misma muestra estratificada completa, no únicamente sobre "
               "las filas cuya etiqueta real pertenece a esa clase. La ponderación de salidas no corrige por sí sola "
               "el muestreo equilibrado de observaciones.")
mode = st.selectbox("Resumen SHAP global", ["Macro: igual peso por salida de clase", "Ponderado por frecuencias de clase del test"], key="int_modo")
top_n = st.selectbox("Número de variables líderes por método", [5, 10, 15, 20, len(comparison)], index=1, key="int_top")
comp = comparar_importancias(comparison, ponderada=mode.startswith("Ponderado"))
visible = union_top(comp, top_n)
gain_leaders = set(comp.loc[comp["Rango ganancia"].le(top_n), "original_feature"])
shap_leaders = set(comp.loc[comp["Rango SHAP"].le(top_n), "original_feature"])
shared = gain_leaders & shap_leaders
st.write(f"Coinciden {len(shared)} variables entre las {len(gain_leaders)} líderes de ganancia y las {len(shap_leaders)} líderes de SHAP.")
st.caption("La gráfica muestra la unión de ambas listas; puede contener más variables que el número elegido. "
           "Los porcentajes se calculan sobre todas las variables de cada método, no solo las visibles. "
           "Comparan concentración relativa: no son contribuciones equivalentes ni efectos causales.")
st.plotly_chart(grafico_comparacion(visible), use_container_width=True, key="int_comparacion", config={"displaylogo": False})
display_columns = ["original_feature", "Ganancia total (%)", "SHAP (%)", "Rango ganancia", "Rango SHAP", "Diferencia de rango (ganancia − SHAP)"]
st.dataframe(visible[display_columns].rename(columns={"original_feature": "Variable"}), hide_index=True, use_container_width=True)
st.caption("Diferencia positiva: la variable ocupa un puesto más alto con SHAP; negativa: con ganancia. "
           "Las coincidencias apoyan una lectura consistente entre métodos, pero no demuestran estabilidad estadística. "
           "Las discrepancias pueden reflejar medidas distintas y variables relacionadas; aquí no se atribuye una causa concreta.")
with st.expander("Todas las discrepancias, incluidas variables fuera del grupo líder"):
    discrepancies = comp.assign(_difference=comp["Diferencia de rango (ganancia − SHAP)"].abs()).sort_values(
        ["_difference", "original_feature"], ascending=[False, True])
    st.dataframe(discrepancies[display_columns].rename(columns={"original_feature": "Variable"}), hide_index=True, use_container_width=True)
    st.download_button("Descargar comparación completa (CSV)", comp.to_csv(index=False).encode("utf-8-sig"),
                       file_name="comparacion_importancias_vista.csv", mime="text/csv", key="int_csv")

st.subheader("2. Importancia SHAP por clase")
chosen = st.selectbox("Salida de clase que se explica", list(CLASES), index=1, format_func=CLASES.get, key="int_clase_shap")
selected = by_class.loc[by_class.class_value.eq(chosen)].sort_values("shap_rank_within_class").head(top_n)
if selected.empty:
    st.info("No hay importancias exportadas para esta clase.")
else:
    figure = px.bar(selected, x="mean_abs_shap", y="original_feature", orientation="h",
                     labels={"mean_abs_shap": "SHAP absoluto medio (margen del modelo)", "original_feature": "Variable"})
    figure.update_layout(yaxis={"autorange": "reversed"}, height=max(300, len(selected) * 28), margin={"l": 0, "r": 0, "t": 10, "b": 0})
    st.plotly_chart(figure, use_container_width=True, key="int_shap_clase", config={"displaylogo": False})
    st.dataframe(selected[["original_feature", "shap_rank_within_class", "mean_abs_shap", "mean_signed_shap"]].rename(columns={
        "original_feature": "Variable", "shap_rank_within_class": "Rango", "mean_abs_shap": "SHAP absoluto medio",
        "mean_signed_shap": "SHAP medio con signo"}), hide_index=True, use_container_width=True)
st.caption("La magnitud indica cuánto utiliza el modelo una señal para esta salida de clase. Las contribuciones están "
           "en la escala de margen, no en puntos porcentuales de probabilidad. El signo medio no indica por sí solo "
           "qué ocurre cuando aumenta el valor de una variable.")
class_factors = factors.loc[factors.class_value.eq(chosen)].sort_values("shap_rank_within_class").head(5)
if class_factors.empty:
    st.info("No hay factores operativos exportados para esta clase; no se inventa una explicación.")
else:
    st.markdown("**Factores operativos globales de la clase**")
    st.dataframe(class_factors[["original_feature", "factor_family", "direction_association", "rank_correlation_value_shap"]].rename(columns={
        "original_feature": "Variable", "factor_family": "Familia operativa", "direction_association": "Asociación valor–SHAP",
        "rank_correlation_value_shap": "Correlación de rangos valor–SHAP"}), hide_index=True, use_container_width=True)
    st.caption("Asociaciones globales de la muestra; no explicaciones locales ni efectos de reposición o retirada.")

st.subheader("3. Falsos negativos · soporte y cautelas")
risk = st.selectbox("Clase real para analizar falsos negativos", [1, 2], format_func=CLASES.get, key="int_clase_error")
st.caption("Un falso negativo es una observación de esta clase real que el modelo clasificó en otra clase. "
           "Tasa FN = falsos negativos / soporte real. No es la tasa de error sobre todas las filas. "
           "Todos los grupos son retrospectivos del test final; no modifican predicciones, umbrales ni recomendaciones.")
try:
    hour_errors = errores_clase(hours, risk, "hour").sort_values("hour")
    month_errors = errores_clase(months, risk, "month").sort_values("month")
    station_errors = errores_clase(stations, risk, "station_id")
except ValueError as error:
    st.error(str(error))
    st.stop()
st.markdown("**Mes: noviembre frente a diciembre de 2022**")
st.dataframe(month_errors.rename(columns={"month": "Mes"}), hide_index=True, use_container_width=True)
st.markdown("**Horas y atención especial a las 08:00, 18:00 y 19:00**")
st.plotly_chart(grafico_errores_hora(hour_errors), use_container_width=True, key="int_horas", config={"displaylogo": False})
st.dataframe(hour_errors.loc[hour_errors.hour.isin([8, 18, 19])].rename(columns={"hour": "Hora"}), hide_index=True, use_container_width=True)
with st.expander("Todas las horas con sus denominadores"):
    st.dataframe(hour_errors.rename(columns={"hour": "Hora"}), hide_index=True, use_container_width=True)

st.markdown("**Estaciones: comparar siempre con soporte**")
st.caption(f"El archivo de revisión contiene {len(stations)} estaciones de las {len(catalog)} del catálogo del test. "
           "No es el conjunto completo: una estación ausente no tiene necesariamente cero errores. "
           "El notebook 09 exigió al menos 500 filas y soporte de 20 en alguna clase crítica; "
           "las banderas por clase indican si se alcanzó ese soporte para vaciado o saturación.")
enough_only = st.checkbox("Solo estaciones con soporte suficiente en la clase seleccionada", value=True, key="int_soporte")
order = st.selectbox("Ordenar estaciones por", ["ID de estación", "Falsos negativos", "Tasa FN (%)"], key="int_orden")
station_view = station_errors.loc[station_errors["Soporte suficiente (notebook 09)"].eq("Sí")].copy() if enough_only else station_errors.copy()
column = "station_id" if order == "ID de estación" else order
station_view = station_view.sort_values([column] + ([] if column == "station_id" else ["station_id"]),
                                       ascending=True if column == "station_id" else [False, True], na_position="last")
st.caption(f"Se muestran {len(station_view)} de las {len(station_errors)} estaciones exportadas. "
           "Cambiar el orden o la bandera solo afecta a esta tabla; no se establece un umbral nuevo.")
if station_view.empty:
    st.info("No hay estaciones con estos filtros.")
else:
    st.dataframe(station_view.rename(columns={"station_id": "ID"}), hide_index=True, use_container_width=True,
                 column_config={"Tasa FN (%)": st.column_config.NumberColumn(format="%.2f")})

names = {int(r.station_id): f"{r.station_number} · {r.station_name} (ID {r.station_id})" for r in catalog.itertuples()}
options = [None] + sorted(names)
if st.session_state.get("int_estacion") not in options:
    st.session_state["int_estacion"] = None
station_id = st.selectbox("Consultar estación del catálogo completo", options,
                          format_func=lambda i: "Selecciona una estación" if i is None else names[i], key="int_estacion")
if station_id is not None:
    stats = stations.loc[stations.station_id.eq(station_id)]
    if stats.empty:
        st.info("No hay estadísticas de revisión exportadas para esta estación. No se sustituyen por ceros.")
    st.dataframe(tabla_falsos_negativos(None if stats.empty else stats.iloc[0]), hide_index=True, use_container_width=True)
    st.caption("Ficha independiente de los filtros de la tabla anterior, con ambas clases y sus banderas originales. "
               "Cautela y monitorización, no correcciones del modelo.")
