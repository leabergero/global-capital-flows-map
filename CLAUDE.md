# CLAUDE.md — Mapa de Flujos Globales

Guía para trabajar en este repo. **Leé esto entero antes de tocar código.**
Hay decisiones de diseño deliberadas que NO se deben romper sin avisar.

---

## Qué es

Terminal cross-asset que visualiza **rotación de capital** entre clases de activo,
sectores e industrias. Dos capas:

- **Backend Flask** (`app.py`): ingiere datos de FMP (+ OpenBB opcional), calcula
  los modelos, cachea y expone un único JSON en `/api/snapshot`.
- **Frontend** (`static/index.html`): vanilla JS + SVG inline, solo pinta el JSON.
  Sin frameworks, sin build step, un solo archivo.

La API key vive **solo** en el backend (variable de entorno). Nunca en el frontend.

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

# probar el camino LIVE sin key válida (todo cae a demo, no debe romper)
FMP_API_KEY=dummy python -c "import app; print(app._live_snapshot()['meta']['mode'])"

# forzar recálculo (borrar caché)
rm -f cache/*.json
```

Sin `.env` o con el placeholder `tu_key_regenerada` → arranca en **modo DEMO**
(datos sintéticos de `demo_data.py`). Con key real → modo LIVE.

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
  "roro":  [ ["SPY / TLT", 0.9], ... ],          // [nombre, z-score]
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

## Capa de datos (FMP) — dónde está la fragilidad

Endpoints en uso (todos en `fmp_client.py`, fáciles de reasignar):

| Método | Endpoint | Robustez |
|--------|----------|----------|
| `historical()` | `v3/historical-price-full/{sym}` | alta (workhorse: RRG, CMF, RORO, macro) |
| `quote()` | `v3/quote/{sym}` | alta |
| `etf_holdings()` / `etf_holding_dates()` | `stable/etf/holdings` | media (puede ser premium) |
| `cot()` | `v4/commitment_of_traders_report/{sym}` | baja (varía por plan) |
| `economic()` | `v4/economic?name=` | baja (varía por plan) |

**Si algo sale mal, casi siempre se arregla en `config.py`, no en la lógica:**
- Tarjeta macro en `n/d` → la convención del símbolo difiere. Ajustá `MACRO_CARDS`
  (probá los `alt`, ej. WTI: `CLUSD`/`WTIUSD`/`USO`). Símbolos de índices como
  `^TNX`, `^DXY` dependen del plan.
- Panel COT vacío → revisá `COT_SYMBOLS` y la lista de nombres de campo en
  `compute/cot.py` (`_LONG`, `_SHORT`, etc.; cambian entre versiones del endpoint).
- Flujo ETF todo en `—` → el plan quizá no expone `/etf/holdings` histórico, o
  el ETF no tiene dos fechas de corte. Es la capa más sensible al plan.

La estrategia es iterativa: correr con la key real, ver qué secciones salen
`parcial` (badge + `meta.notes`) y ajustar símbolos/endpoints. El core (RRG/CMF/
RORO/macro vía precio) corre con los endpoints de alta robustez.

---

## Pendientes / decisiones abiertas

- [ ] **Benchmark RRG cross-asset**: `BENCH_CROSS = "ACWI"` por default en
      `config.py`. Evaluar `URTH` o `VT`. (Sectores usa `SPY`, eso queda.)
- [ ] **COT**: confirmar nombres de campo reales contra la cuenta FMP y fijarlos.
- [ ] **Símbolos commodities/índices**: validar `CLUSD/BZUSD/^TNX/GCUSD/^DXY`
      contra el plan; ajustar `MACRO_CARDS`.
- [ ] **OpenBB**: opcional y pesado, comentado en `requirements.txt`. Sin él,
      noticias caen a FMP e indicadores a FMP economic. Activar solo si hace falta.
- [ ] **RORO**: `maxAbs` del frontend es 1.5; los z reales pueden superarlo (se
      clampean a ±3 en backend). Si se ven barras saturadas, subir el `maxAbs`
      del `renderBars('roroBars', ...)` en `static/index.html`.

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
