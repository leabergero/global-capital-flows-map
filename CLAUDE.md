# CLAUDE.md — Mapa de Flujos Globales

Guía para trabajar en este repo. **Leé esto entero antes de tocar código.**

Hay decisiones de diseño deliberadas que NO se deben romper sin avisar.

---

## Qué es

Terminal cross-asset que visualiza **rotación de capital** entre clases de activo, sectores e industrias. Dos capas:

- **Backend Flask** (`app.py`): ingiere datos de yfinance + FRED + Quandl + OpenBB, calcula los modelos, cachea y expone un único JSON en `/api/snapshot`.
- **Frontend** (`static/index.html`): vanilla JS + SVG inline, solo pinta el JSON. Sin frameworks, sin build step, un solo archivo.

Las API keys (todas opcionales, todas gratis) viven **solo** en el backend (variables de entorno). Nunca en el frontend.

---

## Comandos

```bash
# correr (crea venv, instala deps, arranca en :5000)
bash run.sh

# manual
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py                       # http://127.0.0.1:5000

# verificar que compila todo
python -m py_compile *.py compute/*.py

# probar el camino LIVE sin keys (yfinance es gratis, todo funciona)
python -c "import app; print(app._live_snapshot()['meta']['mode'])"

# forzar recálculo (borrar caché)
rm -rf cache/*.json
```

**Modo**: Siempre **LIVE** con yfinance (gratis, sin API key).
- Con `FRED_API_KEY` → indicadores económicos en vivo
- Con `QUANDL_API_KEY` → COT en vivo
- Sin ellas → esos paneles usan demo/fallback

---

## Estado actual (2026-06-29)

✅ **Completado**:
- RRG interactivo con 3 períodos (5d, 20d, 50d) + enlazados
- Heatmap con glow dinámico (rojo/verde) + períodos
- RORO régimen con BULLISH/BEARISH y glow latente
- SPY/TLT gauge: barra vertical, escala dinámica, glow latente
- Gold/Silver ratio calculado desde Oro y Plata
- 17 KPIs macro con tooltips visuales, organizados por categoría
- Frontend vanilla JS + SVG (sin build)
- Datos: yfinance + FRED + Quandl + OpenBB
- Copyright: Leandro R. Bergero, Msc Finance & Banking BSM-UPF
- Auto-reload cada 1 hora
- Badge de estado con hora de última actualización
- Carga inteligente: 5d inmediatamente, 20d/50d en background

---

## Disciplina conceptual — NO romper

Separa inferencia vs observación:

| Capa | Modelos | Lectura | Afirmar… |
|------|---------|---------|----------|
| **Inferida** | RRG, CMF, RORO | "fuerza" / "presión" | NUNCA "entró/salió capital" |
| **Observada** | Flujo ETF, COT | dinero medido | "el capital se movió" |

---

**Última actualización:** 2026-06-29
**Estado:** ✅ Production-ready
