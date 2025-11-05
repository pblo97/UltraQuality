# UltraQuality Usage Examples

## Basic Usage

### 1. First-Time Setup

```bash
# Clone repository
git clone <repo-url>
cd UltraQuality

# Install dependencies
pip install -r requirements.txt

# Configure API key
cp .env.example .env
nano .env  # Add your FMP API key

# Verify setup
python run_screener.py --help
```

### 2. Run Full Screening

```bash
# Run with default settings
python run_screener.py

# Output:
# ================================================================================
# UltraQuality Screener v1.0
# ================================================================================
#
# [Stage 1/6] Building universe...
# Total profiles fetched: 8542
# After country filter: 7231
# After market cap filter: 3421
# After volume filter: 2156
# Universe built: 2156 stocks
#
# [Stage 2/6] Selecting Top-K for deep analysis...
# Selected Top-150 stocks for deep analysis
#
# [Stage 3/6] Calculating features for Top-K...
# Features calculated for 150 stocks
#
# [Stage 4/6] Calculating guardrails...
# Guardrails calculated for 150 stocks
#
# [Stage 5/6] Scoring and normalization...
# Scoring complete
#   BUY: 12
#   MONITOR: 58
#   AVOID: 80
#
# [Stage 6/6] Exporting results...
# Results exported to ./data/screener_results.csv
#
# ================================================================================
# PIPELINE METRICS
# ================================================================================
# Total runtime: 287.3s
# Total API requests: 453
# Cached responses: 127
# Cache hit rate: 28.0%
#
# ✓ Screening complete. Results: ./data/screener_results.csv
```

### 3. Analyze Results

```bash
# View top BUY candidates
head -20 data/screener_results.csv | column -t -s,

# Or use spreadsheet software (Excel, Google Sheets)
# Sort by composite_0_100 descending
# Filter decision == 'BUY'
```

## Qualitative Analysis

### 4. Deep-Dive on Specific Symbol

```bash
# Analyze MSFT
python run_screener.py --symbol MSFT

# Output:
# ================================================================================
# QUALITATIVE ANALYSIS: MSFT
# ================================================================================
#
# Business Summary:
#   Microsoft Corporation develops, licenses, and supports software, services,
#   devices, and solutions worldwide. Products include Windows OS, Office suite,
#   Azure cloud platform, Xbox gaming, and LinkedIn. Primary revenue drivers:
#   cloud computing (Azure), productivity software (Office 365), and gaming.
#
# Peers: AAPL, GOOG, AMZN, META, ORCL
#
# Competitive Moats:
#   switching_costs: Yes
#   network_effects: Probable
#   brand_IP: Yes
#   scale_efficiency: Yes
#   regulatory_assets: No
#   Notes: 4 potential moats identified from business description.
#
# Skin in the Game:
#   Insider trend (90d): mixed
#   Net share issuance: -1.2%
#   Assessment: positive
#
# Recent News (Top 3):
#   1. Microsoft announces new Azure AI capabilities: Expansion into generative...
#   2. Q4 earnings beat expectations: Cloud revenue up 28% YoY, guidance raised...
#   3. DOJ investigates cloud licensing practices: Antitrust scrutiny on...
#
# Top Risks:
#   1. Regulatory scrutiny on cloud licensing practices
#      Probability: Med, Severity: Med
#      Trigger: DOJ investigation ongoing
#   2. AI competition intensifying (Google, Amazon, OpenAI)
#      Probability: High, Severity: Med
#      Trigger: Rapid AI model releases from competitors
#   3. Economic slowdown reducing IT spending
#      Probability: Med, Severity: High
#      Trigger: GDP growth < 2% or recession
```

### 5. Save Qualitative Analysis to File

```bash
# Save full analysis as JSON
python run_screener.py --symbol AAPL --output aapl_analysis.json

# View JSON
cat aapl_analysis.json | jq .

# Extract specific section
cat aapl_analysis.json | jq '.moats'
cat aapl_analysis.json | jq '.transcript_TLDR.highlights'
```

## Advanced Usage

### 6. Custom Configuration

Create `my_config.yaml`:

```yaml
universe:
  countries: ["US"]
  exchanges: ["NASDAQ"]  # Tech-heavy exchange
  min_market_cap: 2_000_000_000  # $2B min (mid-cap+)
  min_avg_dollar_vol_3m: 10_000_000  # $10M daily
  top_k: 100  # Analyze top 100

scoring:
  weight_value: 0.6  # 60% value, 40% quality
  weight_quality: 0.4
  threshold_buy: 80  # Stricter buy threshold

guardrails:
  non_financial:
    altman_z_red: 2.0  # Stricter bankruptcy threshold
    beneish_m_red: -2.0  # Stricter manipulation threshold
```

Run with custom config:

```bash
python run_screener.py --config my_config.yaml
```

### 7. Filter Results Programmatically

```python
import pandas as pd

# Load results
df = pd.read_csv('data/screener_results.csv')

# Filter: BUY decisions with VERDE guardrails
buys = df[
    (df['decision'] == 'BUY') &
    (df['guardrail_status'] == 'VERDE')
]

print(f"Found {len(buys)} BUY candidates")

# Top 10 by composite score
top10 = buys.nlargest(10, 'composite_0_100')

for _, row in top10.iterrows():
    print(f"{row['ticker']:6} | {row['composite_0_100']:.1f} | {row['notes_short']}")

# Output:
# MSFT   | 87.3 | EV/EBIT p<20; ROIC 45.2%; Acct. OK
# AAPL   | 84.1 | P/E p20-40; ROIC 38.7%; Acct. OK
# GOOG   | 81.9 | EV/EBIT p<20; ROIC 32.1%; Acct. OK
```

### 8. Track Changes Over Time

```bash
# Run weekly and save results
python run_screener.py
mv data/screener_results.csv data/results_2024_01_15.csv

# Next week
python run_screener.py
mv data/screener_results.csv data/results_2024_01_22.csv

# Compare
python -c "
import pandas as pd

df1 = pd.read_csv('data/results_2024_01_15.csv')
df2 = pd.read_csv('data/results_2024_01_22.csv')

# New BUYs
new_buys = set(df2[df2['decision']=='BUY']['ticker']) - set(df1[df1['decision']=='BUY']['ticker'])
print(f'New BUYs this week: {new_buys}')

# Score changes
merged = df1[['ticker','composite_0_100']].merge(df2[['ticker','composite_0_100']], on='ticker', suffixes=('_old','_new'))
merged['change'] = merged['composite_0_100_new'] - merged['composite_0_100_old']
print('\nBiggest movers:')
print(merged.nlargest(10, 'change')[['ticker','change']])
"
```

## Real-World Workflows

### 9. Initial Research Workflow

```bash
# Step 1: Run screener
python run_screener.py

# Step 2: Review BUYs in spreadsheet
# Filter: decision=BUY, guardrail_status=VERDE
# Sort by: composite_0_100 descending

# Step 3: Deep-dive on top 5
for symbol in MSFT AAPL GOOG V JPM; do
  python run_screener.py --symbol $symbol --output "analysis_${symbol}.json"
done

# Step 4: Extract key insights
grep -A5 "moats" analysis_*.json
grep -A3 "top_risks" analysis_*.json

# Step 5: Manual research
# - Read 10-K/10-Q on SEC EDGAR
# - Listen to earnings call
# - Check valuation vs historical range
# - Build DCF model

# Step 6: Build watchlist
python -c "
import pandas as pd
df = pd.read_csv('data/screener_results.csv')
watchlist = df[df['decision']=='BUY'].nsmallest(20, 'composite_0_100')
watchlist[['ticker','name','composite_0_100','notes_short']].to_csv('watchlist.csv', index=False)
"
```

### 10. Monitoring Workflow (Weekly)

```bash
#!/bin/bash
# weekly_screen.sh

DATE=$(date +%Y_%m_%d)

# Run screener
python run_screener.py

# Save results
cp data/screener_results.csv "archive/results_${DATE}.csv"

# Alert on new BUYs
python -c "
import pandas as pd
import sys

current = pd.read_csv('data/screener_results.csv')
try:
    previous = pd.read_csv('archive/results_$(date -d '7 days ago' +%Y_%m_%d).csv')
except:
    print('No previous results to compare')
    sys.exit(0)

new_buys = set(current[current['decision']=='BUY']['ticker']) - set(previous[previous['decision']=='BUY']['ticker'])

if new_buys:
    print(f'NEW BUY ALERTS: {len(new_buys)}')
    for ticker in new_buys:
        row = current[current['ticker']==ticker].iloc[0]
        print(f'  {ticker}: score={row[\"composite_0_100\"]:.1f}, {row[\"notes_short\"]}')
else:
    print('No new BUYs this week')
"
```

### 11. Sector-Specific Analysis

```python
import pandas as pd

# Load results
df = pd.read_csv('data/screener_results.csv')

# Analyze by sector
sector_stats = df.groupby('sector').agg({
    'ticker': 'count',
    'composite_0_100': 'mean',
    'value_score_0_100': 'mean',
    'quality_score_0_100': 'mean'
}).round(1)

sector_stats['buys'] = df[df['decision']=='BUY'].groupby('sector')['ticker'].count()

print(sector_stats)

# Output:
#                        ticker  composite_0_100  value_score  quality_score  buys
# sector
# Consumer Cyclical          23             52.3         48.2           56.4     2
# Financial Services         18             58.1         62.3           53.9     4
# Healthcare                 15             49.7         45.1           54.3     1
# Technology                 32             61.2         55.8           66.6     8
# ...

# Deep-dive on best sector (Technology)
tech = df[(df['sector']=='Technology') & (df['decision']=='BUY')]
print(f"\nTechnology BUYs ({len(tech)}):")
for _, row in tech.iterrows():
    print(f"  {row['ticker']:6} | {row['composite_0_100']:.1f} | {row['notes_short']}")
```

### 12. Build Portfolio

```python
import pandas as pd

df = pd.read_csv('data/screener_results.csv')

# Select top 20 BUYs
buys = df[
    (df['decision'] == 'BUY') &
    (df['guardrail_status'] == 'VERDE')
].nlargest(20, 'composite_0_100')

# Diversify by sector (max 4 per sector)
portfolio = []
sector_counts = {}

for _, row in buys.iterrows():
    sector = row['sector']
    if sector_counts.get(sector, 0) < 4:
        portfolio.append(row)
        sector_counts[sector] = sector_counts.get(sector, 0) + 1

    if len(portfolio) >= 15:
        break

portfolio_df = pd.DataFrame(portfolio)

# Equal-weight portfolio
portfolio_df['weight_%'] = 100 / len(portfolio_df)

print(f"Portfolio: {len(portfolio_df)} stocks\n")
print(portfolio_df[['ticker', 'name', 'sector', 'composite_0_100', 'weight_%']])

# Export
portfolio_df.to_csv('my_portfolio.csv', index=False)
```

## Troubleshooting

### API Key Issues

```bash
# Check if API key is set
echo $FMP_API_KEY

# Test API manually
curl "https://financialmodelingprep.com/api/v3/profile/AAPL?apikey=$FMP_API_KEY"

# If getting 401 Unauthorized:
# 1. Verify key is correct
# 2. Check plan limits (free plans have restricted access)
# 3. Try with a paid plan key
```

### Cache Issues

```bash
# Clear cache to force fresh data
rm -rf cache/*

# Run screener again
python run_screener.py

# Check cache hit rate (should be 0% on first run)
cat logs/pipeline_metrics.json | jq '.metrics.cache_stats'
```

### Performance Issues

```bash
# Reduce Top-K to speed up
# Edit settings.yaml:
universe:
  top_k: 50  # Instead of 150

# Or reduce universe size
universe:
  min_market_cap: 5_000_000_000  # $5B+ only

# Monitor API calls
tail -f logs/screener.log | grep "GET https"
```

### Missing Metrics

```python
import pandas as pd

df = pd.read_csv('data/screener_results.csv')

# Check completeness
metrics = ['ev_ebit_ttm', 'roic_%', 'altmanZ', 'beneishM']
for metric in metrics:
    na_pct = df[metric].isna().sum() / len(df) * 100
    print(f"{metric:20} : {na_pct:.1f}% missing")

# Symbols with >50% metrics missing
cols = [c for c in df.columns if c not in ['ticker','name','sector']]
df['pct_complete'] = df[cols].notna().sum(axis=1) / len(cols) * 100
incomplete = df[df['pct_complete'] < 50]

if len(incomplete) > 0:
    print(f"\n{len(incomplete)} symbols with <50% data completeness:")
    print(incomplete[['ticker', 'pct_complete', 'guardrail_reasons']])
```

## Integration Examples

### 13. Export to Excel with Formatting

```python
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import PatternFill

# Load results
df = pd.read_csv('data/screener_results.csv')

# Write to Excel
df.to_excel('results.xlsx', index=False, sheet_name='Screener')

# Apply conditional formatting
wb = load_workbook('results.xlsx')
ws = wb['Screener']

# Color-code decisions
green_fill = PatternFill(start_color='C6EFCE', fill_type='solid')
yellow_fill = PatternFill(start_color='FFEB9C', fill_type='solid')
red_fill = PatternFill(start_color='FFC7CE', fill_type='solid')

decision_col = [cell for cell in ws[1] if cell.value == 'decision'][0].column

for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
    decision = row[decision_col - 1].value
    if decision == 'BUY':
        for cell in row:
            cell.fill = green_fill
    elif decision == 'MONITOR':
        for cell in row:
            cell.fill = yellow_fill
    elif decision == 'AVOID':
        for cell in row:
            cell.fill = red_fill

wb.save('results_formatted.xlsx')
print("✓ Exported to results_formatted.xlsx with color-coding")
```

### 14. Send Alerts via Email

```python
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

df = pd.read_csv('data/screener_results.csv')
buys = df[df['decision'] == 'BUY']

if len(buys) > 0:
    # Prepare email
    subject = f"UltraQuality Alert: {len(buys)} BUY signals"
    body = "Top BUY candidates:\n\n"

    for _, row in buys.nlargest(10, 'composite_0_100').iterrows():
        body += f"{row['ticker']:6} | Score: {row['composite_0_100']:.1f} | {row['notes_short']}\n"

    # Send email (configure SMTP settings)
    msg = MIMEMultipart()
    msg['From'] = 'screener@example.com'
    msg['To'] = 'investor@example.com'
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    # server = smtplib.SMTP('smtp.gmail.com', 587)
    # server.starttls()
    # server.login('your_email', 'your_password')
    # server.send_message(msg)
    # server.quit()

    print(f"✓ Alert email prepared for {len(buys)} BUYs")
```

## Tips & Best Practices

1. **Run regularly**: Weekly on weekends after market close
2. **Cache aggressively**: Don't clear cache between runs (saves API quota)
3. **Review guardrails**: Don't blindly buy high scores with ROJO flags
4. **Combine with fundamentals**: Use screener as starting point, not final decision
5. **Track performance**: Save historical results to backtest methodology
6. **Diversify**: Don't concentrate portfolio in one sector
7. **Monitor news**: Re-run qualitative analysis before buying
8. **Set alerts**: Notify when composite score > 80 and guardrails = VERDE

---

For more examples, see [README.md](README.md) and [ARCHITECTURE.md](ARCHITECTURE.md).
