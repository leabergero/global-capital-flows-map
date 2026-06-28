"""
COT — Commitment of Traders. Posición neta de no-comerciales (especuladores) y
su cambio semanal. Las claves de FMP varían según el endpoint/plan, así que
probamos varios nombres de campo y degradamos a None sin romper.
"""
import fmp_client as fmp

# posibles nombres de campo en distintas versiones del endpoint
_LONG = ["noncommercialLongTotal", "noncommercial_positions_long_all",
         "noncomm_positions_long_all", "noncommLong"]
_SHORT = ["noncommercialShortTotal", "noncommercial_positions_short_all",
          "noncomm_positions_short_all", "noncommShort"]
_CHG_LONG = ["changeInNoncommercialLong", "change_in_noncomm_long_all"]
_CHG_SHORT = ["changeInNoncommercialShort", "change_in_noncomm_short_all"]


def _pick(d, keys):
    for k in keys:
        if k in d and d[k] is not None:
            try:
                return float(d[k])
            except (TypeError, ValueError):
                continue
    return None


def net_position(symbol):
    """
    Devuelve (neto_k, cambio_k) en miles de contratos, o None.
    """
    rep = fmp.cot(symbol)
    if not rep:
        return None
    lng = _pick(rep, _LONG)
    sht = _pick(rep, _SHORT)
    if lng is None or sht is None:
        return None
    net = (lng - sht) / 1000.0
    chg_l = _pick(rep, _CHG_LONG) or 0.0
    chg_s = _pick(rep, _CHG_SHORT) or 0.0
    chg = (chg_l - chg_s) / 1000.0
    return round(net, 1), round(chg, 1)


def table(symbols):
    """Lista [[label, neto, cambio], ...] para los símbolos que devuelven dato."""
    out = []
    for item in symbols:
        res = net_position(item["symbol"])
        if res:
            out.append([item["label"], res[0], res[1]])
    return out
