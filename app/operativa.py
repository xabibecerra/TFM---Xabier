"""Consulta y auditoría de propuestas guardadas. No calcula emparejamientos."""

import numpy as np
import pandas as pd

from app.riesgo import TIME


ESTADOS = {
    "transferencia_asignada": "Cobertura completa propuesta",
    "cobertura_parcial": "Cobertura parcial propuesta",
    "sin_pareja_factible_en_radio": "Sin asignación en el emparejamiento",
    "monitorizar_sin_brecha_operativa_actual": "Monitorizar: sin brecha actual",
}
PARES = {
    "riesgos_complementarios": "Saturación → vaciado",
    "apoyo_estable_a_vaciado": "Apoyo estable → vaciado",
    "saturacion_a_estacion_estable": "Saturación → apoyo estable",
}


def seleccionar(frame, instante, estacion=None, transferencias=False):
    mask = frame[TIME].eq(pd.Timestamp(instante))
    if estacion is not None:
        mask &= (frame.donor_station_id.eq(estacion) | frame.receiver_station_id.eq(estacion)
                 if transferencias else frame.station_id.eq(estacion))
    return frame.loc[mask].copy()


def filtrar_candidatos(frame, estados, clases=(1, 2)):
    """El score solo ordena la presentación; no se aplica un corte ni se recalcula el rango."""
    return frame.loc[frame.recommendation_status.isin(estados) & frame.prediction.isin(clases)].sort_values(
        ["prediction", "priority_rank_within_hour_and_action", "station_id"], kind="stable").copy()


def resumen_cobertura(candidatos):
    """Separar recepción/retirada evita llamar bicicletas únicas a necesidades en dos extremos."""
    records = []
    for code, action in [(1, "Reposición"), (2, "Retirada")]:
        part = candidatos.loc[candidatos.prediction.eq(code)]
        requested = int(part.requested_units.sum())
        assigned = int(part.assigned_units.sum())
        records.append({"Acción candidata": action, "Estaciones candidatas": len(part),
                        "Unidades solicitadas": requested, "Unidades asignadas": assigned,
                        "Unidades sin cubrir": int(part.uncovered_units.sum()),
                        "Cobertura de unidades (%)": 100 * assigned / requested if requested else None})
    return pd.DataFrame(records)


def auditar_escenario(predicciones, candidatos, transferencias, no_resueltos, politica):
    """Comprueba un escenario completo antes de filtrarlo; nunca altera las propuestas.

    Reconstruye únicamente los límites deterministas de la política para auditar
    las cantidades exportadas, no para asignar nuevas unidades o buscar parejas.
    """
    policy = politica.set_index("parameter").value.to_dict()
    low, high = float(policy["operational_min_ratio"]), float(policy["operational_max_ratio"])
    distance, units = float(policy["max_pair_distance_km"]), float(policy["max_units_per_transfer"])
    if not (0 <= low < high <= 1 and distance > 0 and units >= 1 and policy["risk_score_threshold"] == "none"):
        raise ValueError("Política operativa inválida o con un umbral de riesgo no esperado.")
    p = predicciones.set_index("station_id", verify_integrity=True)
    t, c = transferencias, candidatos
    if (p.empty or predicciones[TIME].nunique() != 1
            or any(not frame[TIME].isin(predicciones[TIME]).all() for frame in [c, t, no_resueltos])):
        raise ValueError("La auditoría requiere un único instante disponible y coincidente.")
    if c.station_id.duplicated().any() or no_resueltos.station_id.duplicated().any():
        raise ValueError("Hay estaciones candidatas duplicadas en el escenario.")
    expected_actions = {0: "monitorizar", 1: "candidata_reposicion_bicicletas", 2: "candidata_retirada_bicicletas"}
    checks = []
    def check(label, passed):
        checks.append({"Comprobación": label, "Resultado": "Correcto" if bool(passed) else "ERROR"})
    check("Señal coherente con la predicción, sin acciones desde riesgos relativos",
          p.model_action_signal.eq(p.prediction.map(expected_actions)).all())
    check("Candidatas solo de clases críticas", set(c.station_id) == set(p.index[p.prediction.isin([1, 2])])
          and c.prediction.isin([1, 2]).all()
          and c.prediction.eq(c.station_id.map(p.prediction)).all()
          and c.model_action_signal.eq(c.prediction.map(expected_actions)).all())
    check("Extremos existentes y diferentes", t.donor_station_id.isin(p.index).all()
          and t.receiver_station_id.isin(p.index).all() and t.donor_station_id.ne(t.receiver_station_id).all())
    check("Distancia y unidades por pareja", t.distance_km.between(0, distance + 1e-9).all()
          and t.units.between(1, units).all() and t.units.mod(1).eq(0).all())
    dp, rp = t.donor_station_id.map(p.prediction), t.receiver_station_id.map(p.prediction)
    check("Compatibilidad de clases; apoyo estable permitido", dp.isin([0, 2]).all() and rp.isin([0, 1]).all()
          and (dp.eq(2) | rp.eq(1)).all() and t.donor_prediction.eq(dp).all() and t.receiver_prediction.eq(rp).all())
    outgoing = t.groupby("donor_station_id").units.sum().reindex(p.index, fill_value=0)
    incoming = t.groupby("receiver_station_id").units.sum().reindex(p.index, fill_value=0)
    supply = (p.bikes_available - np.floor(p.capacity * high)).clip(lower=0)
    need = np.minimum((np.ceil(p.capacity * low) - p.bikes_available).clip(lower=0),
                      (p.docks_available - p.reservations_count).clip(lower=0))
    check("Límites acumulados de donación y recepción", outgoing.le(supply).all() and incoming.le(need).all())
    after = p.bikes_available + incoming - outgoing
    check("Capacidad y conservación del balance", after.between(0, p.capacity).all()
          and incoming.sum() == outgoing.sum() == t.units.sum() and after.sum() == p.bikes_available.sum())
    expected_assigned = c.station_id.map(incoming).where(c.prediction.eq(1), c.station_id.map(outgoing))
    expected_requested = c.station_id.map(need).where(c.prediction.eq(1), c.station_id.map(supply))
    check("Cobertura coherente con transferencias y brecha", c.assigned_units.eq(expected_assigned).all()
          and c.requested_units.eq(expected_requested).all() and c.assigned_units.ge(0).all()
          and c.assigned_units.le(c.requested_units).all()
          and c.uncovered_units.eq(c.requested_units - c.assigned_units).all())
    expected_status = np.select([c.requested_units.eq(0), c.assigned_units.eq(0), c.assigned_units.lt(c.requested_units)],
                               ["monitorizar_sin_brecha_operativa_actual", "sin_pareja_factible_en_radio", "cobertura_parcial"],
                               default="transferencia_asignada")
    check("Estados de cobertura coherentes", c.recommendation_status.eq(expected_status).all())
    expected_unresolved = c.loc[c.recommendation_status.ne("transferencia_asignada")].sort_values("station_id").reset_index(drop=True)
    check("Archivo de no resueltos coincide con las candidatas", expected_unresolved.equals(
        no_resueltos.sort_values("station_id").reset_index(drop=True)))
    result = pd.DataFrame(checks)
    if result.Resultado.eq("ERROR").any():
        failures = result.loc[result.Resultado.eq("ERROR"), "Comprobación"].tolist()
        raise ValueError("Inconsistencia en las propuestas guardadas: " + "; ".join(failures))
    return result
