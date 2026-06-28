"""
Configuración central del backend.

Todos los símbolos de FMP, los TTL de caché por cadencia y los parámetros de
cálculo viven acá para que sean triviales de editar. Si una tarjeta macro sale
"n/d" o un panel cae a demo, lo más probable es que el símbolo/endpoint no esté
en tu plan de FMP o use otra convención: se ajusta en este archivo.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- credenciales -----------------------------------------------------------
FMP_API_KEY = os.environ.get("FMP_API_KEY", "").strip()
FRED_API_KEY = os.environ.get("FRED_API_KEY", "").strip()
QUANDL_API_KEY = os.environ.get("QUANDL_API_KEY", "").strip()
_PLACEHOLDER = {"", "tu_key_regenerada", "tu_fred_key", "tu_quandl_key", "REEMPLAZAR", "CHANGEME"}
# Si no hay key real, el backend corre en modo DEMO (datos sintéticos, sin red).
DEMO_MODE = FMP_API_KEY in _PLACEHOLDER

# --- FMP --------------------------------------------------------------------
FMP_BASE_V3 = "https://financialmodelingprep.com/api/v3"
FMP_BASE_V4 = "https://financialmodelingprep.com/api/v4"
FMP_BASE_STABLE = "https://financialmodelingprep.com/stable"

# --- Quandl COT (Commitment of Traders) - gratis ----
# Obtené key en https://www.quandl.com/ (registro gratis)
QUANDL_COT_MAP = {
    "ES": "CFTC/ES_ALL",    # S&P 500 E-mini
    "CL": "CFTC/CL_ALL",    # Light Sweet Crude
    "GC": "CFTC/GC_ALL",    # Gold
    "ZN": "CFTC/ZN_ALL",    # 10-Year Treasury Note
    "DX": "CFTC/DX_ALL",    # Dollar Index
    "BTC": "CFTC/BTC_ALL",  # Bitcoin (si disponible)
}

HTTP_TIMEOUT = 15          # segundos por request
MAX_WORKERS = 8            # paralelismo al traer históricos
HISTORY_DAYS = 200         # ventana de precios para RRG/CMF/RORO

# --- caché por cadencia (segundos) ------------------------------------------
TTL = {
    "price":  60 * 60,          # históricos / RRG / CMF / RORO -> horaria
    "flows":  60 * 60 * 24,     # flujo implícito ETF          -> diaria
    "cot":    60 * 60 * 24 * 7, # COT                          -> semanal
    "macro":  60 * 60 * 24,     # macro                        -> diaria
    "news":   60 * 15,          # noticias                     -> intradía
    "snapshot": 60 * 60,        # ensamblado completo
}

# --- mapeo de símbolos para yfinance (quote) --------------------------------
# Algunos símbolos necesitan conversión para que yfinance los entienda
YFINANCE_SYMBOL_MAP = {
    "EURUSD":   "EURUSD=X",    # divisas: =X suffix
    "USDJPY":   "JPY=X",       # o directamente a pares
    "GCUSD":    "GC=F",        # commodities: =F for futures, o usar ETF
    "CLUSD":    "CL=F",        # WTI crudo futures
    "WTIUSD":   "USO",         # WTI: usar ETF (más liquido)
    "BZUSD":    "BZ=F",        # Brent crudo futures
    "BTCUSD":   "BTC-USD",     # cripto: -USD suffix
    "^TNX":     "^TNX",        # bonos 10Y: índice directo
    "^DXY":     "UUP",         # índice dólar: usar UUP (USD strength ETF)
    "IEF":      "IEF",         # bonos intermedios: ETF
    "GLD":      "GLD",         # oro: ETF
    "DX":       "UUP",         # dólar: UUP como proxy
    "UUP":      "UUP",         # USD strength ETF
}

# --- parámetros de cálculo --------------------------------------------------
RRG_WINDOW = 12        # ventana de normalización RS (en barras)
RRG_TAIL = 5           # nº de lecturas en la cola del RRG
CMF_WINDOW = 20        # ventana Chaikin Money Flow
RORO_WINDOW = 60       # ventana z-score de los ratios RORO

# --- benchmarks RRG ---------------------------------------------------------
BENCH_EQUITY = "SPY"   # sectores vs S&P500
BENCH_CROSS = "ACWI"   # cross-asset vs índice mundial (cambiá a "URTH"/"VT" si preferís)

# --- componentes RORO (pares de símbolos; ratio = a/b, signo risk-on +) -----
# Para "inv" se invierte el signo del z-score (sube cuando baja el ratio).
RORO_COMPONENTS = [
    {"name": "SPY / Bonos USA",    "a": "SPY",  "b": "TLT",  "inv": False},
    {"name": "Cobre / Oro",        "a": "CPER", "b": "GLD",  "inv": False},
    {"name": "Cíclicos / Defens.", "a": "XLY",  "b": "XLP",  "inv": False},
    {"name": "Spread HY (inv)",    "a": "HYG",  "b": "IEF",  "inv": False},
    {"name": "VIX (inv)",          "a": "VIXY", "b": None,   "inv": True},
]

# --- futuros COT (símbolo FMP -> etiqueta) ----------------------------------
# Las convenciones COT de FMP varían; si el panel sale vacío revisá estos símbolos.
COT_SYMBOLS = [
    {"label": "S&P fut · ES", "symbol": "ES"},
    {"label": "Crudo · CL",   "symbol": "CL"},
    {"label": "Oro · GC",     "symbol": "GC"},
    {"label": "10Y · ZN",     "symbol": "ZN"},
    {"label": "Dólar · DX",   "symbol": "DX"},
    {"label": "BTC · BTC",    "symbol": "BTC"},
]

# --- tarjetas macro ---------------------------------------------------------
# kind: "econ" (FMP economic-indicators / FRED), "quote" (símbolo cotizado).
# Para "econ" usamos 'name' de FMP; el fallback OpenBB/FRED usa 'fred'.
MACRO_CARDS = [
    {"nm": "Fed funds",     "kind": "econ",  "name": "federalFunds",        "fred": "FEDFUNDS", "unit": "%"},
    {"nm": "BCE depo",      "kind": "econ",  "name": "ECBInterestRate",     "fred": "ECBDFR",   "unit": "%"},
    {"nm": "BoJ",           "kind": "econ",  "name": "japanInterestRate",   "fred": "IRSTCI01JPM156N", "unit": "%"},
    {"nm": "PBoC LPR 1A",   "kind": "econ",  "name": "chinaInterestRate",   "fred": "INTDSRCNM193N", "unit": "%"},
    {"nm": "EUR / USD",     "kind": "quote", "symbol": "EURUSD", "unit": ""},
    {"nm": "USD / JPY",     "kind": "quote", "symbol": "USDJPY", "unit": ""},
    {"nm": "IPC EE.UU. a/a","kind": "econ",  "name": "CPI", "fred": "CPIAUCSL", "unit": "%", "yoy": True},
    {"nm": "IPC Eurozona",  "kind": "econ",  "name": "europeCPI", "fred": "CP0000EZ19M086NEST", "unit": "%", "yoy": True},
    {"nm": "WTI",           "kind": "quote", "symbol": "CLUSD", "alt": ["WTIUSD", "USO"], "unit": "$"},
    {"nm": "Brent",         "kind": "quote", "symbol": "BZUSD", "alt": ["BNO"], "unit": "$"},
    {"nm": "UST 10Y",       "kind": "quote", "symbol": "^TNX", "alt": ["IEF"], "unit": "%"},
    {"nm": "Oro",           "kind": "quote", "symbol": "GCUSD", "alt": ["GLD"], "unit": "$"},
    {"nm": "Plata",         "kind": "quote", "symbol": "SIUSD", "alt": ["SLV"], "unit": "$"},
    {"nm": "Plata/Oro",     "kind": "ratio", "a": "SIUSD", "b": "GCUSD", "unit": "ratio", "alt_a": ["SLV"], "alt_b": ["GLD"]},
    {"nm": "DXY",           "kind": "quote", "symbol": "^DXY", "alt": ["DX", "UUP"], "unit": ""},
    {"nm": "VIX",           "kind": "quote", "symbol": "^VIX", "alt": ["VIXY"], "unit": ""},
    {"nm": "BTC",           "kind": "quote", "symbol": "BTCUSD", "unit": "$"},
]
