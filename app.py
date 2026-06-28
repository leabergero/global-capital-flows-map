"""
Backend Flask del Mapa de Flujos Globales.

Rutas:
  GET /                -> sirve el dashboard (static/index.html)
  GET /api/snapshot    -> JSON con todos los paneles
  GET /api/health      -> estado + modo (live/demo)

Filosofía: si no hay key -> DEMO. Si hay key, se construye en vivo pero CADA
sección está blindada: si una llamada a FMP falla, esa sección cae a demo y se
anota en meta.notes; el resto sigue en vivo. La key nunca llega al navegador.
"""
import logging
from concurrent.futures import ThreadPoolExecutor

from flask import Flask, jsonify, send_from_directory

import config
import cache
import universe
import demo_data
import fmp_client as fmp
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


def _build_node(node, bench_bars):
    kids = node.get("children")
    built = [_build_node(c, bench_bars) for c in kids] if kids else None

    rs = mom = cmf_v = None
    flow_m = None                       # flujo en MILLONES de USD (unidad única)
    sym = node.get("symbol")
    if sym:
        bars = _lookup(sym)
        pt = rrg.point(bars, bench_bars)
        if pt:
            rs, mom = pt["rs"], pt["mom"]
        cmf_v = cmf.cmf(bars)
        if node.get("etf"):
            raw = flows.implied_flow(sym, bars)   # USD crudo
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
def _live_snapshot():
    notes = []
    demo = demo_data.snapshot("demo")  # fuente de fallback por sección

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

    tree = safe("tree", lambda: _build_node(universe.TREE, bench_eq), demo["tree"])
    rrg_sec = safe("rrg.sectores",
                   lambda: rrg.dataset(universe.RRG_SECTORES, bench_eq, _lookup),
                   demo["rrg"]["sectores"])
    rrg_cross = safe("rrg.cross",
                     lambda: rrg.dataset(universe.RRG_CROSS, bench_cross, _lookup),
                     demo["rrg"]["cross"])
    roro_rows, comp = safe("roro", lambda: roro.components(_lookup),
                           (demo["roro"], None))
    if comp is None:
        comp = round(sum(r[1] for r in roro_rows) / len(roro_rows), 2) if roro_rows else 0.0
    regime = roro.regime(comp)
    cot_tbl = safe("cot", lambda: cot.table(config.COT_SYMBOLS), demo["cot"])
    macro_cards = safe("macro", macro.cards, demo["macro"])
    news_items = safe("news", lambda: news.headlines(6), demo["news"])

    from datetime import datetime
    mode = "live" if not notes else "parcial"
    if not notes:
        notes = ["Datos en vivo vía FMP" +
                 (" + OpenBB" if _openbb_available() else "") + "."]
    return {
        "meta": {"mode": mode,
                 "generated": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                 "notes": notes},
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
# Rutas
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/snapshot")
def snapshot():
    if config.DEMO_MODE:
        data = demo_data.snapshot(
            "demo", ["Modo DEMO: sin FMP_API_KEY. Datos sintéticos. "
                     "Poné tu key en .env para datos reales."])
        return jsonify(data)
    cached = cache.get("snapshot:full")
    if cached is not None:
        return jsonify(cached)
    data = _live_snapshot()
    cache.set("snapshot:full", data, config.TTL["snapshot"])
    return jsonify(data)


@app.route("/api/health")
def health():
    return jsonify({"ok": True,
                    "mode": "demo" if config.DEMO_MODE else "live",
                    "openbb": _openbb_available()})


if __name__ == "__main__":
    mode = "DEMO (sin key)" if config.DEMO_MODE else "LIVE (FMP)"
    log.info("Arrancando Mapa de Flujos Globales en modo %s", mode)
    app.run(host="127.0.0.1", port=5000, debug=False)
