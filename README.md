# Global Capital Flows Map

> *Global Flow Matrix* — terminal cross-asset interactiva (documentación en español).

**Interactive cross-asset terminal** that visualizes capital rotation and market regime in real time.

🔴 **Live demo:** [flow.quantcentral.eu](https://flow.quantcentral.eu)

**Última actualización:** 2026-08-05

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
- **Riesgo geopolítico (AI-GPR)** - Percentil histórico de tensión global, medido sobre prensa
- **War Lab** (`/war`) - Qué sectores ganan y pierden en las crisis geopolíticas
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

> **Puerto 5055**, no 5000: el `:5000` suele estar ocupado por otro servicio.
> Se cambia con `PORT=xxxx python app.py`.

Abrir **http://127.0.0.1:5055**

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

Abrir **http://127.0.0.1:5055**

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

### 7. Riesgo geopolítico (AI-GPR) y War Lab

Gauge en la barra de régimen con el **percentil histórico** de riesgo geopolítico,
y un laboratorio de análisis en **`/war`**.

**La fuente**: [AI-GPR](https://www.matteoiacoviello.com/ai_gpr.html) de Caldara &
Iacoviello — un LLM (GPT-4o-mini) puntúa artículos del NYT, Washington Post y
Chicago Tribune por intensidad de riesgo geopolítico. Serie **diaria continua desde
1960**, calibrada a media 100 sobre 1985-2019. Publicada con ~5 días de retraso.

**Por qué percentil y no min-max** (la decisión que define el indicador):

| | valor 2026-07-31 | min-max | percentil |
|---|---|---|---|
| `GPR_AI` media 30d | 175,7 | **43,5** → "Moderado" | **95,5** → "Alto" |

El pico del 11-S define el rango entero y aplasta 66 años contra el piso. Peor: el
min-max **reescribe la historia** — cada récord nuevo cambia el número de ayer, y el
indicador deja de ser comparable consigo mismo. El min-max se guarda igual, para
auditoría interna.

**Por qué media de 30 días y no el dato crudo**: el AI-GPR diario cambia un **26,8%
mediano** de un día al otro; sobre MA30, **1,03%**. Un gauge sobre el crudo
parpadearía sin que pasara nada en el mundo.

**Cortes no lineales** (50/75/90/97): con 20/40/60/80, "Alto o Crítico" sería el 40%
de los días de la historia y la palabra dejaría de significar algo.

#### War Lab (`/war`)

Cruza el índice con los 11 sectores sobre **6.960 días hábiles (1998→hoy)**, en
retorno **relativo a SPY** — en una crisis cae todo, lo que importa es quién cae
menos. Cuatro análisis: régimen alto vs bajo, beta al shock, estudio de eventos y
correlación con el RORO.

Tres resultados que vale la pena conocer antes de leer los gráficos:

1. **Cuidado con el spread crudo.** Dice que Tecnología es la gran ganadora de las
   crisis (+9,5 pp anualizados). Es una trampa temporal: los períodos de riesgo alto
   se concentran en 2001-03 y 2022-26, y lo segundo coincide con el boom de IA.
   Demediado por año cae al 3º puesto, y su beta al shock es la **más negativa** de
   las once. Por eso la tabla muestra las dos columnas.
2. **Los ganadores reales son los defensivos clásicos**, medidos por reacción al
   shock (pb de retorno relativo por 1σ de salto del índice):
   Inmobiliario **+5,0** (t=2,96), Consumo básico **+4,0** (t=3,66), Utilities
   **+4,0** (t=3,08). Energía es el caso raro: +3,3 al shock inmediato pero −5,2 pp
   en régimen sostenido.
3. **RORO y riesgo geopolítico son casi ortogonales**: correlación **0,035** en
   niveles y **−0,02** en cambios sobre 6.886 días. El índice aporta información que
   el terminal no tenía, en vez de duplicar el RORO.

> Es **correlación histórica, no causalidad ni predicción**. El AI-GPR mide cobertura
> periodística del riesgo, no la guerra. Y cada crisis es idiosincrática: el petróleo
> dominó 2022 y no 2001 — por eso los episodios se listan uno por uno.

### 8. Actualización Automática
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
snapshot_builder.py    Ensamblado del snapshot (separado de app.py: los jobs de
                       cron lo invocan sin ciclo de imports)
preload_cache.py       Jobs de mercado (cierre 17:00 ET, intradía c/15 min)
price_store.py         Base de precios diarios, ventana fija de 320 barras
intraday_store.py      Velas de 15 min (solo para el período 1d)
etf_flow_tracker.py    Histórico de flujo ETF (SSGA + stockanalysis, ver abajo)
scrape_etf_flows.py    Script diario que alimenta el histórico de flujo
gpr_store.py           Riesgo geopolítico AI-GPR: descarga, percentil, niveles
war_lab.py             Análisis riesgo geopolítico × sectores (sirve a /war)
static/index.html      Frontend vanilla JS + SVG (sin build, sin frameworks)
static/war.html        War Lab, mismo enfoque vanilla
static/favicon.ico     Icono personalizado

data/                  (no versionado, se regenera solo)
  ├─ price_history.json    320 barras diarias por símbolo
  ├─ intraday_bars.json    3 días hábiles de velas de 15 min
  ├─ etf_flows.json        histórico de shares × NAV por ETF
  ├─ ai_gpr_daily.csv      CSV oficial del AI-GPR, completo (15 columnas)
  └─ war_prices.csv        cierres sectoriales desde 1998 (solo War Lab)
```

### Rutas

| Ruta | Devuelve |
|------|----------|
| `GET /` | el terminal |
| `GET /api/snapshot?period={1,5,20,50,180}` | JSON de todos los paneles |
| `GET /api/health` | estado + modo (live/demo) |
| `GET /war` | War Lab |
| `GET /api/war/analysis` | el análisis completo (cacheado 6 h) |
| `GET /api/geopolitical-risk/latest` | último dato del AI-GPR |
| `GET /api/geopolitical-risk/history?days=365` | la serie |

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
| Flujo ETF | SSGA + stockanalysis.com | Gratis | — (FMP `/etf/holdings` es premium) |
| Riesgo geopolítico | AI-GPR (Caldara & Iacoviello) | Gratis | Nada |
| Precios largos (War Lab) | yfinance, desde 1998 | Gratis | Nada |

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

**No usar yfinance para esto.** Sirve `sharesOutstanding` y `totalAssets` cacheados
y congelados: durante 14 días, 24 de 43 símbolos repitieron el mismo valor (SPY
clavado en 917.782.016 cuando el real es ~1.050M) → flujo **exactamente 0**; los
otros 19 caían al fallback `totalAssets/NAV` con `totalAssets` fijo, así que
`Δshares` era el **precio con el signo invertido**. La firma en disco es un AUM
idéntico al 4º decimal durante semanas.

**Las fuentes que sí sirven**, en orden:

1. **SSGA** — `navhist-us-en-{ticker}.xlsx` trae NAV + Shares Outstanding diarios con
   **~22 años de histórico**. Cubre 16/43 (SPY, los 11 XLx, GLD, KBE, KIE, XOP), que
   son los de más peso. Para estos, `snapshot()` reemplaza la serie entera: la fuente
   es autoritativa y corrige huecos sola.
2. **stockanalysis.com** — `/etf/{sym}/__data.json`, cobertura 43/43 pero solo el
   corte de hoy. Los 27 restantes se construyen **hacia adelante**, un día por vez.
   iShares (toda la clase Bonos) publica el mismo archivo que SSGA pero lo bloquea
   con un bot-check que devuelve HTML con `Content-Type: text/csv`.
3. yfinance, último recurso, marcado en `src` para no mezclar escalas.

**Dos guardas que evitan mentir**, ambas en `etf_flow_tracker.py`:

- `_is_live()` devuelve **`None`** (tile gris + aviso) ante cualquier firma de dato
  muerto: shares constante en toda la ventana, o AUM constante mientras shares varía.
  Un `0` en el heatmap se lee como "el capital no se movió", que es una afirmación.
- `_es_split()` neutraliza los splits: XLK partió 2:1 el 2025-12-05 y sin el guard
  aparecía como una entrada de **47.600 millones**, más que todo el flujo real del
  semestre. Exige las dos condiciones (salto de shares + NAV dividido por el mismo
  factor), así que una creación grande de verdad no se confunde con un split.

Los nodos agregadores **suman a sus hijos**; el ETF proxy es solo el fallback: SPY
mide una porción de Equity y AGG una de Bonos, así que el padre contradecía a sus
propios hijos.

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

Los 16 símbolos de SSGA llegan con el histórico completo, así que sus ventanas están
disponibles desde el primer día. Los otros 27 se acumulan. Mientras se llenan, el
heatmap muestra un aviso ámbar y RS/CMF cubren la lectura.

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
| **Narrativa** (exógena) | AI-GPR | contexto | NUNCA como causa de un flujo |

El riesgo geopolítico es una tercera capa: no se deriva de precios ni mide dinero,
mide **cobertura periodística**. Por eso el gauge va separado por un divisor en la
barra de régimen y su tooltip lo dice explícitamente — si estuviera junto al resto,
invitaría a leerlo como causa de los flujos.

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

# Self-checks de los módulos con lógica no trivial (asserts + fuente en vivo)
python etf_flow_tracker.py     # guards de dato muerto, splits, parseo
python gpr_store.py            # niveles, validación del CSV, descarga real
python war_lab.py              # retorno relativo, z-score, y el análisis entero

# Testear modo LIVE sin keys (yfinance es gratis)
python -c "import snapshot_builder as sb; print(sb.live_snapshot(180)['meta']['mode'])"

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
- **AI-GPR**: [Caldara & Iacoviello](https://www.matteoiacoviello.com/ai_gpr.html) — índice de riesgo geopolítico
- **SSGA**: NAV history diario de los SPDR (`navhist-us-en-{ticker}.xlsx`)

---

**Última actualización:** 2026-08-05
**Estado:** ✅ Production-ready — [flow.quantcentral.eu](https://flow.quantcentral.eu)
