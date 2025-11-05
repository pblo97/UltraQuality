#!/bin/bash
# Quick setup script for UltraQuality screener

set -e  # Exit on error

echo "=================================="
echo "UltraQuality Screener - Quick Setup"
echo "=================================="
echo ""

# Check Python version
PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
echo "✓ Python $PYTHON_VERSION found"

# Install dependencies
echo ""
echo "📦 Installing dependencies..."
pip install -q pandas numpy requests pyyaml scipy python-dotenv 2>/dev/null || \
pip install pandas numpy requests pyyaml scipy python-dotenv

echo "✓ Dependencies installed"

# Verify installation
echo ""
echo "🔍 Verifying installation..."
python verify_install.py

echo ""
echo "=================================="
echo "✅ Setup complete!"
echo "=================================="
echo ""
echo "Next steps:"
echo "  1. Set your API key:"
echo "     export FMP_API_KEY='your_key_here'"
echo ""
echo "  2. Run the screener:"
echo "     python run_screener.py"
echo ""
echo "  3. For qualitative analysis:"
echo "     python run_screener.py --symbol AAPL"
echo ""
