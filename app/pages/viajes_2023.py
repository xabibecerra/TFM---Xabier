"""Página descriptiva independiente de los resultados predictivos de 2022."""

import pandas as pd
import plotly.express as px
import streamlit as st

from app.data import DatosAppError, cargar_viajes_2023
from app.riesgo import formato
from app.viajes import DIAS, comprobar_alcance, dias_para_mostrar, filtrar_meses, mapa_actividad, seleccionar_od


st.title("Viajes 2023")
st.caption("Análisis descriptivo independiente · enero-febrero de 2023")
st.warning(
    "No existen datos de estados de estaciones para enero-febrero de 2023. "
    "Esta sección no contiene predicciones, etiquetas de riesgo ni recomendaciones. "
    "Febrero tiene cobertura parcial hasta el 18 de febrero de 2023 a las 07:22:48."
)
try:
    summary = cargar_viajes_2023("resumen_mensual_2023")
    coverage = cargar_viajes_2023("cobertura_mensual_2023")
    daily = cargar_viajes_2023("viajes_por_dia_2023")
    hourly = cargar_viajes_2023("viajes_por_hora_2023")
    weekday = cargar_viajes_2023("viajes_por_dia_semana_2023")
    segment = cargar_viajes_2023("viajes_por_segmento_semana_2023")
    activity = cargar_viajes_2023("actividad_estaciones_2023")
    pairs = cargar_viajes_2023("pares_od_2023")
    duration = cargar_viajes_2023("resumen_duracion_2023")
    scope = cargar_viajes_2023("auditoria_alcance_2023")
    quality = cargar_viajes_2023("auditoria_calidad_2023")
    controls = comprobar_alcance(scope)
except (DatosAppError, OSError, ValueError) as error:
    st.error(f"No se puede abrir el análisis descriptivo: {error}")
    st.stop()

period = st.selectbox("Mes para las vistas temporales y de duración", ["Ambos meses", "2023-01", "2023-02"], key="v23_mes")
months = summary.month.tolist() if period == "Ambos meses" else [period]
monthly = filtrar_meses(summary, months)
selected_coverage = filtrar_meses(coverage, months)
if monthly.empty:
    st.error("No hay resumen exportado para el mes seleccionado.")
    st.stop()
st.caption("El selector de mes afecta a cobertura, volumen, perfiles temporales y duración. "
           "Estaciones y pares origen–destino conservan todo el periodo observado porque no se exportaron por mes.")
a, b, c = st.columns(3)
a.metric("Viajes observados · meses seleccionados", formato(monthly.observed_trips.sum()))
b.metric("Días completos para perfiles", formato(monthly.complete_days.sum()))
c.metric("Días con viajes registrados", formato(monthly.observed_days.sum()))


def chart(fig, key):
    fig.update_layout(margin={"l": 0, "r": 0, "t": 15, "b": 0})
    st.plotly_chart(fig, use_container_width=True, key=key, config={"displaylogo": False})


st.subheader("1. Cobertura y volumen observado")
st.dataframe(selected_coverage.rename(columns={"month": "Mes", "expected_days": "Días del mes", "observed_days": "Días con viajes",
    "complete_days": "Días completos", "first_trip": "Primer viaje", "last_trip": "Último viaje", "month_complete": "Mes completo"}),
    hide_index=True, use_container_width=True)
st.caption("El notebook considera completo un día con primer viaje antes de la 01:00 y último a partir de las 23:00. "
           "Es un criterio de cobertura observada, no una prueba de ausencia de pérdidas de registros. "
           "No se extrapolan los días que faltan en febrero ni se comparan sus totales como meses equivalentes.")
day_view = dias_para_mostrar(filtrar_meses(daily, months))
figure = px.line(day_view, x="date", y="Viajes observados", markers=True, hover_data=["Cobertura", "observed_hours"],
                 labels={"date": "Fecha", "observed_hours": "Horas con registros"})
figure.update_traces(connectgaps=False)
partial = day_view.loc[day_view.observed_day & ~day_view.complete_day]
if not partial.empty:
    figure.add_scatter(x=partial.date, y=partial["Viajes observados"], mode="markers", name="Día parcial",
                      marker={"color": "#D97706", "size": 11})
chart(figure, "v23_diario")
st.caption("Los días sin registros aparecen como huecos, no como demanda cero. El 18 de febrero es parcial; "
           "del 19 al 28 no hay cobertura observada. Los ceros del archivo original no se alteran: solo cambia su presentación.")
with st.expander("Tabla diaria y cobertura"):
    st.dataframe(day_view[["date", "Viajes observados", "observed_hours", "Cobertura"]].rename(columns={"date": "Fecha", "observed_hours": "Horas con registros"}),
                 hide_index=True, use_container_width=True)
chart(px.bar(monthly, x="month", y="mean_trips_per_complete_day", hover_data=["complete_days"],
             labels={"month": "Mes", "mean_trips_per_complete_day": "Media de viajes por día completo", "complete_days": "Días completos"}), "v23_media")
st.dataframe(monthly[["month", "observed_trips", "complete_days", "mean_trips_per_complete_day", "median_trips_per_complete_day"]].rename(columns={
    "month": "Mes", "observed_trips": "Viajes observados (incluye día parcial)", "complete_days": "Días completos",
    "mean_trips_per_complete_day": "Media por día completo", "median_trips_per_complete_day": "Mediana por día completo"}), hide_index=True, use_container_width=True)

st.subheader("2. Patrones horarios y semanales · solo días completos")
st.caption("Medias ya exportadas: 31 días completos en enero y 17 en febrero. "
           "La comparación es descriptiva; no controla meteorología, festivos ni otros cambios de composición.")
hour_view = filtrar_meses(hourly, months).sort_values(["month", "hour"])
chart(px.line(hour_view, x="hour", y="mean_trips_per_complete_day", color="month", markers=True,
              hover_data=["trips", "complete_days"], labels={"hour": "Hora de inicio", "month": "Mes", "trips": "Viajes en días completos",
              "complete_days": "Días completos", "mean_trips_per_complete_day": "Viajes por día completo en esta hora"}), "v23_hora")
week_view = filtrar_meses(weekday, months)
chart(px.bar(week_view, x="weekday", y="mean_trips_per_day", color="month", barmode="group",
             category_orders={"weekday": DIAS}, hover_data=["days", "trips"], labels={"weekday": "Día de la semana", "month": "Mes",
             "mean_trips_per_day": "Media de viajes por día completo", "days": "Días completos del grupo", "trips": "Viajes del grupo"}), "v23_semana")
with st.expander("Denominadores de los perfiles temporales"):
    st.dataframe(hour_view.rename(columns={"month": "Mes", "hour": "Hora", "trips": "Viajes", "complete_days": "Días completos",
                 "mean_trips_per_complete_day": "Media por día completo"}), hide_index=True, use_container_width=True)
    st.dataframe(week_view.drop(columns="index", errors="ignore").rename(columns={"month": "Mes", "weekday": "Día de semana", "days": "Días completos",
                 "trips": "Viajes", "mean_trips_per_day": "Media diaria", "median_trips_per_day": "Mediana diaria"}), hide_index=True, use_container_width=True)
    st.dataframe(filtrar_meses(segment, months).rename(columns={"month": "Mes", "week_segment": "Grupo de días", "days": "Días completos",
                 "mean_trips_per_day": "Media diaria", "median_trips_per_day": "Mediana diaria"}), hide_index=True, use_container_width=True)

st.subheader("3. Duración observada · ventana fija de 1 a 120 minutos")
dur = filtrar_meses(duration, months).copy()
dur["Duraciones incluidas (%)"] = dur.valid_duration_share * 100
st.caption("La duración típica utiliza solo viajes entre 1 y 120 minutos, ambos incluidos. "
           "Los viajes fuera de esa ventana se conservan en los recuentos de volumen. "
           "Esta sección incluye todos los días observados, también el día parcial de febrero.")
st.dataframe(dur.rename(columns={"month": "Mes", "valid_duration_trips": "Viajes incluidos en duración", "observed_trips": "Viajes observados",
    "mean_minutes": "Media (min)", "median_minutes": "Mediana (min)", "p25_minutes": "P25 (min)", "p75_minutes": "P75 (min)",
    "p95_minutes": "P95 (min)", "below_1_minute": "Menos de 1 min", "above_120_minutes": "Más de 120 min"}).drop(columns="valid_duration_share"),
    hide_index=True, use_container_width=True)
st.caption("Son resúmenes de las duraciones incluidas, no percentiles de todos los viajes. "
           "No se reconstruye una distribución ni un histograma a partir de estos agregados.")

st.subheader("4. Estaciones y balance de viajes · todo el periodo")
first, last = pd.Timestamp(controls["first_trip"]), pd.Timestamp(controls["last_trip"])
station_total = int(summary.station_to_station_trips.sum())
st.info(f"Periodo fijo: {first:%d/%m/%Y %H:%M:%S} — {last:%d/%m/%Y %H:%M:%S}. "
        f"Base: {formato(station_total)} viajes con estación de origen y destino identificadas, "
        "incluidos los que vuelven a la misma estación. El selector de mes no afecta a esta sección ni a los pares OD.")
st.caption("Actividad = salidas + llegadas: cuenta extremos de viaje, no viajes únicos. "
           "Un viaje con la misma estación aporta una salida y una llegada a esa estación. "
           "Llegadas − salidas es un balance de viajes; no permite reconstruir bicicletas disponibles, ocupación, vaciado o saturación.")
names = dict(zip(activity.station_id, activity.station_name))
options = [None] + sorted(names)
if st.session_state.get("v23_estacion") not in options:
    st.session_state["v23_estacion"] = None
station = st.selectbox("Estación para actividad y pares OD", options,
                        format_func=lambda i: "Todas las estaciones" if i is None else f"{names[i]} (ID {i})", key="v23_estacion")
station_view = activity if station is None else activity.loc[activity.station_id.eq(station)]
streets = st.checkbox("Mostrar callejero descriptivo (requiere internet)", value=True, key="v23_callejero")
missing_coords = int(station_view[["latitude", "longitude"]].isna().any(axis=1).sum())
if missing_coords:
    st.caption(f"{missing_coords} estaciones sin coordenadas exportadas: siguen en la tabla, pero no en el mapa.")
if missing_coords < len(station_view):
    chart(mapa_actividad(station_view, max(float(activity.net_arrivals.abs().max()), 1), streets), "v23_mapa")
else:
    st.info("No hay coordenadas disponibles para representar esta selección.")
st.caption("Tamaño: actividad total. Color: balance de llegadas menos salidas, con escala fija para todo el periodo. "
           "Los colores no representan clases de riesgo ni señales de intervención.")
st.dataframe(station_view[["station_id", "station_name", "departures", "arrivals", "total_activity", "net_arrivals"]].rename(columns={
    "station_id": "ID", "station_name": "Estación", "departures": "Salidas", "arrivals": "Llegadas",
    "total_activity": "Actividad (extremos)", "net_arrivals": "Llegadas − salidas"}), hide_index=True, use_container_width=True)

st.subheader("5. Pares origen–destino · todo el periodo")
kind = st.selectbox("Tipo de par OD", ["Estaciones distintas", "Misma estación", "Todos"], key="v23_tipo_od")
direction = st.selectbox("Papel de la estación seleccionada", ["Cualquier extremo", "Origen", "Destino"], disabled=station is None, key="v23_sentido")
limit = st.selectbox("Máximo de pares en la tabla", [10, 20, 50, 100], index=1, key="v23_limite")
selected_pairs = seleccionar_od(pairs, station, direction, kind)
top_pairs = selected_pairs.head(limit).copy()
st.caption(f"Filtro completo: {formato(len(selected_pairs))} pares, {formato(selected_pairs.trips.sum())} viajes. "
           f"La tabla muestra {len(top_pairs)} pares con {formato(top_pairs.trips.sum())} viajes. "
           f"Las cuotas conservan como denominador los {formato(station_total)} viajes con ambos extremos identificados, no solo los pares visibles.")
st.caption("Origen y destino no describen el itinerario recorrido. Los viajes a la misma estación no se eliminan ni se "
           "interpretan automáticamente como errores; tampoco equivalen a desplazamientos entre estaciones distintas.")
if top_pairs.empty:
    st.info("No hay pares origen–destino con estos filtros.")
else:
    top_pairs["Cuota del total de viajes con estaciones (%)"] = 100 * top_pairs.share_of_station_trips
    st.dataframe(top_pairs[["origin_station_id", "origin_station_name", "destination_station_id", "destination_station_name", "trips",
                            "Cuota del total de viajes con estaciones (%)", "rank_all_pairs"]].rename(columns={
        "origin_station_id": "ID origen", "origin_station_name": "Origen", "destination_station_id": "ID destino",
        "destination_station_name": "Destino", "trips": "Viajes", "rank_all_pairs": "Rango original entre todos los pares"}),
        hide_index=True, use_container_width=True)
    st.download_button("Descargar todos los pares del filtro (CSV)", selected_pairs.to_csv(index=False).encode("utf-8-sig"),
                       file_name="pares_od_2023_periodo_completo_filtrados.csv", mime="text/csv", key="v23_csv")

with st.expander("Auditorías de calidad y alcance del notebook 11"):
    st.dataframe(quality.rename(columns={"control": "Control", "value": "Valor", "interpretation": "Interpretación"}), hide_index=True, use_container_width=True)
    st.dataframe(scope.rename(columns={"control": "Control", "value": "Valor"}), hide_index=True, use_container_width=True)
    st.caption("Los registros con firmas repetidas no se eliminaron porque no existe un identificador de viaje fiable. "
               "La aplicación no vuelve a limpiar los datos ni añade estados, etiquetas, predicciones o recomendaciones para 2023.")
