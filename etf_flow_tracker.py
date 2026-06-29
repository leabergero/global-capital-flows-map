"""
Rastreador de flujo de ETF — construye el histórico de flujo HACIA ADELANTE.

Por qué existe
--------------
El flujo implícito de un ETF (la única capa de dinero observado, no inferido) es
un DELTA entre dos fechas:

    flujo_t  ≈  (shares_outstanding_t − shares_outstanding_{t-1})  ×  NAV_t

El problema: ninguna fuente gratuita da el histórico de shares outstanding / AUM
de un ETF. Verificado (2026-06):
  • yfinance .info da el snapshot ACTUAL (sharesOutstanding, totalAssets, navPrice)
  • yfinance .get_shares_full() viene VACÍO para ETFs
  • SSGA/iShares publican solo el holding del día (sin histórico)
  • Finnhub/EODHD/FactSet tienen el histórico pero detrás de plan pago

Conclusión: el flujo NO se puede obtener retroactivamente. Se construye guardando
un snapshot diario (shares × NAV) y acumulando en disco. Las ventanas 5/20/50 son
la suma de los flujos diarios de los últimos N snapshots DISPONIBLES; el histórico
se llena con el tiempo (día 6 -> ventana 5, día 51 -> ventana 50).

Granularidad diaria. Solo ETF (tienen creación/redención). Dinero observado.
"""
import json
import os
from datetime import date

import yfinance as yf

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
STORE = os.path.join(DATA_DIR, "etf_flows.json")

# Ventanas temporales que expone el frontend (enlazadas con RRG/heatmap)
WINDOWS = (5, 20, 50)


# ---------------------------------------------------------------------------
# Persistencia (JSON en disco, acumulativo)
# ---------------------------------------------------------------------------
def _load():
    if not os.path.exists(STORE):
        return {}
    try:
        with open(STORE, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save(store):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = STORE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2)
    os.replace(tmp, STORE)          # escritura atómica


# ---------------------------------------------------------------------------
# Captura de un snapshot diario
# ---------------------------------------------------------------------------
def _fetch(symbol):
    """
    (shares_outstanding, nav) actuales de un ETF, o (None, None) si falla.
    Si yfinance no expone sharesOutstanding directo, lo deriva de totalAssets/NAV
    (rescata los ETF menos líquidos: sectoriales, commodities, agrícolas).
    """
    try:
        info = yf.Ticker(symbol).info
    except Exception:
        return None, None
    nav = info.get("navPrice") or info.get("previousClose")
    if not nav:
        return None, None
    shares = info.get("sharesOutstanding")
    if not shares:
        total_assets = info.get("totalAssets")
        if total_assets:
            shares = round(total_assets / nav)     # fallback: AUM / NAV
    if not shares:
        return None, None
    return shares, nav


def snapshot(symbols, today=None):
    """
    Toma un snapshot de hoy para cada símbolo y lo agrega al histórico.
    Idempotente: si ya hay snapshot de hoy, lo reemplaza (no duplica).
    Devuelve (capturados, total).
    """
    today = today or date.today().isoformat()
    store = _load()
    captured = 0
    for sym in symbols:
        shares, nav = _fetch(sym)
        if shares is None:
            continue
        series = store.setdefault(sym, [])
        series[:] = [s for s in series if s["date"] != today]   # idempotencia
        series.append({"date": today, "shares": shares, "nav": round(nav, 4)})
        series.sort(key=lambda s: s["date"])
        captured += 1
    _save(store)
    return captured, len(symbols)


# ---------------------------------------------------------------------------
# Cálculo de flujo
# ---------------------------------------------------------------------------
def _daily_flows(series):
    """Flujos diarios (USD) entre snapshots consecutivos."""
    out = []
    for prev, cur in zip(series, series[1:]):
        d_shares = cur["shares"] - prev["shares"]
        out.append(d_shares * cur["nav"])
    return out


def flow_window(symbol, days):
    """
    Flujo acumulado (USD) de los últimos `days` snapshots disponibles, o None si
    aún no hay histórico suficiente (se necesitan >=2 snapshots).
    """
    series = _load().get(symbol, [])
    if len(series) < 2:
        return None
    flows = _daily_flows(series)
    return sum(flows[-days:]) if flows else None


def all_windows(symbol):
    """Dict {5: flujo, 20: flujo, 50: flujo} para un símbolo (valores o None)."""
    return {w: flow_window(symbol, w) for w in WINDOWS}


def history_depth():
    """Días de histórico acumulados (el ETF con más snapshots)."""
    store = _load()
    return max((len(s) for s in store.values()), default=0)


def coverage():
    """Resumen por símbolo: cuántos snapshots tiene cada uno."""
    return {sym: len(series) for sym, series in sorted(_load().items())}
