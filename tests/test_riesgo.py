"""Pruebas de filtros, mapa y ficha con datos sintéticos aislados del experimento."""

from contextlib import ExitStack
from datetime import date
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from app import data
from app.charts import COLORES, mapa_riesgo, probabilidades_estacion
from app.riesgo import CLASES, TIME, filtrar_escenario, formato, recuentos_clases, tabla_falsos_negativos


ENTRYPOINT = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"


def sample():
    rows = []
    for instant in ["2022-11-01 00:00", "2022-11-01 08:00", "2022-11-01 18:00", "2022-12-31 22:00"]:
        for code in [0, 1, 2]:
            probabilities = [0.01, 0.01, 0.01]
            probabilities[code] = 0.98
            rows.append({TIME: pd.Timestamp(instant), "station_id": code + 1, "station_number": str(code + 1),
                         "station_name": f"Estación {code + 1}", "address": "Dirección de prueba",
                         "latitude": 40.41 + code * 0.01, "longitude": -3.70 + code * 0.01,
                         "capacity": 30, "bikes_available": [15, 1, 29][code],
                         "docks_available": [15, 29, 1][code], "reservations_count": 0,
                         "occupancy_ratio": [0.5, 1 / 30, 29 / 30][code], "tipo_dia": "festivo",
                         "temperature_median_c": 15.0, "relative_humidity_median_pct": 70.0,
                         "wind_speed_median_m_s": 1.0, "precipitation_mean_l_m2": 0.0,
                         "departures_count_lag_1h": float("nan"), "arrivals_count_lag_1h": 2.0,
                         "net_flow_lag_1h": float("nan"), "prediction": code,
                         "model_action_signal": ["monitorizar", "candidata_reposicion_bicicletas", "candidata_retirada_bicicletas"][code],
                         **{f"probability_{c}": probabilities[c] for c in [0, 1, 2]},
                         "critical_risk_type": "riesgo_vaciado", "critical_risk_score": max(probabilities[1:])})
    return pd.DataFrame(rows)


class RiskFunctionsTests(unittest.TestCase):
    def test_filter_and_counts_do_not_mutate_predictions(self):
        p = sample()
        original = p.copy(deep=True)
        result = filtrar_escenario(p, "2022-11-01 00:00", [1])
        self.assertEqual(result.station_id.tolist(), [2])
        self.assertEqual(recuentos_clases(result), {0: 0, 1: 1, 2: 0})
        pd.testing.assert_frame_equal(p, original)

    def test_filter_does_not_create_missing_dates_or_hours(self):
        for timestamp in ["2023-01-01", "2022-12-31 23:00", "2022-11-01 01:00"]:
            with self.subTest(timestamp=timestamp), self.assertRaises(ValueError):
                filtrar_escenario(sample(), timestamp)

    def test_stable_relative_risk_is_not_used_as_action(self):
        result = filtrar_escenario(sample(), "2022-11-01", [0])
        self.assertEqual(result.model_action_signal.tolist(), ["monitorizar"])

    def test_map_has_one_point_per_station_and_fixed_colors(self):
        rows = filtrar_escenario(sample(), "2022-11-01")
        original = rows.copy(deep=True)
        figure = mapa_riesgo(rows)
        self.assertEqual(sum(len(trace.lat) for trace in figure.data), 3)
        for trace in figure.data:
            self.assertEqual(trace.marker.color, COLORES[trace.name])
        self.assertFalse(figure.layout.legend.itemclick)
        pd.testing.assert_frame_equal(rows, original)

    def test_no_street_map_mode_and_empty_map(self):
        rows = filtrar_escenario(sample(), "2022-11-01")
        self.assertEqual(mapa_riesgo(rows, callejero=False).layout.map.style, "white-bg")
        with self.assertRaises(ValueError):
            mapa_riesgo(rows.iloc[:0])

    def test_probability_chart_preserves_exact_values(self):
        row = sample().iloc[0]
        figure = probabilidades_estacion(row)
        self.assertEqual(list(figure.data[0].y), [row[f"probability_{c}"] for c in CLASES])
        self.assertEqual(list(figure.layout.yaxis.range), [0, 1])

    def test_missing_support_is_not_zero(self):
        table = tabla_falsos_negativos(None)
        self.assertTrue(table["Soporte real"].isna().all())
        self.assertTrue(table["Tasa FN (%)"].isna().all())
        self.assertEqual(formato(float("nan")), "No disponible")

    def test_zero_support_and_rates(self):
        row = {"support_empty": 20, "false_negatives_empty": 3, "enough_support_empty": True,
               "support_full": 0, "false_negatives_full": 0, "enough_support_full": False}
        table = tabla_falsos_negativos(row)
        self.assertEqual(table.loc[0, "Tasa FN (%)"], 15)
        self.assertTrue(pd.isna(table.loc[1, "Tasa FN (%)"]))
        self.assertEqual(table.loc[1, "Soporte suficiente (notebook 09)"], "No")


class RiskPageTests(unittest.TestCase):
    def setUp(self):
        self.p = sample()
        stats = {"support_empty": 20, "false_negatives_empty": 3, "support_full": 2,
                 "false_negatives_full": 1, "enough_support_empty": True, "enough_support_full": False}
        station_stats = pd.DataFrame([{"station_id": sid, **stats} for sid in [1, 2]])
        hour_stats = pd.DataFrame([{"hour": hour, **{k: v for k, v in stats.items() if not k.startswith("enough")}}
                                   for hour in [0, 8, 18, 22]])
        flags = pd.DataFrame({"station_id": [1, 2, 3], "sensitive_station_flag": [False, True, False]})
        self.stack = ExitStack()
        for function, value in [("cargar_predicciones", self.p), ("cargar_estaciones_sensibles", station_stats),
                                ("cargar_horas_sensibles", hour_stats), ("cargar_candidatos", flags)]:
            self.stack.enter_context(patch.object(data, function, return_value=value))

    def tearDown(self):
        self.stack.close()

    def start(self):
        app = AppTest.from_file(str(ENTRYPOINT), default_timeout=30).run()
        app.switch_page("pages/riesgo_2022.py").run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 0)
        return app

    def test_initial_map_counts_and_table(self):
        app = self.start()
        self.assertEqual([m.value for m in app.metric], ["3", "1", "1", "1"])
        self.assertEqual(len(app.dataframe[0].value), 3)
        self.assertEqual(len(app.get("plotly_chart")), 1)

    def test_class_filter_updates_counts_table_and_map(self):
        app = self.start()
        app.multiselect(key="riesgo_clases").set_value([1]).run()
        self.assertEqual([m.value for m in app.metric], ["1", "0", "1", "0"])
        self.assertEqual(app.dataframe[0].value.ID.tolist(), [2])
        spec = json.loads(app.get("plotly_chart")[0].proto.spec)
        self.assertEqual(sum(len(trace["lat"]) for trace in spec["data"]), 1)

    def test_empty_class_filter_has_no_stale_map(self):
        app = self.start()
        app.multiselect(key="riesgo_clases").set_value([]).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.get("plotly_chart")), 0)
        self.assertTrue(any("No hay estaciones" in item.value for item in app.info))

    def test_station_details_and_absent_values(self):
        app = self.start()
        app.selectbox(key="riesgo_estacion").select(1).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.get("plotly_chart")), 2)
        self.assertTrue(any("predicha como estable" in item.value for item in app.info))
        self.assertIn("No disponible", app.dataframe[1].value.Valor.tolist())

    def test_invalid_station_selection_resets_after_class_change(self):
        app = self.start()
        app.selectbox(key="riesgo_estacion").select(1).run()
        app.multiselect(key="riesgo_clases").set_value([1]).run()
        self.assertEqual(len(app.exception), 0)
        self.assertIsNone(app.selectbox(key="riesgo_estacion").value)

    def test_changing_date_only_offers_existing_hours(self):
        app = self.start()
        app.selectbox(key="riesgo_fecha").select(date(2022, 12, 31)).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.selectbox(key="riesgo_instante").options, ["22:00"])

    def test_sensitive_hour_and_station_warning_keep_denominators(self):
        app = self.start()
        app.selectbox(key="riesgo_instante").select(pd.Timestamp("2022-11-01 08:00")).run()
        self.assertTrue(any("especial cautela: 08:00" in item.value for item in app.warning))
        app.selectbox(key="riesgo_estacion").select(2).run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("señalada para monitorización" in item.value for item in app.warning))
        self.assertEqual(app.dataframe[2].value["Soporte real"].tolist(), [20, 2])
        self.assertEqual(app.dataframe[2].value["Falsos negativos"].tolist(), [3, 1])

    def test_station_without_error_statistics_does_not_invent_zeros(self):
        app = self.start()
        app.selectbox(key="riesgo_estacion").select(3).run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(app.dataframe[2].value["Soporte real"].isna().all())

    def test_offline_map_mode(self):
        app = self.start()
        app.checkbox(key="riesgo_callejero").uncheck().run()
        spec = json.loads(app.get("plotly_chart")[0].proto.spec)
        self.assertEqual(spec["layout"]["map"]["style"], "white-bg")

    def test_data_failure_shows_error(self):
        with patch.object(data, "cargar_predicciones", side_effect=data.DatosAppError("Falta una tabla")):
            app = AppTest.from_file(str(ENTRYPOINT), default_timeout=30).run()
            app.switch_page("pages/riesgo_2022.py").run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 1)


if __name__ == "__main__":
    unittest.main()
