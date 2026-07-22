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
python -c "import app; print(app._live_snapshot()['meta']['mode'])"

# forzar recálculo (borrar caché)
rm -rf cache/*.json

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

**Última actualización:** 2026-06-29
**Estado:** ✅ Production-ready
