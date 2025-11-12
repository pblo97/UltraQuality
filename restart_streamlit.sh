#!/bin/bash
# Script to completely restart Streamlit with clean cache

echo "🔄 Stopping Streamlit..."
pkill -f "streamlit run"
sleep 2

echo "🧹 Cleaning Python cache..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null

echo "🧹 Cleaning Streamlit cache..."
rm -rf .streamlit/cache 2>/dev/null

echo "✅ Cache limpiado"
echo ""
echo "▶️  Para iniciar Streamlit limpio, ejecuta:"
echo "    python -u run_screener.py"
echo ""
echo "O si usas streamlit directamente:"
echo "    streamlit run run_screener.py --server.runOnSave true"
