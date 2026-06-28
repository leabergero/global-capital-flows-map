"""
RRG — Relative Rotation Graph.

Reproducción abierta y documentada del método de Julius de Kempenaer (el oficial
es propietario). Para cada activo vs un benchmark:

  RS         = 100 * close_activo / close_benchmark        (línea de fuerza rel.)
  RS-Ratio   = 100 + z-score(RS, ventana)                  (eje X)
  RS-Momentum= 100 + z-score( Δ RS-Ratio, ventana)         (eje Y)

Cuadrantes (centro 100,100): líder (X≥100,Y≥100), debilitándose (X≥100,Y<100),
rezagado (X<100,Y<100), mejorando (X<100,Y≥100). La "cola" son las últimas
lecturas, que muestran la rotación (típicamente horaria).

INFERENCIA, no flujo medido: deriva rotación de precios relativos.
"""
import numpy as np
import pandas as pd

import config


def _series(bars):
    """De [{date, close}, ...] ascendente a pd.Series(close) indexada por fecha."""
    if not bars:
        return pd.Series(dtype=float)
    idx = [b["date"] for b in bars]
    return pd.Series([b["close"] for b in bars], index=idx, dtype=float)


def _ratio_momentum(rs: pd.Series, window: int):
    m = rs.rolling(window).mean()
    s = rs.rolling(window).std(ddof=0).replace(0, np.nan)
    rs_ratio = 100 + (rs - m) / s
    roc = rs_ratio.diff()
    mm = roc.rolling(window).mean()
    ss = roc.rolling(window).std(ddof=0).replace(0, np.nan)
    rs_mom = 100 + (roc - mm) / ss
    return rs_ratio, rs_mom


def point(asset_bars, bench_bars, window=None, tail=None):
    """
    Devuelve {'rs', 'mom', 'path'} para un activo vs benchmark, o None si no
    hay datos suficientes. 'path' = lista [[x,y], ...] de la cola.
    """
    window = window or config.RRG_WINDOW
    tail = tail or config.RRG_TAIL
    a = _series(asset_bars)
    b = _series(bench_bars)
    if a.empty or b.empty:
        return None
    df = pd.concat([a, b], axis=1, join="inner").dropna()
    if len(df) < window + tail + 2:
        return None
    rs = 100 * df.iloc[:, 0] / df.iloc[:, 1]
    ratio, mom = _ratio_momentum(rs, window)
    pair = pd.concat([ratio, mom], axis=1).dropna()
    if pair.empty:
        return None
    seq = pair.iloc[-(tail + 1):]
    path = [[round(float(x), 2), round(float(y), 2)]
            for x, y in zip(seq.iloc[:-1, 0], seq.iloc[:-1, 1])]
    cur = seq.iloc[-1]
    return {"rs": round(float(cur[0]), 2),
            "mom": round(float(cur[1]), 2),
            "path": path}


def dataset(pairs, bench_bars, price_lookup):
    """
    pairs: lista (nombre, símbolo). price_lookup(símbolo)->bars.
    Devuelve lista de {name, rs, mom, path} (omite los que no calculan).
    """
    out = []
    for name, sym in pairs:
        pt = point(price_lookup(sym), bench_bars)
        if pt:
            out.append({"name": name, **pt})
    return out
