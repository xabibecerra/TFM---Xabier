"""Comprobaciones de empaquetado, documentación y alcance de la entrega."""

from pathlib import Path
import ast
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DeliveryTests(unittest.TestCase):
    def test_required_files_are_present(self):
        for relative in [
            "README_APP.md",
            "requirements.txt",
            ".streamlit/config.toml",
            "app/streamlit_app.py",
            "app_data/manifiesto_app.json",
        ]:
            with self.subTest(file=relative):
                self.assertTrue((ROOT / relative).is_file())

    def test_theme_configuration_is_valid_and_private(self):
        config = tomllib.loads((ROOT / ".streamlit/config.toml").read_text(encoding="utf-8"))
        self.assertEqual(config["theme"]["primaryColor"], "#2878B5")
        self.assertEqual(config["theme"]["backgroundColor"], "#FFFFFF")
        self.assertFalse(config["browser"]["gatherUsageStats"])

    def test_dependencies_are_exactly_pinned(self):
        lines = [
            line.strip()
            for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        self.assertGreaterEqual(len(lines), 5)
        for line in lines:
            with self.subTest(requirement=line):
                self.assertRegex(line, r"^[A-Za-z0-9_.-]+==[^=\s]+$")

    def test_app_contains_no_training_or_model_deserialization(self):
        imported_modules = set()
        called_methods = set()
        for path in (ROOT / "app").rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported_modules.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported_modules.add(node.module.split(".")[0])
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    called_methods.add(node.func.attr)
        self.assertTrue({"xgboost", "joblib", "pickle"}.isdisjoint(imported_modules))
        self.assertNotIn("fit", called_methods)

    def test_readme_documents_all_pages_and_scientific_scope(self):
        readme = (ROOT / "README_APP.md").read_text(encoding="utf-8")
        for text in [
            "Riesgo 2022",
            "Recomendaciones",
            "Interpretabilidad",
            "Viajes 2023",
            "No existen estados de estaciones",
            "no se utilizan para recalibrar",
            "no demuestra causas",
            "python -m app.data",
            "python -m streamlit run app/streamlit_app.py",
        ]:
            with self.subTest(text=text):
                self.assertIn(text, readme)

    def test_no_development_placeholders_remain(self):
        source = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "app").rglob("*.py"))
        for placeholder in ["TODO", "FIXME", "Página preparada", "incorporarán más adelante"]:
            with self.subTest(placeholder=placeholder):
                self.assertNotIn(placeholder, source)

    def test_version_control_keeps_delivery_data(self):
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn(".venv/", ignore)
        self.assertIn("__pycache__/", ignore)
        self.assertNotIn("app_data/", ignore)

    def test_readme_identifies_historical_non_realtime_prototype(self):
        readme = (ROOT / "README_APP.md").read_text(encoding="utf-8").lower()
        self.assertIn("prototipo histórico de solo lectura", readme)
        self.assertIn("no genera predicciones en tiempo real", readme)
        self.assertIn("no vuelve a calcular recomendaciones", readme)


if __name__ == "__main__":
    unittest.main()
