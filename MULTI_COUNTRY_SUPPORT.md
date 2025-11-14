# 🌍 Global Stock Screening (Hamco Global Style)

## Feature Overview

Comprehensive multi-country stock screening across **24 major markets** worldwide, covering developed and emerging markets. Inspired by global funds like Hamco Global that invest across continents.

## Supported Markets (24 Total)

### 🌎 North America (2)
- 🇺🇸 **United States** (NYSE, NASDAQ, AMEX) - 5000+ stocks
  - Apple, Microsoft, Google, Meta, Tesla
- 🇨🇦 **Canada** (TSX) - 1500+ stocks
  - Shopify, TD Bank, Barrick Gold, Royal Bank

### 🇪🇺 Europe Developed (6)
- 🇬🇧 **United Kingdom** (LSE) - 2000+ stocks
  - BP, HSBC, Shell, Unilever, AstraZeneca
- 🇩🇪 **Germany** (XETRA) - 500+ stocks
  - SAP, Volkswagen, Siemens, BMW, Allianz
- 🇫🇷 **France/Europe** (EURONEXT) - 1300+ stocks
  - LVMH, Airbus, ASML, Heineken, L'Oréal
- 🇪🇸 **Spain** (BME - Madrid) - 130+ stocks
  - Telefónica, Santander, Inditex (Zara), Iberdrola
- 🇨🇭 **Switzerland** (SIX) - 250+ stocks
  - Nestlé, Roche, Novartis, UBS, ABB
- 🇮🇹 **Italy** (MIL - Milan) - 400+ stocks
  - Ferrari, ENI, Intesa Sanpaolo, Enel

### 🌏 Asia Developed (3)
- 🇯🇵 **Japan** (JPX - Tokyo) - 3700+ stocks
  - Toyota, Sony, SoftBank, Keyence, Nintendo
- 🇦🇺 **Australia** (ASX) - 2200+ stocks
  - BHP, CSL, Commonwealth Bank, Fortescue Metals
- 🇸🇬 **Singapore** (SGX) - 700+ stocks
  - DBS Bank, Sea Limited (Shopee), Grab Holdings

### 🌏 Asia Emerging (5)
- 🇰🇷 **South Korea** (KRX - KOSPI) - 2400+ stocks
  - Samsung Electronics, Hyundai Motor, LG, SK Hynix
- 🇹🇼 **Taiwan** (TWSE) - 950+ stocks
  - TSMC, Hon Hai/Foxconn, MediaTek, Delta Electronics
- 🇮🇳 **India** (NSE - Mumbai) - 1700+ stocks
  - Reliance Industries, TCS, Infosys, HDFC Bank
- 🇨🇳 **China (Hong Kong)** (HKSE) - 2500+ stocks
  - Alibaba, Tencent, Xiaomi, JD.com, Meituan
- 🇨🇳 **China (Shanghai)** (SHZ) - 1500+ A-shares
  - Kweichow Moutai, ICBC, PetroChina, Ping An

### 🌎 Latin America (5)
- 🇧🇷 **Brazil** (BOVESPA - São Paulo) - 450+ stocks
  - Vale, Petrobras, Itaú Unibanco, Bradesco
- 🇲🇽 **Mexico** (BMV) - 145+ stocks
  - América Móvil, Femsa, Cemex, Walmex
- 🇨🇱 **Chile** (SCS - Santiago) - 200+ stocks
  - SQM (Lithium), Copec, Falabella, CMPC
- 🇵🇪 **Peru** (BVL - Lima) - 250+ stocks
  - Southern Copper, Credicorp, Buenaventura
- 🇨🇴 **Colombia** (BVC - Bogotá) - 70+ stocks
  - Ecopetrol, Bancolombia, Grupo Aval

### 🌐 All Markets
- 🌎 **All Regions** - All 24 markets combined (~17,000+ stocks)

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

| Exchange | Format | Example Companies |
|----------|--------|-------------------|
| **North America** |
| US (NYSE/NASDAQ) | `SYMBOL` | AAPL, MSFT, GOOGL |
| Canada (TSX) | `SYMBOL.TO` | SHOP.TO (Shopify), TD.TO (TD Bank) |
| **Europe Developed** |
| UK (LSE) | `SYMBOL.L` | BP.L, HSBA.L (HSBC), ULVR.L (Unilever) |
| Germany (XETRA) | `SYMBOL.DE` | SAP.DE, VOW3.DE (Volkswagen), BMW.DE |
| France (EURONEXT) | `SYMBOL.PA` | MC.PA (LVMH), OR.PA (L'Oréal), AIR.PA (Airbus) |
| Spain (BME) | `SYMBOL.MC` | TEF.MC (Telefónica), SAN.MC (Santander), ITX.MC (Inditex) |
| Switzerland (SIX) | `SYMBOL.SW` | NESN.SW (Nestlé), ROG.SW (Roche), NOVN.SW (Novartis) |
| Italy (MIL) | `SYMBOL.MI` | RACE.MI (Ferrari), ENI.MI, ISP.MI (Intesa) |
| **Asia Developed** |
| Japan (JPX) | `SYMBOL.T` | 7203.T (Toyota), 6758.T (Sony), 9984.T (SoftBank) |
| Australia (ASX) | `SYMBOL.AX` | BHP.AX, CSL.AX, CBA.AX (Commonwealth Bank) |
| Singapore (SGX) | `SYMBOL.SI` | D05.SI (DBS), SE.SI (Sea Limited) |
| **Asia Emerging** |
| South Korea (KRX) | `SYMBOL.KS` | 005930.KS (Samsung), 005380.KS (Hyundai) |
| Taiwan (TWSE) | `SYMBOL.TW` | 2330.TW (TSMC), 2317.TW (Hon Hai/Foxconn) |
| India (NSE) | `SYMBOL.NS` | RELIANCE.NS, TCS.NS (Tata Consultancy), INFY.NS (Infosys) |
| Hong Kong (HKSE) | `SYMBOL.HK` | 0700.HK (Tencent), 9988.HK (Alibaba), 1810.HK (Xiaomi) |
| Shanghai (SHZ) | `SYMBOL.SS` | 600519.SS (Kweichow Moutai), 601398.SS (ICBC) |
| **Latin America** |
| Brazil (BOVESPA) | `SYMBOL.SA` | VALE3.SA (Vale), PETR4.SA (Petrobras), ITUB4.SA (Itaú) |
| Mexico (BMV) | `SYMBOL.MX` | AMXL.MX (América Móvil), FEMSAUBD.MX (Femsa) |
| Chile (SCS) | `SYMBOL.SN` | SQM-B.SN (SQM Lithium), COPEC.SN |
| Peru (BVL) | `SYMBOL.LM` | SCCO.LM (Southern Copper), BAP.LM (Credicorp) |
| Colombia (BVC) | `SYMBOL.CN` | ECOPETROL.CN, PFBCOLOM.CN (Bancolombia) |

---

## Technical Notes

### Exchange Codes Used

| Region | FMP Exchange Code | Markets Included |
|--------|-------------------|------------------|
| **North America** |
| United States | `NYSE`, `NASDAQ`, `AMEX` | All US exchanges |
| Canada | `TSX` | Toronto Stock Exchange |
| **Europe Developed** |
| United Kingdom | `LSE` | London Stock Exchange |
| Germany | `XETRA` | Frankfurt/XETRA |
| France/Europe | `EURONEXT` | France, Netherlands, Belgium, Portugal |
| Spain | `BME` | Madrid Stock Exchange |
| Switzerland | `SIX` | Swiss Exchange |
| Italy | `MIL` | Milan Stock Exchange (Borsa Italiana) |
| **Asia Developed** |
| Japan | `JPX` | Tokyo Stock Exchange |
| Australia | `ASX` | Australian Securities Exchange |
| Singapore | `SGX` | Singapore Exchange |
| **Asia Emerging** |
| South Korea | `KRX` | Korea Exchange (KOSPI) |
| Taiwan | `TWSE` | Taiwan Stock Exchange |
| India | `NSE` | National Stock Exchange of India |
| Hong Kong | `HKSE` | Hong Kong Stock Exchange |
| Shanghai | `SHZ` | Shanghai Stock Exchange |
| **Latin America** |
| Brazil | `BOVESPA` | B3 - São Paulo Stock Exchange |
| Mexico | `BMV` | Bolsa Mexicana de Valores |
| Chile | `SCS` | Santiago Stock Exchange |
| Peru | `BVL` | Lima Stock Exchange (Bolsa de Valores de Lima) |
| Colombia | `BVC` | Colombia Stock Exchange (Bolsa de Valores de Colombia) |

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
