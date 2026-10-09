@echo off
REM ============================================================
REM build_exe.bat
REM
REM Genera AnalisisSumasYSaldos.exe listo para distribuir a la
REM empresa, sin que necesiten instalar Python ni nada mas.
REM ============================================================

echo.
echo === Analisis Mensual de Sumas y Saldos - Generador de .exe ===
echo.

if not exist venv\Scripts\activate.bat (
    echo ERROR: No se encontro la carpeta venv.
    echo Cree el entorno virtual primero con: python -m venv venv
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

echo Instalando PyInstaller si hace falta...
pip install -r requirements-dev.txt --quiet

echo.
echo Limpiando compilaciones anteriores...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo.
echo Generando el ejecutable (esto puede tardar unos minutos)...
echo.

pyinstaller --noconfirm --windowed --name "AnalisisSumasYSaldos" ^
    --icon "assets\icon.ico" ^
    --add-data "assets;assets" ^
    --collect-all PySide6 --collect-data plotly ^
    main.py

echo.
if exist dist\AnalisisSumasYSaldos\AnalisisSumasYSaldos.exe (
    echo ================================================
    echo  LISTO. El programa se genero correctamente en:
    echo  dist\AnalisisSumasYSaldos\
    echo.
    echo  Para distribuirlo, comprimi TODA esa carpeta
    echo  (no solo el .exe) y envisela a la empresa.
    echo ================================================
) else (
    echo Algo fallo. Revisa los mensajes de arriba.
)

pause
