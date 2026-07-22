# Global Capital Flows Map

> *Global Flow Matrix* — terminal cross-asset interactiva (documentación en español).

**Interactive cross-asset terminal** that visualizes capital rotation and market regime in real time.

**Última actualización:** 2026-06-29

---

## 🎯 ¿Qué es?

Un dashboard financiero que muestra:

- **RRG (Relative Rotation Graph)** - Rotación de 11 sectores + 8 clases de activo
- **Heatmap jerárquico** - Árbol de activos con navegación por niveles (Equity → Sectores → Industrias → Stocks)
- **Régimen RORO** - Risk-On/Risk-Off con z-scores de 5 ratios cíclicos/defensivos
- **COT (Commitment of Traders)** - Posicionamiento de especuladores (semanal)
- **KPIs Macro** - 17 indicadores: tasas, FX, commodities, inflación, volatilidad, cripto
- **SPY/10Y UST Gauge** - Indicador de ciclo vs defensa (Equity vs Bonos)
- **Gold/Silver Ratio** - Calculado desde Oro y Plata
- **Flujo ETF** - Dinero observado (creación/redención), histórico propio vía scraper
- **Noticias** - Headlines con sentimiento (OpenBB)

**Modo**: con una `FMP_API_KEY` gratuita corre **LIVE** (datos de mercado vía yfinance,
sin costo). Sin ella, arranca en **DEMO** (datos sintéticos). Las keys de FRED/Quandl
son opcionales y enriquecen secciones. Ver [API Keys](#-api-keys).

---

## 🚀 Instalación

Requiere **Python 3.10+** y git. No hay build step ni dependencias de Node.

### 🐧 Linux / macOS

```bash
# 1) Clonar
git clone https://github.com/leabergero/global-capital-flows-map.git
cd global-capital-flows-map

# 2) Entorno virtual + dependencias
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3) (opcional) configurar API keys — ver sección abajo
cp .env.example .env        # y editar con tus keys

# 4) Correr
python app.py               # o: bash run.sh
```

Abrir **http://127.0.0.1:5000**

### 🪟 Windows (PowerShell)

```powershell
# 1) Clonar
git clone https://github.com/leabergero/global-capital-flows-map.git
cd global-capital-flows-map

# 2) Entorno virtual + dependencias
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 3) (opcional) configurar API keys — ver sección abajo
copy .env.example .env       # y editar con tus keys

# 4) Correr
python app.py
```

Abrir **http://127.0.0.1:5000**

> Si PowerShell bloquea el script de activación, ejecutá una vez:
> `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`

### ⏱️ Flujo ETF automático (opcional)

Para acumular el histórico de flujo ETF, programá `scrape_etf_flows.py` 1×/día.
**Linux**: anacron (ver sección [Flujo ETF](#-flujo-etf--dinero-observado-scraper-propio)).
**Windows**: Task Scheduler → tarea diaria que ejecute
`.venv\Scripts\python.exe scrape_etf_flows.py`.

---

## 📊 Características principales

### 1. RRG Interactivo - 3 Ventanas temporales
- **5d** (5 ruedas, últimas 5 lecturas) - Corto plazo
- **20d** (20 barras, trending) - Mediano plazo
- **50d** (50 barras, confirmación) - Largo plazo

**Interactividad:**
- Click en el título de un cuadrante (LÍDER, REZAGADO…) → muestra solo ese cuadrante
- Click en el nombre de un sector → aísla ese sector
- Click en el fondo → limpia la selección
- Leyenda de tiempo centrada arriba (1 lectura = 1 día / 1 semana / 10 días según ventana)
- Flecha en el nodo actual indicando dirección de rotación; nombres pegados a cada línea

Cuadrantes:
- **Verde (Líder)**: X≥100, Y≥100 - Fuerza y momentum positivo
- **Ámbar (Debilitando)**: X≥100, Y<100 - Fuerza pero momentum negativo
- **Rojo (Rezagado)**: X<100, Y<100 - Debilidad en ambos
- **Azul (Mejorando)**: X<100, Y≥100 - Débil pero momentum positivo

### 2. Heatmap Jerárquico
- Navegación por niveles: Global → Clase → Sector → Industria → Stock
- **Verde** = RS alcista (supera benchmark)
- **Rojo** = RS bajista (cae vs benchmark)
- **Glow dinámico** en hover
- 3 métricas disponibles: RS (fuerza relativa), CMF (presión), Flujo (solo ETF)

### 3. Régimen de mercado (RORO)
- En la UI se titula **"Régimen de mercado"**, con tooltip explicativo al pasar el mouse
- **Z-score compuesto** de 5 ratios:
  - SPY / Bonos USA
  - Cobre / Oro
  - Cíclicos / Defensivos
  - Spread HY (bonos alto rendimiento)
  - VIX inverso

**Estados:**
- **BULLISH** (z ≥ +0.75) - Risk-On, confianza, dinero en riesgo
- **NEUTRAL** (-0.75 < z < +0.75) - Transición
- **BEARISH** (z ≤ -0.75) - Risk-Off, miedo, defensa predomina

### 4. SPY/10Y UST Gauge
- Barra vertical que sube/baja desde eje central
- **Arriba (verde)**: SPY MERCADOS - Equity supera Bonos
- **Abajo (roja)**: BONOS DEFENSA - Bonos (10Y UST) supera Equity
- **Escala dinámica** (5%, 25%, 50%, 100%) - Se ajusta automáticamente
- **Glow latente** en la barra activa
- **Tooltip** explicativo al pasar el mouse
- Muestra diferencia % en KPI

> Nomenclatura: usamos **10Y UST** (US Treasury 10-Year, estándar de la industria)
> en lugar del ticker del ETF (TLT) para el nodo de bonos largos.

### 5. Gold/Silver Ratio
- Calculado en vivo: Oro RS / Plata RS
- Media histórica: 60:1
- **Sube** = huida al oro (miedo, defensivo)
- **Baja** = confianza en plata (riesgo, cíclico)

### 6. Macro KPIs - 17 Indicadores
Organizados por categoría:
- **Tasas**: Fed funds, BCE, BoJ, PBoC
- **Monedas**: EUR/USD, USD/JPY
- **IPC**: USA, Eurozona
- **Metales**: Oro, Plata, Gold/Silver
- **Commodities**: WTI, Brent, UST 10Y
- **Índices**: DXY, VIX, BTC

Cada KPI muestra:
- Valor actual
- Cambio % con dirección (up/down/flat)
- Sparkline de últimos ~12 períodos
- Tooltip descriptivo

### 7. Actualización Automática
- **Recarga automática cada 1 hora** - Mantiene datos frescos
- **Badge de estado** con hora de última actualización:
  - 🟢 LIVE (datos en vivo vía FMP)
  - 🟡 PARCIAL (mix de live y fallback demo)
  - 🔴 DEMO (datos sintéticos)

---

## 📁 Arquitectura

```
app.py                 Flask, rutas, orquestación
config.py              ← EDITAR AQUÍ: símbolos, TTLs, benchmarks
cache.py               Caché TTL en disco (JSON sha1)
universe.py            Árbol jerárquico (clases → sectores → industrias → stocks)
fmp_client.py          Wrapper centralizado de datos (yfinance, FRED, Quandl, FMP)

compute/
  ├─ rrg.py            RS-Ratio, RS-Momentum (método JdK documentado)
  ├─ cmf.py            Chaikin Money Flow (presión de precios)
  ├─ flows.py          Flujo implícito ETF (Δ AUM × NAV)
  ├─ roro.py           Z-scores de ratios, régimen
  ├─ cot.py            Posición neta no-comercial (Quandl)
  ├─ macro.py          KPIs económicos (FRED, FMP, yfinance)
  └─ news.py           Headlines con sentimiento (OpenBB, fallback FMP)

demo_data.py           Snapshot sintético (fallback por sección)
etf_flow_tracker.py    Histórico propio de flujo ETF (shares × NAV, acumulativo)
scrape_etf_flows.py    Script diario (anacron) que alimenta el histórico de flujo
static/index.html      Frontend vanilla JS + SVG (sin build, sin frameworks)
static/favicon.ico     Icono personalizado
data/etf_flows.json    Histórico de flujo acumulado localmente (no versionado)
```

---

## 🔗 Contrato JSON (`/api/snapshot`)

```jsonc
{
  "meta": {
    "mode": "live|parcial|demo",
    "generated": "ISO-8601",
    "notes": ["secciones en fallback si las hay"],
    "etf_flow_depth": 1          // días de histórico de flujo ETF acumulados
  },
  
  "regime": {
    "state": "Risk-On|Neutral|Risk-Off",
    "score": 0.36,           // z-score compuesto ±3
    "color": "green|amber|red"
  },
  
  "rrg": {
    "sectores": [
      {"name": "Energía", "rs": 104.6, "mom": 101.9, "path": [[x,y], ...]},
      ...
    ],
    "cross": [...]           // 8 clases de activo
  },
  
  "roro": [
    ["SPY / Bonos USA", 0.9],
    ["Cobre / Oro", -0.4],
    ...
  ],
  
  "cot": [
    ["S&P fut · ES", 126, 18],  // [label, neto_miles, cambio_miles]
    ...
  ],
  
  "tree": {
    "name": "Global",
    "rs": 100.5,
    "mom": 100.2,
    "cmf": 0.15,
    "flow": 125.4,              // millones USD (solo ETF, null para acciones)
    "w": 1,
    "children": [...]           // recursivo
  },
  
  "macro": [
    {"nm": "Fed funds", "val": "5.25", "chg": "+0.5%", "dir": "up", "s": [...]},
    ...
  ],
  
  "news": [
    {"t": "headline", "src": "Reuters", "time": "2h ago", "sent": "pos|neg|neutral"},
    ...
  ]
}
```

**Unidades:**
- `rs`, `mom` ≈ 100 (centro = neutral)
- `cmf` ∈ [-0.5, 0.5]
- `flow` = millones USD (solo nodos ETF; acciones/cripto/FX = null)

---

## 📡 Fuentes de datos

| Componente | Fuente | Costo | Requiere |
|-----------|--------|-------|----------|
| Históricos precio | yfinance | Gratis | Nada |
| RRG, CMF, RORO | yfinance | Gratis | Nada |
| Cotizaciones spot | yfinance | Gratis | Nada |
| Indicadores económicos | FRED | Gratis | `FRED_API_KEY` (opcional) |
| COT (Traders) | Quandl | Gratis | `QUANDL_API_KEY` (opcional) |
| Noticias | OpenBB | Gratis | Instalado en venv |
| Flujo ETF | scraper propio (yfinance) | Gratis | — (FMP `/etf/holdings` es premium) |

**Con la FMP key gratuita** (modo LIVE), el núcleo funciona al 100% (RRG, CMF, RORO, cotizaciones).
- Sin FRED → macro indicadores en "n/d"
- Sin Quandl → COT en demo
- Sin OpenBB → noticias en demo

---

## 💰 Flujo ETF — dinero observado (scraper propio)

El flujo de un ETF es la **única capa de dinero observado** (no inferido): mide la
creación/redención real de unidades.

```
flujo_t  ≈  (shares_outstanding_t − shares_outstanding_{t-1})  ×  NAV_t
```

**El problema**: ninguna fuente gratuita da el *histórico* de shares/AUM de un ETF.
- yfinance da el snapshot **actual** (`sharesOutstanding`, `totalAssets`) — gratis
- `get_shares_full()` viene **vacío** para ETFs
- SSGA/iShares publican solo el holding **del día**
- Finnhub/EODHD/FactSet tienen el histórico pero **detrás de plan pago**
- FMP `/etf/holdings` requiere **plan pago** (devuelve 429 en el plan gratuito)

**La solución**: construir el histórico **hacia adelante**. Un script diario guarda
un snapshot (shares × NAV) y acumula en `data/etf_flows.json`. Las ventanas 5/20/50
son la suma de los flujos diarios de los últimos N snapshots disponibles.

### Uso

```bash
# captura manual de un snapshot (idempotente, 43 ETFs del universo)
python scrape_etf_flows.py

# ver histórico acumulado
python -c "import etf_flow_tracker as t; print(t.coverage())"
```

### Automatización con anacron (recomendado)

Anacron corre el snapshot **una vez al día** y, a diferencia de cron, **recupera
corridas perdidas** si la máquina estuvo apagada.

```
~/.anacron/etc/anacrontab   →  1 5 etf-flows  cd <proj> && .venv/bin/python scrape_etf_flows.py
crontab:
  @reboot      anacron -t ~/.anacron/etc/anacrontab -S ~/.anacron/spool
  0 21 * * *   anacron -t ~/.anacron/etc/anacrontab -S ~/.anacron/spool
```

### Calendario de activación

El histórico se llena con el tiempo (no es retroactivo):

| Días hábiles acumulados | Ventana disponible |
|-------------------------|--------------------|
| ~6 | Flujo **5d** |
| ~21 | Flujo **20d** |
| ~51 | Flujo **50d** |

Mientras se llena, el heatmap muestra un aviso ámbar y RS/CMF cubren la lectura.
Cobertura: 43/43 ETFs (con fallback `totalAssets/NAV` para los menos líquidos).

---

## 🔑 API Keys

Todas las keys son **gratuitas**. Copiá `.env.example` a `.env` y completá las que
quieras. La key **nunca** llega al frontend (vive solo en el backend).

| Key | ¿Obligatoria? | Habilita | Obtener (gratis) |
|-----|---------------|----------|------------------|
| `FMP_API_KEY` | **Sí, para modo LIVE** | Activa el modo en vivo. **Sin ella el sistema corre en DEMO** (datos sintéticos). El plan gratuito alcanza: los datos de mercado vienen de yfinance, no de FMP. | [financialmodelingprep.com](https://site.financialmodelingprep.com/developer/docs) |
| `FRED_API_KEY` | Opcional | Indicadores económicos en vivo (tasas Fed/BCE/BoJ, IPC). Sin ella → "n/d". | [fredaccount.stlouisfed.org/apikeys](https://fredaccount.stlouisfed.org/apikeys) |
| `QUANDL_API_KEY` | Opcional | COT (posición de futuros del CFTC). Sin ella → COT demo. | [data.nasdaq.com/sign-up](https://data.nasdaq.com/sign-up) |
| OpenBB | Opcional (paquete) | Noticias con sentimiento. Sin él → noticias demo. | `pip install openbb` |

> **El gotcha importante:** la `FMP_API_KEY` del plan **gratuito** es lo único que
> hace falta para el modo LIVE — *no* porque FMP provea los datos (los da yfinance,
> gratis), sino porque su ausencia activa el modo DEMO. El endpoint premium de FMP
> (`/etf/holdings`, para flujo ETF) **no** es necesario: ese flujo se construye
> localmente con el scraper.

### Ejemplo de `.env`
```bash
FMP_API_KEY=tu_key_gratuita_de_fmp     # requerida para LIVE
FRED_API_KEY=                          # opcional
QUANDL_API_KEY=                        # opcional
```

### config.py - Editar aquí
```python
BENCH_EQUITY = "SPY"           # Benchmark para sectores
BENCH_CROSS = "ACWI"           # Benchmark global
RRG_WINDOW = 12                # Barras para RS-Ratio (5d default)
RRG_TAIL = 5                   # Puntos de cola del gráfico
TTL = {
  "snapshot": 900,             # 15 min
  "hist": 3600,                # 1 hora
  "roro": 3600
}

MACRO_CARDS = [
  {"symbol": "^GSPC", "alt": [...], "name": "S&P 500", ...},
  ...
]
```

---

## 🎨 Paleta de colores (desaturada)

```css
--bg: #171821           /* fondo */
--surface: #1f2129      /* paneles */
--border: #363a47       /* líneas */
--text: #dcdde3         /* texto principal */
--muted: #8b8fa0        /* texto secundario */
--green: #6dd26d        /* alcista, risk-on, positivo */
--red: #ff6b6b          /* bajista, risk-off, negativo */
--amber: #d4a25e        /* neutral, transición */
--blue: #7a9ec8         /* líder (RRG) */
--purple: #9885b8       /* información, detalles */
```

---

## 📝 Disciplina conceptual

**Regla de oro**: Separar capas de inferencia vs observación.

| Capa | Modelos | Lectura | Afirmación válida |
|------|---------|---------|-------------------|
| **Inferida** (proxy) | RRG, CMF, RORO | "fuerza" / "presión" | NUNCA "entró/salió capital" |
| **Observada** (dinero real) | Flujo ETF, COT | dinero medido | "el capital se movió" |

**No se puede:**
- Etiquetar RS como "flujo de dinero"
- Afirmar magnitudes de dinero desde ratios de precio
- Usar volumen como proxy de flujo neto (comprador/vendedor)

**Se puede:**
- Usar CMF (pondera cierre dentro del rango)
- Calcular flujo implícito ETF (Δ AUM × NAV)
- Reportar COT como dinero observado

---

## 🧪 Testing

```bash
# Verificar que compila
python -m py_compile *.py compute/*.py

# Testear modo LIVE sin keys (yfinance es gratis)
python -c "import app; print(app._live_snapshot()['meta']['mode'])"

# Borrar caché y recargar
rm -rf cache/*.json
```

---

## 📋 Copias de seguridad y actualizaciones

- **Caché**: `cache/` - TTL automático, se limpia solo
- **Datos**: todo en vivo vía APIs (sin DB local)
- **Auto-reload**: cada 1 hora, mantiene datos frescos

---

## 📄 Licencia

© 2026 Leandro R. Bergero, Msc Finance & Banking (BSM-UPF)

---

## 🤝 Contribuir

Para reportar bugs o sugerir features, abre un issue en GitHub.

**Código de conducta:**
- Auditá línea por línea antes de proponer cambios
- Respetá la arquitectura: data → compute → frontend
- No agregues dependencias pesadas sin justificar
- Frontend: vanilla JS + SVG (sin frameworks)
- Backend: mantené `safe()` para degradación elegante

---

## 📚 Recursos

- **RRG**: [Método JdK](https://www.juliusdelkemptradinginformation.com/) - Relative Rotation Graphs
- **CMF**: Chaikin Money Flow (presión de precios)
- **RORO**: Z-scores de ratios cíclicos/defensivos
- **yfinance**: [GitHub](https://github.com/ranaroussi/yfinance)
- **FRED**: [API Docs](https://fred.stlouisfed.org/docs/api/)
- **Quandl**: [API Docs](https://docs.quandl.com/)

---

**Última actualización:** 2026-06-29
**Estado:** ✅ Production-ready
