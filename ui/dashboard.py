"""
dashboard.py

Pantalla de resultados, con selector de PAR DE PERÍODOS (igual
filosofía que Análisis de Compras por Concepto, adaptada a cuentas
contables):
    - El usuario elige "Período base" y "Período comparado".
    - Tarjetas, columna DIFERENCIA/VARIACIÓN/ESTADO de la tabla, panel
      de alertas y gráficos se recalculan según el par elegido.
    - La tabla siempre muestra, además, una columna de saldo por CADA
      período cargado.
    - Doble clic en una fila abre el detalle de la cuenta.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.alerts import generar_alertas
from core.calculations import formato_moneda, formato_porcentaje, ordenar_cronologico
from core.charts import generar_todos_los_graficos
from core.comparator import (
    ComparisonResult,
    ESTADO_DISCONTINUADA,
    ESTADO_NUEVA,
    calcular_metricas_par,
    resumen_par,
)
from ui.alerts_panel import AlertsPanel
from ui.charts_panel import ChartsPanel, ORDEN_GRAFICOS, build_charts_fragment
from ui.report_export import ReportExporter, construir_html_reporte
from ui.detail_dialog import CategoryDetailDialog

FILTRO_TODOS = "Todas"
FILTRO_EXISTENTES = "Existentes"
FILTRO_NUEVAS = "Nuevas"
FILTRO_DISCONTINUADAS = "Discontinuadas"

_FILTRO_A_ESTADO = {
    FILTRO_EXISTENTES: "EXISTENTE",
    FILTRO_NUEVAS: ESTADO_NUEVA,
    FILTRO_DISCONTINUADAS: ESTADO_DISCONTINUADA,
}


class SummaryCard(QFrame):
    def __init__(self, titulo: str, valor: str, variante: str = "neutral", parent=None):
        super().__init__(parent)
        self.setObjectName("summaryCard")
        self.setProperty("variant", variante)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(6)

        titulo_label = QLabel(titulo)
        titulo_label.setObjectName("cardTitle")
        layout.addWidget(titulo_label)

        valor_label = QLabel(valor)
        valor_label.setObjectName("cardValue")
        valor_label.setProperty("variant", variante)
        layout.addWidget(valor_label)

        self._titulo_label = titulo_label
        self._valor_label = valor_label

    def actualizar(self, titulo: str, valor: str, variante: str = "neutral"):
        self._titulo_label.setText(titulo)
        self._valor_label.setText(valor)
        self._valor_label.setProperty("variant", variante)
        self._valor_label.style().unpolish(self._valor_label)
        self._valor_label.style().polish(self._valor_label)


class DashboardPage(QWidget):
    def __init__(self, resultado: ComparisonResult, on_volver, parent=None):
        super().__init__(parent)
        self.resultado = resultado
        self._on_volver = on_volver
        self._charts_panel: ChartsPanel | None = None
        self._alerts_panel: AlertsPanel | None = None
        self._alertas_visibles = True
        self._content_row: QHBoxLayout | None = None

        labels = resultado.labels
        self._label_base = labels[-2] if len(labels) >= 2 else labels[0]
        self._label_comparado = labels[-1]

        self._build_ui()
        self._recalcular_vista()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        root.addLayout(self._build_header())
        root.addLayout(self._build_selector_par())

        # Fila 1: saldos de gastos (4010), ingresos (5010) y resultado.
        self._cards_row = QHBoxLayout()
        self._cards_row.setSpacing(14)
        self._card_gastos_base = SummaryCard("GASTOS (4010)", "-")
        self._card_gastos_comparado = SummaryCard("GASTOS (4010)", "-")
        self._card_ingresos_base = SummaryCard("INGRESOS (5010)", "-")
        self._card_ingresos_comparado = SummaryCard("INGRESOS (5010)", "-")
        self._card_resultado = SummaryCard("RESULTADO", "-")
        for card in (self._card_gastos_base, self._card_gastos_comparado, self._card_ingresos_base,
                     self._card_ingresos_comparado, self._card_resultado):
            self._cards_row.addWidget(card)
        root.addLayout(self._cards_row)

        # Fila 2: variaciones y cuentas nuevas/discontinuadas.
        self._cards_row2 = QHBoxLayout()
        self._cards_row2.setSpacing(14)
        self._card_var_gastos = SummaryCard("VARIACIÓN GASTOS", "-")
        self._card_var_ingresos = SummaryCard("VARIACIÓN INGRESOS", "-")
        self._card_nuevas = SummaryCard("CUENTAS NUEVAS", "-", variante="positivo")
        self._card_discontinuadas = SummaryCard("CUENTAS DISCONTINUADAS", "-", variante="negativo")
        for card in (self._card_var_gastos, self._card_var_ingresos, self._card_nuevas, self._card_discontinuadas):
            self._cards_row2.addWidget(card)
        root.addLayout(self._cards_row2)

        self._tabs = QTabWidget()
        self._tabs.setObjectName("mainTabs")
        self._tabs.addTab(self._build_resumen_tab(), "📋 Resumen")
        self._tabs.addTab(self._build_graficos_tab(), "📈 Gráficos")
        root.addWidget(self._tabs, stretch=1)

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()

        labels = self.resultado.labels
        if len(labels) <= 4:
            rango_txt = " vs ".join(labels)
        else:
            rango_txt = f"{labels[0]} … {labels[-1]} ({len(labels)} períodos)"

        titulo = QLabel(f"📊 SUMAS Y SALDOS — {rango_txt}")
        titulo.setObjectName("dashboardTitle")
        titulo.setWordWrap(True)
        header.addWidget(titulo, stretch=1)

        volver_btn = QPushButton("← Nuevo análisis")
        volver_btn.setObjectName("secondaryButton")
        volver_btn.setCursor(Qt.PointingHandCursor)
        volver_btn.clicked.connect(self._handle_volver)
        header.addWidget(volver_btn)

        imprimir_btn = QPushButton("🖨️ Imprimir")
        imprimir_btn.setObjectName("secondaryButton")
        imprimir_btn.setCursor(Qt.PointingHandCursor)
        imprimir_btn.clicked.connect(self._handle_imprimir)
        header.addWidget(imprimir_btn)

        return header

    def _build_selector_par(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)

        icono = QLabel("🔀")
        row.addWidget(icono)

        label_comparar = QLabel("Comparar:")
        label_comparar.setObjectName("smallLabel")
        row.addWidget(label_comparar)

        self.combo_base = QComboBox()
        self.combo_base.addItems(self.resultado.labels)
        self.combo_base.setCurrentText(self._label_base)
        self.combo_base.currentTextChanged.connect(self._on_par_changed)
        row.addWidget(self.combo_base)

        flecha = QLabel("→")
        flecha.setObjectName("smallLabel")
        row.addWidget(flecha)

        self.combo_comparado = QComboBox()
        self.combo_comparado.addItems(self.resultado.labels)
        self.combo_comparado.setCurrentText(self._label_comparado)
        self.combo_comparado.currentTextChanged.connect(self._on_par_changed)
        row.addWidget(self.combo_comparado)

        nota = QLabel("(afecta variación, alertas y gráficos de comparación — la tabla siempre muestra todos los períodos)")
        nota.setObjectName("smallLabel")
        nota.setWordWrap(True)
        row.addWidget(nota, stretch=1)

        return row

    def _build_resumen_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 14, 0, 0)
        layout.setSpacing(14)

        layout.addLayout(self._build_filter_bar())

        self._content_row = QHBoxLayout()
        self._content_row.setSpacing(16)
        self._content_row.addWidget(self._build_table(), stretch=1)

        self._alerts_panel = AlertsPanel([])
        self._alerts_panel.setFixedWidth(300)
        self._content_row.addWidget(self._alerts_panel)

        layout.addLayout(self._content_row, stretch=1)
        return tab

    def _build_graficos_tab(self) -> QWidget:
        self._graficos_tab = QWidget()
        self._graficos_tab_layout = QVBoxLayout(self._graficos_tab)
        self._graficos_tab_layout.setContentsMargins(0, 14, 0, 0)
        return self._graficos_tab

    def _build_filter_bar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)

        label = QLabel("🔎")
        row.addWidget(label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar cuenta contable...")
        self.search_input.setObjectName("searchInput")
        self.search_input.textChanged.connect(self._apply_filters)
        row.addWidget(self.search_input, stretch=1)

        estado_label = QLabel("Estado:")
        estado_label.setObjectName("smallLabel")
        row.addWidget(estado_label)

        self.estado_filter = QComboBox()
        self.estado_filter.addItems([FILTRO_TODOS, FILTRO_EXISTENTES, FILTRO_NUEVAS, FILTRO_DISCONTINUADAS])
        self.estado_filter.currentTextChanged.connect(self._apply_filters)
        row.addWidget(self.estado_filter)

        self.result_count_label = QLabel("")
        self.result_count_label.setObjectName("smallLabel")
        row.addWidget(self.result_count_label)

        self.alertas_toggle_btn = QPushButton("🔔 Ocultar alertas")
        self.alertas_toggle_btn.setObjectName("secondaryButton")
        self.alertas_toggle_btn.setCursor(Qt.PointingHandCursor)
        self.alertas_toggle_btn.clicked.connect(self._toggle_alertas)
        row.addWidget(self.alertas_toggle_btn)

        return row

    def _build_table(self) -> QTableWidget:
        labels = self.resultado.labels
        self.col_saldos = [f"SALDO_{label}" for label in labels]

        headers = ["CUENTA", "NOMBRE"] + [f"SALDO {label}" for label in labels] + ["DIFERENCIA", "VARIACIÓN", "ESTADO"]

        table = QTableWidget()
        table.setObjectName("resultsTable")
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(False)
        table.horizontalHeader().setMinimumSectionSize(90)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        table.setColumnWidth(0, 110)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        table.setColumnWidth(1, 220)
        for col in range(2, len(headers)):
            table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        table.cellDoubleClicked.connect(self._handle_row_double_click)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.table = table
        return table

    def _on_par_changed(self, *_args):
        self._label_base = self.combo_base.currentText()
        self._label_comparado = self.combo_comparado.currentText()
        self._recalcular_vista()

    def _recalcular_vista(self):
        self._tabla_vista = calcular_metricas_par(self.resultado.tabla, self._label_base, self._label_comparado)
        self._resumen_vista = resumen_par(self._tabla_vista, self._label_base, self._label_comparado)

        self._actualizar_cards()
        self._apply_filters()
        self._actualizar_alertas()
        self._actualizar_graficos()

    def _actualizar_cards(self):
        r = self._resumen_vista
        base, comp = r["periodo_base"], r["periodo_comparado"]

        self._card_gastos_base.actualizar(f"GASTOS (4010) {base}", formato_moneda(r["gastos_base"]))
        self._card_gastos_comparado.actualizar(f"GASTOS (4010) {comp}", formato_moneda(r["gastos_comparado"]))
        self._card_ingresos_base.actualizar(f"INGRESOS (5010) {base}", formato_moneda(r["ingresos_base"]))
        self._card_ingresos_comparado.actualizar(f"INGRESOS (5010) {comp}", formato_moneda(r["ingresos_comparado"]))

        resultado = r["resultado_comparado"]
        self._card_resultado.actualizar(
            f"RESULTADO {comp} (ingresos − gastos)", formato_moneda(resultado),
            variante="positivo" if resultado >= 0 else "negativo",
        )

        vg, vi = r["variacion_gastos_pct"], r["variacion_ingresos_pct"]
        # Gastos: subir es desfavorable. Ingresos: subir es favorable.
        self._card_var_gastos.actualizar(
            "VARIACIÓN GASTOS", formato_porcentaje(vg),
            variante="neutral" if not vg else ("negativo" if vg > 0 else "positivo"),
        )
        self._card_var_ingresos.actualizar(
            "VARIACIÓN INGRESOS", formato_porcentaje(vi),
            variante="neutral" if not vi else ("positivo" if vi > 0 else "negativo"),
        )

        self._card_nuevas.actualizar("CUENTAS NUEVAS", str(r["cant_cuentas_nuevas"]), variante="positivo")
        self._card_discontinuadas.actualizar(
            "CUENTAS DISCONTINUADAS", str(r["cant_cuentas_discontinuadas"]), variante="negativo"
        )

    def _actualizar_alertas(self):
        alertas = generar_alertas(self._tabla_vista, self._label_base, self._label_comparado)
        nuevo_panel = AlertsPanel(alertas)
        nuevo_panel.setFixedWidth(300)
        nuevo_panel.setVisible(self._alertas_visibles)

        if self._alerts_panel is not None:
            self._content_row.replaceWidget(self._alerts_panel, nuevo_panel)
            self._alerts_panel.setParent(None)
            self._alerts_panel.deleteLater()
        else:
            self._content_row.addWidget(nuevo_panel)
        self._alerts_panel = nuevo_panel

    def _toggle_alertas(self):
        self._alertas_visibles = not self._alertas_visibles
        if self._alerts_panel is not None:
            self._alerts_panel.setVisible(self._alertas_visibles)
        texto = "🔔 Ocultar alertas" if self._alertas_visibles else "🔕 Ver alertas"
        self.alertas_toggle_btn.setText(texto)

    def _actualizar_graficos(self):
        graficos = generar_todos_los_graficos(
            self.resultado.labels,
            self.resultado.resumen["gastos_por_periodo"],
            self.resultado.resumen["ingresos_por_periodo"],
            self._tabla_vista,
            self._label_base,
            self._label_comparado,
        )

        if self._charts_panel is not None:
            self._charts_panel.actualizar(graficos)
        else:
            self._charts_panel = ChartsPanel(graficos)
            self._graficos_tab_layout.addWidget(self._charts_panel)

    def _populate_table(self, df):
        self._current_df = df.reset_index(drop=True)
        self.table.setRowCount(len(df))
        n_periodos = len(self.col_saldos)

        for row_idx, (_, row) in enumerate(self._current_df.iterrows()):
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(row["CUENTA"])))
            self.table.setItem(row_idx, 1, QTableWidgetItem(str(row["NOMBRE"])))

            for i, col_saldo in enumerate(self.col_saldos):
                self.table.setItem(row_idx, 2 + i, _numeric_item(formato_moneda(row[col_saldo])))

            diferencia = row["DIFERENCIA"]
            variacion = row["VARIACION_PCT"]
            estado = row["ESTADO"]

            diff_item = _numeric_item(formato_moneda(diferencia))
            diff_item.setForeground(_color_por_valor(diferencia))
            self.table.setItem(row_idx, 2 + n_periodos, diff_item)

            var_item = _numeric_item(formato_porcentaje(variacion))
            var_item.setForeground(_color_por_valor(variacion))
            self.table.setItem(row_idx, 3 + n_periodos, var_item)

            estado_item = QTableWidgetItem(_estado_texto(estado))
            estado_item.setTextAlignment(Qt.AlignCenter)
            estado_item.setForeground(_color_por_estado(estado))
            self.table.setItem(row_idx, 4 + n_periodos, estado_item)

        self.result_count_label.setText(f"{len(df)} cuentas")

    def _apply_filters(self, *_args):
        texto = self.search_input.text().strip().lower()
        filtro_estado = self.estado_filter.currentText()

        df = self._tabla_vista
        if texto:
            df = df[
                df["NOMBRE"].str.lower().str.contains(texto, na=False)
                | df["CUENTA"].str.lower().str.contains(texto, na=False)
            ]
        if filtro_estado != FILTRO_TODOS:
            estado_valor = _FILTRO_A_ESTADO[filtro_estado]
            df = df[df["ESTADO"] == estado_valor]

        self._populate_table(df)

    def _handle_row_double_click(self, row_idx: int, _col_idx: int):
        if row_idx < 0 or row_idx >= len(self._current_df):
            return
        row = self._current_df.iloc[row_idx]
        dialog = CategoryDetailDialog(row, self.resultado, self._label_base, self._label_comparado, parent=self)
        dialog.exec()

    def _handle_volver(self):
        if self._charts_panel is not None:
            self._charts_panel.cleanup()
        self._on_volver()

    def _handle_imprimir(self):
        resumen = self.resultado.resumen
        n_per = len(self.resultado.labels)
        # Arriba del PDF solo van los totales de todos los períodos cargados.
        tarjetas = [
            (f"GASTOS TOTALES — 4010 ({n_per} períodos)", formato_moneda(sum(resumen["gastos_por_periodo"].values())), "#f4f7fb"),
            (f"INGRESOS TOTALES — 5010 ({n_per} períodos)", formato_moneda(sum(resumen["ingresos_por_periodo"].values())), "#f4f7fb"),
        ]

        def _num(v):
            return 0.0 if v is None or v != v else float(v)

        def _m(v):
            """Monto en millones con 3 decimales, estilo argentino: 501100211.19 -> $501,100M"""
            texto = f"{v / 1_000_000:,.3f}".replace(",", "␟").replace(".", ",").replace("␟", ".")
            return f"${texto}M"

        # Períodos del más antiguo al más nuevo (por fecha), sin importar el orden de carga.
        labels_orden = ordenar_cronologico(self.resultado.labels)
        cols_orden = [f"SALDO_{l}" for l in labels_orden]

        headers = ["Cuenta", "Nombre"] + [f"Saldo {l}" for l in labels_orden] + ["Total"]
        # Primero todas las cuentas 4010 (gastos) y después todas las 5010 (ingresos),
        # cada bloque con su fila de total. Dentro de cada bloque van ordenadas por número de cuenta.
        etiquetas = {"GASTO": "GASTOS (4010)", "INGRESO": "INGRESOS (5010) — saldo acreedor"}
        filas = []
        for g in ("GASTO", "INGRESO"):
            sub = self._current_df[self._current_df["GRUPO"] == g].sort_values("CUENTA", key=lambda c: c.astype(str))
            if sub.empty:
                continue
            acum = [0.0] * len(cols_orden)
            for _, row in sub.iterrows():
                valores = [_num(row[c]) for c in cols_orden]
                for i, v in enumerate(valores):
                    acum[i] += v
                filas.append(
                    [str(row["CUENTA"]), str(row["NOMBRE"])]
                    + [_m(v) for v in valores]
                    + [f"<b>{_m(sum(valores))}</b>"]
                )
            filas.append(
                ["<b>TOTAL</b>", f"<b>{etiquetas[g]}</b>"]
                + [f"<b>{_m(v)}</b>" for v in acum]
                + [f"<b>{_m(sum(acum))}</b>"]
            )

        graficos = generar_todos_los_graficos(
            labels_orden, resumen["gastos_por_periodo"], resumen["ingresos_por_periodo"],
            self._tabla_vista, self._label_base, self._label_comparado,
        )
        # En el PDF va solo el gráfico de gastos e ingresos por período.
        graficos["gastos_ingresos"].update_layout(autosize=False, width=900, height=480)
        graficos_html = build_charts_fragment(graficos, ["gastos_ingresos"])

        rango_txt = " → ".join(labels_orden) if n_per <= 4 else f"{labels_orden[0]} … {labels_orden[-1]} ({n_per} períodos)"

        html = construir_html_reporte(
            titulo_app="📊 Análisis Mensual de Sumas y Saldos",
            subtitulo_periodo=f"{rango_txt} — tabla en millones de pesos (M)",
            tarjetas=tarjetas,
            tabla_headers=headers,
            tabla_filas=filas,
            graficos_html=graficos_html,
            color_fondo="#0b1220",
            color_texto="#e5eaf3",
            color_borde="#22314a",
            color_acento="#2dd4bf",
            n_fijas_inicio=2,
            n_fijas_fin=1,
            max_periodos_por_bloque=12,
        )

        if self._charts_panel is None or self._charts_panel._temp_dir is None:
            return
        exporter = ReportExporter(self, self._charts_panel._temp_dir)
        exporter.exportar(html, "reporte_sumas_y_saldos.pdf")
        self._report_exporter = exporter


def _numeric_item(texto: str) -> QTableWidgetItem:
    item = QTableWidgetItem(texto)
    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return item


def _color_por_valor(valor):
    from PySide6.QtGui import QColor

    if valor is None or (isinstance(valor, float) and valor != valor):
        return QColor("#7d8ba1")
    if valor > 0:
        return QColor("#2dd4bf")
    if valor < 0:
        return QColor("#f87171")
    return QColor("#7d8ba1")


def _color_por_estado(estado: str):
    from PySide6.QtGui import QColor

    if estado == ESTADO_NUEVA:
        return QColor("#2dd4bf")
    if estado == ESTADO_DISCONTINUADA:
        return QColor("#f87171")
    return QColor("#7d8ba1")


def _estado_texto(estado: str) -> str:
    return {
        ESTADO_NUEVA: "🆕 NUEVA",
        ESTADO_DISCONTINUADA: "🗂️ DISCONTINUADA",
    }.get(estado, "—")
