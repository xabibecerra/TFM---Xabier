"""Transformaciones de presentación del riesgo; nunca producen predicciones."""

import pandas as pd


TIME = "fecha_hora_local"
CLASES = {0: "Estable", 1: "Riesgo de vaciado", 2: "Riesgo de saturación"}
ACCIONES = {
    "monitorizar": "Monitorizar",
    "candidata_reposicion_bicicletas": "Candidata técnica a reposición",
    "candidata_retirada_bicicletas": "Candidata técnica a retirada",
}


def filtrar_escenario(predicciones, instante, clases=(0, 1, 2), estacion=None):
    """Devuelve una copia filtrada; no usa scores ni critical_risk_type."""
    instant = pd.Timestamp(instante)
    if pd.isna(instant) or instant.tzinfo is not None or not predicciones[TIME].eq(instant).any():
        raise ValueError("Selecciona un instante disponible en las predicciones congeladas.")
    if not set(clases).issubset(CLASES):
        raise ValueError("Clase de riesgo desconocida.")
    mask = predicciones[TIME].eq(instant) & predicciones.prediction.isin(clases)
    if estacion is not None:
        mask &= predicciones.station_id.eq(estacion)
    return predicciones.loc[mask].copy()


def recuentos_clases(escenario):
    return {code: int(escenario.prediction.eq(code).sum()) for code in CLASES}


def tabla_falsos_negativos(row):
    """Dos clases con denominadores explícitos; sin soporte la tasa es ausente."""
    records = []
    for risk, label in [("empty", "Vaciado"), ("full", "Saturación")]:
        support = row.get(f"support_{risk}") if row is not None else None
        fn = row.get(f"false_negatives_{risk}") if row is not None else None
        enough = row.get(f"enough_support_{risk}") if row is not None else None
        rate = 100 * fn / support if pd.notna(support) and support > 0 and pd.notna(fn) else None
        support_label = "No exportado" if pd.isna(enough) else ("Sí" if enough else "No")
        records.append({"Riesgo real": label, "Soporte real": support, "Falsos negativos": fn,
                        "Tasa FN (%)": rate, "Soporte suficiente (notebook 09)": support_label})
    return pd.DataFrame(records)


def formato(value, decimales=0, unidad=""):
    if pd.isna(value):
        return "No disponible"
    return f"{value:,.{decimales}f}".replace(",", "_").replace(".", ",").replace("_", ".") + unidad
