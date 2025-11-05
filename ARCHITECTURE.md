# UltraQuality Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     UltraQuality Screener                       │
│                  Quality + Value Investment Pipeline             │
└─────────────────────────────────────────────────────────────────┘

┌─────────────┐
│   Config    │  settings.yaml (universe filters, weights, thresholds)
│  & Settings │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│                      ORCHESTRATOR                                │
│                  (orchestrator.py)                               │
│                                                                   │
│  Stage 1: Screener → Stage 2: Top-K → Stage 3: Features         │
│  Stage 4: Guardrails → Stage 5: Scoring → Stage 6: Export       │
└───────────────────────┬──────────────────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        ▼                               ▼
┌──────────────┐                ┌──────────────┐
│   INGEST     │                │  QUALITATIVE │
│  (FMP API)   │                │  (on-demand) │
│              │                │              │
│ • Rate Limit │                │ • News/PR    │
│ • Caching    │                │ • Transcripts│
│ • Retries    │                │ • Moats      │
└──────┬───────┘                │ • Risks      │
       │                        └──────────────┘
       │
       ├─────────────────┬─────────────────┬──────────────────┐
       ▼                 ▼                 ▼                  ▼
┌────────────┐    ┌────────────┐   ┌────────────┐   ┌──────────────┐
│  FEATURES  │    │ GUARDRAILS │   │  SCORING   │   │   EXPORT     │
│            │    │            │   │            │   │              │
│ • ROIC     │    │ • Altman Z │   │ • Industry │   │ • CSV        │
│ • EV/EBIT  │    │ • Beneish M│   │   Normalize│   │ • Metrics Log│
│ • ROA/ROE  │    │ • Accruals │   │ • Value    │   │              │
│ • FFO/AFFO │    │ • Dilution │   │   Score    │   │              │
│            │    │ • M&A Flag │   │ • Quality  │   │              │
│            │    │            │   │   Score    │   │              │
└────────────┘    └────────────┘   └────────────┘   └──────────────┘
```

## Module Breakdown

### 1. `ingest.py` - FMP API Client

**Responsibilities:**
- HTTP requests to FMP API
- Rate limiting (token bucket with jitter)
- Multi-tier caching (universe, symbol, qualitative)
- Exponential backoff on failures
- Request metrics tracking

**Key Classes:**
- `FMPClient`: Main client with endpoint wrappers
- `RateLimiter`: Token bucket algorithm
- `FMPCache`: File-based cache with TTL

**Endpoints Used:**
```python
# Universe
get_stock_screener()
get_profile_bulk(symbols)

# Financial Statements
get_income_statement(symbol, period='quarter')
get_balance_sheet(symbol, period='quarter')
get_cash_flow(symbol, period='quarter')

# Ratios & Metrics
get_key_metrics_ttm(symbol)
get_ratios_ttm(symbol)
get_enterprise_values(symbol)

# Qualitative
get_stock_news(symbol)
get_press_releases(symbol)
get_earnings_call_transcript(symbol)
get_stock_peers(symbol)
```

### 2. `features.py` - Metric Calculation

**Responsibilities:**
- Calculate Value metrics (valuation multiples, yields)
- Calculate Quality metrics (profitability, efficiency, leverage)
- Handle three company types: non_financial, financial, reit

**Key Formulas:**

#### ROIC (Non-Financials)
```python
tax_rate = income_tax_expense / income_before_tax
nopat = ebit_ttm * (1 - tax_rate)

noa = (total_assets - cash) - (total_liabilities - total_debt)

roic = (nopat / noa) * 100
```

#### Shareholder Yield
```python
dividends = abs(dividends_paid)
buybacks = abs(stock_repurchased)
issuance = stock_issued

shareholder_yield = (dividends + buybacks - issuance) / market_cap * 100
```

#### FFO (REITs)
```python
ffo = net_income + depreciation - gains_on_sales
affo = ffo - maintenance_capex

p_ffo = market_cap / ffo
```

### 3. `guardrails.py` - Accounting Quality

**Responsibilities:**
- Detect bankruptcy risk (Altman Z)
- Detect earnings manipulation (Beneish M)
- Assess earnings quality (Accruals)
- Track dilution (net share issuance)
- Flag M&A activity

**Key Formulas:**

#### Altman Z-Score
```python
x1 = (current_assets - current_liabilities) / total_assets
x2 = retained_earnings / total_assets
x3 = ebit / total_assets
x4 = market_value_equity / total_liabilities
x5 = sales / total_assets

z_score = 1.2*x1 + 1.4*x2 + 3.3*x3 + 0.6*x4 + 1.0*x5

# Z > 2.99: Safe
# 1.81 - 2.99: Gray zone
# Z < 1.81: Distress
```

#### Beneish M-Score
```python
dsri = (receivables_t / sales_t) / (receivables_t1 / sales_t1)
gmi = gross_margin_t1 / gross_margin_t
aqi = asset_quality_t / asset_quality_t1
sgi = sales_t / sales_t1
# ... (8 indices total)

m_score = -4.84 + 0.920*dsri + 0.528*gmi + 0.404*aqi + ...

# M > -1.78: High manipulation risk
# M < -2.22: Low risk
```

#### Accruals / NOA
```python
accruals = (
    delta_current_assets
    - delta_cash
    - delta_current_liabilities
    + delta_short_term_debt
    + delta_tax_payable
    - depreciation
)

noa = (total_assets - cash) - (total_liabilities - total_debt)

accruals_pct = (accruals / noa) * 100

# High accruals (>p80) = lower earnings quality
```

### 4. `scoring.py` - Normalization & Ranking

**Responsibilities:**
- Normalize metrics by industry (z-scores)
- Calculate Value Score (0-100)
- Calculate Quality Score (0-100)
- Composite Score (weighted average)
- Decision logic (BUY / MONITOR / AVOID)

**Normalization:**
```python
# Robust z-score (uses median + MAD for outliers)
median = series.median()
mad = np.median(np.abs(series - median))

z_score = (value - median) / (1.4826 * mad)

# Convert to percentile (0-100)
percentile = norm.cdf(z_score) * 100
```

**Scoring:**
```python
# Average z-scores across valid metrics
value_score = mean(value_metrics_zscores) → percentile (0-100)
quality_score = mean(quality_metrics_zscores) → percentile (0-100)

composite = w_value * value_score + w_quality * quality_score

# Decision logic
if composite >= 75 and guardrail == 'VERDE':
    decision = 'BUY'
elif composite >= 60 or guardrail == 'AMBAR':
    decision = 'MONITOR'
else:
    decision = 'AVOID'
```

### 5. `qualitative.py` - Deep-Dive Analysis

**Responsibilities:**
- Business description (what they do, how they make money)
- Peer comparison
- Moats assessment (5 types)
- Insider activity & dilution
- News/PR summaries
- Earnings transcript TL;DR
- Risk synthesis

**Moats Checklist:**
1. **Switching Costs**: Subscription, enterprise software, platform lock-in
2. **Network Effects**: Marketplace, social network, two-sided platform
3. **Brand/IP**: Brand recognition, patents, proprietary tech
4. **Scale/Efficiency**: Largest player, distribution advantage, manufacturing scale
5. **Regulatory Assets**: Licensed, regulated industry, barriers to entry

**Risk Assessment:**
```python
# Synthesize from multiple sources:
- Transcript risks (mentioned by management)
- News tags (litigation, regulatory, financing)
- Guardrail flags (high dilution, high accruals, etc.)

# Output: Top 3 risks with probability × severity
{
  'risk': 'Legal litigation in progress',
  'prob': 'High',
  'severity': 'Med',
  'trigger': 'Recent lawsuit filed'
}
```

### 6. `orchestrator.py` - Pipeline Coordinator

**Responsibilities:**
- Initialize all modules
- Execute 6-stage pipeline
- Handle errors gracefully
- Log metrics and timing
- Export results

**Pipeline Flow:**
```python
def run():
    # Stage 1: Build universe (filtered by market cap, volume)
    df_universe = _build_universe()  # 5000+ stocks

    # Stage 2: Select Top-K for deep analysis
    df_topk = _select_topk(df_universe)  # 150 stocks

    # Stage 3: Calculate features for Top-K
    df_features = _calculate_features(df_topk)

    # Stage 4: Calculate guardrails
    df_guardrails = _calculate_guardrails(df_features)

    # Stage 5: Score and rank
    df_scored = _score_universe(df_guardrails)

    # Stage 6: Export CSV
    output_csv = _export_results(df_scored)

    return output_csv
```

## Data Flow

```
┌──────────────┐
│  FMP API     │
│  (REST)      │
└──────┬───────┘
       │
       ▼
┌──────────────┐     ┌──────────────┐
│   Cache      │ ◄───┤ Rate Limiter │
│ (File-based) │     │ (Token Bucket│
└──────┬───────┘     └──────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│        Raw Data (JSON)               │
│  • Profiles (sector, industry, cap)  │
│  • Statements (IS, BS, CF)           │
│  • Ratios (P/E, P/B, ROE, etc.)      │
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│     Feature Calculation              │
│  • ROIC = f(EBIT, NOA)               │
│  • EV/EBIT = f(Market Cap, Debt)     │
│  • FFO = f(NI, Depreciation)         │
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│     Guardrails                       │
│  • Z-Score = f(Balance Sheet)        │
│  • M-Score = f(Time Series)          │
│  • Accruals = f(ΔBalance Sheet)      │
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│     Normalization (by Industry)      │
│  • Z-scores (robust, median + MAD)   │
│  • Percentiles (0-100)               │
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│     Scoring                          │
│  • Value Score (0-100)               │
│  • Quality Score (0-100)             │
│  • Composite (weighted avg)          │
│  • Decision (BUY/MONITOR/AVOID)      │
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│     Export                           │
│  • CSV (one row per ticker)          │
│  • Metrics Log (JSON)                │
└──────────────────────────────────────┘
```

## Performance Optimization

### 1. Top-K Strategy

Instead of analyzing all 5000+ stocks in depth:
1. Fetch profiles for entire universe (cheap)
2. Apply basic filters (market cap, volume)
3. Preliminary ranking (using simple heuristic)
4. Deep-dive on Top-K (default: 150)

**API Call Reduction**: ~95% fewer calls

### 2. Caching Strategy

Three cache tiers with different TTLs:

| Cache Type | TTL | Use Case |
|------------|-----|----------|
| Universe | 12h | Profiles, screener data |
| Symbol | 48h | Financial statements, ratios |
| Qualitative | 24h | News, transcripts, peers |

**Cache Hit Rate Target**: >80% on repeated runs

### 3. Bulk Endpoints

Use bulk endpoints where available:
- `profile-bulk` (paginated)
- `key-metrics-ttm-bulk`
- `ratios-ttm-bulk`
- `peers-bulk`

**Reduces**: Round-trips from O(N) to O(1)

### 4. Rate Limiting

Token bucket with jitter:
```python
rate = 8 req/s
interval = 1.0 / rate  # 125ms

# Add ±10% jitter to avoid thundering herd
jitter = interval * 0.1 * random()
sleep(interval + jitter)
```

### 5. Fail-Soft Strategy

If a metric fails to calculate:
- Log warning
- Set metric to `None`
- Continue with other metrics
- Flag in `guardrail_reasons`

**Result**: Partial results > no results

## Configuration

All tunable parameters in `settings.yaml`:

```yaml
universe:
  top_k: 150              # Deep-dive count
  min_market_cap: 500M
  min_avg_dollar_vol_3m: 5M

scoring:
  weight_value: 0.5       # Value vs Quality weight
  weight_quality: 0.5
  threshold_buy: 75       # Composite score threshold
  threshold_monitor: 60

guardrails:
  non_financial:
    altman_z_red: 1.8
    beneish_m_red: -1.78
    net_share_issuance_red_pct: 10.0

cache:
  ttl_universe_hours: 12
  ttl_symbol_hours: 48

fmp:
  rate_limit_rps: 8
  max_retries: 3
```

## Extending the System

### Adding a New Metric

1. **Add to `features.py`**:
```python
def _calc_new_metric(self, symbol: str) -> float:
    # Fetch data
    data = self.fmp.get_something(symbol)

    # Calculate
    metric = data['x'] / data['y']

    return metric
```

2. **Add to appropriate company type method**:
```python
def _calc_non_financial(self, symbol: str) -> Dict:
    # ... existing code ...
    features['new_metric'] = self._calc_new_metric(symbol)
    return features
```

3. **Add to scoring**:
```python
# In scoring.py
quality_metrics = ['roic_%', 'fcf_margin_%', 'new_metric']
```

4. **Add to CSV columns** (in `orchestrator.py`)

### Adding a New Company Type

Example: Utilities (separate from non-financials)

1. **Add classifier** in `orchestrator.py`:
```python
def _classify_utility(self, row) -> bool:
    return 'utilities' in row['sector'].lower()
```

2. **Add calc method** in `features.py`:
```python
def _calc_utility(self, symbol: str) -> Dict:
    # Utility-specific metrics (regulated ROE, rate base, etc.)
    pass
```

3. **Add scoring logic** in `scoring.py`:
```python
def _score_utilities(self, df: pd.DataFrame) -> pd.DataFrame:
    # Utility-specific normalization
    pass
```

## Error Handling

### API Failures
- Exponential backoff: 2s → 4s → 8s
- Max retries: 3
- Log error and continue (fail-soft)

### Missing Data
- Set metric to `None`
- Add note to `guardrail_reasons`
- Don't exclude symbol (unless >80% metrics missing)

### Invalid Calculations
- Catch division by zero
- Return `None` for that metric
- Log warning with symbol + metric name

## Testing Strategy

### Unit Tests
- Test each formula in isolation
- Mock FMP client responses
- Verify edge cases (zero, negative, missing)

### Integration Tests
- Test full pipeline with small universe
- Verify CSV output format
- Check cache behavior

### Performance Tests
- Measure API call count
- Verify cache hit rate
- Profile bottlenecks

## Deployment

### Requirements
- Python 3.9+
- 1GB RAM
- 500MB disk (for cache)
- FMP API key (paid plan recommended for bulk endpoints)

### Scaling
- **Horizontal**: Run multiple instances with different exchanges
- **Vertical**: Increase Top-K (requires more API quota)
- **Schedule**: Run daily after market close (cache refresh)

## Roadmap

- [ ] International markets (adjust Z-Score coefficients)
- [ ] Sector-specific metrics (e.g., banks: CET1, insurance: combined ratio)
- [ ] LLM integration for qualitative analysis
- [ ] Web UI for interactive exploration
- [ ] Backtesting framework (historical scores vs returns)
- [ ] Alert system (notify when new BUYs appear)
