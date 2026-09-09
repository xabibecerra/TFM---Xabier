"""Pruebas de interpretación sin SHAP, entrenamiento ni recalibración en ejecución."""

from contextlib import ExitStack
from pathlib import Path
import unittest
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from app import data
from app.interpretacion import comparar_importancias, errores_clase, grafico_errores_hora, union_top


ROOT = Path(__file__).resolve().parents[1]


def comparison():
    return pd.DataFrame({"original_feature": ["A", "B", "C"], "total_gain_share": [.6, .3, .1],
        "gain_rank": [1, 2, 3], "mean_abs_shap_macro": [.2, .7, .1], "shap_macro_rank": [2, 1, 3],
        "mean_abs_shap_test_weighted": [.1, .2, .7], "shap_test_weighted_rank": [3, 2, 1]})


def error_fixture(group, values):
    return pd.DataFrame({group: values, "support_empty": [20] * len(values),
        "false_negatives_empty": [5] * len(values), "support_full": [10] * len(values),
        "false_negatives_full": [3] * len(values)})


class InterpretationFunctionsTests(unittest.TestCase):
    def test_comparison_preserves_input_and_normalizes_full_population(self):
        frame = comparison()
        before = frame.copy()
        result = comparar_importancias(frame)
        pd.testing.assert_frame_equal(before, frame)
        top = union_top(result, 1)
        self.assertEqual(set(top.original_feature), {"A", "B"})
        self.assertAlmostEqual(top["SHAP (%)"].sum(), 90)
        self.assertEqual(result["Diferencia de rango (ganancia − SHAP)"].tolist(), [-1, 1, 0])

    def test_weighted_view_uses_exported_weighted_ranks(self):
        result = comparar_importancias(comparison(), True)
        self.assertEqual(result["Rango SHAP"].tolist(), [3, 2, 1])
        self.assertEqual(set(union_top(result, 1).original_feature), {"A", "C"})

    def test_zero_importance_does_not_invent_percentages(self):
        frame = comparison()
        frame["mean_abs_shap_macro"] = 0
        self.assertTrue(comparar_importancias(frame)["SHAP (%)"].isna().all())
        with self.assertRaises(ValueError): union_top(comparar_importancias(frame), 0)

    def test_fn_rate_uses_class_support_not_all_rows(self):
        frame = error_fixture("hour", [8])
        frame["rows"] = 10000
        self.assertEqual(errores_clase(frame, 1, "hour")["Tasa FN (%)"].tolist(), [25.0])
        self.assertEqual(errores_clase(frame, 2, "hour")["Tasa FN (%)"].tolist(), [30.0])

    def test_zero_and_missing_support_stay_undefined(self):
        frame = error_fixture("hour", [0, 8])
        frame.loc[0, ["support_empty", "false_negatives_empty"]] = 0
        frame.loc[1, ["support_empty", "false_negatives_empty"]] = float("nan")
        self.assertTrue(errores_clase(frame, 1, "hour")["Tasa FN (%)"].isna().all())

    def test_invalid_counts_are_rejected(self):
        frame = error_fixture("hour", [8])
        frame["false_negatives_empty"] = 21
        with self.assertRaises(ValueError): errores_clase(frame, 1, "hour")
        with self.assertRaises(ValueError): errores_clase(frame, 0, "hour")

    def test_hour_chart_is_chronological_and_retains_denominators(self):
        values = errores_clase(error_fixture("hour", [19, 8, 18]), 1, "hour")
        fig = grafico_errores_hora(values)
        self.assertEqual(list(fig.data[0].x), [8, 18, 19])
        self.assertEqual(list(fig.data[0].customdata[0]), [20, 5])
        self.assertFalse(fig.data[0].connectgaps)
        self.assertEqual([s.x0 for s in fig.layout.shapes], [8, 18, 19])


class InterpretationPageTests(unittest.TestCase):
    def setUp(self):
        self.hours = error_fixture("hour", [0, 8, 18, 19])
        self.months = error_fixture("month", ["2022-11", "2022-12"])
        self.stations = error_fixture("station_id", [1, 2])
        self.stations["station_name"] = ["Una", "Dos"]
        self.stations["enough_support_empty"] = [True, False]
        self.stations["enough_support_full"] = [False, True]
        self.catalog = pd.DataFrame({"station_id": [1, 2, 3], "station_name": ["Una", "Dos", "Tres"], "station_number": ["1", "2", "3"]})
        class_rows = []
        for code in range(3):
            for rank, feature in enumerate(["A", "B", "C"], 1):
                class_rows.append({"class_value": code, "original_feature": feature,
                    "shap_rank_within_class": rank, "mean_abs_shap": (code + 1) / rank, "mean_signed_shap": -.1})
        self.factors = pd.DataFrame({"class_value": [1, 2], "original_feature": ["A", "B"],
            "factor_family": ["estado_actual_estacion", "dinamica_historica_reciente"],
            "direction_association": ["valores_altos_reducen_contribucion"] * 2,
            "rank_correlation_value_shap": [-.9, -.4], "shap_rank_within_class": [1, 1]})
        self.tables = {"comparacion_gain_vs_shap": comparison(), "shap_importancia_por_clase": pd.DataFrame(class_rows),
            "errores_por_mes_2022": self.months,
            "metricas_test_2022": pd.DataFrame({"model": ["xgboost_refined", "logistic_refined"],
                "f1_macro": [.8, .7], "balanced_accuracy": [.82, .72], "test_rows": [100, 100]}),
            "informe_por_clase_test_2022": pd.DataFrame({"model": ["xgboost_refined"] * 3,
                "class": ["estable", "riesgo_vaciado", "riesgo_saturacion"], "precision": [.9, .8, .7],
                "recall": [.8, .7, .6], "f1-score": [.85, .75, .65], "support": [70, 20, 10]})}
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(data, "cargar_tabla", side_effect=lambda name: self.tables[name].copy()))
        for method, attribute in [("cargar_horas_sensibles", "hours"), ("cargar_estaciones_sensibles", "stations"), ("cargar_factores_por_clase", "factors")]:
            self.stack.enter_context(patch.object(data, method, side_effect=lambda attr=attribute: getattr(self, attr).copy()))
        self.stack.enter_context(patch.object(data, "cargar_predicciones", side_effect=lambda columnas=None: self.catalog.copy()))

    def start(self):
        app = AppTest.from_file(str(ROOT / "app/streamlit_app.py"), default_timeout=20).run()
        app.switch_page("pages/interpretabilidad.py").run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        return app

    def text(self, app):
        return "\n".join(item.value for kind in ["caption", "info", "warning", "markdown"] for item in app.get(kind))

    def test_initial_metrics_layers_and_limits(self):
        app = self.start()
        self.assertEqual([m.value for m in app.metric], ["0.8000", "0.8200", "100"])
        self.assertEqual(len(app.subheader), 3)
        self.assertEqual(len(app.get("plotly_chart")), 3)
        for text in ["no causas", "no recalcula SHAP", "no al número de predicciones", "no son contribuciones equivalentes"]:
            self.assertIn(text, self.text(app))

    def test_shap_weighted_mode_and_stable_class(self):
        app = self.start()
        app.selectbox(key="int_modo").select("Ponderado por frecuencias de clase del test").run()
        self.assertFalse(app.exception)
        app.selectbox(key="int_clase_shap").select(0).run()
        self.assertIn("No hay factores operativos exportados", self.text(app))
        self.assertEqual(len(app.get("plotly_chart")), 3)

    def test_error_class_changes_rates_and_support_filter(self):
        app = self.start()
        def station_table():
            return next(d.value for d in app.dataframe if "ID" in d.value.columns)
        self.assertEqual(station_table().ID.tolist(), [1])
        app.selectbox(key="int_clase_error").select(2).run()
        self.assertEqual(station_table().ID.tolist(), [2])
        self.assertEqual(station_table()["Tasa FN (%)"].tolist(), [30.0])
        app.checkbox(key="int_soporte").uncheck().run()
        self.assertEqual(len(station_table()), 2)

    def test_station_order_retains_support_and_fn_columns(self):
        app = self.start().selectbox(key="int_orden").select("Tasa FN (%)").run()
        self.assertFalse(app.exception)
        table = next(d.value for d in app.dataframe if "ID" in d.value.columns)
        self.assertTrue({"Soporte real", "Falsos negativos", "Tasa FN (%)"}.issubset(table.columns))

    def test_absent_station_does_not_get_zero_errors(self):
        app = self.start().selectbox(key="int_estacion").select(3).run()
        self.assertFalse(app.exception)
        self.assertIn("No hay estadísticas de revisión exportadas", self.text(app))
        self.assertTrue(app.dataframe[-1].value["Soporte real"].isna().all())

    def test_station_detail_keeps_both_classes(self):
        app = self.start().selectbox(key="int_estacion").select(1).run()
        self.assertEqual(app.dataframe[-1].value["Riesgo real"].tolist(), ["Vaciado", "Saturación"])
        self.assertEqual(app.dataframe[-1].value["Soporte suficiente (notebook 09)"].tolist(), ["Sí", "No"])

    def test_loading_failure_has_friendly_error(self):
        with patch.object(data, "cargar_horas_sensibles", side_effect=data.DatosAppError("Archivo ausente")):
            app = AppTest.from_file(str(ROOT / "app/streamlit_app.py"), default_timeout=20).run()
            app.switch_page("pages/interpretabilidad.py").run()
        self.assertFalse(app.exception)
        self.assertIn("Archivo ausente", app.error[0].value)


if __name__ == "__main__":
    unittest.main()
