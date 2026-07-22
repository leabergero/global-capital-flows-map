"""
Noticias. Cascada: OpenBB (obb.news.world) -> FMP directo -> yfinance
(Ticker.news, gratis y sin key, mismo proveedor que ya usa el resto de la app
para históricos/cotizaciones). Sentimiento heurístico por palabras clave (un
clasificador real iría en el backend si se quisiera).
"""
import logging
from datetime import datetime

import yfinance

import config
import fmp_client as fmp
import cache

log = logging.getLogger("news")

_POS = ("sube", "récord", "gana", "rally", "entrada", "inflow", "alza", "máximo",
        "supera", "rises", "gains", "surge", "record", "beats", "jumps")
_NEG = ("cae", "baja", "salida", "outflow", "pérdida", "desploma", "mínimo",
        "falls", "drops", "loss", "plunge", "slumps", "misses")


def _sentiment(text):
    t = (text or "").lower()
    if any(w in t for w in _POS):
        return "pos"
    if any(w in t for w in _NEG):
        return "neg"
    return "neutral"


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
                        "sent": _sentiment(title)})
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
                    "sent": _sentiment(title)})
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
                            "sent": _sentiment(title)})
    except Exception as e:
        log.warning("yfinance news :: %s", e)
        return None
    return out or None


def headlines(limit=6):
    cached = cache.get("news:world")
    if cached is not None:
        return cached
    out = _from_openbb(limit) or _from_fmp(limit) or _from_yfinance(limit)
    if out:
        cache.set("news:world", out, config.TTL["news"])
    return out or []
