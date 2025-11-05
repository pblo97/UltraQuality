# UltraQuality: Quality + Value Investment Screener

A comprehensive Python-based investment screening pipeline that combines **Quality** and **Value** metrics to identify attractive investment opportunities. Uses Financial Modeling Prep (FMP) as the data source.

## Features

### 🎯 Core Capabilities

- **Multi-Asset Type Support**: Handles non-financials, financials (banks, insurance), and REITs with type-specific metrics
- **Accounting Quality Guardrails**: Altman Z-Score, Beneish M-Score, accruals analysis, dilution tracking
- **Industry-Normalized Scoring**: Z-score normalization by industry for fair comparisons
- **Efficient API Usage**: Bulk endpoints, aggressive caching (24-72h), rate limiting (8-10 req/s)
- **On-Demand Qualitative Analysis**: Deep-dive analysis for selected symbols (business summary, moats, insider activity, transcript summaries, news/PR, M&A)

### 📊 Metrics Calculated

#### Non-Financials (Manufacturing, Tech, Services, Consumer)

**Value Metrics:**
- EV/EBIT (TTM)
- EV/FCF (TTM)
- P/E (TTM)
- P/B (TTM)
- Shareholder Yield % (dividends + buybacks - issuance)

**Quality Metrics:**
- ROIC % (Return on Invested Capital = NOPAT / NOA)
- ROIC Persistence (std dev over 4 quarters)
- Gross Profits / Assets (Novy-Marx)
- FCF Margin %
- CFO / Net Income
- Net Debt / EBITDA
- Interest Coverage
- Fixed Charge Coverage

#### Financials (Banks, Insurance, Asset Management)

**Value Metrics:**
- P/E (TTM)
- P/B (TTM)
- P / Tangible Book
- Dividend Yield %

**Quality Metrics:**
- ROA %
- ROE %
- Efficiency Ratio (Operating Expenses / Revenue)
- Net Interest Margin % (banks)
- Combined Ratio % (insurance)
- CET1 / Leverage Ratio %
- Loans to Deposits

#### REITs

**Value Metrics:**
- P/FFO (Funds From Operations)
- P/AFFO (Adjusted FFO)
- Dividend Yield %

**Quality Metrics:**
- FFO Payout %
- AFFO Payout %
- Same-Store NOI Growth %
- Occupancy %
- Net Debt / EBITDA (RE-adjusted)
- Debt to Gross Assets %
- Secured Debt %

#### Guardrails (All Types)

- **Altman Z-Score**: Bankruptcy risk (non-financials only)
- **Beneish M-Score**: Earnings manipulation detection
- **Accruals / NOA**: Earnings quality (Sloan 1996)
- **Net Share Issuance**: Dilution tracking (12m %)
- **M&A Flag**: Stock-financed acquisitions + goodwill growth
- **Debt Maturity**: % maturing < 24 months (if available)
- **Rate Mix**: Variable rate debt % (if available)

## Installation

### Requirements

- Python 3.9+
- FMP API Key (get one at [financialmodelingprep.com](https://financialmodelingprep.com))

### Setup

```bash
# Clone repository
git clone <repo-url>
cd UltraQuality

# Install dependencies
pip install -r requirements.txt

# Set API key
export FMP_API_KEY="your_api_key_here"

# Or create .env file
echo "FMP_API_KEY=your_api_key_here" > .env
```

## Usage

### 1. Basic Screening (Full Pipeline)

```bash
# Run full screening pipeline
python src/screener/orchestrator.py

# Or with custom config
python src/screener/orchestrator.py --config my_config.yaml
```

**Output**: CSV file at `./data/screener_results.csv` with all metrics and scores.

### 2. Configuration

Edit `settings.yaml` to customize:

```yaml
universe:
  countries: ["US"]
  exchanges: ["NYSE", "NASDAQ"]
  min_market_cap: 500_000_000  # $500M
  min_avg_dollar_vol_3m: 5_000_000  # $5M daily
  top_k: 150  # Deep-dive on top 150

scoring:
  weight_value: 0.5
  weight_quality: 0.5
  exclude_reds: true  # Exclude ROJO guardrails
  threshold_buy: 75
  threshold_monitor: 60

cache:
  ttl_universe_hours: 12
  ttl_symbol_hours: 48
  ttl_qualitative_hours: 24
```

### 3. On-Demand Qualitative Analysis

After screening, dive deep into specific symbols:

```bash
# Run qualitative analysis for a symbol
python src/screener/orchestrator.py --qualitative AAPL
```

**Output**: JSON with:
- Business summary (what they do, how they make money)
- Competitive position vs peers
- Moats assessment (switching costs, network effects, brand/IP, scale, regulatory)
- Skin in the game (insider activity, dilution)
- News & press release summaries
- Latest earnings transcript TL;DR
- Recent M&A activity
- Top 3 risks (probability × severity)

### 4. Programmatic Usage

```python
from src.screener.orchestrator import ScreenerPipeline

# Initialize pipeline
pipeline = ScreenerPipeline('settings.yaml')

# Run full screening
output_csv = pipeline.run()
print(f"Results: {output_csv}")

# On-demand qualitative analysis
qual_summary = pipeline.get_qualitative_analysis('MSFT')
print(qual_summary['business_summary'])
print(qual_summary['moats'])
print(qual_summary['top_risks'])
```

## Pipeline Architecture

### Stage 1: Screener (Universe)

- Fetches profiles using `profile-bulk` (paginated)
- Classifies companies: non_financial / financial / REIT / utility
- Filters by country, exchange, market cap, volume
- **Endpoints**: `profile-bulk`, `sectors-list`, `industries-list`

### Stage 2: Preliminary Ranking (Top-K)

- Quick ranking to select Top-K for deep analysis
- Avoids fetching full data for entire universe
- Heuristic: market cap rank (or basic P/E if available)

### Stage 3: Features (Value & Quality)

- Fetches financial statements, ratios, metrics for Top-K
- Calculates type-specific metrics (see Metrics section)
- **Endpoints**: `income-statement`, `balance-sheet-statement`, `cash-flow-statement`, `key-metrics-ttm`, `ratios-ttm`, `enterprise-values`

### Stage 4: Guardrails (Accounting Quality)

- Altman Z-Score (non-financials)
- Beneish M-Score (all)
- Accruals / NOA (non-financials)
- Net share issuance (all)
- M&A flag (all)
- **Endpoints**: Uses data from Stage 3, `financial-scores` (optional)

### Stage 5: Scoring & Normalization

- Normalize metrics by industry (robust z-scores)
- Calculate Value Score (0-100)
- Calculate Quality Score (0-100)
- Composite Score (weighted average)
- Decision logic: BUY / MONITOR / AVOID

### Stage 6: Export

- Single CSV with all columns (see Output Format)
- Metrics log (JSON) with request counts, cache stats, latencies

## Output Format

CSV columns (one row per ticker):

```
ticker, name, country, exchange, sector, industry, marketCap, avgDollarVol_3m, freeFloat,
is_financial, is_REIT, is_utility,

# Value (non-fin)
ev_ebit_ttm, ev_fcf_ttm, pe_ttm, pb_ttm, shareholder_yield_%,

# Value (fin)
p_tangibleBook,

# Value (REIT)
p_ffo, p_affo,

# Quality (non-fin)
roic_%, roic_persistence, grossProfits_to_assets, fcf_margin_%, cfo_to_ni,
netDebt_ebitda, interestCoverage, fixedChargeCoverage,

# Quality (fin)
roa_%, roe_%, efficiency_ratio, nim_%, combined_ratio_%,
cet1_or_leverage_ratio_%, loans_to_deposits,

# Quality (REIT)
ffo_payout_%, affo_payout_%, sameStoreNOI_growth_%, occupancy_%,
netDebt_ebitda_re, debt_to_grossAssets_%, securedDebt_%,

# Guardrails
altmanZ, beneishM, accruals_noa_%, netShareIssuance_12m_%,
mna_flag, debt_maturity_<24m_%, rate_mix_variable_%,
guardrail_status, guardrail_reasons,

# Scores & decision
value_score_0_100, quality_score_0_100, composite_0_100, decision, notes_short
```

## Testing

Run unit tests:

```bash
# All tests
pytest

# Specific module
pytest tests/test_guardrails.py
pytest tests/test_features.py

# With coverage
pytest --cov=src/screener --cov-report=html
```

## Performance & Optimization

### API Call Minimization

- **Bulk endpoints** for universe and Top-K ratios
- **Caching**: 12h for universe, 48h for symbol data, 24h for qualitative
- **Top-K strategy**: Only deep-dive on 150 symbols (not entire universe)
- **On-demand qualitative**: Only when user selects a symbol

### Rate Limiting

- Configured at 8-10 req/s (configurable)
- Token bucket algorithm with jitter
- Exponential backoff on failures (2s, 4s, 8s)

### Data Quality

- Computes % non-NA fields per symbol
- Flags incomplete data in guardrail_reasons
- Fail-soft: returns partial results if some metrics missing

## Formulas & Methodology

### ROIC (Return on Invested Capital)

```
ROIC = NOPAT / NOA

Where:
  NOPAT = EBIT × (1 - Tax Rate)
  NOA = Operating Assets - Operating Liabilities
      = Total Assets - Cash - (Total Liabilities - Total Debt)
```

### Altman Z-Score (Public Manufacturing)

```
Z = 1.2×X1 + 1.4×X2 + 3.3×X3 + 0.6×X4 + 1.0×X5

Where:
  X1 = Working Capital / Total Assets
  X2 = Retained Earnings / Total Assets
  X3 = EBIT / Total Assets
  X4 = Market Value Equity / Total Liabilities
  X5 = Sales / Total Assets

Interpretation:
  Z > 2.99: Safe
  1.81 - 2.99: Gray zone
  Z < 1.81: Distress
```

### Beneish M-Score

```
M = -4.84 + 0.920×DSRI + 0.528×GMI + 0.404×AQI + 0.892×SGI
    + 0.115×DEPI - 0.172×SGAI + 4.679×TATA - 0.327×LVGI

Interpretation:
  M > -1.78: High manipulation likelihood (RED)
  M < -2.22: Low likelihood (VERDE)
```

### Accruals / NOA (Sloan 1996)

```
Accruals = ΔCA - ΔCash - ΔCL + ΔSTD + ΔTP - Depreciation
Accruals % = Accruals / NOA × 100

High accruals (> p80 in industry) = lower earnings quality
```

### FFO & AFFO (REITs)

```
FFO = Net Income + Depreciation & Amortization - Gains on Property Sales
AFFO = FFO - Maintenance Capex ± Other Adjustments

P/FFO = Market Cap / FFO
P/AFFO = Market Cap / AFFO
```

## FMP Endpoints Used

| Stage | Endpoint | Purpose |
|-------|----------|---------|
| Screener | `profile-bulk` | Company profiles (sector, industry, cap) |
| Screener | `sectors-list`, `industries-list` | Taxonomy validation |
| Features | `income-statement`, `balance-sheet-statement`, `cash-flow-statement` | Financial statements (quarterly) |
| Features | `key-metrics-ttm`, `ratios-ttm` | Ratios and metrics (TTM) |
| Features | `enterprise-values` | EV calculations |
| Guardrails | `financial-scores` | Altman Z, Piotroski (optional) |
| Guardrails | `shares_float` | Share count history |
| Qualitative | `stock-peers`, `peers-bulk` | Peer comparisons |
| Qualitative | `stock-news`, `press-releases` | Recent news & PR |
| Qualitative | `earnings-call-transcripts` | Latest earnings transcript |
| Qualitative | `revenue-product-segmentation`, `revenue-geographic-segmentation` | Segment data for moat analysis |
| Qualitative | `mergers-acquisitions-latest` | Recent M&A activity |

## Contributing

Contributions welcome! Areas for improvement:

- [ ] Add more REIT-specific metrics (same-store NOI, occupancy) when FMP exposes them
- [ ] Integrate LLM for better qualitative summaries (moats, risks, transcript TL;DR)
- [ ] Add support for international markets (adjust Z-Score coefficients)
- [ ] Implement debt maturity & rate mix analysis (requires footnote parsing)
- [ ] Create interactive web UI for qualitative analysis

## License

MIT License - see LICENSE file

## Disclaimer

**This tool is for educational and research purposes only.** It is NOT investment advice. Always conduct your own due diligence and consult with a qualified financial advisor before making investment decisions.

The calculations and scores are based on heuristics and may not capture all nuances of a company's financial health. Use at your own risk.

## Acknowledgments

Built with:
- [Financial Modeling Prep API](https://financialmodelingprep.com)
- Methodologies from Sloan (1996), Altman (1968), Beneish (1999), Novy-Marx (2013)

---

**Questions?** Open an issue or contact the maintainer.
