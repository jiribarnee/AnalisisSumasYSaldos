#!/bin/bash
# ============================================================
# build_exe_mac.sh
#
# Genera AnalisisSumasYSaldos.app para macOS.
#
# Uso:
#   chmod +x build_exe_mac.sh
#   ./build_exe_mac.sh
# ============================================================

set -e

echo ""
echo "=== Analisis Mensual de Sumas y Saldos - Generador de .app (macOS) ==="
echo ""

if [ ! -f "venv/bin/activate" ]; then
    echo "ERROR: No se encontró la carpeta venv."
    echo "Creá el entorno virtual primero con: python3 -m venv venv"
    exit 1
fi

source venv/bin/activate

echo "Instalando PyInstaller si hace falta..."
pip install -r requirements-dev.txt --quiet

echo ""
echo "Limpiando compilaciones anteriores..."
rm -rf build dist

echo ""
echo "Generando el ejecutable (esto puede tardar unos minutos)..."
echo ""

ICON_FLAG=""
if [ -f "assets/icon.icns" ]; then
    ICON_FLAG="--icon assets/icon.icns"
fi

pyinstaller --noconfirm --windowed --name "AnalisisSumasYSaldos" \
    $ICON_FLAG \
    --add-data "assets:assets" \
    --collect-all PySide6 --collect-data plotly \
    main.py

echo ""
if [ -d "dist/AnalisisSumasYSaldos.app" ]; then
    echo "================================================"
    echo " LISTO. El programa se generó correctamente en:"
    echo " dist/AnalisisSumasYSaldos.app"
    echo ""
    echo " Para distribuirlo, comprimí ese archivo .app"
    echo " (clic derecho -> Comprimir) y envíaselo."
    echo "================================================"
else
    echo "Algo falló. Revisá los mensajes de arriba."
fi
