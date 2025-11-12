#!/usr/bin/env python3
"""
Test both v3 and v4 insider trading endpoints.

RESULT: According to FMP documentation, insider trading is a v4 endpoint.
The code has been updated to use v4.
"""
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
print("\n📋 According to FMP documentation:")
print("   - Insider Trading uses v4 API")
print("   - URL: https://financialmodelingprep.com/api/v4/insider-trading")
print("   - Parameters: symbol, page (not limit)")
print("")

# Test v3 (should not work)
print("\n1️⃣ Testing v3 endpoint (legacy - not recommended):")
url_v3 = f'https://financialmodelingprep.com/api/v3/insider-trading?symbol={symbol}&page=0&apikey={api_key}'
print(f"URL: {url_v3[:80]}...")

try:
    r = requests.get(url_v3, timeout=10)
    print(f"Status: {r.status_code}")
    data = r.json()
    if isinstance(data, list) and len(data) > 0:
        print(f"✅ v3: {len(data)} items")
        print(f"   Sample: {data[0].get('transactionDate')} - {data[0].get('reportingName')}")
    elif isinstance(data, dict) and 'Error Message' in data:
        print(f"❌ v3 Error: {data['Error Message']}")
    else:
        print(f"⚠️  v3: Empty or unexpected response")
        print(f"   Response: {data}")
except Exception as e:
    print(f"❌ v3 Exception: {e}")

# Test v4 (correct endpoint)
print("\n2️⃣ Testing v4 endpoint (✅ CORRECT):")
url_v4 = f'https://financialmodelingprep.com/api/v4/insider-trading?symbol={symbol}&page=0&apikey={api_key}'
print(f"URL: {url_v4[:80]}...")

try:
    r = requests.get(url_v4, timeout=10)
    print(f"Status: {r.status_code}")
    data = r.json()
    if isinstance(data, list) and len(data) > 0:
        print(f"✅ v4: {len(data)} items")
        print(f"   Sample: {data[0].get('transactionDate')} - {data[0].get('reportingName')}")
        print(f"   Transaction: {data[0].get('transactionType')}")
    elif isinstance(data, dict) and 'Error Message' in data:
        print(f"❌ v4 Error: {data['Error Message']}")
    else:
        print(f"⚠️  v4: Empty or unexpected response")
        print(f"   Response: {data}")
except Exception as e:
    print(f"❌ v4 Exception: {e}")

print("\n" + "="*80)
print("CONCLUSION")
print("="*80)
print("✅ The code has been updated to use v4 endpoint")
print("✅ src/screener/ingest.py now uses /api/v4/insider-trading")
print("")
print("If v4 returns data above, insider trading should now work!")
