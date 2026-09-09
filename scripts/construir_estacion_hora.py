#!/usr/bin/env python3
"""Construye la base analítica BiciMAD a nivel estación-hora por meses.

Cada salida conserva una instantánea de estado, los flujos de viajes de esa
hora, el calendario y la meteorología municipal. Se particiona por mes para no
forzar un CSV único de varios gigabytes. Los archivos fuente no se modifican.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import fmean
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
ANALYTICS = ROOT / "Datos analiticos"
BICIMAD = ANALYTICS / "BiciMAD"
STATES = BICIMAD / "estado_estaciones"
TRIPS = BICIMAD / "viajes"
CALENDAR = ANALYTICS / "calendario_tfm.csv"
WEATHER = ANALYTICS / "meteorologia_hora.csv"
OUTPUT = ANALYTICS / "estacion_hora"
MANIFEST = OUTPUT / "manifest_estacion_hora.csv"
MADRID = ZoneInfo("Europe/Madrid")

STATE_FIELDS = [
    "snapshot_at", "fecha_hora_local", "fecha", "station_id", "station_number",
    "station_name", "address", "latitude", "longitude", "capacity",
    "bikes_available", "docks_available", "reservations_count", "no_available",
    "activation", "light", "occupancy_ratio",
]
FLOW_FIELDS = [
    "departures_count", "arrivals_count", "net_flow",
    "departure_duration_mean_seconds", "weather_available",
]
MANIFEST_FIELDS = [
    "period", "output_file", "rows", "trip_rows_read", "unmatched_departures",
    "unmatched_arrivals", "missing_weather_rows", "status",
]


def read_csv_as_dict(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as input_file:
        reader = csv.DictReader(input_file)
        return {row[reader.fieldnames[0]]: row for row in reader}


def parse_local_hour(raw: str) -> str:
    """Return a Europe/Madrid wall-clock hour from mixed BiciMAD timestamps."""
    value = (raw or "").strip()
    if not value:
        return ""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(MADRID).replace(tzinfo=None)
    return parsed.replace(minute=0, second=0, microsecond=0).isoformat(timespec="seconds")


def safe_float(raw: str) -> float | None:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def occupancy_ratio(row: dict[str, str]) -> str:
    bikes = safe_float(row.get("bikes_available", ""))
    capacity = safe_float(row.get("capacity", ""))
    if bikes is None or capacity is None or capacity <= 0:
        return ""
    return f"{bikes / capacity:.6f}".rstrip("0").rstrip(".")


def period_from_state_path(path: Path) -> str:
    return path.stem.rsplit("_", 1)[1]


def read_trip_flows(
    path: Path,
    period: str,
    pending_arrivals: dict[str, dict[tuple[str, str], int]],
) -> tuple[dict[tuple[str, str], list[float]], dict[tuple[str, str], int], int]:
    """Aggregate departures for this period and carry arrivals into their month."""
    departures: dict[tuple[str, str], list[float]] = defaultdict(lambda: [0, 0.0])
    arrivals = pending_arrivals.pop(period, defaultdict(int))
    rows = 0
    with path.open("r", encoding="utf-8-sig", newline="") as input_file:
        for trip in csv.DictReader(input_file):
            rows += 1
            duration = safe_float(trip.get("duration_seconds", ""))
            start_hour = parse_local_hour(trip.get("start_at", ""))
            origin = (trip.get("origin_station_id") or "").strip()
            if start_hour and origin:
                aggregate = departures[(start_hour, origin)]
                aggregate[0] += 1
                if duration is not None:
                    aggregate[1] += duration
            end_hour = parse_local_hour(trip.get("end_at", ""))
            destination = (trip.get("destination_station_id") or "").strip()
            if end_hour and destination:
                target_period = end_hour[:7].replace("-", "")
                target = arrivals if target_period == period else pending_arrivals[target_period]
                target[(end_hour, destination)] += 1
    return departures, arrivals, rows


def append_manifest(entry: dict[str, str | int]) -> None:
    first_write = not MANIFEST.exists()
    with MANIFEST.open("a", encoding="utf-8-sig", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=MANIFEST_FIELDS)
        if first_write:
            writer.writeheader()
        writer.writerow(entry)


def manifest_periods() -> set[str]:
    if not MANIFEST.exists():
        return set()
    with MANIFEST.open("r", encoding="utf-8-sig", newline="") as input_file:
        return {row["period"] for row in csv.DictReader(input_file)}


def build() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    calendar = read_csv_as_dict(CALENDAR)
    weather = read_csv_as_dict(WEATHER)
    calendar_fields = [field for field in next(iter(calendar.values())).keys() if field != "fecha"]
    weather_fields = [field for field in next(iter(weather.values())).keys() if field != "fecha_hora_local"]
    fieldnames = STATE_FIELDS + FLOW_FIELDS + weather_fields + calendar_fields
    pending_arrivals: dict[str, dict[tuple[str, str], int]] = defaultdict(lambda: defaultdict(int))
    completed = manifest_periods()

    for state_file in sorted(STATES.glob("estado_estaciones_*.csv")):
        period = period_from_state_path(state_file)
        trip_file = TRIPS / f"viajes_{period}.csv"
        if not trip_file.exists():
            raise FileNotFoundError(f"No existe el CSV de viajes para {period}: {trip_file}")
        departures, arrivals, trip_rows = read_trip_flows(trip_file, period, pending_arrivals)
        destination = OUTPUT / f"estacion_hora_{period}.csv"
        if destination.exists():
            print(f"OMITIDO (ya existe): {destination.relative_to(ROOT)}", flush=True)
            continue
        temporary = destination.with_suffix(destination.suffix + ".part")
        if temporary.exists():
            raise FileExistsError(f"Resultado temporal pendiente: {temporary}")
        print(f"ESTACIÓN-HORA {period}", flush=True)
        rows = 0
        missing_weather = 0
        with state_file.open("r", encoding="utf-8-sig", newline="") as input_file, temporary.open("x", encoding="utf-8-sig", newline="") as output_file:
            reader = csv.DictReader(input_file)
            writer = csv.DictWriter(output_file, fieldnames=fieldnames)
            writer.writeheader()
            for state in reader:
                hour = state["snapshot_hour"]
                station_id = state["station_id"].strip()
                departure_count, departure_duration = departures.pop((hour, station_id), [0, 0.0])
                arrival_count = arrivals.pop((hour, station_id), 0)
                weather_row = weather.get(hour, {})
                calendar_row = calendar.get(hour[:10], {})
                if not weather_row:
                    missing_weather += 1
                output_row = {
                    "snapshot_at": state["snapshot_at"],
                    "fecha_hora_local": hour,
                    "fecha": hour[:10],
                    "station_id": station_id,
                    "station_number": state["station_number"],
                    "station_name": state["station_name"],
                    "address": state["address"],
                    "latitude": state["latitude"],
                    "longitude": state["longitude"],
                    "capacity": state["capacity"],
                    "bikes_available": state["bikes_available"],
                    "docks_available": state["docks_available"],
                    "reservations_count": state["reservations_count"],
                    "no_available": state["no_available"],
                    "activation": state["activation"],
                    "light": state["light"],
                    "occupancy_ratio": occupancy_ratio(state),
                    "departures_count": int(departure_count),
                    "arrivals_count": int(arrival_count),
                    "net_flow": int(arrival_count - departure_count),
                    "departure_duration_mean_seconds": (f"{departure_duration / departure_count:.3f}" if departure_count else ""),
                    "weather_available": int(bool(weather_row)),
                }
                output_row.update(weather_row)
                output_row.update(calendar_row)
                writer.writerow(output_row)
                rows += 1
        temporary.replace(destination)
        unmatched_departures = sum(int(aggregate[0]) for aggregate in departures.values())
        unmatched_arrivals = sum(arrivals.values())
        entry = {
            "period": period,
            "output_file": str(destination.relative_to(ROOT)),
            "rows": rows,
            "trip_rows_read": trip_rows,
            "unmatched_departures": unmatched_departures,
            "unmatched_arrivals": unmatched_arrivals,
            "missing_weather_rows": missing_weather,
            "status": "created",
        }
        append_manifest(entry)
        print(f"  -> {rows:,} filas; sin meteorología={missing_weather:,}; viajes no emparejados={unmatched_departures + unmatched_arrivals:,}", flush=True)


if __name__ == "__main__":
    build()
