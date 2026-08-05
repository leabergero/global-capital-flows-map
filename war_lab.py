"""
War Lab — ¿qué sectores aprovechan las crisis geopolíticas y cuáles pierden?

Cruza el AI-GPR (riesgo geopolítico medido sobre prensa, ver `gpr_store.py`)
con los retornos de los 11 sectores del S&P y con el compuesto RORO, sobre
~26 años de historia (los SPDR sectoriales cotizan desde fines de 1998).

Qué responde
------------
1. `regimenes`  — retorno RELATIVO anualizado de cada sector (vs SPY) cuando el
   riesgo está alto (percentil >= 90) contra cuando está bajo (< 50). Es la
   respuesta directa a "quién gana y quién pierde en las crisis".
2. `betas`      — sensibilidad del retorno relativo diario de cada sector a un
   SHOCK de riesgo (variación diaria del GPR en desviaciones estándar), con su
   t-estadístico. Mide reacción inmediata, no nivel.
3. `eventos`    — estudio de eventos: los picos históricos de riesgo (percentil
   >= 97, agrupados) y el retorno relativo acumulado de cada sector en los 20
   días hábiles siguientes.
4. `roro_gpr`   — correlación entre el compuesto RORO y el riesgo geopolítico,
   en niveles y en cambios, más la nube de puntos para graficarla.

Por qué retorno RELATIVO y no absoluto
--------------------------------------
En una crisis suele caer todo. Un sector que baja 8% cuando el mercado baja 12%
está GANANDO la rotación: ahí es donde se refugia el capital. El retorno
absoluto solo mediría el movimiento del mercado, que ya es la pregunta del
RORO. Restando SPY queda el efecto sector, que es lo que se pregunta acá.

Advertencias que la página repite al usuario
--------------------------------------------
* Esto es CORRELACIÓN HISTÓRICA, no causalidad ni predicción. El AI-GPR mide
  cobertura periodística, no la guerra en sí.
* Cada crisis es idiosincrática: el petróleo dominó 1990 y 2022, pero no 2001.
  Las medias esconden esa dispersión — por eso se muestran también los eventos
  uno por uno.
* El índice se publica con ~5 días de retraso: sirve para leer el régimen, no
  para anticiparlo.
"""
import logging
import os

import numpy as np
import pandas as pd

import config
import gpr_store

log = logging.getLogger("war_lab")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
PRECIOS = os.path.join(DATA_DIR, "war_prices.csv")
DESDE = "1998-12-01"        # arranque de los SPDR sectoriales

SECTORES = {
    "XLE": "Energía", "XLK": "Tecnología", "XLF": "Financials",
    "XLV": "Salud", "XLY": "Cons. discrec.", "XLP": "Cons. básico",
    "XLI": "Industriales", "XLB": "Materiales", "XLU": "Utilities",
    "XLRE": "Inmobiliario", "XLC": "Comunicaciones",
}
BENCH = "SPY"
# Símbolos extra que necesita el compuesto RORO (además de SPY/XLY/XLP)
EXTRA = ["TLT", "CPER", "GLD", "HYG", "IEF", "VIXY", "GDX", "ITA", "USO"]

ALTO, BAJO = 90.0, 50.0     # cortes de percentil para el análisis de régimen
PICO = 97.0                 # percentil que define un "evento"
VENTANA_EVENTO = 20         # días hábiles posteriores al pico
DIAS_ANIO = 252


# ---------------------------------------------------------------------------
# Datos
# ---------------------------------------------------------------------------
def descargar_precios(force=False):
    """
    Cierres ajustados diarios desde 1998. Se cachean en data/war_prices.csv.

    No usa `price_store` a propósito: ese guarda una ventana fija de 320 barras
    (~15 meses) porque le alcanza para el RRG, y acá hacen falta 26 años para
    que entren el 11-S, Irak, Crimea, Ucrania y Gaza.
    """
    if os.path.exists(PRECIOS) and not force:
        return pd.read_csv(PRECIOS, index_col=0, parse_dates=True)

    import yfinance as yf
    simbolos = sorted(set(SECTORES) | {BENCH} | set(EXTRA))
    log.info("descargando %d símbolos desde %s (una sola vez)...",
             len(simbolos), DESDE)
    raw = yf.download(simbolos, start=DESDE, auto_adjust=True,
                      progress=False, threads=True)["Close"]
    raw = raw.dropna(how="all").sort_index()
    os.makedirs(DATA_DIR, exist_ok=True)
    raw.to_csv(PRECIOS)
    return raw


def _serie_gpr():
    """percentil diario del AI-GPR MA30, indexado por fecha."""
    df = gpr_store.serie()
    if df is None or df.empty:
        raise RuntimeError("no hay datos de AI-GPR: corré gpr_store.update()")
    return df


def _roro_historico(px):
    """
    Compuesto RORO reconstruido sobre la historia larga, con la MISMA
    definición que `compute/roro.py` (mismos ratios, misma ventana, mismo
    z-score acotado a ±3), pero vectorizado sobre toda la serie en vez del
    último valor. Los componentes que todavía no cotizaban en una fecha
    simplemente no promedian ahí (CPER y VIXY arrancan en 2011).
    """
    w = config.RORO_WINDOW
    zs = []
    for comp in config.RORO_COMPONENTS:
        a, b = comp["a"], comp["b"]
        if a not in px.columns or (b and b not in px.columns):
            continue
        ratio = px[a] / px[b] if b else px[a]
        z = (ratio - ratio.rolling(w).mean()) / ratio.rolling(w).std(ddof=0)
        if comp["inv"]:
            z = -z
        zs.append(z.clip(-3, 3))
    return pd.concat(zs, axis=1).mean(axis=1, skipna=True) if zs else None


def dataset():
    """Tabla diaria alineada: precios, retornos relativos, GPR y RORO."""
    px = descargar_precios()
    gpr = _serie_gpr()

    ret = np.log(px).diff()                       # retornos log diarios
    rel = ret[list(SECTORES)].sub(ret[BENCH], axis=0)   # exceso sobre el mercado
    roro = _roro_historico(px)

    df = rel.copy()
    df["_mkt"] = ret[BENCH]
    df["roro"] = roro
    # El GPR trae todos los días calendario; el mercado no. Se alinea al día
    # hábil (reindex + ffill) para no perder los picos de fin de semana.
    df["gpr_pct"] = gpr["percentile"].reindex(df.index, method="ffill")
    df["gpr_ma30"] = gpr["ma30"].reindex(df.index, method="ffill")
    return df.dropna(subset=["gpr_pct"])


# ---------------------------------------------------------------------------
# Análisis
# ---------------------------------------------------------------------------
def por_regimen(df):
    """
    Retorno relativo anualizado de cada sector en riesgo alto vs bajo.

    Se reporta también `spread_aj`, la misma diferencia pero DEMEDIADA POR AÑO
    (a cada sector se le resta su propia media de ese año antes de comparar).
    Sin ese control el resultado es una trampa: los años de riesgo alto están
    concentrados (2001-2003, 2022-2026), así que el sector que simplemente tuvo
    una buena década aparece como "ganador de las guerras". Tecnología es el
    caso de manual — sale primera en el spread crudo porque el GPR alto de
    2023-2026 coincide con el boom de IA, no porque se beneficie de las
    crisis; su beta al shock es, de hecho, la más NEGATIVA de las once.
    """
    anio = df.index.year
    filas = []
    for sym, nombre in SECTORES.items():
        s = df[sym]
        aj = s - s.groupby(anio).transform("mean")     # sin drift secular
        m_alto, m_bajo = df["gpr_pct"] >= ALTO, df["gpr_pct"] < BAJO
        a, b = s[m_alto].dropna(), s[m_bajo].dropna()
        if len(a) < 60 or len(b) < 60:
            continue
        ra, rb = a.mean() * DIAS_ANIO * 100, b.mean() * DIAS_ANIO * 100
        aa = aj[m_alto].dropna().mean() * DIAS_ANIO * 100
        ab = aj[m_bajo].dropna().mean() * DIAS_ANIO * 100
        filas.append({
            "symbol": sym, "name": nombre,
            "alto": round(float(ra), 1),
            "bajo": round(float(rb), 1),
            "spread": round(float(ra - rb), 1),
            "spread_aj": round(float(aa - ab), 1),
            "dias_alto": int(len(a)),
            "hit": round(float((a > 0).mean() * 100), 1),   # % de días en verde
        })
    return sorted(filas, key=lambda f: f["spread_aj"], reverse=True)


def betas(df):
    """
    Sensibilidad a un shock de riesgo: OLS de ret_relativo ~ ΔGPR_estandarizado.
    Se reporta el t-estadístico para no leer como señal lo que es ruido.
    """
    shock = df["gpr_ma30"].diff()
    shock = (shock / shock.std()).rename("shock")
    filas = []
    for sym, nombre in SECTORES.items():
        d = pd.concat([df[sym], shock], axis=1).dropna()
        if len(d) < 250:
            continue
        x, y = d["shock"].to_numpy(), d[sym].to_numpy()
        beta, alfa = np.polyfit(x, y, 1)
        resid = y - (beta * x + alfa)
        se = np.sqrt((resid @ resid) / (len(x) - 2) / ((x - x.mean()) @ (x - x.mean())))
        filas.append({
            "symbol": sym, "name": nombre,
            # en puntos básicos por 1 sigma de shock, que se lee mejor
            "beta_bp": round(float(beta * 10_000), 1),
            "t": round(float(beta / se), 2) if se else 0.0,
            "n": int(len(d)),
        })
    return sorted(filas, key=lambda f: f["beta_bp"], reverse=True)


def eventos(df, max_eventos=12):
    """
    Picos de riesgo (percentil >= PICO) agrupados en episodios, con el retorno
    relativo acumulado de cada sector en los VENTANA_EVENTO días siguientes.
    """
    marca = df["gpr_pct"] >= PICO
    # un episodio nuevo empieza cuando hubo al menos 60 días hábiles de calma
    inicio = marca & (~marca.shift(1, fill_value=False))
    fechas = [f for f in df.index[inicio]]
    episodios, ultima = [], None
    for f in fechas:
        if ultima is None or (f - ultima).days > 120:
            episodios.append(f)
        ultima = f

    salida = []
    for f in episodios[-max_eventos:]:
        i = df.index.get_loc(f)
        fin = min(i + VENTANA_EVENTO, len(df) - 1)
        if fin <= i:
            continue
        tramo = df.iloc[i:fin + 1]
        rend = {sym: round(float(tramo[sym].sum() * 100), 1)
                for sym in SECTORES if tramo[sym].notna().any()}
        if not rend:
            continue
        ganador = max(rend, key=rend.get)
        perdedor = min(rend, key=rend.get)
        salida.append({
            "date": f.date().isoformat(),
            "gpr": round(float(df["gpr_ma30"].iloc[i]), 1),
            "pct": round(float(df["gpr_pct"].iloc[i]), 1),
            "mercado": round(float(tramo["_mkt"].sum() * 100), 1),
            "sectores": rend,
            "ganador": {"symbol": ganador, "name": SECTORES[ganador],
                        "ret": rend[ganador]},
            "perdedor": {"symbol": perdedor, "name": SECTORES[perdedor],
                         "ret": rend[perdedor]},
        })
    return list(reversed(salida))


def roro_vs_gpr(df):
    """Correlación RORO ↔ riesgo geopolítico, en niveles y en cambios."""
    d = df[["roro", "gpr_pct", "gpr_ma30"]].dropna()
    if len(d) < 250:
        return None
    niveles = float(d["roro"].corr(d["gpr_pct"]))
    cambios = float(d["roro"].diff().corr(d["gpr_ma30"].diff()))
    # nube de puntos submuestreada: 1 de cada 5 días, para que el SVG no pese
    puntos = [[round(float(r.gpr_pct), 1), round(float(r.roro), 2)]
              for r in d.iloc[::5].itertuples()]
    # RORO medio por decil de riesgo: la lectura que de verdad importa
    deciles = (d.groupby(pd.cut(d["gpr_pct"], np.arange(0, 101, 10)),
                         observed=True)["roro"].mean().round(2))
    return {
        "corr_niveles": round(niveles, 3),
        "corr_cambios": round(cambios, 3),
        "n": int(len(d)),
        "puntos": puntos,
        "deciles": [{"rango": f"{int(iv.left)}-{int(iv.right)}",
                     "roro": None if pd.isna(v) else float(v)}
                    for iv, v in deciles.items()],
    }


def serie_grafico(df, años=8):
    """Serie para el gráfico temporal: percentil GPR y RORO, submuestreada."""
    d = df.iloc[-int(años * DIAS_ANIO):][["gpr_pct", "roro"]].dropna()
    paso = max(1, len(d) // 900)
    return [{"date": i.date().isoformat(),
             "gpr": round(float(r.gpr_pct), 1),
             "roro": round(float(r.roro), 2)}
            for i, r in zip(d.index[::paso], d.iloc[::paso].itertuples())]


def analizar():
    """Todo el análisis en un dict listo para servir como JSON."""
    df = dataset()
    ult = gpr_store.latest()
    return {
        "meta": {
            "desde": df.index[0].date().isoformat(),
            "hasta": df.index[-1].date().isoformat(),
            "dias": int(len(df)),
            "corte_alto": ALTO, "corte_bajo": BAJO, "corte_pico": PICO,
            "ventana_evento": VENTANA_EVENTO,
            "gpr_hoy": ult,
        },
        "regimenes": por_regimen(df),
        "betas": betas(df),
        "eventos": eventos(df),
        "roro_gpr": roro_vs_gpr(df),
        "serie": serie_grafico(df),
    }


# ---------------------------------------------------------------------------
# Self-check: `python war_lab.py`
# ---------------------------------------------------------------------------
def _self_check():
    # el retorno relativo debe anular el mercado: si un sector ES el mercado,
    # su exceso es cero
    idx = pd.bdate_range("2020-01-01", periods=10)
    px = pd.DataFrame({"SPY": np.linspace(100, 110, 10)}, index=idx)
    ret = np.log(px).diff()
    assert abs(float((ret["SPY"] - ret["SPY"]).sum())) < 1e-12

    # el z-score del RORO se acota a ±3 en ambos sentidos
    px2 = pd.DataFrame({s: np.r_[np.ones(80), np.array([50.0])]
                        for s in ["SPY", "TLT", "CPER", "GLD", "XLY", "XLP",
                                  "HYG", "IEF", "VIXY"]},
                       index=pd.bdate_range("2020-01-01", periods=81))
    z = _roro_historico(px2)
    assert z.abs().max() <= 3.0 + 1e-9, z.abs().max()
    print("self-check OK")

    r = analizar()
    m = r["meta"]
    print(f"muestra: {m['desde']} -> {m['hasta']}  ({m['dias']} días hábiles)")
    print(f"GPR hoy: {m['gpr_hoy']['percentile']} pct ({m['gpr_hoy']['level']})")
    print("\nretorno relativo anualizado (riesgo alto vs bajo):")
    for f in r["regimenes"]:
        print(f"  {f['name']:<16} alto={f['alto']:>7.1f}%  bajo={f['bajo']:>7.1f}%"
              f"  spread={f['spread']:>7.1f} pp   ajustado={f['spread_aj']:>7.1f} pp")
    print("\nbeta al shock (pb por 1σ, t-stat):")
    for f in r["betas"]:
        print(f"  {f['name']:<16} {f['beta_bp']:>7.1f} pb   t={f['t']:>6.2f}")
    rg = r["roro_gpr"]
    print(f"\nRORO vs GPR: corr niveles={rg['corr_niveles']}  "
          f"cambios={rg['corr_cambios']}  (n={rg['n']})")
    print("\nepisodios de riesgo extremo (+20d):")
    for e in r["eventos"][:8]:
        print(f"  {e['date']}  GPR={e['gpr']:>6.1f}  mercado={e['mercado']:>6.1f}%"
              f"   gana {e['ganador']['name']} ({e['ganador']['ret']:+.1f}%)"
              f"   pierde {e['perdedor']['name']} ({e['perdedor']['ret']:+.1f}%)")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    _self_check()
