"""
Noticias. Cascada: OpenBB (obb.news.world) -> FMP directo -> yfinance
(Ticker.news, gratis y sin key, mismo proveedor que ya usa el resto de la app
para históricos/cotizaciones). Sentimiento heurístico por palabras clave (un
clasificador real iría en el backend si se quisiera).
"""
import logging
import re
from datetime import datetime

import yfinance

import config
import fmp_client as fmp
import cache

log = logging.getLogger("news")

# Comienzos de palabra: "fall" cubre fall/falls/falling, "sub" sube/suben/subió.
_POS = re.compile(r"\b(?:sub[eiíao]|récord|record|gan[aóa]|rall|repunt|entrada|inflow|alza|"
                  r"máximo|supera|rise|rising|rose|gain|surg|beat|jump|climb|soar|rebound|"
                  r"advanc|higher|boost)", re.IGNORECASE)
_NEG = re.compile(r"\b(?:cae|caen|cayó|caíd|baja|bajan|bajó|salida|outflow|pérdida|desplom|"
                  r"mínimo|hund|fall|fell|drop|loss|lose|plung|slump|miss|tumbl|slid|sink|"
                  r"sank|slip|lower|crash|selloff|sell-off|retreat|declin|weak)", re.IGNORECASE)


def _sentiment(text):
    """Positiva, negativa o neutral, por palabras clave.

    Antes ganaba la primera lista que encontrara algo, y se miraba primero la
    positiva: "futures fall after tech rally" salía positiva por "rally". Ahora
    se cuentan las dos, y si empatan manda la que aparece primero, que en un
    titular suele ser el hecho principal.
    """
    t = text or ""
    pos, neg = list(_POS.finditer(t)), list(_NEG.finditer(t))
    if len(pos) != len(neg):
        return "pos" if len(pos) > len(neg) else "neg"
    if not pos:
        return "neutral"
    return "pos" if pos[0].start() < neg[0].start() else "neg"


def _url(u):
    """El link a la nota, sólo si es http(s): llega de afuera y va a un href."""
    u = str(u or "").strip()
    return u if u.startswith(("https://", "http://")) else ""


def _hhmm(ts):
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "")).strftime("%H:%M")
    except Exception:
        return ""


def _from_openbb(limit):
    try:
        from openbb import obb
    except Exception:
        return None
    try:
        # Tiingo Starter (free) no incluye News API -> no forzar ese provider,
        # dejar que OpenBB use su default (FMP) y caer directo a fallback si falla.
        res = obb.news.world(limit=limit)
        items = res.results
        out = []
        for it in items[:limit]:
            title = getattr(it, "title", "") or ""
            src = getattr(it, "source", "") or "OpenBB"
            date = getattr(it, "date", "") or ""
            out.append({"t": title, "src": str(src), "time": _hhmm(date),
                        "sent": _sentiment(title), "url": _url(getattr(it, "url", ""))})
        return out or None
    except Exception as e:
        # 402/403/429 = feed FMP fuera del plan gratuito o límite alcanzado -> DEBUG.
        level = logging.DEBUG if any(c in str(e) for c in ("402", "403", "429")) else logging.WARNING
        log.log(level, "OpenBB news :: %s", e)
        return None


def _from_fmp(limit):
    url = f"{config.FMP_BASE_STABLE}/news/general-latest"
    # usamos el wrapper genérico vía historical? No: hacemos un get directo simple
    import requests
    try:
        r = requests.get(url, params={"limit": limit, "apikey": config.FMP_API_KEY},
                         timeout=config.HTTP_TIMEOUT)
        data = r.json() if r.status_code == 200 else []
    except Exception as e:
        log.warning("FMP news :: %s", e)
        return None
    if not isinstance(data, list) or not data:
        return None
    out = []
    for it in data[:limit]:
        title = it.get("title") or it.get("text", "")[:120]
        out.append({"t": title, "src": it.get("site") or it.get("publisher", "FMP"),
                    "time": _hhmm(it.get("publishedDate") or it.get("date")),
                    "sent": _sentiment(title), "url": _url(it.get("url"))})
    return out or None


# Símbolos ampliamente cubiertos (mercado general) para pescar titulares
# variados vía yfinance sin depender de un solo ticker.
_YF_NEWS_SYMBOLS = ["SPY", "QQQ", "^TNX", "GC=F"]


def _from_yfinance(limit):
    """Titulares vía Ticker.news (gratis, sin key, mismo proveedor que históricos)."""
    seen_ids = set()
    out = []
    try:
        for sym in _YF_NEWS_SYMBOLS:
            if len(out) >= limit:
                break
            for it in yfinance.Ticker(sym).news or []:
                if len(out) >= limit:
                    break
                c = it.get("content") or {}
                item_id = it.get("id") or c.get("title")
                if not item_id or item_id in seen_ids:
                    continue
                seen_ids.add(item_id)
                title = c.get("title") or ""
                if not title:
                    continue
                src = (c.get("provider") or {}).get("displayName") or "Yahoo Finance"
                out.append({"t": title, "src": src,
                            "time": _hhmm(c.get("pubDate")),
                            "sent": _sentiment(title),
                            "url": _url((c.get("clickThroughUrl") or c.get("canonicalUrl") or {}).get("url"))})
    except Exception as e:
        log.warning("yfinance news :: %s", e)
        return None
    return out or None


def _from_yfinance_search(limit):
    """Titulares vía la búsqueda de Yahoo.

    Desde octubre de 2026 `Ticker.news` vuelve vacío para todos los símbolos
    (SPY, QQQ, AAPL…) y FMP corta con 429 en el plan gratis: el panel quedaba en
    demo y la cabecera en "parcial". La búsqueda sí sigue respondiendo.
    """
    try:
        items = yfinance.Search("stock market", news_count=limit).news or []
    except Exception as e:
        log.warning("yfinance search news :: %s", e)
        return None
    out = []
    for it in items[:limit]:
        title = it.get("title") or ""
        if not title:
            continue
        ts = it.get("providerPublishTime")
        out.append({"t": title, "src": it.get("publisher") or "Yahoo Finance",
                    "time": datetime.fromtimestamp(ts).strftime("%H:%M") if ts else "",
                    "sent": _sentiment(title), "url": _url(it.get("link"))})
    return out or None


def headlines(limit=6):
    cached = cache.get("news:world")
    if cached is not None:
        return cached
    out = (_from_openbb(limit) or _from_fmp(limit) or _from_yfinance(limit)
           or _from_yfinance_search(limit))
    if out:
        cache.set("news:world", out, config.TTL["news"])
    return out or []


if __name__ == "__main__":
    casos = {
        "Stock market today: Dow, S&P 500, Nasdaq futures fall after tech rally": "neg",
        "Stock Market Today: Dow Tumbles 400 Points As Yields Jump; Fed Minutes On Deck": "neg",
        "S&P 500 rallies to record as tech stocks climb": "pos",
        "5 Things to Know Before the Stock Market Opens on Wednesday": "neutral",
        "El Merval sube 3% y los bonos tocan máximos": "pos",
        "El petróleo cae y el dólar se desploma": "neg",
        "La empresa trabaja en un nuevo plan": "neutral",
    }
    assert _url("javascript:alert(1)") == "" and _url("https://x.com/a") == "https://x.com/a"
    for titulo, esperado in casos.items():
        assert _sentiment(titulo) == esperado, (titulo, _sentiment(titulo), esperado)
    print("ok:", len(casos), "titulares")
