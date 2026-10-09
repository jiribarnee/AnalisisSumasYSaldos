"""
calculations.py

Funciones de cálculo puras y reutilizables. Sin dependencias de la UI.
"""

from __future__ import annotations

import math
import re


def variacion_absoluta(valor_p1: float, valor_p2: float) -> float:
    return valor_p2 - valor_p1


def variacion_porcentual(valor_p1: float, valor_p2: float) -> float | None:
    """
    Variación porcentual de p1 a p2. Devuelve None si p1 == 0 (no hay
    base significativa para calcular un %).
    """
    if valor_p1 == 0:
        return None
    return ((valor_p2 - valor_p1) / abs(valor_p1)) * 100


def formato_moneda(valor: float, simbolo: str = "$") -> str:
    """Formatea un número como moneda estilo argentino: $1.234.567,89"""
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return "-"
    texto = f"{valor:,.2f}"
    texto = texto.replace(",", "␟").replace(".", ",").replace("␟", ".")
    return f"{simbolo}{texto}"


def formato_porcentaje(valor: float | None, decimales: int = 2) -> str:
    if valor is None or (isinstance(valor, float) and valor != valor):
        return "N/A"
    signo = "+" if valor >= 0 else ""
    texto = f"{signo}{valor:.{decimales}f}"
    texto = texto.replace(".", ",")
    return f"{texto}%"


# ----------------------------------------------------------------------
# Orden cronológico de períodos
# ----------------------------------------------------------------------

_MESES = {
    "ENE": 1, "ENERO": 1, "FEB": 2, "FEBRERO": 2, "MAR": 3, "MARZO": 3,
    "ABR": 4, "ABRIL": 4, "MAY": 5, "MAYO": 5, "JUN": 6, "JUNIO": 6,
    "JUL": 7, "JULIO": 7, "AGO": 8, "AGOSTO": 8, "SEP": 9, "SEPT": 9, "SEPTIEMBRE": 9,
    "OCT": 10, "OCTUBRE": 10, "NOV": 11, "NOVIEMBRE": 11, "DIC": 12, "DICIEMBRE": 12,
}


def clave_cronologica(label: str) -> tuple[int, int] | None:
    """
    Devuelve (año, mes) leyendo el nombre del período, o None si no se
    puede interpretar. Entiende "RES. 10 2025", "10-2025", "2025-10",
    "Octubre 2025" y nombres de mes solos ("JUNIO", que queda con año 0).
    """
    texto = str(label).upper()

    m = re.search(r"(?<!\d)(\d{4})\D+(\d{1,2})(?!\d)", texto)          # 2025-10
    if m and 1 <= int(m.group(2)) <= 12:
        return int(m.group(1)), int(m.group(2))

    m = re.search(r"(?<!\d)(\d{1,2})\D+(\d{4})(?!\d)", texto)          # 10 2025 / 10-2025
    if m and 1 <= int(m.group(1)) <= 12:
        return int(m.group(2)), int(m.group(1))

    palabras = re.findall(r"[A-ZÁÉÍÓÚ]+", texto)
    for palabra in palabras:
        sin_tilde = palabra.translate(str.maketrans("ÁÉÍÓÚ", "AEIOU"))
        if sin_tilde in _MESES:
            anio = re.search(r"(?<!\d)(\d{4})(?!\d)", texto) or re.search(r"(?<!\d)(\d{2})(?!\d)", texto)
            if anio:
                a = int(anio.group(1))
                return (a + 2000 if a < 100 else a), _MESES[sin_tilde]
            return 0, _MESES[sin_tilde]

    m = re.search(r"(?<!\d)(\d{1,2})\D+(\d{2})(?!\d)", texto)          # 07/26
    if m and 1 <= int(m.group(1)) <= 12:
        return 2000 + int(m.group(2)), int(m.group(1))

    m = re.search(r"(?<!\d)(\d{1,2})(?!\d)", texto)                     # "SUMAS 07"
    if m and 1 <= int(m.group(1)) <= 12:
        return 0, int(m.group(1))
    return None


def ordenar_cronologico(labels: list[str]) -> list[str]:
    """Ordena los períodos del más antiguo al más nuevo. Si alguno no se puede interpretar, deja el orden original."""
    claves = [clave_cronologica(l) for l in labels]
    if any(c is None for c in claves):
        return list(labels)
    return [l for _, l in sorted(zip(claves, labels), key=lambda x: x[0])]
