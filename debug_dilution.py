#!/usr/bin/env python3
"""
Debug dilution calculation for specific tickers (MA, CL)
to understand why they show high dilution values.
"""

import os
import sys
from pathlib import Path
import yaml

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from screener.ingest import FMPClient

def analyze_dilution(ticker: str):
    """Analyze dilution calculation for a specific ticker."""

    print(f"\n{'='*60}")
    print(f"ANALYZING DILUTION FOR: {ticker}")
    print(f"{'='*60}\n")

    # Load config and API key
    api_key = os.getenv('FMP_API_KEY')
    if not api_key:
        print("❌ FMP_API_KEY environment variable not set")
        return

    # Load config
    config_path = Path(__file__).parent / 'config.yaml'
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    client = FMPClient(api_key, config['fmp'])

    # Fetch balance sheet data
    print("Fetching balance sheet data...")
    balance = client.get_balance_sheet(ticker, period='quarter', limit=10)

    if not balance or len(balance) < 5:
        print(f"❌ Not enough balance sheet data (got {len(balance) if balance else 0} quarters)")
        return

    print(f"✓ Got {len(balance)} quarters of data\n")

    # Display share count over time
    print("SHARE COUNT HISTORY:")
    print("-" * 100)
    print(f"{'Quarter':<12} {'Date':<12} {'weightedAvg':<20} {'sharesOutstanding':<20} {'diluted':<20}")
    print("-" * 100)

    for i, q in enumerate(balance[:8]):
        date = q.get('date', 'N/A')
        weighted = q.get('weightedAverageShsOut', 0)
        outstanding = q.get('commonStockSharesOutstanding', 0)
        diluted = q.get('weightedAverageShsOutDil', 0)

        print(f"Q-{i:<10} {date:<12} {weighted:>18,} {outstanding:>18,} {diluted:>18,}")

    print("-" * 100)

    # Calculate dilution using the same logic as guardrails.py
    print("\nDILUTION CALCULATION:")
    print("-" * 60)

    shares_t = (balance[0].get('weightedAverageShsOut') or
                balance[0].get('commonStockSharesOutstanding') or
                balance[0].get('weightedAverageShsOutDil'))

    shares_t4 = (balance[4].get('weightedAverageShsOut') or
                 balance[4].get('commonStockSharesOutstanding') or
                 balance[4].get('weightedAverageShsOutDil'))

    print(f"Most recent (Q0): {shares_t:,}")
    print(f"4 quarters ago (Q4): {shares_t4:,}")

    if shares_t and shares_t4 and shares_t4 > 0:
        raw_pct = ((shares_t - shares_t4) / shares_t4) * 100
        capped_pct = max(-100, min(100, raw_pct))

        print(f"\nRaw calculation: ({shares_t:,} - {shares_t4:,}) / {shares_t4:,} * 100")
        print(f"Raw result: {raw_pct:.2f}%")
        print(f"Capped result: {capped_pct:.2f}%")

        if raw_pct != capped_pct:
            print(f"⚠️  Value was capped from {raw_pct:.2f}% to {capped_pct:.2f}%")

        if abs(raw_pct) > 20:
            print(f"\n⚠️  WARNING: {abs(raw_pct):.1f}% change is unusual for mature company")
            print("   Possible causes:")
            print("   - Stock split (should be adjusted by FMP)")
            print("   - Major acquisition paid with stock")
            print("   - Data quality issue from FMP API")
            print("   - Share repurchase program (if negative)")
    else:
        print("❌ Unable to calculate dilution (missing data)")

    # Also check cash flow method
    print("\n" + "-" * 60)
    print("CASH FLOW METHOD (Alternative):")
    print("-" * 60)

    cashflow = client.get_cash_flow(ticker, period='quarter', limit=5)

    if cashflow:
        cf = cashflow[0]
        stock_issued = cf.get('commonStockIssued', 0)
        stock_repurchased = cf.get('commonStockRepurchased', 0)
        date = cf.get('date', 'N/A')

        print(f"Latest quarter ({date}):")
        print(f"  Stock issued: ${stock_issued:,}")
        print(f"  Stock repurchased: ${stock_repurchased:,}")
        print(f"  Net: ${stock_issued + stock_repurchased:,}")

        if stock_issued + stock_repurchased != 0:
            equity = balance[0].get('totalStockholdersEquity', 1)
            dilution_pct = ((stock_issued + stock_repurchased) / equity) * 100
            capped_dilution_pct = max(-100, min(100, dilution_pct))
            print(f"  Equity: ${equity:,}")
            print(f"  Dilution %: {dilution_pct:.2f}%")
            print(f"  Capped: {capped_dilution_pct:.2f}%")
    else:
        print("❌ No cash flow data available")

    print("\n" + "=" * 60 + "\n")


def main():
    """Analyze dilution for problematic tickers."""

    tickers = ['MA', 'CL']  # Mastercard, Colgate-Palmolive

    print("\n" + "=" * 60)
    print("DILUTION CALCULATION DIAGNOSTIC")
    print("=" * 60)
    print("\nAnalyzing tickers with suspiciously high dilution values...")
    print("Target tickers: MA (61.1%), CL (60.3%)")

    for ticker in tickers:
        try:
            analyze_dilution(ticker)
        except Exception as e:
            print(f"\n❌ Error analyzing {ticker}: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60)


if __name__ == '__main__':
    main()
