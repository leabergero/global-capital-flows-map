"""
Caché TTL en disco (JSON). Respeta los límites de FMP y persiste entre
reinicios. Cada entrada guarda timestamp + ttl; si expiró, se ignora.
"""
import os
import json
import time
import hashlib

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)


def _path(key: str) -> str:
    h = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return os.path.join(CACHE_DIR, f"{h}.json")


def get(key: str):
    """Devuelve el valor cacheado si sigue fresco, si no None."""
    p = _path(key)
    if not os.path.exists(p):
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            entry = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    if time.time() - entry.get("ts", 0) > entry.get("ttl", 0):
        return None
    return entry.get("value")


def set(key: str, value, ttl: int):
    """Guarda value bajo key con vencimiento ttl segundos."""
    p = _path(key)
    entry = {"ts": time.time(), "ttl": ttl, "value": value}
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(entry, f)
    except OSError:
        pass  # un fallo de caché nunca debe romper la app


def clear():
    for fn in os.listdir(CACHE_DIR):
        if fn.endswith(".json"):
            try:
                os.remove(os.path.join(CACHE_DIR, fn))
            except OSError:
                pass
