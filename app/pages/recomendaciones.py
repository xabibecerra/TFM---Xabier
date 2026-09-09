"""Exploración de las propuestas congeladas del notebook 10 (fase 12)."""

import pandas as pd
import streamlit as st

from app.charts import mapa_transferencias
from app.data import (DatosAppError, cargar_candidatos, cargar_factores_por_clase,
                      cargar_no_resueltos, cargar_predicciones, cargar_tabla, cargar_transferencias)
from app.operativa import ESTADOS, PARES, auditar_escenario, filtrar_candidatos, resumen_cobertura, seleccionar
from app.riesgo import ACCIONES, CLASES, TIME, formato


st.title("Recomendaciones")
st.caption("Escenarios históricos · noviembre-diciembre de 2022 · propuestas del notebook 10")
st.info("Consulta de solo lectura. No se recalculan emparejamientos, cantidades, predicciones ni umbrales.")

try:
    predictions = cargar_predicciones()
    candidates = cargar_candidatos()
    transfers = cargar_transferencias()
    unresolved = cargar_no_resueltos()
    policy = cargar_tabla("politica_operativa")
    factors = cargar_factores_por_clase()
except (DatosAppError, OSError) as error:
    st.error(f"No se pueden cargar las recomendaciones: {error}")
    st.stop()

instants = predictions[TIME].drop_duplicates().sort_values()
dates = sorted(set(instants.dt.date))
if not dates:
    st.error("No hay instantes de predicción disponibles.")
    st.stop()
if st.session_state.get("op_fecha") not in dates:
    st.session_state["op_fecha"] = dates[0]
left, right = st.columns(2)
with left:
    date = st.selectbox("Fecha del escenario", dates, format_func=lambda d: d.strftime("%d/%m/%Y"), key="op_fecha")
times = instants.loc[instants.dt.date.eq(date)].tolist()
if st.session_state.get("op_hora") not in times:
    st.session_state["op_hora"] = times[0]
with right:
    instant = st.selectbox("Hora del escenario", times, format_func=lambda t: t.strftime("%H:%M"), key="op_hora")

snapshot = seleccionar(predictions, instant)
hour_candidates = seleccionar(candidates, instant)
hour_transfers = seleccionar(transfers, instant)
hour_unresolved = seleccionar(unresolved, instant)
try:
    audit = auditar_escenario(snapshot, hour_candidates, hour_transfers, hour_unresolved, policy)
except (ValueError, KeyError, TypeError) as error:
    st.error(f"Consulta detenida: {error}. Revisa los archivos preparados; no se han corregido ni regenerado.")
    st.stop()

names = {int(r.station_id): f"{r.station_number} · {r.station_name} (ID {r.station_id})" for r in snapshot.itertuples()}
station_options = [None] + sorted(names)
if st.session_state.get("op_estacion") not in station_options:
    st.session_state["op_estacion"] = None
station = st.selectbox("Estación (candidata o apoyo logístico)", station_options,
                       format_func=lambda i: "Todas las estaciones" if i is None else names[i], key="op_estacion")
visible_candidates = seleccionar(hour_candidates, instant, station)
visible_transfers = seleccionar(hour_transfers, instant, station, transferencias=True)
visible_unresolved = seleccionar(hour_unresolved, instant, station)

st.caption(f"{instant:%d/%m/%Y %H:%M} · Los contadores corresponden a la estación seleccionada o al escenario completo. "
           "Las transferencias conservan ambos extremos, incluido el apoyo estable.")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Candidatas técnicas", len(visible_candidates))
m2.metric("Transferencias propuestas", len(visible_transfers))
m3.metric("Bicicletas propuestas en parejas", formato(visible_transfers.units.sum()))
m4.metric("Candidatas con brecha pendiente", int(visible_candidates.uncovered_units.gt(0).sum()))
st.warning("Una estación estable no origina una candidata por riesgo propio a partir de critical_risk_type. "
           "Sí puede participar como apoyo logístico. Los emparejamientos horarios no son rutas definitivas ni movimientos ejecutados.")
st.caption("Cada hora es un escenario independiente: no se arrastran inventarios simulados entre horas. "
           "La suma de unidades asignadas en candidatas puede contar los dos extremos de una misma transferencia; "
           "las bicicletas propuestas se cuentan una sola vez desde la tabla de parejas.")

with st.expander("Política congelada y comprobaciones del escenario", expanded=False):
    st.dataframe(policy.rename(columns={"parameter": "Parámetro", "value": "Valor", "source": "Origen"}), hide_index=True, use_container_width=True)
    policy_values = policy.set_index("parameter").value
    st.caption(f"Banda operativa {float(policy_values['operational_min_ratio']):.0%}–{float(policy_values['operational_max_ratio']):.0%}; "
               f"radio geográfico máximo {float(policy_values['max_pair_distance_km']):g} km; "
               f"máximo {float(policy_values['max_units_per_transfer']):g} bicicletas por pareja. "
               "Son restricciones del escenario exportado, no umbrales de clasificación ni parámetros editables. "
               "Los anclajes conservadores descuentan reservas. No se modelan flota, tiempos de servicio ni rutas de vehículos.")
    st.dataframe(audit, hide_index=True, use_container_width=True)
    st.caption("Auditoría de todas las transferencias de esta hora antes del filtro de estación: "
               "incluye asignaciones acumuladas por extremo, capacidad y balance. No busca nuevas parejas.")

st.subheader("1. Señal predictiva · candidatas técnicas")
st.caption("Orden original dentro de cada hora y acción. critical_risk_score sirve solo para ordenar; "
           "no es una cantidad de bicicletas ni un umbral de intervención. Los filtros siguientes solo afectan a las tablas de candidatas.")
status = st.multiselect("Estado de cobertura de las candidatas", list(ESTADOS), default=list(ESTADOS),
                        format_func=ESTADOS.get, key="op_estados")
classes = st.multiselect("Acciones candidatas", [1, 2], default=[1, 2],
                         format_func=lambda c: "Reposición" if c == 1 else "Retirada", key="op_clases")
listed = filtrar_candidatos(visible_candidates, status, classes)

CANDIDATE_COLUMNS = {
    "station_id": "ID", "station_name": "Estación", "prediction": "Predicción",
    "model_action_signal": "Señal técnica", "critical_risk_score": "Score (solo orden)",
    "priority_rank_within_hour_and_action": "Orden original por acción",
    "requested_units": "Unidades solicitadas", "assigned_units": "Unidades asignadas",
    "uncovered_units": "Unidades sin cubrir", "recommendation_status": "Estado de cobertura",
}

def candidate_table(frame):
    display = frame[list(CANDIDATE_COLUMNS)].copy()
    display.prediction = display.prediction.map(CLASES)
    display.model_action_signal = display.model_action_signal.map(ACCIONES)
    display.recommendation_status = display.recommendation_status.map(ESTADOS)
    return display.rename(columns=CANDIDATE_COLUMNS)

if listed.empty:
    st.info("No hay candidatas para estos filtros. Una estación estable puede tener transferencias aunque esta tabla esté vacía.")
else:
    st.dataframe(candidate_table(listed), hide_index=True, use_container_width=True,
                 column_config={"Score (solo orden)": st.column_config.NumberColumn(format="%.6f")})
st.dataframe(resumen_cobertura(listed), hide_index=True, use_container_width=True,
             column_config={"Cobertura de unidades (%)": st.column_config.NumberColumn(format="%.2f")})
st.caption("Cobertura de las candidatas filtradas, separada por acción y con denominador de unidades solicitadas. "
           "Sin brecha, la tasa queda ausente; no implica una cobertura del 100 %.")

st.subheader("2. Factibilidad logística · transferencias guardadas")
st.caption("Todas las parejas asociadas a la fecha, hora y estación elegidas. Los filtros de estado y acción anteriores no ocultan parejas.")
if visible_transfers.empty:
    st.info("No hay transferencias guardadas para esta selección. No se generan alternativas nuevas.")
else:
    streets = st.checkbox("Mostrar callejero de transferencias (requiere internet)", value=True, key="op_callejero")
    st.plotly_chart(mapa_transferencias(visible_transfers, snapshot, callejero=streets),
                    use_container_width=True, key="op_mapa", config={"displaylogo": False})
    st.caption("Las líneas unen donante y receptora, no representan calles ni itinerarios. "
               "La dirección donante → receptora figura en la tabla y en el detalle emergente. "
               "Los colores de las estaciones mantienen su clase predicha: azul estable, naranja vaciado, morado saturación.")
    transfer_display = visible_transfers[["donor_station_id", "donor_station_name", "donor_prediction",
                                         "receiver_station_id", "receiver_station_name", "receiver_prediction",
                                         "units", "distance_km", "pair_type"]].copy()
    for col in ["donor_prediction", "receiver_prediction"]:
        transfer_display[col] = transfer_display[col].map(CLASES)
    transfer_display.pair_type = transfer_display.pair_type.map(PARES)
    transfer_display = transfer_display.rename(columns={"donor_station_id": "ID donante", "donor_station_name": "Donante",
        "donor_prediction": "Clase donante", "receiver_station_id": "ID receptora", "receiver_station_name": "Receptora",
        "receiver_prediction": "Clase receptora", "units": "Bicicletas propuestas", "distance_km": "Distancia geográfica (km)", "pair_type": "Tipo de pareja"})
    st.dataframe(transfer_display, hide_index=True, use_container_width=True,
                 column_config={"Distancia geográfica (km)": st.column_config.NumberColumn(format="%.2f")})
    st.download_button("Descargar parejas mostradas (CSV)", visible_transfers.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"transferencias_{instant:%Y%m%d_%H%M}.csv", mime="text/csv", key="op_descarga")

st.markdown("**Coberturas parciales, sin asignación y monitorización**")
unresolved_list = filtrar_candidatos(visible_unresolved, status, classes)
st.caption("Esta tabla procede del archivo de no resueltos y respeta los filtros de candidatas. "
           "Incluye monitorización sin brecha actual, que no debe contarse como bicicletas pendientes. "
           "«Sin asignación» describe el resultado del emparejamiento; no demuestra que ninguna solución alternativa sea posible.")
if unresolved_list.empty:
    st.info("No hay filas de no resueltos para estos filtros.")
else:
    st.dataframe(candidate_table(unresolved_list), hide_index=True, use_container_width=True)

st.subheader("3. Explicación operativa · detalle de una candidata")
detail_options = [None] + listed.station_id.tolist()
if st.session_state.get("op_detalle") not in detail_options:
    st.session_state["op_detalle"] = None
detail = st.selectbox("Candidata a explicar", detail_options,
                      format_func=lambda i: "Selecciona una candidata" if i is None else names[i], key="op_detalle")
if detail is None:
    st.info("Selecciona una candidata para ver su brecha, cobertura, explicación exportada y cautelas con soporte.")
    st.stop()

row = listed.loc[listed.station_id.eq(detail)].iloc[0]
st.markdown(f"**{names[detail]} · {ESTADOS[row.recommendation_status]}**")
st.write(f"Señal: {ACCIONES[row.model_action_signal]}. Brecha solicitada: {row.requested_units} bicicletas; "
         f"asignadas en las propuestas: {row.assigned_units}; sin cubrir: {row.uncovered_units}.")
st.dataframe(pd.DataFrame([{"Capacidad": row.capacity, "Bicicletas observadas": row.bikes_available,
    "Anclajes observados": row.docks_available, "Reservas": row.reservations_count,
    "Anclajes conservadores": row.free_docks_conservative, "Objetivo mínimo": row.target_min_bikes,
    "Objetivo máximo": row.target_max_bikes}]), hide_index=True, use_container_width=True)
st.write(row.operational_explanation)
st.caption("Texto conservado del notebook 10. Los factores SHAP son globales de la clase, no una explicación local "
           "calculada para esta estación-hora. Identifican asociaciones predictivas, no causas ni efectos de intervenir.")
class_factors = factors.loc[factors.class_value.eq(row.prediction)].sort_values("shap_rank_within_class").head(5)
if class_factors.empty:
    st.info("No hay factores SHAP exportados para esta clase; no se inventa una explicación.")
else:
    class_factors = class_factors.copy()
    class_factors["Lectura operativa"] = class_factors.original_feature.map({
        "occupancy_ratio": "Ocupación observada de la estación", "bikes_available": "Bicicletas disponibles",
        "occupancy_ratio_mean_previous_24h": "Ocupación media de las 24 horas previas",
        "docks_available": "Anclajes disponibles", "reservations_count": "Reservas registradas",
        "light": "Variable contextual light (no implica causalidad)",
    }).fillna(class_factors.original_feature)
    class_factors.factor_family = class_factors.factor_family.replace({
        "estado_actual_estacion": "Estado actual de la estación", "dinamica_historica_reciente": "Evolución reciente",
        "otra_senal_contextual": "Contexto", "temporal_y_calendario": "Horario y calendario",
        "identidad_y_heterogeneidad_espacial": "Diferencias entre estaciones", "meteorologia": "Meteorología"})
    class_factors.direction_association = class_factors.direction_association.replace({
        "valores_altos_reducen_contribucion": "Valores altos asociados a menor contribución a esta clase",
        "valores_altos_aumentan_contribucion": "Valores altos asociados a mayor contribución a esta clase",
        "sin_direccion_monotona_clara": "Sin dirección monótona clara"})
    st.dataframe(class_factors[["original_feature", "Lectura operativa", "shap_rank_within_class", "mean_abs_shap", "factor_family", "direction_association"]].rename(
        columns={"original_feature": "Factor del modelo", "shap_rank_within_class": "Orden SHAP en clase",
                 "mean_abs_shap": "SHAP absoluto medio", "factor_family": "Familia operativa", "direction_association": "Asociación global"}),
        hide_index=True, use_container_width=True)

if row.sensitive_hour_flag or row.sensitive_station_flag:
    st.warning("Cautela de monitorización exportada: " + ("hora sensible; " if row.sensitive_hour_flag else "")
               + ("estación sensible; " if row.sensitive_station_flag else "") + "no modifica la propuesta ni el modelo.")
st.caption("Diagnóstico retrospectivo de todo el test, no información conocida en el instante seleccionado. "
           "Las cifras siguientes agrupan vaciado y saturación; no son tasas específicas de la clase de esta candidata. "
           "El desglose por clase está en Riesgo 2022.")
enough = row.get("enough_support_empty" if row.prediction == 1 else "enough_support_full")
enough_text = "No exportado" if pd.isna(enough) else ("Sí" if enough else "No")
st.caption(f"Soporte suficiente de esta estación para la clase candidata (criterio del notebook 09): {enough_text}. "
           "No se establece un corte nuevo ni se cambia la prioridad.")
stats = []
for label, prefix in [("Estación · riesgos críticos combinados", ""), ("Hora · riesgos críticos combinados", "hour_")]:
    support = row[f"{prefix}critical_support"]
    fn = row[f"{prefix}critical_false_negatives"]
    stats.append({"Grupo": label, "Soporte crítico real": support, "Falsos negativos críticos": fn,
                  "Tasa FN (%)": 100 * row[f"{prefix}critical_false_negative_rate"] if pd.notna(support) and support > 0 else None})
st.dataframe(pd.DataFrame(stats), hide_index=True, use_container_width=True,
             column_config={"Tasa FN (%)": st.column_config.NumberColumn(format="%.2f")})
