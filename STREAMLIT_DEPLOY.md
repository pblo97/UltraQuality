# Deploying UltraQuality to Streamlit Cloud

This guide shows how to deploy the screener on Streamlit Cloud.

## ⚠️ Important Note

**UltraQuality is a CLI tool**, not a web app. However, you can run it on Streamlit Cloud by:
1. Using Streamlit secrets for the API key
2. Running the screener via terminal/logs
3. Or creating a simple Streamlit wrapper (optional)

---

## 🚀 Quick Deploy to Streamlit Cloud

### 1. Fork/Clone Repository

```bash
# Fork the repository on GitHub
# Or push to your own repo
git clone https://github.com/pblo97/UltraQuality.git
cd UltraQuality
```

### 2. Configure Secrets

On Streamlit Cloud:

1. Go to your app settings
2. Click "Secrets" in the sidebar
3. Add this to your secrets:

```toml
FMP_API_KEY = "your_actual_api_key_here"
```

**Get API key**: https://financialmodelingprep.com

### 3. Deploy

1. Go to https://share.streamlit.io
2. Click "New app"
3. Select your repository
4. Set **Main file path**: `run_screener.py`
5. Click "Deploy"

---

## 🔧 Local Testing with Streamlit Secrets

```bash
# 1. Create .streamlit directory
mkdir -p .streamlit

# 2. Copy secrets template
cp .streamlit/secrets.toml.example .streamlit/secrets.toml

# 3. Edit secrets.toml
nano .streamlit/secrets.toml

# Add your real API key:
# FMP_API_KEY = "your_actual_key_here"

# 4. Test connection
python test_fmp_connection.py

# 5. Run screener
python run_screener.py
```

---

## 📝 Creating a Streamlit Web UI (Optional)

If you want a web interface, create `app.py`:

```python
import streamlit as st
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from screener.orchestrator import ScreenerPipeline

st.set_page_config(
    page_title="UltraQuality Screener",
    page_icon="📊",
    layout="wide"
)

st.title("📊 UltraQuality: Quality + Value Screener")

# Sidebar config
st.sidebar.header("Configuration")

top_k = st.sidebar.slider("Top-K Stocks", 50, 300, 150)
min_mcap = st.sidebar.number_input("Min Market Cap ($M)", 100, 10000, 500)

# Run screener button
if st.sidebar.button("Run Screener", type="primary"):
    with st.spinner("Running screener... This may take 3-5 minutes"):
        try:
            pipeline = ScreenerPipeline('settings.yaml')
            output = pipeline.run()

            st.success(f"✅ Screening complete!")

            # Display results
            import pandas as pd
            df = pd.read_csv(output)

            # Filter BUYs
            buys = df[df['decision'] == 'BUY']

            st.subheader(f"🎯 {len(buys)} BUY Signals")
            st.dataframe(
                buys[['ticker', 'name', 'composite_0_100', 'notes_short']]
                .sort_values('composite_0_100', ascending=False)
            )

            # Download button
            st.download_button(
                "Download Full Results (CSV)",
                df.to_csv(index=False).encode('utf-8'),
                "screener_results.csv",
                "text/csv"
            )

        except Exception as e:
            st.error(f"Error: {e}")

# Qualitative Analysis
st.sidebar.header("Qualitative Analysis")
symbol = st.sidebar.text_input("Symbol", "AAPL")

if st.sidebar.button("Analyze Symbol"):
    with st.spinner(f"Analyzing {symbol}..."):
        try:
            pipeline = ScreenerPipeline('settings.yaml')
            analysis = pipeline.get_qualitative_analysis(symbol)

            st.subheader(f"Deep-Dive: {symbol}")

            # Business summary
            st.write("**Business Summary:**")
            st.write(analysis['business_summary'])

            # Moats
            st.write("**Competitive Moats:**")
            moats = analysis['moats']
            cols = st.columns(5)
            for i, (moat, value) in enumerate(moats.items()):
                if moat != 'notes':
                    cols[i % 5].metric(moat.replace('_', ' ').title(), value)

            # Risks
            st.write("**Top Risks:**")
            for risk in analysis['top_risks']:
                with st.expander(risk['risk'][:50]):
                    st.write(f"**Probability:** {risk['prob']}")
                    st.write(f"**Severity:** {risk['severity']}")
                    st.write(f"**Trigger:** {risk['trigger']}")

        except Exception as e:
            st.error(f"Error: {e}")
```

Then deploy with:
```bash
streamlit run app.py
```

---

## 🔐 Environment Variables vs Secrets

### Streamlit Cloud (Production)
```toml
# .streamlit/secrets.toml (in Streamlit Cloud UI)
FMP_API_KEY = "your_key"
```

### Local Development
```bash
# .env
FMP_API_KEY=your_key
```

The code automatically tries both methods!

---

## 📊 Monitoring on Streamlit Cloud

### View Logs
1. Go to your app on Streamlit Cloud
2. Click "Manage app" → "Logs"
3. You'll see the screener output in real-time

### Check Resource Usage
- Free tier: 1 GB RAM
- Screener uses ~200-500 MB depending on universe size
- Caching reduces memory usage on subsequent runs

---

## ⚙️ Streamlit Configuration

Create `.streamlit/config.toml`:

```toml
[server]
maxUploadSize = 200
enableXsrfProtection = false

[browser]
gatherUsageStats = false

[theme]
primaryColor = "#00a86b"
backgroundColor = "#ffffff"
secondaryBackgroundColor = "#f0f2f6"
textColor = "#262730"
font = "sans serif"
```

---

## 🐛 Troubleshooting

### Issue: "FMP_API_KEY not found"

**Solution**: Add to Streamlit Cloud secrets (not .env)

```toml
FMP_API_KEY = "your_actual_key"
```

### Issue: "No profiles fetched"

**Causes**:
1. Invalid API key
2. Free plan doesn't support bulk endpoints
3. Network/firewall blocking FMP

**Solution**:
```bash
# Test connection first
python test_fmp_connection.py
```

### Issue: App timeout / out of memory

**Solutions**:
1. Reduce Top-K in `settings.yaml` (150 → 50)
2. Increase min market cap filter ($500M → $2B)
3. Upgrade to Streamlit Cloud paid tier

### Issue: Slow performance

**Solutions**:
1. Enable caching (already enabled by default)
2. Use bulk endpoints (requires paid FMP plan)
3. Reduce universe size with stricter filters

---

## 📈 Performance Tips

1. **Cache aggressively**: First run is slow, subsequent runs are fast
2. **Reduce Top-K**: Use 50 instead of 150 for faster results
3. **Filter strictly**: Higher market cap = fewer stocks = faster
4. **Upgrade FMP plan**: Paid plans have higher rate limits and bulk endpoints
5. **Run scheduled**: Set up weekly runs instead of on-demand

---

## 🔗 Resources

- **Streamlit Docs**: https://docs.streamlit.io
- **Streamlit Cloud**: https://share.streamlit.io
- **FMP API Docs**: https://site.financialmodelingprep.com/developer/docs
- **UltraQuality Docs**: [README.md](README.md)

---

## ✅ Checklist

Before deploying:

- [ ] API key added to Streamlit secrets
- [ ] Repository pushed to GitHub
- [ ] `requirements.txt` includes all dependencies
- [ ] Test connection: `python test_fmp_connection.py`
- [ ] Tested locally: `python run_screener.py`
- [ ] Reviewed `settings.yaml` configuration
- [ ] Checked FMP plan limits (requests/day)

---

**Ready to deploy?** Go to https://share.streamlit.io and click "New app"!
