"""
Backend Flask de Global Flow Matrix.

Rutas:
  GET /                -> sirve el dashboard (static/index.html)
  GET /api/snapshot    -> JSON con todos los paneles
  GET /api/health      -> estado + modo (live/demo)

Filosofía: si no hay key -> DEMO. Si hay key, se construye en vivo pero CADA
sección está blindada: si una llamada a FMP falla, esa sección cae a demo y se
anota en meta.notes; el resto sigue en vivo. La key nunca llega al navegador.

El ensamblado del snapshot vive en snapshot_builder.py (no acá) para que los
jobs de cron en preload_cache.py puedan invocarlo sin crear un ciclo de
imports (app.py -> preload_cache.py -> app.py).
"""
import logging
import os
from apscheduler.schedulers.background import BackgroundScheduler

from flask import Flask, jsonify, send_from_directory, request

import config
import cache
import demo_data
import gpr_store
import preload_cache
import snapshot_builder

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")

app = Flask(__name__, static_folder="static", static_url_path="")


# ---------------------------------------------------------------------------
# Scheduler: jobs de mercado deterministas (sin bloquear Flask)
# ---------------------------------------------------------------------------
_scheduler = None


def _init_scheduler():
    """Inicializa el scheduler de jobs de mercado (una sola vez al startup)."""
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        return  # Ya está en marcha

    # Timezone explícito: sin esto, BackgroundScheduler usa la hora local del
    # SO del servidor (en Oracle, probablemente UTC), y los horarios de
    # mercado de abajo quedarían desalineados.
    _scheduler = BackgroundScheduler(timezone="America/New_York")

    # Precarga inicial síncrona (mismo comportamiento de bloqueo al boot que
    # existía antes): siembra/actualiza ambos stores para que el primer
    # request ya tenga caché caliente.
    try:
        log.info("Precarga inicial: actualizando stores de precios...")
        preload_cache.job_market_close_update()
        preload_cache.job_intraday_update()
    except Exception as e:
        log.warning("Precarga inicial no completó: %s (continuando)", e)

    # Job de cierre: 17:00 ET, 1h post-cierre NYSE (16:00 ET), lunes-viernes.
    _scheduler.add_job(
        preload_cache.job_market_close_update,
        'cron',
        hour=17,
        minute=0,
        day_of_week='0-4',
        id='market_close_update_job',
        replace_existing=True,
    )

    # Job intradía: cada 15 min en horario de mercado, lunes-viernes.
    _scheduler.add_job(
        preload_cache.job_intraday_update,
        'cron',
        hour='9-16',
        minute='*/15',
        day_of_week='0-4',
        id='intraday_update_job',
        replace_existing=True,
    )

    # Job diario: captura de flujos ETF a las 18:00 (cierre US, lunes-viernes)
    _scheduler.add_job(
        preload_cache.job_capture_etf_flows,
        'cron',
        hour=18,
        minute=0,
        day_of_week='0-4',  # lunes-viernes
        id='capture_etf_flows_job',
        replace_existing=True,
    )

    # Job diario: riesgo geopolítico AI-GPR. Todos los días (el índice es de
    # prensa, no de mercado: también corre fines de semana) y a las 7:00 ET,
    # antes de la apertura. La serie se publica con ~5 días de retraso, así que
    # la hora exacta da igual mientras corra una vez al día.
    _scheduler.add_job(
        gpr_store.update,
        'cron',
        hour=7,
        minute=0,
        id='gpr_update_job',
        replace_existing=True,
    )

    try:
        _scheduler.start()
        log.info("Scheduler iniciado: cierre 17:00 ET + intradía c/15min + "
                 "captura ETF 18:00 ET + AI-GPR 7:00 ET")
    except Exception as e:
        log.error("Error al iniciar scheduler: %s", e)


# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/snapshot")
def snapshot():
    period = int(request.args.get("period", 5))
    if period not in (1, 5, 20, 50, 180):
        period = 5

    if config.DEMO_MODE:
        data = demo_data.snapshot(
            "demo", ["Modo DEMO: sin FMP_API_KEY. Datos sintéticos. "
                     "Poné tu key en .env para datos reales."])
        return jsonify(data)

    cache_key = f"snapshot:full:{period}"
    cached = cache.get(cache_key)
    if cached is not None:
        return jsonify(cached)
    # Fallback síncrono (red de seguridad): en régimen normal, los jobs de
    # cron ya dejaron esto cacheado antes de que un usuario lo pida.
    data = snapshot_builder.build_and_cache(period)
    return jsonify(data)


@app.route("/api/geopolitical-risk/latest")
def gpr_latest():
    data = gpr_store.latest()
    if data is None:
        return jsonify({"error": "sin datos de AI-GPR todavía"}), 503
    return jsonify(data)


@app.route("/api/geopolitical-risk/history")
def gpr_history():
    try:
        days = int(request.args.get("days", 365))
    except ValueError:
        days = 365
    return jsonify(gpr_store.history(days))


@app.route("/war")
def war():
    """Laboratorio de análisis riesgo geopolítico x sectores (ver war_lab.py)."""
    return send_from_directory(app.static_folder, "war.html")


@app.route("/api/war/analysis")
def war_analysis():
    # El análisis cruza 26 años de precios con el AI-GPR: pesado para hacerlo
    # por request, y la entrada solo cambia una vez al día.
    cached = cache.get("war:analysis")
    if cached is not None:
        return jsonify(cached)
    try:
        import war_lab
        data = war_lab.analizar()
    except Exception as e:
        log.exception("war_lab falló")
        return jsonify({"error": str(e)}), 503
    cache.set("war:analysis", data, 6 * 3600)
    return jsonify(data)


@app.route("/api/health")
def health():
    return jsonify({"ok": True,
                    "mode": "demo" if config.DEMO_MODE else "live",
                    "openbb": snapshot_builder._openbb_available()})


if __name__ == "__main__":
    mode = "DEMO (sin key)" if config.DEMO_MODE else "LIVE (FMP)"
    log.info("Arrancando Global Flow Matrix en modo %s", mode)

    # Inicializar scheduler de jobs de mercado (si no estamos en DEMO_MODE)
    if not config.DEMO_MODE:
        _init_scheduler()
    else:
        log.info("Scheduler deshabilitado (modo DEMO)")

    host = os.environ.get("HOST", "127.0.0.1")
    # 5055 y no 5000: en la máquina de desarrollo el :5000 lo ocupa el otro
    # proyecto (Neural), igual que en el server. En producción el .service fija
    # PORT=5001, así que este default no afecta al deploy.
    port = int(os.environ.get("PORT", "5055"))
    app.run(host=host, port=port, debug=False)
