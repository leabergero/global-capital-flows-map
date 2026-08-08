"""
Store de velas intradía (15 min) — solo para el período "1d".

Por qué existe
--------------
El resto de las ventanas (5d/20d/50d/180d) operan sobre cierres diarios
(`price_store.py`), que solo cambian 1x/día. El período "1d" necesita reflejar
el movimiento DENTRO del día, así que usa velas reales de 15 minutos
(yfinance las da gratis vía `interval="15m"`), actualizadas cada 15 min por
`preload_cache.job_intraday_update` mientras el mercado está abierto.

Se conservan los últimos INTRADAY_KEEP_DAYS días de mercado (podado por
fecha, no reseteado a cero cada mañana): un solo día da ~26 barras de 15 min,
insuficientes para `rrg.point()` (necesita window+tail+2) recién abierto el
mercado. Con 3 días de sobra siempre hay margen, incluso a los pocos minutos
de la apertura.
"""
import json
import logging
import math
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from zoneinfo import ZoneInfo

import yfinance

import config

log = logging.getLogger("intraday_store")

# Mismos parámetros y mismo motivo que price_store.py.
YF_REINTENTOS = 2
YF_BACKOFF_SEG = 1.5
# A diferencia de price_store (diario, "viejo" la mayor parte del tiempo por
# diseño), acá SÍ es señal real: si el mercado NYSE está abierto y el dato
# más nuevo que sirvió Yahoo tiene más de esto de antigüedad, no es que "no
# pasó nada" — es que Yahoo empezó a servir un snapshot congelado (soft-ban).
STALE_AFTER_MIN = 60
_NYSE_TZ = ZoneInfo("America/New_York")


def _nyse_open_now():
    """True si NYSE está en sesión regular ahora (aprox., sin feriados).

    Guard barato para no confundir "mercado cerrado" con "soft-ban": el job
    solo corre en este horario, pero el preload síncrono del arranque
    (`app.py`) lo dispara también fuera de horario/fin de semana.
    """
    now = datetime.now(_NYSE_TZ)
    if now.weekday() >= 5:
        return False
    minutes = now.hour * 60 + now.minute
    return 9 * 60 + 30 <= minutes <= 16 * 60

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
STORE = os.path.join(DATA_DIR, "intraday_bars.json")

# Mismo motivo que price_store.py: get() se llama muchas veces por snapshot.
_mem_cache = None
_mem_cache_mtime = None


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
    os.replace(tmp, STORE)
    _mem_cache = store
    _mem_cache_mtime = os.path.getmtime(STORE)


def _check_stale(ticker, symbol):
    """Loguea si Yahoo sirvió un dato viejo con el mercado abierto — señal de
    snapshot congelado (soft-ban), no de que no pasó nada."""
    if not _nyse_open_now():
        return
    meta = getattr(ticker, "history_metadata", None) or {}
    ts = meta.get("regularMarketTime")
    if not isinstance(ts, (int, float)):
        return
    age_min = (time.time() - ts) / 60
    if age_min > STALE_AFTER_MIN:
        log.warning("posible soft-ban de Yahoo: %s con dato de hace %.0f min (mercado abierto)", symbol, age_min)


def _fetch_yf_intraday(symbol):
    """
    Velas de 15 min del día en curso (+ margen de días previos).
    [{date: <ISO completo con hora>, open, high, low, close, volume}, ...]
    ascendente, o [] si falla. Reintenta ante error transitorio (429/timeout).
    """
    yf_symbol = config.YFINANCE_SYMBOL_MAP.get(symbol, symbol)

    df = None
    ultimo_error = None
    for intento in range(1, YF_REINTENTOS + 1):
        try:
            ticker = yfinance.Ticker(yf_symbol)
            df = ticker.history(period=config.INTRADAY_FETCH_PERIOD,
                                 interval=config.INTRADAY_INTERVAL)
            _check_stale(ticker, symbol)
            break
        except Exception as e:
            ultimo_error = e
            if intento < YF_REINTENTOS:
                time.sleep(YF_BACKOFF_SEG * intento)
    if df is None:
        log.warning("yfinance intradía FAIL %s tras %d intentos :: %s", symbol, YF_REINTENTOS, ultimo_error)
        return []

    try:
        if df.empty:
            log.warning("yfinance intradía vacío %s", symbol)
            return []

        out = []
        for ts_idx, row in df.iterrows():
            try:
                close = float(row["Close"])
                if math.isnan(close):
                    continue  # vela en curso todavía sin cerrar / placeholder
                out.append({
                    "date": ts_idx.isoformat(),
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
        log.warning("yfinance intradía parseo FAIL %s :: %s", symbol, e)
        return []


def get(symbol):
    """Velas de 15 min almacenadas, o [] si aún no corrió ningún job hoy.

    Sin seed lazy de red: el fallback a diario lo resuelve
    fmp_client.historical_intraday().
    """
    return _load().get(symbol, [])


def update(symbols):
    """
    Job intradía: trae velas de 15 min para todos los símbolos, reconcilia
    TODAS las fechas presentes en el fetch (no solo "hoy" — así se
    autocorrige cualquier gap de una corrida anterior que no llegó a
    ejecutarse) y poda a los INTRADAY_KEEP_DAYS días de mercado más
    recientes. Un solo _load()/_save() (evita condición de carrera).

    Devuelve (ok, fail, elapsed).
    """
    start = time.time()
    store = _load()
    ok = fail = 0

    def _fetch_one(sym):
        return sym, _fetch_yf_intraday(sym)

    try:
        with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as ex:
            for sym, bars_new in ex.map(_fetch_one, symbols):
                if not bars_new:
                    fail += 1
                    continue
                days_new = {b["date"][:10] for b in bars_new}
                existing = [b for b in store.get(sym, []) if b["date"][:10] not in days_new]
                merged = existing + bars_new
                merged.sort(key=lambda b: b["date"])

                days_sorted = sorted({b["date"][:10] for b in merged}, reverse=True)
                keep_days = set(days_sorted[:config.INTRADAY_KEEP_DAYS])
                store[sym] = [b for b in merged if b["date"][:10] in keep_days]
                ok += 1
    except Exception as e:
        log.error("update intradía abortado: %s", e)

    _save(store)
    return ok, fail, time.time() - start
