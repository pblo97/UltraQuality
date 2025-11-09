# Intrinsic Value Calculation Troubleshooting Guide

## Overview
This guide helps you troubleshoot "N/A" values in the Intrinsic Value Estimation section.

## How to Use the Diagnostic System

### Step 1: Check the Debug Section

When you run qualitative analysis for a symbol:

1. Go to **🔍 Qualitative** tab
2. Select a ticker and click "🔍 Run Deep Analysis"
3. Scroll to **💰 Intrinsic Value Estimation** section
4. Click the expandable section **"📋 Calculation Details & Debug Info"**

### Step 2: Interpret the Messages

Messages are color-coded for easy identification:

#### ✅ **Green (Success)**
```
✓ DCF: $123.45 (WACC: 10.0%)
✓ Forward Multiple: $234.56
```
**Meaning**: Calculation completed successfully

#### ❌ **Red (Error)**
```
✗ DCF: Base cash flow <= 0 (got -5,234,567). Company may have negative FCF or losses.
✗ Forward Multiple: EBIT forward <= 0 (got -2,345,678). Check EBITDA and D&A data.
✗ DCF: Missing financials - income:True, balance:True, cashflow:False
✗ DCF: Could not get shares outstanding (got 0)
```
**Meaning**: Calculation failed - shows exact reason and values

#### ⚠️ **Yellow (Warning)**
```
⚠️ Current price unavailable - showing intrinsic values only (no upside/downside calculation)
```
**Meaning**: Partial data available, some features disabled

#### ℹ️ **Blue (Info)**
```
Industry: High Growth Asset Light
Primary metric: EV/Revenue
Methods: DCF, Forward Multiple
WACC: 11.0%
```
**Meaning**: General information about the calculation

### Step 3: Common Issues and Solutions

#### Issue: "DCF: Missing financials"

**Possible Causes:**
- Company is too new (IPO < 2 years ago)
- FMP API doesn't have data for this symbol
- Symbol is not a stock (e.g., ETF, index)

**Solution:**
- Check if the symbol is correct
- Try a different, more established company
- Verify the company type is correct (non_financial, financial, reit)

#### Issue: "DCF: Base cash flow <= 0"

**Possible Causes:**
- Company has negative free cash flow
- Company is loss-making
- High growth company with large capex

**What This Means:**
- **Not necessarily bad!** Many high-growth companies (Amazon, Tesla in early years) had negative FCF
- The DCF model can't value companies with negative FCF using traditional methods
- Other valuation methods (Forward Multiple) may still work

**Alternative:**
- Check **Forward Multiple** value instead
- For growth companies, revenue multiples are more appropriate anyway

#### Issue: "Forward Multiple: EBIT forward <= 0"

**Possible Causes:**
- Company has negative EBITDA
- Missing depreciation & amortization data
- Operating losses

**What This Means:**
- Company is not profitable at operating level
- May be early-stage or in restructuring
- Traditional multiple-based valuation doesn't apply

**Solution:**
- This is normal for early-stage tech companies
- Look at revenue multiples instead (not currently implemented)
- Consider if the company is worth analyzing at all

#### Issue: "Could not get shares outstanding"

**Possible Causes:**
- Data issue with FMP API
- Symbol format incorrect (use base symbol, not suffixes like .A, .B)

**Solution:**
- Try using the base ticker (e.g., BRK.B → BRKB if applicable)
- Check FMP API directly to verify data availability

### Step 4: Expected Behavior by Company Type

#### **Mature, Profitable Companies** (e.g., AAPL, MSFT, JPM)
**Should see:**
- ✓ DCF: Value calculated
- ✓ Forward Multiple: Value calculated
- Fair Value with upside/downside %

**If not:**
- Review debug messages
- File an issue with the specific ticker

#### **High-Growth, Unprofitable Companies** (e.g., recent tech IPOs)
**May see:**
- ✗ DCF: Negative cash flow (expected)
- ✗ Forward Multiple: Negative EBIT (expected)

**This is normal!** These companies require different valuation methods (revenue multiples, TAM analysis, etc.) not yet implemented.

#### **Early-Stage or Loss-Making Companies**
**Will see:**
- Multiple ✗ errors

**This is expected** - traditional valuation doesn't apply to these companies.

## Backend Logging

If you have access to application logs, look for these patterns:

### Successful Calculation
```
INFO: DCF: Fetching financials for AAPL
INFO: DCF: Got income=2 statements, balance=1, cashflow=2
INFO: DCF: AAPL shares from balance sheet: 15,123,456,789
INFO: DCF: AAPL OCF=104,000,000,000, capex=10,500,000,000, revenue=394,000,000,000
INFO: DCF: AAPL revenue_growth=7.79%, maintenance_capex=7,350,000,000 (70% of total)
INFO: DCF: AAPL calculated base_cf=96,650,000,000 for non_financial
INFO: DCF: AAPL ev=2,123,456,789,012, net_debt=-45,678,901,234, equity_value=2,169,135,690,246, shares=15,123,456,789, value_per_share=$143.45
INFO: DCF: ✓ Final result for AAPL: $143.45
```

### Failed Calculation (Negative FCF)
```
WARNING: UBER DCF: Base cash flow <= 0 (got -1,234,567,890). Company may have negative FCF or losses.
```

### Failed Calculation (Missing Data)
```
WARNING: NEWCO DCF: Missing financials for NEWCO - income:True, balance:True, cashflow:False
```

## Reporting Issues

If you find a mature, profitable company where calculations fail unexpectedly:

1. **Collect Information:**
   - Ticker symbol
   - Company type (non_financial, financial, reit)
   - All error messages from "📋 Calculation Details & Debug Info"
   - Current price shown

2. **Check Manually:**
   - Go to https://financialmodelingprep.com/
   - Verify data is available for the company
   - Check if financial statements exist

3. **File Issue:**
   - Create GitHub issue with title: "Intrinsic value N/A for [TICKER]"
   - Include all information from step 1
   - Add FMP data check results from step 2

## Technical Details

### Calculation Flow

```
1. Get current price from profile endpoint
   └─ Try: price, lastPrice, regularMarketPrice

2. DCF Calculation:
   ├─ Get financials (income, balance, cashflow)
   ├─ Get shares outstanding
   ├─ Calculate base cash flow:
   │  ├─ Non-financial: OCF - Maintenance Capex
   │  ├─ Financial: Net Income
   │  └─ REIT: FFO - Maintenance Capex
   ├─ Estimate growth rate (from revenue)
   ├─ Project 5-year cash flows
   ├─ Calculate terminal value
   └─ Convert to per-share value

3. Forward Multiple:
   ├─ Get financials
   ├─ Get shares outstanding
   ├─ Calculate current EBIT:
   │  ├─ Try: EBITDA - D&A (from cashflow)
   │  └─ Fallback: operatingIncome
   ├─ Project forward EBIT
   ├─ Apply peer/sector multiple
   └─ Convert to per-share value

4. Historical Multiple:
   └─ Same as Forward Multiple but uses historical average multiples

5. Weighted Average:
   ├─ Weight varies by industry profile
   ├─ DCF: 30-50% (higher for stable companies)
   └─ Multiples: 50-70%
```

### Key Data Fields

#### From Profile Endpoint
- `price` or `lastPrice` or `regularMarketPrice` → Current Price
- `sharesOutstanding` → Fallback for shares

#### From Income Statement
- `revenue` → Growth calculation
- `ebitda` or `EBITDA` → EBIT calculation
- `operatingIncome` → EBIT fallback
- `netIncome` → For financials

#### From Balance Sheet
- `weightedAverageShsOut` or `commonStockSharesOutstanding` → Shares
- `totalDebt` → Net debt calculation
- `cashAndCashEquivalents` → Net debt calculation

#### From Cash Flow
- `operatingCashFlow` → FCF calculation
- `capitalExpenditure` → FCF calculation
- `depreciationAndAmortization` → EBIT calculation (PRIMARY SOURCE)

### Why D&A Location Matters

**Before fix:**
```python
ebit = income[0].get('ebitda', 0) - abs(income[0].get('depreciationAndAmortization', 0))
# ❌ depreciationAndAmortization not in income statement → D&A = 0 → EBIT wrong
```

**After fix:**
```python
# Try cash flow first (correct location)
da = abs(cashflow[0].get('depreciationAndAmortization', 0))
if not da:
    # Fallback to income statement
    da = abs(income[0].get('depreciationAndAmortization', 0))

if ebitda and da:
    ebit = ebitda - da
else:
    # Use operatingIncome directly (this IS EBIT)
    ebit = income[0].get('operatingIncome') or 0
```

## Version History

- **v1.0** (Initial): Basic calculations, minimal error handling
- **v2.0** (EBIT Fix): Fixed D&A location issue, added operatingIncome fallback
- **v3.0** (Diagnostics): Comprehensive logging, UI improvements, detailed error messages

## Additional Resources

- [FMP API Documentation](https://financialmodelingprep.com/developer/docs/)
- [Damodaran Valuation Research](http://pages.stern.nyu.edu/~adamodar/)
- [DCF Valuation Guide](https://corporatefinanceinstitute.com/resources/valuation/dcf-formula-guide/)
