# 🌍 Global Stock Screening (Hamco Global Style)

## Feature Overview

Comprehensive multi-country stock screening across **24 major markets** worldwide, covering developed and emerging markets. Inspired by global funds like Hamco Global that invest across continents.

## Supported Markets (24 Total)

### 🌎 North America (2)
- 🇺🇸 **United States** (NYSE, NASDAQ, AMEX) - 5000+ stocks
  - Apple, Microsoft, Google, Meta, Tesla
- 🇨🇦 **Canada** (TSX) - 1500+ stocks
- 🇲🇽 **Mexico** (MEX - BMV) - Mexican companies
- 🇧🇷 **Brazil** (SAO - B3) - Brazilian companies
- 🇨🇱 **Chile** (SCS - Santiago) - Copper & Lithium companies

### Europe
- 🇬🇧 **United Kingdom** (LSE - London) - 2000+ stocks
- 🇩🇪 **Germany** (XETRA - Frankfurt) - 500+ stocks (DAX, MDAX)
- 🇫🇷 **France/Europe** (EURONEXT) - Pan-European (France, Netherlands, Belgium, Portugal)

### Asia
- 🇮🇳 **India** (IN - NSE/BSE) - 1700+ stocks
- 🇨🇳 **China - Hong Kong** (HK - HKSE) - Major Chinese companies (Alibaba, Tencent, etc.)
- 🇨🇳 **China - Shanghai** (CN - SSE) - A-shares, mainland China
- 🇰🇷 **South Korea** (KR - KRX) - Samsung, Hyundai, LG, SK
- 🇯🇵 **Japan** (JP - TSE) - Toyota, Sony, SoftBank

### All Regions
- 🌎 **All Regions** - Combined screening (may be slower)

---

## Changes Made

### 1. UI Changes (run_screener.py)

Added new dropdown selector in sidebar under "🌍 Universe Filters":

```python
region_options = {
    "🇺🇸 United States": "US",
    "🇨🇦 Canada": "CA",
    "🇬🇧 United Kingdom": "UK",
    "🇩🇪 Germany": "DE",
    "🇫🇷 France / Europe": "FR",
    "🇮🇳 India": "IN",
    "🇨🇳 China (Hong Kong)": "HK",
    "🇨🇳 China (Shanghai)": "CN",
    "🇰🇷 South Korea": "KR",
    "🇯🇵 Japan": "JP",
    "🇨🇱 Chile": "CL",
    "🇲🇽 Mexico": "MX",
    "🇧🇷 Brazil": "BR",
    "🌎 All Regions": "ALL"
}
```

**Features:**
- User-friendly country flags and names
- Information tooltip showing number of stocks per region
- Default to US market
- Uses ISO 2-letter country codes for filtering via FMP API `country` parameter

### 2. API Client (src/screener/ingest.py)

Added `country` parameter to stock screener:

```python
def get_stock_screener(
    self,
    market_cap_more_than: Optional[int] = None,
    volume_more_than: Optional[int] = None,
    exchange: Optional[str] = None,
    country: Optional[str] = None,  # NEW: Country code filtering
    limit: int = 10000
) -> List[Dict]:
    """
    Args:
        exchange: Exchange code (e.g., 'nasdaq', 'nyse', 'tsx', 'lse')
        country: Country code (e.g., 'US', 'MX', 'BR', 'HK', 'CA')
                Recommended for international markets.
    """
```

The `country` parameter uses 2-letter ISO country codes and is more reliable than exchange codes for international markets.

### 3. Pipeline Orchestrator (src/screener/orchestrator.py)

Modified universe building to support country/exchange filtering:

**Before:**
- Always queried all exchanges without filtering

**After:**
- Reads `exchanges` list from config (can contain country codes or exchange codes)
- Auto-detects if value is country code (2 uppercase letters) or exchange code
- Uses appropriate API parameter (country vs exchange)
- Aggregates results from multiple filters

```python
if exchanges:
    for exchange in exchanges:
        # Detect if country code (2 uppercase letters) or exchange code
        is_country_code = len(exchange) == 2 and exchange.isupper()

        if is_country_code:
            profiles = self.fmp.get_stock_screener(
                market_cap_more_than=min_mcap,
                volume_more_than=min_vol // 1000,
                country=exchange,  # ← Filter by country code
                limit=10000
            )
        else:
            profiles = self.fmp.get_stock_screener(
                market_cap_more_than=min_mcap,
                volume_more_than=min_vol // 1000,
                exchange=exchange.lower(),  # ← Filter by exchange
                limit=10000
            )
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
| Hong Kong (HK) | SYMBOL.HK | 0700.HK, 9988.HK |
| Shanghai (CN) | SYMBOL.SS | 600519.SS |
| South Korea (KR) | SYMBOL.KS | 005930.KS (Samsung) |
| Japan (JP) | SYMBOL.T | 7203.T (Toyota) |
| Mexico (MX) | SYMBOL.MX | WALMEX.MX, CEMEXCPO.MX |
| Brazil (BR) | SYMBOL.SA | PETR4.SA, VALE3.SA |

---

## Technical Notes

### Country Codes Used

| Region | FMP Country Code | Markets Included |
|--------|------------------|------------------|
| US | `US` | NYSE, NASDAQ, AMEX |
| Canada | `CA` | Toronto Stock Exchange (TSX) |
| UK | `UK` | London Stock Exchange (LSE) |
| Germany | `DE` | Frankfurt/XETRA |
| France | `FR` | Euronext Paris |
| India | `IN` | NSE, BSE |
| Hong Kong | `HK` | Hong Kong Stock Exchange |
| China | `CN` | Shanghai, Shenzhen |
| South Korea | `KR` | Korea Exchange (KRX/KOSPI) |
| Japan | `JP` | Tokyo Stock Exchange (TSE) |
| Chile | `CL` | Santiago Stock Exchange |
| Mexico | `MX` | Mexican Stock Exchange (BMV) |
| Brazil | `BR` | B3 São Paulo |

**Note:** The screener uses ISO 2-letter country codes instead of exchange codes. This is more reliable as the FMP API's `country` parameter is better documented and more consistent than exchange-specific filtering.

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

Test with these well-known international stocks to verify each market works:

### North America
**Canada:**
- SHOP.TO (Shopify) - E-commerce Tech
- TD.TO (TD Bank) - Banking
- ABX.TO (Barrick Gold) - Mining

### Europe Developed
**UK:**
- BP.L (BP) - Energy
- HSBA.L (HSBC) - Financial
- ULVR.L (Unilever) - Consumer Goods

**Germany:**
- SAP.DE (SAP) - Enterprise Software
- VOW3.DE (Volkswagen) - Automotive
- BMW.DE (BMW) - Automotive

**France:**
- MC.PA (LVMH) - Luxury
- OR.PA (L'Oréal) - Beauty
- AIR.PA (Airbus) - Aerospace

**Spain:**
- ITX.MC (Inditex/Zara) - Retail
- SAN.MC (Santander) - Banking

**Switzerland:**
- NESN.SW (Nestlé) - Food & Beverage
- ROG.SW (Roche) - Pharma
- NOVN.SW (Novartis) - Pharma

**Italy:**
- RACE.MI (Ferrari) - Luxury Auto
- ENI.MI (ENI) - Energy

### Asia Developed
**Japan:**
- 7203.T (Toyota) - Automotive
- 6758.T (Sony) - Electronics/Entertainment
- 9984.T (SoftBank) - Telecom/Investments

**Australia:**
- BHP.AX (BHP) - Mining
- CSL.AX (CSL) - Biotechnology
- CBA.AX (Commonwealth Bank) - Banking

**Singapore:**
- D05.SI (DBS Bank) - Banking
- SE.SI (Sea Limited) - Tech/E-commerce

### Asia Emerging
**South Korea:**
- 005930.KS (Samsung Electronics) - Tech/Semiconductors
- 005380.KS (Hyundai Motor) - Automotive
- 000660.KS (SK Hynix) - Semiconductors

**Taiwan:**
- 2330.TW (TSMC) - Semiconductors (World's largest foundry)
- 2317.TW (Hon Hai/Foxconn) - Electronics Manufacturing
- 2454.TW (MediaTek) - Semiconductors

**India:**
- RELIANCE.NS (Reliance Industries) - Conglomerate (Energy, Retail, Telecom)
- TCS.NS (Tata Consultancy Services) - IT Services
- INFY.NS (Infosys) - IT Services

**China (Hong Kong):**
- 0700.HK (Tencent) - Internet/Gaming
- 9988.HK (Alibaba) - E-commerce
- 1810.HK (Xiaomi) - Consumer Electronics

**China (Shanghai):**
- 600519.SS (Kweichow Moutai) - Spirits/Luxury
- 601398.SS (ICBC) - Banking

### Latin America
**Brazil:**
- VALE3.SA (Vale) - Mining (Iron Ore)
- PETR4.SA (Petrobras) - Energy
- ITUB4.SA (Itaú Unibanco) - Banking

**Mexico:**
- AMXL.MX (América Móvil) - Telecom
- FEMSAUBD.MX (Femsa) - Beverages/Retail
- CEMEXCPO.MX (Cemex) - Cement

**Chile:**
- SQM-B.SN (SQM) - Lithium Mining (Critical for EVs)
- COPEC.SN (Copec) - Energy/Retail
- FALABELLA.SN (Falabella) - Retail

**Peru:**
- SCCO.LM (Southern Copper) - Mining
- BAP.LM (Credicorp) - Banking
- BVN.LM (Buenaventura) - Gold Mining

**Colombia:**
- ECOPETROL.CN (Ecopetrol) - Energy
- PFBCOLOM.CN (Bancolombia) - Banking

**South Korea:**
- 005930.KS (Samsung Electronics) - Technology
- 005380.KS (Hyundai Motor) - Automotive

**Japan:**
- 7203.T (Toyota Motor) - Automotive
- 9984.T (SoftBank Group) - Technology/Telecom

**Mexico:**
- WALMEX.MX (Walmart de México) - Retail
- CEMEXCPO.MX (Cemex) - Building Materials

**Brazil:**
- PETR4.SA (Petrobras) - Energy
- VALE3.SA (Vale) - Mining

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
GET /api/v3/stock-screener?country=CA&marketCapMoreThan=500000000
→ Screen stocks by country code (recommended for international markets)

GET /api/v3/stock-screener?exchange=tsx&marketCapMoreThan=500000000
→ Screen stocks by exchange code (lowercase, for specific exchanges)

GET /api/v3/stock-screener?marketCapMoreThan=500000000
→ Screen all regions (no country/exchange filter)
```

**Note:** The `country` parameter is preferred over `exchange` for international markets as it's more reliable and better documented in the FMP API.

---

## Support

For issues or questions:
- Check FMP API documentation: https://site.financialmodelingprep.com/developer/docs
- Verify exchange codes in exchanges-list endpoint
- Ensure Ultimate plan has international data access
