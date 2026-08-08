"""
Jobs de actualización de mercado — mantienen el servidor con datos frescos
SIN depender de TTL relativo.

El flujo:
  1. Job de cierre (17:00 ET, 1h post-cierre NYSE, lun-vie): actualiza el
     store diario de precios (price_store) para TODOS los símbolos y
     recalcula+cachea los snapshots de 5d/20d/50d/180d.
  2. Job intradía (cada 60 min, 9:00-16:00 ET, lun-vie): actualiza el store
     de velas de 15 min (intraday_store) y recalcula+cachea el snapshot 1d.
  3. Resultado: /api/snapshot SIEMPRE sirve desde caché ya caliente — nadie
     paga el costo de recomputar en su propia request, salvo que un job haya
     fallado por completo (fallback síncrono como red de seguridad).

Sin esto, el TTL relativo de 1h dejaba que el próximo usuario después de cada
expiración pagara la recomputación, saturando la VM pequeña bajo carga.
"""
import logging

import config
import universe
import price_store
import intraday_store

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


def intraday_symbols():
    """Símbolos que de verdad consumen `intraday_store` en period=1.

    A diferencia de `all_symbols_with_macro()` (usado por el job de cierre),
    NO incluye los símbolos de MACRO_CARDS: esas tarjetas salen de
    `fmp.quote()` (vivo) + `fmp.historical()` (diario) en `compute/macro.py`,
    nunca pasan por `intraday_store` — traerlos acá era puro gasto de cupo
    contra Yahoo sin ningún efecto visible. Sí quedan los componentes RORO
    (`roro.components()` recibe el `lookup` de period=1) y el benchmark cross
    del RRG (ACWI, se pide vía `lookup` directo aunque no esté en el árbol).
    """
    symbols = set(universe.all_symbols())
    symbols.add(config.BENCH_CROSS)
    for comp in config.RORO_COMPONENTS:
        if comp.get("a"):
            symbols.add(comp["a"])
        if comp.get("b"):
            symbols.add(comp["b"])
    return sorted(symbols)


def job_market_close_update():
    """
    Job de cierre de mercado: 17:00 ET, lunes a viernes (1h post-cierre NYSE).
    Actualiza el store diario de precios para TODOS los símbolos y recalcula
    + cachea los snapshots de 5d/20d/50d/180d (todos derivan de la misma
    base). Se ejecuta en background (no bloquea Flask), salvo la llamada
    inicial en el startup del proceso.
    """
    import snapshot_builder
    try:
        symbols = all_symbols_with_macro()
        ok, fail, elapsed = price_store.update_today(symbols)
        log.info("Cierre diario: %d OK, %d fail en %.1fs", ok, fail, elapsed)

        for period in (5, 20, 50, 180):
            try:
                snapshot_builder.build_and_cache(period)
            except Exception as e:
                log.error("No se pudo recalcular snapshot %sd: %s", period, e)
    except Exception as e:
        log.error("Job cierre diario falló: %s", e)


def job_intraday_update():
    """
    Job intradía: cada 60 min entre 9:00 y 16:00 ET, lunes a viernes.
    Actualiza el store de velas de 15 min y recalcula + cachea solo el
    snapshot de 1d. Usa `intraday_symbols()`, no `all_symbols_with_macro()`
    (ver docstring de esa función).
    """
    import snapshot_builder
    try:
        symbols = intraday_symbols()
        ok, fail, elapsed = intraday_store.update(symbols)
        log.info("Intradía: %d OK, %d fail en %.1fs", ok, fail, elapsed)

        try:
            snapshot_builder.build_and_cache(1)
        except Exception as e:
            log.error("No se pudo recalcular snapshot 1d: %s", e)
    except Exception as e:
        log.error("Job intradía falló: %s", e)


def job_capture_etf_flows():
    """
    Job diario: captura snapshots de flujo ETF a las 18:00 (cierre US).
    Ejecuta scrape_etf_flows.py y acumula histórico en data/etf_flows.json.
    Se ejecuta en background (no bloquea Flask).
    """
    try:
        log.info("Iniciando captura de flujos ETF...")
        import etf_flow_tracker as tracker
        import universe

        # Extraer símbolos ETF del árbol
        def etf_symbols():
            out = set()

            def walk(n):
                if n.get("etf") and n.get("symbol"):
                    out.add(n["symbol"])
                for c in (n.get("children") or []):
                    walk(c)

            walk(universe.TREE)
            return sorted(out)

        syms = etf_symbols()
        captured, total = tracker.snapshot(syms)
        depth = tracker.history_depth()

        # Log del resultado
        log.info(
            "Captura de flujos ETF: %d/%d ETFs capturados, "
            "histórico acumulado de %d día(s)",
            captured, total, depth
        )

        ready = [w for w in tracker.WINDOWS if depth > w]
        if ready:
            log.info("Ventanas disponibles: %s", ", ".join(f"{w}d" for w in ready))

    except Exception as e:
        log.error("Job captura ETF falló: %s", e)
