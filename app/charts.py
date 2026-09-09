"""Gráficos de presentación con colores consistentes y sin inferencia."""

import plotly.express as px
import plotly.graph_objects as go

from app.riesgo import ACCIONES, CLASES


COLORES = {"Estable": "#2878B5", "Riesgo de vaciado": "#D97706", "Riesgo de saturación": "#7C3AED"}


def mapa_riesgo(escenario, callejero=True):
    """Un punto por estación del escenario, con probabilidades sin redondear en origen."""
    if escenario.empty:
        raise ValueError("No hay estaciones para dibujar el mapa.")
    display = escenario.copy()
    display["Clase predicha"] = display.prediction.map(CLASES)
    display["Señal técnica"] = display.model_action_signal.map(ACCIONES)
    display["Estación"] = display.station_number.astype(str) + " · " + display.station_name
    figure = px.scatter_map(
        display, lat="latitude", lon="longitude", color="Clase predicha",
        color_discrete_map=COLORES, category_orders={"Clase predicha": list(COLORES)},
        hover_name="Estación", custom_data=["station_id"],
        hover_data={"station_id": True, "capacity": True, "bikes_available": True,
                    "docks_available": True, "occupancy_ratio": ":.1%", "Señal técnica": True,
                    "probability_0": ":.2%", "probability_1": ":.2%", "probability_2": ":.2%",
                    "latitude": False, "longitude": False},
        labels={"station_id": "ID", "capacity": "Capacidad", "bikes_available": "Bicicletas",
                "docks_available": "Anclajes disponibles", "occupancy_ratio": "Ocupación",
                "probability_0": "P(estable)", "probability_1": "P(vaciado)", "probability_2": "P(saturación)"},
        map_style="carto-positron" if callejero else "white-bg",
        center={"lat": float(display.latitude.mean()), "lon": float(display.longitude.mean())},
        zoom=14 if len(display) == 1 else 11, height=510,
    )
    figure.update_traces(marker={"size": 13, "opacity": 0.9})
    figure.update_layout(margin={"l": 0, "r": 0, "t": 8, "b": 0},
                         legend={"title": {"text": "Clase predicha"}, "orientation": "h", "y": 1.08,
                                 "itemclick": False, "itemdoubleclick": False})
    return figure


def mapa_transferencias(transferencias, escenario, callejero=True):
    """Segmentos entre extremos exportados, no rutas viarias ni itinerarios."""
    if transferencias.empty:
        raise ValueError("No hay transferencias para dibujar.")
    ids = set(transferencias.donor_station_id) | set(transferencias.receiver_station_id)
    points = escenario.loc[escenario.station_id.isin(ids)].copy()
    positions = points.set_index("station_id", verify_integrity=True)
    if set(positions.index) != ids:
        raise ValueError("Falta el contexto geográfico de un extremo de la transferencia.")
    lat, lon, labels = [], [], []
    for row in transferencias.itertuples():
        donor, receiver = positions.loc[row.donor_station_id], positions.loc[row.receiver_station_id]
        text = (f"{row.donor_station_name} (ID {row.donor_station_id}) → "
                f"{row.receiver_station_name} (ID {row.receiver_station_id})"
                f"<br>{row.units} bicicletas propuestas · {row.distance_km:.2f} km geográficos")
        lat.extend([donor.latitude, receiver.latitude, None])
        lon.extend([donor.longitude, receiver.longitude, None])
        labels.extend([text, text, None])
    figure = go.Figure(go.Scattermap(lat=lat, lon=lon, mode="lines",
                                    line={"width": 2, "color": "#64748B"}, text=labels,
                                    hovertemplate="%{text}<extra></extra>", showlegend=False))
    for trace in mapa_riesgo(points, callejero).data:
        figure.add_trace(trace)
    figure.update_layout(map={"style": "carto-positron" if callejero else "white-bg",
                              "center": {"lat": float(points.latitude.mean()), "lon": float(points.longitude.mean())}, "zoom": 11},
                         height=480, margin={"l": 0, "r": 0, "t": 10, "b": 0},
                         legend={"orientation": "h", "y": 1.08, "itemclick": False, "itemdoubleclick": False})
    return figure


def probabilidades_estacion(row):
    values = [float(row[f"probability_{code}"]) for code in CLASES]
    figure = go.Figure(go.Bar(
        x=list(CLASES.values()), y=values, marker_color=list(COLORES.values()),
        text=[f"{value:.2%}" for value in values], textposition="auto",
        hovertemplate="%{x}: %{y:.6%}<extra></extra>",
    ))
    figure.update_layout(height=280, margin={"l": 0, "r": 0, "t": 10, "b": 0},
                         yaxis={"range": [0, 1], "tickformat": ".0%", "title": "Probabilidad guardada"},
                         xaxis={"title": None}, showlegend=False)
    return figure
