"""Fase 7: validar resultados congelados y preparar Parquet para Streamlit.

Uso desde la raíz del proyecto:
    python scripts/preparar_datos_app.py --solo-validar
    python scripts/preparar_datos_app.py

No ejecuta notebooks, carga modelos, ajusta umbrales ni crea recomendaciones.
Conserva todas las filas y columnas. Solo tipa fechas e identificadores y cambia
el formato de almacenamiento. Los CSV originales nunca se modifican.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow


ROOT = Path(__file__).resolve().parents[1]
MODEL = Path("notebooks/Datos modelado")
INTERP = MODEL / "interpretabilidad_modelo_final"
OPER = MODEL / "recomendaciones_operativas"
TEST = MODEL / "test_final_2022"
TRIPS = Path("notebooks/Datos analiticos/analisis_descriptivo_viajes_2023_enero_febrero")
TIME = "fecha_hora_local"
KEY = [TIME, "station_id"]
NAMES = {0: "estable", 1: "riesgo_vaciado", 2: "riesgo_saturacion"}
SIGNALS = {
    0: "monitorizar",
    1: "candidata_reposicion_bicicletas",
    2: "candidata_retirada_bicicletas",
}

# Salida -> (fuente, columnas obligatorias). No se eliminan columnas adicionales.
TABLES = {
    "predicciones_contexto_2022": (INTERP / "entrada_10_predicciones_y_contexto.csv",
        KEY + ["station_name", "station_number", "latitude", "longitude", "capacity",
               "bikes_available", "docks_available", "reservations_count", "prediction",
               "predicted_risk_name", "model_action_signal", "probability_0",
               "probability_1", "probability_2", "critical_risk_score", "critical_risk_type"]),
    "candidatos_2022": (OPER / "candidatos_tecnicos_priorizados.csv",
        KEY + ["prediction", "model_action_signal", "requested_units", "assigned_units",
               "uncovered_units", "candidate_role", "recommendation_status",
               "class_shap_explanation", "operational_explanation",
               "receiver_units_assigned", "donor_units_assigned"]),
    "transferencias_2022": (OPER / "transferencias_factibles.csv",
        [TIME, "donor_station_id", "receiver_station_id", "donor_prediction",
         "receiver_prediction", "units", "distance_km", "pair_type", "risk_score_for_ordering"]),
    "candidatos_no_resueltos_2022": (OPER / "candidatos_no_resueltos.csv",
        KEY + ["recommendation_status"]),
    "factores_por_clase": (INTERP / "entrada_10_factores_por_clase.csv",
        ["class_value", "class_name", "original_feature", "mean_abs_shap", "interpretation_scope"]),
    "horas_sensibles": (INTERP / "entrada_10_horas_sensibles.csv",
        ["hour", "support_empty", "false_negatives_empty", "support_full", "false_negatives_full"]),
    "estaciones_sensibles": (INTERP / "entrada_10_estaciones_sensibles.csv",
        ["station_id", "support_empty", "false_negatives_empty", "support_full", "false_negatives_full",
         "enough_support_empty", "enough_support_full"]),
    "comparacion_gain_vs_shap": (INTERP / "comparacion_gain_vs_shap.csv",
        ["original_feature", "gain_rank", "shap_macro_rank"]),
    "shap_importancia_global": (INTERP / "shap_importancia_global.csv",
        ["original_feature", "mean_abs_shap_macro", "mean_abs_shap_test_weighted"]),
    "shap_importancia_por_clase": (INTERP / "shap_importancia_agregada_por_clase.csv",
        ["class_value", "class_name", "original_feature", "mean_abs_shap"]),
    "explicaciones_shap_por_clase": (OPER / "explicaciones_shap_por_clase.csv",
        ["class_value", "class_name", "global_shap_explanation"]),
    "politica_operativa": (OPER / "politica_operativa.csv", ["parameter", "value", "source"]),
    "metricas_test_2022": (TEST / "comparacion_test_final_2022.csv", ["model", "f1_macro", "test_rows"]),
    "informe_por_clase_test_2022": (TEST / "informe_por_clase_test_final_2022.csv",
        ["model", "class", "precision", "recall", "f1-score", "support"]),
    "matrices_confusion_test_2022": (TEST / "matrices_confusion_test_final_2022.csv",
        ["model", "real", "predicted", "count"]),
    "errores_por_mes_2022": (INTERP / "errores_por_mes_modelo_final.csv", ["month"]),
    "resumen_mensual_2023": (TRIPS / "resumen_mensual_viajes_2023.csv",
        ["month", "observed_trips", "complete_days", "month_complete"]),
    "cobertura_mensual_2023": (TRIPS / "cobertura_mensual_2023.csv",
        ["month", "complete_days", "first_trip", "last_trip", "month_complete"]),
    "viajes_por_dia_2023": (TRIPS / "viajes_por_dia_2023.csv",
        ["date", "month", "trips", "complete_day", "first_trip", "last_trip"]),
    "viajes_por_hora_2023": (TRIPS / "viajes_por_hora_2023.csv",
        ["month", "hour", "trips", "complete_days", "mean_trips_per_complete_day"]),
    "viajes_por_dia_semana_2023": (TRIPS / "viajes_por_dia_semana_2023.csv",
        ["month", "weekday", "trips", "days"]),
    "viajes_por_segmento_semana_2023": (TRIPS / "viajes_por_segmento_semana_2023.csv",
        ["month", "week_segment", "days", "mean_trips_per_day"]),
    "actividad_estaciones_2023": (TRIPS / "actividad_por_estacion_2023.csv",
        ["station_id", "departures", "arrivals", "latitude", "longitude"]),
    "pares_od_2023": (TRIPS / "pares_origen_destino_2023.csv",
        ["origin_station_id", "destination_station_id", "trips"]),
    "resumen_duracion_2023": (TRIPS / "resumen_duracion_viajes_2023.csv",
        ["month", "valid_duration_trips", "median_minutes", "p95_minutes"]),
    "auditoria_alcance_2023": (TRIPS / "auditoria_alcance_descriptivo_2023.csv", ["control", "value"]),
    "auditoria_calidad_2023": (TRIPS / "auditoria_calidad_viajes_2023.csv", ["control", "value"]),
}
MANIFESTS = {
    "test": TEST / "manifiesto_test_final_2022.json",
    "operaciones": OPER / "manifiesto_recomendaciones_operativas.json",
    "viajes": TRIPS / "manifiesto_analisis_descriptivo_2023.json",
}


def require(condition, message):
    """No usar assert: las validaciones deben funcionar también con python -O."""
    if not bool(condition):
        raise ValueError(message)


def sha256(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def load_inputs(root):
    paths = [path for path, _ in TABLES.values()] + list(MANIFESTS.values())
    missing = [str(path) for path in paths if not (root / path).is_file()]
    require(not missing, "Faltan fuentes:\n" + "\n".join(missing))
    fingerprints = {str(path): sha256(root / path) for path in paths}
    tables = {}
    for name, (path, required) in TABLES.items():
        # 'none' en la política es texto significativo, no un valor ausente.
        table = pd.read_csv(root / path, encoding="utf-8-sig", keep_default_na=False,
                            na_values=[""], float_precision="round_trip", low_memory=False,
                            dtype={"station_number": "string"})
        require(set(required).issubset(table.columns),
                f"{path.name}: faltan columnas {sorted(set(required) - set(table.columns))}")
        require(not table.empty, f"{path.name}: tabla vacía")
        for column in (TIME, "date", "first_trip", "last_trip"):
            if column in table:
                table[column] = pd.to_datetime(table[column], errors="raise")
                require(table[column].dt.tz is None, f"{path.name}: zona horaria inesperada")
        tables[name] = table
    metadata = {name: json.loads((root / path).read_text(encoding="utf-8-sig"))
                for name, path in MANIFESTS.items()}
    return tables, metadata, fingerprints


def validate_predictions(p):
    require(not p.duplicated(KEY).any(), "Predicciones: estación-hora duplicada")
    require(p[TIME].notna().all(), "Predicciones: fecha ausente")
    require(p[TIME].ge("2022-11-01").all() and p[TIME].lt("2023-01-01").all(),
            "Predicciones fuera del test final de noviembre-diciembre de 2022")
    require(p["station_id"].notna().all(), "Predicciones: identificador ausente")
    require(p["prediction"].isin(NAMES).all(), "Clase de predicción desconocida")
    require(p["model_action_signal"].eq(p["prediction"].map(SIGNALS)).all(),
            "Señal incompatible con prediction; una estable solo puede originar monitorización")
    require(p["predicted_risk_name"].eq(p["prediction"].map(NAMES)).all(), "Nombre de clase incoherente")
    probs = p[["probability_0", "probability_1", "probability_2"]].to_numpy(dtype=float)
    require(np.isfinite(probs).all() and ((probs >= 0) & (probs <= 1)).all(), "Probabilidades inválidas")
    # Tolerancia de representación numérica, no umbral de clasificación.
    require(np.allclose(probs.sum(axis=1), 1, atol=1e-6, rtol=0), "Las probabilidades no suman 1")
    require(np.allclose(p["critical_risk_score"], probs[:, 1:].max(axis=1), atol=1e-6, rtol=0),
            "critical_risk_score no coincide con las probabilidades guardadas")
    require(p["latitude"].between(-90, 90).all() and p["longitude"].between(-180, 180).all(),
            "Coordenadas ausentes o fuera de rango")
    for column in ["capacity", "bikes_available", "docks_available", "reservations_count"]:
        require(p[column].notna().all() and np.isfinite(p[column]).all() and p[column].ge(0).all(),
                f"Disponibilidad inválida: {column}")
    # critical_risk_type NO se usa para generar, corregir o validar una acción estable.


def validate_operations(p, c, t, unresolved, policy):
    require(not c.duplicated(KEY).any(), "Candidatos: estación-hora duplicada")
    require(c["prediction"].isin([1, 2]).all(), "Una estación estable figura como candidata por riesgo propio")
    expected = p.loc[p.prediction.isin([1, 2])].set_index(KEY).sort_index()
    actual = c.set_index(KEY).sort_index()
    pd.testing.assert_frame_equal(actual[p.columns.drop(KEY)], expected, check_exact=True)
    require(c["candidate_role"].eq(c.prediction.map({1: "receiver", 2: "donor"})).all(), "Rol crítico incoherente")
    require(c["requested_units"].ge(0).all() and c["assigned_units"].ge(0).all(), "Unidades negativas")
    require(c["assigned_units"].le(c["requested_units"]).all(), "Asignación superior a la petición")
    require(c["uncovered_units"].eq(c["requested_units"] - c["assigned_units"]).all(), "Brecha sin cubrir incoherente")
    status = np.select(
        [c.requested_units.eq(0), c.assigned_units.eq(c.requested_units), c.assigned_units.gt(0)],
        ["monitorizar_sin_brecha_operativa_actual", "transferencia_asignada", "cobertura_parcial"],
        default="sin_pareja_factible_en_radio")
    require(c.recommendation_status.eq(status).all(), "Estado operativo incoherente con las unidades")
    expected_unresolved = c.loc[c.recommendation_status.ne("transferencia_asignada")]
    pd.testing.assert_frame_equal(unresolved.set_index(KEY).sort_index(),
                                  expected_unresolved.set_index(KEY).sort_index(), check_exact=True)
    require(t["units"].between(1, policy["max_units_per_transfer"]).all()
            and t["units"].mod(1).eq(0).all(), "Unidades por transferencia inválidas")
    require(t["distance_km"].between(0, policy["max_pair_distance_km"] + 1e-9).all(),
            "Distancia fuera de la política congelada")
    require(t.donor_station_id.ne(t.receiver_station_id).all(), "Transferencia a la misma estación")
    require(t.donor_prediction.isin([0, 2]).all() and t.receiver_prediction.isin([0, 1]).all(), "Roles incompatibles")
    require((t.donor_prediction.eq(2) | t.receiver_prediction.eq(1)).all(), "Pareja estable-estable")

    # Reconciliar unidades almacenadas con la política ya definida, sin emparejar de nuevo.
    indexed = p.set_index(KEY)
    for role in ["donor", "receiver"]:
        ids = pd.MultiIndex.from_frame(t[[TIME, f"{role}_station_id"]].set_axis(KEY, axis=1))
        require(ids.isin(indexed.index).all(), f"{role}: estación-hora ausente en el contexto")
        require(np.array_equal(indexed.loc[ids, "prediction"], t[f"{role}_prediction"]),
                f"{role}: predicción distinta de la congelada")
        totals = t.groupby([TIME, f"{role}_station_id"])["units"].sum()
        totals.index.names = KEY
        state = indexed.loc[totals.index]
        if role == "donor":
            limit = np.maximum(0, state.bikes_available - np.floor(state.capacity * policy["operational_max_ratio"]))
        else:
            limit = np.minimum(np.maximum(0, np.ceil(state.capacity * policy["operational_min_ratio"]) - state.bikes_available),
                               np.maximum(0, state.docks_available - state.reservations_count))
        require(totals.le(limit).all(), f"{role}: bicicletas asignadas exceden el margen disponible")
        assigned = totals.reindex(actual.index, fill_value=0)
        require(np.array_equal(assigned, actual[f"{role}_units_assigned"]), f"{role}: unidades no reconciliadas")
    require(c.assigned_units.eq(c.receiver_units_assigned + c.donor_units_assigned).all(), "Asignación total incoherente")


def validate_all(tables, metadata):
    p, c, t, u = [tables[name] for name in ["predicciones_contexto_2022", "candidatos_2022",
                                          "transferencias_2022", "candidatos_no_resueltos_2022"]]
    validate_predictions(p)
    policy = metadata["operaciones"]["policy"]
    require(policy == {"operational_min_ratio": 0.3, "operational_max_ratio": 0.7,
                       "max_pair_distance_km": 3.0, "max_units_per_transfer": 10}, "Ha cambiado la política operativa congelada")
    policy_csv = tables["politica_operativa"].set_index("parameter")["value"]
    for key, value in policy.items():
        require(float(policy_csv[key]) == value, f"Política CSV/JSON distinta: {key}")
    require(policy_csv["risk_score_threshold"] == "none", "Se ha introducido un umbral operativo")
    validate_operations(p, c, t, u, policy)
    # Referencia del experimento actual, no parámetros ajustables desde la aplicación.
    counts = {"predicciones": len(p), "candidatos": len(c), "transferencias": len(t),
              "unidades_por_escenarios": int(t.units.sum()), "no_resueltos": len(u)}
    require(counts == {"predicciones": 379104, "candidatos": 49702, "transferencias": 41630,
                       "unidades_por_escenarios": 104360, "no_resueltos": 30299},
            f"El snapshot no coincide con los resultados revisados: {counts}")
    require(p.prediction.value_counts().to_dict() == {0: 329402, 1: 43173, 2: 6529}, "Distribución de predicciones diferente")
    require(metadata["test"]["test_rows"] == len(p) and metadata["test"]["fit_calls"] == 0,
            "Manifiesto del test incoherente")
    require(metadata["test"]["final_model"] == "xgboost_refined", "Modelo final inesperado")
    for name in ["horas_sensibles", "estaciones_sensibles"]:
        for risk in ["empty", "full"]:
            support, fn = tables[name][f"support_{risk}"], tables[name][f"false_negatives_{risk}"]
            require(support.ge(0).all() and fn.ge(0).all() and fn.le(support).all(), f"{name}: soporte/FN incoherentes")
    require(tables["factores_por_clase"].interpretation_scope.eq("asociacion_predictiva_no_causal").all(),
            "Alcance SHAP inesperado")

    trips = tables["resumen_mensual_2023"].set_index("month")
    coverage = tables["cobertura_mensual_2023"].set_index("month")
    require(trips.observed_trips.to_dict() == {"2023-01": 295923, "2023-02": 168494}, "Volumen de viajes diferente")
    require(coverage.complete_days.to_dict() == {"2023-01": 31, "2023-02": 17}, "Cobertura de días diferente")
    require(bool(coverage.loc["2023-01", "month_complete"])
            and not bool(coverage.loc["2023-02", "month_complete"]), "Completitud mensual incoherente")
    require(coverage.loc["2023-02", "last_trip"] == pd.Timestamp("2023-02-18 07:22:48"), "Fin observado de febrero diferente")
    daily = tables["viajes_por_dia_2023"].groupby("month").trips.sum()
    require(daily.to_dict() == trips.observed_trips.to_dict(), "Viajes diarios y mensuales no reconciliados")
    guards = metadata["viajes"]["scope_guards"]
    require(all(guards[key] is False for key in ["station_state_data_used", "risk_labels_or_predictions_used",
                                                "operational_recommendations_generated"])
            and guards["february_is_partial"] is True, "El alcance descriptivo de 2023 ha cambiado")
    for name, (path, _) in TABLES.items():
        if path.parent == TRIPS:
            require(not set(["prediction", "model_action_signal", "critical_risk_score", "target"]).intersection(tables[name].columns),
                    f"{name}: contiene columnas predictivas ajenas al descriptivo")
    return counts


def check_sources_unchanged(root, fingerprints):
    require(all(sha256(root / path) == value for path, value in fingerprints.items()),
            "Las fuentes han cambiado durante la preparación. No se publicarán los datos.")


def export_tables(tables, metadata, fingerprints, counts, output):
    require(output != ROOT and ROOT / "notebooks" not in [output, *output.parents],
            "La salida no puede ser la raíz del proyecto ni estar dentro de notebooks")
    names = [f"{name}.parquet" for name in tables] + ["manifiesto_app.json"]
    conflicts = [name for name in names if (output / name).exists()]
    if conflicts:
        # Una repetición idéntica no reescribe nada. Nunca sobrescribir un snapshot distinto.
        manifest_path = output / "manifiesto_app.json"
        require(manifest_path.is_file(), "Ya hay salidas sin manifiesto; utiliza una carpeta nueva mediante --salida")
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        require(previous.get("fuentes_sha256") == fingerprints and previous.get("script_sha256") == sha256(Path(__file__)),
                "Ya hay una preparación diferente; conserva esa carpeta y utiliza otra mediante --salida")
        exports = previous.get("tablas", {})
        require(set(exports) == set(tables), "El manifiesto existente no incluye todas las tablas")
        require(all((output / f"{name}.parquet").is_file()
                    and sha256(output / f"{name}.parquet") == exports[name]["sha256"] for name in tables),
                "Faltan salidas o han cambiado; conserva la carpeta y utiliza otra mediante --salida")
        print("Los datos ya estaban preparados y coinciden con las fuentes. No se ha sobrescrito nada.")
        return

    with tempfile.TemporaryDirectory(prefix="tfm-fase7-") as temporary:
        staging = Path(temporary)
        manifest = {
            "version": 1, "creado_utc": datetime.now(timezone.utc).isoformat(),
            "script_sha256": sha256(Path(__file__)), "fuentes_sha256": fingerprints,
            "python": sys.version.split()[0], "pandas": pd.__version__, "pyarrow": pyarrow.__version__,
            "recuentos": counts, "modelo_final": metadata["test"]["final_model"],
            "periodos": {"entrenamiento": "2019, 2021 y enero-septiembre de 2022",
                         "validacion": "octubre de 2022", "test": "noviembre-diciembre de 2022",
                         "viajes_2023_observados": metadata["viajes"]["period_observed"]},
            "politica_operativa": metadata["operaciones"]["policy"],
            "clases": NAMES, "senales": SIGNALS,
            "alcance": {"modelo_reentrenado": False, "predicciones_recalculadas": False,
                        "umbrales_ajustados": False, "recomendaciones_recalculadas": False,
                        "shap": "factores globales por clase; no explicación local ni causal",
                        "critical_risk_score": "solo ordenación; no decisión ni cantidad",
                        "estables": "monitorización por riesgo propio; pueden prestar apoyo logístico",
                        "transferencias": "escenarios horarios independientes; no rutas ni bicicletas únicas",
                        "viajes_2023": metadata["viajes"]["scope_guards"]},
            "transformaciones": ["CSV UTF-8 con BOM a Parquet comprimido Snappy",
                                 "fechas locales sin inventar zona horaria", "station_number como texto",
                                 "sin eliminar, imputar o redondear filas o columnas"],
            "tablas": {},
        }
        for name, table in tables.items():
            path = staging / f"{name}.parquet"
            table.to_parquet(path, engine="pyarrow", compression="snappy", index=False)
            restored = pd.read_parquet(path)
            pd.testing.assert_frame_equal(table, restored, check_exact=True)
            manifest["tablas"][name] = {
                "archivo": path.name, "fuente": str(TABLES[name][0]), "filas": len(table),
                "columnas": {col: str(dtype) for col, dtype in table.dtypes.items()},
                "ausentes": {col: int(n) for col, n in table.isna().sum().items() if n},
                "bytes": path.stat().st_size, "sha256": sha256(path),
                "igualdad_tras_lectura_verificada": True,
            }
        check_sources_unchanged(ROOT, fingerprints)
        (staging / "manifiesto_app.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        output.mkdir(parents=True, exist_ok=True)
        # Todas las tablas se validan antes de publicar; el manifiesto se copia al final.
        for name in names:
            with (staging / name).open("rb") as source, (output / name).open("xb") as target:
                shutil.copyfileobj(source, target)
        print(f"Preparación completada: {len(tables)} archivos Parquet y manifiesto_app.json")
        print(f"Carpeta: {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--solo-validar", action="store_true", help="Comprobar fuentes sin escribir salidas")
    parser.add_argument("--salida", type=Path, default=ROOT / "app_data", help="Carpeta de Parquet; por defecto app_data")
    args = parser.parse_args()
    print("Leyendo resultados congelados de los notebooks 08–11...", flush=True)
    tables, metadata, fingerprints = load_inputs(ROOT)
    print("Validando predicciones, logística, interpretación y cobertura...", flush=True)
    counts = validate_all(tables, metadata)
    check_sources_unchanged(ROOT, fingerprints)
    for name, value in counts.items():
        print(f"  {name}: {value:,}".replace(",", "."))
    if args.solo_validar:
        print("Validación completada. No se ha escrito ningún dato.")
    else:
        export_tables(tables, metadata, fingerprints, counts, args.salida.resolve())


if __name__ == "__main__":
    try:
        main()
    except (ValueError, AssertionError, OSError, KeyError, TypeError) as error:
        print(f"\nPreparación detenida: {error}", file=sys.stderr)
        print("No se han modificado las fuentes ni se han ejecutado notebooks.", file=sys.stderr)
        sys.exit(1)
