#!/usr/bin/env python3
"""Quick test to see GOOG's overextension risk."""

import sys
sys.path.insert(0, 'src')

import os
import yaml
from screener.ingest import FMPClient
from screener.cache import CachedFMPClient
from screener.technical.analyzer import EnhancedTechnicalAnalyzer

def load_api_key():
    """Load API key from .env file."""
    if os.path.exists('.env'):
        with open('.env') as f:
            for line in f:
                if line.strip().startswith('FMP_API_KEY='):
                    api_key = line.split('=', 1)[1].strip()
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
    print("   Edita .env y reemplaza YOUR_FMP_API_KEY_HERE con tu key real")
    sys.exit(1)

print(f"✅ API Key configurada: {api_key[:10]}...")

# Initialize
fmp_base = FMPClient(api_key, config['fmp'])
fmp = CachedFMPClient(fmp_base, cache_dir='.cache')
analyzer = EnhancedTechnicalAnalyzer(fmp)

# Test GOOG
print("\n" + "="*60)
print("Analizando GOOG...")
print("="*60)

result = analyzer.analyze('GOOG', sector='Technology', country='USA')

print(f"\n📊 Technical Score: {result['score']}/100")
print(f"📈 Signal: {result['signal']}")
print(f"📏 Distance from MA200: {result['distance_from_ma200']:+.1f}%")
print(f"\n⚠️  OVEREXTENSION RISK: {result['overextension_risk']}/7")
print(f"🔴 OVEREXTENSION LEVEL: {result['overextension_level']}")

# Show recommendations
risk_mgmt = result.get('risk_management', {})
if risk_mgmt:
    entry = risk_mgmt.get('entry_strategy', {})
    print(f"\n🎯 Entry Strategy: {entry.get('strategy', 'N/A')}")

    options = risk_mgmt.get('options_strategies', [])
    print(f"\n📈 Options Strategies: {len(options)} recommended")
    for i, opt in enumerate(options[:3], 1):  # Show first 3
        print(f"   {i}. {opt.get('name', 'N/A')}")

print("\n" + "="*60)
