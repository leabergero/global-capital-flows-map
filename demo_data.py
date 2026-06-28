"""
Generador de snapshot sintético. Se usa cuando no hay key (modo DEMO) y como
fallback por-sección si una llamada a FMP falla. Deriva métricas deterministas
del propio árbol de `universe` para que la estructura DEMO == estructura LIVE.
Los números son ilustrativos, NO datos reales.
"""
import math
from datetime import datetime

import universe


def _seed(s):
    h = 0
    for ch in s:
        h = (h * 131 + ord(ch)) & 0xFFFFFFFF
    return h


def _metrics(name):
    """rs ~ [94,108], mom ~ [96,105], cmf ~ [-0.5,0.5] deterministas."""
    h = _seed(name)
    rs = 94 + (h % 1400) / 100.0
    mom = 96 + ((h >> 7) % 900) / 100.0
    cmf = round(((h >> 13) % 1000) / 1000.0 - 0.5, 3)
    return round(rs, 1), round(mom, 1), cmf


def _tree(node):
    rs, mom, cmf = _metrics(node["name"])
    flow = None
    if node.get("etf"):
        h = _seed(node["name"] + "f")
        flow = round(((h % 1600) - 700) * 1.0, 0)  # USD millones, +/-
    out = {"name": node["name"], "rs": rs, "mom": mom, "cmf": cmf,
           "flow": flow, "w": node.get("w", 1)}
    kids = node.get("children")
    if kids:
        out["children"] = [_tree(c) for c in kids]
    else:
        out["children"] = None
    return out


def _rrg(pairs):
    out = []
    for name, _sym in pairs:
        rs, mom, _ = _metrics(name)
        path = []
        for i in range(5, 0, -1):
            k = i / 5.0
            path.append([round(rs - (math.sin(i * 1.3) * 2.2 * k + 1.4 * k), 2),
                         round(mom - (math.cos(i * 1.1) * 1.8 * k + 1.1 * k), 2)])
        out.append({"name": name, "rs": rs, "mom": mom, "path": path})
    return out


def _roro():
    rows = [["SPY / TLT", 0.9], ["Cobre / Oro", -0.4], ["Cíclicos / Defens.", 0.6],
            ["Spread HY (inv)", 0.3], ["VIX (inv)", 0.5]]
    comp = round(sum(r[1] for r in rows) / len(rows), 2)
    return rows, comp


def _regime(comp):
    if comp >= 0.75:
        return {"state": "Risk-On", "score": comp, "color": "green"}
    if comp <= -0.75:
        return {"state": "Risk-Off", "score": comp, "color": "red"}
    return {"state": "Neutral / transición", "score": comp, "color": "amber"}


def _cot():
    return [["S&P fut · ES", 126, 18], ["Crudo · CL", 284, 12],
            ["Oro · GC", 198, 24], ["10Y · ZN", -142, -31],
            ["Dólar · DX", 41, -9], ["BTC · BTC", 6.4, 1.1]]


def _macro():
    def sp(seed, base, vol, n=12):
        return [round(base + math.sin(seed + i * 0.9) * vol
                      + math.cos(seed * 1.7 + i * 0.4) * vol * 0.6, 4)
                for i in range(n)]
    return [
        {"nm": "Fed funds", "val": "4.25%", "chg": "-0.25", "dir": "down", "s": sp(1, 4.6, 0.04)},
        {"nm": "BCE depo", "val": "2.40%", "chg": "0.00", "dir": "flat", "s": sp(2, 2.5, 0.03)},
        {"nm": "BoJ", "val": "0.75%", "chg": "+0.25", "dir": "up", "s": sp(3, 0.4, 0.02)},
        {"nm": "PBoC LPR 1A", "val": "3.00%", "chg": "-0.10", "dir": "down", "s": sp(4, 3.2, 0.02)},
        {"nm": "EUR / USD", "val": "1.0840", "chg": "+0.4%", "dir": "up", "s": sp(5, 1.07, 0.004)},
        {"nm": "USD / JPY", "val": "151.2", "chg": "-0.6%", "dir": "down", "s": sp(6, 153, 0.5)},
        {"nm": "IPC EE.UU. a/a", "val": "2.9%", "chg": "-0.1", "dir": "down", "s": sp(7, 3.2, 0.05)},
        {"nm": "IPC Eurozona", "val": "2.3%", "chg": "0.0", "dir": "flat", "s": sp(8, 2.4, 0.04)},
        {"nm": "WTI", "val": "$74.6", "chg": "+1.8%", "dir": "up", "s": sp(9, 71, 0.8)},
        {"nm": "Brent", "val": "$78.9", "chg": "+1.5%", "dir": "up", "s": sp(10, 75, 0.8)},
        {"nm": "UST 10Y", "val": "4.18%", "chg": "+4 pb", "dir": "up", "s": sp(11, 4.0, 0.04)},
        {"nm": "Oro", "val": "$2,940", "chg": "+0.9%", "dir": "up", "s": sp(12, 2820, 18)},
        {"nm": "DXY", "val": "103.4", "chg": "-0.3%", "dir": "down", "s": sp(13, 104, 0.4)},
        {"nm": "BTC", "val": "$71.8k", "chg": "+3.2%", "dir": "up", "s": sp(14, 66, 1.6)},
    ]


def _news():
    return [
        {"t": "El petróleo extiende su subida mientras los flujos rotan hacia energía y metales preciosos", "src": "Reuters", "time": "08:42", "sent": "pos"},
        {"t": "Entradas récord en ETF de oro: la creación/redención confirma demanda real de refugio", "src": "Bloomberg", "time": "08:15", "sent": "pos"},
        {"t": "Tecnología bajo presión: salidas netas en software pese a precios sostenidos", "src": "FT", "time": "07:50", "sent": "neg"},
        {"t": "El BoJ sorprende con un alza de 25 pb; el yen rebota frente al dólar", "src": "Nikkei", "time": "07:20", "sent": "neutral"},
        {"t": "COT: largos especulativos en crudo suben por tercera semana consecutiva", "src": "CFTC", "time": "06:58", "sent": "pos"},
        {"t": "Rotación defensiva pierde fuerza: salud e inmobiliario en cuadrante rezagado del RRG", "src": "MarketWatch", "time": "06:30", "sent": "neg"},
    ]


def snapshot(mode="demo", notes=None):
    roro_rows, comp = _roro()
    return {
        "meta": {"mode": mode,
                 "generated": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                 "notes": notes or ["Datos sintéticos de demostración."]},
        "regime": _regime(comp),
        "rrg": {"sectores": _rrg(universe.RRG_SECTORES),
                "cross": _rrg(universe.RRG_CROSS)},
        "roro": roro_rows,
        "cot": _cot(),
        "tree": _tree(universe.TREE),
        "macro": _macro(),
        "news": _news(),
    }
