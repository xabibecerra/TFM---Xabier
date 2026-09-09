"""Cobertura, denominadores y separación predictiva de la página descriptiva."""

from contextlib import ExitStack
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from app import data
from app.viajes import CONTROLES, comprobar_alcance, dias_para_mostrar, filtrar_meses, mapa_actividad, seleccionar_od


ROOT = Path(__file__).resolve().parents[1]


class TripFunctionsTests(unittest.TestCase):
    def test_unobserved_days_are_gaps_not_zero_demand(self):
        frame = pd.DataFrame({"date": pd.to_datetime(["2023-02-17", "2023-02-18", "2023-02-19"]),
            "trips": [100, 30, 0], "complete_day": [True, False, False], "observed_day": [True, True, False]})
        before = frame.copy(deep=True)
        view = dias_para_mostrar(frame)
        self.assertEqual(view["Viajes observados"].iloc[:2].tolist(), [100, 30])
        self.assertTrue(pd.isna(view["Viajes observados"].iloc[2]))
        self.assertEqual(view.Cobertura.iloc[1], "Día parcial")
        pd.testing.assert_frame_equal(frame, before)

    def test_scope_parses_false_strings_and_fails_closed(self):
        audit = pd.DataFrame({"control": CONTROLES + ["net_flow_interpretation"],
            "value": ["False"] * len(CONTROLES) + ["balance_de_viajes_no_disponibilidad"]})
        comprobar_alcance(audit)
        with self.assertRaises(ValueError): comprobar_alcance(audit.iloc[1:])
        audit.loc[0, "value"] = "True"
        with self.assertRaises(ValueError): comprobar_alcance(audit)

    def test_od_filters_keep_original_shares_ranks_and_same_station(self):
        frame = pd.DataFrame({"origin_station_id": [1, 1, 2], "destination_station_id": [1, 2, 1],
            "trips": [10, 6, 4], "same_station": [True, False, False], "share_of_station_trips": [.5, .3, .2], "rank_all_pairs": [1, 2, 3]})
        before = frame.copy()
        view = seleccionar_od(frame, 1, "Origen", "Estaciones distintas")
        self.assertEqual(view.trips.tolist(), [6])
        self.assertEqual(view.share_of_station_trips.tolist(), [.3])
        self.assertEqual(view.rank_all_pairs.tolist(), [2])
        self.assertEqual(seleccionar_od(frame, 1, tipo="Misma estación").trips.sum(), 10)
        self.assertEqual(len(seleccionar_od(frame, 1, tipo="Todos")), 3)
        self.assertTrue(seleccionar_od(frame, 3).empty)
        pd.testing.assert_frame_equal(frame, before)

    def test_month_filter_does_not_mutate_or_reweight(self):
        frame = pd.DataFrame({"month": ["2023-01", "2023-02"], "complete_days": [31, 17], "mean": [100., 90.]})
        view = filtrar_meses(frame, ["2023-02"])
        self.assertEqual(view.complete_days.tolist(), [17])
        view.loc[:, "mean"] = 1
        self.assertEqual(frame["mean"].tolist(), [100., 90.])

    def test_map_omits_missing_coordinates_without_changing_source(self):
        frame = pd.DataFrame({"station_id": [1, 2], "station_name": ["Una", "Dos"], "latitude": [40., None],
            "longitude": [-3., None], "departures": [3, 2], "arrivals": [2, 3], "total_activity": [5, 5], "net_arrivals": [-1, 1]})
        figure = mapa_actividad(frame, 5, False)
        self.assertEqual(len(figure.data[0].lat), 1)
        self.assertEqual(figure.layout.map.style, "white-bg")
        self.assertEqual(figure.layout.coloraxis.cmin, -5)
        self.assertEqual(len(frame), 2)
        with self.assertRaises(ValueError): mapa_actividad(frame.iloc[1:], 5)


class TripPageTests(unittest.TestCase):
    """Integra los agregados reales en copias aisladas; impide cargar datos predictivos."""

    @classmethod
    def setUpClass(cls):
        cls.originals = {name: pd.read_parquet(ROOT / "app_data" / f"{name}.parquet") for name in data.TABLAS_2023}

    def setUp(self):
        self.tables = {name: frame.copy(deep=True) for name, frame in self.originals.items()}
        self.calls = []
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        def loader(name="resumen_mensual_2023"):
            self.calls.append(name)
            return self.tables[name].copy(deep=True)
        self.stack.enter_context(patch.object(data, "cargar_viajes_2023", side_effect=loader))
        for name in ["cargar_predicciones", "cargar_candidatos", "cargar_transferencias", "cargar_no_resueltos", "cargar_tabla"]:
            self.stack.enter_context(patch.object(data, name, side_effect=AssertionError("No cargar datos predictivos en Viajes 2023")))

    def start(self):
        app = AppTest.from_file(str(ROOT / "app/streamlit_app.py"), default_timeout=20).run()
        app.switch_page("pages/viajes_2023.py").run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        return app

    def text(self, app):
        return "\n".join(x.value for kind in ["caption", "info", "warning", "markdown"] for x in app.get(kind))

    def test_initial_counts_and_descriptive_isolation(self):
        app = self.start()
        self.assertEqual([m.value for m in app.metric], ["464.417", "48", "49"])
        self.assertEqual(set(self.calls), set(data.TABLAS_2023))
        self.assertEqual(len(app.subheader), 5)
        self.assertIn("no contiene predicciones", self.text(app))
        self.assertIn("07:22:48", self.text(app))

    def test_february_changes_monthly_views_but_not_station_od_scope(self):
        app = self.start()
        initial_od = next(d.value for d in app.dataframe if "ID origen" in d.value.columns)
        app.selectbox(key="v23_mes").select("2023-02").run()
        self.assertFalse(app.exception)
        self.assertEqual([m.value for m in app.metric], ["168.494", "17", "18"])
        current_od = next(d.value for d in app.dataframe if "ID origen" in d.value.columns)
        pd.testing.assert_frame_equal(initial_od, current_od)
        duration = next(d.value for d in app.dataframe if "Viajes incluidos en duración" in d.value.columns)
        self.assertEqual(duration.Mes.tolist(), ["2023-02"])
        self.assertIn("El selector de mes no afecta", self.text(app))

    def test_no_coverage_dates_are_missing_in_daily_display(self):
        app = self.start()
        days = next(d.value for d in app.dataframe if "Cobertura" in d.value.columns)
        missing = days.loc[days.Fecha.ge(pd.Timestamp("2023-02-19"))]
        self.assertEqual(len(missing), 10)
        self.assertTrue(missing["Viajes observados"].isna().all())

    def test_same_station_pairs_and_top_limit_keep_global_denominator(self):
        app = self.start().selectbox(key="v23_tipo_od").select("Misma estación").run()
        table = next(d.value for d in app.dataframe if "ID origen" in d.value.columns)
        self.assertTrue(table["ID origen"].eq(table["ID destino"]).all())
        self.assertAlmostEqual(table["Cuota del total de viajes con estaciones (%)"].iloc[0], 2137 / 462766 * 100, places=6)
        app.selectbox(key="v23_limite").select(10).run()
        self.assertEqual(len(next(d.value for d in app.dataframe if "ID origen" in d.value.columns)), 10)

    def test_station_selection_restricts_origin_without_changing_monthly_metrics(self):
        app = self.start().selectbox(key="v23_estacion").select(43).run()
        app.selectbox(key="v23_sentido").select("Origen").run()
        self.assertFalse(app.exception)
        table = next(d.value for d in app.dataframe if "ID origen" in d.value.columns)
        self.assertTrue(table["ID origen"].eq(43).all())
        self.assertEqual(app.metric[0].value, "464.417")

    def test_missing_station_coordinates_leave_table_available(self):
        table = self.tables["actividad_estaciones_2023"]
        table.loc[table.station_id.eq(43), ["latitude", "longitude"]] = float("nan")
        app = self.start().selectbox(key="v23_estacion").select(43).run()
        self.assertFalse(app.exception)
        self.assertIn("No hay coordenadas disponibles", self.text(app))
        self.assertTrue(any("Actividad (extremos)" in d.value.columns for d in app.dataframe))

    def test_offline_map(self):
        app = self.start().checkbox(key="v23_callejero").uncheck().run()
        specs = [json.loads(x.proto.spec) for x in app.get("plotly_chart")]
        self.assertEqual(next(x for x in specs if "map" in x["layout"])["layout"]["map"]["style"], "white-bg")

    def test_empty_od_filter_is_explained(self):
        self.tables["pares_od_2023"] = self.tables["pares_od_2023"].iloc[:0]
        app = self.start()
        self.assertIn("No hay pares origen–destino", self.text(app))

    def test_scope_violation_stops_before_charts(self):
        audit = self.tables["auditoria_alcance_2023"]
        audit.loc[audit.control.eq("model_predictions_used"), "value"] = "True"
        app = AppTest.from_file(str(ROOT / "app/streamlit_app.py"), default_timeout=20).run()
        app.switch_page("pages/viajes_2023.py").run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.error), 1)
        self.assertEqual(len(app.get("plotly_chart")), 0)

    def test_load_failure_is_explained(self):
        with patch.object(data, "cargar_viajes_2023", side_effect=data.DatosAppError("Archivo ausente")):
            app = AppTest.from_file(str(ROOT / "app/streamlit_app.py"), default_timeout=20).run()
            app.switch_page("pages/viajes_2023.py").run()
        self.assertFalse(app.exception)
        self.assertIn("Archivo ausente", app.error[0].value)


if __name__ == "__main__":
    unittest.main()
