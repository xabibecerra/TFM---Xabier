"""Comprobaciones de la portada metodológica de la fase 10."""

from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from app import data


ENTRYPOINT = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"


class HomePageTests(unittest.TestCase):
    def start(self):
        app = AppTest.from_file(str(ENTRYPOINT), default_timeout=20).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 0)
        return app

    def text(self, app):
        return "\n".join(item.value for kind in ("markdown", "caption", "info", "warning")
                         for item in app.get(kind))

    def test_all_sections_are_present(self):
        app = self.start()
        headings = [item.value for item in app.subheader]
        self.assertEqual(headings, ["Objetivo y caso de uso", "Periodos del experimento",
                                   "Cómo interpretar el sistema", "Explorar la aplicación"])

    def test_counts_come_from_manifest(self):
        manifest = data.cargar_manifiesto()
        manifest["recuentos"]["predicciones"] = 123456
        with patch.object(data, "cargar_manifiesto", return_value=manifest):
            app = self.start()
        self.assertEqual(app.metric[0].value, "123.456")
        self.assertEqual(app.metric[1].value, "49.702")
        self.assertEqual(app.metric[2].value, "41.630")

    def test_temporal_split_matches_manifest(self):
        app = self.start()
        table = app.table[0].value
        periods = data.cargar_manifiesto()["periodos"]
        self.assertEqual(table.Periodo.iloc[:3].tolist(),
                         [periods["entrenamiento"], periods["validacion"], periods["test"]])
        self.assertIn("2023", table.Periodo.iloc[3])
        self.assertIn("Descriptivo", table.Etapa.iloc[3])

    def test_partial_coverage_and_guide_revision_are_explicit(self):
        text = self.text(self.start())
        self.assertIn("18/02/2023 07:22:48", text)
        self.assertIn("Febrero tiene cobertura parcial", text)
        self.assertIn("deja de ser el test predictivo", text)

    def test_operational_and_interpretation_limits_are_explicit(self):
        text = self.text(self.start())
        for expected in ["no recalibra", "no causas", "critical_risk_type", "critical_risk_score",
                         "soporte, falsos negativos y tasa", "08:00", "18:00", "19:00",
                         "no son bicicletas únicas", "No se ha demostrado una reducción real"]:
            with self.subTest(expected=expected):
                self.assertIn(expected, text)

    def test_all_pages_available_without_claiming_production_readiness(self):
        text = self.text(self.start())
        self.assertIn("Las cinco páginas ya están disponibles", text)
        self.assertIn("no un sistema operativo en producción", text)

    def test_incomplete_summary_has_friendly_error(self):
        manifest = data.cargar_manifiesto()
        manifest.pop("periodos")
        with patch.object(data, "cargar_manifiesto", return_value=manifest):
            app = AppTest.from_file(str(ENTRYPOINT), default_timeout=20).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 1)
        self.assertIn("resumen metodológico", app.error[0].value)


if __name__ == "__main__":
    unittest.main()
