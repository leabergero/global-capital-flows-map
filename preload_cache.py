"""
Precarga automática de caché — mantiene el servidor con datos frescos.

El flujo:
  1. Startup: precarga paralela de TODOS los símbolos (ETFs + sectores + macro)
  2. Background: cada 20 min (durante horario de mercado) refresca históricos
  3. Resultado: /api/snapshot sirve DESDE CACHÉ (sin latencia de red)

Sin esto, cada cambio de ventana temporal (5d → 20d → 50d) y cada usuario
nuevo genera llamadas síncronas a FMP en vivo, saturando la VM pequeña.
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import config
import universe
import fmp_client as fmp

log = logging.getLogger("preload")


def all_symbols_with_macro():
    """Símbolos del árbol + macro KPIs + benchmarks RRG."""
    symbols = set(universe.all_symbols())

    # Benchmarks del RRG
    symbols.add(config.BENCH_EQUITY)
    symbols.add(config.BENCH_CROSS)

    # Macro KPIs
    for card in config.MACRO_CARDS:
        if card.get("symbol"):
            symbols.add(card["symbol"])
        # Fallback alternos
        if card.get("alt"):
            symbols.update(card["alt"])

    # RORO componentes
    for comp in config.RORO_COMPONENTS:
        if comp.get("a"):
            symbols.add(comp["a"])
        if comp.get("b"):
            symbols.add(comp["b"])

    return sorted(symbols)


def warm_cache(verbose=False):
    """
    Precarga paralela de históricos (5d + 200d para RRG/CMF/RORO).
    Retorna (count_ok, count_fail, elapsed_sec).
    """
    symbols = all_symbols_with_macro()
    total = len(symbols)

    if verbose:
        log.info("Iniciando precarga: %d símbolos", total)

    start = time.time()
    ok = fail = 0

    try:
        with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as ex:
            futures = {ex.submit(fmp.historical, s): s for s in symbols}

            for future in futures:
                try:
                    bars = future.result(timeout=30)
                    if bars is not None and len(bars) > 0:
                        ok += 1
                    else:
                        fail += 1
                except Exception as e:
                    fail += 1
                    if verbose:
                        sym = futures[future]
                        log.debug("Error precargando %s: %s", sym, e)
    except Exception as e:
        log.error("Precarga abortada: %s", e)
        return 0, total, time.time() - start

    elapsed = time.time() - start

    if verbose:
        log.info("Precarga completada: %d OK, %d failed en %.1f seg", ok, fail, elapsed)

    return ok, fail, elapsed


def job_warm_cache():
    """
    Job recurrente: precarga cada 20 min sin bloquear.
    Se ejecuta en background (no afecta a las rutas Flask).
    """
    try:
        ok, fail, elapsed = warm_cache(verbose=True)
        if fail > 0:
            log.warning("Precarga parcial: %d fallaron (posiblemente fuera de horario o red)", fail)
    except Exception as e:
        log.error("Job precarga falló: %s", e)
