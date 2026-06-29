#!/usr/bin/env python3
"""
Captura el snapshot diario de flujo de ETF. Correr 1x/día (cron).

    python scrape_etf_flows.py

Acumula shares outstanding × NAV de cada ETF del universo en data/etf_flows.json.
El histórico se construye hacia adelante: las ventanas 5/20/50 quedan disponibles
a medida que pasan los días (ver etf_flow_tracker.py para el detalle).

Cron sugerido (todos los días hábiles a las 18:00, tras el cierre US):
    0 18 * * 1-5  cd /ruta/flujos-globales && .venv/bin/python scrape_etf_flows.py
"""
import etf_flow_tracker as tracker
import universe


def etf_symbols():
    """Símbolos de los nodos ETF del árbol (los que tienen creación/redención)."""
    out = set()

    def walk(n):
        if n.get("etf") and n.get("symbol"):
            out.add(n["symbol"])
        for c in (n.get("children") or []):
            walk(c)

    walk(universe.TREE)
    return sorted(out)


if __name__ == "__main__":
    syms = etf_symbols()
    captured, total = tracker.snapshot(syms)
    depth = tracker.history_depth()
    print(f"Snapshot tomado: {captured}/{total} ETFs capturados.")
    print(f"Histórico acumulado: {depth} día(s).")
    ready = [w for w in tracker.WINDOWS if depth > w]
    if ready:
        print(f"Ventanas disponibles: {', '.join(f'{w}d' for w in ready)}.")
    else:
        nxt = min(tracker.WINDOWS)
        print(f"Aún sin ventanas completas (faltan {nxt + 1 - depth} día/s "
              f"para la primera de {nxt}d).")
