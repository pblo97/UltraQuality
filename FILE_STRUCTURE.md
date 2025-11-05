# UltraQuality File Structure

## 🚀 Entry Points

### Web Interface (Streamlit Cloud)
```bash
run_screener.py          # MAIN FILE - Streamlit web UI
                         # This is what Streamlit Cloud executes
                         # Opens at: https://your-app.streamlit.app
```

### Command Line Interface (Local)
```bash
python cli_run_screener.py              # Run full screening
python cli_run_screener.py --symbol AAPL  # Qualitative analysis
```

## 📁 Project Structure

```
UltraQuality/
├── run_screener.py          ⭐ Main - Streamlit web UI
├── cli_run_screener.py      🖥️  CLI tool for terminal usage
├── requirements.txt         📦 Python dependencies
├── settings.yaml            ⚙️  Configuration
│
├── src/screener/            🔧 Core screening modules
│   ├── ingest.py           # FMP API client
│   ├── features.py         # Calculate metrics (ROIC, P/E, etc.)
│   ├── guardrails.py       # Altman Z, Beneish M, Accruals
│   ├── scoring.py          # Industry normalization & scoring
│   └── orchestrator.py     # Pipeline coordinator
│
├── src/qualitative/         🔍 Qualitative analysis
│   └── analyst.py          # Moats, risks, insider activity
│
├── outputs/                 📊 Generated reports (CSVs)
├── cache/                   💾 API response cache
└── docs/                    📚 Documentation
```

## 🎯 Quick Start

### For Users (Web Interface)
1. Open: https://your-app.streamlit.app
2. Set filters in sidebar
3. Click "🚀 Run Screener"
4. Explore Results, Analytics, and Qualitative tabs

### For Developers (Local)
```bash
# Install dependencies
pip install -r requirements.txt

# Set API key
cp .env.example .env
# Edit .env and add your FMP_API_KEY

# Run web UI locally
streamlit run run_screener.py

# Or use CLI
python cli_run_screener.py
```

## 🔑 Configuration Files

- **`.env`** - API keys (local development)
- **`.streamlit/secrets.toml`** - API keys (Streamlit Cloud)
- **`settings.yaml`** - Screening parameters
- **`requirements.txt`** - Python packages

## ⚠️ Important Notes

1. **Do NOT rename run_screener.py** - Streamlit Cloud is configured to use this file
2. **API Key required** - Get from https://financialmodelingprep.com
3. **CLI vs Web** - CLI is `cli_run_screener.py`, Web is `run_screener.py`
4. **Cache** - Responses cached 24-72h in `cache/` directory

## 🛠️ Development

- **Edit UI**: Modify `run_screener.py`
- **Edit Pipeline**: Modify files in `src/screener/`
- **Edit Metrics**: Modify `src/screener/features.py`
- **Edit Scoring**: Modify `src/screener/scoring.py`

## 📝 Testing

```bash
# Test API connection
python test_fmp_connection.py

# Verify installation
python verify_install.py

# Run full screening
python cli_run_screener.py
```
