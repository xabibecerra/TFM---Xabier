#!/usr/bin/env python3
"""Crea CSV analiticos de BiciMAD sin modificar los ficheros fuente.

El resultado se particiona por mes para que sea manejable y se pueda leer con
pandas, Excel (por partes) o DuckDB. Tambien normaliza los CSV de viajes que
ya venian en ese formato; asi todos los meses comparten un mismo esquema.

Uso:
    python3 scripts/convertir_bicimad_json_a_csv.py
    python3 scripts/convertir_bicimad_json_a_csv.py --kind station
    python3 scripts/convertir_bicimad_json_a_csv.py --kind trips
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Bases de datos" / "Históricos de BiciMAD 2019-2023"
OUTPUT = ROOT / "Datos analiticos" / "BiciMAD"
MANIFEST = OUTPUT / "manifest_conversion.csv"

STATION_FIELDS = [
    "source_file", "snapshot_at", "snapshot_hour", "station_id",
    "station_number", "station_name", "address", "latitude", "longitude",
    "capacity", "bikes_available", "docks_available", "reservations_count",
    "no_available", "activation", "light",
]

TRIP_FIELDS = [
    "source_file", "source_format", "trip_id", "start_at", "end_at",
    "duration_seconds", "origin_station_id", "destination_station_id",
    "origin_dock_id", "destination_dock_id", "user_type", "age_range",
    "postal_code", "origin_latitude", "origin_longitude",
    "destination_latitude", "destination_longitude",
]

MANIFEST_FIELDS = [
    "source_file", "dataset", "period", "output_file", "rows", "status", "notes"
]


def value(data: dict[str, Any], *names: str) -> Any:
    """Return the first present value, retaining legitimate zeroes."""
    for name in names:
        if name in data and data[name] is not None:
            return data[name]
    return ""


def source_period(path: Path) -> str:
    match = re.search(r"(20\d{2})[_-]?(0[1-9]|1[0-2])", path.name)
    if match:
        return f"{match.group(1)}{match.group(2)}"
    match = re.search(r"trips_(\d{2})_(\d{2})", path.name)
    if match:
        return f"20{match.group(1)}{match.group(2)}"
    raise ValueError(f"No se ha podido deducir AAAAMM de {path.name}")


def normalise_datetime(raw: Any) -> str:
    """Keep the instant supplied by BiciMAD in an ISO-like representation.

    The source has both ISO strings and Mongo's {"$date": ...} shape. We do
    not force a timezone conversion here; that must be decided explicitly in
    the modelling notebook after checking the source documentation.
    """
    if isinstance(raw, dict):
        raw = raw.get("$date", "")
    return str(raw or "")


def hour_from_timestamp(timestamp: str) -> str:
    if not timestamp:
        return ""
    # Snapshot times are local naive timestamps. The output deliberately keeps
    # this calendar hour rather than silently converting it to another timezone.
    match = re.match(r"(\d{4}-\d{2}-\d{2})T(\d{2})", timestamp)
    return f"{match.group(1)}T{match.group(2)}:00:00" if match else ""


def end_timestamp(start: str, seconds: Any) -> str:
    try:
        duration = float(seconds)
        # Supports both Z and numeric ISO offsets. If parsing fails, preserve
        # the start time but leave the derived end time blank.
        parsed = datetime.fromisoformat(start.replace("Z", "+00:00"))
        return (parsed + timedelta(seconds=duration)).isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError):
        return ""


def json_lines(path: Path) -> Iterator[dict[str, Any]]:
    """Yield line-delimited JSON records; source JSON is NDJSON, not an array."""
    with path.open("rb") as source:
        for number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                decoded = line.decode("utf-8-sig")
            except UnicodeDecodeError:
                # Bicimad_Stations_201901.json uses Windows-1252, including
                # Spanish ordinal characters in station addresses.
                decoded = line.decode("cp1252")
            try:
                record = json.loads(decoded)
            except json.JSONDecodeError as exc:
                raise ValueError(f"JSON no válido en línea {number}: {exc.msg}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"Registro no objeto en línea {number}")
            yield record


def station_sources() -> list[Path]:
    return sorted(
        (
            path for path in SOURCE.rglob("*.json")
            if "movement" not in path.name.lower() and "usage" not in path.name.lower()
        ),
        key=lambda path: (source_period(path), str(path)),
    )


def json_trip_sources() -> list[Path]:
    # June 2021 and all subsequent months already have a supplied trip CSV.
    # Avoid generating two analytical outputs for the same month.
    result = []
    for path in SOURCE.rglob("*.json"):
        if "movement" not in path.name.lower() and "usage" not in path.name.lower():
            continue
        if source_period(path) >= "202106":
            continue
        result.append(path)
    return sorted(result, key=lambda path: (source_period(path), str(path)))


def csv_trip_sources() -> list[Path]:
    return sorted(SOURCE.rglob("trips_*.csv"))


def write_station_file(path: Path, destination: Path) -> int:
    rows = 0
    temporary = destination.with_suffix(destination.suffix + ".part")
    with temporary.open("x", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=STATION_FIELDS)
        writer.writeheader()
        for snapshot in json_lines(path):
            timestamp = normalise_datetime(snapshot.get("_id"))
            for station in snapshot.get("stations", []):
                if not isinstance(station, dict):
                    continue
                writer.writerow({
                    "source_file": str(path.relative_to(ROOT)),
                    "snapshot_at": timestamp,
                    "snapshot_hour": hour_from_timestamp(timestamp),
                    "station_id": value(station, "id"),
                    "station_number": value(station, "number"),
                    "station_name": value(station, "name"),
                    "address": value(station, "address"),
                    "latitude": value(station, "latitude"),
                    "longitude": value(station, "longitude"),
                    "capacity": value(station, "total_bases"),
                    "bikes_available": value(station, "dock_bikes"),
                    "docks_available": value(station, "free_bases"),
                    "reservations_count": value(station, "reservations_count"),
                    "no_available": value(station, "no_available"),
                    "activation": value(station, "activate"),
                    "light": value(station, "light"),
                })
                rows += 1
    temporary.replace(destination)
    return rows


def json_trip_row(record: dict[str, Any], path: Path) -> dict[str, Any]:
    trip_id = record.get("_id", "")
    if isinstance(trip_id, dict):
        trip_id = trip_id.get("$oid", "")
    start = normalise_datetime(record.get("unplug_hourTime"))
    duration = value(record, "travel_time")
    return {
        "source_file": str(path.relative_to(ROOT)),
        "source_format": "json",
        "trip_id": trip_id,
        "start_at": start,
        "end_at": end_timestamp(start, duration),
        "duration_seconds": duration,
        "origin_station_id": value(record, "idunplug_station"),
        "destination_station_id": value(record, "idplug_station"),
        "origin_dock_id": value(record, "idunplug_base"),
        "destination_dock_id": value(record, "idplug_base"),
        "user_type": value(record, "user_type"),
        "age_range": value(record, "ageRange"),
        "postal_code": value(record, "zip_code"),
        "origin_latitude": "", "origin_longitude": "",
        "destination_latitude": "", "destination_longitude": "",
    }


def point_coordinates(raw: Any) -> tuple[Any, Any]:
    """Read BiciMAD's Python-like GeoJSON string without evaluating it."""
    if not raw:
        return "", ""
    match = re.search(r"coordinates['\"]?\s*:\s*\[\s*([^,]+),\s*([^\]]+)\]", str(raw))
    return (match.group(2).strip(), match.group(1).strip()) if match else ("", "")


def csv_trip_row(record: dict[str, str], path: Path) -> dict[str, Any]:
    start = (record.get("unlock_date") or "").strip()
    end = (record.get("lock_date") or "").strip()
    try:
        duration = str(round(float((record.get("trip_minutes") or "").replace(",", ".") ) * 60, 3))
    except ValueError:
        duration = ""
    origin_lat, origin_lon = point_coordinates(record.get("geolocation_unlock"))
    destination_lat, destination_lon = point_coordinates(record.get("geolocation_lock"))
    return {
        "source_file": str(path.relative_to(ROOT)),
        "source_format": "csv_original",
        "trip_id": record.get("idTrip", ""),
        "start_at": start,
        "end_at": end,
        "duration_seconds": duration,
        "origin_station_id": record.get("station_unlock", ""),
        "destination_station_id": record.get("station_lock", ""),
        "origin_dock_id": record.get("dock_unlock", ""),
        "destination_dock_id": record.get("dock_lock", ""),
        "user_type": "", "age_range": "", "postal_code": "",
        "origin_latitude": origin_lat, "origin_longitude": origin_lon,
        "destination_latitude": destination_lat, "destination_longitude": destination_lon,
    }


def write_json_trip_file(path: Path, destination: Path) -> int:
    rows = 0
    temporary = destination.with_suffix(destination.suffix + ".part")
    with temporary.open("x", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=TRIP_FIELDS)
        writer.writeheader()
        for record in json_lines(path):
            writer.writerow(json_trip_row(record, path))
            rows += 1
    temporary.replace(destination)
    return rows


def write_csv_trip_file(path: Path, destination: Path) -> int:
    rows = 0
    temporary = destination.with_suffix(destination.suffix + ".part")
    with path.open("r", newline="", encoding="utf-8-sig") as source, temporary.open("x", newline="", encoding="utf-8-sig") as output:
        reader = csv.DictReader(source, delimiter=";")
        writer = csv.DictWriter(output, fieldnames=TRIP_FIELDS)
        writer.writeheader()
        for record in reader:
            if not any((cell or "").strip() for cell in record.values()):
                continue
            writer.writerow(csv_trip_row(record, path))
            rows += 1
    temporary.replace(destination)
    return rows


def append_manifest(entries: list[dict[str, Any]]) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    new_file = not MANIFEST.exists()
    with MANIFEST.open("a", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=MANIFEST_FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerows(entries)


def manifest_output_files() -> set[str]:
    if not MANIFEST.exists():
        return set()
    with MANIFEST.open("r", newline="", encoding="utf-8-sig") as source:
        return {row["output_file"] for row in csv.DictReader(source) if row.get("output_file")}


def csv_data_rows(path: Path) -> int:
    """Count physical records in our generated files (none contain multiline fields)."""
    with path.open("rb") as source:
        return max(sum(1 for _ in source) - 1, 0)


def convert(kind: str) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    registered_outputs = manifest_output_files()

    if kind in ("station", "all"):
        destination_dir = OUTPUT / "estado_estaciones"
        destination_dir.mkdir(exist_ok=True)
        for path in station_sources():
            period = source_period(path)
            destination = destination_dir / f"estado_estaciones_{period}.csv"
            if destination.exists():
                print(f"OMITIDO (ya existe): {destination.relative_to(ROOT)}")
                output_file = str(destination.relative_to(ROOT))
                if output_file not in registered_outputs:
                    entry = {"source_file": str(path.relative_to(ROOT)), "dataset": "estado_estaciones", "period": period, "output_file": output_file, "rows": csv_data_rows(destination), "status": "verificado_existente", "notes": "CSV creado antes del registro automático"}
                    append_manifest([entry])
                    registered_outputs.add(output_file)
                continue
            print(f"ESTADO {period}: {path.name}", flush=True)
            rows = write_station_file(path, destination)
            entry = {"source_file": str(path.relative_to(ROOT)), "dataset": "estado_estaciones", "period": period, "output_file": str(destination.relative_to(ROOT)), "rows": rows, "status": "creado", "notes": "JSON de instantáneas a nivel estación"}
            entries.append(entry)
            append_manifest([entry])
            registered_outputs.add(entry["output_file"])
            print(f"  -> {rows:,} filas", flush=True)

    if kind in ("trips", "all"):
        destination_dir = OUTPUT / "viajes"
        destination_dir.mkdir(exist_ok=True)
        sources: list[tuple[Path, str]] = [(path, "json") for path in json_trip_sources()]
        sources.extend((path, "csv") for path in csv_trip_sources())
        for path, format_name in sorted(sources, key=lambda item: source_period(item[0])):
            period = source_period(path)
            destination = destination_dir / f"viajes_{period}.csv"
            if destination.exists():
                print(f"OMITIDO (ya existe): {destination.relative_to(ROOT)}")
                output_file = str(destination.relative_to(ROOT))
                if output_file not in registered_outputs:
                    entry = {"source_file": str(path.relative_to(ROOT)), "dataset": "viajes", "period": period, "output_file": output_file, "rows": csv_data_rows(destination), "status": "verificado_existente", "notes": "CSV creado antes del registro automático"}
                    append_manifest([entry])
                    registered_outputs.add(output_file)
                continue
            print(f"VIAJES {period}: {path.name}", flush=True)
            rows = write_json_trip_file(path, destination) if format_name == "json" else write_csv_trip_file(path, destination)
            entry = {"source_file": str(path.relative_to(ROOT)), "dataset": "viajes", "period": period, "output_file": str(destination.relative_to(ROOT)), "rows": rows, "status": "creado", "notes": "Esquema unificado; origen " + format_name}
            entries.append(entry)
            append_manifest([entry])
            registered_outputs.add(entry["output_file"])
            print(f"  -> {rows:,} filas", flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=("all", "station", "trips"), default="all")
    args = parser.parse_args()
    convert(args.kind)
