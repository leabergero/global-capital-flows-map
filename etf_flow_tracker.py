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

Por qué NO yfinance para shares (2026-08)
-----------------------------------------
El snapshot diario se tomaba de yfinance y resultó no medir nada:
  • 24/43 símbolos devolvían el MISMO `sharesOutstanding` día tras día (SPY
    clavado en 917.782.016 cuando el real es ~1.050M) -> Δshares = 0 -> flujo
    exactamente 0.0 para SPY, AGG, DBC, TLT, XLK, GLD, HYG…
  • los otros 19 no traían `sharesOutstanding` y caían al fallback
    `totalAssets/NAV`, pero `totalAssets` TAMBIÉN viene cacheado y constante:
    shares = K/nav hace que Δshares refleje solo el movimiento del precio, y
    con el signo invertido (precio baja -> "entrada" de capital inexistente).
Ambas patologías se ven en el histórico como AUM idéntico al 4º decimal
durante semanas. Hoy la fuente primaria es stockanalysis.com (shares reales,
43/43 de cobertura) y yfinance queda solo como último recurso, marcado en
`src` para no mezclar escalas entre fuentes. `_is_live()` desconfía de toda
serie con esa firma de dato muerto y devuelve None en vez de un cero o un
ruido que en pantalla se lee como señal.
"""
import io
import json
import os
import re
from datetime import date

import openpyxl
import requests
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
SSGA_URL = ("https://www.ssga.com/library-content/products/fund-data/etfs/us/"
            "navhist-us-en-{}.xlsx")
# Cuántos snapshots conservar por símbolo. La ventana más larga que pide el
# frontend es la de 180d (`build_node` pasa el período como `flow_days`), que
# necesita 181 snapshots; 190 deja margen para feriados. SSGA sirve ~22 años
# por fondo: guardarlos sería inflar el JSON con datos que la herramienta no
# mira nunca — no vamos más atrás de 6 meses de mercado.
MAX_KEEP = 190
_MESES = {m: i for i, m in enumerate(
    "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1)}


def _fetch_ssga_history(symbol):
    """
    Serie histórica COMPLETA [{date, shares, nav, src}] de un SPDR, o [].

    SSGA publica el NAV history diario con `Shares Outstanding` real —
    ~22 años por fondo, la única fuente gratuita que encontramos con
    HISTÓRICO (stockanalysis solo da el corte de hoy, e iShares bloquea la
    descarga con un bot-check que devuelve HTML con Content-Type text/csv).
    Cubre 16/43 del universo: SPY, los 11 sectores XLx, GLD, KBE, KIE, XOP.
    """
    try:
        r = requests.get(SSGA_URL.format(symbol.lower()),
                         headers={"User-Agent": SA_UA}, timeout=45)
        if r.status_code != 200 or "spreadsheet" not in r.headers.get("Content-Type", ""):
            return []                       # no es SPDR: la respuesta es el HTML del 404
        ws = openpyxl.load_workbook(io.BytesIO(r.content), read_only=True).active
        rows = list(ws.iter_rows(values_only=True))
    except Exception:
        return []

    out = []
    for row in rows:
        # cabecera y filas de metadata (Fund Name, Ticker Symbol, vacías)
        if not row or len(row) < 3 or not isinstance(row[0], str):
            continue
        try:
            d, mes, a = row[0].split("-")           # '04-Aug-2026'
            fecha = f"{int(a):04d}-{_MESES[mes]:02d}-{int(d):02d}"
        except (ValueError, KeyError):
            continue
        nav, shares = row[1], row[2]
        if not isinstance(nav, (int, float)) or not isinstance(shares, (int, float)):
            continue
        out.append({"date": fecha, "shares": round(shares),
                    "nav": round(float(nav), 4), "src": "ssga"})
    out.sort(key=lambda r_: r_["date"])             # el xlsx viene descendente
    return out


SA_URL = "https://stockanalysis.com/etf/{}/__data.json"
SA_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
         "Chrome/120.0.0.0 Safari/537.36")
_SUFFIX = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}


def _num(v):
    """'$41.69B' / '505.60M' / 1234.5 -> float, o None si no es un número."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    if not isinstance(v, str):
        return None
    m = re.fullmatch(r"(-?\d+(?:\.\d+)?)\s*([KMBT])?",
                     v.strip().replace("$", "").replace(",", ""))
    return float(m.group(1)) * _SUFFIX.get(m.group(2) or "", 1) if m else None


def _fetch_stockanalysis(symbol):
    """
    (shares_outstanding, nav) reales, o (None, None).

    El payload es el `__data.json` de SvelteKit: los objetos guardan índices
    contra un array plano de valores, así que hay que desreferenciar.
    El NAV se toma como aum/shares (consistente por construcción y de la misma
    fecha de corte, en vez de mezclar un precio de otra fuente).
    """
    try:
        r = requests.get(SA_URL.format(symbol.lower()),
                         headers={"User-Agent": SA_UA}, timeout=20)
        if r.status_code != 200:
            return None, None
        doc = r.json()
    except Exception:
        return None, None
    for node in doc.get("nodes", []):
        values = node.get("data")
        if not isinstance(values, list):
            continue
        for v in values:
            if not (isinstance(v, dict) and "sharesOut" in v and "aum" in v):
                continue
            i_sh, i_aum = v["sharesOut"], v["aum"]
            if not (isinstance(i_sh, int) and isinstance(i_aum, int)):
                continue
            shares = _num(values[i_sh])
            aum = _num(values[i_aum])
            if shares and aum:
                return round(shares), aum / shares
    return None, None


def _fetch_yfinance(symbol):
    """
    Último recurso. OJO: yfinance sirve shares/AUM cacheados que pueden estar
    congelados semanas (ver docstring del módulo) — por eso queda marcado como
    src='yf' y `_is_live()` descarta la serie si no se mueve.
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


def _fetch(symbol):
    """(shares_outstanding, nav, fuente) actuales de un ETF, o (None, None, None)."""
    shares, nav = _fetch_stockanalysis(symbol)
    if shares:
        return shares, nav, "sa"
    shares, nav = _fetch_yfinance(symbol)
    if shares:
        return shares, nav, "yf"
    return None, None, None


def snapshot(symbols, today=None):
    """
    Toma un snapshot de hoy para cada símbolo y lo agrega al histórico.
    Idempotente: si ya hay snapshot de hoy, lo reemplaza (no duplica).

    Para los SPDR reemplaza la serie entera con el navhist de SSGA en vez de
    ir agregando un punto por día: la fuente es autoritativa y trae el
    histórico completo, así que la primera corrida ya deja 5d/20d/50d
    disponibles (backfill) y las siguientes corrigen cualquier hueco por sí
    solas. Para el resto no hay histórico gratuito: se acumula hacia adelante.

    Devuelve (capturados, total, backfilled).
    """
    today = today or date.today().isoformat()
    store = _load()
    captured = backfilled = 0
    for sym in symbols:
        hist = _fetch_ssga_history(sym)
        if len(hist) >= 2:
            store[sym] = hist[-MAX_KEEP:]
            captured += 1
            backfilled += 1
            continue
        shares, nav, src = _fetch(sym)
        if shares is None:
            continue
        series = store.setdefault(sym, [])
        series[:] = [s for s in series if s["date"] != today]   # idempotencia
        series.append({"date": today, "shares": shares,
                       "nav": round(nav, 4), "src": src})
        series.sort(key=lambda s: s["date"])
        del series[:-MAX_KEEP]
        captured += 1
    _save(store)
    return captured, len(symbols), backfilled


# ---------------------------------------------------------------------------
# Cálculo de flujo
# ---------------------------------------------------------------------------
def _daily_flows(series):
    """
    Flujos diarios (USD) entre snapshots consecutivos.

    Ignora los pares que cruzan de una fuente a otra: cada fuente mide shares
    en su propia escala (yfinance daba 109,7M para TLT donde el real es 505,6M),
    así que ese salto sería un flujo fantasma de miles de millones.
    """
    out = []
    for prev, cur in zip(series, series[1:]):
        if prev.get("src") != cur.get("src"):
            continue
        if _es_split(prev, cur):
            continue
        out.append((cur["shares"] - prev["shares"]) * cur["nav"])
    return out


def _es_split(prev, cur):
    """
    ¿El salto de shares es un split y no dinero?

    En un split las unidades se multiplican y el NAV se divide por el mismo
    factor: el AUM queda igual, no entró ni salió un dólar. Visto en XLK el
    2025-12-05 (shares +99,7%, NAV −49,6%), que sin este guard aparecía como
    una entrada de 47.600 millones — más que todo el flujo real del semestre.
    Pide las DOS condiciones, así que una creación grande de verdad (que no
    mueve el NAV) no se confunde con un split.
    """
    if not prev["shares"] or not prev["nav"]:
        return False
    ratio = cur["shares"] / prev["shares"]
    if abs(ratio - 1) <= 0.15:
        return False
    return abs(ratio * cur["nav"] / prev["nav"] - 1) < 0.02


def _is_live(window):
    """
    ¿La serie mide algo, o es un dato congelado disfrazado de flujo?

    Dos firmas de dato muerto, ambas vistas en producción con yfinance:
      • shares idéntico en toda la ventana -> Δ=0 siempre. En 43 ETFs líquidos
        no existen 5 días sin una sola creación/redención: es el campo cacheado.
      • AUM constante mientras shares varía -> shares se derivó de un
        totalAssets fijo dividido por el NAV, así que el "flujo" es el precio
        con el signo dado vuelta.
    Preferimos None (tile gris + aviso) antes que un número que se lee como
    señal. Es la única capa que el terminal declara OBSERVADA: si no mide, calla.
    """
    shares = {r["shares"] for r in window}
    if len(shares) < 2:
        return False
    aums = [r["shares"] * r["nav"] for r in window]
    return (max(aums) - min(aums)) / max(aums) > 1e-6


def _usable(series):
    """
    Snapshots comparables entre sí: los de la fuente del último snapshot.

    Descarta solo los de OTRAS fuentes, así que el histórico yfinance viejo se
    ignora sin borrar el archivo, y un día suelto en que stockanalysis falle no
    parte la serie en dos (queda un hueco de un día, no un flujo fantasma).
    """
    if not series:
        return []
    src = series[-1].get("src")
    return [r for r in series if r.get("src") == src]


def flow_window(symbol, days):
    """
    Flujo acumulado (USD) de los últimos `days` snapshots disponibles, o None si
    aún no hay histórico suficiente (se necesitan >=2 snapshots) o si la serie
    no mide nada (ver `_is_live`).
    """
    window = _usable(_load().get(symbol, []))[-(days + 1):]
    if len(window) < 2 or not _is_live(window):
        return None
    flows = _daily_flows(window)
    return sum(flows) if flows else None


def all_windows(symbol):
    """Dict {5: flujo, 20: flujo, 50: flujo} para un símbolo (valores o None)."""
    return {w: flow_window(symbol, w) for w in WINDOWS}


def history_depth():
    """
    Días de histórico USABLE (el ETF con más snapshots de la fuente vigente).
    El frontend lo muestra como 'llevás N días' — contar snapshots de una
    fuente descartada prometería ventanas que nunca van a aparecer.
    """
    store = _load()
    return max((len(_usable(s)) for s in store.values()), default=0)


def coverage():
    """Resumen por símbolo: cuántos snapshots usables tiene cada uno."""
    return {sym: len(_usable(series)) for sym, series in sorted(_load().items())}


# ---------------------------------------------------------------------------
# Self-check: `python etf_flow_tracker.py` (sin red salvo el último bloque)
# ---------------------------------------------------------------------------
def _self_check():
    assert _num("505.60M") == 505_600_000
    assert _num("$41.69B") == 41_690_000_000
    assert _num("1,234.5") == 1234.5
    assert _num("n/a") is None and _num(None) is None

    def serie(pares, src="sa"):
        return [{"date": f"2026-08-{i + 1:02d}", "shares": sh, "nav": nav, "src": src}
                for i, (sh, nav) in enumerate(pares)]

    # shares congelado (yfinance): 0.0 falso -> None
    muerta = serie([(1000, 10.0), (1000, 11.0), (1000, 9.0)])
    assert not _is_live(muerta)

    # AUM constante, shares = K/nav (fallback totalAssets/NAV): ruido -> None
    degenerada = serie([(1000, 10.0), (1250, 8.0), (800, 12.5)])
    assert not _is_live(degenerada)

    # creación/redención real
    viva = serie([(1000, 10.0), (1100, 10.2), (1050, 10.1)])
    assert _is_live(viva)
    assert _daily_flows(viva) == [100 * 10.2, -50 * 10.1]

    # el salto entre fuentes no inventa un flujo
    mixta = serie([(1000, 10.0), (1100, 10.2)]) + serie([(5000, 10.3)], src="yf")
    assert _daily_flows(mixta) == [100 * 10.2]

    # split 2:1 (XLK, 2025-12-05): shares x2 y NAV /2 -> no es flujo
    split = serie([(325_805_897, 291.04), (650_611_794, 146.62),
                   (651_000_000, 147.0)])
    assert _daily_flows(split) == [(651_000_000 - 650_611_794) * 147.0]
    # creación real del 20% (el NAV no se mueve): SÍ es flujo
    grande = serie([(1000, 10.0), (1200, 10.05)])
    assert _daily_flows(grande) == [200 * 10.05]

    # migración: el histórico yfinance viejo se ignora sin borrar el archivo
    vieja = [{"date": "2026-07-01", "shares": 999, "nav": 5.0}]     # sin 'src'
    assert _usable(vieja + viva) == viva
    assert _usable(vieja) == vieja      # mientras no haya fuente nueva, se usa

    print("self-check OK")

    # Fuentes en vivo (se saltean si no hay red)
    hist = _fetch_ssga_history("SPY")
    if hist:
        print(f"SSGA SPY: {len(hist)} filas, {hist[0]['date']} -> {hist[-1]['date']}")
        assert len(hist) > 180, "navhist corto: no alcanza para la ventana de 180d"
        assert hist == sorted(hist, key=lambda r: r["date"]), "sin ordenar"
        assert 5e8 < hist[-1]["shares"] < 3e9, hist[-1]
        assert _is_live(hist[-51:]), "el histórico de SSGA debería moverse"
    assert not _fetch_ssga_history("TLT"), "TLT no es SPDR: debería dar []"

    shares, nav, src = _fetch("TLT")
    if shares:
        print(f"TLT en vivo: shares={shares:,} nav={nav:.2f} src={src}")
        assert src == "sa", "stockanalysis caído: cayó al yfinance congelado"
        assert 3e8 < shares < 1e9, f"shares de TLT fuera de rango: {shares}"
    else:
        print("sin red: omitido el chequeo de fuente en vivo")


if __name__ == "__main__":
    _self_check()
