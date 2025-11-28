#!/usr/bin/env python3
"""Debug script to see why overextension risk is always 0."""

import sys
sys.path.insert(0, 'src')

import os
import yaml
from screener.ingest import FMPClient
from screener.cache import CachedFMPClient
from screener.technical.analyzer import EnhancedTechnicalAnalyzer

def load_api_key():
    """Load API key from multiple sources (same as Streamlit)."""
    # Try .streamlit/secrets.toml first
    secrets_file = '.streamlit/secrets.toml'
    if os.path.exists(secrets_file):
        import toml
        try:
            secrets = toml.load(secrets_file)
            api_key = secrets.get('fmp_api_key') or secrets.get('FMP_API_KEY')
            if api_key and api_key != 'YOUR_FMP_API_KEY_HERE':
                return api_key
        except:
            pass

    # Try .env file
    if os.path.exists('.env'):
        with open('.env') as f:
            for line in f:
                if line.strip().startswith('FMP_API_KEY='):
                    api_key = line.split('=', 1)[1].strip()
                    if api_key and api_key != 'YOUR_FMP_API_KEY_HERE':
                        return api_key

    # Try environment variable
    api_key = os.environ.get('FMP_API_KEY')
    if api_key and api_key != 'YOUR_FMP_API_KEY_HERE':
        return api_key

    return None

# Load config
with open('settings.yaml') as f:
    config = yaml.safe_load(f)

# Load API key
api_key = load_api_key()
if not api_key:
    print("❌ Configure tu API key en .env primero")
    sys.exit(1)

print(f"✅ API Key: {api_key[:10]}...")

# Initialize
fmp_base = FMPClient(api_key, config['fmp'])
fmp = CachedFMPClient(fmp_base, cache_dir='.cache')
analyzer = EnhancedTechnicalAnalyzer(fmp)

# Test with multiple stocks
stocks = [
    ('COST', 'Consumer Defensive'),  # Costco - el que probaste
    ('NVDA', 'Technology'),          # NVIDIA - típicamente sobreextendido
    ('AAPL', 'Technology'),          # Apple
    ('XOM', 'Energy'),               # Exxon
]

print("\n" + "="*80)
print("DEBUGGING OVEREXTENSION RISK")
print("="*80)

for symbol, sector in stocks:
    print(f"\n{'='*80}")
    print(f"Testing: {symbol} ({sector})")
    print('='*80)

    try:
        result = analyzer.analyze(symbol, sector=sector, country='USA')

        # Show key metrics
        print(f"\n📊 Technical Score: {result['score']}/100")
        print(f"📈 Signal: {result['signal']}")

        # Show distance from MA200 (this is the KEY metric)
        distance = result.get('distance_from_ma200', 0)
        print(f"\n📏 Distance from MA200: {distance:+.1f}%")

        # Show overextension risk
        overext_risk = result.get('overextension_risk', 0)
        overext_level = result.get('overextension_level', 'UNKNOWN')
        print(f"⚠️  Overextension Risk: {overext_risk}/7 ({overext_level})")

        # Show momentum metrics (used for parabolic detection)
        print(f"\n📈 Momentum:")
        print(f"   1M: {result.get('momentum_1m', 0):+.1f}%")
        print(f"   6M: {result.get('momentum_6m', 0):+.1f}%")
        print(f"   12M: {result.get('momentum_12m', 0):+.1f}%")

        # Show volatility (used for parabolic detection)
        print(f"\n📊 Volatility (12M): {result.get('volatility_12m', 0):.1f}%")

        # Show warnings
        warnings = result.get('warnings', [])
        overext_warnings = [w for w in warnings if 'overextension' in w.get('message', '').lower() or 'parabolic' in w.get('message', '').lower()]
        if overext_warnings:
            print(f"\n⚠️  Overextension Warnings:")
            for w in overext_warnings:
                print(f"   [{w.get('type', 'INFO')}] {w.get('message', '')}")
        else:
            print(f"\n✅ No overextension warnings")

        # Show entry strategy
        risk_mgmt = result.get('risk_management', {})
        if risk_mgmt:
            entry = risk_mgmt.get('entry_strategy', {})
            print(f"\n🎯 Entry Strategy: {entry.get('strategy', 'N/A')}")

        # Expected overextension calculation (manual)
        print(f"\n🔍 EXPECTED CALCULATION:")
        abs_distance = abs(distance)
        expected_points = 0

        if abs_distance > 60:
            expected_points += 4
            print(f"   Distance >60% → +4 points")
        elif abs_distance > 50:
            expected_points += 3
            print(f"   Distance >50% → +3 points")
        elif abs_distance > 40:
            expected_points += 2
            print(f"   Distance >40% → +2 points")
        elif abs_distance > 30:
            expected_points += 1
            print(f"   Distance >30% → +1 point")
        else:
            print(f"   Distance {abs_distance:.1f}% ≤30% → +0 points")

        volatility = result.get('volatility_12m', 0)
        mom_1m = result.get('momentum_1m', 0)

        if volatility > 40 and mom_1m > 15:
            expected_points += 2
            print(f"   Parabolic (vol {volatility:.1f}% + mom1M {mom_1m:+.1f}%) → +2 points")
        elif volatility > 35 and mom_1m > 10:
            expected_points += 1
            print(f"   High-vol momentum → +1 point")

        if mom_1m > 25:
            expected_points += 1
            print(f"   Blow-off top (mom1M {mom_1m:+.1f}%) → +1 point")

        print(f"\n   ➡️  EXPECTED TOTAL: {expected_points}/7")
        print(f"   ➡️  ACTUAL RESULT: {overext_risk}/7")

        if expected_points != overext_risk:
            print(f"\n   ⚠️  MISMATCH! Expected {expected_points} but got {overext_risk}")
        else:
            print(f"\n   ✅ Match! Calculation is correct.")

    except Exception as e:
        print(f"❌ Error analyzing {symbol}: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "="*80)
print("DEBUGGING COMPLETE")
print("="*80)
