"""Carga de solo lectura para la aplicación del TFM (fase 8).

Desde la raíz del proyecto: ``python -m app.data`` comprueba las 27 tablas.
Las páginas importarán, por ejemplo, ``from app.data import cargar_predicciones``.
No depende de scripts de preparación, CSV, notebooks ni artefactos del modelo.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Sequence

import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
APP_DATA = ROOT / "app_data"

TABLAS_2022 = (
    "predicciones_contexto_2022", "candidatos_2022", "transferencias_2022",
    "candidatos_no_resueltos_2022", "factores_por_clase", "horas_sensibles",
    "estaciones_sensibles", "comparacion_gain_vs_shap", "shap_importancia_global",
    "shap_importancia_por_clase", "explicaciones_shap_por_clase", "politica_operativa",
    "metricas_test_2022", "informe_por_clase_test_2022", "matrices_confusion_test_2022",
    "errores_por_mes_2022",
)
TABLAS_2023 = (
    "resumen_mensual_2023", "cobertura_mensual_2023", "viajes_por_dia_2023",
    "viajes_por_hora_2023", "viajes_por_dia_semana_2023", "viajes_por_segmento_semana_2023",
    "actividad_estaciones_2023", "pares_od_2023", "resumen_duracion_2023",
    "auditoria_alcance_2023", "auditoria_calidad_2023",
)
TABLAS = TABLAS_2022 + TABLAS_2023


class DatosAppError(RuntimeError):
    """Error de datos que las páginas podrán mostrar con un mensaje claro."""


def _firma_archivo(path: Path) -> tuple[int, int, int]:
    """El cambio de archivo invalida la caché, sin calcular su hash en cada rerun."""
    if not path.is_file():
        raise DatosAppError(
            f"Falta el archivo {path.name} en {path.parent}. "
            "Completa la fase 7 con: python scripts/preparar_datos_app.py. "
            "Si ya había una preparación, revisa su integridad antes de continuar."
        )
    info = path.stat()
    return info.st_mtime_ns, info.st_ctime_ns, info.st_size


@st.cache_data(show_spinner=False, max_entries=4)
def _leer_manifiesto(path_text: str, firma: tuple[int, int, int]) -> dict:
    path = Path(path_text)
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise DatosAppError(f"No se puede leer {path.name}: {error}") from error
    if (not isinstance(manifest, dict) or manifest.get("version") != 1
            or not isinstance(manifest.get("tablas"), dict)):
        raise DatosAppError("El manifiesto no corresponde al formato de la fase 7.")
    if _firma_archivo(path) != firma:
        raise DatosAppError("El manifiesto cambió durante la lectura. Repite la comprobación.")
    return manifest


def cargar_manifiesto() -> dict:
    """Devuelve metadatos y limitaciones; no transforma las claves del JSON."""
    path = APP_DATA / "manifiesto_app.json"
    return _leer_manifiesto(str(path), _firma_archivo(path))


@st.cache_data(show_spinner=False, max_entries=48)
def _leer_parquet(
    path_text: str,
    firma: tuple[int, int, int],
    expected_sha256: str,
    expected_rows: int,
    schema: tuple[tuple[str, str], ...],
    columns: tuple[str, ...] | None,
) -> pd.DataFrame:
    """Verifica integridad en la primera lectura de cada versión del archivo."""
    path = Path(path_text)
    try:
        with path.open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        if digest != expected_sha256:
            raise DatosAppError(
                f"{path.name} no coincide con la huella del manifiesto. "
                "No edites el manifiesto para ocultar la diferencia; revisa la preparación de la fase 7."
            )
        frame = pd.read_parquet(path, columns=list(columns) if columns is not None else None)
    except DatosAppError:
        raise
    except Exception as error:
        raise DatosAppError(f"No se puede leer {path.name}: {error}") from error
    expected_schema = dict(schema)
    selected = list(columns) if columns is not None else list(expected_schema)
    if len(frame) != expected_rows or list(frame.columns) != selected:
        raise DatosAppError(f"{path.name}: filas o columnas distintas de las registradas en el manifiesto.")
    for column in selected:
        if str(frame[column].dtype) != expected_schema[column]:
            raise DatosAppError(f"{path.name}: tipo de dato inesperado en {column}.")
    if _firma_archivo(path) != firma:
        raise DatosAppError(f"{path.name} cambió durante la lectura. Repite la comprobación.")
    return frame


def cargar_tabla(nombre: str, columnas: Sequence[str] | None = None) -> pd.DataFrame:
    """Carga una tabla registrada, opcionalmente solo las columnas solicitadas.

    Se conservan filas, orden, tipos y valores ausentes. Cada llamada recibe su
    propia copia desde st.cache_data; filtrarla no cambia los datos originales.
    No admite rutas libres ni vuelve a generar un archivo ausente.
    """
    if nombre not in TABLAS:
        raise DatosAppError(f"Tabla desconocida: {nombre}. Consulta listar_tablas().")
    manifest = cargar_manifiesto()
    entry = manifest["tablas"].get(nombre)
    if not isinstance(entry, dict):
        raise DatosAppError(f"La tabla {nombre} no está registrada en el manifiesto de la fase 7.")
    if (entry.get("archivo") != f"{nombre}.parquet"
            or not isinstance(entry.get("columnas"), dict)
            or not isinstance(entry.get("filas"), int)
            or entry["filas"] < 0
            or not isinstance(entry.get("sha256"), str)):
        raise DatosAppError(f"Metadatos incompletos o inválidos para {nombre}.")
    selected = None
    if columnas is not None:
        if isinstance(columnas, str):
            raise DatosAppError("columnas debe ser una lista o tupla, no una cadena de texto.")
        selected = tuple(columnas)
        if not selected or not all(isinstance(c, str) for c in selected):
            raise DatosAppError("Indica al menos un nombre de columna válido.")
        if len(selected) != len(set(selected)):
            raise DatosAppError("No se pueden solicitar columnas duplicadas.")
        missing = sorted(set(selected) - set(entry["columnas"]))
        if missing:
            raise DatosAppError(f"Columnas desconocidas en {nombre}: {', '.join(missing)}")
    path = APP_DATA / f"{nombre}.parquet"
    return _leer_parquet(str(path), _firma_archivo(path), entry["sha256"], entry["filas"],
                         tuple(entry["columnas"].items()), selected)


def listar_tablas() -> list[str]:
    """Nombres registrados que reconoce esta versión de la aplicación."""
    manifest = cargar_manifiesto()
    return [name for name in TABLAS if name in manifest["tablas"]]


def cargar_predicciones(columnas: Sequence[str] | None = None) -> pd.DataFrame:
    return cargar_tabla("predicciones_contexto_2022", columnas)


def cargar_candidatos(columnas: Sequence[str] | None = None) -> pd.DataFrame:
    return cargar_tabla("candidatos_2022", columnas)


def cargar_transferencias(columnas: Sequence[str] | None = None) -> pd.DataFrame:
    return cargar_tabla("transferencias_2022", columnas)


def cargar_no_resueltos(columnas: Sequence[str] | None = None) -> pd.DataFrame:
    return cargar_tabla("candidatos_no_resueltos_2022", columnas)


def cargar_factores_por_clase() -> pd.DataFrame:
    """Factores SHAP globales por clase, no explicaciones locales ni causales."""
    return cargar_tabla("factores_por_clase")


def cargar_horas_sensibles() -> pd.DataFrame:
    """Conserva soporte, falsos negativos y tasas; no corrige predicciones."""
    return cargar_tabla("horas_sensibles")


def cargar_estaciones_sensibles() -> pd.DataFrame:
    return cargar_tabla("estaciones_sensibles")


def cargar_viajes_2023(nombre: str = "resumen_mensual_2023") -> pd.DataFrame:
    """Entrada descriptiva separada: rechaza tablas predictivas u operativas."""
    if nombre not in TABLAS_2023:
        raise DatosAppError(f"{nombre} no pertenece al análisis descriptivo de viajes de 2023.")
    return cargar_tabla(nombre)


def obtener_instantes_disponibles() -> list[pd.Timestamp]:
    """Solo momentos observados: no genera ni rellena horas inexistentes."""
    times = cargar_predicciones(columnas=["fecha_hora_local"])["fecha_hora_local"]
    return times.dropna().drop_duplicates().sort_values().tolist()


def limpiar_cache_datos() -> None:
    """Borra únicamente las cachés de este módulo, nunca archivos o modelos."""
    _leer_manifiesto.clear()
    _leer_parquet.clear()


def comprobar_datos() -> pd.DataFrame:
    """Comprobación de lectura e integridad de las 27 tablas, sin escribir salidas."""
    manifest = cargar_manifiesto()
    if set(manifest["tablas"]) != set(TABLAS):
        raise DatosAppError("El manifiesto debe contener exactamente las 27 tablas de la fase 7.")
    rows = []
    for name in TABLAS:
        frame = cargar_tabla(name)
        rows.append({"tabla": name, "filas": len(frame), "columnas": len(frame.columns)})
    return pd.DataFrame(rows)


def main() -> int:
    print("Comprobando la carga de datos de la aplicación...", flush=True)
    try:
        report = comprobar_datos()
        print(report.to_string(index=False))
        print("\nCarga correcta: 27 tablas verificadas. No se ha modificado ningún archivo de datos.")
        print("La fase 8 está preparada. Todavía no se ha iniciado la interfaz de Streamlit.")
        return 0
    except (DatosAppError, OSError) as error:
        print(f"\nComprobación detenida: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
