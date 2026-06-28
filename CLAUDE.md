# CLAUDE.md — Mapa de Flujos Globales

Guía para trabajar en este repo. **Leé esto entero antes de tocar código.**
Hay decisiones de diseño deliberadas que NO se deben romper sin avisar.

---

## Qué es

Terminal cross-asset que visualiza **rotación de capital** entre clases de activo,
sectores e industrias. Dos capas:

- **Backend Flask** (`app.py`): ingiere datos de yfinance + FRED + Quandl + OpenBB,
  calcula los modelos, cachea y expone un único JSON en `/api/snapshot`.
- **Frontend** (`static/index.html`): vanilla JS + SVG inline, solo pinta el JSON.
  Sin frameworks, sin build step, un solo archivo.

Las API keys (todas opcionales, todas gratis) viven **solo** en el backend
(variables de entorno). Nunca en el frontend.

---

## Comandos

```bash
# correr (crea venv, instala deps, arranca en :5000)
bash run.sh

# manual
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python app.py                       # http://127.0.0.1:5000

# verificar que compila todo
python -m py_compile *.py compute/*.py

# probar el camino LIVE sin keys (yfinance es gratis, todo funciona)
python -c "import app; print(app._live_snapshot()['meta']['mode'])"

# forzar recálculo (borrar caché)
rm -rf cache/*.json
```

**Modo**: Siempre **LIVE** con yfinance (gratis, sin API key).
- Con `FRED_API_KEY` → indicadores económicos en vivo
- Con `QUANDL_API_KEY` → COT en vivo
- Sin ellas → esos paneles usan demo/fallback

---

## Arquitectura y archivos

```
app.py            Flask. Rutas / , /api/snapshot , /api/health.
                  _live_snapshot() ensambla por sección con safe() (blindaje).
                  _build_node() recorre el árbol calculando rs/mom/cmf/flujo.
config.py         ÚNICA fuente de símbolos, TTLs, benchmarks y parámetros.
                  ← Acá se ajusta casi todo. Editá esto antes que la lógica.
universe.py       Árbol jerárquico (clases→sectores→industrias→constituyentes)
                  con tickers FMP. node(), TREE, RRG_SECTORES, RRG_CROSS.
cache.py          Caché TTL en disco (JSON sha1). get/set/clear.
fmp_client.py     Wrapper FMP. Todas las URLs centralizadas. Errores → None,
                  nunca excepción. Cada request se loguea con su status.
compute/
  rrg.py          RS-Ratio / RS-Momentum (reproducción documentada de JdK).
  cmf.py          Chaikin Money Flow.
  flows.py        Flujo implícito ETF (Δ AUM × NAV).  ← dinero observado.
  roro.py         Índice risk-on/off (z-score compuesto) + regime().
  cot.py          Posición neta no-comercial.
  macro.py        Tarjetas: tasas, FX, commodities, CPI.
  news.py         OpenBB → fallback FMP.
demo_data.py      Snapshot sintético. Modo DEMO y fallback por-sección.
                  Deriva del MISMO universe.TREE → estructura demo == live.
static/index.html Frontend STATE-driven. fetch('/api/snapshot'); si falla,
                  usa el DEMO embebido. Badge live/parcial/demo.
```

---

## Contrato JSON (`/api/snapshot`)

Backend y frontend dependen de esta forma EXACTA. Si cambiás una, cambiá la otra
(y `demo_data.py`, que también la produce).

```jsonc
{
  "meta":   { "mode": "live|parcial|demo", "generated": "ISO", "notes": ["..."] },
  "regime": { "state": "Risk-On|Risk-Off|Neutral...", "score": 0.36, "color": "green|amber|red" },
  "rrg": {
    "sectores": [ { "name": "Energía", "rs": 104.6, "mom": 101.9, "path": [[x,y],...] } ],
    "cross":    [ ... ]
  },
  "roro":  [ ["SPY / Bonos USA", 0.9], ... ],   // [nombre, z-score]
  "cot":   [ ["S&P fut · ES", 126, 18], ... ],   // [label, neto_miles, cambio_miles]
  "tree":  { "name","rs","mom","cmf","flow","w","children": [ ...recursivo... ] },
  "macro": [ { "nm","val","chg","dir":"up|down|flat","s":[sparkline...] } ],
  "news":  [ { "t","src","time","sent":"pos|neg|neutral" } ]
}
```

**Unidades del árbol:** `rs`/`mom` ~100 (centro), `cmf` ∈ [-0.5,0.5] aprox,
`flow` en **millones de USD** o `null` (solo nodos ETF tienen flujo; acciones,
cripto y FX van en `null` → tile neutro). El default neutro es rs=mom=100, cmf=0.

---

## Frontend — interactividad y visual (2026-06-28)

**RRG (Relative Rotation Graph)**:
- **Hover sobre cuadrante**: resalta todos los sectores del cuadrante
- **Hover sobre línea/punto**: resalta un sector individual
- **Click en nombre de cuadrante**: fija todos los sectores (resto desaparece)
- **Click en línea/punto**: fija un sector solo
- **Líneas**: 0.7px con glow dinámico (color por cuadrante)

**Heatmap**:
- **Glow dinámico**: verde si positivo (alcista), rojo si negativo (bajista)
- **Hover**: levanta, escala, brillo aumenta
- **Navegación**: click en tiles sin flecha (▸) para expandir niveles
- **Se aplica**: todos los niveles, todos los tiles

**Macro KPIs**:
- **17 indicadores**: Fed funds, BCE, BoJ, IPC, WTI, Brent, Oro, Plata, Plata/Oro,
  UST 10Y, DXY, VIX, BTC, EUR/USD, USD/JPY
- **Hover tooltip**: descripción completa de qué indica
- **Sparkline**: últimos ~12 períodos (fallback "n/d" si no hay datos)

**Animaciones**:
- `fadeIn` al cargar panels
- Glow effects en COT/RORO/Macro valores
- News dots crecen y brillan al hover

---

## Disciplina conceptual — NO romper

El mapa separa dos cosas que no son lo mismo. Esto es el corazón del proyecto:

| Capa | Modelos | Cómo se lee | Puede afirmar… |
|------|---------|-------------|----------------|
| **Inferida** (proxy, tiempo real) | RRG, CMF, ratios RORO | "fuerza" / "presión" | NUNCA "entró/salió capital" |
| **Observada** (dinero real, con lag) | flujo implícito ETF, COT | dinero medido | "el capital se movió" |

Reglas duras:
- **Nunca** etiquetar RS-Ratio ni CMF como flujo de dinero. Son presión/fuerza.
- **No** agregar Sankey con flechas par-a-par: el dato no soporta esas magnitudes.
- El volumen mide rotación, no flujo neto (un cierre en baja con volumen alto
  tiene comprador del otro lado). Por eso usamos CMF, que pondera *dónde* cierra
  el precio dentro del rango, no un up/down simple.
- Solo `flow` (ETF) y `cot` pueden comunicarse como dinero observado.

---

## Convenciones de código

- **Auditá línea por línea** antes de dar por cerrado un cambio: cuestioná la
  lógica y la necesidad de cada línea. Recién después se presenta.
- **La key jamás toca el frontend.** Solo `os.environ` en el backend. FMP además
  bloquea CORS desde el navegador: llamarlo desde el front ni funcionaría.
- **Degradación elegante por sección.** Toda fuente externa va envuelta de modo
  que un fallo caiga a demo/`n/d` y el resto siga vivo. Mirá `safe()` en
  `app.py` y los `try/except` de cada `compute/`. Nunca dejar que un endpoint
  caído rompa el snapshot entero.
- **Paleta oscura desaturada** (en TODO el CSS/SVG; ya está en `static/index.html`):

  ```
  bg #171821 · surface #1f2129 / #272934 · border #363a47
  text #dcdde3 · muted #8b8fa0
  blue #7a9ec8 · green #8fbc8f · amber #d4a25e · purple #9885b8
  red #e85a5a  (RESERVADO a pérdidas / estados críticos)
  ```
  Nada de colores neón o saturados.
- Comentarios y textos de UI en español. Logs también.

---

## Fuentes de datos (2026-06-28)

| Componente | Fuente | Costo | Requiere |
|-----------|--------|-------|----------|
| Históricos de precio | yfinance | Gratis | Nada |
| RRG, CMF, RORO | yfinance | Gratis | Nada |
| Cotizaciones spot | yfinance | Gratis | Nada |
| Indicadores económicos | FRED | Gratis | FRED_API_KEY (opcional) |
| COT (Traders) | Quandl | Gratis | QUANDL_API_KEY (opcional) |
| Noticias | OpenBB | Gratis | Instalado en venv |
| Flujo ETF | FMP | Gratis | FMP_API_KEY (opcional) |

**Sin keys opcionales**: sistema funciona 100% (RRG, CMF, RORO, cotizaciones, noticias).
- Sin FRED → macro indicadores en "n/d"
- Sin Quandl → COT en demo

**Si algo sale mal, casi siempre se arregla en `config.py`**:
- Macro KPI en `n/d` → símbolo yfinance incorrecto. Revisá `MACRO_CARDS`
  (probá los `alt`, ej. WTI: `CLUSD`/`WTIUSD`/`USO`).
- COT vacío → revisá `COT_SYMBOLS` y campos en `compute/cot.py`.
- Flujo ETF vacío → FMP key falta o plan no expone `/etf/holdings` histórico.

La estrategia es iterativa: correr, ver qué secciones salen `parcial` (badge +
`meta.notes`) y ajustar símbolos/endpoints en `config.py`. El core (RRG/CMF/RORO/
cotizaciones) funciona sin keys (yfinance es gratis).

---

## Estado actual (2026-06-28)

✅ **Completado**:
- RRG interactivo (click en cuadrante/sector)
- Heatmap con glow dinámico (rojo/verde)
- RORO verificado conceptualmente correcto
- 17 KPIs macro con tooltips visuales
- Frontend vanilla JS + SVG (sin build)
- Datos: yfinance + FRED + Quandl + OpenBB
- Copyright: Leandro R. Bergero, Msc Finance & Banking BSM-UPF
- Animaciones CSS y glow effects en todos los paneles

⚠️ **Pendientes menores**:
- [ ] Benchmark RRG cross-asset: validar `BENCH_CROSS = "ACWI"` vs alternativas
- [ ] Mobile responsive (hoy es desktop-only)
- [ ] Persistencia histórica de snapshots (para evolución de rotación)

## Ideas de v2 (no empezar sin pedir)

- Netflows on-chain de cripto (requiere fuente aparte tipo Glassnode; hoy cripto
  no tiene capa de dinero observado, solo precio/RS).
- Persistencia histórica de snapshots para ver evolución de la rotación.

---

## Cómo NO ayudar acá

- No metas la API key en el frontend ni en ningún archivo versionado.
- No conviertas paneles inferidos (RS/CMF/RORO) en afirmaciones de flujo de dinero.
- No agregues dependencias pesadas sin avisar (el front es vanilla a propósito).
- No presentes código sin la auditoría línea por línea.
- No cambies el contrato JSON de un lado sin actualizar los tres puntos que lo
  producen/consumen: `app.py`, `demo_data.py`, `static/index.html`.
