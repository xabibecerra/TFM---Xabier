"""Auditoría y navegación operativa con escenarios sintéticos; no ejecuta notebooks."""

from contextlib import ExitStack
from datetime import date
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from app import data
from app.charts import mapa_transferencias
from app.operativa import ESTADOS, auditar_escenario, filtrar_candidatos, resumen_cobertura, seleccionar
from app.riesgo import TIME


ROOT = Path(__file__).resolve().parents[1]


def fixture():
    instant = pd.Timestamp("2022-11-01")
    predictions = []
    for station, code, bikes in [(1, 0, 29), (2, 1, 1), (3, 2, 24), (4, 1, 10), (5, 1, 2), (6, 0, 15)]:
        predictions.append({TIME: instant, "station_id": station, "station_number": str(station),
            "station_name": f"Estación {station}", "latitude": 40.4 + station / 1000,
            "longitude": -3.7, "prediction": code, "capacity": 30, "bikes_available": bikes,
            "docks_available": 30 - bikes, "reservations_count": 0, "occupancy_ratio": bikes / 30,
            "model_action_signal": {0: "monitorizar", 1: "candidata_reposicion_bicicletas", 2: "candidata_retirada_bicicletas"}[code],
            "critical_risk_type": "riesgo_vaciado", "critical_risk_score": 0.9 if code else 0.00001,
            **{f"probability_{i}": 0.9 if i == code else 0.05 for i in range(3)}})
    p = pd.DataFrame(predictions)
    c = p.loc[p.prediction.ne(0)].copy()
    c["requested_units"] = [8, 3, 0, 7]
    c["assigned_units"] = [5, 3, 0, 0]
    c["uncovered_units"] = c.requested_units - c.assigned_units
    c["recommendation_status"] = ["cobertura_parcial", "transferencia_asignada", "monitorizar_sin_brecha_operativa_actual", "sin_pareja_factible_en_radio"]
    c["priority_rank_within_hour_and_action"] = [1, 1, 2, 3]
    c["free_docks_conservative"] = c.docks_available
    c["target_min_bikes"], c["target_max_bikes"] = 9, 21
    c["operational_explanation"] = "Estado observado y cobertura exportada. Asociación predictiva, no causal."
    c["sensitive_hour_flag"], c["sensitive_station_flag"] = False, False
    c.loc[c.station_id.eq(2), "sensitive_station_flag"] = True
    c["critical_support"], c["critical_false_negatives"], c["critical_false_negative_rate"] = 20.0, 3.0, 0.15
    c["hour_critical_support"], c["hour_critical_false_negatives"], c["hour_critical_false_negative_rate"] = 100, 20, 0.2
    c.loc[c.station_id.eq(5), ["critical_support", "critical_false_negatives", "critical_false_negative_rate"]] = float("nan")
    transfers = []
    for donor, code, units in [(1, 0, 2), (3, 2, 3)]:
        transfers.append({TIME: instant, "donor_station_id": donor, "donor_station_name": f"Estación {donor}",
            "donor_prediction": code, "receiver_station_id": 2, "receiver_station_name": "Estación 2",
            "receiver_prediction": 1, "units": units, "distance_km": 1.0,
            "pair_type": "apoyo_estable_a_vaciado" if code == 0 else "riesgos_complementarios"})
    t = pd.DataFrame(transfers)
    u = c.loc[c.recommendation_status.ne("transferencia_asignada")].copy()
    policy = pd.DataFrame({"parameter": ["operational_min_ratio", "operational_max_ratio", "max_pair_distance_km",
                                        "max_units_per_transfer", "risk_score_threshold"],
                           "value": ["0.3", "0.7", "3.0", "10", "none"], "source": ["exportado"] * 5})
    f = pd.DataFrame({"class_value": [1, 2], "original_feature": ["occupancy_ratio"] * 2,
                      "shap_rank_within_class": [1, 1], "mean_abs_shap": [1.5, 2.0],
                      "factor_family": ["estado_actual_estacion"] * 2,
                      "direction_association": ["valores_altos_reducen_contribucion", "valores_altos_aumentan_contribucion"]})
    return p, c, t, u, policy, f


class OperationalFunctionsTests(unittest.TestCase):
    def test_audit_preserves_all_sources(self):
        tables = fixture()[:5]
        copies = [x.copy(deep=True) for x in tables]
        self.assertTrue(auditar_escenario(*tables).Resultado.eq("Correcto").all())
        for original, result in zip(copies, tables):
            pd.testing.assert_frame_equal(original, result)

    def test_stable_support_keeps_both_transfer_endpoints(self):
        p, c, t, *_ = fixture()
        self.assertTrue(seleccionar(c, "2022-11-01", 1).empty)
        subset = seleccionar(t, "2022-11-01", 1, transferencias=True)
        self.assertEqual(subset.receiver_station_id.tolist(), [2])
        self.assertEqual(subset.units.sum(), 2)
        fig = mapa_transferencias(subset, p, callejero=False)
        self.assertEqual(sum(len(trace.lat) for trace in fig.data[1:]), 2)
        self.assertEqual(fig.layout.map.style, "white-bg")

    def test_coverage_denominators_and_no_double_counting(self):
        _, c, t, u, *_ = fixture()
        result = resumen_cobertura(c)
        self.assertEqual(result["Unidades asignadas"].sum(), 8)
        self.assertEqual(t.units.sum(), 5)
        self.assertEqual(len(u), 3)
        self.assertEqual(c.uncovered_units.gt(0).sum(), 2)
        monitor = c.loc[c.requested_units.eq(0)]
        self.assertTrue(resumen_cobertura(monitor)["Cobertura de unidades (%)"].isna().all())

    def test_filters_preserve_scores_and_original_ranks(self):
        _, c, *_ = fixture()
        c.loc[c.station_id.eq(5), "critical_risk_score"] = 0.000001
        result = filtrar_candidatos(c, ["sin_pareja_factible_en_radio"])
        self.assertEqual(result.station_id.tolist(), [5])
        self.assertEqual(result.priority_rank_within_hour_and_action.tolist(), [3])
        self.assertEqual(result.critical_risk_score.tolist(), [0.000001])
        self.assertTrue(filtrar_candidatos(c, []).empty)

    def test_inconsistent_inputs_fail_closed(self):
        for mutation in ["distance", "units", "accumulated", "stable_action", "unresolved", "status", "different_hour", "threshold"]:
            p, c, t, u, policy, _ = fixture()
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                if mutation == "distance": t.loc[0, "distance_km"] = 4.0
                elif mutation == "units": t.loc[0, "units"] = 11
                elif mutation == "accumulated": t = pd.concat([t, t, t])
                elif mutation == "stable_action": p.loc[0, "model_action_signal"] = "candidata_reposicion_bicicletas"
                elif mutation == "unresolved": u = u.iloc[:0]
                elif mutation == "status": c.loc[c.station_id.eq(4), "recommendation_status"] = "cobertura_parcial"
                elif mutation == "different_hour": t[TIME] = pd.Timestamp("2023-01-01")
                elif mutation == "threshold": policy.loc[policy.parameter.eq("risk_score_threshold"), "value"] = "0.5"
                auditar_escenario(p, c, t, u, policy)

    def test_map_missing_endpoint_or_empty_transfers_is_rejected(self):
        p, _, t, *_ = fixture()
        with self.assertRaises(ValueError): mapa_transferencias(t, p.loc[p.station_id.ne(1)])
        with self.assertRaises(ValueError): mapa_transferencias(t.iloc[:0], p)


class OperationalPageTests(unittest.TestCase):
    def setUp(self):
        self.p, self.c, self.t, self.u, self.policy, self.f = fixture()
        # Una hora sensible, y otro día disponible sin candidatas ni transferencias.
        for name in ["p", "c", "t", "u"]:
            frame = getattr(self, name)
            later = frame.copy()
            later[TIME] = pd.Timestamp("2022-11-01 08:00")
            if "sensitive_hour_flag" in later: later["sensitive_hour_flag"] = True
            setattr(self, name, pd.concat([frame, later], ignore_index=True))
        last = self.p.loc[self.p.station_id.eq(6)].head(1).copy()
        last[TIME] = pd.Timestamp("2022-12-31 22:00")
        self.p = pd.concat([self.p, last], ignore_index=True)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for method, name in [("cargar_predicciones", "p"), ("cargar_candidatos", "c"),
                             ("cargar_transferencias", "t"), ("cargar_no_resueltos", "u"),
                             ("cargar_factores_por_clase", "f")]:
            self.stack.enter_context(patch.object(data, method, side_effect=lambda name=name: getattr(self, name).copy()))
        self.stack.enter_context(patch.object(data, "cargar_tabla", return_value=self.policy))

    def start(self):
        app = AppTest.from_file(str(ROOT / "app/streamlit_app.py"), default_timeout=20).run()
        app.switch_page("pages/recomendaciones.py").run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 0)
        return app

    def text(self, app):
        return "\n".join(item.value for kind in ["caption", "info", "warning", "markdown"] for item in app.get(kind))

    def test_initial_counts_and_layers(self):
        app = self.start()
        self.assertEqual([x.value for x in app.metric], ["4", "2", "5", "2"])
        self.assertEqual(len(app.subheader), 3)
        for phrase in ["no son rutas definitivas", "dos extremos", "solo para ordenar"]:
            self.assertIn(phrase, self.text(app))

    def test_stable_support_filter_does_not_create_candidate(self):
        app = self.start().selectbox(key="op_estacion").select(1).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual([x.value for x in app.metric], ["0", "1", "2", "0"])
        self.assertEqual(len(app.get("plotly_chart")), 1)
        self.assertEqual(app.selectbox(key="op_detalle").options, ["Selecciona una candidata"])

    def test_local_candidate_filters_do_not_hide_pairs(self):
        app = self.start().multiselect(key="op_estados").set_value([]).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual([x.value for x in app.metric], ["4", "2", "5", "2"])
        self.assertEqual(len(app.get("plotly_chart")), 1)
        self.assertEqual(len(app.selectbox(key="op_detalle").options), 1)

    def test_detail_uses_class_shap_and_retrospective_denominators(self):
        app = self.start().selectbox(key="op_detalle").select(2).run()
        self.assertEqual(len(app.exception), 0)
        text = self.text(app)
        self.assertIn("globales de la clase, no una explicación local", text)
        self.assertIn("no modifica la propuesta", text)
        self.assertEqual(app.dataframe[-1].value["Soporte crítico real"].tolist(), [20.0, 100.0])
        self.assertEqual(app.dataframe[-1].value["Falsos negativos críticos"].tolist(), [3.0, 20.0])
        self.assertEqual(app.dataframe[-1].value["Tasa FN (%)"].tolist(), [15.0, 20.0])

    def test_missing_error_statistics_stay_missing(self):
        app = self.start().selectbox(key="op_detalle").select(5).run()
        self.assertTrue(app.dataframe[-1].value.iloc[0][["Soporte crítico real", "Falsos negativos críticos", "Tasa FN (%)"]].isna().all())

    def test_sensitive_hour_flag_is_only_caution(self):
        app = self.start().selectbox(key="op_hora").select(pd.Timestamp("2022-11-01 08:00")).run()
        app.selectbox(key="op_detalle").select(4).run()
        self.assertIn("hora sensible", self.text(app))
        self.assertEqual([x.value for x in app.metric], ["4", "2", "5", "2"])

    def test_date_change_empty_scenario_and_reset_detail(self):
        app = self.start().selectbox(key="op_detalle").select(2).run()
        app.selectbox(key="op_fecha").select(date(2022, 12, 31)).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 0)
        self.assertEqual(app.selectbox(key="op_hora").options, ["22:00"])
        self.assertEqual([x.value for x in app.metric], ["0", "0", "0", "0"])
        self.assertEqual(len(app.get("plotly_chart")), 0)
        self.assertIsNone(app.selectbox(key="op_detalle").value)

    def test_offline_map_style(self):
        app = self.start().checkbox(key="op_callejero").uncheck().run()
        self.assertEqual(json.loads(app.get("plotly_chart")[0].proto.spec)["layout"]["map"]["style"], "white-bg")

    def test_inconsistent_transfers_stop_before_recommendations(self):
        self.t.loc[0, "units"] = 99
        app = AppTest.from_file(str(ROOT / "app/streamlit_app.py"), default_timeout=20).run()
        app.switch_page("pages/recomendaciones.py").run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 1)
        self.assertIn("Consulta detenida", app.error[0].value)
        self.assertEqual(len(app.metric), 0)

    def test_loading_error_is_explained(self):
        with patch.object(data, "cargar_candidatos", side_effect=data.DatosAppError("Archivo ausente")):
            app = AppTest.from_file(str(ROOT / "app/streamlit_app.py"), default_timeout=20).run()
            app.switch_page("pages/recomendaciones.py").run()
        self.assertEqual(len(app.exception), 0)
        self.assertIn("Archivo ausente", app.error[0].value)


if __name__ == "__main__":
    unittest.main()
