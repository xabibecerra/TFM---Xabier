"""Pruebas de integridad sin modificar las fuentes ni cargar el modelo."""

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from scripts import preparar_datos_app as prep


def predictions():
    return pd.DataFrame([
        {prep.TIME: pd.Timestamp("2022-11-01"), "station_id": 1, "prediction": 1,
         "predicted_risk_name": "riesgo_vaciado", "model_action_signal": prep.SIGNALS[1],
         "probability_0": 0.05, "probability_1": 0.94, "probability_2": 0.01,
         "critical_risk_score": 0.94, "critical_risk_type": "riesgo_vaciado",
         "capacity": 30, "bikes_available": 0, "docks_available": 30,
         "reservations_count": 0, "latitude": 40.4, "longitude": -3.7},
        {prep.TIME: pd.Timestamp("2022-11-01"), "station_id": 2, "prediction": 0,
         "predicted_risk_name": "estable", "model_action_signal": prep.SIGNALS[0],
         "probability_0": 0.99, "probability_1": 0.009, "probability_2": 0.001,
         "critical_risk_score": 0.009, "critical_risk_type": "riesgo_vaciado",
         "capacity": 30, "bikes_available": 25, "docks_available": 5,
         "reservations_count": 0, "latitude": 40.41, "longitude": -3.7},
    ])


def operations(units=3):
    p = predictions()
    c = p.iloc[[0]].copy()
    for name, value in {"requested_units": 9, "assigned_units": units,
                        "uncovered_units": 9 - units, "candidate_role": "receiver",
                        "recommendation_status": "cobertura_parcial",
                        "receiver_units_assigned": units, "donor_units_assigned": 0}.items():
        c[name] = value
    t = pd.DataFrame([{prep.TIME: pd.Timestamp("2022-11-01"), "donor_station_id": 2,
                       "receiver_station_id": 1, "donor_prediction": 0, "receiver_prediction": 1,
                       "units": units, "distance_km": 1.0, "pair_type": "apoyo_estable_a_vaciado"}])
    policy = {"operational_min_ratio": 0.3, "operational_max_ratio": 0.7,
              "max_pair_distance_km": 3.0, "max_units_per_transfer": 10}
    return p, c, t, c.copy(), policy


class PreparationTests(unittest.TestCase):
    def test_valid_predictions(self):
        prep.validate_predictions(predictions())

    def test_stable_relative_risk_does_not_generate_action(self):
        p = predictions()
        p.loc[1, "critical_risk_type"] = "riesgo_saturacion"
        prep.validate_predictions(p)
        self.assertEqual(p.loc[1, "model_action_signal"], "monitorizar")

    def test_stable_cannot_be_critical_candidate(self):
        p = predictions()
        p.loc[1, "model_action_signal"] = prep.SIGNALS[1]
        with self.assertRaisesRegex(ValueError, "Señal incompatible"):
            prep.validate_predictions(p)

    def test_invalid_probability_is_rejected(self):
        p = predictions()
        p.loc[0, "probability_1"] = 1.1
        with self.assertRaisesRegex(ValueError, "Probabilidades inválidas"):
            prep.validate_predictions(p)

    def test_duplicate_station_hour_is_rejected(self):
        p = predictions()
        with self.assertRaisesRegex(ValueError, "duplicada"):
            prep.validate_predictions(pd.concat([p, p.iloc[[0]]]))

    def test_2023_cannot_enter_predictive_page(self):
        p = predictions()
        p.loc[0, prep.TIME] = pd.Timestamp("2023-01-01")
        with self.assertRaisesRegex(ValueError, "fuera del test"):
            prep.validate_predictions(p)

    def test_stable_logistical_support_is_allowed(self):
        prep.validate_operations(*operations())

    def test_donor_supply_limit_is_checked(self):
        with self.assertRaisesRegex(ValueError, "exceden el margen"):
            prep.validate_operations(*operations(units=5))

    def test_distance_limit_is_checked(self):
        args = operations()
        args[2].loc[0, "distance_km"] = 3.1
        with self.assertRaisesRegex(ValueError, "Distancia"):
            prep.validate_operations(*args)

    def test_missing_sources_are_reported(self):
        with tempfile.TemporaryDirectory(prefix="tfm-test-fase7-") as folder:
            with self.assertRaisesRegex(ValueError, "Faltan fuentes"):
                prep.load_inputs(Path(folder))


if __name__ == "__main__":
    unittest.main()
