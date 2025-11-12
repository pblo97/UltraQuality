#!/usr/bin/env python3
"""
Quick diagnostic: What transaction types does v4 API actually return for AAPL?
This will show us exactly why buys aren't being detected.
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import yaml
import requests
from pathlib import Path
from collections import Counter
from screener.orchestrator import ScreenerOrchestrator

# Use orchestrator to get API key properly
config_path = Path(__file__).parent / 'settings_premium.yaml'
if not config_path.exists():
    config_path = Path(__file__).parent / 'settings.yaml'

with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

# Let orchestrator handle API key loading (Streamlit secrets, env vars, etc.)
try:
    orch = ScreenerOrchestrator(config)
    api_key = orch.fmp.api_key
    print(f"✓ Using API key: {api_key[:10]}...{api_key[-4:]}\n")
except Exception as e:
    print(f"❌ Failed to get API key: {e}")
    print("\nTry setting FMP_API_KEY environment variable:")
    print("export FMP_API_KEY='your_key_here'")
    sys.exit(1)

# Test with AAPL
symbol = 'AAPL'
print("="*80)
print(f"Diagnosing Transaction Types for {symbol}")
print("="*80)

url = f'https://financialmodelingprep.com/api/v4/insider-trading'
params = {'symbol': symbol, 'page': 0, 'apikey': api_key}

print(f"\nCalling: {url}?symbol={symbol}&page=0")
print("Waiting for response...\n")

try:
    response = requests.get(url, params=params, timeout=15)

    if response.status_code != 200:
        print(f"❌ Error {response.status_code}: {response.text}")
        sys.exit(1)

    data = response.json()

    if isinstance(data, dict) and 'Error Message' in data:
        print(f"❌ API Error: {data['Error Message']}")
        sys.exit(1)

    if not isinstance(data, list):
        print(f"⚠️  Unexpected response type: {type(data)}")
        sys.exit(1)

    print(f"✅ Got {len(data)} transactions\n")

    if len(data) == 0:
        print("⚠️  No data returned")
        sys.exit(0)

    # Count transaction types
    type_counter = Counter()
    for trade in data:
        ttype = trade.get('transactionType', 'MISSING')
        type_counter[ttype] += 1

    print("="*80)
    print("TRANSACTION TYPE BREAKDOWN:")
    print("="*80)
    for ttype, count in type_counter.most_common():
        print(f"  {count:3d}x  '{ttype}'")

    print("\n" + "="*80)
    print("CLASSIFICATION TEST:")
    print("="*80)

    # Test our classification logic
    buys = 0
    sells = 0
    other = []

    for trade in data:
        ttype = trade.get('transactionType', '').upper()

        is_buy = (
            'P-PURCHASE' in ttype or
            'PURCHASE' in ttype or
            ttype.startswith('P-') or
            ttype == 'P' or
            'BUY' in ttype or
            'ACQUIRE' in ttype
        )
        is_sell = (
            'S-SALE' in ttype or
            'SALE' in ttype or
            ttype.startswith('S-') or
            ttype == 'S' or
            'SELL' in ttype or
            'DISPOSE' in ttype
        )

        if is_buy:
            buys += 1
        elif is_sell:
            sells += 1
        else:
            if ttype not in [o[0] for o in other]:
                other.append((ttype, trade.get('transactionType')))

    print(f"\n✅ BUY transactions detected: {buys}")
    print(f"✅ SELL transactions detected: {sells}")

    if other:
        print(f"\n⚠️  UNCLASSIFIED ({len(other)} unique types):")
        for upper_type, orig_type in other:
            print(f"    '{orig_type}' -> (uppercase: '{upper_type}')")

    print("\n" + "="*80)
    print("SAMPLE TRANSACTIONS:")
    print("="*80)

    # Show examples of each type
    types_shown = set()
    for trade in data[:20]:  # First 20 transactions
        ttype = trade.get('transactionType')
        if ttype not in types_shown:
            print(f"\n📄 Type: '{ttype}'")
            print(f"   Date: {trade.get('transactionDate')}")
            print(f"   Name: {trade.get('reportingName', 'N/A')}")
            print(f"   Shares: {trade.get('securitiesTransacted', 0):,.0f}")
            print(f"   Price: ${trade.get('price', 0):.2f}")
            types_shown.add(ttype)

    print("\n" + "="*80)
    print("CONCLUSION:")
    print("="*80)

    if buys == 0 and sells > 0:
        print("⚠️  BUY transactions NOT detected but SELL transactions are!")
        print("   This confirms there's a classification issue.")
        print("   Check the 'UNCLASSIFIED' section above for buy types.")
    elif buys > 0 and sells > 0:
        print("✅ Both BUY and SELL transactions detected correctly!")
    elif buys == 0 and sells == 0:
        print("❌ NO transactions classified at all!")
        print("   All transaction types are unclassified.")
    else:
        print(f"📊 Results: {buys} buys, {sells} sells")

except Exception as e:
    print(f"\n❌ Exception: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
