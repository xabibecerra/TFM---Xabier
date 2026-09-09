"""Presentación de importancias y errores exportados, sin inferencia ni ajustes."""

import pandas as pd
import plotly.express as px


def comparar_importancias(frame, ponderada=False):
    """Normaliza sobre TODAS las variables, nunca sobre el top visible."""
    result = frame.copy()
    value = "mean_abs_shap_test_weighted" if ponderada else "mean_abs_shap_macro"
    rank = "shap_test_weighted_rank" if ponderada else "shap_macro_rank"
    total = result[value].sum(min_count=1)
    result["SHAP (%)"] = 100 * result[value] / total if pd.notna(total) and total > 0 else float("nan")
    result["Ganancia total (%)"] = 100 * result.total_gain_share
    result["Rango SHAP"] = result[rank]
    result["Rango ganancia"] = result.gain_rank
    result["Diferencia de rango (ganancia − SHAP)"] = result.gain_rank - result[rank]
    return result


def union_top(frame, n):
    """Incluye las líderes de ambos métodos, no solo las preferidas por SHAP."""
    if n < 1:
        raise ValueError("El número de variables debe ser positivo.")
    return frame.loc[frame["Rango SHAP"].le(n) | frame["Rango ganancia"].le(n)].sort_values(
        ["Rango SHAP", "original_feature"], kind="stable").copy()


def grafico_comparacion(frame):
    values = frame.melt(id_vars="original_feature", value_vars=["Ganancia total (%)", "SHAP (%)"],
                        var_name="Método", value_name="Importancia relativa (%)")
    fig = px.bar(values, x="Importancia relativa (%)", y="original_feature", color="Método", barmode="group",
                 orientation="h", labels={"original_feature": "Variable"},
                 color_discrete_map={"Ganancia total (%)": "#2878B5", "SHAP (%)": "#7C3AED"})
    fig.update_layout(yaxis={"categoryorder": "array", "categoryarray": frame.original_feature.tolist(), "autorange": "reversed"},
                      height=max(350, len(frame) * 38), margin={"l": 0, "r": 0, "t": 10, "b": 0},
                      legend={"orientation": "h", "y": 1.06})
    return fig


def errores_clase(frame, clase, grupo):
    """FN/soporte de la clase real; cero soporte produce tasa ausente."""
    if clase not in [1, 2]:
        raise ValueError("El desglose de falsos negativos admite vaciado o saturación.")
    suffix = "empty" if clase == 1 else "full"
    result = frame[[grupo]].copy()
    result["Soporte real"] = frame[f"support_{suffix}"]
    result["Falsos negativos"] = frame[f"false_negatives_{suffix}"]
    support, fn = result["Soporte real"], result["Falsos negativos"]
    if ((support.dropna() < 0).any() or (fn.dropna() < 0).any() or fn.gt(support).any()):
        raise ValueError("Los falsos negativos y su soporte son incoherentes.")
    result["Tasa FN (%)"] = 100 * fn / support.where(support.gt(0))
    flag = f"enough_support_{suffix}"
    if flag in frame:
        result["Soporte suficiente (notebook 09)"] = frame[flag].map({True: "Sí", False: "No"}).fillna("No exportado")
    if "station_name" in frame:
        result["Estación"] = frame.station_name
    return result


def grafico_errores_hora(frame):
    view = frame.sort_values("hour")
    fig = px.line(view, x="hour", y="Tasa FN (%)", markers=True,
                  hover_data=["Soporte real", "Falsos negativos"], labels={"hour": "Hora local"})
    fig.update_traces(connectgaps=False, line_color="#2878B5")
    for hour in [8, 18, 19]:
        fig.add_vline(x=hour, line_dash="dot", line_color="#D97706", opacity=0.6)
    fig.update_layout(height=330, xaxis={"tickmode": "linear", "dtick": 1},
                      yaxis={"range": [0, 100]}, margin={"l": 0, "r": 0, "t": 10, "b": 0})
    return fig
