#!/usr/bin/env python3
"""
Test script to validate risk management recommendations.

Tests with GOOG (known to be overextended at +58% above MA200)
"""

import sys
sys.path.insert(0, 'src')

import os
import yaml
from screener.ingest import FMPClient
from screener.cache import CachedFMPClient
from screener.technical.analyzer import EnhancedTechnicalAnalyzer
import json

def load_api_key():
    """Load API key from environment or .env file."""
    api_key = os.environ.get('FMP_API_KEY')
    if api_key:
        return api_key

    if os.path.exists('.env'):
        with open('.env') as f:
            for line in f:
                if line.strip().startswith('FMP_API_KEY='):
                    api_key = line.split('=', 1)[1].strip()
                    if api_key and api_key != 'YOUR_FMP_API_KEY_HERE':
                        return api_key

    return None

def main():
    print("="*80)
    print("RISK MANAGEMENT SYSTEM TEST")
    print("="*80)

    # Load config
    with open('settings.yaml') as f:
        config = yaml.safe_load(f)

    # Load API key
    api_key = load_api_key()
    if not api_key:
        print("❌ No API key found. Set FMP_API_KEY in .env")
        sys.exit(1)

    print(f"✅ API Key: {api_key[:10]}...")

    # Initialize clients
    fmp_base = FMPClient(api_key, config['fmp'])
    fmp = CachedFMPClient(fmp_base, cache_dir='.cache')

    # Initialize analyzer
    analyzer = EnhancedTechnicalAnalyzer(fmp)

    # Test with GOOG (overextended stock)
    print("\n" + "="*80)
    print("Testing with GOOG (Known overextended: +58% above MA200)")
    print("="*80)

    result = analyzer.analyze('GOOG', sector='Technology', country='USA')

    # Display key results
    print(f"\n📊 TECHNICAL SCORE: {result['score']}/100")
    print(f"📈 SIGNAL: {result['signal']}")
    print(f"🌍 MARKET REGIME: {result['market_regime']}")

    # Display overextension risk
    print(f"\n⚠️  OVEREXTENSION RISK: {result['overextension_risk']}/7 ({result['overextension_level']})")
    print(f"📏 Distance from MA200: {result['distance_from_ma200']:+.1f}%")

    # Display risk management recommendations
    risk_mgmt = result.get('risk_management', {})

    if risk_mgmt:
        print("\n" + "="*80)
        print("RISK MANAGEMENT RECOMMENDATIONS")
        print("="*80)

        # 1. Position Sizing
        print("\n1️⃣  POSITION SIZING:")
        pos_sizing = risk_mgmt.get('position_sizing', {})
        print(f"   Recommended Size: {pos_sizing.get('recommended_size', 'N/A')}")
        print(f"   Max Portfolio Weight: {pos_sizing.get('max_portfolio_weight', 'N/A')}")
        print(f"   Rationale: {pos_sizing.get('rationale', 'N/A')}")

        # 2. Entry Strategy
        print("\n2️⃣  ENTRY STRATEGY:")
        entry = risk_mgmt.get('entry_strategy', {})
        print(f"   Strategy: {entry.get('strategy', 'N/A')}")
        if 'tranche_1' in entry:
            print(f"   Tranche 1: {entry['tranche_1']}")
        if 'tranche_2' in entry:
            print(f"   Tranche 2: {entry['tranche_2']}")
        if 'tranche_3' in entry:
            print(f"   Tranche 3: {entry['tranche_3']}")
        print(f"   Rationale: {entry.get('rationale', 'N/A')}")

        # 3. Stop Loss
        print("\n3️⃣  STOP LOSS:")
        stop_loss = risk_mgmt.get('stop_loss', {})
        print(f"   Recommended: {stop_loss.get('recommended', 'N/A').upper()}")
        stops = stop_loss.get('stops', {})
        for stop_type in ['aggressive', 'moderate', 'conservative']:
            if stop_type in stops:
                s = stops[stop_type]
                print(f"   {stop_type.upper()}: {s.get('level', 'N/A')} ({s.get('distance', 'N/A')})")

        # 4. Profit Taking
        print("\n4️⃣  PROFIT TAKING:")
        profit = risk_mgmt.get('profit_taking', {})
        print(f"   Strategy: {profit.get('strategy', 'N/A')}")
        for key, value in profit.items():
            if key not in ['strategy', 'rationale']:
                print(f"   {key}: {value}")

        # 5. Options Strategies
        print("\n5️⃣  OPTIONS STRATEGIES:")
        options = risk_mgmt.get('options_strategies', [])
        print(f"   {len(options)} strategies recommended:")
        for i, strategy in enumerate(options, 1):
            print(f"\n   {i}. {strategy.get('name', 'N/A')}")
            print(f"      When: {strategy.get('when', 'N/A')}")
            print(f"      Structure: {strategy.get('structure', 'N/A')}")
            if 'rationale' in strategy:
                print(f"      Rationale: {strategy['rationale']}")
            if 'evidence' in strategy:
                print(f"      Evidence: {strategy['evidence']}")

    # Display warnings
    print("\n" + "="*80)
    print("WARNINGS")
    print("="*80)

    warnings = result.get('warnings', [])
    if warnings:
        for w in warnings:
            severity = w.get('type', 'INFO')
            message = w.get('message', '')
            icon = '🔴' if severity == 'HIGH' else '🟡' if severity == 'MEDIUM' else '🔵'
            print(f"{icon} [{severity}] {message}")
    else:
        print("✅ No warnings")

    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)

    # Save full result to JSON for inspection
    with open('test_risk_management_result.json', 'w') as f:
        json.dump(result, f, indent=2, default=str)

    print("\n✅ Full result saved to: test_risk_management_result.json")

if __name__ == '__main__':
    main()
