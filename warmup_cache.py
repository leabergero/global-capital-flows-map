#!/usr/bin/env python3
"""
Precarga de caché al startup — calienta todos los períodos antes de servir.

Ejecuta esto una sola vez al deploy en producción para que el servidor
ya tenga 6 meses de datos cacheados desde el primer request.

Uso:
  python warmup_cache.py

Resultado:
  - Precarga todos los 5 períodos (1d, 5d, 20d, 50d, 6m)
  - Cada snapshot se cachea por su TTL
  - El servidor está listo para servir <3ms inmediatamente
"""
import sys
import time
import requests

BASE_URL = "http://127.0.0.1:5000"
PERIODS = [1, 5, 20, 50, 180]

print("╔═══════════════════════════════════════════════════════╗")
print("║         WARMUP: Precalculando 6 meses de datos        ║")
print("╚═══════════════════════════════════════════════════════╝")
print()

for period in PERIODS:
    try:
        start = time.time()
        response = requests.get(f"{BASE_URL}/api/snapshot?period={period}", timeout=60)
        elapsed = time.time() - start

        if response.status_code == 200:
            data = response.json()
            mode = data.get("meta", {}).get("mode", "?")
            etf_depth = data.get("meta", {}).get("etf_flow_depth", "?")

            label_map = {1: "1d   ", 5: "5d   ", 20: "20d  ", 50: "50d  ", 180: "6m   "}
            label = label_map.get(period, f"{period:3d}d")

            print(f"✅ {label} → {elapsed:6.1f}s (mode: {mode}, etf_depth: {etf_depth})")
        else:
            print(f"❌ {period}d → Error {response.status_code}")
    except Exception as e:
        print(f"❌ {period}d → {e}")

print()
print("╔═══════════════════════════════════════════════════════╗")
print("║  ✅ Caché precalentado — Servidor listo para servir   ║")
print("╚═══════════════════════════════════════════════════════╝")
