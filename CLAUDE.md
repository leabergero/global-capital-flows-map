# CLAUDE.md — Global Flow Matrix

Guía para trabajar en este repo. **Leé esto entero antes de tocar código.**

Hay decisiones de diseño deliberadas que NO se deben romper sin avisar.

---

## Qué es

Terminal cross-asset que visualiza **rotación de capital** entre clases de activo, sectores e industrias. Dos capas:

- **Backend Flask** (`app.py`): ingiere datos de yfinance + FRED + Quandl + OpenBB, calcula los modelos, cachea y expone un único JSON en `/api/snapshot`.
- **Frontend** (`static/index.html`): vanilla JS + SVG inline, solo pinta el JSON. Sin frameworks, sin build step, un solo archivo.

Las API keys (todas opcionales, todas gratis) viven **solo** en el backend (variables de entorno). Nunca en el frontend.

---

## Comandos

```bash
# correr (crea venv, instala deps, arranca en :5000)
bash run.sh

# manual
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py                       # http://127.0.0.1:5000

# verificar que compila todo
python -m py_compile *.py compute/*.py

# probar el camino LIVE sin keys (yfinance es gratis, todo funciona)
python -c "import snapshot_builder as sb; print(sb.live_snapshot(180)['meta']['mode'])"

# forzar recálculo de snapshots ensamblados (macro/cot/news, TTL corto)
rm -rf cache/*.json

# forzar re-siembra completa de precios (borra las bases de 6m e intradía)
rm -f data/price_history.json data/intraday_bars.json

# forzar los jobs de cron a mano, sin esperar al horario de mercado
python -c "import preload_cache; preload_cache.job_market_close_update()"
python -c "import preload_cache; preload_cache.job_intraday_update()"

# capturar snapshot de flujo ETF (acumulativo, idempotente)
python scrape_etf_flows.py
```

> **Reiniciar el server**: usá `fuser -k 5000/tcp` para liberar el puerto, NO
> `pkill -f "python app.py"` — ese patrón coincide con el propio comando del shell
> y se auto-mata (exit 144).

**Modo**: Siempre **LIVE** con yfinance (gratis, sin API key).
- Con `FRED_API_KEY` → indicadores económicos en vivo
- Con `QUANDL_API_KEY` → COT en vivo
- Sin ellas → esos paneles usan demo/fallback

---

## Deploy (producción)

Vive en **https://flow.quantcentral.eu**, en el mismo Oracle Cloud (`152.70.14.73`)
donde corre otro proyecto del usuario (Neural, puerto `:5000`) — conviven en la
misma VM sin compartir nada más que nginx: servicio, venv, directorio, subdominio
y cert propios.

- Server: usuario **`ubuntu`** (no `leandro` — la imagen es Ubuntu 24.04 Minimal
  y ese es el usuario de la instancia), repo en `/home/ubuntu/global-flow-matrix`.
  `bash DEPLOY_ORACLE.sh` automatiza `git pull` + `pip install` + `sudo systemctl
  restart global-flow-matrix.service` + espera activa del health-check.
- `app.py` lee `HOST`/`PORT` de variables de entorno (default `127.0.0.1:5000`
  igual que local); en el server el `.service` fija `PORT=5001`.
- `config.MAX_WORKERS` también por env (default `8`); en el server va en `3`
  porque la VM es chica (1 OCPU/1GB + 2GB de swap) y con el default original
  una primera carga live sin caché disparó ~40 llamadas concurrentes que
  saturaron la VM entera (OOM-killer se llevó puesto el otro proyecto).
- El arranque del proceso (`app._init_scheduler`) siembra/actualiza los stores
  de precios de forma SÍNCRONA antes de que Flask acepte conexiones — en un
  primer deploy sin `data/price_history.json` esto puede tardar varios minutos
  (~4 min visto en producción con `MAX_WORKERS=3`, 140 símbolos). Es esperado,
  no un cuelgue; `DEPLOY_ORACLE.sh` hace polling activo del health-check en
  vez de un `sleep` fijo por esto mismo.
- Cron diario (`flock`) corriendo `scrape_etf_flows.py` en el server — el
  anacron local de abajo es solo para la máquina de desarrollo del usuario.

---

## Estado actual (2026-06-29)

✅ **Completado**:
- RRG interactivo: click en título de cuadrante aísla ese cuadrante; click en
  nombre de sector lo aísla; click en fondo limpia. Leyenda de tiempo arriba
  (1 lectura = 1 día/semana/10 días). Flecha de dirección en nodo actual.
- Heatmap con glow dinámico (rojo/verde) en TODOS los tiles, incluidas hojas
  (`.tile.leaf:hover` también tiene glow — Bonos/Divisas).
- Régimen "de mercado" (RORO) con BULLISH/BEARISH, glow latente y tooltip.
- SPY/10Y UST gauge: barra vertical, escala dinámica, glow latente, tooltip.
- Gold/Silver ratio calculado desde Oro y Plata.
- 17 KPIs macro con tooltips visuales, organizados por categoría.
- Tooltips visuales (no `title` nativo) en: régimen, métricas del heatmap,
  SPY/10Y UST. Disparados con `.regime-info:hover`, `#metricSeg button:hover`.
  Ojo: `overflow:hidden` en contenedores recorta tooltips — `#metricSeg` lleva
  `overflow:visible`.
- COT marcado SEMANAL (LED stale, no live: el dato del CFTC es semanal).
- Nomenclatura: **10Y UST** en lugar de TLT (estándar de industria).
- Flujo ETF: histórico propio acumulado (`etf_flow_tracker.py` +
  `scrape_etf_flows.py`), porque FMP `/etf/holdings` es premium. Fallback en
  `_build_node`: si FMP da None, usa `etf_tracker.flow_window(sym, period)`.
- Frontend vanilla JS + SVG (sin build). Auto-reload cada 1 hora.
- Carga inteligente: 5d inmediatamente, 20d/50d en background.
- Copyright: Leandro R. Bergero, Msc Finance & Banking BSM-UPF.
- Fase 4: store de precios con ventana fija (320 barras diarias, 3 días de
  velas de 15min para 1d) + cron real de mercado (cierre 17:00 ET, intradía
  c/15min 9:30–16:00 ET) — ver sección dedicada más abajo. Las 5 ventanas
  quedan precacheadas antes de que el usuario entre, en vez de recomputarse
  on-demand con TTL de 1h.

---

## Store de precios — ventana fija + cron real de mercado (Fase 4)

Reemplazó el caché de históricos por TTL relativo (expiraba cada 1h; el
próximo usuario después de la expiración pagaba el costo de recomputar en su
propia request). Ahora hay una base persistente por símbolo, de tamaño
constante, actualizada por eventos reales de mercado en vez de por tiempo:

- `price_store.py`: `data/price_history.json`, **320 barras de trading**
  por símbolo (poda FIFO al agregar el cierre de hoy). 320 y no ~260 (que
  parecía alcanzar por la validación superficial de `compute/rrg.py`) porque
  el RRG hace un rolling DOBLE (uno para `rs_ratio`, otro para `rs_mom` sobre
  el `diff()` de ese ratio) — el período 180d (`rrg_window=144`) necesita
  ~2×window+tail ≈ 293 filas válidas, no `window+tail+2`. Actualizado 1x/día
  por el job de cierre.
- `intraday_store.py`: `data/intraday_bars.json`, velas reales de 15 min
  (yfinance `interval="15m"`) solo para el período **1d** — antes usaba la
  misma barra diaria recortada a 5 lecturas. Conserva los últimos **3 días
  hábiles** (podado por fecha, no reseteado a 0 cada mañana): un solo día da
  ~26 barras, insuficiente para el rolling apenas abre el mercado.
- `snapshot_builder.py`: ensamblado del snapshot (`live_snapshot`,
  `build_node`, `build_and_cache`) vive acá y no en `app.py`, para que
  `preload_cache.py` pueda invocarlo desde los jobs de cron sin crear un
  ciclo de imports (`app` → `preload_cache` → `app`).
- Dos jobs en el `BackgroundScheduler` de `app.py` (timezone
  **`America/New_York`** explícito — sin esto, el cron corre en la hora local
  del SO del servidor, no en horario de mercado real):
  - `job_market_close_update` (17:00 ET, 1h post-cierre NYSE, lun-vie):
    actualiza `price_store` y recalcula+cachea `snapshot:full:{5,20,50,180}`.
  - `job_intraday_update` (cada 15 min, 9:30–16:00 ET, lun-vie): actualiza
    `intraday_store` y recalcula+cachea solo `snapshot:full:1`.
- `fmp_client.historical()` es ahora un delegado fino de `price_store.get()`
  (sin red en el hot path salvo la siembra lazy de un símbolo nunca visto);
  `fmp_client.historical_intraday()` lee `intraday_store` con fallback a
  `price_store` si aún no corrió el job del día (server recién levantado,
  deploy fuera de horario de mercado).
- yfinance a veces devuelve la barra más reciente con OHLC en `NaN` (vela del
  día aún sin cerrar) — ambos stores la descartan explícitamente
  (`math.isnan(close)`); sin ese filtro se cuela como un cierre inválido.
- `get()` en ambos stores cachea el dict completo en memoria (invalidado por
  `mtime` del archivo) — sin esto, cada llamada (docenas por snapshot: una
  por símbolo del árbol, más RRG, más ROTO) releía y re-parseaba el JSON
  entero del disco, dominando el tiempo de ensamblado (bajó un snapshot de
  ~78s a ~44s en pruebas locales).

---

## Flujo ETF — scraper propio (capa de dinero observado)

FMP `/etf/holdings` es premium (429 en plan gratuito). Ninguna fuente gratuita da
el histórico de shares/AUM de un ETF, así que se construye **hacia adelante**:

- `etf_flow_tracker.py`: captura shares × NAV vía yfinance, acumula en
  `data/etf_flows.json`. `flujo_t = (shares_t − shares_{t-1}) × NAV_t`.
  Fallback `totalAssets/NAV` para ETF menos líquidos → cobertura 43/43.
- `scrape_etf_flows.py`: corre 1x/día. Las ventanas 5/20/50 se llenan con el
  tiempo (día 6 → 5d, día 21 → 20d, día 51 → 50d).
- Automatizado con **anacron** (recupera corridas si la máquina estuvo apagada):
  `~/.anacron/etc/anacrontab` + disparadores cron `@reboot` y `0 21 * * *`.
- `data/*.json` NO se versiona (es histórico local; ver `.gitignore`).

---

## Disciplina conceptual — NO romper

Separa inferencia vs observación:

| Capa | Modelos | Lectura | Afirmar… |
|------|---------|---------|----------|
| **Inferida** | RRG, CMF, RORO | "fuerza" / "presión" | NUNCA "entró/salió capital" |
| **Observada** | Flujo ETF, COT | dinero medido | "el capital se movió" |

---

**Última actualización:** 2026-07-26
**Estado:** ✅ Production-ready — deployado en https://flow.quantcentral.eu
