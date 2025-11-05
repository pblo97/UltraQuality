# FMP Endpoints Reference

Complete reference of Financial Modeling Prep (FMP) endpoints used in UltraQuality screener.

## Universe & Classification

### Profile (Bulk)

**Endpoint**: `GET /stable/profile-bulk?part={n}&apikey={key}`

**Purpose**: Fetch company profiles in bulk (paginated)

**Response Fields**:
```json
{
  "symbol": "AAPL",
  "companyName": "Apple Inc.",
  "country": "US",
  "exchangeShortName": "NASDAQ",
  "sector": "Technology",
  "industry": "Consumer Electronics",
  "mktCap": 2800000000000,
  "price": 175.43,
  "volAvg": 52341234,
  "beta": 1.23,
  "description": "...",
  "currency": "USD"
}
```

**Usage**: Stage 1 (Universe)

---

### Profile (Single)

**Endpoint**: `GET /stable/profile/{symbol}?apikey={key}`

**Purpose**: Single company profile

**Usage**: Qualitative analysis

---

## Financial Statements

### Income Statement

**Endpoint**: `GET /stable/income-statement/{symbol}?period={quarter|annual}&limit={n}&apikey={key}`

**Response Fields**:
```json
{
  "date": "2024-09-30",
  "period": "Q3",
  "revenue": 94930000000,
  "costOfRevenue": 52310000000,
  "grossProfit": 42620000000,
  "operatingIncome": 29350000000,
  "ebitda": 33210000000,
  "netIncome": 23980000000,
  "interestExpense": 780000000,
  "incomeTaxExpense": 4320000000,
  "incomeBeforeTax": 28300000000
}
```

**Usage**:
- EBIT (operatingIncome)
- EBITDA
- Tax rate calculation
- Gross margin
- Net income

---

### Balance Sheet

**Endpoint**: `GET /stable/balance-sheet-statement/{symbol}?period={quarter|annual}&limit={n}&apikey={key}`

**Response Fields**:
```json
{
  "date": "2024-09-30",
  "totalAssets": 365725000000,
  "totalCurrentAssets": 135406000000,
  "cashAndCashEquivalents": 28994000000,
  "netReceivables": 28470000000,
  "propertyPlantEquipmentNet": 42117000000,
  "goodwill": 0,
  "intangibleAssets": 0,
  "totalLiabilities": 279414000000,
  "totalCurrentLiabilities": 133973000000,
  "totalDebt": 106628000000,
  "shortTermDebt": 10938000000,
  "totalStockholdersEquity": 86311000000,
  "retainedEarnings": -214000000,
  "commonStock": 77287000000
}
```

**Usage**:
- NOA calculation (Operating Assets - Operating Liabilities)
- Working capital
- Debt levels
- Altman Z-Score components
- Accruals calculation

---

### Cash Flow Statement

**Endpoint**: `GET /stable/cash-flow-statement/{symbol}?period={quarter|annual}&limit={n}&apikey={key}`

**Response Fields**:
```json
{
  "date": "2024-09-30",
  "operatingCashFlow": 31477000000,
  "capitalExpenditure": -2447000000,
  "freeCashFlow": 29030000000,
  "dividendsPaid": -3740000000,
  "commonStockRepurchased": -22463000000,
  "commonStockIssued": 1280000000,
  "depreciationAndAmortization": 3160000000
}
```

**Usage**:
- FCF (Free Cash Flow)
- Shareholder yield (dividends + buybacks - issuance)
- FFO calculation (for REITs)
- CFO/NI ratio
- Dilution tracking

---

## Ratios & Metrics

### Key Metrics (TTM)

**Endpoint**: `GET /stable/key-metrics-ttm/{symbol}?apikey={key}`

**Response Fields**:
```json
{
  "symbol": "AAPL",
  "marketCapTTM": 2780000000000,
  "peRatioTTM": 29.45,
  "pbRatioTTM": 32.17,
  "roeTTM": 1.478,
  "roicTTM": 0.523,
  "debtToEquityTTM": 1.97,
  "currentRatioTTM": 1.01,
  "quickRatioTTM": 0.85
}
```

**Usage**: Quick access to common ratios

---

### Ratios (TTM)

**Endpoint**: `GET /stable/ratios-ttm/{symbol}?apikey={key}`

**Response Fields**:
```json
{
  "dividendYieldTTM": 0.0045,
  "priceEarningsRatioTTM": 29.45,
  "priceToBookRatioTTM": 32.17,
  "returnOnAssetsTTM": 0.2213,
  "returnOnEquityTTM": 1.478,
  "debtToAssetsTTM": 0.2915,
  "interestCoverageTTM": 37.6
}
```

**Usage**: Additional ratio coverage

---

### Enterprise Values

**Endpoint**: `GET /stable/enterprise-values/{symbol}?period={quarter|annual}&limit={n}&apikey={key}`

**Response Fields**:
```json
{
  "date": "2024-09-30",
  "symbol": "AAPL",
  "stockPrice": 175.43,
  "numberOfShares": 15850442000,
  "marketCapitalization": 2780000000000,
  "enterpriseValue": 2857000000000,
  "evToSales": 7.12,
  "evToEbitda": 22.5,
  "evToOperatingCashFlow": 19.8,
  "evToFreeCashFlow": 23.4
}
```

**Usage**: EV multiples (EV/EBIT, EV/FCF)

---

## Accounting Quality

### Financial Scores

**Endpoint**: `GET /stable/financial-scores/{symbol}?apikey={key}`

**Response Fields**:
```json
{
  "symbol": "AAPL",
  "altmanZScore": 7.32,
  "piotroskiScore": 8,
  "workingCapital": 1433000000,
  "totalAssets": 365725000000,
  "retainedEarnings": -214000000,
  "ebit": 117155000000
}
```

**Usage**:
- Altman Z (pre-calculated, or calculate locally)
- Piotroski score (optional)

**Note**: May not be available in all FMP plans; calculate locally if needed.

---

## Qualitative Data

### Stock News

**Endpoint**: `GET /stable/stock-news?tickers={symbol}&limit={n}&apikey={key}`

**Response Fields**:
```json
{
  "symbol": "AAPL",
  "publishedDate": "2024-01-15T08:30:00.000Z",
  "title": "Apple Announces New iPhone Models",
  "image": "https://...",
  "site": "Reuters",
  "text": "Apple Inc announced...",
  "url": "https://..."
}
```

**Usage**: Recent news for qualitative analysis

---

### Press Releases

**Endpoint**: `GET /stable/press-releases/{symbol}?limit={n}&apikey={key}`

**Response Fields**:
```json
{
  "symbol": "AAPL",
  "date": "2024-01-15T16:00:00.000Z",
  "title": "Apple Reports First Quarter Results",
  "text": "Apple today announced financial results...",
  "url": "https://..."
}
```

**Usage**: Official company announcements

---

### Earnings Call Transcripts

**Endpoint**: `GET /stable/earnings-call-transcripts/{symbol}?apikey={key}`

**Response Fields**:
```json
{
  "symbol": "AAPL",
  "quarter": 1,
  "year": 2024,
  "date": "2024-02-01 16:30:00",
  "content": "Operator: Good day, and thank you for standing by..."
}
```

**Usage**: Extract highlights, risks, outlook from latest call

---

### Stock Peers

**Endpoint**: `GET /stable/stock-peers/{symbol}?apikey={key}`

**Response Fields**:
```json
{
  "symbol": "AAPL",
  "peersList": ["MSFT", "GOOG", "AMZN", "META", "NVDA"]
}
```

**Usage**: Peer comparison

---

### Revenue Segmentation

**Product Segmentation**: `GET /stable/revenue-product-segmentation/{symbol}?apikey={key}`

**Geographic Segmentation**: `GET /stable/revenue-geographic-segmentation/{symbol}?apikey={key}`

**Usage**: Moat analysis (concentration risk, geographic diversification)

---

## Historical Data

### Shares Float

**Endpoint**: `GET /api/v4/shares_float?symbol={symbol}&apikey={key}`

**Response Fields**:
```json
{
  "symbol": "AAPL",
  "date": "2024-01-15",
  "freeFloat": 15850000000,
  "floatShares": 15850000000,
  "outstandingShares": 15850442000,
  "source": "..."
}
```

**Usage**:
- Free float calculation
- Share dilution tracking (compare over time)

---

## Bulk Endpoints (Recommended)

### Key Metrics (Bulk)

**Endpoint**: `GET /stable/key-metrics-ttm-bulk?apikey={key}`

**Returns**: All companies' key metrics in single request

**Advantage**: Fetch Top-K metrics in one call vs K individual calls

---

### Ratios (Bulk)

**Endpoint**: `GET /stable/ratios-ttm-bulk?apikey={key}`

**Advantage**: Same as key-metrics-ttm-bulk

---

### Peers (Bulk)

**Endpoint**: `GET /stable/peers-bulk?apikey={key}`

**Advantage**: Pre-fetch all peer relationships

---

## Rate Limits & Best Practices

### API Limits (by Plan)

| Plan | Requests/min | Requests/day |
|------|-------------|--------------|
| Free | 250 | 250 |
| Starter | 300 | 10,000 |
| Professional | 750 | 100,000 |
| Enterprise | Custom | Custom |

### Optimization Strategies

1. **Use Bulk Endpoints**: Reduces round-trips by ~95%
2. **Cache Aggressively**:
   - Universe: 12h
   - Symbol data: 48h
   - Qualitative: 24h
3. **Top-K Strategy**: Only deep-dive on 150 symbols
4. **Rate Limiting**: 8 req/s with jitter (stays under limits)
5. **Exponential Backoff**: 2s → 4s → 8s on failures

### Endpoint Priority

**High-Priority** (always use bulk):
- `profile-bulk`
- `key-metrics-ttm-bulk`
- `ratios-ttm-bulk`

**Medium-Priority** (bulk if available):
- `income-statement`
- `balance-sheet-statement`
- `cash-flow-statement`

**Low-Priority** (on-demand only):
- `stock-news`
- `press-releases`
- `earnings-call-transcripts`

---

## Example API Calls

### Test Connection

```bash
curl "https://financialmodelingprep.com/api/v3/profile/AAPL?apikey=YOUR_KEY"
```

### Fetch Universe (First Page)

```bash
curl "https://financialmodelingprep.com/api/v3/profile-bulk?part=0&apikey=YOUR_KEY"
```

### Fetch TTM Ratios

```bash
curl "https://financialmodelingprep.com/api/v3/ratios-ttm/AAPL?apikey=YOUR_KEY"
```

### Fetch Income Statement (Quarterly, Last 4)

```bash
curl "https://financialmodelingprep.com/api/v3/income-statement/AAPL?period=quarter&limit=4&apikey=YOUR_KEY"
```

---

## Error Handling

### Common Errors

| HTTP Code | Meaning | Solution |
|-----------|---------|----------|
| 401 | Invalid API key | Check FMP_API_KEY env var |
| 403 | Plan limit exceeded | Upgrade plan or reduce requests |
| 404 | Symbol not found | Verify symbol is correct |
| 429 | Rate limit hit | Implement backoff (already done) |
| 500 | FMP server error | Retry after delay |

### Error Response Format

```json
{
  "Error Message": "Invalid API KEY. Please retry or visit our documentation to create one."
}
```

**Handling in Code**:
```python
response = requests.get(url)
data = response.json()

if isinstance(data, dict) and 'Error Message' in data:
    raise Exception(f"FMP API Error: {data['Error Message']}")
```

---

## Additional Resources

- **FMP Documentation**: https://site.financialmodelingprep.com/developer/docs
- **API Playground**: https://site.financialmodelingprep.com/developer/docs/playground
- **Pricing**: https://financialmodelingprep.com/developer/docs/pricing
- **Support**: support@financialmodelingprep.com

---

**Note**: Endpoint URLs may change. Always refer to the official FMP documentation for the latest endpoint specifications.
