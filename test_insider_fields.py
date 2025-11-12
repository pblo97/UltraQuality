#!/usr/bin/env python3
"""
Test what fields v4 insider trading API actually returns.
This will help us understand if field names are different.
"""
import os
import sys
import yaml
import requests
from pathlib import Path

# Get API key (same logic as orchestrator.py)
api_key = None

# 1. Try environment variable first
api_key = os.getenv('FMP_API_KEY')
if api_key:
    print(f"✓ Using API key from environment: {api_key[:10]}...")

# 2. Try Streamlit secrets
if not api_key:
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and 'FMP_API_KEY' in st.secrets:
            api_key = st.secrets['FMP_API_KEY']
            print(f"✓ Using API key from Streamlit secrets: {api_key[:10]}...")
    except:
        pass

# 3. Try config file (and expand ${FMP_API_KEY} if present)
if not api_key:
    config_path = Path(__file__).parent / 'settings_premium.yaml'
    if not config_path.exists():
        config_path = Path(__file__).parent / 'settings.yaml'

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    config_key = config['fmp']['api_key']

    # Expand environment variable if format is ${VAR_NAME}
    if config_key and config_key.startswith('${') and config_key.endswith('}'):
        var_name = config_key[2:-1]
        api_key = os.getenv(var_name)
        if api_key:
            print(f"✓ Using API key from {var_name} env var: {api_key[:10]}...")
    else:
        api_key = config_key
        if api_key:
            print(f"✓ Using API key from config: {api_key[:10]}...")

if not api_key or api_key.startswith('${'):
    print("❌ No valid API key found!")
    print("   Set FMP_API_KEY environment variable:")
    print("   export FMP_API_KEY='your_key_here'")
    sys.exit(1)

# Test with AAPL (definitely has insider trading activity)
symbol = 'AAPL'

print("="*80)
print(f"Testing v4 Insider Trading API for {symbol}")
print("="*80)

url = f'https://financialmodelingprep.com/api/v4/insider-trading'
params = {
    'symbol': symbol,
    'page': 0,
    'apikey': api_key
}

print(f"\nURL: {url}")
print(f"Params: symbol={symbol}, page=0")
print("\nCalling API...")

try:
    response = requests.get(url, params=params, timeout=10)
    print(f"Status: {response.status_code}")

    if response.status_code != 200:
        print(f"❌ Error: {response.text}")
        sys.exit(1)

    data = response.json()

    # Check response type
    if isinstance(data, dict) and 'Error Message' in data:
        print(f"❌ API Error: {data['Error Message']}")
        sys.exit(1)

    if not isinstance(data, list):
        print(f"⚠️  Unexpected response type: {type(data)}")
        print(f"Response: {data}")
        sys.exit(1)

    # Show results
    print(f"\n✅ Success! Got {len(data)} records")

    if len(data) == 0:
        print("\n⚠️  No data returned (try a different symbol)")
        sys.exit(0)

    # Show first record with all fields
    print("\n" + "="*80)
    print("FIRST RECORD - ALL FIELDS:")
    print("="*80)
    first = data[0]

    import json
    print(json.dumps(first, indent=2))

    # Analyze field names
    print("\n" + "="*80)
    print("FIELD ANALYSIS:")
    print("="*80)

    fields = list(first.keys())
    print(f"\n📋 Available fields ({len(fields)}):")
    for field in sorted(fields):
        value = first[field]
        value_str = str(value)[:50]
        print(f"  • {field:25s} = {value_str}")

    # Check if our expected fields exist
    print("\n" + "="*80)
    print("COMPATIBILITY CHECK:")
    print("="*80)

    expected_fields = [
        'transactionDate',
        'transactionType',
        'securitiesTransacted',
        'price',
        'reportingName'
    ]

    print("\nChecking fields our code expects:")
    for field in expected_fields:
        exists = field in first
        status = "✅" if exists else "❌"
        print(f"  {status} {field:25s} {'EXISTS' if exists else 'MISSING'}")

    # Look for alternative field names
    print("\n" + "="*80)
    print("ALTERNATIVE FIELD NAMES:")
    print("="*80)

    # Transaction type alternatives
    type_fields = [f for f in fields if 'type' in f.lower() or 'transaction' in f.lower()]
    if type_fields:
        print(f"\n🔍 Type/Transaction fields: {type_fields}")
        for f in type_fields:
            print(f"    {f} = {first[f]}")

    # Price/value alternatives
    price_fields = [f for f in fields if 'price' in f.lower() or 'value' in f.lower()]
    if price_fields:
        print(f"\n💰 Price/Value fields: {price_fields}")
        for f in price_fields:
            print(f"    {f} = {first[f]}")

    # Name alternatives
    name_fields = [f for f in fields if 'name' in f.lower() or 'reporting' in f.lower()]
    if name_fields:
        print(f"\n👤 Name/Reporting fields: {name_fields}")
        for f in name_fields:
            print(f"    {f} = {first[f]}")

    # Shares/securities alternatives
    shares_fields = [f for f in fields if 'securi' in f.lower() or 'share' in f.lower()]
    if shares_fields:
        print(f"\n📊 Shares/Securities fields: {shares_fields}")
        for f in shares_fields:
            print(f"    {f} = {first[f]}")

    print("\n" + "="*80)
    print("SUMMARY:")
    print("="*80)
    print(f"✅ v4 API is working and returning data")
    print(f"📊 {len(data)} records returned for {symbol}")

    # Determine if we need to update field names
    missing = [f for f in expected_fields if f not in first]
    if missing:
        print(f"\n⚠️  NEED TO UPDATE CODE:")
        print(f"   Missing fields: {missing}")
        print(f"   Check the alternative field names above")
    else:
        print(f"\n✅ All expected fields exist - code should work!")

except Exception as e:
    print(f"\n❌ Exception: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
