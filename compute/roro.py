"""
RORO — risk-on / risk-off. Termómetro de régimen.

Para cada componente (un ratio a/b de precios) calculamos el z-score sobre una
ventana; el signo se orienta para que "risk-on" sea positivo (los marcados 'inv'
se invierten: suben cuando el ratio baja, p.ej. VIX). El compuesto es el promedio
de los z, escalado para leerse en ±3.
"""
import numpy as np
import pandas as pd

import config


def _z_last(series: pd.Series, window: int):
    if len(series) < window + 1:
        return None
    m = series.rolling(window).mean().iloc[-1]
    s = series.rolling(window).std(ddof=0).iloc[-1]
    if pd.isna(s) or s == 0:
        return None
    return float((series.iloc[-1] - m) / s)


def _close(bars):
    return pd.Series([b["close"] for b in bars],
                     index=[b["date"] for b in bars], dtype=float) if bars else pd.Series(dtype=float)


def components(price_lookup, window=None):
    """
    Devuelve (lista [[name, z], ...], compuesto). price_lookup(sym)->bars.
    """
    window = window or config.RORO_WINDOW
    rows = []
    zs = []
    for comp in config.RORO_COMPONENTS:
        a = _close(price_lookup(comp["a"]))
        if comp["b"]:
            b = _close(price_lookup(comp["b"]))
            df = pd.concat([a, b], axis=1, join="inner").dropna()
            if df.empty:
                continue
            ratio = df.iloc[:, 0] / df.iloc[:, 1]
        else:
            ratio = a.dropna()
        z = _z_last(ratio, window)
        if z is None:
            continue
        if comp["inv"]:
            z = -z
        z = max(-3.0, min(3.0, z))
        rows.append([comp["name"], round(z, 2)])
        zs.append(z)
    composite = round(float(np.mean(zs)) * 1.0, 2) if zs else 0.0
    return rows, composite


def regime(composite):
    if composite >= 0.75:
        return {"state": "Risk-On", "score": composite, "color": "green"}
    if composite <= -0.75:
        return {"state": "Risk-Off", "score": composite, "color": "red"}
    return {"state": "Neutral / transición", "score": composite, "color": "amber"}
