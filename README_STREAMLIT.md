# 🚨 API Key Not Found Error - SOLUTION

If you see this error:
```
ValueError: No profiles fetched. Check API key and connectivity.
```

## ✅ Quick Fix (Streamlit Cloud)

You're running on **Streamlit Cloud** but the API key is not configured correctly.

### Step 1: Add API Key to Streamlit Secrets

1. Go to your app on Streamlit Cloud
2. Click **"⋮"** (three dots menu) → **"Settings"**
3. Click **"Secrets"** in the left sidebar
4. Add this:

```toml
FMP_API_KEY = "paste_your_real_api_key_here"
```

5. Click **"Save"**
6. Click **"Reboot app"**

### Step 2: Get Your API Key

If you don't have one:
1. Go to https://financialmodelingprep.com
2. Sign up (free plan available)
3. Copy your API key from the dashboard
4. Paste it in Streamlit secrets (Step 1 above)

---

## 🧪 Test Your API Key

Before running the full screener, test your connection:

```bash
python test_fmp_connection.py
```

This will:
- ✓ Find your API key (from secrets/env/.env)
- ✓ Test FMP API connection
- ✓ Verify your key is valid
- ✓ Check bulk endpoint availability

---

## 🔍 Troubleshooting

### Error: "API key not found"

**Cause**: Not configured in Streamlit secrets

**Fix**:
1. Go to Streamlit Cloud → App Settings → Secrets
2. Add: `FMP_API_KEY = "your_key"`
3. Save and reboot

---

### Error: "401 Unauthorized"

**Cause**: Invalid or expired API key

**Fix**:
1. Get a new key from https://financialmodelingprep.com
2. Update Streamlit secrets
3. Reboot app

---

### Error: "403 Forbidden" or "Rate limit exceeded"

**Cause**: Free plan limits exceeded

**Fix**:
1. Upgrade to paid plan ($14-$30/month)
2. Or reduce `top_k` in `settings.yaml` (150 → 50)
3. Or increase `min_market_cap` ($500M → $2B)

---

### Error: "No profiles fetched" but key is valid

**Cause**: Bulk endpoint not available (free plan)

**Fix**:
The screener will try to fallback to individual requests (slower).

Edit `src/screener/orchestrator.py` line ~165:

Change:
```python
for part in range(5):  # Fetch first 5 parts
```

To:
```python
for part in range(1):  # Fetch only 1 part (faster for testing)
```

Or upgrade to a paid FMP plan that includes bulk endpoints.

---

## 📊 Streamlit Cloud vs Local

### Streamlit Cloud
```toml
# Configure in UI: Settings → Secrets
FMP_API_KEY = "your_key"
```

### Local Machine
```bash
# Create .env file
echo "FMP_API_KEY=your_key" > .env

# Or export
export FMP_API_KEY="your_key"
```

---

## 🎯 Where to Configure

The code tries 3 locations **in order**:

1. **Streamlit secrets** (`.streamlit/secrets.toml` or Streamlit Cloud UI)
2. **Environment variable** (`export FMP_API_KEY=...`)
3. **Config file** (`settings.yaml` - NOT recommended)

---

## ✅ Verification Steps

1. **Test API key**:
   ```bash
   python test_fmp_connection.py
   ```

2. **Expected output**:
   ```
   ✓ API key found (Streamlit secrets)
   Key: abc1234567...xyz9
   Testing connection to FMP API...
   HTTP Status: 200
   Company: Apple Inc.
   ✅ API connection successful!
   ```

3. **If successful**, run screener:
   ```bash
   python run_screener.py
   ```

---

## 📞 Still Having Issues?

1. Check FMP status: https://financialmodelingprep.com/status
2. Verify your plan: https://financialmodelingprep.com/developer/docs/pricing
3. Test manually:
   ```bash
   curl "https://financialmodelingprep.com/api/v3/profile/AAPL?apikey=YOUR_KEY"
   ```

If you get valid JSON back, your key works!

---

## 🚀 Next Steps

Once your API key is configured:

```bash
# Full screening
python run_screener.py

# Analyze specific stock
python run_screener.py --symbol AAPL

# Custom config
python run_screener.py --config my_settings.yaml
```

Results will be in: `./data/screener_results.csv`

---

**Need more help?** See [STREAMLIT_DEPLOY.md](STREAMLIT_DEPLOY.md) for full deployment guide.
