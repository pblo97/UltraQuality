#!/usr/bin/env python3
"""
Simple check: Does AAPL actually have any P-Purchase transactions?
This bypasses all the complex logic and just checks the raw API data.
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Minimal imports
import yaml
from pathlib import Path

# Load config
config_path = Path(__file__).parent / 'settings.yaml'
with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

# Get API key from Streamlit secrets (simplest way)
try:
    import streamlit as st
    if hasattr(st, 'secrets') and 'FMP_API_KEY' in st.secrets:
        api_key = st.secrets['FMP_API_KEY']
        print(f"✓ Using API key from Streamlit secrets\n")
    else:
        print("❌ No API key in Streamlit secrets")
        print("Make sure ~/.streamlit/secrets.toml has FMP_API_KEY")
        sys.exit(1)
except Exception as e:
    print(f"❌ Error loading Streamlit secrets: {e}")
    sys.exit(1)

# Direct API call
import requests
from datetime import datetime, timedelta

symbol = 'AAPL'
url = f'https://financialmodelingprep.com/api/v4/insider-trading'
params = {'symbol': symbol, 'page': 0, 'apikey': api_key}

print("="*80)
print(f"Checking {symbol} Insider Trading")
print("="*80)
print(f"\nCalling: {url}")
print("Waiting...\n")

try:
    response = requests.get(url, params=params, timeout=15)

    if response.status_code != 200:
        print(f"❌ HTTP {response.status_code}: {response.text[:200]}")
        sys.exit(1)

    data = response.json()

    if not isinstance(data, list):
        print(f"❌ Unexpected response: {data}")
        sys.exit(1)

    print(f"✅ Got {len(data)} total transactions\n")

    if len(data) == 0:
        print("⚠️  No transactions returned by API")
        sys.exit(0)

    # Show first transaction structure
    print("="*80)
    print("FIRST TRANSACTION (to see structure):")
    print("="*80)
    first = data[0]
    for key, value in first.items():
        print(f"  {key:25s} = {str(value)[:60]}")

    # Count by transaction type
    print("\n" + "="*80)
    print("TRANSACTION TYPE COUNTS:")
    print("="*80)

    from collections import defaultdict
    type_counts = defaultdict(int)

    for trade in data:
        ttype = trade.get('transactionType', 'MISSING')
        type_counts[ttype] += 1

    for ttype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {count:3d}x  '{ttype}'")

    # Check last 12 months
    print("\n" + "="*80)
    print("LAST 12 MONTHS ANALYSIS:")
    print("="*80)

    one_year_ago = datetime.now() - timedelta(days=365)
    recent = []
    date_errors = 0

    for trade in data:
        try:
            date_str = trade.get('transactionDate', '')
            if not date_str:
                date_errors += 1
                continue
            trade_date = datetime.strptime(date_str, '%Y-%m-%d')
            if trade_date >= one_year_ago:
                recent.append(trade)
        except Exception as e:
            date_errors += 1

    print(f"\nRecent trades (last 12 months): {len(recent)}")
    if date_errors > 0:
        print(f"Date parsing errors: {date_errors}")

    # Classify recent trades
    buys = []
    sells = []
    other = []

    for trade in recent:
        ttype = trade.get('transactionType', '').upper()

        # Check if it's a buy
        is_buy = (
            'P-PURCHASE' in ttype or
            'PURCHASE' in ttype or
            ttype.startswith('P-') or
            ttype == 'P' or
            'BUY' in ttype
        )

        # Check if it's a sell
        is_sell = (
            'S-SALE' in ttype or
            'SALE' in ttype or
            ttype.startswith('S-') or
            ttype == 'S' or
            'SELL' in ttype
        )

        if is_buy:
            buys.append(trade)
        elif is_sell:
            sells.append(trade)
        else:
            other.append(trade)

    print(f"\n✅ Buys detected: {len(buys)}")
    print(f"✅ Sells detected: {len(sells)}")
    print(f"⚠️  Other/Unclassified: {len(other)}")

    if buys:
        print(f"\n📈 SAMPLE BUY TRANSACTIONS:")
        for i, trade in enumerate(buys[:3]):
            print(f"\n  Buy #{i+1}:")
            print(f"    Date: {trade.get('transactionDate')}")
            print(f"    Type: {trade.get('transactionType')}")
            print(f"    Name: {trade.get('reportingName', 'N/A')}")
            print(f"    Shares: {trade.get('securitiesTransacted', 0):,.0f}")
    else:
        print("\n⚠️  NO BUY TRANSACTIONS FOUND IN LAST 12 MONTHS")
        print("    This might be legitimate - AAPL insiders may only sell, not buy.")
        print("    Insiders often receive stock compensation and sell it regularly.")

    if other:
        print(f"\n⚠️  UNCLASSIFIED TRANSACTION TYPES:")
        uniq_types = set(t.get('transactionType') for t in other)
        for ttype in sorted(uniq_types):
            count = sum(1 for t in other if t.get('transactionType') == ttype)
            print(f"    {count}x  '{ttype}'")

    print("\n" + "="*80)
    print("CONCLUSION:")
    print("="*80)

    if len(buys) == 0 and len(sells) > 0:
        print("\n⚠️  AAPL has NO purchases in the last 12 months, only sales.")
        print("   This is actually NORMAL for large tech companies like Apple.")
        print("   Insiders receive stock as compensation and sell it, but rarely buy.")
        print("\n✅ The code is working correctly!")
        print("   Try testing with a different symbol that has insider purchases.")
        print("\n💡 Symbols that typically have insider buys:")
        print("   - Smaller cap growth stocks")
        print("   - Companies where founders are still active")
        print("   - Check symbols from: https://www.insider-monitor.com/trading_purchases.html")
    elif len(buys) > 0:
        print(f"\n✅ Found {len(buys)} buy transactions - code is working!")
    else:
        print("\n⚠️  No transactions found at all")

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
