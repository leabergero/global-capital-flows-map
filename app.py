"""
Backend Flask de Global Flow Matrix.

Rutas:
  GET /                -> sirve el dashboard (static/index.html)
  GET /api/snapshot    -> JSON con todos los paneles
  GET /api/health      -> estado + modo (live/demo)

Filosofía: si no hay key -> DEMO. Si hay key, se construye en vivo pero CADA
sección está blindada: si una llamada a FMP falla, esa sección cae a demo y se
anota en meta.notes; el resto sigue en vivo. La key nunca llega al navegador.
"""
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler

from flask import Flask, jsonify, send_from_directory, request

import config
import cache
import universe
import demo_data
import fmp_client as fmp
import etf_flow_tracker as etf_tracker
import preload_cache
from compute import rrg, cmf, flows, roro, cot, macro, news

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")

app = Flask(__name__, static_folder="static", static_url_path="")


# ---------------------------------------------------------------------------
# Prefetch de históricos (paraleliza la primera carga; luego pega a caché disco)
# ---------------------------------------------------------------------------
def _prefetch(symbols):
    with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as ex:
        list(ex.map(lambda s: fmp.historical(s), symbols))


def _lookup(sym):
    return fmp.historical(sym)


# ---------------------------------------------------------------------------
# Árbol en vivo
# ---------------------------------------------------------------------------
def _agg(children, key):
    """Promedio ponderado por w de una métrica entre hijos (ignora None)."""
    num = den = 0.0
    for c in children:
        v = c.get(key)
        if v is None:
            continue
        w = c.get("w", 1) or 1
        num += v * w
        den += w
    return round(num / den, 2) if den else None


def _build_node(node, bench_bars, rrg_window=None, rrg_tail=None, flow_days=5):
    if rrg_window is None:
        rrg_window = config.RRG_WINDOW
    if rrg_tail is None:
        rrg_tail = config.RRG_TAIL

    kids = node.get("children")
    built = [_build_node(c, bench_bars, rrg_window, rrg_tail, flow_days) for c in kids] if kids else None

    rs = mom = cmf_v = None
    flow_m = None                       # flujo en MILLONES de USD (unidad única)
    sym = node.get("symbol")
    if sym:
        bars = _lookup(sym)
        pt = rrg.point(bars, bench_bars, window=rrg_window, tail=rrg_tail)
        if pt:
            rs, mom = pt["rs"], pt["mom"]
        cmf_v = cmf.cmf(bars)
        if node.get("etf"):
            raw = flows.implied_flow(sym, bars)   # USD crudo (FMP, premium)
            if raw is None:
                # Fallback gratuito: histórico acumulado por scrape_etf_flows.py
                raw = etf_tracker.flow_window(sym, flow_days)
            if raw is not None:
                flow_m = round(raw / 1e6, 1)      # -> millones (una sola vez)

    # completar huecos con la agregación de hijos
    if built:
        if rs is None:
            rs = _agg(built, "rs")
        if mom is None:
            mom = _agg(built, "mom")
        if cmf_v is None:
            cmf_v = _agg(built, "cmf")
        if flow_m is None:
            # los hijos ya vienen en millones: se suman directo, sin re-dividir
            child_flows = [c["flow"] for c in built if c.get("flow") is not None]
            flow_m = round(sum(child_flows), 1) if child_flows else None

    return {
        "name": node["name"],
        "rs": rs if rs is not None else 100.0,
        "mom": mom if mom is not None else 100.0,
        "cmf": cmf_v if cmf_v is not None else 0.0,
        "flow": flow_m,                 # ya en millones de USD (o None)
        "w": node.get("w", 1),
        "children": built,
    }


# ---------------------------------------------------------------------------
# Snapshot en vivo, sección por sección y blindado
# ---------------------------------------------------------------------------
def _live_snapshot(period_days=None):
    notes = []
    demo = demo_data.snapshot("demo")  # fuente de fallback por sección

    # Mapear período a window/tail del RRG
    if period_days is None:
        period_days = 5
    period_map = {5: (12, 5), 20: (30, 5), 50: (60, 5)}
    rrg_window, rrg_tail = period_map.get(period_days, (12, 5))

    _prefetch(universe.all_symbols())
    bench_eq = _lookup(config.BENCH_EQUITY)
    bench_cross = _lookup(config.BENCH_CROSS) or bench_eq

    def safe(section, fn, fallback):
        try:
            val = fn()
            if val in (None, [], {}):
                raise ValueError("vacío")
            return val
        except Exception as e:
            log.warning("sección '%s' -> demo :: %s", section, e)
            notes.append(f"{section}: sin datos en vivo (fallback demo)")
            return fallback

    tree = safe("tree", lambda: _build_node(universe.TREE, bench_eq, rrg_window, rrg_tail, period_days), demo["tree"])
    rrg_sec = safe("rrg.sectores",
                   lambda: rrg.dataset(universe.RRG_SECTORES, bench_eq, _lookup,
                                      window=rrg_window, tail=rrg_tail),
                   demo["rrg"]["sectores"])
    rrg_cross = safe("rrg.cross",
                     lambda: rrg.dataset(universe.RRG_CROSS, bench_cross, _lookup,
                                        window=rrg_window, tail=rrg_tail),
                     demo["rrg"]["cross"])
    roro_rows, comp = safe("roro", lambda: roro.components(_lookup, window=rrg_window),
                           (demo["roro"], None))
    if comp is None:
        comp = round(sum(r[1] for r in roro_rows) / len(roro_rows), 2) if roro_rows else 0.0
    regime = roro.regime(comp)
    cot_tbl = safe("cot", lambda: cot.table(config.COT_SYMBOLS), demo["cot"])
    macro_cards = safe("macro", macro.cards, demo["macro"])
    news_items = safe("news", lambda: news.headlines(6), demo["news"])

    from datetime import datetime, timezone
    mode = "live" if not notes else "parcial"
    if not notes:
        notes = ["Datos en vivo vía FMP" +
                 (" + OpenBB" if _openbb_available() else "") + "."]
    return {
        "meta": {"mode": mode,
                 "generated": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
                 "notes": notes,
                 "etf_flow_depth": etf_tracker.history_depth()},
        "regime": regime,
        "rrg": {"sectores": rrg_sec, "cross": rrg_cross},
        "roro": roro_rows,
        "cot": cot_tbl,
        "tree": tree,
        "macro": macro_cards,
        "news": news_items,
    }


def _openbb_available():
    try:
        import openbb  # noqa: F401
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Scheduler: precarga automática (sin bloquear Flask)
# ---------------------------------------------------------------------------
_scheduler = None


def _init_scheduler():
    """Inicializa el scheduler de precarga automática (una sola vez al startup)."""
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        return  # Ya está en marcha

    _scheduler = BackgroundScheduler()

    # Precarga inicial: todos los símbolos (paralelizada)
    try:
        log.info("Precarga inicial: calentando caché...")
        ok, fail, elapsed = preload_cache.warm_cache(verbose=True)
    except Exception as e:
        log.warning("Precarga inicial no completó: %s (continuando)", e)

    # Job recurrente: cada 20 min durante horario de mercado (09:30 - 16:00 EST)
    _scheduler.add_job(
        preload_cache.job_warm_cache,
        'cron',
        hour='9-16',
        minute='*/20',
        id='preload_cache_job',
        replace_existing=True,
    )

    try:
        _scheduler.start()
        log.info("Scheduler iniciado: precarga cada 20 min (09:30-16:00 EST)")
    except Exception as e:
        log.error("Error al iniciar scheduler: %s", e)


# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/snapshot")
def snapshot():
    period = int(request.args.get("period", 5))
    if period not in (5, 20, 50):
        period = 5

    if config.DEMO_MODE:
        data = demo_data.snapshot(
            "demo", ["Modo DEMO: sin FMP_API_KEY. Datos sintéticos. "
                     "Poné tu key en .env para datos reales."])
        return jsonify(data)

    cache_key = f"snapshot:full:{period}"
    cached = cache.get(cache_key)
    if cached is not None:
        return jsonify(cached)
    data = _live_snapshot(period_days=period)
    cache.set(cache_key, data, config.TTL["snapshot"])
    return jsonify(data)


@app.route("/api/health")
def health():
    return jsonify({"ok": True,
                    "mode": "demo" if config.DEMO_MODE else "live",
                    "openbb": _openbb_available()})


if __name__ == "__main__":
    mode = "DEMO (sin key)" if config.DEMO_MODE else "LIVE (FMP)"
    log.info("Arrancando Global Flow Matrix en modo %s", mode)

    # Inicializar scheduler de precarga (si no estamos en DEMO_MODE)
    if not config.DEMO_MODE:
        _init_scheduler()
    else:
        log.info("Scheduler deshabilitado (modo DEMO)")

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    app.run(host=host, port=port, debug=False)
