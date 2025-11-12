#!/usr/bin/env python3
"""
Test if FMP API returns insider trading data.
This helps diagnose if it's a plan limitation or symbol issue.
"""
import os
import sys
import yaml

sys.path.insert(0, 'src/screener')

print("="*80)
print("🔍 Testing Insider Trading API Access")
print("="*80)

# Load config
with open('settings.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Get API key
api_key = os.getenv('FMP_API_KEY')
if not api_key:
    api_key = config['fmp'].get('api_key')
    if api_key and api_key.startswith('${'):
        print("\n❌ FMP_API_KEY not set in environment")
        print("Set it with: export FMP_API_KEY='your_key'")
        sys.exit(1)

print(f"\n✓ API Key: {api_key[:10]}...{api_key[-4:]}")

# Import FMPClient
from ingest import FMPClient

client = FMPClient(api_key, config)

# Test with well-known stocks that should have insider trading
test_symbols = ['AAPL', 'MSFT', 'GOOGL', 'META', 'NVDA']

print(f"\n📊 Testing insider trading data for {len(test_symbols)} symbols:")
print("-"*80)

for symbol in test_symbols:
    try:
        data = client.get_insider_trading(symbol, limit=10)
        
        if data:
            print(f"\n✅ {symbol}: {len(data)} insider transactions found")
            if len(data) > 0:
                latest = data[0]
                print(f"   Latest: {latest.get('transactionDate')} - {latest.get('reportingName')} - {latest.get('transactionType')}")
        else:
            print(f"\n⚠️  {symbol}: No data returned (empty list)")
            
    except Exception as e:
        print(f"\n❌ {symbol}: API Error - {e}")

print("\n" + "="*80)
print("DIAGNOSIS:")
print("="*80)

print("""
If you see:
- ✅ "X insider transactions found" → Your API key HAS access to insider trading
- ⚠️  "No data returned" → Either:
  - Your FMP plan doesn't include insider trading
  - The specific symbol has no insider trades
  - API is having issues

If ALL symbols show "No data", your plan likely doesn't include this feature.
You need Professional+ plan for insider trading data.
""")
