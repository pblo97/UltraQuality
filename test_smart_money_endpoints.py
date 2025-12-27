"""
Test script para verificar los endpoints de smart money.
"""
import sys
import os
import yaml

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from screener.ingest import FMPClient

# Load config
config_file = 'settings_premium.yaml' if os.path.exists('settings_premium.yaml') else 'settings.yaml'
with open(config_file, 'r') as f:
    config = yaml.safe_load(f)

# Get API key
api_key = os.getenv('FMP_API_KEY') or config['fmp'].get('api_key')

if not api_key or api_key.startswith('${'):
    print("ERROR: No FMP API key found!")
    sys.exit(1)

print(f"Using API key: {api_key[:10]}...")
print(f"Config file: {config_file}")
print("")

# Initialize client
fmp = FMPClient(api_key, config)

# Test symbol
symbol = 'META'
print(f"Testing endpoints for {symbol}...\n")

# Test 1: Senate Trading
print("=" * 60)
print("TEST 1: Senate Trading")
print("=" * 60)
try:
    result = fmp.get_senate_trading(symbol)
    print(f"Result type: {type(result)}")
    print(f"Result length: {len(result) if result else 0}")
    if result:
        print(f"First item: {result[0]}")
    else:
        print("No data returned")
except Exception as e:
    print(f"ERROR: {e}")

print("\n")

# Test 2: Revenue Geographic
print("=" * 60)
print("TEST 2: Revenue Geographic Segmentation")
print("=" * 60)
try:
    result = fmp.get_revenue_geographic_segmentation(symbol)
    print(f"Result type: {type(result)}")
    print(f"Result length: {len(result) if result else 0}")
    if result:
        print(f"First item: {result[0]}")
    else:
        print("No data returned")
except Exception as e:
    print(f"ERROR: {e}")

print("\n")

# Test 3: Earnings Surprises
print("=" * 60)
print("TEST 3: Earnings Surprises")
print("=" * 60)
try:
    result = fmp.get_earnings_surprises(symbol)
    print(f"Result type: {type(result)}")
    print(f"Result length: {len(result) if result else 0}")
    if result:
        print(f"First 3 items:")
        for i, item in enumerate(result[:3]):
            print(f"  {i+1}. {item}")
    else:
        print("No data returned")
except Exception as e:
    print(f"ERROR: {e}")

print("\n")

# Test 4: Price Target Consensus
print("=" * 60)
print("TEST 4: Price Target Consensus")
print("=" * 60)
try:
    result = fmp.get_price_target_consensus(symbol)
    print(f"Result type: {type(result)}")
    print(f"Result length: {len(result) if result else 0}")
    if result:
        print(f"First item: {result[0]}")
    else:
        print("No data returned")
except Exception as e:
    print(f"ERROR: {e}")

print("\n")

# Test 5: Upgrades/Downgrades Consensus
print("=" * 60)
print("TEST 5: Upgrades/Downgrades Consensus")
print("=" * 60)
try:
    result = fmp.get_upgrades_downgrades_consensus(symbol)
    print(f"Result type: {type(result)}")
    print(f"Result length: {len(result) if result else 0}")
    if result:
        print(f"First item: {result[0]}")
    else:
        print("No data returned")
except Exception as e:
    print(f"ERROR: {e}")

print("\n" + "=" * 60)
print("TESTS COMPLETE")
print("=" * 60)
