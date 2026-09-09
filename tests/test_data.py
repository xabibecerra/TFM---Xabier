"""Pruebas del cargador en directorios temporales; nunca editan app_data/."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from app import data


class DataLoaderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="tfm-fase8-test-")
        self.folder = Path(self.temporary.name)
        self.patch = patch.object(data, "APP_DATA", self.folder)
        self.patch.start()
        data.limpiar_cache_datos()
        self.name = "predicciones_contexto_2022"
        self.file = self.folder / f"{self.name}.parquet"
        self.frame = pd.DataFrame({
            "fecha_hora_local": pd.to_datetime(["2022-11-01 02:00", "2022-11-01 00:00", "2022-11-01 00:00"]),
            "station_id": [1, 1, 2], "prediction": [0, 1, 0],
            "model_action_signal": ["monitorizar", "candidata_reposicion_bicicletas", "monitorizar"],
            "optional_value": [0.2, float("nan"), 0.1],
        })
        self.write_snapshot()

    def tearDown(self):
        data.limpiar_cache_datos()
        self.patch.stop()
        self.temporary.cleanup()

    def write_snapshot(self):
        self.frame.to_parquet(self.file, index=False)
        self.manifest = {"version": 1, "tablas": {self.name: {
            "archivo": self.file.name, "filas": len(self.frame),
            "columnas": {name: str(dtype) for name, dtype in self.frame.dtypes.items()},
            "sha256": hashlib.sha256(self.file.read_bytes()).hexdigest(),
        }}}
        self.write_manifest()

    def write_manifest(self):
        (self.folder / "manifiesto_app.json").write_text(json.dumps(self.manifest), encoding="utf-8")

    def test_exact_loading_and_missing_values_preserved(self):
        pd.testing.assert_frame_equal(data.cargar_predicciones(), self.frame, check_exact=True)

    def test_column_projection_preserves_order(self):
        columns = ["prediction", "station_id"]
        pd.testing.assert_frame_equal(data.cargar_predicciones(columns), self.frame[columns])

    def test_cache_avoids_repeated_parquet_reads(self):
        with patch.object(data.pd, "read_parquet", wraps=pd.read_parquet) as reader:
            data.cargar_predicciones()
            data.cargar_predicciones()
            self.assertEqual(reader.call_count, 1)

    def test_returned_copies_are_independent(self):
        first = data.cargar_predicciones()
        first.loc[0, "prediction"] = 2
        self.assertEqual(data.cargar_predicciones().loc[0, "prediction"], 0)

    def test_changed_parquet_invalidates_cache_and_is_rejected(self):
        data.cargar_predicciones()
        self.frame.loc[0, "prediction"] = 2
        self.frame.to_parquet(self.file, index=False)
        with self.assertRaisesRegex(data.DatosAppError, "huella"):
            data.cargar_predicciones()

    def test_updated_snapshot_is_read_instead_of_stale_cache(self):
        data.cargar_predicciones()
        self.frame.loc[0, "prediction"] = 2
        self.write_snapshot()
        self.assertEqual(data.cargar_predicciones().loc[0, "prediction"], 2)

    def test_missing_file_does_not_fall_back_to_csv(self):
        self.file.unlink()
        with self.assertRaisesRegex(data.DatosAppError, "fase 7"):
            data.cargar_predicciones()

    def test_missing_manifest_is_reported(self):
        (self.folder / "manifiesto_app.json").unlink()
        with self.assertRaisesRegex(data.DatosAppError, "manifiesto_app.json"):
            data.cargar_predicciones()

    def test_invalid_json_is_reported(self):
        (self.folder / "manifiesto_app.json").write_text("{", encoding="utf-8")
        with self.assertRaisesRegex(data.DatosAppError, "No se puede leer"):
            data.cargar_manifiesto()

    def test_unknown_table_and_path_are_rejected(self):
        with self.assertRaisesRegex(data.DatosAppError, "Tabla desconocida"):
            data.cargar_tabla("../predicciones_contexto_2022")

    def test_manifest_cannot_redirect_to_external_file(self):
        self.manifest["tablas"][self.name]["archivo"] = "../otra_tabla.parquet"
        self.write_manifest()
        with self.assertRaisesRegex(data.DatosAppError, "Metadatos"):
            data.cargar_predicciones()

    def test_manifest_row_count_is_checked(self):
        self.manifest["tablas"][self.name]["filas"] = 42
        self.write_manifest()
        with self.assertRaisesRegex(data.DatosAppError, "filas o columnas"):
            data.cargar_predicciones()

    def test_manifest_dtypes_are_checked(self):
        self.manifest["tablas"][self.name]["columnas"]["prediction"] = "float64"
        self.write_manifest()
        with self.assertRaisesRegex(data.DatosAppError, "tipo de dato"):
            data.cargar_predicciones()

    def test_bad_column_selection_is_rejected(self):
        for columns in ["prediction", [], ["not_a_column"], ["prediction", "prediction"]]:
            with self.subTest(columns=columns), self.assertRaises(data.DatosAppError):
                data.cargar_predicciones(columns)

    def test_2023_loader_rejects_predictive_tables(self):
        with self.assertRaisesRegex(data.DatosAppError, "descriptivo"):
            data.cargar_viajes_2023(self.name)

    def test_available_times_are_observed_unique_and_sorted(self):
        self.assertEqual(data.obtener_instantes_disponibles(),
                         [pd.Timestamp("2022-11-01 00:00"), pd.Timestamp("2022-11-01 02:00")])

    def test_full_check_reports_incomplete_manifest(self):
        with self.assertRaisesRegex(data.DatosAppError, "27 tablas"):
            data.comprobar_datos()


if __name__ == "__main__":
    unittest.main()
