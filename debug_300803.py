"""
Debug script to analyze why 300803.SZ has high score despite poor metrics.
"""
import pandas as pd
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Check if results file exists
results_file = Path('./data/screener_results.csv')
if not results_file.exists():
    print("❌ No screener results found. Please run the screener first.")
    print("Looking for: ./data/screener_results.csv")
    sys.exit(1)

# Load results
df = pd.read_csv(results_file)

# Find 300803.SZ
ticker = '300803.SZ'
if ticker not in df['ticker'].values:
    print(f"❌ {ticker} not found in results.")
    print(f"Available tickers: {df['ticker'].head(10).tolist()}")
    sys.exit(1)

# Get the row
row = df[df['ticker'] == ticker].iloc[0]

print("=" * 80)
print(f"DIAGNOSTIC REPORT: {ticker}")
print("=" * 80)

# Basic info
print(f"\nCOMPANY INFO:")
print(f"  Name: {row.get('name', 'N/A')}")
print(f"  Sector: {row.get('sector', 'N/A')}")
print(f"  Industry: {row.get('industry', 'N/A')}")
print(f"  Country: {row.get('country', 'N/A')}")

# Scores
print(f"\nSCORES:")
print(f"  Value Score: {row.get('value_score_0_100', 'N/A'):.1f}/100")
print(f"  Quality Score: {row.get('quality_score_0_100', 'N/A'):.1f}/100")
print(f"  Composite Score: {row.get('composite_0_100', 'N/A'):.1f}/100")
print(f"  Decision: {row.get('decision', 'N/A')}")

# Value metrics (should be LOW for EV/FCF=200)
print(f"\nVALUE METRICS:")
print(f"  EV/EBIT: {row.get('ev_ebit_ttm', 'N/A')}")
print(f"  EV/FCF: {row.get('ev_fcf_ttm', 'N/A')}")
print(f"  P/E: {row.get('pe_ttm', 'N/A')}")
print(f"  P/B: {row.get('pb_ttm', 'N/A')}")
print(f"  Shareholder Yield: {row.get('shareholder_yield_%', 'N/A')}%")

# Quality metrics (should be LOW for ROIC=3%)
print(f"\nQUALITY METRICS:")
print(f"  ROIC: {row.get('roic_%', 'N/A')}%")
print(f"  ROIC Persistence: {row.get('roic_persistence', 'N/A')}")
print(f"  FCF Margin: {row.get('fcf_margin_%', 'N/A')}%")
print(f"  Gross Profit/Assets: {row.get('grossProfits_to_assets', 'N/A')}")
print(f"  CFO/NI: {row.get('cfo_to_ni', 'N/A')}")
print(f"  Revenue Growth 3Y: {row.get('revenue_growth_3y', 'N/A')}%")
print(f"  Moat Score: {row.get('moat_score', 'N/A')}")

# Leverage
print(f"\nLEVERAGE:")
print(f"  Net Debt/EBITDA: {row.get('netDebt_ebitda', 'N/A')}")
print(f"  Interest Coverage: {row.get('interestCoverage', 'N/A')}")

# Guardrails
print(f"\nGUARDRAILS:")
print(f"  Status: {row.get('guardrail_status', 'N/A')}")
print(f"  Reasons: {row.get('guardrail_reasons', 'N/A')}")

# Check if company type
print(f"\nCOMPANY TYPE:")
print(f"  is_financial: {row.get('is_financial', 'N/A')}")
print(f"  is_REIT: {row.get('is_REIT', 'N/A')}")
print(f"  is_utility: {row.get('is_utility', 'N/A')}")

print("\n" + "=" * 80)
print("HYPOTHESIS:")
print("=" * 80)

# Analyze scores
value_score = row.get('value_score_0_100', 0)
quality_score = row.get('quality_score_0_100', 0)
composite = row.get('composite_0_100', 0)

if value_score < 30:
    print("✓ Value score is LOW (as expected for EV/FCF=200)")
else:
    print(f"❌ BUG: Value score is {value_score:.1f} (should be <30 for EV/FCF=200)")

if quality_score < 30:
    print("✓ Quality score is LOW (as expected for ROIC=3%)")
elif quality_score > 70:
    print(f"❌ BUG: Quality score is {quality_score:.1f} (should be <30 for ROIC=3%)")
    print("   Possible causes:")
    print("   1. Normalization by industry makes ROIC=3% look 'average'")
    print("   2. Other quality metrics (revenue growth, moat) are compensating")
    print("   3. Bug in z-score calculation or aggregation")
else:
    print(f"⚠️  Quality score is MEDIUM {quality_score:.1f} (unexpected for ROIC=3%)")

# Compare to industry
industry = row.get('industry', 'Unknown')
industry_peers = df[df['industry'] == industry]
print(f"\nINDUSTRY COMPARISON ({industry}):")
print(f"  Peers in dataset: {len(industry_peers)}")
if len(industry_peers) > 1:
    print(f"  ROIC range: {industry_peers['roic_%'].min():.1f}% - {industry_peers['roic_%'].max():.1f}%")
    print(f"  ROIC median: {industry_peers['roic_%'].median():.1f}%")
    print(f"  300803.SZ ROIC: {row.get('roic_%', 'N/A')}%")

    print(f"\n  Quality Score range: {industry_peers['quality_score_0_100'].min():.1f} - {industry_peers['quality_score_0_100'].max():.1f}")
    print(f"  Quality Score median: {industry_peers['quality_score_0_100'].median():.1f}")
    print(f"  300803.SZ Quality: {row.get('quality_score_0_100', 'N/A'):.1f}")

print("\n" + "=" * 80)
