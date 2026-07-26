"""
Store de precios diario — ventana fija actualizada por evento de mercado, no
por TTL.

Por qué existe
--------------
Antes, `fmp_client.historical()` cacheaba cada fetch de yfinance con un TTL
relativo de 1h: al expirar, el PRÓXIMO usuario que pedía ese símbolo pagaba el
costo de recomputar en su propia request. Este módulo lo reemplaza por una
base persistente por símbolo, de tamaño constante (se poda el dato más viejo
al agregar el cierre de hoy), que solo se actualiza cuando corre el job de
cierre de mercado (`preload_cache.job_market_close_update`, 1x/día). Entre
medio, `get()` nunca pega a red — sirve directo del JSON en disco.

Mismo patrón de persistencia atómica que `etf_flow_tracker.py`.
"""
import json
import logging
import math
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

import yfinance

import config

log = logging.getLogger("price_store")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
STORE = os.path.join(DATA_DIR, "price_history.json")

# Caché en memoria del store completo, invalidada por mtime del archivo.
# get() se llama decenas de veces por snapshot (una por símbolo del árbol,
# más RRG, más ROTO) — sin esto, cada llamada releía y re-parseaba el JSON
# completo del disco, dominando el tiempo de ensamblado.
_mem_cache = None
_mem_cache_mtime = None


# ---------------------------------------------------------------------------
# Persistencia (JSON en disco, ventana fija)
# ---------------------------------------------------------------------------
def _load():
    global _mem_cache, _mem_cache_mtime
    if not os.path.exists(STORE):
        _mem_cache, _mem_cache_mtime = {}, None
        return _mem_cache
    mtime = os.path.getmtime(STORE)
    if _mem_cache is not None and mtime == _mem_cache_mtime:
        return _mem_cache
    try:
        with open(STORE, encoding="utf-8") as f:
            _mem_cache = json.load(f)
        _mem_cache_mtime = mtime
    except (json.JSONDecodeError, OSError):
        _mem_cache = {}
    return _mem_cache


def _save(store):
    global _mem_cache, _mem_cache_mtime
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = STORE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(store, f)
    os.replace(tmp, STORE)          # escritura atómica
    _mem_cache = store
    _mem_cache_mtime = os.path.getmtime(STORE)


# ---------------------------------------------------------------------------
# Fetch yfinance (movido tal cual desde el viejo fmp_client.historical)
# ---------------------------------------------------------------------------
def _fetch_yf(symbol: str, days: int):
    """
    Devuelve lista ascendente de barras OHLCV:
    [{date, open, high, low, close, volume}, ...]  o []  si falla.
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        yf_symbol = config.YFINANCE_SYMBOL_MAP.get(symbol, symbol)
        ticker = yfinance.Ticker(yf_symbol)
        df = ticker.history(start=start_date, end=end_date)

        if df.empty:
            log.warning("yfinance vacío %s", symbol)
            return []

        out = []
        for date_idx, row in df.iterrows():
            try:
                close = float(row["Close"])
                if math.isnan(close):
                    # Barra del día en curso todavía sin cerrar / placeholder
                    # de yfinance: no es un cierre real, se descarta.
                    continue
                out.append({
                    "date": date_idx.strftime("%Y-%m-%d"),
                    "open": float(row.get("Open", row.get("Close", 0)) or 0),
                    "high": float(row.get("High", 0) or 0),
                    "low": float(row.get("Low", 0) or 0),
                    "close": close,
                    "volume": float(row.get("Volume", 0) or 0),
                })
            except (KeyError, TypeError, ValueError):
                continue

        return out
    except Exception as e:
        log.warning("yfinance FAIL %s :: %s", symbol, e)
        return []


# ---------------------------------------------------------------------------
# Lectura (hot path — nunca pega a red salvo la primera vez que se ve un símbolo)
# ---------------------------------------------------------------------------
def _seed(symbol):
    """Primera vez que se ve un símbolo: siembra DAILY_STORE_BARS barras."""
    bars = _fetch_yf(symbol, config.DAILY_STORE_SEED_DAYS)
    bars = bars[-config.DAILY_STORE_BARS:]
    if bars:
        store = _load()
        store[symbol] = bars
        _save(store)
    return bars


def get(symbol):
    """Barras diarias del store; siembra lazy si el símbolo nunca se vio."""
    store = _load()
    bars = store.get(symbol)
    if not bars:
        return _seed(symbol)
    return bars


# ---------------------------------------------------------------------------
# Actualización diaria (job de cierre de mercado)
# ---------------------------------------------------------------------------
def update_today(symbols, today=None):
    """
    Agrega el cierre de hoy para cada símbolo (idempotente: si ya hay entrada
    de hoy, la reemplaza) y poda a DAILY_STORE_BARS. Un solo _load()/_save()
    para todos los símbolos (evita condición de carrera read-modify-write
    entre hilos); el fetch de red sí se paraleliza.

    Devuelve (ok, fail, elapsed).
    """
    import time
    today = today or date.today().isoformat()
    start = time.time()

    store = _load()

    def _fetch_one(sym):
        # Símbolo nunca visto: sembrar histórico completo (no solo el cierre
        # de hoy), si no quedaría con una única barra en vez de 260.
        is_new = not store.get(sym)
        days = config.DAILY_STORE_SEED_DAYS if is_new else 5
        return sym, is_new, _fetch_yf(sym, days)

    ok = fail = 0

    try:
        with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as ex:
            for sym, is_new, bars in ex.map(_fetch_one, symbols):
                if not bars:
                    fail += 1
                    continue
                if is_new:
                    store[sym] = bars[-config.DAILY_STORE_BARS:]
                    ok += 1
                    continue
                latest = bars[-1]
                if latest["date"] != today:
                    # yfinance todavía no publicó el cierre de hoy (delay,
                    # feriado no detectado): no forzar una entrada falsa.
                    fail += 1
                    continue
                series = [b for b in store.get(sym, []) if b["date"] != today]  # idempotencia
                series.append(latest)
                series.sort(key=lambda b: b["date"])
                store[sym] = series[-config.DAILY_STORE_BARS:]
                ok += 1
    except Exception as e:
        log.error("update_today abortado: %s", e)

    _save(store)
    return ok, fail, time.time() - start
