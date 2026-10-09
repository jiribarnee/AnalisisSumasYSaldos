"""
main_window.py

Ventana principal de la aplicación. Contiene dos "páginas" dentro de un
QStackedWidget:

    1. SelectionPage: elegir entre 2 y 12 archivos Excel a comparar.
    2. DashboardPage: mostrar los resultados de la comparación.
"""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.comparator import MAX_PERIODOS, MIN_PERIODOS, comparar_periodos
from core.excel_processor import (
    ExcelProcessingError,
    detect_period_label,
    load_balance_file,
)
from ui.dashboard import DashboardPage


def resource_path(relative_path: str) -> str:
    """
    Devuelve la ruta absoluta a un recurso (ej: assets/style.qss),
    funcionando tanto si la app corre con "python main.py" como si
    corre empaquetada (.exe en Windows, .app en macOS) con PyInstaller.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


class FilePickerRow(QFrame):
    def __init__(self, numero: int, on_remove=None, parent=None):
        super().__init__(parent)
        self.filepath: str | None = None
        self._on_remove = on_remove
        self._numero = numero

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        top_row = QHBoxLayout()
        self.label = QLabel(f"Archivo período {numero}")
        self.label.setObjectName("fieldLabel")
        top_row.addWidget(self.label)
        top_row.addStretch()

        if on_remove is not None:
            self.remove_button = QPushButton("✕")
            self.remove_button.setObjectName("removeButton")
            self.remove_button.setCursor(Qt.PointingHandCursor)
            self.remove_button.setFixedSize(24, 24)
            self.remove_button.clicked.connect(lambda: self._on_remove(self))
            top_row.addWidget(self.remove_button)
        layout.addLayout(top_row)

        row = QHBoxLayout()
        row.setSpacing(8)

        self.path_display = QLineEdit()
        self.path_display.setReadOnly(True)
        self.path_display.setMinimumWidth(320)
        self.path_display.setMinimumHeight(38)
        self.path_display.setPlaceholderText("Ningún archivo seleccionado...")
        self.path_display.setObjectName("pathDisplay")
        row.addWidget(self.path_display, stretch=1)

        self.browse_button = QPushButton("📁 Examinar")
        self.browse_button.setObjectName("browseButton")
        self.browse_button.setMinimumHeight(38)
        self.browse_button.setMinimumWidth(130)
        self.browse_button.setCursor(Qt.PointingHandCursor)
        self.browse_button.clicked.connect(self._on_browse)
        row.addWidget(self.browse_button)

        layout.addLayout(row)

        period_row = QHBoxLayout()
        period_label = QLabel("Nombre del período:")
        period_label.setObjectName("smallLabel")
        period_row.addWidget(period_label)

        self.period_input = QLineEdit()
        self.period_input.setPlaceholderText("Se detecta automáticamente...")
        self.period_input.setObjectName("periodInput")
        self.period_input.setMinimumWidth(280)
        self.period_input.setMinimumHeight(36)
        period_row.addWidget(self.period_input, stretch=1)

        layout.addLayout(period_row)

    def set_numero(self, numero: int):
        self._numero = numero
        self.label.setText(f"Archivo período {numero}")

    def _on_browse(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo Excel", "", "Archivos Excel (*.xlsx *.xlsm)"
        )
        if not filepath:
            return
        self.filepath = filepath
        self.path_display.setText(os.path.basename(filepath))
        self.path_display.setToolTip(filepath)
        if not self.period_input.text().strip():
            self.period_input.setText(detect_period_label(filepath))

    def get_period_label(self) -> str | None:
        text = self.period_input.text().strip()
        return text if text else None


class SelectionPage(QWidget):
    def __init__(self, on_analizar, parent=None):
        super().__init__(parent)
        self._on_analizar = on_analizar
        self._picker_rows: list[FilePickerRow] = []
        self._build_ui()
        self._agregar_periodo()
        self._agregar_periodo()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignCenter)
        outer.setContentsMargins(60, 40, 60, 40)

        card = QFrame()
        card.setObjectName("selectionCard")
        card.setMinimumWidth(760)
        card.setMaximumWidth(920)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(40, 36, 40, 36)
        card_layout.setSpacing(16)

        title = QLabel("📊 ANÁLISIS MENSUAL DE SUMAS Y SALDOS")
        title.setObjectName("titleLabel")
        title.setAlignment(Qt.AlignCenter)
        title.setWordWrap(True)
        card_layout.addWidget(title)

        subtitle = QLabel("Comparás el balance de cuentas contables entre varios períodos (2 a 12 meses)")
        subtitle.setObjectName("subtitleLabel")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        card_layout.addWidget(subtitle)

        card_layout.addSpacing(6)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setMinimumHeight(400)
        scroll.setMaximumHeight(480)

        self._pickers_container = QWidget()
        self._pickers_layout = QVBoxLayout(self._pickers_container)
        self._pickers_layout.setSpacing(16)
        self._pickers_layout.setContentsMargins(0, 0, 8, 0)
        self._pickers_layout.addStretch()
        scroll.setWidget(self._pickers_container)

        card_layout.addWidget(scroll)

        self.agregar_button = QPushButton("+ Agregar otro período")
        self.agregar_button.setObjectName("addPeriodButton")
        self.agregar_button.setCursor(Qt.PointingHandCursor)
        self.agregar_button.clicked.connect(self._agregar_periodo)
        card_layout.addWidget(self.agregar_button)

        card_layout.addSpacing(6)

        self.analizar_button = QPushButton("ANALIZAR")
        self.analizar_button.setObjectName("primaryButton")
        self.analizar_button.setCursor(Qt.PointingHandCursor)
        self.analizar_button.setMinimumHeight(54)
        self.analizar_button.clicked.connect(self._handle_analizar)
        card_layout.addWidget(self.analizar_button)

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        card_layout.addWidget(self.status_label)

        outer.addWidget(card, alignment=Qt.AlignCenter)

    def _agregar_periodo(self):
        if len(self._picker_rows) >= MAX_PERIODOS:
            return
        numero = len(self._picker_rows) + 1
        on_remove = self._quitar_periodo if numero > MIN_PERIODOS else None
        row = FilePickerRow(numero, on_remove=on_remove)
        self._picker_rows.append(row)
        self._pickers_layout.insertWidget(self._pickers_layout.count() - 1, row)
        self._actualizar_estado_botones()

    def _quitar_periodo(self, row: FilePickerRow):
        if len(self._picker_rows) <= MIN_PERIODOS:
            return
        self._picker_rows.remove(row)
        row.setParent(None)
        row.deleteLater()
        self._renumerar()
        self._actualizar_estado_botones()

    def _renumerar(self):
        for idx, row in enumerate(self._picker_rows, start=1):
            row.set_numero(idx)
            can_remove = idx > MIN_PERIODOS
            if hasattr(row, "remove_button"):
                row.remove_button.setVisible(can_remove)

    def _actualizar_estado_botones(self):
        self.agregar_button.setEnabled(len(self._picker_rows) < MAX_PERIODOS)
        self.agregar_button.setText(f"+ Agregar otro período ({len(self._picker_rows)}/{MAX_PERIODOS})")

    def _handle_analizar(self):
        periodos_info = []
        for row in self._picker_rows:
            if not row.filepath:
                self.status_label.setText("⚠️ Completá todos los períodos antes de analizar (o quitá los que no vayas a usar).")
                return
            periodos_info.append((row.filepath, row.get_period_label()))

        duplicado = self._detectar_archivo_duplicado(periodos_info)
        if duplicado:
            self.status_label.setText(
                f"⚠️ Seleccionaste el mismo archivo más de una vez: \"{duplicado}\". "
                f"Cada período debe cargarse desde un archivo distinto."
            )
            return

        self.status_label.setText("")
        self._on_analizar(periodos_info)

    @staticmethod
    def _detectar_archivo_duplicado(periodos_info: list[tuple[str, str | None]]) -> str | None:
        vistos: set[str] = set()
        for filepath, _ in periodos_info:
            clave = os.path.normcase(os.path.abspath(filepath))
            if clave in vistos:
                return os.path.basename(filepath)
            vistos.add(clave)
        return None

    def show_error(self, message: str):
        self.status_label.setText(f"⚠️ {message}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Análisis Mensual de Sumas y Saldos")
        self.resize(1280, 900)
        self.setMinimumSize(960, 680)

        icon_path = resource_path(os.path.join("assets", "icon.ico"))
        if os.path.isfile(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.selection_page = SelectionPage(on_analizar=self._analizar)
        self.stack.addWidget(self.selection_page)

        self._load_stylesheet()

    def _load_stylesheet(self):
        qss_path = resource_path(os.path.join("assets", "style.qss"))
        if os.path.isfile(qss_path):
            with open(qss_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())

    def _analizar(self, periodos_info: list[tuple[str, str | None]]):
        periodos = []
        for filepath, label in periodos_info:
            try:
                periodo = load_balance_file(filepath, period_label=label)
            except ExcelProcessingError as exc:
                self._show_processing_error(str(exc))
                return
            except Exception as exc:  # noqa: BLE001
                self._show_processing_error(
                    f"Ocurrió un error inesperado al leer los archivos.\n\nDetalle: {exc}"
                )
                return
            periodos.append(periodo)

        vistos: dict[str, int] = {}
        for p in periodos:
            if p.label in vistos:
                vistos[p.label] += 1
                p.label = f"{p.label} ({vistos[p.label]})"
            else:
                vistos[p.label] = 1

        try:
            resultado = comparar_periodos(periodos)
        except Exception as exc:  # noqa: BLE001
            self._show_processing_error(f"Ocurrió un error al comparar los períodos.\n\nDetalle: {exc}")
            return

        dashboard = DashboardPage(resultado, on_volver=self._volver_a_seleccion)
        if self.stack.count() > 1:
            old_widget = self.stack.widget(1)
            self.stack.removeWidget(old_widget)
            old_widget.deleteLater()
        self.stack.addWidget(dashboard)
        self.stack.setCurrentWidget(dashboard)

    def _show_processing_error(self, message: str):
        QMessageBox.warning(self, "No se pudo procesar el archivo", message)
        self.selection_page.show_error(message)

    def _volver_a_seleccion(self):
        self.stack.setCurrentWidget(self.selection_page)
