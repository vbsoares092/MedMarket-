#!/usr/bin/env bash
# render-build.sh — executado pelo Render antes de iniciar a aplicação
set -e

echo "==> Installing Python dependencies"
pip install -r requirements.txt

echo "==> Creating upload directories"
mkdir -p instance/uploads/clinics
mkdir -p static/uploads/anuncios
mkdir -p static/uploads/prontuarios
mkdir -p static/uploads/documentos
mkdir -p static/uploads/profiles

echo "==> Build complete"
