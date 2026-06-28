#!/usr/bin/env bash
# Arranque rápido del Mapa de Flujos Globales.
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "› Creando entorno virtual…"
  python3 -m venv .venv
fi
source .venv/bin/activate

echo "› Instalando dependencias…"
pip install -q --upgrade pip
pip install -q -r requirements.txt

if [ ! -f ".env" ]; then
  echo "› No hay .env: copiando plantilla (arrancará en modo DEMO)."
  cp .env.example .env
fi

echo "› Servidor en http://127.0.0.1:5000"
python app.py
