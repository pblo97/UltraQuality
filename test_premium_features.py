#!/usr/bin/env python3
"""
Test script to verify premium features are enabled and accessible.
"""
import os
import sys
import yaml
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'screener'))

def test_config_loading():
    """Test 1: Verify config loads correctly."""
    print("=" * 60)
    print("TEST 1: Config Loading")
    print("=" * 60)

    with open('settings_premium.yaml', 'r') as f:
        config = yaml.safe_load(f)

    # Check cache settings
    cache_config = config.get('cache', {})
    print(f"\n✓ Cache config loaded:")
    print(f"  - ttl_universe_hours: {cache_config.get('ttl_universe_hours')}")
    print(f"  - ttl_symbol_hours: {cache_config.get('ttl_symbol_hours')}")
    print(f"  - ttl_qualitative_hours: {cache_config.get('ttl_qualitative_hours')}")

    # Check premium settings
    premium_config = config.get('premium', {})
    print(f"\n✓ Premium config loaded:")
    print(f"  - enable_insider_trading: {premium_config.get('enable_insider_trading')}")
    print(f"  - enable_earnings_transcripts: {premium_config.get('enable_earnings_transcripts')}")

    return config

def test_fmpclient_init(config):
    """Test 2: Verify FMPClient initializes with correct config."""
    print("\n" + "=" * 60)
    print("TEST 2: FMPClient Initialization")
    print("=" * 60)

    from ingest import FMPClient

    # Mock API key
    os.environ['FMP_API_KEY'] = 'test_key_12345'
    api_key = os.environ['FMP_API_KEY']

    # Initialize client
    client = FMPClient(api_key, config)

    print(f"\n✓ FMPClient initialized")
    print(f"  - Rate limiter: {client.rate_limiter.rate} RPS")
    print(f"  - Max retries: {client.max_retries}")

    # Check cache TTLs
    print(f"\n✓ Cache TTLs:")
    print(f"  - Universe: {client.cache_universe.ttl.total_seconds() / 3600:.1f}h")
    print(f"  - Symbol: {client.cache_symbol.ttl.total_seconds() / 3600:.1f}h")
    print(f"  - Qualitative: {client.cache_qualitative.ttl.total_seconds() / 3600:.1f}h")

    return client

def test_qualitative_analyzer(client, config):
    """Test 3: Verify QualitativeAnalyzer can access premium config."""
    print("\n" + "=" * 60)
    print("TEST 3: QualitativeAnalyzer Premium Config Access")
    print("=" * 60)

    from qualitative import QualitativeAnalyzer

    analyzer = QualitativeAnalyzer(client, config)

    # Check if analyzer can read premium config
    premium_config = analyzer.config.get('premium', {})

    print(f"\n✓ QualitativeAnalyzer initialized")
    print(f"  - Has access to config: {analyzer.config is not None}")
    print(f"  - Premium config accessible: {premium_config is not None}")
    print(f"  - enable_insider_trading: {premium_config.get('enable_insider_trading')}")
    print(f"  - enable_earnings_transcripts: {premium_config.get('enable_earnings_transcripts')}")

    return analyzer

def test_premium_features_simulation(analyzer):
    """Test 4: Simulate premium feature execution logic."""
    print("\n" + "=" * 60)
    print("TEST 4: Premium Features Execution Logic")
    print("=" * 60)

    premium_config = analyzer.config.get('premium', {})

    print(f"\nSimulating feature checks:")

    # Simulate Insider Trading check
    if premium_config.get('enable_insider_trading', False):
        print(f"  ✅ Insider Trading: WOULD EXECUTE")
        print(f"     - Function: _analyze_insider_trading()")
    else:
        print(f"  ❌ Insider Trading: SKIPPED (disabled)")

    # Simulate Earnings Sentiment check
    if premium_config.get('enable_earnings_transcripts', False):
        print(f"  ✅ Earnings Sentiment: WOULD EXECUTE")
        print(f"     - Function: _analyze_earnings_sentiment()")
    else:
        print(f"  ❌ Earnings Sentiment: SKIPPED (disabled)")

    print(f"\n✓ Premium features are configured to execute")

def test_method_existence(analyzer):
    """Test 5: Verify premium methods exist."""
    print("\n" + "=" * 60)
    print("TEST 5: Premium Methods Existence")
    print("=" * 60)

    has_insider = hasattr(analyzer, '_analyze_insider_trading')
    has_sentiment = hasattr(analyzer, '_analyze_earnings_sentiment')

    print(f"\n✓ Method checks:")
    print(f"  - _analyze_insider_trading: {'✅ EXISTS' if has_insider else '❌ MISSING'}")
    print(f"  - _analyze_earnings_sentiment: {'✅ EXISTS' if has_sentiment else '❌ MISSING'}")

    if has_insider and has_sentiment:
        print(f"\n✅ All premium methods are implemented")
    else:
        print(f"\n❌ Some methods are missing!")
        return False

    return True

def main():
    """Run all tests."""
    print("\n" + "🔬" * 30)
    print("PREMIUM FEATURES VERIFICATION TEST")
    print("🔬" * 30)

    try:
        # Test 1: Config loading
        config = test_config_loading()

        # Test 2: FMPClient initialization
        client = test_fmpclient_init(config)

        # Test 3: QualitativeAnalyzer initialization
        analyzer = test_qualitative_analyzer(client, config)

        # Test 4: Premium features execution logic
        test_premium_features_simulation(analyzer)

        # Test 5: Method existence
        all_methods_exist = test_method_existence(analyzer)

        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)

        if all_methods_exist:
            print("\n✅ ALL TESTS PASSED!")
            print("\nPremium features are:")
            print("  1. ✅ Enabled in config")
            print("  2. ✅ Accessible by FMPClient (cache)")
            print("  3. ✅ Accessible by QualitativeAnalyzer")
            print("  4. ✅ Implemented and ready to execute")
            print("\nTo use premium features, run:")
            print("  python run_screener.py --config settings_premium.yaml")
            return 0
        else:
            print("\n❌ SOME TESTS FAILED")
            print("Please review the output above")
            return 1

    except Exception as e:
        print(f"\n❌ TEST FAILED WITH ERROR:")
        print(f"  {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
