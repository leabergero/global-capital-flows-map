"""
Panel macro. Cada tarjeta sale de:
  kind="quote" -> símbolo cotizado (FX, commodities, índices): precio + variación
                  + sparkline desde el histórico. Prueba símbolos alternativos.
  kind="econ"  -> indicador económico (tasas de política, CPI): FMP economic;
                  si viene vacío, fallback a OpenBB/FRED; si no, "n/d".
Nunca lanza: una tarjeta que falla queda en "n/d".
"""
import logging

import config
import fmp_client as fmp

log = logging.getLogger("macro")


def _spark(values, points=12):
    """Submuestrea a 'points' valores para el sparkline."""
    vals = [v for v in values if v is not None]
    if not vals:
        return []
    if len(vals) <= points:
        return [round(float(v), 4) for v in vals]
    step = len(vals) / points
    return [round(float(vals[int(i * step)]), 4) for i in range(points)]


def _fmt(value, unit):
    if value is None:
        return "n/d"
    if unit == "%":
        return f"{value:.2f}%"
    if unit == "$":
        if value >= 1000:
            return f"${value:,.0f}"
        return f"${value:,.1f}"
    if abs(value) < 10:
        return f"{value:.4f}"
    return f"{value:,.1f}"


def _dir(chg):
    if chg is None:
        return "flat"
    return "up" if chg > 0 else "down" if chg < 0 else "flat"


def _quote_card(card):
    syms = [card["symbol"]] + card.get("alt", [])
    for sym in syms:
        q = fmp.quote(sym)
        if not q or q.get("price") is None:
            continue
        price = float(q["price"])
        chg = q.get("changesPercentage")
        try:
            chg = float(chg) if chg is not None else None
        except (TypeError, ValueError):
            chg = None
        bars = fmp.historical(sym, 40)
        spark = _spark([b["close"] for b in bars]) if bars else [price]
        chg_txt = (f"{chg:+.1f}%" if chg is not None else "—")
        return {"nm": card["nm"], "val": _fmt(price, card["unit"]),
                "chg": chg_txt, "dir": _dir(chg), "s": spark}
    return {"nm": card["nm"], "val": "n/d", "chg": "—", "dir": "flat", "s": []}


def _price_of(sym, alts):
    """Último precio de sym probando alternativas, o None."""
    for s in [sym] + list(alts or []):
        q = fmp.quote(s)
        if q and q.get("price") is not None:
            try:
                return float(q["price"])
            except (TypeError, ValueError):
                continue
    return None


def _ratio_card(card):
    """Tarjeta de cociente entre dos símbolos (ej: Plata/Oro)."""
    pa = _price_of(card["a"], card.get("alt_a"))
    pb = _price_of(card["b"], card.get("alt_b"))
    if pa is None or pb is None or pb == 0:
        return {"nm": card["nm"], "val": "n/d", "chg": "—", "dir": "flat", "s": []}
    ratio = pa / pb
    return {"nm": card["nm"], "val": _fmt(ratio, card.get("unit", "ratio")),
            "chg": "—", "dir": "flat", "s": [round(ratio, 4)]}


def _econ_series_fmp(name):
    data = fmp.economic(name)
    if not data:
        return None
    # esperado: [{date, value}, ...] (orden variable)
    try:
        rows = sorted(data, key=lambda d: d.get("date", ""))
        vals = [float(d["value"]) for d in rows if d.get("value") is not None]
        return vals or None
    except (KeyError, TypeError, ValueError):
        return None


def _econ_series_fred_direct(fred_id):
    """FRED vía fredapi (ligero, sin OpenBB)."""
    if not config.FRED_API_KEY:
        return None
    try:
        from fredapi import Fred
        fred = Fred(api_key=config.FRED_API_KEY)
        df = fred.get_series(fred_id)
        vals = [float(v) for v in df.dropna().tolist()]
        return vals or None
    except Exception as e:
        log.warning("FRED (direct) %s :: %s", fred_id, e)
        return None


def _econ_series_fred(fred_id):
    """FRED vía OpenBB (fallback pesado)."""
    try:
        from openbb import obb  # import perezoso: OpenBB es opcional/pesado
    except Exception:
        return None
    try:
        res = obb.economy.fred_series(symbol=fred_id)
        df = res.to_dataframe()
        col = df.columns[-1]
        vals = [float(v) for v in df[col].dropna().tolist()]
        return vals or None
    except Exception as e:
        log.warning("FRED (OpenBB) %s :: %s", fred_id, e)
        return None


def _econ_card(card):
    # FRED primero (gratis y vivo); FMP v4/economic es endpoint legacy (403).
    vals = _econ_series_fred_direct(card["fred"]) if card.get("fred") else None
    if not vals:
        vals = _econ_series_fmp(card.get("name"))
    if not vals and card.get("fred"):
        vals = _econ_series_fred(card["fred"])  # fallback a OpenBB (pesado)
    if not vals:
        return {"nm": card["nm"], "val": "n/d", "chg": "—", "dir": "flat", "s": []}
    if card.get("yoy") and len(vals) > 12:
        # variación interanual sobre el índice (CPI)
        latest = (vals[-1] / vals[-13] - 1.0) * 100.0
        prev = (vals[-2] / vals[-14] - 1.0) * 100.0
        chg = latest - prev
        return {"nm": card["nm"], "val": _fmt(latest, "%"),
                "chg": f"{chg:+.1f}", "dir": _dir(chg),
                "s": _spark(vals[-24:])}
    latest = vals[-1]
    chg = latest - vals[-2] if len(vals) > 1 else 0.0
    return {"nm": card["nm"], "val": _fmt(latest, card.get("unit", "%")),
            "chg": f"{chg:+.2f}", "dir": _dir(chg), "s": _spark(vals)}


def cards():
    out = []
    for card in config.MACRO_CARDS:
        try:
            kind = card["kind"]
            if kind == "econ":
                out.append(_econ_card(card))
            elif kind == "ratio":
                out.append(_ratio_card(card))
            else:
                out.append(_quote_card(card))
        except Exception as e:               # blindaje total por tarjeta
            log.warning("macro %s :: %s", card.get("nm"), e)
            out.append({"nm": card["nm"], "val": "n/d", "chg": "—",
                        "dir": "flat", "s": []})
    return out
