#!/usr/bin/env python3
"""
Test premium features execution flow with detailed logging.
This simulates exactly what happens when you run the screener.
"""
import os
import sys
import yaml
import logging
from pathlib import Path

# Setup detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s [%(name)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'screener'))

def main():
    print("\n" + "="*80)
    print("PREMIUM FEATURES EXECUTION FLOW TEST")
    print("="*80)

    # Step 1: Check API key
    api_key = os.getenv('FMP_API_KEY')
    if not api_key or api_key.startswith('${'):
        print("\n❌ ERROR: FMP_API_KEY not found")
        print("Set it with: export FMP_API_KEY='your_key'")
        return 1

    print(f"\n✓ API Key: {api_key[:10]}...{api_key[-4:]}")

    # Step 2: Load config
    print("\n" + "-"*80)
    print("STEP 1: Loading Config")
    print("-"*80)

    with open('settings_premium.yaml', 'r') as f:
        config = yaml.safe_load(f)

    premium_config = config.get('premium', {})
    cache_config = config.get('cache', {})

    print(f"✓ Config loaded")
    print(f"\n  Cache settings:")
    print(f"    - ttl_universe_hours: {cache_config.get('ttl_universe_hours')}")
    print(f"    - ttl_symbol_hours: {cache_config.get('ttl_symbol_hours')}")
    print(f"    - ttl_qualitative_hours: {cache_config.get('ttl_qualitative_hours')}")

    print(f"\n  Premium settings:")
    print(f"    - enable_insider_trading: {premium_config.get('enable_insider_trading')}")
    print(f"    - enable_earnings_transcripts: {premium_config.get('enable_earnings_transcripts')}")

    # Step 3: Initialize FMPClient
    print("\n" + "-"*80)
    print("STEP 2: Initializing FMPClient")
    print("-"*80)

    from ingest import FMPClient

    print(f"Calling: FMPClient(api_key, config)")
    client = FMPClient(api_key, config)

    print(f"✓ FMPClient initialized")
    print(f"  - Rate limit: {client.rate_limiter.rate} RPS")
    print(f"  - Cache TTLs:")
    print(f"    - Universe: {client.cache_universe.ttl.total_seconds()/3600:.1f}h")
    print(f"    - Symbol: {client.cache_symbol.ttl.total_seconds()/3600:.1f}h")
    print(f"    - Qualitative: {client.cache_qualitative.ttl.total_seconds()/3600:.1f}h")

    # Step 4: Initialize QualitativeAnalyzer
    print("\n" + "-"*80)
    print("STEP 3: Initializing QualitativeAnalyzer")
    print("-"*80)

    from qualitative import QualitativeAnalyzer

    print(f"Calling: QualitativeAnalyzer(client, config)")
    analyzer = QualitativeAnalyzer(client, config)

    print(f"✓ QualitativeAnalyzer initialized")
    print(f"  - Config accessible: {analyzer.config is not None}")

    # Verify analyzer can see premium config
    analyzer_premium = analyzer.config.get('premium', {})
    print(f"  - Premium config in analyzer:")
    print(f"    - enable_insider_trading: {analyzer_premium.get('enable_insider_trading')}")
    print(f"    - enable_earnings_transcripts: {analyzer_premium.get('enable_earnings_transcripts')}")

    # Step 5: Call intrinsic value estimation (this is where premium features execute)
    print("\n" + "-"*80)
    print("STEP 4: Calling _estimate_intrinsic_value()")
    print("-"*80)
    print("\nThis is where premium features should execute...")
    print("Watch for log messages with 🔍 ✓ and ❌")
    print("\n" + "~"*80)

    test_symbol = 'AAPL'

    try:
        result = analyzer._estimate_intrinsic_value(test_symbol, 'non_financial', None)

        print("~"*80)
        print("\n✓ Function completed")

        # Step 6: Check results
        print("\n" + "-"*80)
        print("STEP 5: Checking Results")
        print("-"*80)

        has_insider = 'insider_trading' in result
        has_sentiment = 'earnings_sentiment' in result

        print(f"\n📊 Premium features in result:")
        print(f"  - insider_trading: {'✅ YES' if has_insider else '❌ NO'}")
        print(f"  - earnings_sentiment: {'✅ YES' if has_sentiment else '❌ NO'}")

        if has_insider:
            insider = result['insider_trading']
            print(f"\n  Insider Trading details:")
            print(f"    - available: {insider.get('available')}")
            if insider.get('available'):
                print(f"    - signal: {insider.get('signal')}")
                print(f"    - score: {insider.get('score')}")
            else:
                print(f"    - note: {insider.get('note')}")

        if has_sentiment:
            sentiment = result['earnings_sentiment']
            print(f"\n  Earnings Sentiment details:")
            print(f"    - available: {sentiment.get('available')}")
            if sentiment.get('available'):
                print(f"    - tone: {sentiment.get('tone')}")
                print(f"    - grade: {sentiment.get('grade')}")
            else:
                print(f"    - note: {sentiment.get('note')}")

        # Summary
        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)

        if has_insider and has_sentiment:
            print("\n✅ SUCCESS! Both premium features executed and are in the result")
            print("\n  They are located at:")
            print("    result['insider_trading']")
            print("    result['earnings_sentiment']")
            print("\n  When returned from analyze_symbol(), they will be at:")
            print("    summary['intrinsic_value']['insider_trading']")
            print("    summary['intrinsic_value']['earnings_sentiment']")
            return 0
        elif not has_insider and not has_sentiment:
            print("\n❌ PROBLEM: NO premium features in result")
            print("\n  Possible causes:")
            print("    1. Premium config didn't reach the function")
            print("    2. The if conditions didn't pass")
            print("    3. Functions returned None/empty")
            print("\n  Check the log messages above (🔍 ✓ ❌)")
            print("  They should show what happened during execution")
            return 1
        else:
            print("\n⚠️  PARTIAL: Only some features present")
            print(f"    - Has insider: {has_insider}")
            print(f"    - Has sentiment: {has_sentiment}")
            print("\n  Check log messages to see which one failed")
            return 0

    except Exception as e:
        print("\n❌ ERROR during execution:")
        print(f"  {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
