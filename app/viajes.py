"""Presentación descriptiva de viajes: sin estados, riesgo o inferencia."""

import pandas as pd
import plotly.express as px


DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
CONTROLES = ["station_state_data_used", "risk_labels_created", "model_predictions_used",
             "model_evaluation_performed", "probabilities_or_thresholds_adjusted", "operational_recommendations_generated"]


def comprobar_alcance(audit):
    if audit.control.duplicated().any():
        raise ValueError("La auditoría de alcance tiene controles duplicados.")
    controls = audit.set_index("control").value.to_dict()
    if any(str(controls.get(key)).lower() != "false" for key in CONTROLES):
        raise ValueError("Falta una garantía de separación entre viajes descriptivos y modelización predictiva.")
    if controls.get("net_flow_interpretation") != "balance_de_viajes_no_disponibilidad":
        raise ValueError("El balance exportado no tiene el alcance descriptivo esperado.")
    return controls


def filtrar_meses(frame, meses):
    return frame.loc[frame.month.isin(meses)].copy()


def dias_para_mostrar(frame):
    result = frame.sort_values("date").copy()
    result["Viajes observados"] = result.trips.where(result.observed_day)
    result["Cobertura"] = "Sin viajes registrados / sin cobertura confirmada"
    result.loc[result.observed_day, "Cobertura"] = "Día parcial"
    result.loc[result.complete_day & result.observed_day, "Cobertura"] = "Día completo según criterio exportado"
    return result


def seleccionar_od(frame, estacion=None, sentido="Cualquier extremo", tipo="Estaciones distintas"):
    mask = pd.Series(True, index=frame.index)
    if estacion is not None:
        origin, destination = frame.origin_station_id.eq(estacion), frame.destination_station_id.eq(estacion)
        mask &= origin if sentido == "Origen" else destination if sentido == "Destino" else origin | destination
    if tipo == "Estaciones distintas":
        mask &= ~frame.same_station
    elif tipo == "Misma estación":
        mask &= frame.same_station
    elif tipo != "Todos":
        raise ValueError("Tipo de par origen–destino desconocido.")
    return frame.loc[mask].sort_values(["trips", "origin_station_id", "destination_station_id"], ascending=[False, True, True]).copy()


def mapa_actividad(frame, limite_color, callejero=True):
    spatial = frame.dropna(subset=["latitude", "longitude"])
    if spatial.empty:
        raise ValueError("No hay coordenadas exportadas para esta selección.")
    fig = px.scatter_map(spatial, lat="latitude", lon="longitude", size="total_activity", size_max=30,
                          color="net_arrivals", color_continuous_scale="Tealrose", range_color=[-limite_color, limite_color],
                          hover_name="station_name", hover_data={"station_id": True, "departures": True, "arrivals": True,
                          "total_activity": True, "net_arrivals": True, "latitude": False, "longitude": False},
                          labels={"departures": "Salidas", "arrivals": "Llegadas", "net_arrivals": "Llegadas − salidas",
                                  "total_activity": "Actividad (extremos de viaje)", "station_id": "ID"},
                          map_style="carto-positron" if callejero else "white-bg", zoom=11,
                          center={"lat": float(spatial.latitude.mean()), "lon": float(spatial.longitude.mean())})
    fig.update_layout(height=440, margin={"l": 0, "r": 0, "t": 10, "b": 0})
    return fig
