"""
Ensamblado del snapshot en vivo (árbol + RRG + ROTO + COT + macro + noticias).

Vive en un módulo propio (separado de app.py) para que `preload_cache.py`
pueda invocar `build_and_cache()` desde los jobs de cron sin crear un ciclo de
imports (app.py importa preload_cache; si preload_cache importara app.py de
vuelta, sería circular).

Todo lo que antes recibía la función global `_lookup` (app.py) ahora recibe
el lookup como parámetro explícito: `fmp.historical` (diario, default) o
`fmp.historical_intraday` (velas de 15 min, solo para period=1).
"""
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import config
import cache
import universe
import demo_data
import fmp_client as fmp
import etf_flow_tracker as etf_tracker
from compute import rrg, cmf, flows, roro, cot, macro, news

log = logging.getLogger("snapshot_builder")

# Mapea período (días) -> (rrg_window, rrg_tail). 1d usa velas de 15 min
# (ver config.RRG_INTRADAY_WINDOW/TAIL); el resto, cierres diarios.
PERIOD_MAP = {
    1:   (config.RRG_INTRADAY_WINDOW, config.RRG_INTRADAY_TAIL),
    5:   (12, 5),
    20:  (30, 5),
    50:  (60, 5),
    180: (144, 5),
}


def _lookup_for(period_days):
    return fmp.historical_intraday if period_days == 1 else fmp.historical


def prefetch(symbols, lookup=None):
    lookup = lookup or fmp.historical
    with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as ex:
        list(ex.map(lambda s: lookup(s), symbols))


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


def build_node(node, bench_bars, lookup, rrg_window=None, rrg_tail=None, flow_days=5):
    if rrg_window is None:
        rrg_window = config.RRG_WINDOW
    if rrg_tail is None:
        rrg_tail = config.RRG_TAIL

    kids = node.get("children")
    built = [build_node(c, bench_bars, lookup, rrg_window, rrg_tail, flow_days)
             for c in kids] if kids else None

    rs = mom = cmf_v = None
    flow_m = None                       # flujo en MILLONES de USD (unidad única)
    sym = node.get("symbol")
    if sym:
        bars = lookup(sym)
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


def _openbb_available():
    try:
        import openbb  # noqa: F401
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Snapshot en vivo, sección por sección y blindado
# ---------------------------------------------------------------------------
def live_snapshot(period_days=None, lookup=None):
    notes = []
    demo = demo_data.snapshot("demo")  # fuente de fallback por sección

    if period_days is None:
        period_days = 5
    lookup = lookup or _lookup_for(period_days)
    rrg_window, rrg_tail = PERIOD_MAP.get(period_days, (12, 5))

    prefetch(universe.all_symbols(), lookup=lookup)
    bench_eq = lookup(config.BENCH_EQUITY)
    bench_cross = lookup(config.BENCH_CROSS) or bench_eq

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

    tree = safe("tree", lambda: build_node(universe.TREE, bench_eq, lookup, rrg_window, rrg_tail, period_days), demo["tree"])
    rrg_sec = safe("rrg.sectores",
                   lambda: rrg.dataset(universe.RRG_SECTORES, bench_eq, lookup,
                                      window=rrg_window, tail=rrg_tail),
                   demo["rrg"]["sectores"])
    rrg_cross = safe("rrg.cross",
                     lambda: rrg.dataset(universe.RRG_CROSS, bench_cross, lookup,
                                        window=rrg_window, tail=rrg_tail),
                     demo["rrg"]["cross"])
    roro_rows, comp = safe("roro", lambda: roro.components(lookup, window=rrg_window),
                           (demo["roro"], None))
    if comp is None:
        comp = round(sum(r[1] for r in roro_rows) / len(roro_rows), 2) if roro_rows else 0.0
    regime = roro.regime(comp)
    cot_tbl = safe("cot", lambda: cot.table(config.COT_SYMBOLS), demo["cot"])
    macro_cards = safe("macro", macro.cards, demo["macro"])
    news_items = safe("news", lambda: news.headlines(6), demo["news"])

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


def build_and_cache(period_days):
    """Construye el snapshot de un período y lo cachea bajo snapshot:full:{period}.

    Punto único usado tanto por la ruta /api/snapshot (fallback síncrono) como
    por los jobs de cron (preload_cache.job_market_close_update /
    job_intraday_update) para mantener el caché siempre caliente.
    """
    data = live_snapshot(period_days, lookup=_lookup_for(period_days))
    cache.set(f"snapshot:full:{period_days}", data, config.TTL["snapshot"])
    return data
