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
    captured, total, backfilled = tracker.snapshot(syms)
    cov = tracker.coverage()
    print(f"Snapshot tomado: {captured}/{total} ETFs capturados "
          f"({backfilled} con histórico completo de SSGA).")

    # Los SPDR llegan con histórico; el resto se acumula de a un día, así que
    # lo útil es cuántos símbolos tienen ya cada ventana, no la profundidad máx.
    for w in tracker.WINDOWS:
        listos = [s for s, n in cov.items() if n > w]
        print(f"  ventana {w:>3}d: {len(listos):>2}/{total} símbolos")
    faltan = sorted(s for s, n in cov.items() if n <= min(tracker.WINDOWS))
    if faltan:
        print(f"Acumulando hacia adelante (sin histórico gratuito): "
              f"{', '.join(faltan)}")
