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
TIINGO_API_KEY = os.environ.get("TIINGO_API_KEY", "").strip()
_PLACEHOLDER = {"", "tu_key_regenerada", "tu_fred_key", "tu_quandl_key", "REEMPLAZAR", "CHANGEME"}

# OpenBB busca credenciales por el nombre EXACTO de la variable (sin prefijo
# "OPENBB_"), case-insensitive: para Tiingo es "TIINGO_TOKEN". Hay que
# setearla antes del primer "import openbb" del proceso (carga credenciales
# una sola vez, a nivel de módulo).
if TIINGO_API_KEY:
    os.environ.setdefault("TIINGO_TOKEN", TIINGO_API_KEY)
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

# --- CFTC directo (gratis, público, sin key) --------------------------------
# Fallback cuando Quandl/Nasdaq Data Link no responde (bloqueo Incapsula u
# otro). Fuente: Socrata public API, dataset "Legacy Futures Only" (6dca-aqww).
# cftc_contract_market_code identifica el contrato exacto (a diferencia de
# cftc_commodity_code, que agrupa variantes: p. ej. Gold y Micro Gold comparten
# "088", E-mini S&P 500 y sus sub-índices comparten "138").
CFTC_API_URL = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
CFTC_SYMBOL_MAP = {
    "ES": "13874A",   # E-MINI S&P 500 - CME
    "CL": "067411",   # CRUDE OIL, LIGHT SWEET-WTI - ICE Futures Europe
    "GC": "088691",   # GOLD - COMMODITY EXCHANGE INC.
    "ZN": "043602",   # UST 10Y NOTE - CBOT
    "DX": "098662",   # USD INDEX - ICE Futures U.S.
    "BTC": "133741",  # BITCOIN - CME
}

HTTP_TIMEOUT = 15          # segundos por request
MAX_WORKERS = int(os.environ.get("MAX_WORKERS", "8"))  # paralelismo al traer históricos
HISTORY_DAYS = 200         # ventana de precios para RRG/CMF/RORO (legado, ver price_store.py)

# --- store de precios diario (ventana fija, actualizado por cron de cierre) -
# Reemplaza el caché por TTL de históricos: en vez de expirar por tiempo, se
# actualiza 1x/día (job de cierre de mercado) y mantiene tamaño constante.
DAILY_STORE_BARS = 320        # barras de trading a conservar. compute/rrg.py hace
                               # un rolling DOBLE (uno para rs_ratio, otro para
                               # rs_mom sobre el diff de ese ratio) -> el período
                               # 180d (rrg_window=144) necesita ~2*window+tail=293
                               # filas válidas, no window+tail+2. 320 da margen
                               # ante feriados/símbolos con huecos.
DAILY_STORE_SEED_DAYS = 470    # días calendario a pedir a yfinance al sembrar
                               # un símbolo nuevo (~320 hábiles + margen feriados).

# --- store intradía (velas de 15 min, período "1d") -------------------------
INTRADAY_INTERVAL = "15m"
INTRADAY_FETCH_PERIOD = "5d"   # margen para fines de semana largos/feriados
INTRADAY_KEEP_DAYS = 3         # días de mercado a conservar (podado por fecha)
RRG_INTRADAY_WINDOW = 8        # ventana RRG para period=1 sobre velas de 15m
RRG_INTRADAY_TAIL = 8          # cola RRG para period=1

# --- caché por cadencia (segundos) ------------------------------------------
TTL = {
    "price":  60 * 60,          # legado (ya no lo usa el path de históricos)
    "flows":  60 * 60 * 24,     # flujo implícito ETF          -> diaria
    "cot":    60 * 60 * 24 * 7, # COT                          -> semanal
    "macro":  60 * 60 * 24,     # macro                        -> diaria
    "news":   60 * 15,          # noticias                     -> intradía
    "snapshot": 60 * 60 * 24,   # red de seguridad: la frescura real la dan los
                                 # jobs de cierre/intradía, no este TTL.
}

# --- mapeo de símbolos para yfinance (quote + histórico) --------------------
# Convención FMP -> convención yfinance. Se aplica tanto en quote() como en
# historical(): sin esto, cripto/forex/commodities salen "possibly delisted".
YFINANCE_SYMBOL_MAP = {
    # divisas: sufijo =X (par completo, no la forma corta JPY=X)
    "EURUSD":   "EURUSD=X",
    "USDJPY":   "USDJPY=X",
    "GBPUSD":   "GBPUSD=X",
    "USDCNY":   "USDCNY=X",
    # commodities: futuros =F (o ETF cuando es más líquido)
    "GCUSD":    "GC=F",        # oro
    "SIUSD":    "SI=F",        # plata
    "CLUSD":    "CL=F",        # WTI crudo
    "BZUSD":    "BZ=F",        # Brent crudo
    "WTIUSD":   "USO",         # WTI: ETF (más líquido)
    # cripto: sufijo -USD (Uniswap va con el ticker desambiguado de Yahoo)
    "BTCUSD":   "BTC-USD",
    "ETHUSD":   "ETH-USD",
    "SOLUSD":   "SOL-USD",
    "UNIUSD":   "UNI7083-USD",
    "AAVEUSD":  "AAVE-USD",
    "USDTUSD":  "USDT-USD",
    "USDCUSD":  "USDC-USD",
    # índices
    "^TNX":     "^TNX",        # bonos 10Y: índice directo
    "^DXY":     "DX-Y.NYB",    # índice dólar real (ICE); UUP como alt en la card
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
