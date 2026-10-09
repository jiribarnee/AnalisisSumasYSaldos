"""
excel_processor.py

Lee un archivo Excel de "Sumas y Saldos" (balance contable mensual) y
lo devuelve como un DataFrame de pandas limpio y normalizado.

Estructura esperada (detectada analizando sumas_06-2026.xlsx y
sumas_07-2026.xlsx):

    CUENTA, NOMBRE, DEBE, HABER, SALDO

Cada fila es UNA CUENTA CONTABLE (código de 10 dígitos + nombre), con
sus movimientos del mes (DEBE/HABER) y el saldo resultante
(SALDO = DEBE - HABER, verificado numéricamente).

IMPORTANTE: a diferencia de otras versiones de esta familia de apps,
acá SALDO puede dar exactamente $0 aunque la cuenta haya tenido
movimiento real en el mes (por ejemplo, una cuenta de IVA donde
DEBE == HABER). Por eso, para decidir si una cuenta es nueva o
discontinuada entre dos períodos, NO se puede mirar si el saldo es
distinto de cero: hay que mirar si la cuenta aparece como fila en el
archivo de ese período (ver core/comparator.py).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

import pandas as pd

REQUIRED_COLUMNS = {
    "CUENTA": True,
    "NOMBRE": True,
    "SALDO": True,
    "DEBE": False,
    "HABER": False,
}


class ExcelProcessingError(Exception):
    """Error controlado durante la lectura/validación de un Excel."""

    pass


@dataclass
class LoadedPeriod:
    label: str
    filepath: str
    dataframe: pd.DataFrame
    row_count: int = field(init=False)

    def __post_init__(self):
        self.row_count = len(self.dataframe)


def detect_period_label(filepath: str) -> str:
    """Genera un nombre de período legible a partir del nombre del archivo."""
    filename = os.path.basename(filepath)
    name_without_ext = os.path.splitext(filename)[0]
    cleaned = re.sub(r"[_\-]+", " ", name_without_ext).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.upper() if cleaned else "PERIODO"


def load_balance_file(filepath: str, period_label: str | None = None) -> LoadedPeriod:
    """
    Lee un archivo Excel de Sumas y Saldos y devuelve un LoadedPeriod
    con el DataFrame ya limpio. Lanza ExcelProcessingError con un
    mensaje claro si algo no es válido.
    """
    _validate_file_exists_and_extension(filepath)

    df = _read_excel_safely(filepath)
    df = _normalize_columns(df, filepath)
    _validate_required_columns(df, filepath)
    df = _clean_data(df)

    if len(df) == 0:
        raise ExcelProcessingError(
            f'El archivo "{os.path.basename(filepath)}" no contiene filas de datos '
            f"válidas después de limpiarlo. Verifique que no esté vacío."
        )

    label = period_label or detect_period_label(filepath)
    return LoadedPeriod(label=label, filepath=filepath, dataframe=df)


def _validate_file_exists_and_extension(filepath: str) -> None:
    if not os.path.isfile(filepath):
        raise ExcelProcessingError(f"No se encontró el archivo:\n{filepath}")

    ext = os.path.splitext(filepath)[1].lower()
    if ext not in (".xlsx", ".xlsm"):
        raise ExcelProcessingError(
            f'El archivo "{os.path.basename(filepath)}" no es un Excel válido (.xlsx).\n'
            f"Formato detectado: {ext or 'desconocido'}"
        )


def _read_excel_safely(filepath: str) -> pd.DataFrame:
    try:
        return pd.read_excel(filepath, sheet_name=0)
    except Exception as exc:  # noqa: BLE001
        raise ExcelProcessingError(
            f'No se pudo abrir "{os.path.basename(filepath)}".\n'
            f"El archivo podría estar corrupto, dañado o no ser un Excel real.\n\n"
            f"Detalle técnico: {exc}"
        ) from exc


def _normalize_columns(df: pd.DataFrame, filepath: str) -> pd.DataFrame:
    if df.empty and len(df.columns) == 0:
        raise ExcelProcessingError(
            f'El archivo "{os.path.basename(filepath)}" está vacío (sin columnas).'
        )
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _validate_required_columns(df: pd.DataFrame, filepath: str) -> None:
    missing = [col for col, required in REQUIRED_COLUMNS.items() if required and col not in df.columns]
    if missing:
        cols_txt = ", ".join(f'"{c}"' for c in missing)
        raise ExcelProcessingError(
            f'El archivo "{os.path.basename(filepath)}" no tiene la estructura esperada.\n\n'
            f"Faltan las columnas: {cols_txt}\n\n"
            f'Verifique que el Excel sea un "Sumas y Saldos" con al menos '
            f"las columnas CUENTA, NOMBRE y SALDO."
        )


# Solo se analizan las cuentas cuyo código empieza con estos prefijos:
# 4010 = gastos y 5010 = ingresos. El resto del balance (activo, pasivo)
# se ignora al leer el archivo.
PREFIJO_GASTOS = "4010"
PREFIJO_INGRESOS = "5010"
PREFIJOS_CUENTAS = (PREFIJO_GASTOS, PREFIJO_INGRESOS)


def _clean_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if "NOMBRE" in df.columns:
        df["NOMBRE"] = df["NOMBRE"].astype(str).str.strip()
        df = df[df["NOMBRE"].str.len() > 0]

    if "CUENTA" in df.columns:
        df["CUENTA"] = df["CUENTA"].astype(str).str.strip()
        df = df[df["CUENTA"].str.startswith(PREFIJOS_CUENTAS)]

    if "SALDO" in df.columns:
        df["SALDO"] = pd.to_numeric(df["SALDO"], errors="coerce")
        df = df[df["SALDO"].notna()]

    for col in ("DEBE", "HABER"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    df = df.reset_index(drop=True)
    return df


def prefijo_cuenta(cuenta: str, digitos: int = 2) -> str:
    """Devuelve los primeros N dígitos del código de cuenta (agrupación contable)."""
    return str(cuenta)[:digitos]
