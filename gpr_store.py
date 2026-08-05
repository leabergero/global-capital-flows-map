"""
Riesgo geopolítico global — AI-GPR de Caldara & Iacoviello.

Qué es
------
El AI-GPR puntúa con un LLM (GPT-4o-mini) los artículos del New York Times,
Washington Post y Chicago Tribune según la intensidad del riesgo geopolítico
que describen, en vez de contar palabras clave como el GPR clásico. Serie
DIARIA continua desde 1960 (24.300+ filas, sin huecos de fecha), calibrada por
el autor a media 100 sobre 1985-2019.

    https://www.matteoiacoviello.com/ai_gpr.html

Capa conceptual: esto NO es ni inferencia sobre precios (RRG/CMF/RORO) ni
dinero observado (flujo ETF/COT) — es **narrativa exógena** medida sobre
prensa. No afirma que el capital se movió ni que vaya a moverse: es contexto.
Ver la tabla de disciplina en CLAUDE.md.

Decisiones de cálculo (y por qué)
--------------------------------
* **Base = media móvil de 30 días, no el dato diario.** El AI-GPR crudo cambia
  un 26,8% MEDIANO de un día al otro (24/07: 233,8 -> 25/07: 274,0 -> 26/07:
  124,2). Un widget sobre el crudo parpadearía sin que pase nada en el mundo.
  Sobre MA30 el cambio mediano diario es 1,03%.
* **Valor mostrado = percentil histórico, no min-max.** El min-max lo aplasta
  todo contra el piso porque un solo evento define el rango: con el dato del
  31/07/2026, el MA30 está en el percentil 94,5 de la historia (el 5,5% de días
  más tensos en 66 años) pero el min-max da 43,5, que se leería como
  "Moderado". Peor todavía: el min-max REESCRIBE la historia — el día que haya
  un récord nuevo, el número de ayer cambia, y el indicador deja de ser
  comparable consigo mismo. El min-max se calcula igual y se guarda, pero solo
  para auditoría interna.
* **Ventana de referencia = 1985 en adelante**, por coherencia con la
  calibración del propio índice (media 100 en 1985-2019). Incluir 1960-1984
  metería Vietnam y la Guerra Fría en la distribución y bajaría el percentil de
  hoy.
* **Cortes no lineales** (50/75/90/97): con cortes lineales 20/40/60/80,
  "Alto o Crítico" sería el 40% de todos los días de la historia y la palabra
  dejaría de significar algo.

Ojo con el retraso: la serie se publica con ~5 días de atraso, así que el panel
muestra SIEMPRE la fecha del dato, nunca "hoy".
"""
import logging
import os
import time

import numpy as np
import pandas as pd
import requests

log = logging.getLogger("gpr")

# Configurable por entorno: si el autor mueve el archivo, no hay que tocar código.
GPR_URL = os.environ.get(
    "GPR_URL",
    "https://www.matteoiacoviello.com/ai_gpr_files/ai_gpr_data_daily.csv")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
STORE = os.path.join(DATA_DIR, "ai_gpr_daily.csv")

COLUMNA = "GPR_AI"          # el índice principal
MA_WINDOW = 30              # días calendario (el CSV trae todos los días)
REF_START = "1985-01-01"    # ventana de referencia del percentil
TIMEOUT = 30
REINTENTOS = 3

# Cortes NO lineales sobre el percentil -> (límite superior, clave, etiqueta es)
NIVELES = (
    (50,  "very_low", "Muy Bajo"),
    (75,  "low",      "Bajo"),
    (90,  "moderate", "Moderado"),
    (97,  "high",     "Alto"),
    (101, "critical", "Crítico"),
)

# Mínimos para aceptar una descarga como válida (ver _validar)
MIN_FILAS = 20_000
COLUMNAS_REQUERIDAS = {"Date", COLUMNA}


# ---------------------------------------------------------------------------
# Descarga y persistencia
# ---------------------------------------------------------------------------
def _validar(df):
    """Levanta ValueError si el CSV descargado no sirve."""
    faltan = COLUMNAS_REQUERIDAS - set(df.columns)
    if faltan:
        raise ValueError(f"faltan columnas: {sorted(faltan)}")
    if len(df) < MIN_FILAS:
        raise ValueError(f"solo {len(df)} filas (se esperaban >= {MIN_FILAS})")
    if df[COLUMNA].isna().all():
        raise ValueError(f"la columna {COLUMNA} viene vacía")
    if df["Date"].isna().any():
        raise ValueError("hay fechas que no se pudieron parsear")
    return df


def descargar():
    """
    Descarga y valida el CSV oficial. Reintenta con backoff.
    Devuelve el DataFrame; levanta la última excepción si agota los intentos.
    """
    ultimo_error = None
    for intento in range(1, REINTENTOS + 1):
        try:
            r = requests.get(GPR_URL, timeout=TIMEOUT)
            r.raise_for_status()
            df = pd.read_csv(pd.io.common.BytesIO(r.content), parse_dates=["Date"])
            return _validar(df)
        except Exception as e:
            ultimo_error = e
            log.warning("descarga AI-GPR falló (intento %d/%d): %s",
                        intento, REINTENTOS, e)
            if intento < REINTENTOS:
                time.sleep(2 ** intento)
    raise ultimo_error


def update():
    """
    Job diario: descarga, compara con lo guardado y persiste el CSV COMPLETO.

    Se guarda el archivo entero (las 15 columnas, no solo GPR_AI) para poder
    crecer después a GPR_OIL, THREATS/ACTS y el desglose regional sin tener que
    volver a construir el histórico.

    Reemplazar el archivo entero hace la operación idempotente por
    construcción: no hay forma de duplicar una fecha. Devuelve el número de
    filas nuevas respecto de la corrida anterior.
    """
    df = descargar()
    previas = 0
    if os.path.exists(STORE):
        try:
            previas = len(pd.read_csv(STORE, usecols=["Date"]))
        except Exception as e:
            log.warning("no se pudo leer el store previo (%s): se reemplaza", e)

    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = STORE + ".tmp"
    df.to_csv(tmp, index=False)
    os.replace(tmp, STORE)                       # escritura atómica
    _CACHE.clear()

    nuevas = len(df) - previas
    log.info("AI-GPR actualizado: %d filas (%+d nuevas), último dato %s",
             len(df), nuevas, df["Date"].iloc[-1].date())
    return nuevas


# ---------------------------------------------------------------------------
# Cálculo
# ---------------------------------------------------------------------------
_CACHE = {}


def _frame():
    """
    DataFrame con date/raw/ma30, cacheado en memoria e invalidado por mtime.

    Sin el caché, cada request releería y re-parsearía 24.000 filas y
    recalcularía el rolling — el mismo problema que ya tuvimos en price_store.
    """
    if not os.path.exists(STORE):
        return None
    mtime = os.path.getmtime(STORE)
    if _CACHE.get("mtime") != mtime:
        df = pd.read_csv(STORE, usecols=["Date", COLUMNA], parse_dates=["Date"])
        df = df.dropna(subset=[COLUMNA]).sort_values("Date")
        df["ma30"] = df[COLUMNA].rolling(MA_WINDOW).mean()
        df = df.dropna(subset=["ma30"]).reset_index(drop=True)
        ref = df.loc[df["Date"] >= REF_START, "ma30"].to_numpy()
        _CACHE.update(mtime=mtime, df=df, ref=np.sort(ref))
    return _CACHE["df"]


def _percentil(valores):
    """% de la referencia (1985-hoy) que queda por DEBAJO de cada valor."""
    ref = _CACHE["ref"]
    return np.searchsorted(ref, valores, side="left") / len(ref) * 100.0


def nivel(percentil):
    """Percentil -> (clave, etiqueta) según los cortes no lineales."""
    for limite, clave, etiqueta in NIVELES:
        if percentil < limite:
            return clave, etiqueta
    return NIVELES[-1][1], NIVELES[-1][2]


def _fila(df, i, pct):
    ma30 = float(df["ma30"].iloc[i])
    clave, etiqueta = nivel(pct)
    return {
        "date": df["Date"].iloc[i].date().isoformat(),
        "raw": round(float(df[COLUMNA].iloc[i]), 2),      # crudo, para auditoría
        "ma30": round(ma30, 2),
        "normalized": round(float(pct), 1),               # = percentil (mostrado)
        "percentile": round(float(pct), 1),
        "level": clave,
        "level_label": etiqueta,
    }


def latest():
    """Último dato disponible, o None si todavía no se descargó nada."""
    df = _frame()
    if df is None or df.empty:
        return None
    pct = _percentil(df["ma30"].to_numpy()[-1:])[0]
    fila = _fila(df, len(df) - 1, pct)
    # min-max: NO se muestra (un solo evento define el rango), se guarda para
    # poder auditar la diferencia contra el percentil.
    ref = _CACHE["ref"]
    fila["minmax"] = round(100 * (fila["ma30"] - ref[0]) / (ref[-1] - ref[0]), 1)
    fila["ref_start"] = REF_START
    fila["source"] = "AI-GPR · Caldara & Iacoviello"
    return fila


def serie():
    """
    DataFrame completo (raw/ma30/percentile) indexado por fecha.

    Para consumo interno de otros módulos: `history()` materializa un dict por
    día, que sobre las 24.000 filas de la serie completa son ~50 MB de objetos
    Python. En la VM de producción (1 GB) eso es plata; acá no se sale de numpy.
    """
    df = _frame()
    if df is None or df.empty:
        return None
    return pd.DataFrame(
        {"raw": df[COLUMNA].to_numpy(),
         "ma30": df["ma30"].to_numpy(),
         "percentile": _percentil(df["ma30"].to_numpy())},
        index=pd.DatetimeIndex(df["Date"]))


def history(days=365):
    """Serie de los últimos `days` días (misma forma que `latest`, sin extras)."""
    df = _frame()
    if df is None or df.empty:
        return []
    days = max(1, min(int(days), len(df)))
    sub = df.iloc[-days:]
    pcts = _percentil(sub["ma30"].to_numpy())
    base = len(df) - days
    return [_fila(df, base + i, pcts[i]) for i in range(len(sub))]


# ---------------------------------------------------------------------------
# Self-check: `python gpr_store.py` (descarga real al final)
# ---------------------------------------------------------------------------
def _self_check():
    assert nivel(0)[0] == "very_low"
    assert nivel(49.9)[0] == "very_low"
    assert nivel(50)[0] == "low"
    assert nivel(89.9)[0] == "moderate"
    assert nivel(90)[0] == "high"
    assert nivel(96.9)[0] == "high"
    assert nivel(97)[0] == "critical"
    assert nivel(100)[0] == "critical"

    # validación: un CSV corto o sin columnas no debe pasar
    for malo, motivo in [(pd.DataFrame({"Date": [], COLUMNA: []}), "vacío"),
                         (pd.DataFrame({"Date": pd.to_datetime(["2026-01-01"]),
                                        "otra": [1]}), "sin GPR_AI")]:
        try:
            _validar(malo)
            raise AssertionError(f"debería haber rechazado el CSV {motivo}")
        except ValueError:
            pass
    print("self-check OK")

    if not os.path.exists(STORE):
        print("sin store local: corriendo update()...")
        update()
    df = _frame()
    ult = latest()
    print(f"filas: {len(df)} | referencia desde {REF_START}: {len(_CACHE['ref'])}")
    print(f"último: {ult['date']}  raw={ult['raw']}  ma30={ult['ma30']}  "
          f"percentil={ult['percentile']}  minmax={ult['minmax']}  "
          f"nivel={ult['level']}")
    assert 0 <= ult["percentile"] <= 100
    assert ult["minmax"] != ult["percentile"], \
        "si coinciden, alguna de las dos normalizaciones está mal"
    h = history(30)
    assert len(h) == 30 and h[-1]["date"] == ult["date"]
    print(f"history(30): {h[0]['date']} -> {h[-1]['date']}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    _self_check()
