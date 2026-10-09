"""
detail_dialog.py

Diálogo que se abre al hacer doble clic sobre una fila de la tabla del
dashboard. Muestra:
    - El saldo de esa cuenta en CADA período cargado (2 a 12), con los
      dos períodos elegidos para comparar resaltados.
    - Un selector propio de "Período base" / "Período comparado"
      (arranca con el mismo par activo en el dashboard).
    - Diferencia, variación, y el detalle de Debe/Haber del período
      comparado (el movimiento del mes, no un acumulado).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
)

from core.calculations import formato_moneda, formato_porcentaje, variacion_absoluta, variacion_porcentual
from core.comparator import ComparisonResult, ESTADO_DISCONTINUADA, ESTADO_NUEVA


class CategoryDetailDialog(QDialog):
    def __init__(self, row, resultado: ComparisonResult, label_base: str, label_comparado: str, parent=None):
        super().__init__(parent)
        self._row = row
        self._resultado = resultado
        self._label_base = label_base
        self._label_comparado = label_comparado

        self.setWindowTitle(f"Detalle — {row['NOMBRE']}")
        self.setMinimumWidth(560)
        self.setMinimumHeight(480)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        titulo = QLabel(f"📒 {self._row['NOMBRE']}")
        titulo.setStyleSheet("font-size: 18px; font-weight: 800; color: #f4f7fb;")
        titulo.setWordWrap(True)
        layout.addWidget(titulo)

        cuenta_label = QLabel(f"Cuenta: {self._row['CUENTA']}")
        cuenta_label.setStyleSheet("color: #7d8ba1; font-size: 11px;")
        layout.addWidget(cuenta_label)

        layout.addLayout(self._build_selector_par())

        self._estado_label = QLabel()
        self._estado_label.setStyleSheet("font-weight: 700; font-size: 12px;")
        layout.addWidget(self._estado_label)

        self._serie_container_holder = QVBoxLayout()
        layout.addLayout(self._serie_container_holder)

        separador = QFrame()
        separador.setFrameShape(QFrame.HLine)
        separador.setStyleSheet("background-color: #22314a; max-height: 1px; border: none;")
        layout.addWidget(separador)

        self._resumen_container_holder = QVBoxLayout()
        self._resumen_container_holder.setSpacing(8)
        layout.addLayout(self._resumen_container_holder)

        self._separador2 = QFrame()
        self._separador2.setFrameShape(QFrame.HLine)
        self._separador2.setStyleSheet("background-color: #22314a; max-height: 1px; border: none;")
        layout.addWidget(self._separador2)

        self._movimiento_titulo = QLabel()
        self._movimiento_titulo.setStyleSheet("font-weight: 800; font-size: 13px; color: #cbd5e1;")
        self._movimiento_titulo.setWordWrap(True)
        layout.addWidget(self._movimiento_titulo)

        self._movimiento_container_holder = QVBoxLayout()
        layout.addLayout(self._movimiento_container_holder)

        cerrar_btn = QPushButton("Cerrar")
        cerrar_btn.setCursor(Qt.PointingHandCursor)
        cerrar_btn.setStyleSheet(
            "background-color: #1c2c47; border: none; border-radius: 9px; "
            "padding: 10px; color: #f4f7fb; font-weight: 700;"
        )
        cerrar_btn.clicked.connect(self.accept)
        layout.addWidget(cerrar_btn)

        self._refrescar_contenido()

    def _build_selector_par(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        icono = QLabel("🔀")
        row.addWidget(icono)

        label = QLabel("Comparar:")
        label.setStyleSheet("color: #7d8ba1; font-size: 12px;")
        row.addWidget(label)

        self.combo_base = QComboBox()
        self.combo_base.addItems(self._resultado.labels)
        self.combo_base.setCurrentText(self._label_base)
        self.combo_base.currentTextChanged.connect(self._on_par_changed)
        row.addWidget(self.combo_base)

        flecha = QLabel("→")
        flecha.setStyleSheet("color: #7d8ba1;")
        row.addWidget(flecha)

        self.combo_comparado = QComboBox()
        self.combo_comparado.addItems(self._resultado.labels)
        self.combo_comparado.setCurrentText(self._label_comparado)
        self.combo_comparado.currentTextChanged.connect(self._on_par_changed)
        row.addWidget(self.combo_comparado)

        row.addStretch()
        return row

    def _on_par_changed(self, *_args):
        self._label_base = self.combo_base.currentText()
        self._label_comparado = self.combo_comparado.currentText()
        self._refrescar_contenido()

    def _refrescar_contenido(self):
        row = self._row
        label_base = self._label_base
        label_comparado = self._label_comparado

        col_saldo_base = f"SALDO_{label_base}"
        col_saldo_comparado = f"SALDO_{label_comparado}"
        col_presente_base = f"_PRESENTE_{label_base}"
        col_presente_comparado = f"_PRESENTE_{label_comparado}"

        valor_base = row.get(col_saldo_base, 0.0) or 0.0
        valor_comparado = row.get(col_saldo_comparado, 0.0) or 0.0
        presente_base = bool(row.get(col_presente_base, False))
        presente_comparado = bool(row.get(col_presente_comparado, False))

        estado = _estado_para_par(presente_base, presente_comparado)
        estado_txt, estado_color = _estado_visual(estado)
        self._estado_label.setText(estado_txt)
        self._estado_label.setStyleSheet(f"font-weight: 700; font-size: 12px; color: {estado_color};")

        _limpiar_layout(self._serie_container_holder)
        self._serie_container_holder.addWidget(self._build_serie_periodos(row, label_base, label_comparado))

        _limpiar_layout(self._resumen_container_holder)
        diferencia = variacion_absoluta(valor_base, valor_comparado)
        variacion = variacion_porcentual(valor_base, valor_comparado)
        self._resumen_container_holder.addWidget(
            self._metric_line("💰", f"Diferencia de saldo ({label_base} → {label_comparado})", formato_moneda(diferencia), diferencia)
        )
        self._resumen_container_holder.addWidget(
            self._metric_line("📈", "Variación", formato_porcentaje(variacion), variacion)
        )

        movimiento = self._build_movimiento(row, label_comparado)
        _limpiar_layout(self._movimiento_container_holder)
        if movimiento is not None:
            self._movimiento_titulo.setText(f"🧾 Movimiento del período ({label_comparado})")
            self._movimiento_titulo.setVisible(True)
            self._separador2.setVisible(True)
            self._movimiento_container_holder.addWidget(movimiento)
        else:
            self._movimiento_titulo.setVisible(False)
            self._separador2.setVisible(False)

    def _build_serie_periodos(self, row, label_base, label_comparado):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setMaximumHeight(150)

        container = QFrame()
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(4)
        container_layout.setContentsMargins(0, 0, 4, 0)

        for label in self._resultado.labels:
            presente = bool(row.get(f"_PRESENTE_{label}", False))
            valor = row.get(f"SALDO_{label}", 0.0)
            es_seleccionado = label in (label_base, label_comparado)

            fila = QFrame()
            fila.setObjectName("metricBlock" if es_seleccionado else "")
            fila_layout = QHBoxLayout(fila)
            fila_layout.setContentsMargins(10, 6, 10, 6)

            peso = "800" if es_seleccionado else "500"
            nombre_label = QLabel(label + ("" if presente else "  (sin datos)"))
            color_nombre = "#cbd5e1" if presente else "#5b6472"
            nombre_label.setStyleSheet(f"color: {color_nombre}; font-size: 12px; font-weight: {peso};")
            fila_layout.addWidget(nombre_label, stretch=1)

            color = "#f4f7fb" if es_seleccionado else "#94a3b8"
            valor_label = QLabel(formato_moneda(valor) if presente else "-")
            valor_label.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: {peso};")
            fila_layout.addWidget(valor_label)

            container_layout.addWidget(fila)

        container_layout.addStretch()
        scroll.setWidget(container)
        return scroll

    def _build_movimiento(self, row, label_comparado):
        col_debe = f"DEBE_{label_comparado}"
        col_haber = f"HABER_{label_comparado}"
        if col_debe not in row.index and col_haber not in row.index:
            return None

        debe = row.get(col_debe, 0.0) or 0.0
        haber = row.get(col_haber, 0.0) or 0.0
        if debe == 0 and haber == 0:
            return None

        container = QFrame()
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(6)
        container_layout.setContentsMargins(0, 0, 0, 0)

        for etiqueta, valor in [("Debe", debe), ("Haber", haber)]:
            fila = QFrame()
            fila.setObjectName("componentRow")
            fila_layout = QHBoxLayout(fila)
            fila_layout.setContentsMargins(10, 6, 10, 6)

            nombre_label = QLabel(etiqueta)
            nombre_label.setStyleSheet("color: #e5eaf3; font-size: 12px;")
            fila_layout.addWidget(nombre_label, stretch=1)

            valor_label = QLabel(formato_moneda(valor))
            valor_label.setStyleSheet("color: #f4f7fb; font-size: 12px; font-weight: 700;")
            fila_layout.addWidget(valor_label)

            container_layout.addWidget(fila)

        return container

    def _metric_line(self, icono, etiqueta, valor_txt, valor_num):
        row_widget = QFrame()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel(f"{icono} {etiqueta}")
        label.setStyleSheet("color: #94a3b8; font-size: 13px;")
        label.setWordWrap(True)
        row_layout.addWidget(label, stretch=1)

        color = "#2dd4bf" if (valor_num is not None and valor_num >= 0) else "#f87171"
        valor = QLabel(valor_txt)
        valor.setStyleSheet(f"color: {color}; font-weight: 800; font-size: 13px;")
        row_layout.addWidget(valor)

        return row_widget


def _limpiar_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()


def _estado_para_par(presente_base: bool, presente_comparado: bool) -> str:
    if presente_base and not presente_comparado:
        return ESTADO_DISCONTINUADA
    if presente_comparado and not presente_base:
        return ESTADO_NUEVA
    return "EXISTENTE"


def _estado_visual(estado: str) -> tuple[str, str]:
    if estado == ESTADO_NUEVA:
        return "🆕 Cuenta nueva (no existía en el período base)", "#2dd4bf"
    if estado == ESTADO_DISCONTINUADA:
        return "🗂️ Cuenta discontinuada (no aparece en el período comparado)", "#f87171"
    return "Cuenta presente en ambos períodos del par elegido", "#7d8ba1"
