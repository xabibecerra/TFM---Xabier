#!/usr/bin/env python3
"""Filtra y enriquece el calendario laboral de Madrid para el TFM.

Los originales permanecen intactos. La salida tiene una fila por día y usa
fechas ISO para poder unirla directamente con datos horarios.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Bases de datos" / "Calendario laboral" / "300082-1-calendario_laboral-csv.csv"
OUTPUT = ROOT / "Datos analiticos" / "calendario_tfm.csv"
FIELDS = [
    "fecha", "anio", "mes", "dia_mes", "dia_semana", "dia_semana_num",
    "es_fin_de_semana", "es_laborable", "es_festivo", "tipo_dia",
    "tipo_festivo", "festividad",
]


def generate() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(OUTPUT.suffix + ".part")
    if OUTPUT.exists() or temporary.exists():
        raise FileExistsError(f"Ya existe un resultado: {OUTPUT}")
    rows = 0
    with SOURCE.open("r", encoding="utf-8-sig", newline="") as input_file, temporary.open("x", encoding="utf-8-sig", newline="") as output_file:
        reader = csv.DictReader(input_file, delimiter=";")
        writer = csv.DictWriter(output_file, fieldnames=FIELDS)
        writer.writeheader()
        for source_row in reader:
            date = datetime.strptime(source_row["Dia"], "%d/%m/%Y").date()
            if not 2019 <= date.year <= 2022:
                continue
            type_day = (source_row["laborable / festivo / domingo festivo"] or "").strip().lower()
            weekend = date.weekday() >= 5
            writer.writerow({
                "fecha": date.isoformat(),
                "anio": date.year,
                "mes": date.month,
                "dia_mes": date.day,
                "dia_semana": (source_row["Dia_semana"] or "").strip().lower(),
                "dia_semana_num": date.weekday(),
                "es_fin_de_semana": int(weekend),
                "es_laborable": int(type_day == "laborable"),
                "es_festivo": int("festivo" in type_day),
                "tipo_dia": type_day,
                "tipo_festivo": (source_row["Tipo de Festivo"] or "").strip(),
                "festividad": (source_row["Festividad"] or "").strip(),
            })
            rows += 1
    temporary.replace(OUTPUT)
    return rows


if __name__ == "__main__":
    print(f"CSV creado: {OUTPUT.relative_to(ROOT)}")
    print(f"Filas: {generate():,}")
