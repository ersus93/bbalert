#!/bin/bash
set -e

echo "=== Desplegando a PRODUCCIÓN ==="
cd ~/bbalert-prod/bbalert
git fetch origin
git checkout main
git pull origin main
source ../venv/bin/activate
pip install -r requirements.txt --quiet
echo "Producción actualizado a: $(git log -1 --oneline)"
