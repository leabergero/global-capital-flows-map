"""
Universo jerárquico: clases -> sectores -> industrias -> constituyentes.

Cada nodo:
  name   etiqueta visible
  symbol símbolo FMP para precio/RS/CMF (un ETF representativo en los nodos
         agregados; el ticker propio en las hojas). None = nodo puramente
         contenedor (se agrega desde los hijos).
  etf    True si el símbolo es un ETF cuyo flujo implícito tiene sentido medir
         (creación/redención). False en acciones/cripto/FX.
  w      peso relativo (solo dimensiona el tile en el heatmap).
  children
Editá libremente: agregar/quitar un ticker acá se refleja en todo el mapa.
"""


def node(name, symbol=None, etf=False, w=1.0, children=None):
    return {"name": name, "symbol": symbol, "etf": etf, "w": w,
            "children": children}


TREE = node("Global", w=100, children=[
    node("Equity", "SPY", True, 46, children=[
        node("Energía", "XLE", True, 12, children=[
            node("Oil & Gas E&P", "XOP", True, 4.2, children=[
                node("EOG", "EOG", w=1), node("DVN", "DVN", w=0.8),
                node("FANG", "FANG", w=0.9), node("COP", "COP", w=1.1),
                node("OXY", "OXY", w=0.9)]),
            node("Equip. & Servicios", "OIH", True, 2.0, children=[
                node("SLB", "SLB", w=1), node("HAL", "HAL", w=0.7),
                node("BKR", "BKR", w=0.7)]),
            node("Midstream", "AMLP", True, 2.6, children=[
                node("KMI", "KMI", w=0.9), node("WMB", "WMB", w=0.9),
                node("OKE", "OKE", w=0.8), node("ET", "ET", w=0.7)]),
            node("Refino & Marketing", "CRAK", True, 1.8, children=[
                node("MPC", "MPC", w=0.7), node("VLO", "VLO", w=0.6),
                node("PSX", "PSX", w=0.6)]),
            node("Integradas", None, False, 1.4, children=[
                node("XOM", "XOM", w=0.8), node("CVX", "CVX", w=0.6)])]),
        node("Tecnología", "XLK", True, 16, children=[
            node("Semiconductores", "SMH", True, 5.6, children=[
                node("NVDA", "NVDA", w=2.2), node("AVGO", "AVGO", w=1.4),
                node("AMD", "AMD", w=0.9), node("TXN", "TXN", w=0.6),
                node("INTC", "INTC", w=0.5)]),
            node("Software", "IGV", True, 6.4, children=[
                node("MSFT", "MSFT", w=2.6), node("ORCL", "ORCL", w=1.0),
                node("CRM", "CRM", w=0.9), node("ADBE", "ADBE", w=0.9)]),
            node("Hardware", None, False, 4.0, children=[
                node("AAPL", "AAPL", w=2.6), node("DELL", "DELL", w=0.7),
                node("HPQ", "HPQ", w=0.7)])]),
        node("Financials", "XLF", True, 13, children=[
            node("Bancos", "KBE", True, 5.0, children=[
                node("JPM", "JPM", w=1.8), node("BAC", "BAC", w=1.2),
                node("WFC", "WFC", w=1.1), node("C", "C", w=0.9)]),
            node("Mercados de capital", "IAI", True, 3.4, children=[
                node("GS", "GS", w=1.2), node("MS", "MS", w=1.1),
                node("SCHW", "SCHW", w=1.1)]),
            node("Seguros", "KIE", True, 4.6, children=[
                node("BRK.B", "BRK-B", w=2.4), node("PGR", "PGR", w=1.1),
                node("MET", "MET", w=1.1)])]),
        node("Salud", "XLV", True, 11, children=[
            node("LLY", "LLY", w=3.0), node("UNH", "UNH", w=2.4),
            node("JNJ", "JNJ", w=2.6), node("PFE", "PFE", w=1.6),
            node("MRK", "MRK", w=1.4)]),
        node("Consumo discrec.", "XLY", True, 10, children=[
            node("AMZN", "AMZN", w=3.4), node("TSLA", "TSLA", w=2.0),
            node("HD", "HD", w=1.6), node("MCD", "MCD", w=1.4),
            node("NKE", "NKE", w=0.9)]),
        node("Consumo básico", "XLP", True, 7, children=[
            node("PG", "PG", w=1.9), node("KO", "KO", w=1.7),
            node("WMT", "WMT", w=2.0), node("COST", "COST", w=1.4)]),
        node("Industriales", "XLI", True, 9, children=[
            node("CAT", "CAT", w=1.6), node("GE", "GE", w=1.6),
            node("UNP", "UNP", w=1.4), node("BA", "BA", w=1.2),
            node("HON", "HON", w=1.3)]),
        node("Materiales", "XLB", True, 4, children=[
            node("LIN", "LIN", w=1.4), node("FCX", "FCX", w=1.0),
            node("NEM", "NEM", w=0.8), node("NUE", "NUE", w=0.8)]),
        node("Utilities", "XLU", True, 5, children=[
            node("NEE", "NEE", w=1.6), node("DUK", "DUK", w=1.2),
            node("SO", "SO", w=1.2), node("D", "D", w=1.0)]),
        node("Inmobiliario", "XLRE", True, 4, children=[
            node("AMT", "AMT", w=1.2), node("PLD", "PLD", w=1.2),
            node("EQIX", "EQIX", w=1.0), node("O", "O", w=0.6)]),
        node("Comunicaciones", "XLC", True, 9, children=[
            node("GOOGL", "GOOGL", w=2.8), node("META", "META", w=2.6),
            node("NFLX", "NFLX", w=1.2), node("DIS", "DIS", w=1.4)])]),

    node("Bonos", "AGG", True, 24, children=[
        node("Corto plazo · SHY", "SHY", True, 4),
        node("Intermedio · IEF", "IEF", True, 5),
        node("Largo · 10Y UST", "TLT", True, 5),
        node("Crédito IG · LQD", "LQD", True, 4),
        node("High Yield · HYG", "HYG", True, 3),
        node("TIPS · TIP", "TIP", True, 2),
        node("EM deuda · EMB", "EMB", True, 2)]),

    node("Commodities", "DBC", True, 16, children=[
        node("Energía", "DBE", True, 5, children=[
            node("WTI · USO", "USO", True, 2.4),
            node("Brent · BNO", "BNO", True, 1.8),
            node("Gas nat. · UNG", "UNG", True, 0.8)]),
        node("Metales preciosos", None, False, 5, children=[
            node("Oro · GLD", "GLD", True, 2.6),
            node("Plata · SLV", "SLV", True, 1.4),
            node("Platino · PPLT", "PPLT", True, 1.0)]),
        node("Metales industriales", None, False, 4, children=[
            node("Cobre · CPER", "CPER", True, 2.2),
            node("Base · DBB", "DBB", True, 1.0)]),
        node("Agrícolas", "DBA", True, 2, children=[
            node("Maíz · CORN", "CORN", True, 0.8),
            node("Trigo · WEAT", "WEAT", True, 0.6),
            node("Soja · SOYB", "SOYB", True, 0.6)])]),

    node("Cripto", "BTCUSD", False, 8, children=[
        node("Layer 1", None, False, 5, children=[
            node("BTC", "BTCUSD", w=3.2), node("ETH", "ETHUSD", w=1.4),
            node("SOL", "SOLUSD", w=0.7)]),
        node("DeFi", None, False, 1.4, children=[
            node("UNI", "UNIUSD", w=0.7), node("AAVE", "AAVEUSD", w=0.7)]),
        node("Stablecoins", None, False, 1.6, children=[
            node("USDT", "USDTUSD", w=0.9), node("USDC", "USDCUSD", w=0.7)])]),

    node("Divisas", "UUP", False, 6, children=[
        node("DXY", "UUP", w=1.4), node("EUR", "EURUSD", w=1.2),
        node("JPY", "USDJPY", w=1.0), node("GBP", "GBPUSD", w=0.8),
        node("CNY", "USDCNY", w=1.0)]),
])


# --- RRG datasets: qué símbolos se grafican en cada vista -------------------
RRG_SECTORES = [
    ("Energía", "XLE"), ("Tecnología", "XLK"), ("Financials", "XLF"),
    ("Salud", "XLV"), ("Industriales", "XLI"), ("Materiales", "XLB"),
    ("Cons. básico", "XLP"), ("Cons. discrec.", "XLY"), ("Utilities", "XLU"),
    ("Inmobiliario", "XLRE"), ("Comunic.", "XLC"),
]
RRG_CROSS = [
    ("Equity", "SPY"), ("Bonos", "AGG"), ("Commodities", "DBC"),
    ("Cripto", "BTCUSD"), ("Divisas", "UUP"), ("Oro", "GLD"),
    ("High Yield", "HYG"), ("10Y UST", "TLT"),
]


def all_symbols():
    """Todos los símbolos únicos del árbol (para prefetch de históricos)."""
    out = set()

    def walk(n):
        if n.get("symbol"):
            out.add(n["symbol"])
        for c in (n.get("children") or []):
            walk(c)
    walk(TREE)
    for _, s in RRG_SECTORES + RRG_CROSS:
        out.add(s)
    return sorted(out)
