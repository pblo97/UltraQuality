#!/usr/bin/env python3
"""Quick test of insider trading endpoint"""
import os
import requests

api_key = os.getenv('FMP_API_KEY')
if not api_key:
    print("Set FMP_API_KEY first: export FMP_API_KEY='your_key'")
    exit(1)

symbols = ['AAPL', 'MSFT', 'NVDA']

for symbol in symbols:
    url = f'https://financialmodelingprep.com/api/v4/insider-trading?symbol={symbol}&limit=10&apikey={api_key}'
    
    print(f"\n🔍 Testing {symbol}:")
    print(f"URL: {url[:80]}...")
    
    try:
        response = requests.get(url, timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Result: {len(data) if isinstance(data, list) else 'not a list'} items")
            if isinstance(data, list) and len(data) > 0:
                print(f"✅ First transaction: {data[0].get('transactionDate')} - {data[0].get('reportingName')}")
            elif isinstance(data, dict) and 'Error Message' in data:
                print(f"❌ API Error: {data['Error Message']}")
            else:
                print(f"⚠️  Empty or unexpected response")
        else:
            print(f"❌ HTTP Error: {response.text[:200]}")
    except Exception as e:
        print(f"❌ Exception: {e}")
