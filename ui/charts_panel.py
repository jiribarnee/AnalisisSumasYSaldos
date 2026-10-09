"""
charts_panel.py

Panel que embebe los gráficos de Plotly dentro de la app usando
QtWebEngine, renderizado 100% local (sin conexión a internet).

La librería plotly.js (~4-5 MB) se escribe UNA SOLA VEZ a un archivo
compartido en disco. Cada actualización (al cambiar el par de
períodos) solo genera el HTML específico de los gráficos (unos pocos
KB) y lo carga vía setHtml(), sin reescribir la librería completa.
"""

from __future__ import annotations

import os
import tempfile

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QVBoxLayout, QWidget

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    WEBENGINE_DISPONIBLE = True
except ImportError:  # pragma: no cover
    WEBENGINE_DISPONIBLE = False

try:
    import plotly.offline as _pyo
    PLOTLY_OFFLINE_DISPONIBLE = True
except ImportError:  # pragma: no cover
    PLOTLY_OFFLINE_DISPONIBLE = False


ORDEN_GRAFICOS = ["gastos_ingresos", "distribucion_estado", "top_saldos", "top_variaciones"]


def build_charts_fragment(graficos: dict, orden: list[str]) -> str:
    """
    Arma solo el fragmento HTML de las tarjetas de gráficos (sin el
    documento completo), para reutilizar tanto en el panel embebido
    como en el reporte imprimible.
    """
    bloques = []
    for key in orden:
        fig = graficos.get(key)
        if fig is None:
            continue
        fragment = fig.to_html(
            include_plotlyjs=False,
            full_html=False,
            config={"displayModeBar": False, "responsive": True},
        )
        bloques.append(f'<div class="chart-card">{fragment}</div>')
    return "\n".join(bloques)


class ChartsPanel(QWidget):
    def __init__(self, graficos: dict, parent=None):
        super().__init__(parent)
        self._temp_dir: str | None = None
        self._plotly_js_listo = False
        self._build_ui(graficos)

    def _build_ui(self, graficos: dict):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if not WEBENGINE_DISPONIBLE:
            from PySide6.QtWidgets import QLabel
            from PySide6.QtCore import Qt

            aviso = QLabel(
                "⚠️ No se encontró QtWebEngine.\n\n"
                "Instalá la dependencia completa de PySide6 para ver los gráficos:\n"
                "pip install PySide6"
            )
            aviso.setAlignment(Qt.AlignCenter)
            aviso.setWordWrap(True)
            layout.addWidget(aviso)
            return

        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view)
        self._asegurar_plotly_js()
        self._render_charts(graficos)

    def _asegurar_plotly_js(self):
        if self._plotly_js_listo:
            return
        self._temp_dir = tempfile.mkdtemp(prefix="analisis_sumas_saldos_charts_")
        plotly_js_path = os.path.join(self._temp_dir, "plotly.min.js")

        js_contenido = _pyo.get_plotlyjs() if PLOTLY_OFFLINE_DISPONIBLE else ""
        with open(plotly_js_path, "w", encoding="utf-8") as f:
            f.write(js_contenido)
        self._plotly_js_listo = True

    def _render_charts(self, graficos: dict):
        html = self._build_combined_html(graficos)
        base_url = QUrl.fromLocalFile(self._temp_dir + os.sep)
        self.web_view.setHtml(html, base_url)

    def _build_combined_html(self, graficos: dict) -> str:
        charts_html = build_charts_fragment(graficos, ORDEN_GRAFICOS)

        return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<script src="plotly.min.js"></script>
<style>
    body {{
        background-color: #0b1220;
        margin: 0;
        padding: 16px;
        font-family: 'Segoe UI', sans-serif;
    }}
    .grid {{
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 16px;
    }}
    .chart-card {{
        background-color: #111a2e;
        border: 1px solid #22314a;
        border-radius: 14px;
        padding: 8px;
        overflow: hidden;
        box-shadow: 0 1px 3px rgba(0,0,0,0.2);
    }}
    .chart-card:first-child {{
        grid-column: 1 / -1;
    }}
</style>
</head>
<body>
    <div class="grid">
        {charts_html}
    </div>
</body>
</html>"""

    def actualizar(self, graficos: dict):
        html = self._build_combined_html(graficos)
        base_url = QUrl.fromLocalFile(self._temp_dir + os.sep)
        self.web_view.setHtml(html, base_url)

    def cleanup(self):
        if self._temp_dir and os.path.isdir(self._temp_dir):
            import shutil

            shutil.rmtree(self._temp_dir, ignore_errors=True)
