"""
CMF — Chaikin Money Flow. Mide PRESIÓN (acumulación/distribución), no flujo.

  MFM = ((Close - Low) - (High - Close)) / (High - Low)   [posición del cierre]
  MFV = MFM * Volumen
  CMF = Σ(MFV, n) / Σ(Volumen, n)

Cierre arriba del rango con volumen -> acumulación (CMF>0); abajo -> distribución
(CMF<0). Captura el matiz distribución-vs-capitulación porque pondera DÓNDE
cierra dentro de la barra, no solo si subió o bajó. Sigue siendo proxy: se
etiqueta como presión, nunca como "entró/salió capital".
"""
import numpy as np
import pandas as pd

import config


def cmf(bars, n=None):
    """CMF más reciente a partir de barras OHLCV ascendentes, o None."""
    n = n or config.CMF_WINDOW
    if not bars or len(bars) < n:
        return None
    df = pd.DataFrame(bars)
    if not {"high", "low", "close", "volume"}.issubset(df.columns):
        return None
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    mfm = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / rng
    mfv = mfm.fillna(0) * df["volume"]
    vol_sum = df["volume"].rolling(n).sum()
    cmf_series = mfv.rolling(n).sum() / vol_sum.replace(0, np.nan)
    val = cmf_series.iloc[-1]
    if pd.isna(val):
        return None
    return round(float(val), 3)
