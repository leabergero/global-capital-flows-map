"""
Cliente FMP. Centraliza TODAS las rutas en un solo lugar (ENDPOINTS) para que
ajustar una URL no implique tocar la lógica. Cada request se loguea con su
status; los errores no se propagan como excepción: devuelven None y quedan
registrados, de modo que un endpoint caído degrada un panel, no toda la app.

Históricos: yfinance (gratis, no requiere key). El resto: FMP.
"""
import logging
import requests
from datetime import datetime, timedelta

import yfinance
import config
import cache

log = logging.getLogger("fmp")


def _get(url: str, params: dict, ttl_key: str, cache_key: str):
    """GET con caché + logging. Devuelve JSON parseado o None."""
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    params = dict(params or {})
    params["apikey"] = config.FMP_API_KEY
    try:
        r = requests.get(url, params=params, timeout=config.HTTP_TIMEOUT)
    except requests.RequestException as e:
        log.warning("FMP red FAIL %s :: %s", url, e)
        return None
    if r.status_code != 200:
        # logueamos sin la apikey
        log.warning("FMP %s %s :: %s", r.status_code, url, r.text[:160])
        return None
    try:
        data = r.json()
    except ValueError:
        log.warning("FMP JSON inválido %s", url)
        return None
    cache.set(cache_key, data, config.TTL.get(ttl_key, 3600))
    return data


# ----------------------------------------------------------------------------
# Históricos de precio (yfinance: gratis, no requiere key)
# Workhorse: RRG, CMF, RORO y la mayoría del macro
# ----------------------------------------------------------------------------
def historical(symbol: str, days: int = None):
    """
    Devuelve lista ascendente de barras OHLCV:
    [{date, open, high, low, close, volume}, ...]  o []  si falla.

    Usa yfinance (gratis) en lugar de FMP (que requiere plan Pro para v3 legacy).
    """
    days = days or config.HISTORY_DAYS
    cache_key = f"hist:{symbol}:{days}"

    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        ticker = yfinance.Ticker(symbol)
        df = ticker.history(start=start_date, end=end_date)

        if df.empty:
            log.warning("yfinance vacío %s", symbol)
            return []

        out = []
        for date_idx, row in df.iterrows():
            try:
                out.append({
                    "date": date_idx.strftime("%Y-%m-%d"),
                    "open": float(row.get("Open", row.get("Close", 0)) or 0),
                    "high": float(row.get("High", 0) or 0),
                    "low": float(row.get("Low", 0) or 0),
                    "close": float(row["Close"]),
                    "volume": float(row.get("Volume", 0) or 0),
                })
            except (KeyError, TypeError, ValueError):
                continue

        if out:
            cache.set(cache_key, out, config.TTL.get("price", 3600))
            log.debug("yfinance OK %s (%d barras)", symbol, len(out))
        else:
            log.warning("yfinance sin barras válidas %s", symbol)

        return out
    except Exception as e:
        log.warning("yfinance FAIL %s :: %s", symbol, e)
        return []


def quote(symbol: str):
    """Cotización actual: {price, changesPercentage, ...} o None.

    Usa yfinance (gratis, sin key). Fallback a FMP si yfinance falla.
    """
    cache_key = f"quote:{symbol}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    # Convertir símbolo si está en el mapeo
    yf_symbol = config.YFINANCE_SYMBOL_MAP.get(symbol, symbol)

    try:
        ticker = yfinance.Ticker(yf_symbol)
        info = ticker.info or {}
        price = info.get("currentPrice") or info.get("regularMarketPrice")

        if price is None:
            # Fallback: intentar histórico + último close
            df = ticker.history(period="1d")
            if df.empty:
                log.warning("yfinance vacío %s", symbol)
                return None
            price = df["Close"].iloc[-1]

        # Calcular cambio % si tenemos precio previo
        prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
        chg_pct = None
        if prev_close and price:
            chg_pct = ((price - prev_close) / prev_close) * 100.0

        result = {
            "symbol": symbol,
            "price": float(price),
            "changesPercentage": float(chg_pct) if chg_pct is not None else 0.0,
        }

        cache.set(cache_key, result, config.TTL.get("price", 3600))
        log.debug("yfinance quote OK %s = %.2f", symbol, price)
        return result
    except Exception as e:
        log.warning("yfinance quote FAIL %s :: %s", symbol, e)
        # Fallback a FMP si yfinance falla
        url = f"{config.FMP_BASE_V3}/quote/{symbol}"
        data = _get(url, {}, "price", cache_key)
        if isinstance(data, list) and data:
            return data[0]
        return None


# ----------------------------------------------------------------------------
# ETF holdings -> base del flujo implícito (única capa de dinero observado)
# ----------------------------------------------------------------------------
def etf_holding_dates(symbol: str):
    """Fechas en que se actualizaron los holdings del ETF (desc)."""
    url = f"{config.FMP_BASE_STABLE}/etf/holdings/dates"
    data = _get(url, {"symbol": symbol}, "flows", f"etfdates:{symbol}")
    if isinstance(data, list):
        # puede venir como [{"date": "..."}] o ["..."]
        out = []
        for d in data:
            out.append(d.get("date") if isinstance(d, dict) else d)
        return [d for d in out if d]
    return []


def etf_holdings(symbol: str, date: str):
    """Holdings del ETF en una fecha: lista con marketValue/sharesNumber."""
    url = f"{config.FMP_BASE_STABLE}/etf/holdings"
    data = _get(url, {"symbol": symbol, "date": date}, "flows",
                f"etfhold:{symbol}:{date}")
    return data if isinstance(data, list) else []


# ----------------------------------------------------------------------------
# COT y económicos (los frágiles: dependen del plan; degradan a n/d)
# ----------------------------------------------------------------------------
def quandl_cot(symbol: str):
    """COT de Quandl (gratis). Devuelve dict compatible con formato FMP."""
    if not config.QUANDL_API_KEY:
        return None

    cache_key = f"cot:{symbol}:quandl"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    dataset_code = config.QUANDL_COT_MAP.get(symbol)
    if not dataset_code:
        return None

    try:
        import quandl
        quandl.ApiConfig.api_key = config.QUANDL_API_KEY

        df = quandl.get(dataset_code, rows=1)
        if df.empty:
            log.warning("Quandl vacío %s", symbol)
            return None

        row = df.iloc[0]

        long_candidates = [
            "Noncommercial Long", "Noncomm Long", "Non-commercial Long",
        ]
        short_candidates = [
            "Noncommercial Short", "Noncomm Short", "Non-commercial Short",
        ]
        chg_long_candidates = [
            "Change in Noncommercial Long", "Change in Noncomm Long",
        ]
        chg_short_candidates = [
            "Change in Noncommercial Short", "Change in Noncomm Short",
        ]

        long_val = None
        for col in long_candidates:
            if col in row.index:
                long_val = row[col]
                break

        short_val = None
        for col in short_candidates:
            if col in row.index:
                short_val = row[col]
                break

        if long_val is None or short_val is None:
            log.warning("Quandl campos faltantes %s", symbol)
            return None

        chg_long = 0.0
        for col in chg_long_candidates:
            if col in row.index:
                chg_long = row[col] or 0.0
                break

        chg_short = 0.0
        for col in chg_short_candidates:
            if col in row.index:
                chg_short = row[col] or 0.0
                break

        result = {
            "noncommercialLongTotal": long_val,
            "noncommercialShortTotal": short_val,
            "changeInNoncommercialLong": chg_long,
            "changeInNoncommercialShort": chg_short,
            "reportDate": str(df.index[0].date()) if hasattr(df.index[0], 'date') else str(df.index[0]),
        }

        cache.set(cache_key, result, config.TTL.get("cot", 604800))
        log.debug("Quandl OK %s", symbol)
        return result

    except ImportError:
        log.warning("Quandl no instalado")
        return None
    except Exception as e:
        log.warning("Quandl FAIL %s :: %s", symbol, e)
        return None


def cftc_cot(symbol: str):
    """Último COT de CFTC (gratis, sin key). Devuelve dict compatible con formato FMP."""
    cache_key = f"cot:{symbol}:cftc"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    # Obtener código CFTC del símbolo
    cftc_code = config.CFTC_SYMBOL_MAP.get(symbol)
    if not cftc_code:
        log.warning("CFTC símbolo desconocido %s", symbol)
        return None

    try:
        # CFTC API endpoint histórico
        r = requests.get(config.CFTC_API_URL, timeout=config.HTTP_TIMEOUT)
        if r.status_code != 200:
            log.warning("CFTC %s %s", r.status_code, symbol)
            return None

        data = r.json()
        # Estructura: { "success": true/false, "data": [ {...}, ... ] }
        if not data.get("success") or not data.get("data"):
            log.warning("CFTC no data %s", symbol)
            return None

        # Buscar el registro más reciente para este commodity
        rows = data["data"]
        matching = [row for row in rows if row.get("commodity_code") == cftc_code]
        if not matching:
            log.warning("CFTC %s no encontrado en %d registros", symbol, len(rows))
            return None

        # Ordenar por fecha (descendente) y tomar el más reciente
        matching.sort(key=lambda x: x.get("report_date_as_date", ""), reverse=True)
        latest = matching[0]

        # Convertir a formato FMP compatible
        # CFTC: all_money_longs / all_money_shorts
        # O: noncomm_positions_long_all / noncomm_positions_short_all
        long_val = (
            latest.get("noncomm_positions_long_all")
            or latest.get("all_money_longs")
            or latest.get("noncommercialLongTotal")
        )
        short_val = (
            latest.get("noncomm_positions_short_all")
            or latest.get("all_money_shorts")
            or latest.get("noncommercialShortTotal")
        )

        if long_val is None or short_val is None:
            log.warning("CFTC campos faltantes %s", symbol)
            return None

        # Intentar obtener cambios
        chg_long = (
            latest.get("change_in_noncomm_long_all")
            or latest.get("changeInNoncommercialLong")
            or 0
        )
        chg_short = (
            latest.get("change_in_noncomm_short_all")
            or latest.get("changeInNoncommercialShort")
            or 0
        )

        # Estructura compatible con FMP
        result = {
            "noncommercialLongTotal": long_val,
            "noncommercialShortTotal": short_val,
            "changeInNoncommercialLong": chg_long,
            "changeInNoncommercialShort": chg_short,
            "reportDate": latest.get("report_date_as_date"),
        }

        cache.set(cache_key, result, config.TTL.get("cot", 604800))  # 7 días
        log.debug("CFTC OK %s (fecha %s)", symbol, result.get("reportDate"))
        return result

    except Exception as e:
        log.warning("CFTC FAIL %s :: %s", symbol, e)
        return None


def cot(symbol: str):
    """Último reporte COT para un símbolo de futuro, o None.

    Cascada: Quandl (gratis) → CFTC (gratis) → FMP → None
    """
    # 1. Intentar Quandl primero (mejor cobertura, más fácil)
    result = quandl_cot(symbol)
    if result:
        return result

    # 2. Fallback a CFTC (gratis, público)
    result = cftc_cot(symbol)
    if result:
        return result

    # 3. Fallback a FMP (plan Pro)
    url = f"{config.FMP_BASE_V4}/commitment_of_traders_report/{symbol}"
    data = _get(url, {}, "cot", f"cot:{symbol}")
    if isinstance(data, list) and data:
        return data[0]

    return None


def economic(name: str):
    """Serie de un indicador económico de FMP, o []."""
    url = f"{config.FMP_BASE_V4}/economic"
    data = _get(url, {"name": name}, "macro", f"econ:{name}")
    return data if isinstance(data, list) else []
