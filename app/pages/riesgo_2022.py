"""Mapa del test final, con consulta de contexto y cautelas retrospectivas."""

import pandas as pd
import streamlit as st

from app.charts import mapa_riesgo, probabilidades_estacion
from app.data import (DatosAppError, cargar_candidatos, cargar_estaciones_sensibles,
                      cargar_horas_sensibles, cargar_predicciones)
from app.riesgo import ACCIONES, CLASES, TIME, filtrar_escenario, formato, recuentos_clases, tabla_falsos_negativos


st.title("Riesgo 2022")
st.caption("Test final · noviembre-diciembre de 2022")
st.info("Consulta histórica de predicciones congeladas. Los filtros solo seleccionan registros: no recalculan el modelo ni ajustan umbrales.")

try:
    predictions = cargar_predicciones()
    hours = cargar_horas_sensibles()
    stations = cargar_estaciones_sensibles()
    flags = cargar_candidatos(columnas=["station_id", "sensitive_station_flag"]).drop_duplicates()
except (DatosAppError, OSError) as error:
    st.error(f"No se pueden cargar los datos de riesgo: {error}")
    st.stop()

if predictions.empty:
    st.error("No hay predicciones disponibles. Comprueba la preparación de datos.")
    st.stop()

instants = predictions[TIME].drop_duplicates().sort_values()
dates = sorted(set(instants.dt.date))
if st.session_state.get("riesgo_fecha") not in dates:
    st.session_state["riesgo_fecha"] = dates[0]
date_column, hour_column = st.columns(2)
with date_column:
    selected_date = st.selectbox("Fecha", dates, format_func=lambda d: d.strftime("%d/%m/%Y"), key="riesgo_fecha")
available_times = instants.loc[instants.dt.date.eq(selected_date)].tolist()
if st.session_state.get("riesgo_instante") not in available_times:
    st.session_state["riesgo_instante"] = available_times[0]
with hour_column:
    instant = st.selectbox("Hora", available_times, format_func=lambda t: t.strftime("%H:%M"), key="riesgo_instante")
st.caption("Solo se ofrecen momentos presentes en el test. Fecha y hora local tal como fueron exportadas, sin rellenar huecos.")

classes = st.multiselect("Clases que se muestran", list(CLASES), default=list(CLASES),
                         format_func=CLASES.get, key="riesgo_clases")
snapshot = filtrar_escenario(predictions, instant)
class_filtered = filtrar_escenario(predictions, instant, classes)
station_options = [None] + sorted(class_filtered.station_id.unique().tolist())
names = {int(row.station_id): f"{row.station_number} · {row.station_name} (ID {row.station_id})"
         for row in class_filtered.itertuples()}
if st.session_state.get("riesgo_estacion") not in station_options:
    st.session_state["riesgo_estacion"] = None
station_id = st.selectbox("Estación", station_options,
                          format_func=lambda v: "Todas las estaciones" if v is None else names[v], key="riesgo_estacion")
filtered = filtrar_escenario(predictions, instant, classes, station_id)
counts = recuentos_clases(filtered)
all_count, stable_count, empty_count, full_count = st.columns(4)
all_count.metric("Estaciones mostradas", len(filtered))
stable_count.metric("Estables", counts[0])
empty_count.metric("Riesgo de vaciado", counts[1])
full_count.metric("Riesgo de saturación", counts[2])
st.caption(f"{len(filtered)} de {len(snapshot)} estaciones disponibles a las {instant:%H:%M} del {instant:%d/%m/%Y}. "
           f"Señales técnicas visibles: {counts[1]} candidatas a reposición y {counts[2]} a retirada; no son órdenes de movimiento.")
if instant.hour in [8, 18, 19]:
    st.warning(f"Hora de especial cautela: {instant:%H:%M}. Aviso retrospectivo de monitorización, no corrección del modelo. "
               "La ficha de estación muestra soporte, falsos negativos y tasas de esta hora en todo el test.")

if filtered.empty:
    st.info("No hay estaciones para estos filtros. Selecciona al menos una clase o cambia el instante.")
    st.stop()

st.subheader("Mapa de estaciones")
street_map = st.checkbox("Mostrar callejero (requiere conexión a internet)", value=True, key="riesgo_callejero")
st.plotly_chart(mapa_riesgo(filtered, callejero=street_map), use_container_width=True,
                key="riesgo_mapa", config={"displaylogo": False})
st.caption("Azul: estable · Naranja: vaciado · Morado: saturación. Pasa el cursor sobre un punto para consultar su contexto. "
           "Selecciona una estación en el desplegable para ver su ficha. Si el callejero no carga, desactívalo; los puntos y la tabla siguen disponibles.")

st.subheader("Estaciones del escenario filtrado")
display = filtered[["station_id", "station_number", "station_name", "capacity", "bikes_available", "docks_available",
                    "occupancy_ratio", "prediction", "model_action_signal", "probability_0", "probability_1", "probability_2"]].copy()
display["prediction"] = display.prediction.map(CLASES)
display["model_action_signal"] = display.model_action_signal.map(ACCIONES)
for col in ["occupancy_ratio", "probability_0", "probability_1", "probability_2"]:
    display[col] = display[col] * 100  # Solo formato de presentación; la fuente sigue intacta.
display = display.rename(columns={"station_id": "ID", "station_number": "Número", "station_name": "Estación",
                                  "capacity": "Capacidad", "bikes_available": "Bicicletas", "docks_available": "Anclajes",
                                  "occupancy_ratio": "Ocupación (%)", "prediction": "Predicción", "model_action_signal": "Señal técnica",
                                  "probability_0": "P(estable) (%)", "probability_1": "P(vaciado) (%)", "probability_2": "P(saturación) (%)"})
st.dataframe(display, hide_index=True, use_container_width=True,
             column_config={col: st.column_config.NumberColumn(format="%.2f") for col in display if col.endswith("(%)")})

if station_id is None:
    st.info("Selecciona una estación para consultar disponibilidad, probabilidades, meteorología y errores históricos.")
    st.stop()

row = filtered.iloc[0]
st.subheader(f"Detalle de estación · {row.station_number} · {row.station_name}")
st.caption(f"ID {int(row.station_id)} · {row.address} · {instant:%d/%m/%Y %H:%M}")
st.markdown(f"**Predicción congelada:** {CLASES[int(row.prediction)]}. **Señal técnica:** {ACCIONES[row.model_action_signal]}.")
if row.prediction == 0:
    st.info("Estación predicha como estable: monitorización, sin candidata por riesgo propio. "
            "critical_risk_type solo compara los dos riesgos relativos y no activa una intervención. "
            "La estación puede actuar como apoyo logístico en una transferencia ya calculada.")
else:
    st.info("La clase crítica señala una candidata técnica. La página de Recomendaciones determinará cómo consultar "
            "su factibilidad y cobertura ya calculadas; esta ficha no propone nuevas cantidades.")

capacity, bikes, docks, occupancy = st.columns(4)
capacity.metric("Capacidad", formato(row.capacity))
bikes.metric("Bicicletas disponibles", formato(row.bikes_available))
docks.metric("Anclajes disponibles", formato(row.docks_available))
occupancy.metric("Ocupación observada", formato(row.occupancy_ratio * 100, 1, " %"))
st.caption(f"Reservas: {formato(row.reservations_count)}. El estado observado no debe confundirse con la clase de riesgo predicha.")
st.plotly_chart(probabilidades_estacion(row), use_container_width=True, key="riesgo_probabilidades", config={"displaylogo": False})
st.caption("Probabilidades guardadas, sin recalibración. El redondeo mostrado no convierte una probabilidad pequeña en un cero exacto; "
           "el detalle emergente ofrece más decimales.")

with st.expander("Meteorología y flujos previos", expanded=False):
    context = [
        {"Variable": "Tipo de día", "Valor": str(row.tipo_dia)},
        {"Variable": "Temperatura", "Valor": formato(row.temperature_median_c, 1, " °C")},
        {"Variable": "Humedad relativa", "Valor": formato(row.relative_humidity_median_pct, 1, " %")},
        {"Variable": "Viento", "Valor": formato(row.wind_speed_median_m_s, 2, " m/s")},
        {"Variable": "Precipitación", "Valor": formato(row.precipitation_mean_l_m2, 2, " l/m²")},
        {"Variable": "Salidas de la hora anterior", "Valor": formato(row.departures_count_lag_1h)},
        {"Variable": "Llegadas de la hora anterior", "Valor": formato(row.arrivals_count_lag_1h)},
        {"Variable": "Flujo neto de la hora anterior", "Valor": formato(row.net_flow_lag_1h)},
    ]
    st.dataframe(pd.DataFrame(context), hide_index=True, use_container_width=True)
    st.caption("Solo contexto observado. No se modifica la meteorología ni se imputan flujos ausentes.")

st.subheader("Cautelas retrospectivas y soporte")
st.caption("Diagnóstico agregado de todo el test final, no información conocida en el instante mostrado. "
           "No entra en la predicción ni la corrige. Tasa FN = falsos negativos / soporte real de cada clase.")
station_stats = stations.loc[stations.station_id.eq(station_id)]
hour_stats = hours.loc[hours.hour.eq(instant.hour)]
station_flag = flags.loc[flags.station_id.eq(station_id), "sensitive_station_flag"]
if not station_flag.empty and station_flag.eq(True).any():
    st.warning("Estación señalada para monitorización en el notebook 10. Consulta los denominadores por clase antes de interpretar sus errores.")
elif station_flag.empty:
    st.caption("No hay una bandera de monitorización exportada para esta estación; no equivale a ausencia de riesgo.")
else:
    st.caption("Sin bandera especial de estación en el notebook 10; no garantiza ausencia de errores.")
for label, stats in [("Estación seleccionada · todo el test", station_stats), ("Hora seleccionada · todas las estaciones del test", hour_stats)]:
    st.markdown(f"**{label}**")
    if stats.empty:
        st.info("No hay estadísticas exportadas para este grupo. No se sustituyen por ceros.")
    st.dataframe(tabla_falsos_negativos(None if stats.empty else stats.iloc[0]), hide_index=True,
                 use_container_width=True, column_config={"Tasa FN (%)": st.column_config.NumberColumn(format="%.2f")})
st.caption("Soporte suficiente conserva el criterio exportado por el notebook 09; no se introduce un umbral nuevo. "
           "Una tasa sin soporte se deja ausente. La tabla por hora no exporta esa bandera de suficiencia.")
