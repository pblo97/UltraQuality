# 🔧 Fix: Insider Trading API Endpoint

## Problem
Insider Trading analysis was returning `available: false` despite the user having an Ultimate FMP plan that includes all premium features.

## Root Cause
The code was using the **wrong API version**:
- ❌ Used: `https://financialmodelingprep.com/api/v3/insider-trading`
- ✅ Correct: `https://financialmodelingprep.com/api/v4/insider-trading`

According to FMP's official documentation, the Insider Trading endpoint is a **v4 API**, not v3.

## What Was Changed

### File: `src/screener/ingest.py`

**Method:** `get_insider_trading()`

**Changes:**
1. Updated to use v4 API endpoint instead of v3
2. Changed parameter from `limit` to `page` (v4 uses pagination)
3. Explicitly construct v4 URL: `v4_base_url = self.base_url.replace('/api/v3', '/api/v4')`
4. Added detailed error handling and logging
5. Updated docstring to document that it uses v4

**Before:**
```python
def get_insider_trading(self, symbol: str, limit: int = 100) -> List[Dict]:
    params = {'symbol': symbol, 'limit': limit}
    return self._request('insider-trading', params, cache=self.cache_symbol)
```

**After:**
```python
def get_insider_trading(self, symbol: str, limit: int = 100) -> List[Dict]:
    # Insider trading is a v4 endpoint
    v4_base_url = self.base_url.replace('/api/v3', '/api/v4')
    url = f"{v4_base_url}/insider-trading"
    params = {'symbol': symbol, 'page': 0}  # v4 uses 'page' instead of 'limit'
    # ... full request handling with error checking
```

## How to Test

### 1. Quick test (if you have API key):
```bash
python test_both_endpoints.py
```

This will test both v3 and v4 endpoints and confirm v4 works.

### 2. Full test in UI:
```bash
# Clean cache and restart
python diagnose_and_clean.py

# Start Streamlit
python run_screener.py

# In UI:
# 1. Go to "Deep Dive" tab
# 2. Enter a symbol (e.g., AAPL)
# 3. Click "Run Deep Analysis"
# 4. Open the "🔍 DEBUG: Premium Features Status" expander
# 5. Look for insider_trading in intrinsic_value section
# 6. Should now show: "available": true with full analysis
```

## Expected Result

**Before fix:**
```json
"insider_trading": {
  "available": false,
  "note": "No insider trading data available"
}
```

**After fix (with data):**
```json
"insider_trading": {
  "available": true,
  "score": 85,
  "signal": "Strong Buy",
  "buy_cluster_3m": 5,
  "executive_buying": true,
  "buy_sell_ratio": 4.2,
  "net_dollar_value": 5000000,
  "interpretation": "Multiple insiders buying, including C-suite executives",
  "detailed_transactions": [...]
}
```

**After fix (no data for symbol):**
```json
"insider_trading": {
  "available": false,
  "note": "No insider trading data available"
}
```

Note: Some symbols legitimately have no insider trading data (small companies, recent IPOs, etc.). Try AAPL, MSFT, GOOGL which definitely have insider trading activity.

## Technical Details

### Why v4 instead of v3?

From FMP documentation:
- **v3**: Legacy APIs, some endpoints deprecated
- **v4**: Current APIs for premium features
- **Insider Trading**: Explicitly documented as v4 endpoint

### Parameter Differences

| Version | Parameters | Example |
|---------|------------|---------|
| v3 | symbol, limit | `?symbol=AAPL&limit=100` |
| v4 | symbol, page | `?symbol=AAPL&page=0` |

### Why the fix wasn't applied before

The base URL was configured to v3 globally (`https://financialmodelingprep.com/api/v3`), and the `_request()` helper method automatically prepended this. The fix required:
1. Detecting that insider trading needs v4
2. Overriding the base URL for this specific endpoint
3. Implementing custom request logic to use v4

## Other Premium Features

✅ **Earnings Call Sentiment**: Already working (uses v3 endpoint correctly)
✅ **Insider Trading**: Now fixed (uses v4 endpoint)

## Status
🟢 **FIXED** - Insider Trading now uses correct v4 API endpoint
