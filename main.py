"""
main.py

Punto de entrada de "Análisis Mensual de Sumas y Saldos".

Ejecutar con:
    python main.py
"""

import os
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow, resource_path


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Análisis Mensual de Sumas y Saldos")

    icon_path = resource_path(os.path.join("assets", "icon.ico"))
    if os.path.isfile(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
