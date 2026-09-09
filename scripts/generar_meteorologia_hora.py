#!/usr/bin/env python3
"""Genera una serie meteorológica ciudad-hora para el TFM de BiciMAD.

Lee los CSV horarios municipales anchos (H01..H24), mantiene únicamente
medidas validadas como V y agrega las estaciones mediante la mediana. Para
precipitación conserva además la media y el máximo, ya que una mediana puede
ser cero aunque llueva en parte de la ciudad.

Los datos fuente no se modifican. H01 es la 01:00 del mismo día; H24 se
representa como las 00:00 del día siguiente, según la documentación municipal.
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Bases de datos" / "Meteorología horaria desde 2019"
DEFAULT_OUTPUT = ROOT / "Datos analiticos" / "meteorologia_hora.csv"

PARAMETERS = {
    "80": ("uv_radiation_median_mw_m2", "n_uv_radiation"),
    "81": ("wind_speed_median_m_s", "n_wind_speed"),
    "82": ("wind_direction", "n_wind_direction"),
    "83": ("temperature_median_c", "n_temperature"),
    "86": ("relative_humidity_median_pct", "n_relative_humidity"),
    "87": ("barometric_pressure_median_mb", "n_barometric_pressure"),
    "88": ("solar_radiation_median_w_m2", "n_solar_radiation"),
    "89": ("precipitation", "n_precipitation"),
}

FIELDS = [
    "fecha_hora_local",
    "uv_radiation_median_mw_m2", "n_uv_radiation",
    "wind_speed_median_m_s", "n_wind_speed",
    "wind_direction_mean_deg", "wind_direction_sin_mean", "wind_direction_cos_mean", "n_wind_direction",
    "temperature_median_c", "n_temperature",
    "relative_humidity_median_pct", "n_relative_humidity",
    "barometric_pressure_median_mb", "n_barometric_pressure",
    "solar_radiation_median_w_m2", "n_solar_radiation",
    "precipitation_mean_l_m2", "precipitation_max_l_m2", "n_precipitation",
]


def as_float(raw: str) -> float | None:
    try:
        return float(raw.strip().replace(",", "."))
    except (AttributeError, ValueError):
        return None


def measurement_timestamp(row: dict[str, str], hour: int) -> datetime:
    timestamp = datetime(int(row["ANO"]), int(row["MES"]), int(row["DIA"]))
    if hour == 24:
        return timestamp + timedelta(days=1)
    return timestamp.replace(hour=hour)


def output_value(number: float) -> str:
    """Stable, compact decimal representation suitable for CSV."""
    return f"{number:.6f}".rstrip("0").rstrip(".")


def aggregate(source: Path, start_year: int, end_year: int) -> tuple[dict[datetime, dict[str, list[float]]], int, int]:
    values: dict[datetime, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    accepted = 0
    rejected = 0
    for path in sorted(source.rglob("*.csv")):
        with path.open("r", encoding="utf-8-sig", newline="") as input_file:
            reader = csv.DictReader(input_file, delimiter=";")
            for row in reader:
                year = int(row["ANO"])
                code = row["MAGNITUD"].strip()
                if not start_year <= year <= end_year or code not in PARAMETERS:
                    continue
                for hour in range(1, 25):
                    flag = (row.get(f"V{hour:02d}") or "").strip()
                    value = as_float(row.get(f"H{hour:02d}") or "")
                    if flag != "V" or value is None:
                        rejected += 1
                        continue
                    values[measurement_timestamp(row, hour)][code].append(value)
                    accepted += 1
    return values, accepted, rejected


def circular_mean(degrees: list[float]) -> tuple[float, float, float]:
    sin_mean = statistics.fmean(math.sin(math.radians(value)) for value in degrees)
    cos_mean = statistics.fmean(math.cos(math.radians(value)) for value in degrees)
    angle = math.degrees(math.atan2(sin_mean, cos_mean)) % 360
    return angle, sin_mean, cos_mean


def row_for(timestamp: datetime, measures: dict[str, list[float]]) -> dict[str, str | int]:
    result: dict[str, str | int] = {"fecha_hora_local": timestamp.isoformat(timespec="seconds")}
    for code, (column, count_column) in PARAMETERS.items():
        numbers = measures.get(code, [])
        result[count_column] = len(numbers)
        if not numbers:
            continue
        if code == "82":
            direction, sin_mean, cos_mean = circular_mean(numbers)
            result["wind_direction_mean_deg"] = output_value(direction)
            result["wind_direction_sin_mean"] = output_value(sin_mean)
            result["wind_direction_cos_mean"] = output_value(cos_mean)
        elif code == "89":
            result["precipitation_mean_l_m2"] = output_value(statistics.fmean(numbers))
            result["precipitation_max_l_m2"] = output_value(max(numbers))
        else:
            result[column] = output_value(statistics.median(numbers))
    return result


def generate(output: Path, start_year: int, end_year: int) -> None:
    values, accepted, rejected = aggregate(SOURCE, start_year, end_year)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".part")
    if output.exists() or temporary.exists():
        raise FileExistsError(f"Ya existe un resultado: {output}")
    with temporary.open("x", encoding="utf-8-sig", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=FIELDS)
        writer.writeheader()
        for timestamp in sorted(values):
            writer.writerow(row_for(timestamp, values[timestamp]))
    temporary.replace(output)
    print(f"CSV creado: {output.relative_to(ROOT)}")
    print(f"Horas ciudad: {len(values):,}")
    print(f"Medidas válidas: {accepted:,}; descartadas por validación/ausencia: {rejected:,}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, default=2019)
    parser.add_argument("--end-year", type=int, default=2022)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    if arguments.start_year > arguments.end_year:
        parser.error("--start-year debe ser menor o igual que --end-year")
    generate(arguments.output, arguments.start_year, arguments.end_year)
