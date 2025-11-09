#!/usr/bin/env python
"""Debug script to check shares outstanding data from FMP API."""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from screener.ingest import FMPClient

def debug_shares(symbol='AAPL'):
    """Debug shares outstanding retrieval."""
    # Try to load from .env file manually
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    api_key = None

    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                if line.strip().startswith('FMP_API_KEY='):
                    api_key = line.split('=', 1)[1].strip().strip('"').strip("'")
                    break

    if not api_key:
        api_key = os.getenv('FMP_API_KEY')

    if not api_key:
        print("❌ FMP_API_KEY not found in .env")
        return

    fmp = FMPClient(api_key)

    print(f"\n{'='*60}")
    print(f"🔍 Debugging Shares Outstanding for {symbol}")
    print(f"{'='*60}\n")

    # 1. Try balance sheet
    print("1️⃣ BALANCE SHEET (Annual):")
    print("-" * 60)
    balance = fmp.get_balance_sheet(symbol, period='annual', limit=1)
    if balance and len(balance) > 0:
        print(f"✓ Got balance sheet data for {balance[0].get('date', 'N/A')}")
        print(f"\nSearching for shares outstanding fields:")

        # Check all possible fields
        shares_fields = [
            'weightedAverageShsOut',
            'weightedAverageShsOutDil',
            'commonStockSharesOutstanding',
            'sharesOutstanding',
            'commonStock'
        ]

        found_any = False
        for field in shares_fields:
            value = balance[0].get(field)
            if value:
                print(f"  ✓ {field}: {value:,}")
                found_any = True
            else:
                print(f"  ✗ {field}: {value}")

        if not found_any:
            print("\n⚠️ No shares outstanding fields found in balance sheet")
            print("\nAll available fields:")
            for key in sorted(balance[0].keys()):
                val = balance[0][key]
                if val and not isinstance(val, str):
                    print(f"  • {key}: {val:,}" if isinstance(val, (int, float)) else f"  • {key}: {val}")
    else:
        print("✗ No balance sheet data")

    # 2. Try profile
    print(f"\n2️⃣ PROFILE:")
    print("-" * 60)
    profile = fmp.get_profile(symbol)
    if profile and len(profile) > 0:
        print(f"✓ Got profile data")

        shares_fields = ['sharesOutstanding', 'mktCap', 'price']
        for field in shares_fields:
            value = profile[0].get(field)
            if value:
                print(f"  ✓ {field}: {value:,}")
            else:
                print(f"  ✗ {field}: {value}")

        # Calculate shares from market cap and price
        mkt_cap = profile[0].get('mktCap')
        price = profile[0].get('price')
        if mkt_cap and price and price > 0:
            calculated_shares = mkt_cap / price
            print(f"\n  💡 Calculated shares (mktCap/price): {calculated_shares:,.0f}")
    else:
        print("✗ No profile data")

    # 3. Try income statement (for weighted average)
    print(f"\n3️⃣ INCOME STATEMENT (TTM):")
    print("-" * 60)
    income = fmp.get_income_statement(symbol, period='annual', limit=1)
    if income and len(income) > 0:
        print(f"✓ Got income statement for {income[0].get('date', 'N/A')}")

        shares_fields = [
            'weightedAverageShsOut',
            'weightedAverageShsOutDil'
        ]

        for field in shares_fields:
            value = income[0].get(field)
            if value:
                print(f"  ✓ {field}: {value:,}")
            else:
                print(f"  ✗ {field}: {value}")
    else:
        print("✗ No income statement data")

    print(f"\n{'='*60}\n")

if __name__ == '__main__':
    symbol = sys.argv[1] if len(sys.argv) > 1 else 'AAPL'
    debug_shares(symbol)
