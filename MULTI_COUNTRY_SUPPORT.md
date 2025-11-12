# 🌍 Multi-Country Stock Screening

## Feature Overview

Added support for screening stocks from multiple countries/regions beyond just the United States.

## Supported Markets

### Americas
- 🇺🇸 **United States** (NYSE, NASDAQ, AMEX) - 5000+ stocks
- 🇨🇦 **Canada** (TSX) - 1500+ stocks
- 🇨🇱 **Chile** (SCS - Santiago) - Copper & Lithium companies

### Europe
- 🇬🇧 **United Kingdom** (LSE - London) - 2000+ stocks
- 🇩🇪 **Germany** (XETRA - Frankfurt) - 500+ stocks (DAX, MDAX)
- 🇫🇷 **France/Europe** (EURONEXT) - Pan-European (France, Netherlands, Belgium, Portugal)

### Asia
- 🇮🇳 **India** (NSE - National Stock Exchange) - 1700+ stocks
- 🇨🇳 **China - Hong Kong** (HKSE) - Major Chinese companies (Alibaba, Tencent, etc.)
- 🇨🇳 **China - Shanghai** (SHZ) - A-shares, mainland China

### All Regions
- 🌎 **All Regions** - Combined screening (may be slower)

---

## Changes Made

### 1. UI Changes (run_screener.py)

Added new dropdown selector in sidebar under "🌍 Universe Filters":

```python
region_options = {
    "🇺🇸 United States": "US",
    "🇨🇦 Canada": "TSX",
    "🇬🇧 United Kingdom": "LSE",
    "🇩🇪 Germany": "XETRA",
    "🇫🇷 France / Europe": "EURONEXT",
    "🇮🇳 India": "NSE",
    "🇨🇳 China (Hong Kong)": "HKSE",
    "🇨🇳 China (Shanghai)": "SHZ",
    "🇨🇱 Chile": "SCS",
    "🌎 All Regions": "ALL"
}
```

**Features:**
- User-friendly country flags and names
- Information tooltip showing number of stocks per region
- Default to US market
- Pass selected exchange to pipeline config

### 2. API Client (src/screener/ingest.py)

Added new method to retrieve available exchanges:

```python
def get_exchanges_list(self) -> List[Dict]:
    """
    Endpoint: /exchanges-list
    Returns list of all available exchanges in FMP.
    """
    return self._request('exchanges-list', cache=self.cache_universe)
```

Updated `get_stock_screener()` documentation to clarify exchange parameter usage.

### 3. Pipeline Orchestrator (src/screener/orchestrator.py)

Modified universe building to support exchange filtering:

**Before:**
- Always queried all exchanges without filtering

**After:**
- Reads `exchanges` list from config
- If exchanges specified → queries each exchange separately
- If no exchanges (empty list) → queries all regions
- Aggregates results from multiple exchanges

```python
if exchanges:
    for exchange in exchanges:
        profiles = self.fmp.get_stock_screener(
            market_cap_more_than=min_mcap,
            volume_more_than=min_vol // 1000,
            exchange=exchange,  # ← Filter by exchange
            limit=10000
        )
else:
    # No filter - get all regions
    profiles = self.fmp.get_stock_screener(...)
```

---

## How to Use

### 1. In the UI (Streamlit)

**Step 1:** Open sidebar → "🌍 Universe Filters"

**Step 2:** Select desired market from "📍 Market/Region" dropdown

**Step 3:** Configure other filters (Market Cap, Volume, etc.)

**Step 4:** Click "🚀 Run Screener"

### 2. Example: Screen Canadian Stocks

```
1. Select: 🇨🇦 Canada
2. Min Market Cap: $500M (lower than US default)
3. Min Volume: $2M (lower than US default)
4. Run Screener
```

Results will show only TSX-listed companies.

### 3. Example: Screen European Value Stocks

```
1. Select: 🇫🇷 France / Europe (EURONEXT)
2. Min Market Cap: $1B
3. Quality Weight: 0.60 (more value-focused)
4. Run Screener
```

### 4. Example: Screen All Regions

```
1. Select: 🌎 All Regions
2. Min Market Cap: $5B (higher to avoid too many results)
3. Run Screener
```

**Note:** "All Regions" may be slower as it queries all exchanges.

---

## International Symbol Format

When using Deep Dive for individual stock analysis, use proper ticker format:

| Exchange | Format | Example |
|----------|--------|---------|
| US (NYSE/NASDAQ) | SYMBOL | AAPL, MSFT |
| Canada (TSX) | SYMBOL.TO | SHOP.TO, TD.TO |
| UK (LSE) | SYMBOL.L | BP.L, HSBA.L |
| Germany (XETRA) | SYMBOL.DE | SAP.DE, VOW3.DE |
| France (EURONEXT) | SYMBOL.PA | MC.PA, OR.PA |
| India (NSE) | SYMBOL.NS | RELIANCE.NS, TCS.NS |
| Hong Kong (HKSE) | SYMBOL.HK | 0700.HK, 9988.HK |
| Shanghai (SHZ) | SYMBOL.SS | 600519.SS |

---

## Technical Notes

### Exchange Codes Used

| Region | FMP Exchange Code | Markets Included |
|--------|-------------------|------------------|
| US | `NYSE`, `NASDAQ`, `AMEX` | All US exchanges |
| Canada | `TSX` | Toronto Stock Exchange |
| UK | `LSE` | London Stock Exchange |
| Germany | `XETRA` | Frankfurt/XETRA |
| Europe | `EURONEXT` | France, Netherlands, Belgium, Portugal |
| India | `NSE` | National Stock Exchange of India |
| Hong Kong | `HKSE` | Hong Kong Stock Exchange |
| Shanghai | `SHZ` | Shanghai Stock Exchange |
| Chile | `SCS` | Santiago Stock Exchange |

### Currency Considerations

- All market cap and volume filters are in **USD equivalent**
- FMP API converts foreign currencies to USD automatically
- Results show market cap and prices in USD

### Performance

- **Single Exchange:** ~30-60 seconds to fetch universe
- **Multiple Exchanges (US):** ~60-90 seconds (queries 3 exchanges: NYSE, NASDAQ, AMEX)
- **All Regions:** ~2-3 minutes (queries all available exchanges)

---

## Future Enhancements

Potential improvements for future versions:

1. **Currency Display Options**
   - Show prices in local currency
   - Add currency conversion info

2. **More Exchanges**
   - Japan (JPX/TSE)
   - Australia (ASX)
   - Brazil (BOVESPA)
   - Mexico (BMV)

3. **Multi-Region Screening**
   - Select multiple regions at once
   - Compare stocks across regions

4. **Region-Specific Metrics**
   - Different quality/value thresholds per region
   - Adjust for accounting standards (GAAP vs IFRS)

---

## Testing Recommendations

Test with these well-known international stocks:

**Canada:**
- SHOP.TO (Shopify) - Tech
- TD.TO (TD Bank) - Financial

**UK:**
- BP.L (BP) - Energy
- HSBA.L (HSBC) - Financial

**Germany:**
- SAP.DE (SAP) - Tech
- VOW3.DE (Volkswagen) - Auto

**India:**
- RELIANCE.NS (Reliance Industries)
- TCS.NS (Tata Consultancy)

**Hong Kong:**
- 0700.HK (Tencent)
- 9988.HK (Alibaba)

**Chile:**
- COPEC.SN (Copec) - Energy/Retail
- SQM-B.SN (SQM) - Lithium mining

---

## Known Limitations

1. **Data Availability**
   - Some exchanges have less comprehensive data
   - Insider trading data primarily available for US stocks
   - Earnings transcripts mainly US companies

2. **Market Hours**
   - Real-time data limited to US exchanges
   - International exchanges may have delayed quotes

3. **Premium Features**
   - Insider Trading Analysis: Primarily US stocks
   - Earnings Call Sentiment: Mainly large-cap international

---

## Files Modified

1. `src/screener/ingest.py` (lines 219-228)
   - Added `get_exchanges_list()` method
   - Updated `get_stock_screener()` docs

2. `src/screener/orchestrator.py` (lines 195-226)
   - Modified universe building with exchange filtering
   - Added multi-exchange support

3. `run_screener.py` (lines 656-722, 863-872)
   - Added region selector UI
   - Pass exchange filter to pipeline

---

## API Endpoints Used

```
GET /api/v3/exchanges-list
→ Returns list of all available exchanges

GET /api/v3/stock-screener?exchange=TSX&marketCapMoreThan=500000000
→ Screen stocks on specific exchange

GET /api/v3/stock-screener?marketCapMoreThan=500000000
→ Screen all exchanges (no exchange parameter)
```

---

## Support

For issues or questions:
- Check FMP API documentation: https://site.financialmodelingprep.com/developer/docs
- Verify exchange codes in exchanges-list endpoint
- Ensure Ultimate plan has international data access
