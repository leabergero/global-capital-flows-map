#!/bin/bash

# Script de deployment a Oracle para Global Flow Matrix v1.3
# Ejecutar: bash DEPLOY_ORACLE.sh
# O: ./DEPLOY_ORACLE.sh

HOST="leandro@152.70.14.73"
SSH_KEY="${HOME}/.ssh/oracle_mapa.key"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║      DEPLOYMENT: Global Flow Matrix v1.3 a Oracle         ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Host: $HOST"
echo "SSH Key: $SSH_KEY"
echo ""

# Verificar que la clave existe
if [ ! -f "$SSH_KEY" ]; then
    echo "❌ Error: No se encontró clave SSH en $SSH_KEY"
    echo ""
    echo "Intenta con:"
    echo "  ssh -i ~/.ssh/oracle_mapa.key $HOST"
    exit 1
fi

echo "Conectando a servidor Oracle..."
echo ""

# Ejecutar deployment
ssh -i "$SSH_KEY" "$HOST" bash -c '
set -e

echo "════════════════════════════════════════════════════════════"
echo "  DEPLOYMENT: Global Flow Matrix v1.3"
echo "════════════════════════════════════════════════════════════"
echo ""

echo "1️⃣  Actualizando código desde GitHub..."
cd ~/global-flow-matrix
git pull origin main
echo "✅ Completado"
echo ""

echo "2️⃣  Instalando nuevas dependencias..."
source .venv/bin/activate
pip install -r requirements.txt -q
echo "✅ Completado (apscheduler instalado)"
echo ""

echo "3️⃣  Reiniciando servicio..."
# El arranque siembra/actualiza los stores de precios (diario + intradía) de
# forma síncrona ANTES de aceptar requests (ver app._init_scheduler) — en un
# primer deploy sin data/price_history.json esto puede tardar varios minutos
# (siembra ~130 símbolos con MAX_WORKERS=3). Es esperado, no un cuelgue.
sudo systemctl restart global-flow-matrix.service
sleep 3
echo "✅ Servicio reiniciado"
echo ""

echo "4️⃣  Esperando startup (puede tardar más en el primer deploy, ver nota arriba)..."
sleep 10
echo "✅ Listo"
echo ""

echo "5️⃣  Verificando estado..."
curl -s http://127.0.0.1:5001/api/health
echo ""

echo "6️⃣  Precalentando caché de snapshots ensamblados..."
source .venv/bin/activate
python warmup_cache.py
echo ""

echo "════════════════════════════════════════════════════════════"
echo "  ✅ DEPLOYMENT COMPLETADO EXITOSAMENTE"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "Dashboard: https://flow.quantcentral.eu"
echo ""
'

echo ""
echo "Verificar después:"
echo "  curl https://flow.quantcentral.eu/api/health"
echo "  Abrir en navegador: https://flow.quantcentral.eu"
