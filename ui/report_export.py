"""
report_export.py

Genera un reporte imprimible (resumen + tabla + gráficos — SIN el
panel de alertas, por pedido explícito) y lo exporta a PDF usando
QtWebEngine (que ya sabe renderizar los mismos gráficos de Plotly que
se ven en la pestaña "Gráficos").

Flujo:
    1. Se arma un único HTML con: título, tarjetas de resumen, tabla
       completa, y los gráficos (reutilizando plotly.min.js ya escrito
       en disco por ChartsPanel, para no duplicar los ~5 MB de la
       librería).
    2. Se carga ese HTML en un QWebEngineView oculto.
    3. Una vez que termina de cargar (loadFinished), se llama a
       printToPdf() para generar el archivo.
    4. Al terminar (pdfPrintingFinished), se abre el PDF con la
       aplicación predeterminada del sistema, para que desde ahí el
       usuario lo imprima (Cmd/Ctrl+P) o lo guarde donde quiera.
"""

from __future__ import annotations

import re

import os

from PySide6.QtCore import QUrl, QTimer, QMarginsF
from PySide6.QtGui import QDesktopServices, QPageLayout, QPageSize
from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    WEBENGINE_DISPONIBLE = True
except ImportError:  # pragma: no cover
    WEBENGINE_DISPONIBLE = False

from core.calculations import formato_moneda, formato_porcentaje


class ReportExporter:
    """
    Maneja el ciclo de vida de exportar un reporte a PDF: pedir dónde
    guardarlo, renderizar el HTML oculto, exportar, y abrir el
    resultado. Se instancia una vez por exportación (no se reutiliza).
    """

    def __init__(self, parent: QWidget, plotly_temp_dir: str):
        self._parent = parent
        self._plotly_temp_dir = plotly_temp_dir
        self._hidden_view: QWebEngineView | None = None
        self._output_path: str | None = None

    def exportar(self, html: str, nombre_sugerido: str):
        if not WEBENGINE_DISPONIBLE:
            QMessageBox.warning(
                self._parent, "No disponible",
                "No se encontró QtWebEngine, necesario para generar el PDF."
            )
            return

        path, _ = QFileDialog.getSaveFileName(
            self._parent, "Guardar reporte como PDF", nombre_sugerido, "Archivos PDF (*.pdf)"
        )
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        self._output_path = path

        # Vista oculta: no se agrega a ningún layout visible, solo se
        # usa como "hoja de render" para generar el PDF.
        self._hidden_view = QWebEngineView()
        self._hidden_view.resize(1200, 1600)
        self._hidden_view.page().pdfPrintingFinished.connect(self._on_pdf_finished)
        self._hidden_view.loadFinished.connect(self._on_load_finished)

        base_url = QUrl.fromLocalFile(self._plotly_temp_dir + os.sep)
        self._hidden_view.setHtml(html, base_url)

    def _on_load_finished(self, ok: bool):
        if not ok or self._hidden_view is None or self._output_path is None:
            QMessageBox.warning(self._parent, "No se pudo generar el PDF", "Falló la carga del reporte.")
            return
        # Apaisado (horizontal): el reporte tiene tablas y gráficos anchos,
        # que se cortarían con el ancho angosto de una hoja A4 vertical.
        page_layout = QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Landscape, QMarginsF(12, 12, 12, 12))
        self._hidden_view.page().printToPdf(self._output_path, page_layout)

    def _on_pdf_finished(self, path: str, success: bool):
        if success:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        else:
            QMessageBox.warning(self._parent, "No se pudo generar el PDF", "Ocurrió un error al exportar.")
        # Esperar un instante antes de liberar la vista oculta: Chromium
        # sigue haciendo limpieza interna justo después de terminar el
        # PDF, y borrarla en el instante mismo de la señal puede crashear.
        if self._hidden_view is not None:
            vista = self._hidden_view
            self._hidden_view = None
            QTimer.singleShot(300, vista.deleteLater)


# Máximo de columnas de períodos por bloque de tabla en el PDF. Con más
# períodos la tabla se parte en bloques (repitiendo las columnas de
# identificación), así los montos se imprimen completos y legibles.
MAX_PERIODOS_POR_BLOQUE = 6


def _bloques_columnas(n_cols: int, n_ini: int, n_fin: int, max_periodos: int = MAX_PERIODOS_POR_BLOQUE) -> list[list[int]]:
    """Índices de columnas de cada bloque: fijas iniciales + trozo de períodos (+ fijas finales en el último)."""
    medio = list(range(n_ini, n_cols - n_fin))
    if len(medio) <= max_periodos:
        return [list(range(n_cols))]
    k = -(-len(medio) // max_periodos)      # cantidad de bloques
    tam = -(-len(medio) // k)                           # tamaño parejo
    trozos = [medio[i:i + tam] for i in range(0, len(medio), tam)]
    ini = list(range(n_ini))
    fin = list(range(n_cols - n_fin, n_cols))
    bloques = [ini + t for t in trozos]
    bloques[-1] = bloques[-1] + fin
    return bloques


def construir_html_reporte(
    titulo_app: str,
    subtitulo_periodo: str,
    tarjetas: list[tuple[str, str, str]],  # (etiqueta, valor, color_hex)
    tabla_headers: list[str],
    tabla_filas: list[list[str]],
    graficos_html: str,
    color_fondo: str,
    color_texto: str,
    color_borde: str,
    color_acento: str,
    n_fijas_inicio: int = 1,
    n_fijas_fin: int = 3,
    max_periodos_por_bloque: int = MAX_PERIODOS_POR_BLOQUE,
) -> str:
    """
    Arma el HTML completo del reporte: título, tarjetas, tabla y
    gráficos ya renderizados (graficos_html viene armado por el
    llamador, reutilizando las figuras de Plotly de core/charts.py).

    NO incluye alertas, por pedido explícito.
    """
    tarjetas_html = "\n".join(
        f'''<div class="card">
                <div class="card-label">{etiqueta}</div>
                <div class="card-value" style="color:{color};">{valor}</div>
            </div>'''
        for etiqueta, valor, color in tarjetas
    )

    bloques = _bloques_columnas(len(tabla_headers), n_fijas_inicio, n_fijas_fin, max_periodos_por_bloque)
    tablas_html = []
    for i, cols in enumerate(bloques):
        head = "".join(f"<th>{tabla_headers[c]}</th>" for c in cols)
        body = "\n".join(
            "<tr>" + "".join(f"<td>{fila[c]}</td>" for c in cols) + "</tr>"
            for fila in tabla_filas
        )
        clase = ' class="bloque-nuevo"' if i > 0 else ""
        tablas_html.append(f"<table{clase}><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>")
    tablas_html = "\n".join(tablas_html)
    n_cols_bloque = len(bloques[0])
    tamano_tabla = "12px" if n_cols_bloque <= 8 else "10px" if n_cols_bloque <= 11 else "9px" if n_cols_bloque <= 13 else "8px"
    nombre_izq = "th:nth-child(2), td:nth-child(2) { text-align: left; }" if n_fijas_inicio >= 2 else ""
    padding_celda = "4px 8px" if n_cols_bloque <= 11 else "4px 4px"

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<script src="plotly.min.js"></script>
<style>
    body {{
        background-color: {color_fondo};
        color: {color_texto};
        margin: 0;
        padding: 24px;
        font-family: 'Segoe UI', sans-serif;
    }}
    h1 {{ font-size: 20px; margin: 0 0 4px; }}
    .subtitulo {{ font-size: 13px; color: {color_texto}; opacity: 0.7; margin: 0 0 20px; }}
    .cards {{ display: flex; gap: 12px; margin-bottom: 24px; flex-wrap: wrap; }}
    .card {{
        background: rgba(128,128,128,0.08);
        border: 1px solid {color_borde};
        border-radius: 10px;
        padding: 10px 14px;
        min-width: 190px;
        flex: 1 1 190px;
    }}
    .cards.pocas .card {{ max-width: 440px; flex: 0 1 440px; padding: 16px 22px; }}
    .cards.pocas .card-label {{ font-size: 12px; }}
    .cards.pocas .card-value {{ font-size: 26px; }}
    .card-label {{ font-size: 10px; text-transform: uppercase; opacity: 0.7; margin-bottom: 4px; white-space: nowrap; }}
    .card-value {{ font-size: 15px; font-weight: 700; white-space: nowrap; }}
    table {{ width: 100%; border-collapse: collapse; margin-bottom: 28px; font-size: {tamano_tabla}; }}
    table.bloque-nuevo {{ page-break-before: always; break-before: page; }}
    tr {{ page-break-inside: avoid; }}
    th, td {{ padding: {padding_celda}; border-bottom: 1px solid {color_borde}; text-align: right; }}
    th:first-child, td:first-child {{ text-align: left; }}
    {nombre_izq}
    th {{ text-transform: uppercase; font-size: 10px; opacity: 0.7; border-bottom: 2px solid {color_acento}; }}
    .grid {{
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 16px;
        page-break-before: always;
        break-before: page;
    }}
    .chart-card {{
        background: rgba(128,128,128,0.05);
        border: 1px solid {color_borde};
        border-radius: 10px;
        padding: 8px;
        overflow: hidden;
    }}
    .chart-card:first-child {{ grid-column: 1 / -1; }}
</style>
</head>
<body>
    <h1>{titulo_app}</h1>
    <p class="subtitulo">{subtitulo_periodo}</p>
    <div class="cards{" pocas" if len(tarjetas) <= 3 else ""}">{tarjetas_html}</div>
    {tablas_html}
    <div class="grid">
        {graficos_html}
    </div>
</body>
</html>"""
