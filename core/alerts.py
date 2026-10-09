"""
alerts.py

Detecta variaciones relevantes de saldo entre dos períodos elegidos, y
cuentas nuevas/discontinuadas (basado en presencia real, ver
comparator.py).

Las cuentas 4010 son gastos y las 5010 ingresos, así que el color sí
indica si el cambio es favorable (verde: baja un gasto o sube un
ingreso) o desfavorable (rojo: sube un gasto o baja un ingreso).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.comparator import ESTADO_DISCONTINUADA, ESTADO_NUEVA

NIVEL_ALTO = "alto"
NIVEL_MEDIO = "medio"
NIVEL_NEUTRO = "neutro"
NIVEL_FAVORABLE = "favorable"
NIVEL_DESFAVORABLE = "desfavorable"


@dataclass
class Alerta:
    icono: str
    titulo: str
    detalle: str
    nivel: str


@dataclass
class UmbralesAlertas:
    variacion_relevante_pct: float = 30.0
    monto_relevante_nueva: float = 500_000.0
    monto_relevante_discontinuada: float = 500_000.0
    top_n: int = 5


def generar_alertas(
    tabla_vista: pd.DataFrame,
    label_base: str,
    label_comparado: str,
    umbrales: UmbralesAlertas | None = None,
) -> list[Alerta]:
    umbrales = umbrales or UmbralesAlertas()
    col_saldo_base = f"SALDO_{label_base}"
    col_saldo_comparado = f"SALDO_{label_comparado}"

    alertas: list[Alerta] = []
    alertas += _alertas_variacion_fuerte(tabla_vista, umbrales, label_base, label_comparado)
    alertas += _alertas_nuevas(tabla_vista, col_saldo_comparado, umbrales)
    alertas += _alertas_discontinuadas(tabla_vista, col_saldo_base, umbrales)

    return alertas


def _alertas_variacion_fuerte(tabla, umbrales, label_base, label_comparado) -> list[Alerta]:
    pct = tabla["VARIACION_REAL_PCT"]
    filtro = (tabla["ESTADO"] == "EXISTENTE") & pct.notna() & (pct.abs() >= umbrales.variacion_relevante_pct)
    subset = tabla[filtro].reindex(tabla[filtro]["VARIACION_REAL_PCT"].abs().sort_values(ascending=False).index)
    subset = subset.head(umbrales.top_n)

    alertas = []
    for _, row in subset.iterrows():
        var = row["VARIACION_REAL_PCT"]
        icono = "📈" if var >= 0 else "📉"
        signo = "+" if var >= 0 else ""
        tipo = "Gasto" if row["GRUPO"] == "GASTO" else "Ingreso"
        verbo = "subió" if var >= 0 else "bajó"
        alertas.append(
            Alerta(
                icono=icono,
                titulo=f"{tipo} {verbo}: {row['NOMBRE']}",
                detalle=f"{signo}{var:.1f}% de {label_base} a {label_comparado}",
                nivel=NIVEL_FAVORABLE if row["FAVORABLE"] else NIVEL_DESFAVORABLE,
            )
        )
    return alertas


def _alertas_nuevas(tabla, col_saldo_comparado, umbrales) -> list[Alerta]:
    filtro = (tabla["ESTADO"] == ESTADO_NUEVA) & (tabla[col_saldo_comparado].abs() >= umbrales.monto_relevante_nueva)
    subset = tabla[filtro].reindex(tabla[filtro][col_saldo_comparado].abs().sort_values(ascending=False).index)
    subset = subset.head(umbrales.top_n)

    return [
        Alerta(
            icono="📦",
            titulo=f"Cuenta nueva: {row['NOMBRE']}",
            detalle=f"No existía en el período base. Saldo en el período comparado: ${row[col_saldo_comparado]:,.0f}",
            nivel=NIVEL_MEDIO,
        )
        for _, row in subset.iterrows()
    ]


def _alertas_discontinuadas(tabla, col_saldo_base, umbrales) -> list[Alerta]:
    filtro = (tabla["ESTADO"] == ESTADO_DISCONTINUADA) & (tabla[col_saldo_base].abs() >= umbrales.monto_relevante_discontinuada)
    subset = tabla[filtro].reindex(tabla[filtro][col_saldo_base].abs().sort_values(ascending=False).index)
    subset = subset.head(umbrales.top_n)

    return [
        Alerta(
            icono="🗂️",
            titulo=f"Cuenta discontinuada: {row['NOMBRE']}",
            detalle=f"Tenía saldo ${row[col_saldo_base]:,.0f} en el período base, no aparece en el período comparado",
            nivel=NIVEL_MEDIO,
        )
        for _, row in subset.iterrows()
    ]
