# Deployment: Global Flow Matrix v1.3 (Fases 1-3)

**Fecha**: 2026-07-25
**Status**: ✅ Production ready
**Commits**: 3 (Fase 1, 2, 3)

---

## Resumen de cambios

### **Fase 1** ✅ — Precarga automática cada 20 min
- Background scheduler (APScheduler)
- Precarga paralela de ~140 símbolos
- Job c/20 min durante 09:30-16:00 EST

### **Fase 2** ✅ — Captura automática de flujos ETF
- Job diario a las 18:00 EST (lunes-viernes)
- Ejecuta `scrape_etf_flows.py` automáticamente
- Heatmap siempre con datos frescos

### **Fase 3** ✅ — 5 ventanas temporales
- 1d (intradía, window=5)
- 5d (default, window=12)
- 20d (medio, window=30)
- 50d (largo, window=60)
- 6m (muy largo, window=144)

---

## Deployment en producción

### Paso 1: SSH al servidor
```bash
ssh user@152.70.14.73
cd ~/global-flow-matrix
```

### Paso 2: Actualizar código
```bash
git pull origin main
```

### Paso 3: Instalar nuevas dependencias
```bash
source .venv/bin/activate
pip install -r requirements.txt  # Instala apscheduler
```

### Paso 4: Reiniciar servicio
```bash
sudo systemctl restart global-flow-matrix.service
sleep 5
sudo systemctl status global-flow-matrix.service
```

### Paso 5: Precalcular caché (IMPORTANTE)
```bash
# Esperar a que el servidor esté listo (~10 seg)
source .venv/bin/activate
python warmup_cache.py
```

**Salida esperada**:
```
✅ 1d    →    0.0s (mode: live, etf_depth: 23)
✅ 5d    →    0.0s (mode: live, etf_depth: 23)
✅ 20d   →    0.0s (mode: live, etf_depth: 23)
✅ 50d   →    0.0s (mode: live, etf_depth: 23)
✅ 6m    →    0.0s (mode: parcial, etf_depth: 23)
✅ Caché precalentado — Servidor listo para servir
```

### Paso 6: Verificar
```bash
# Health check
curl https://flow.quantcentral.eu/api/health

# Esperado:
# {"ok":true,"mode":"live","openbb":true}

# Medir latencia
curl -w "Latency: %{time_total}s\n" \
  https://flow.quantcentral.eu/api/snapshot?period=5
  
# Esperado: < 0.1s
```

---

## Timeline

| Paso | Tiempo | Comando |
|------|--------|---------|
| SSH + git pull | 1 min | `git pull origin main` |
| pip install | 2 min | `pip install -r requirements.txt` |
| Restart service | 30 seg | `sudo systemctl restart ...` |
| Warmup caché | 1-2 min | `python warmup_cache.py` |
| **Total** | **~5 min** | |

---

## Verificación post-deployment

### 1. Logs en vivo
```bash
sudo journalctl -u global-flow-matrix.service -f

# Debes ver:
# "Precarga inicial: calentando caché..."
# "Precarga completada: 140 OK"
# "Scheduler iniciado: precarga c/20min + captura ETF"
```

### 2. Cada 20 minutos (durante horario de mercado)
```
INFO preload: Precarga completada: 140 OK, 0 failed en 11.2 seg
```

### 3. Diariamente a las 18:00
```
INFO preload: Iniciando captura de flujos ETF...
INFO preload: Captura de flujos ETF: 42/42 ETFs capturados, histórico de 180 días
```

---

## Rollback (si algo falla)

```bash
# Volver a versión anterior (sin Fase 1-3)
git reset --hard HEAD~3

# O ir a commit específico
git reset --hard a3c593b  # Antes de Fase 1

# Reinstalar y reiniciar
pip install -r requirements.txt
sudo systemctl restart global-flow-matrix.service
```

---

## Archivos modificados

```
Nuevos:
  + preload_cache.py (108 líneas) — módulo de precarga
  + warmup_cache.py (67 líneas) — script de precalcule
  + DEPLOYMENT.md (este archivo)

Modificados:
  ± app.py (+95 líneas) — scheduler + nuevos períodos
  ± static/index.html (+12 líneas) — UI + i18n
  ± requirements.txt (+1 línea) — apscheduler

Diferencial neto: ~220 líneas
```

---

## Performance esperado

| Métrica | Valor |
|---------|-------|
| Startup | ~10s (precarga única) |
| /api/snapshot (caché) | <3ms |
| /api/snapshot (primera vez) | 25-30s |
| Job precarga | 10-15s c/20 min |
| Job ETF | 5-10s c/18:00 |
| CPU (precarga) | +10% mientras ejecuta |
| CPU (idle) | Sin cambios |

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'apscheduler'"
```bash
pip install apscheduler>=3.10
```

### "/api/snapshot devuelve modo DEMO"
```bash
# Verificar FMP_API_KEY está seteada
grep "FMP_API_KEY" .env

# Si no existe, crear:
echo "FMP_API_KEY=<tu_key>" >> .env
```

### Precarga tarda mucho (>30s)
```bash
# Es normal la primera vez (cálculo de RRG)
# Verificar logs:
tail -f /tmp/app.log | grep -i "precarga\|error"
```

### Job ETF no se ejecuta
```bash
# Verificar cron job en server (solo para referencia)
# El job está integrado en APScheduler, no en cron
sudo journalctl -u global-flow-matrix.service | grep "capture_etf"
```

---

## Commits incluidos

```bash
git log --oneline -3

a3fd320 Fase 3: Nuevas ventanas temporales (1d + 6 meses)
1e41ed1 Fase 2: Captura automática ETF a las 18:00
a3c593b Fase 1: Precarga automática de caché
```

---

## Post-deployment checklist

- [ ] SSH conectado al servidor
- [ ] `git pull origin main` completado
- [ ] `pip install -r requirements.txt` completado
- [ ] `sudo systemctl restart` completado
- [ ] Esperados 10 segundos para que inicie
- [ ] `python warmup_cache.py` ejecutado
- [ ] Todos los períodos OK en warmup
- [ ] `/api/health` retorna live
- [ ] `/api/snapshot?period=5` <3ms
- [ ] Navegador: http://flow.quantcentral.eu carga
- [ ] Botones 1d, 5d, 20d, 50d, 6m visibles
- [ ] Cambio de ventana instantáneo
- [ ] Logs: "Scheduler iniciado"
- [ ] Logs: "Precarga completada" (c/20 min)

---

**Versión**: 1.3 (Fases 1-2-3)
**Última actualización**: 2026-07-25 16:30
**Estado**: ✅ Ready to deploy
