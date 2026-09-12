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
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

import yfinance

import config

log = logging.getLogger("price_store")

# Reintentos ante fallo transitorio (429/timeout), mismo patrón que
# gpr_store.descargar(). Pocos y con backoff corto: bajo MAX_WORKERS hilos
# en paralelo, reintentar de más durante un soft-ban real solo empeoraría
# la ráfaga contra la misma IP.
YF_REINTENTOS = 2
YF_BACKOFF_SEG = 1.5
# La detección de "snapshot congelado" (ver intraday_store._check_stale) NO
# aplica acá: este store es diario, así que su última barra tiene horas de
# antigüedad la MAYOR parte del tiempo (fin de semana, fuera de horario) sin
# que eso sea señal de nada — aplicarla acá solo generaba ruido falso.

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
    Reintenta ante error transitorio (429/timeout); no reintenta si Yahoo
    responde vacío pero sin error (símbolo sin más historia, feriado, etc.).
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    yf_symbol = config.YFINANCE_SYMBOL_MAP.get(symbol, symbol)

    df = None
    ultimo_error = None
    for intento in range(1, YF_REINTENTOS + 1):
        try:
            ticker = yfinance.Ticker(yf_symbol)
            df = ticker.history(start=start_date, end=end_date)
            break
        except Exception as e:
            ultimo_error = e
            if intento < YF_REINTENTOS:
                time.sleep(YF_BACKOFF_SEG * intento)
    if df is None:
        log.warning("yfinance FAIL %s tras %d intentos :: %s", symbol, YF_REINTENTOS, ultimo_error)
        return []

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


# ---------------------------------------------------------------------------
# Lectura (hot path — nunca pega a red salvo la primera vez que se ve un símbolo)
# ---------------------------------------------------------------------------
def _gap_dias(ultima, today):
    """Días calendario entre la última barra en disco y hoy (grande si no parsea)."""
    try:
        return (date.fromisoformat(today) - date.fromisoformat(ultima)).days
    except (TypeError, ValueError):
        return 9999


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
    Reconcilia las barras que traiga el fetch para cada símbolo (idempotente:
    una fecha ya presente se reemplaza) y poda a DAILY_STORE_BARS. No exige
    que haya barra de HOY: si la hubiera exigido, cualquier corrida fuera del
    horario de cierre descartaría datos válidos. Un solo _load()/_save()
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
        # Símbolo con hueco (máquina apagada, server caído a la hora del job):
        # también se re-siembra, porque pedir 5 días no tapa un hueco más largo
        # y la base quedaría clavada en la última fecha buena para siempre.
        prev = store.get(sym)
        is_new = not prev or _gap_dias(prev[-1].get("date"), today) > 5
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
                # Reconciliar TODAS las fechas del fetch (mismo patrón que
                # intraday_store.update). Antes se exigía que la última barra
                # fuera de HOY y si no, se descartaba el fetch entero: una
                # corrida antes del cierre, un feriado o un reinicio fuera de
                # horario tiraban barras válidas, y el hueco no se recuperaba
                # nunca (140 símbolos clavados 7 semanas en la máquina local).
                # Las del fetch pisan a las de disco -> sigue siendo idempotente
                # y corrige una barra provisoria guardada con el mercado abierto.
                merged = {b["date"]: b for b in store.get(sym, [])}
                merged.update({b["date"]: b for b in bars})
                store[sym] = [merged[d] for d in sorted(merged)][-config.DAILY_STORE_BARS:]
                ok += 1
    except Exception as e:
        log.error("update_today abortado: %s", e)

    _save(store)
    return ok, fail, time.time() - start


if __name__ == "__main__":
    # Self-check sin red: el caso que clavó la base (fetch sin la barra de HOY,
    # y hueco largo por máquina apagada) tiene que quedar cubierto.
    import tempfile

    def _bar(d, c=1.0):
        return {"date": d, "open": c, "high": c, "low": c, "close": c, "volume": 0}

    DATA_DIR = tempfile.mkdtemp()
    STORE = os.path.join(DATA_DIR, "price_history.json")
    HOY = "2026-09-12"
    pedidos = {}

    def _fake(symbol, days):
        pedidos[symbol] = days
        # yfinance todavía no publicó la barra de HOY (job corriendo antes del
        # cierre, o feriado): la más reciente es la de la rueda anterior.
        return [_bar("2026-09-10", 10), _bar("2026-09-11", 11)]

    _fetch_yf = _fake

    # 1) Al día salvo la última rueda -> las barras entran igual, sin ser de hoy.
    _save({"AAA": [_bar("2026-09-09", 9)]})
    ok, fail, _ = update_today(["AAA"], today=HOY)
    assert (ok, fail) == (1, 0), (ok, fail)
    assert [b["date"] for b in get("AAA")] == ["2026-09-09", "2026-09-10", "2026-09-11"]
    assert pedidos["AAA"] == 5, "sin hueco tiene que pedir el fetch corto"

    # 2) Idempotencia: repetir la corrida no duplica y pisa con el valor nuevo.
    update_today(["AAA"], today=HOY)
    assert len(get("AAA")) == 3 and get("AAA")[-1]["close"] == 11

    # 3) Hueco largo -> re-siembra completa (pedir 5 días no lo taparía).
    st = _load()
    st["BBB"] = [_bar("2026-07-23", 7)]
    _save(st)
    update_today(["BBB"], today=HOY)
    assert pedidos["BBB"] == config.DAILY_STORE_SEED_DAYS, "con hueco tiene que re-sembrar"
    assert [b["date"] for b in get("BBB")] == ["2026-09-10", "2026-09-11"]

    # 4) Fetch vacío = fail, y no pisa lo que ya había.
    _fetch_yf = lambda symbol, days: []
    ok, fail, _ = update_today(["AAA"], today=HOY)
    assert (ok, fail) == (0, 1) and len(get("AAA")) == 3

    print("price_store self-check OK")
