#!/usr/bin/env python3
"""Test both v3 and v4 insider trading endpoints"""
import os
import requests

api_key = os.getenv('FMP_API_KEY')
if not api_key:
    print("Set FMP_API_KEY: export FMP_API_KEY='your_key'")
    exit(1)

symbol = 'AAPL'

print("="*80)
print(f"Testing Insider Trading Endpoints for {symbol}")
print("="*80)

# Test v3
print("\n1️⃣ Testing v3 endpoint:")
url_v3 = f'https://financialmodelingprep.com/api/v3/insider-trading?symbol={symbol}&limit=10&apikey={api_key}'
print(f"URL: {url_v3[:80]}...")

try:
    r = requests.get(url_v3, timeout=10)
    print(f"Status: {r.status_code}")
    data = r.json()
    if isinstance(data, list):
        print(f"✅ v3: {len(data)} items")
        if len(data) > 0:
            print(f"   Sample: {data[0].get('transactionDate')} - {data[0].get('reportingName')}")
    elif isinstance(data, dict) and 'Error Message' in data:
        print(f"❌ v3 Error: {data['Error Message']}")
    else:
        print(f"⚠️  v3: Unexpected response")
except Exception as e:
    print(f"❌ v3 Exception: {e}")

# Test v4
print("\n2️⃣ Testing v4 endpoint:")
url_v4 = f'https://financialmodelingprep.com/api/v4/insider-trading?symbol={symbol}&limit=10&apikey={api_key}'
print(f"URL: {url_v4[:80]}...")

try:
    r = requests.get(url_v4, timeout=10)
    print(f"Status: {r.status_code}")
    data = r.json()
    if isinstance(data, list):
        print(f"✅ v4: {len(data)} items")
        if len(data) > 0:
            print(f"   Sample: {data[0].get('transactionDate')} - {data[0].get('reportingName')}")
    elif isinstance(data, dict) and 'Error Message' in data:
        print(f"❌ v4 Error: {data['Error Message']}")
    else:
        print(f"⚠️  v4: Unexpected response")
except Exception as e:
    print(f"❌ v4 Exception: {e}")

print("\n" + "="*80)
print("Which one works?")
print("="*80)
