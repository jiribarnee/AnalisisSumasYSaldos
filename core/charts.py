"""
charts.py

Genera los gráficos de Plotly para Sumas y Saldos. A diferencia de las
apps de gastos, acá NO tiene sentido un gráfico de "saldo total por
período" (siempre da ~$0, porque en todo balance Debe total = Haber
total). En su lugar, se grafica el total de DEBE y HABER por período
(volumen de movimiento), y las variaciones de saldo por cuenta para el
par elegido.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

COLOR_FONDO = "#0b1220"
COLOR_TEXTO = "#e5eaf3"
COLOR_GRILLA = "#22314a"
COLOR_ACENTO = "#2dd4bf"       # teal/turquesa
COLOR_ACENTO_SUAVE = "#5eead4"
COLOR_SECUNDARIO = "#94a3b8"
COLOR_AMBAR = "#f5b942"
COLOR_ROJO_SUAVE = "#f87171"
COLOR_VERDE = "#4ade80"


def _layout_base(titulo: str) -> dict:
    return dict(
        title=dict(text=titulo, font=dict(size=15, color=COLOR_TEXTO), x=0.02),
        paper_bgcolor=COLOR_FONDO,
        plot_bgcolor=COLOR_FONDO,
        font=dict(color=COLOR_TEXTO, family="Segoe UI, sans-serif", size=12),
        margin=dict(l=50, r=30, t=50, b=40),
        xaxis=dict(gridcolor=COLOR_GRILLA, zerolinecolor=COLOR_GRILLA),
        yaxis=dict(gridcolor=COLOR_GRILLA, zerolinecolor=COLOR_GRILLA),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=COLOR_TEXTO)),
        height=340,
    )


PALETA_LINEAS = ["#2dd4bf", "#f5b942", "#60a5fa", "#f472b6", "#a78bfa", "#4ade80", "#fb923c", "#94a3b8"]


def grafico_gastos_ingresos_por_periodo(
    labels: list[str], gastos: dict, ingresos: dict, label_base: str, label_comparado: str
) -> go.Figure:
    """
    Gastos (cuentas 4010) e ingresos (cuentas 5010) de TODOS los períodos
    cargados, en barras agrupadas. Los dos períodos del par elegido
    quedan a color pleno y el resto atenuado, como contexto.
    """
    opacidad = [1.0 if l in (label_base, label_comparado) else 0.4 for l in labels]
    valores_g = [gastos[l] for l in labels]
    valores_i = [ingresos[l] for l in labels]

    # Con muchos períodos las etiquetas se ponen en vertical (con el monto
    # completo) para que no se encimen.
    muchos = len(labels) > 4
    def _txt(v):
        return f"${v:,.0f}"
    estilo_txt = dict(textangle=-90, constraintext="none", textfont=dict(size=9, color=COLOR_TEXTO)) if muchos else {}
    techo = max(valores_g + valores_i + [0]) * (1.42 if muchos else 1.1)

    fig = go.Figure(
        data=[
            go.Bar(name="Gastos (4010)", x=labels, y=valores_g, marker=dict(color=COLOR_AMBAR, opacity=opacidad),
                   text=[_txt(v) for v in valores_g], textposition="outside", **estilo_txt),
            go.Bar(name="Ingresos (5010)", x=labels, y=valores_i, marker=dict(color=COLOR_ACENTO, opacity=opacidad),
                   text=[_txt(v) for v in valores_i], textposition="outside", **estilo_txt),
        ]
    )
    fig.update_layout(**_layout_base("Gastos e ingresos por período"))
    fig.update_layout(
        yaxis=dict(gridcolor=COLOR_GRILLA, zerolinecolor=COLOR_GRILLA, rangemode="tozero", range=[0, techo]),
        barmode="group",
    )
    return fig


def grafico_top_cuentas_por_saldo(tabla_vista: pd.DataFrame, label_comparado: str, n: int = 10) -> go.Figure:
    """Top N cuentas con mayor saldo (valor absoluto) en el período comparado: gastos en ámbar, ingresos en turquesa."""
    col = f"SALDO_{label_comparado}"
    top = tabla_vista.reindex(tabla_vista[col].abs().sort_values(ascending=False).index).head(n)
    top = top.assign(_monto=top[col].abs()).sort_values("_monto")

    colores = [COLOR_AMBAR if g == "GASTO" else COLOR_ACENTO for g in top["GRUPO"]]

    fig = go.Figure(
        data=[
            go.Bar(
                x=top["_monto"], y=top["NOMBRE"], orientation="h", marker_color=colores,
                text=[f"${v:,.0f}" for v in top["_monto"]], textposition="outside",
            )
        ]
    )
    fig.update_layout(**_layout_base(f"Top {n} cuentas por monto ({label_comparado}) — gastos ámbar, ingresos turquesa"))
    fig.update_layout(height=max(340, n * 34))
    return fig


def grafico_top_variaciones(tabla_vista: pd.DataFrame, label_base: str, label_comparado: str, n: int = 10) -> go.Figure:
    """Top N cuentas con mayor variación entre el par elegido. Verde = favorable (baja un gasto / sube un ingreso), rojo = desfavorable."""
    subset = tabla_vista[tabla_vista["ESTADO"] == "EXISTENTE"].dropna(subset=["VARIACION_REAL_PCT"])
    top = subset.reindex(subset["VARIACION_REAL_PCT"].abs().sort_values(ascending=False).index).head(n)
    top = top.sort_values("VARIACION_REAL_PCT")

    colores = [COLOR_VERDE if f else COLOR_ROJO_SUAVE for f in top["FAVORABLE"]]

    fig = go.Figure(
        data=[
            go.Bar(
                x=top["VARIACION_REAL_PCT"], y=top["NOMBRE"], orientation="h", marker_color=colores,
                text=[f"{v:+.1f}%" for v in top["VARIACION_REAL_PCT"]], textposition="outside",
            )
        ]
    )
    fig.update_layout(**_layout_base(f"Top {n} variaciones: {label_base} → {label_comparado} (verde favorable, rojo desfavorable)"))
    fig.update_layout(height=max(340, n * 34))
    return fig


def grafico_distribucion_estado(tabla_vista: pd.DataFrame) -> go.Figure:
    conteo = tabla_vista["ESTADO"].value_counts()

    etiquetas = {"EXISTENTE": "Existentes", "NUEVA": "Nuevas", "DISCONTINUADA": "Discontinuadas"}
    colores = {"EXISTENTE": COLOR_ACENTO, "NUEVA": COLOR_AMBAR, "DISCONTINUADA": COLOR_SECUNDARIO}

    labels = [etiquetas.get(k, k) for k in conteo.index]
    values = list(conteo.values)
    colors = [colores.get(k, COLOR_SECUNDARIO) for k in conteo.index]

    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels, values=values, marker=dict(colors=colors), hole=0.55,
                textinfo="label+value", textfont=dict(color=COLOR_TEXTO),
            )
        ]
    )
    fig.update_layout(**_layout_base("Cuentas por estado (par seleccionado)"))
    fig.update_layout(showlegend=False)
    return fig


def generar_todos_los_graficos(
    labels: list[str],
    gastos_por_periodo: dict,
    ingresos_por_periodo: dict,
    tabla_vista: pd.DataFrame,
    label_base: str,
    label_comparado: str,
) -> dict[str, go.Figure]:
    return {
        "gastos_ingresos": grafico_gastos_ingresos_por_periodo(
            labels, gastos_por_periodo, ingresos_por_periodo, label_base, label_comparado
        ),
        "distribucion_estado": grafico_distribucion_estado(tabla_vista),
        "top_saldos": grafico_top_cuentas_por_saldo(tabla_vista, label_comparado),
        "top_variaciones": grafico_top_variaciones(tabla_vista, label_base, label_comparado),
    }
