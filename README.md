# 📊 Análisis Mensual de Sumas y Saldos

Aplicación de escritorio en Python que compara un **balance de Sumas y
Saldos** (cuentas contables) entre **2 y 12 períodos**, a partir de
archivos Excel mensuales. Desarrollada para **Bailo Hnos.**

Es el tercer programa de esta familia (junto a **Analizador de
Compras** y **Análisis de Compras por Concepto**), con una identidad
visual propia — azul marino oscuro con acento turquesa — para
diferenciarlo de los otros dos, aunque comparte el logo de la empresa.

## Qué hace

- Cargás entre 2 y 12 Excel de Sumas y Saldos (uno por período).
- Compara el **saldo de cada cuenta contable** (columna `CUENTA` +
  `NOMBRE`) a lo largo de todos los períodos cargados.
- Selector para elegir **cualquier par de períodos** a comparar (no
  solo el primero/último): afecta variación, alertas y gráficos.
- Detecta cuentas nuevas y discontinuadas **por presencia real en el
  archivo**, no por si el saldo da cero — una cuenta puede tener saldo
  $0 y haber tenido movimiento real ese mes (ej: una cuenta de IVA
  donde Debe = Haber). Este caso está verificado explícitamente.
- Alertas automáticas neutras (sin juicio de "bueno/malo", ya que una
  suba de saldo puede ser positiva o negativa según el tipo de cuenta).
- Gráficos: movimiento total (Debe/Haber) por período, top cuentas por
  saldo, top variaciones, distribución por estado.
- Detalle por cuenta: saldo en todos los períodos, y el detalle de
  Debe/Haber del período comparado.
- Empaquetable como ejecutable standalone (Windows `.exe` / macOS `.app`).

## Estructura real del Excel de origen

```
CUENTA, NOMBRE, DEBE, HABER, SALDO
```

`CUENTA` es un código contable de 10 dígitos. `SALDO = DEBE - HABER`
(verificado numéricamente). Los primeros 2 dígitos de `CUENTA` agrupan
por tipo contable (10=Activo, 20=Pasivo, 40=Gastos, 50=Ingresos, según
lo detectado en los archivos de la empresa).

## Instalación

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux
pip install -r requirements.txt
python main.py
```

Podés probar con los archivos de ejemplo **ficticios** en
`data/sample/` (los reales de Bailo Hnos. nunca se suben a un
repositorio público).

## Generar el ejecutable

**Windows:** `venv\Scripts\activate` → `pip install -r requirements-dev.txt` → `build_exe.bat`

**macOS:** `source venv/bin/activate` → `pip install -r requirements-dev.txt` → `chmod +x build_exe_mac.sh` → `./build_exe_mac.sh`

## Estructura del proyecto

```
AnalisisSumasYSaldos/
├── main.py
├── requirements.txt / requirements-dev.txt
├── build_exe.bat / build_exe_mac.sh
│
├── core/
│   ├── excel_processor.py   # Lectura y validación del balance
│   ├── comparator.py        # Comparación multi-período por cuenta
│   ├── calculations.py
│   ├── charts.py
│   └── alerts.py
│
├── ui/
│   ├── main_window.py
│   ├── dashboard.py
│   ├── charts_panel.py
│   ├── alerts_panel.py
│   └── detail_dialog.py
│
├── assets/                  # Ícono, logo, hoja de estilos
├── data/sample/              # Datos ficticios para pruebas
└── docs/screenshots/
```

## Privacidad

Todo el procesamiento es 100% local. Los Excel reales de la empresa no
se envían a ningún servidor ni se suben a este repositorio.

## Roadmap

- [x] Comparación multi-período por cuenta, con detección correcta de
      presencia (no basada en saldo cero), alertas, gráficos, detalle,
      manejo de errores.
- [x] Empaquetado como ejecutable standalone (Windows y macOS).
- [ ] Exportación de resultados a Excel/PDF.
