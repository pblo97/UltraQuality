#!/usr/bin/env python3
"""
Test del módulo Technical Analyzer

Testea las funcionalidades básicas del análisis técnico.
"""

import sys
from pathlib import Path
import yaml

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from screener.ingest import FMPClient
from screener.cache import CachedFMPClient
from screener.technical import TechnicalAnalyzer


def test_technical_analyzer():
    """Test básico del TechnicalAnalyzer."""

    print("\n" + "="*80)
    print("TEST: Technical Analyzer")
    print("="*80 + "\n")

    # Load config
    with open('settings.yaml') as f:
        config = yaml.safe_load(f)

    # Setup FMP client
    api_key = config['fmp']['api_key']
    fmp_base = FMPClient(api_key, config['fmp'])
    fmp = CachedFMPClient(fmp_base, cache_dir='.cache_test')

    # Initialize analyzer
    analyzer = TechnicalAnalyzer(fmp)

    # Test symbols
    test_cases = [
        ('AAPL', 'Technology'),
        ('NVDA', 'Technology'),
        ('JPM', 'Financials'),
        ('XOM', 'Energy'),
    ]

    for symbol, sector in test_cases:
        print(f"\n{'='*80}")
        print(f"Analyzing: {symbol} ({sector})")
        print(f"{'='*80}")

        try:
            # Analyze
            result = analyzer.analyze(symbol, sector=sector)

            # Display results
            print(f"\nScore: {result['score']:.0f}/100")
            print(f"Signal: {result['signal']}")
            print(f"\nComponents:")
            print(f"  Momentum (12M): {result['component_scores']['momentum']:.0f}/35")
            print(f"    - Return: {result['momentum_12m']:+.1f}%")
            print(f"    - Status: {result['momentum_status']}")
            print(f"  Sector: {result['component_scores']['sector']:.0f}/25")
            print(f"    - Sector Return: {result['sector_momentum_6m']:+.1f}%")
            print(f"    - Relative Strength: {result['relative_strength']:+.1f}%")
            print(f"    - Status: {result['sector_status']}")
            print(f"  Trend: {result['component_scores']['trend']:.0f}/25")
            print(f"    - Trend: {result['trend']}")
            print(f"    - Distance MA200: {result['distance_from_ma200']:+.1f}%")
            print(f"  Volume: {result['component_scores']['volume']:.0f}/15")
            print(f"    - Status: {result['volume_status']}")

            # Warnings
            if result['warnings']:
                print(f"\n⚠️  Warnings ({len(result['warnings'])}):")
                for w in result['warnings']:
                    print(f"  - [{w['severity']}] {w['message']}")
            else:
                print(f"\n✅ No warnings")

            print(f"\n✅ Test passed for {symbol}")

        except Exception as e:
            print(f"\n❌ Test failed for {symbol}: {str(e)}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*80}")
    print("TEST COMPLETE")
    print(f"{'='*80}\n")


if __name__ == '__main__':
    test_technical_analyzer()
