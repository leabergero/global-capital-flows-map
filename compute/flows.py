"""
Flujo implícito de ETF — la ÚNICA capa donde el dinero es observable, no inferido.

Idea: el AUM cambia por dos motivos, (1) el precio de lo que tiene, y (2) plata
que entra/sale vía creación/redención de unidades. Aislamos (2):

  flujo_t  ≈  AUM_t  −  AUM_{t-1} * (1 + retorno_precio_t)

AUM se aproxima sumando el marketValue de todos los holdings en cada fecha de
corte (endpoint /etf/holdings?date=). El retorno se toma del precio del propio
ETF entre ambas fechas. Resultado en USD (lo formateamos a millones/billones).

Granularidad diaria (no horaria) y solo para nodos ETF. En acciones, cripto y FX
NO aplica: ahí no hay creación/redención -> el flujo queda en None (tile neutro).
"""
import fmp_client as fmp


def _aum(symbol, date):
    holdings = fmp.etf_holdings(symbol, date)
    if not holdings:
        return None
    total = 0.0
    found = False
    for h in holdings:
        mv = h.get("marketValue")
        if mv is None:
            continue
        try:
            total += float(mv)
            found = True
        except (TypeError, ValueError):
            continue
    return total if found else None


def _close_on_or_before(bars, date):
    """Último close con fecha <= date (bars ascendente)."""
    chosen = None
    for b in bars:
        if b["date"] <= date:
            chosen = b["close"]
        else:
            break
    return chosen


def implied_flow(symbol, price_bars):
    """
    Devuelve flujo neto estimado en USD (float) o None.
    Usa las dos fechas de holdings más recientes.
    """
    dates = fmp.etf_holding_dates(symbol)
    if not dates or len(dates) < 2:
        return None
    dates = sorted(dates)          # ascendente
    d_prev, d_cur = dates[-2], dates[-1]
    aum_prev = _aum(symbol, d_prev)
    aum_cur = _aum(symbol, d_cur)
    if aum_prev in (None, 0) or aum_cur is None:
        return None
    # retorno del precio entre cortes
    ret = 0.0
    p_prev = _close_on_or_before(price_bars, d_prev)
    p_cur = _close_on_or_before(price_bars, d_cur)
    if p_prev and p_cur and p_prev != 0:
        ret = (p_cur / p_prev) - 1.0
    flow = aum_cur - aum_prev * (1.0 + ret)
    return float(flow)
