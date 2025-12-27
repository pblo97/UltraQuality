import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from screener.ingest import FMPClient
import yaml

config_file = 'settings_premium.yaml' if os.path.exists('settings_premium.yaml') else 'settings.yaml'
with open(config_file, 'r') as f:
    config = yaml.safe_load(f)

api_key = "qGDE52LhIJ9CQSyRwKpAzjLXeLP4Pwkt"
fmp = FMPClient(api_key, config)

# Test with AAPL
print("Testing AAPL...")
print("\n1. Senate Trading:")
result = fmp.get_senate_trading('AAPL')
print(f"   Length: {len(result) if result else 0}")
if result and len(result) > 0:
    print(f"   First item: {result[0]}")

print("\n2. Revenue Geographic:")
result = fmp.get_revenue_geographic_segmentation('AAPL', period='annual')
print(f"   Length: {len(result) if result else 0}")
if result and len(result) > 0:
    print(f"   Keys: {result[0].keys()}")

print("\n3. Earnings Surprises:")
result = fmp.get_earnings_surprises('AAPL')
print(f"   Length: {len(result) if result else 0}")
if result and len(result) > 0:
    print(f"   First item: {result[0]}")

print("\n4. Price Target Consensus:")
result = fmp.get_price_target_consensus('AAPL')
print(f"   Length: {len(result) if result else 0}")
if result and len(result) > 0:
    print(f"   First item: {result[0]}")

print("\n5. Upgrades/Downgrades Consensus:")
result = fmp.get_upgrades_downgrades_consensus('AAPL')
print(f"   Length: {len(result) if result else 0}")
if result and len(result) > 0:
    print(f"   First item: {result[0]}")
