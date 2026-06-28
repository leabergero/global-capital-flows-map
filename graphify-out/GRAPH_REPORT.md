# Graph Report - /home/leandro/Vídeos/flujos-globales  (2026-06-28)

## Corpus Check
- Corpus is ~8,788 words - fits in a single context window. You may not need a graph.

## Summary
- 109 nodes · 148 edges · 13 communities (12 shown, 1 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 1 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Data Ingestion (FMP API)|Data Ingestion (FMP API)]]
- [[_COMMUNITY_Demo & Fallback Data|Demo & Fallback Data]]
- [[_COMMUNITY_Cache Layer|Cache Layer]]
- [[_COMMUNITY_Flask Backend & Aggregation|Flask Backend & Aggregation]]
- [[_COMMUNITY_Macro Indicators|Macro Indicators]]
- [[_COMMUNITY_RRG (Relative Rotation)|RRG (Relative Rotation)]]
- [[_COMMUNITY_Capital Flows (ETF)|Capital Flows (ETF)]]
- [[_COMMUNITY_News Extraction|News Extraction]]
- [[_COMMUNITY_COT (Trader Positioning)|COT (Trader Positioning)]]
- [[_COMMUNITY_RORO Index|RORO Index]]
- [[_COMMUNITY_CMF (Money Flow)|CMF (Money Flow)]]
- [[_COMMUNITY_Configuration|Configuration]]

## God Nodes (most connected - your core abstractions)
1. `snapshot()` - 8 edges
2. `_get()` - 8 edges
3. `_econ_card()` - 7 edges
4. `_live_snapshot()` - 6 edges
5. `_metrics()` - 5 edges
6. `point()` - 5 edges
7. `_quote_card()` - 5 edges
8. `_tree()` - 4 edges
9. `set()` - 4 edges
10. `_build_node()` - 4 edges

## Surprising Connections (you probably didn't know these)
- `all_symbols()` --calls--> `set()`  [INFERRED]
  universe.py → cache.py

## Communities (13 total, 1 thin omitted)

### Community 0 - "Data Ingestion (FMP API)"
Cohesion: 0.17
Nodes (15): cot(), economic(), etf_holding_dates(), etf_holdings(), _get(), historical(), quote(), Cliente FMP. Centraliza TODAS las rutas en un solo lugar (ENDPOINTS) para que aj (+7 more)

### Community 1 - "Demo & Fallback Data"
Cohesion: 0.29
Nodes (12): _cot(), _macro(), _metrics(), _news(), Generador de snapshot sintético. Se usa cuando no hay key (modo DEMO) y como fal, rs ~ [94,108], mom ~ [96,105], cmf ~ [-0.5,0.5] deterministas., _regime(), _roro() (+4 more)

### Community 2 - "Cache Layer"
Cohesion: 0.18
Nodes (9): get(), _path(), Caché TTL en disco (JSON). Respeta los límites de FMP y persiste entre reinicios, Devuelve el valor cacheado si sigue fresco, si no None., Guarda value bajo key con vencimiento ttl segundos., set(), all_symbols(), Universo jerárquico: clases -> sectores -> industrias -> constituyentes.  Cada n (+1 more)

### Community 3 - "Flask Backend & Aggregation"
Cohesion: 0.29
Nodes (10): _agg(), _build_node(), health(), _live_snapshot(), _lookup(), _openbb_available(), _prefetch(), Backend Flask del Mapa de Flujos Globales.  Rutas:   GET /                -> sir (+2 more)

### Community 4 - "Macro Indicators"
Cohesion: 0.36
Nodes (10): cards(), _dir(), _econ_card(), _econ_series_fmp(), _econ_series_fred(), _fmt(), _quote_card(), Panel macro. Cada tarjeta sale de:   kind="quote" -> símbolo cotizado (FX, commo (+2 more)

### Community 5 - "RRG (Relative Rotation)"
Cohesion: 0.31
Nodes (8): dataset(), point(), _ratio_momentum(), RRG — Relative Rotation Graph.  Reproducción abierta y documentada del método de, De [{date, close}, ...] ascendente a pd.Series(close) indexada por fecha., Devuelve {'rs', 'mom', 'path'} para un activo vs benchmark, o None si no     hay, pairs: lista (nombre, símbolo). price_lookup(símbolo)->bars.     Devuelve lista, _series()

### Community 6 - "Capital Flows (ETF)"
Cohesion: 0.38
Nodes (6): _aum(), _close_on_or_before(), implied_flow(), Flujo implícito de ETF — la ÚNICA capa donde el dinero es observable, no inferid, Último close con fecha <= date (bars ascendente)., Devuelve flujo neto estimado en USD (float) o None.     Usa las dos fechas de ho

### Community 7 - "News Extraction"
Cohesion: 0.57
Nodes (6): _from_fmp(), _from_openbb(), headlines(), _hhmm(), Noticias. Primario: OpenBB (obb.news.world). Si OpenBB no está instalado o falla, _sentiment()

### Community 8 - "COT (Trader Positioning)"
Cohesion: 0.38
Nodes (6): net_position(), _pick(), COT — Commitment of Traders. Posición neta de no-comerciales (especuladores) y s, Devuelve (neto_k, cambio_k) en miles de contratos, o None., Lista [[label, neto, cambio], ...] para los símbolos que devuelven dato., table()

### Community 9 - "RORO Index"
Cohesion: 0.38
Nodes (5): _close(), components(), RORO — risk-on / risk-off. Termómetro de régimen.  Para cada componente (un rati, Devuelve (lista [[name, z], ...], compuesto). price_lookup(sym)->bars., _z_last()

### Community 10 - "CMF (Money Flow)"
Cohesion: 0.5
Nodes (3): cmf(), CMF — Chaikin Money Flow. Mide PRESIÓN (acumulación/distribución), no flujo., CMF más reciente a partir de barras OHLCV ascendentes, o None.

## Knowledge Gaps
- **35 isolated node(s):** `Configuración central del backend.  Todos los símbolos de FMP, los TTL de caché`, `Generador de snapshot sintético. Se usa cuando no hay key (modo DEMO) y como fal`, `rs ~ [94,108], mom ~ [96,105], cmf ~ [-0.5,0.5] deterministas.`, `Caché TTL en disco (JSON). Respeta los límites de FMP y persiste entre reinicios`, `Devuelve el valor cacheado si sigue fresco, si no None.` (+30 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What connects `Configuración central del backend.  Todos los símbolos de FMP, los TTL de caché`, `Generador de snapshot sintético. Se usa cuando no hay key (modo DEMO) y como fal`, `rs ~ [94,108], mom ~ [96,105], cmf ~ [-0.5,0.5] deterministas.` to the rest of the system?**
  _35 weakly-connected nodes found - possible documentation gaps or missing edges._