# Quick Start Guide

Get up and running in 2 minutes.

## ⚡ Fastest Method

### Linux / macOS

```bash
# 1. Clone and enter directory
git clone https://github.com/pblo97/UltraQuality.git
cd UltraQuality

# 2. Run setup script
bash quick_setup.sh

# 3. Set API key
export FMP_API_KEY="your_api_key_here"

# 4. Run screener
python run_screener.py
```

### Windows

```cmd
REM 1. Clone and enter directory
git clone https://github.com/pblo97/UltraQuality.git
cd UltraQuality

REM 2. Run setup script
quick_setup.bat

REM 3. Set API key
set FMP_API_KEY=your_api_key_here

REM 4. Run screener
python run_screener.py
```

---

## 📋 Manual Installation

If automatic setup doesn't work:

```bash
# Install dependencies
pip install pandas numpy requests pyyaml scipy python-dotenv

# Verify
python verify_install.py

# Configure API key
export FMP_API_KEY="your_key_here"

# Run
python run_screener.py
```

---

## 🔑 Get API Key

1. Go to https://financialmodelingprep.com
2. Sign up (free tier available)
3. Copy your API key
4. Set it: `export FMP_API_KEY="your_key"`

---

## ✅ Verify Everything Works

```bash
# Check dependencies
python verify_install.py

# Test screener help
python run_screener.py --help

# Expected output:
# usage: run_screener.py [-h] [--config CONFIG] [--symbol SYMBOL]
```

---

## 🚀 Run Your First Screen

```bash
# Full screening (takes 3-5 minutes)
python run_screener.py

# Output: ./data/screener_results.csv
```

---

## 🔍 Analyze a Specific Stock

```bash
# Deep-dive analysis
python run_screener.py --symbol AAPL

# Save to file
python run_screener.py --symbol MSFT --output msft_analysis.json
```

---

## 🐛 Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'dotenv'"

**Solution**: Dependencies not installed

```bash
pip install python-dotenv pandas numpy requests pyyaml scipy
```

### Issue: "FMP_API_KEY not set"

**Solution**: Set your API key

```bash
export FMP_API_KEY="your_key_here"
# Or create .env file
echo "FMP_API_KEY=your_key_here" > .env
```

### Issue: Seeing Streamlit/Web UI messages

**Problem**: You're running the wrong script

**Solution**: Use `python run_screener.py` (NOT `streamlit run` or any web command)

### Issue: Installation takes too long

**Solution**: Use lightweight requirements

```bash
pip install -r requirements-core.txt  # Only 6 packages
```

---

## 📊 What Happens When You Run It?

```
[Stage 1/6] Building universe...
  → Fetches 2000+ stocks matching criteria

[Stage 2/6] Selecting Top-K...
  → Picks top 150 for deep analysis

[Stage 3/6] Calculating features...
  → Value metrics (EV/EBIT, P/E, etc.)
  → Quality metrics (ROIC, ROA, etc.)

[Stage 4/6] Calculating guardrails...
  → Altman Z-Score
  → Beneish M-Score
  → Accruals analysis

[Stage 5/6] Scoring...
  → Industry normalization
  → Value + Quality scores
  → BUY/MONITOR/AVOID decision

[Stage 6/6] Exporting...
  → CSV with 50+ metrics per stock
```

**Output**: `./data/screener_results.csv`

---

## 📈 View Results

```bash
# View top 20 rows
head -20 data/screener_results.csv

# Filter BUY decisions
grep ",BUY," data/screener_results.csv

# Open in Excel/Google Sheets
# Sort by composite_0_100 descending
# Filter decision == 'BUY'
```

---

## 📚 Next Steps

- **Full documentation**: [README.md](README.md)
- **System architecture**: [ARCHITECTURE.md](ARCHITECTURE.md)
- **Usage examples**: [EXAMPLES.md](EXAMPLES.md)
- **Installation guide**: [INSTALL.md](INSTALL.md)
- **API reference**: [FMP_ENDPOINTS.md](FMP_ENDPOINTS.md)

---

## 💡 Pro Tips

1. **Cache saves time**: Runs after the first are much faster (cached data)
2. **Customize settings**: Edit `settings.yaml` to adjust filters/weights
3. **Track changes**: Run weekly and compare results over time
4. **Deep-dive selectively**: Use `--symbol` for stocks that interest you
5. **Start small**: Use high market cap filter ($5B+) for first run

---

## ⚠️ Important Notes

- **NOT investment advice**: This is a research tool, not a recommendation
- **Do your own research**: Always verify findings independently
- **Check guardrails**: Don't ignore ROJO (red) flags
- **Understand metrics**: Read methodology in README.md
- **API limits**: Free tier has request limits (upgrade for heavy use)

---

**Questions?** Open an issue on GitHub or check the docs!

**Ready to start?** → `bash quick_setup.sh`
