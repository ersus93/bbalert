#!/bin/bash
# clean_cache.sh - Script to clean Python cache and restart the bot
# Run this on your VPS: bash clean_cache.sh

echo "🧹 Limpiando caché de Python..."

# Find and remove all __pycache__ directories
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null

# Find and remove all .pyc files
find . -name "*.pyc" -delete 2>/dev/null

echo "✅ Caché limpiado."

echo "🔄 Reiniciando el bot..."
sudo systemctl restart dev

echo "⏳ Esperando 3 segundos..."
sleep 3

echo "📋 Últimos logs:"
sudo journalctl -u dev -n 20 --no-pager

echo ""
echo "✅ ¡Bot reiniciado! Verifica que no aparezca el error de recursión."
