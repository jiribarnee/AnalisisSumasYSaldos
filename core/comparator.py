"""
comparator.py

Compara entre 2 y 12 períodos de Sumas y Saldos, agrupando por cuenta
(CUENTA/NOMBRE).

CORRECCIÓN IMPORTANTE respecto a otras apps de esta familia: acá una
cuenta puede tener SALDO == 0 en un período y sin embargo haber tenido
movimiento real ese mes (DEBE == HABER, por ejemplo cuentas de IVA).
Por eso "nueva"/"discontinuada" se decide mirando si la cuenta
APARECE COMO FILA en el archivo de ese período (columna auxiliar
_PRESENTE_<label>), no si su saldo es distinto de cero.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import reduce

import pandas as pd

from core.calculations import variacion_absoluta, variacion_porcentual
from core.excel_processor import PREFIJO_GASTOS, PREFIJO_INGRESOS, LoadedPeriod

ESTADO_NUEVA = "NUEVA"
ESTADO_DISCONTINUADA = "DISCONTINUADA"
ESTADO_EXISTENTE = "EXISTENTE"

MIN_PERIODOS = 2
MAX_PERIODOS = 12

_COMPONENTES = ["DEBE", "HABER"]


@dataclass
class ComparisonResult:
    labels: list[str]
    tabla: pd.DataFrame
    resumen: dict
    columnas_componentes: list[str]  # ["DEBE", "HABER"] si están presentes en todos los períodos

    @property
    def label_primero(self) -> str:
        return self.labels[0]

    @property
    def label_ultimo(self) -> str:
        return self.labels[-1]

    @property
    def label_penultimo(self) -> str | None:
        return self.labels[-2] if len(self.labels) >= 2 else None


def comparar_periodos(periodos: list[LoadedPeriod]) -> ComparisonResult:
    if len(periodos) < MIN_PERIODOS:
        raise ValueError(f"Se necesitan al menos {MIN_PERIODOS} períodos para comparar.")
    if len(periodos) > MAX_PERIODOS:
        raise ValueError(f"No se pueden comparar más de {MAX_PERIODOS} períodos a la vez.")

    labels = [p.label for p in periodos]

    componentes_por_periodo = [
        set(c for c in _COMPONENTES if c in p.dataframe.columns) for p in periodos
    ]
    componentes_comunes = [c for c in _COMPONENTES if all(c in s for s in componentes_por_periodo)]

    aggs = [_agrupar_por_cuenta(p.dataframe, componentes_comunes) for p in periodos]
    tabla = _combinar(aggs, labels, componentes_comunes)
    resumen = _calcular_resumen(tabla, labels, componentes_comunes)

    return ComparisonResult(labels=labels, tabla=tabla, resumen=resumen, columnas_componentes=componentes_comunes)


def _agrupar_por_cuenta(df: pd.DataFrame, componentes: list[str]) -> pd.DataFrame:
    agg_dict = {"NOMBRE": ("NOMBRE", lambda s: s.value_counts().idxmax()), "SALDO": ("SALDO", "sum")}
    for comp in componentes:
        agg_dict[comp] = (comp, "sum")
    return df.groupby("CUENTA").agg(**agg_dict).reset_index()


def _combinar(aggs: list[pd.DataFrame], labels: list[str], componentes: list[str]) -> pd.DataFrame:
    renamed = []
    for df, label in zip(aggs, labels):
        df = df.copy()
        # Antes de renombrar: marcar presencia real de la cuenta en este período
        df[f"_PRESENTE_{label}"] = True
        rename_map = {"NOMBRE": f"NOMBRE_{label}", "SALDO": f"SALDO_{label}"}
        for comp in componentes:
            rename_map[comp] = f"{comp}_{label}"
        renamed.append(df.rename(columns=rename_map))

    merged = reduce(lambda left, right: pd.merge(left, right, on="CUENTA", how="outer"), renamed)

    for label in labels:
        col_presente = f"_PRESENTE_{label}"
        merged[col_presente] = merged[col_presente].fillna(False)

        col_saldo = f"SALDO_{label}"
        merged[col_saldo] = merged[col_saldo].fillna(0.0)
        for comp in componentes:
            col = f"{comp}_{label}"
            if col in merged.columns:
                merged[col] = merged[col].fillna(0.0)

    nombre_cols = [f"NOMBRE_{label}" for label in labels]

    def _pick_nombre(row):
        for col in reversed(nombre_cols):
            if pd.notna(row[col]):
                return row[col]
        return "(sin nombre)"

    merged["NOMBRE"] = merged.apply(_pick_nombre, axis=1)
    merged = merged.drop(columns=nombre_cols)

    col_presente_primero = f"_PRESENTE_{labels[0]}"
    col_presente_ultimo = f"_PRESENTE_{labels[-1]}"
    col_saldo_primero = f"SALDO_{labels[0]}"
    col_saldo_ultimo = f"SALDO_{labels[-1]}"

    def _estado(row):
        presente_primero = bool(row[col_presente_primero])
        presente_ultimo = bool(row[col_presente_ultimo])
        if presente_primero and not presente_ultimo:
            return ESTADO_DISCONTINUADA
        if presente_ultimo and not presente_primero:
            return ESTADO_NUEVA
        return ESTADO_EXISTENTE

    merged["ESTADO"] = merged.apply(_estado, axis=1)
    merged["DIFERENCIA"] = merged.apply(
        lambda r: variacion_absoluta(r[col_saldo_primero], r[col_saldo_ultimo]), axis=1
    )
    merged["VARIACION_PCT"] = merged.apply(
        lambda r: variacion_porcentual(r[col_saldo_primero], r[col_saldo_ultimo]), axis=1
    )

    columnas_saldo = [f"SALDO_{label}" for label in labels]
    columnas_presente = [f"_PRESENTE_{label}" for label in labels]
    columnas_componentes_final = [
        f"{comp}_{label}" for label in labels for comp in componentes if f"{comp}_{label}" in merged.columns
    ]

    columnas_base = ["CUENTA", "NOMBRE"] + columnas_saldo + ["DIFERENCIA", "VARIACION_PCT", "ESTADO"]
    merged = merged[columnas_base + columnas_componentes_final + columnas_presente]
    merged = merged.sort_values(by=col_saldo_ultimo, key=lambda s: s.abs(), ascending=False).reset_index(drop=True)
    return merged


GRUPO_GASTO = "GASTO"
GRUPO_INGRESO = "INGRESO"


def _grupo_por_cuenta(cuentas: pd.Series) -> pd.Series:
    """GASTO para cuentas 4010*, INGRESO para cuentas 5010*."""
    return cuentas.astype(str).str.startswith(PREFIJO_INGRESOS).map({True: GRUPO_INGRESO, False: GRUPO_GASTO})


def _calcular_resumen(tabla: pd.DataFrame, labels: list[str], componentes: list[str]) -> dict:
    grupo = _grupo_por_cuenta(tabla["CUENTA"])
    # Gastos: saldo tal cual (positivo). Ingresos: saldo con signo invertido
    # (en contabilidad el ingreso tiene saldo acreedor/negativo), así ambos
    # se leen como montos positivos.
    gastos_por_periodo = {l: float(tabla.loc[grupo == GRUPO_GASTO, f"SALDO_{l}"].sum()) for l in labels}
    ingresos_por_periodo = {l: -float(tabla.loc[grupo == GRUPO_INGRESO, f"SALDO_{l}"].sum()) for l in labels}

    totales_debe = {}
    totales_haber = {}
    for label in labels:
        col_debe = f"DEBE_{label}"
        col_haber = f"HABER_{label}"
        totales_debe[label] = float(tabla[col_debe].sum()) if col_debe in tabla.columns else None
        totales_haber[label] = float(tabla[col_haber].sum()) if col_haber in tabla.columns else None

    saldo_primero = float(tabla[f"SALDO_{labels[0]}"].sum())
    saldo_ultimo = float(tabla[f"SALDO_{labels[-1]}"].sum())

    return {
        "labels": labels,
        "cant_periodos": len(labels),
        "totales_debe": totales_debe,
        "totales_haber": totales_haber,
        "gastos_por_periodo": gastos_por_periodo,
        "ingresos_por_periodo": ingresos_por_periodo,
        "periodo_primero": labels[0],
        "periodo_ultimo": labels[-1],
        "saldo_total_primero": saldo_primero,
        "saldo_total_ultimo": saldo_ultimo,
        "cant_cuentas_nuevas": int((tabla["ESTADO"] == ESTADO_NUEVA).sum()),
        "cant_cuentas_discontinuadas": int((tabla["ESTADO"] == ESTADO_DISCONTINUADA).sum()),
    }


# ----------------------------------------------------------------------
# Recalculo para un PAR de períodos elegido libremente por el usuario
# ----------------------------------------------------------------------

def calcular_metricas_par(tabla: pd.DataFrame, label_base: str, label_comparado: str) -> pd.DataFrame:
    """
    Copia de la tabla ancha con ESTADO, DIFERENCIA y VARIACION_PCT
    recalculados para el par (label_base, label_comparado) elegido por
    el usuario. ESTADO usa las columnas _PRESENTE_<label> (presencia
    real), no si el saldo da cero.
    """
    tabla = tabla.copy()
    col_saldo_base = f"SALDO_{label_base}"
    col_saldo_comparado = f"SALDO_{label_comparado}"
    col_presente_base = f"_PRESENTE_{label_base}"
    col_presente_comparado = f"_PRESENTE_{label_comparado}"

    def _estado(row):
        presente_base = bool(row[col_presente_base])
        presente_comparado = bool(row[col_presente_comparado])
        if presente_base and not presente_comparado:
            return ESTADO_DISCONTINUADA
        if presente_comparado and not presente_base:
            return ESTADO_NUEVA
        return ESTADO_EXISTENTE

    tabla["ESTADO"] = tabla.apply(_estado, axis=1)
    tabla["GRUPO"] = _grupo_por_cuenta(tabla["CUENTA"])
    tabla["DIFERENCIA"] = tabla.apply(
        lambda r: variacion_absoluta(r[col_saldo_base], r[col_saldo_comparado]), axis=1
    )
    tabla["VARIACION_PCT"] = tabla.apply(
        lambda r: variacion_porcentual(r[col_saldo_base], r[col_saldo_comparado]), axis=1
    )

    # Variación "real" (ingresos con signo invertido: más ingreso = sube) y
    # si el cambio es favorable (gasto baja / ingreso sube).
    signo = tabla["GRUPO"].map({GRUPO_GASTO: 1.0, GRUPO_INGRESO: -1.0})
    base_real = tabla[col_saldo_base] * signo
    dif_real = tabla["DIFERENCIA"] * signo
    tabla["VARIACION_REAL_PCT"] = [
        (d / abs(b) * 100) if b != 0 else None for d, b in zip(dif_real, base_real)
    ]
    tabla["FAVORABLE"] = [
        (d < 0) if g == GRUPO_GASTO else (d > 0)
        for d, g in zip(dif_real, tabla["GRUPO"])
    ]
    return tabla


def resumen_par(tabla_vista: pd.DataFrame, label_base: str, label_comparado: str) -> dict:
    col_saldo_base = f"SALDO_{label_base}"
    col_saldo_comparado = f"SALDO_{label_comparado}"
    col_debe_comparado = f"DEBE_{label_comparado}"
    col_haber_comparado = f"HABER_{label_comparado}"

    es_gasto = tabla_vista["GRUPO"] == GRUPO_GASTO
    es_ingreso = ~es_gasto
    gastos_base = float(tabla_vista.loc[es_gasto, col_saldo_base].sum())
    gastos_comparado = float(tabla_vista.loc[es_gasto, col_saldo_comparado].sum())
    ingresos_base = -float(tabla_vista.loc[es_ingreso, col_saldo_base].sum())
    ingresos_comparado = -float(tabla_vista.loc[es_ingreso, col_saldo_comparado].sum())

    def _pct(base, comp):
        return ((comp - base) / abs(base) * 100) if base else None

    return {
        "periodo_base": label_base,
        "periodo_comparado": label_comparado,
        "gastos_base": gastos_base,
        "gastos_comparado": gastos_comparado,
        "ingresos_base": ingresos_base,
        "ingresos_comparado": ingresos_comparado,
        "resultado_base": ingresos_base - gastos_base,
        "resultado_comparado": ingresos_comparado - gastos_comparado,
        "variacion_gastos_pct": _pct(gastos_base, gastos_comparado),
        "variacion_ingresos_pct": _pct(ingresos_base, ingresos_comparado),
        "saldo_base": float(tabla_vista[col_saldo_base].sum()),
        "saldo_comparado": float(tabla_vista[col_saldo_comparado].sum()),
        "debe_comparado": float(tabla_vista[col_debe_comparado].sum()) if col_debe_comparado in tabla_vista.columns else None,
        "haber_comparado": float(tabla_vista[col_haber_comparado].sum()) if col_haber_comparado in tabla_vista.columns else None,
        "cant_cuentas_nuevas": int((tabla_vista["ESTADO"] == ESTADO_NUEVA).sum()),
        "cant_cuentas_discontinuadas": int((tabla_vista["ESTADO"] == ESTADO_DISCONTINUADA).sum()),
    }
