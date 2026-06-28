# Mapa de Flujos Globales

**Terminal cross-asset para visualizar rotación de capital** entre clases de activo, sectores e industrias.

Terminal interactiva que muestra:
- **RRG (Relative Rotation Graph)**: rotación de sectores con análisis de cuadrantes
- **RORO (Risk-On/Risk-Off)**: régimen de mercado con z-scores de ratios cíclicos/defensivos
- **CMF (Chaikin Money Flow)**: presión de precios en el árbol jerárquico
- **COT (Commitment of Traders)**: posicionamiento de especuladores
- **Macro KPIs**: tasas, FX, commodities, inflación, volatilidad
- **Noticias**: headlines con sentimiento
- **Heatmap interactivo**: árbol jerárquico con navegación por niveles

---

## Arranque rápido

```bash
# 1) Configurar keys (todas gratis)
cp .env.example .env
# Editar .env y agregar (opcional):
#   FRED_API_KEY=<tu_fred_key>        (Federal Reserve Economic Data)
#   QUANDL_API_KEY=<tu_quandl_key>    (COT - Commitment of Traders)

# 2) Correr
bash run.sh

# Manual
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Abrir **http://127.0.0.1:5000**

---

## Arquitectura

### Backend (Flask - app.py)
```
compute/
  ├─ rrg.py      RS-Ratio / RS-Momentum (fuerza relativa vs momentum)
  ├─ cmf.py      Chaikin Money Flow (presión de precios)
  ├─ roro.py     Risk-On/Off (z-scores de SPY/Bonos USA, Cobre/Oro, etc.)
  ├─ cot.py      Commitment of Traders (especuladores)
  ├─ macro.py    KPIs económicos (tasas, FX, commodities, inflación)
  └─ news.py     Headlines con sentimiento
  
fmp_client.py    Wrapper de datos (yfinance, FRED, Quandl, FMP)
cache.py         Caché TTL en disco
config.py        Símbolos, parámetros, benchmarks ← editar aquí
universe.py      Árbol jerárquico (clases → sectores → industrias → activos)
```

### Frontend (vanilla JS + SVG)
```
static/index.html (sin build step, sin frameworks)
  ├─ RRG interactivo (PixiJS + SVG fallback)
  │   └─ Click en cuadrante = selecciona todos los sectores
  │   └─ Click en línea/punto = selecciona un sector solo
  ├─ Heatmap interactivo con glow dinámico
  │   └─ Verde (positivo) / Rojo (negativo)
  ├─ Tooltips visuales en macro KPIs
  └─ Animaciones CSS fade-in y hover effects
```

---

## Fuentes de datos

| Componente | Fuente | Costo | Requiere |
|-----------|--------|-------|----------|
| **Históricos de precio** | yfinance | Gratis | Nada |
| **RRG Sectores/Cross** | yfinance | Gratis | Nada |
| **CMF (presión)** | yfinance | Gratis | Nada |
| **RORO (régimen)** | yfinance | Gratis | Nada |
| **Cotizaciones** | yfinance | Gratis | Nada |
| **Indicadores económicos** | FRED | Gratis | FRED_API_KEY |
| **COT (Traders)** | Quandl | Gratis | QUANDL_API_KEY |
| **Noticias** | OpenBB | Gratis | Instalado |
| **Flujo ETF** | FMP | Gratis | FMP_API_KEY |

**Sin keys opcionales**: sistema funciona al 100% (RRG, CMF, RORO, cotizaciones, noticias).
- Sin FRED → macro indicadores en "n/d"
- Sin Quandl → COT en demo

---

## Interactividad

### RRG (Relative Rotation Graph)
- **Hover sobre cuadrante**: resalta todos los sectores del cuadrante
- **Hover sobre línea/punto**: resalta un sector individual
- **Click en nombre de cuadrante**: fija todos los sectores (resto desaparece)
- **Click en línea/punto**: fija un sector solo
- **Click en background**: deselecciona

### Heatmap
- **Navega**: click en tiles sin flechas (▸) para expandir
- **Glow dinámico**: verde (alcista) / rojo (bajista)
- **Hover**: levanta y resalta
- **Métrica**: botones para cambiar entre RS, CMF

### Macro KPIs
- **Hover**: tooltip con descripción de qué indica
- **Sparkline**: últimos 12 períodos
- Soporta: tasas, FX, commodities, inflación, volatilidad (VIX)

---

## Conceptos clave

### Flujos inferidos vs observados
- **Inferidos** (proxy, tiempo real): RRG, CMF, RORO → se leen como *fuerza/presión*
- **Observados** (dinero real, con lag): flujo ETF, COT → se leen como *capital real*

Nunca etiquetar RRG/CMF como "entró/salió capital". Solo flujo ETF y COT pueden.

### RORO (Risk-On/Risk-Off)
Compuesto de:
- **SPY / Bonos USA**: acciones vs bonos (ciclo vs defensa)
- **Cobre / Oro**: ciclo vs refugio
- **Cíclicos / Defensivos**: XLY vs XLP
- **Spread HY (inv)**: high-yield vs treasuries
- **VIX (invertido)**: volatilidad inversa

**Positivo (+)** = Risk-On (favorables al riesgo)  
**Negativo (-)** = Risk-Off (defensivos)

---

## Customización

### Agregar/quitar sectores
Editar `universe.py` → se refleja automáticamente en todo el árbol.

### Cambiar símbolos macro
Editar `MACRO_CARDS` en `config.py`:
```python
MACRO_CARDS = [
    {"nm": "Fed funds", "kind": "econ", "name": "federalFunds", "fred": "FEDFUNDS", "unit": "%"},
    {"nm": "Plata/Oro", "kind": "ratio", "a": "SIUSD", "b": "GCUSD", "unit": "ratio"},
    ...
]
```

### Cambiar benchmarks RRG
`config.py`:
```python
BENCH_EQUITY = "SPY"      # Benchmark para sectores
BENCH_CROSS = "ACWI"      # Benchmark para cross-asset
```

---

## Troubleshooting

- **Macro KPI sin gráfico**: símbolo FMP incorrecto. Probar `alt` en `config.py`.
- **COT vacío**: revisión de `COT_SYMBOLS` y nombres de campos en `compute/cot.py`.
- **Badge "parcial"**: ver `meta.notes` en el pie; algún endpoint premium no disponible.
- **RRG labels superpuestos**: es normal en zoom alto; click en línea para aislar.

---

## Datos y caché

Para forzar recálculo:
```bash
rm -rf cache/*.json
```

TTLs en `config.py`:
- Precios (RRG, CMF): **horaria**
- Macro, ETF flows: **diaria**
- COT: **semanal**

---

## Autor

© 2026 Leandro R. Bergero, Msc Finance & Banking BSM-UPF

Análisis de rotación de capital global | Datos en vivo, inferencias reales.
