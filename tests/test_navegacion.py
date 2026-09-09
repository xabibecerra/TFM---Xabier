"""Pruebas de la navegación real de Streamlit, sin abrir navegador ni servidor."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from app import data


ENTRYPOINT = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"


class NavigationTests(unittest.TestCase):
    def start(self):
        app = AppTest.from_file(str(ENTRYPOINT), default_timeout=20).run()
        self.assertEqual(len(app.exception), 0)
        return app

    def test_home_is_default(self):
        app = self.start()
        self.assertEqual(app.title[0].value, "BiciMAD — Riesgo y apoyo operativo")
        self.assertEqual(len(app.error), 0)
        self.assertIn("Prototipo histórico de solo lectura", app.info[0].value)

    def test_all_pages_and_return_to_home(self):
        app = self.start()
        for file, title in [
            ("riesgo_2022.py", "Riesgo 2022"),
            ("recomendaciones.py", "Recomendaciones"),
            ("interpretabilidad.py", "Interpretabilidad"),
            ("viajes_2023.py", "Viajes 2023"),
            ("inicio.py", "BiciMAD — Riesgo y apoyo operativo"),
        ]:
            with self.subTest(page=file):
                app.switch_page(f"pages/{file}").run()
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(len(app.error), 0)
                self.assertEqual(app.title[0].value, title)
                self.assertTrue(any("No es un servicio en tiempo real" in item.value for item in app.sidebar.caption))

    def test_2023_scope_is_explicit(self):
        app = self.start().switch_page("pages/viajes_2023.py").run()
        text = app.warning[0].value
        self.assertIn("no contiene predicciones", text)
        self.assertIn("cobertura parcial", text)
        self.assertIn("07:22:48", text)

    def test_stable_logistical_support_is_not_confused_with_risk(self):
        app = self.start().switch_page("pages/recomendaciones.py").run()
        self.assertIn("no origina una candidata por riesgo propio", app.warning[0].value)
        self.assertIn("apoyo logístico", app.warning[0].value)

    def test_missing_manifest_has_actionable_error(self):
        with tempfile.TemporaryDirectory(prefix="tfm-fase9-test-") as folder:
            with patch.object(data, "APP_DATA", Path(folder)):
                app = self.start()
                self.assertEqual(len(app.error), 1)
                self.assertIn("manifiesto_app.json", app.error[0].value)
                self.assertIn("python -m app.data", app.info[0].value)

    def test_home_does_not_load_parquet_tables(self):
        with patch.object(data.pd, "read_parquet", side_effect=AssertionError("Inicio solo carga el manifiesto")):
            app = self.start()
            self.assertEqual(len(app.exception), 0)


if __name__ == "__main__":
    unittest.main()
