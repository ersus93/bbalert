#!/bin/bash
set -e

echo "=== Desplegando a STAGING ==="
cd ~/bbalert-staging/bbalert
git fetch origin
git checkout testing
git pull origin testing
source ../venv/bin/activate
pip install -r requirements.txt --quiet
echo "Staging actualizado a: $(git log -1 --oneline)"
