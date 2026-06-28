# Mapa de Flujos Globales

Terminal cross-asset que visualiza la **rotación de capital** entre clases de
activo, sectores e industrias. Backend Flask que ingiere/calcula/cachea datos de
FMP (+ OpenBB opcional) y un frontend que solo pinta. La API key **nunca** toca
el navegador.

---

## ⚠️ Antes que nada: tu API key

Si pegaste tu key de FMP en algún chat o canal, **considerala comprometida**:
entrá al panel de FMP y **regenerala**. Después poné la nueva en `.env` (local,
en `.gitignore`, nunca al repo).

---

## Arranque rápido

```bash
# 1) configurar la key (o dejá el placeholder para modo DEMO)
cp .env.example .env
#   editá .env y poné FMP_API_KEY=<tu_key_regenerada>

# 2) opción A — script todo-en-uno
bash run.sh

# 2) opción B — manual
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Abrí **http://127.0.0.1:5000**.

- **Sin key** (placeholder) → arranca en **modo DEMO** con datos sintéticos: sirve
  para ver la herramienta funcionando al instante.
- **Con key** → construye en vivo. Si una llamada a FMP falla (endpoint premium,
  símbolo con otra convención, rate limit), **esa sección cae a demo** y el resto
  sigue en vivo; el badge muestra `parcial` y el pie lista qué cayó.

---

## Arquitectura (dos capas)

```
navegador (static/index.html)
   │  fetch GET /api/snapshot   (solo JSON ya procesado)
   ▼
Flask (app.py)
   ├─ fmp_client.py     wrapper FMP + caché en disco + logging
   ├─ compute/
   │   ├─ rrg.py        RS-Ratio / RS-Momentum (reproducción JdK)
   │   ├─ cmf.py        Chaikin Money Flow (presión)
   │   ├─ flows.py      flujo implícito ETF (Δ AUM × NAV)  ← dinero observado
   │   ├─ roro.py       índice risk-on/off (z-score compuesto)
   │   ├─ cot.py        posición neta no-comercial
   │   ├─ macro.py      tasas / FX / commodities / CPI
   │   └─ news.py       OpenBB → fallback FMP
   ├─ universe.py       árbol jerárquico + tickers FMP
   ├─ config.py         símbolos, TTLs, parámetros  ← editá acá
   └─ cache/            caché TTL en disco
```

**La key vive solo en el backend** (variable de entorno). El frontend recibe
datos, nunca credenciales. FMP además bloquea CORS desde el navegador, así que
llamarlo desde el frontend ni funcionaría: por eso esta separación es obligatoria.

---

## Disciplina conceptual (importante)

El mapa separa dos cosas que **no** son lo mismo:

- **Flujos inferidos** (proxy, tiempo real): RRG, CMF, ratios RORO. Se leen como
  *fuerza* o *presión*. **Nunca** afirman “entró/salió capital”.
- **Flujos observados** (dinero real, con lag): **flujo implícito ETF** (Δ AUM por
  creación/redención) y COT. Solo estos pueden decir “el capital se movió”.

Por eso no hay Sankey con flechas par-a-par: el dato no soporta esa magnitud.
El volumen mide rotación, no flujo neto (un cierre en baja con volumen alto tiene
comprador del otro lado); por eso usamos CMF, que pondera *dónde* cierra el precio.

---

## Cadencia de actualización (TTL de caché, en `config.py`)

| Capa | Fuente | Cadencia |
|------|--------|----------|
| RRG · CMF · RORO | precios FMP | horaria |
| Flujo implícito ETF | FMP `/etf/holdings` | diaria |
| COT | FMP COT | semanal |
| Macro | FMP econ + OpenBB/FRED | diaria |
| Noticias | OpenBB → FMP | intradía |

Para forzar recálculo, borrá `cache/*.json`.

---

## Troubleshooting (iterativo, como tus otros proyectos)

Los logs de consola muestran cada request FMP con su status. Lo más común:

- **Una tarjeta macro sale `n/d`** → la convención de símbolo de FMP para ese
  commodity/índice difiere. Ajustá `MACRO_CARDS` en `config.py` (probá los `alt`
  o reemplazá el símbolo). Ej.: WTI puede ser `CLUSD`, `WTIUSD`, o el ETF `USO`.
- **Panel COT vacío** → el endpoint/los nombres de campo COT varían por plan.
  Revisá `COT_SYMBOLS` en `config.py` y la lista de campos en `compute/cot.py`.
- **Flujo ETF en `—` para todo** → tu plan FMP quizá no expone `/etf/holdings`
  histórico, o el ETF no tiene dos fechas de corte. Es la capa más sensible al
  plan. El resto del dashboard funciona igual.
- **Sección entera en demo (badge `parcial`)** → mirá `meta.notes` en el pie y el
  log; suele ser un endpoint premium o un rate limit (plan gratuito de FMP es
  acotado; subí el TTL o el plan).
- **Noticias genéricas / sin OpenBB** → OpenBB es opcional y pesado. Sin él,
  caen a FMP. Para activarlo: descomentá `openbb` en `requirements.txt` e instalá.

Editá `universe.py` para agregar/quitar tickers: se refleja en todo el mapa.

---

## Notas

- Datos marcados **DEMO** son sintéticos e ilustrativos, no reales.
- `BENCH_EQUITY` / `BENCH_CROSS` en `config.py` cambian los benchmarks del RRG.
- Probado en modo DEMO de punta a punta. El modo LIVE depende de tu plan FMP;
  iteramos sobre lo que devuelva tu cuenta.
