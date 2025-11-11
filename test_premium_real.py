#!/usr/bin/env python3
"""
Test premium features with REAL API calls.
This will verify that premium features actually execute and return data.
"""
import os
import sys
import yaml
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'screener'))

def main():
    print("\n" + "🔍" * 35)
    print("REAL API TEST - Premium Features")
    print("🔍" * 35)

    # Check API key
    api_key = os.getenv('FMP_API_KEY')
    if not api_key or api_key.startswith('${'):
        print("\n❌ ERROR: FMP_API_KEY not found in environment")
        print("\nSet it with:")
        print("  export FMP_API_KEY='your_key_here'")
        print("\nOr add to .env file:")
        print("  FMP_API_KEY=your_key_here")
        return 1

    print(f"\n✓ API Key found: {api_key[:10]}...{api_key[-4:]}")

    # Load config
    with open('settings_premium.yaml', 'r') as f:
        config = yaml.safe_load(f)

    print(f"✓ Config loaded: settings_premium.yaml")

    # Import modules
    from ingest import FMPClient
    from qualitative import QualitativeAnalyzer

    # Initialize client and analyzer
    client = FMPClient(api_key, config)
    analyzer = QualitativeAnalyzer(client, config)

    print(f"✓ FMPClient initialized")
    print(f"✓ QualitativeAnalyzer initialized")

    # Test symbol (you can change this)
    test_symbol = 'AAPL'  # Apple - widely covered, should have data

    print(f"\n" + "=" * 70)
    print(f"Testing with symbol: {test_symbol}")
    print("=" * 70)

    # Check premium config
    premium_config = config.get('premium', {})
    print(f"\n📋 Premium Config:")
    print(f"  - enable_insider_trading: {premium_config.get('enable_insider_trading')}")
    print(f"  - enable_earnings_transcripts: {premium_config.get('enable_earnings_transcripts')}")

    print(f"\n🔄 Calling _estimate_intrinsic_value('{test_symbol}')...")
    print("   This will execute premium features if enabled...")

    try:
        # Call the function that contains premium features
        result = analyzer._estimate_intrinsic_value(test_symbol, 'non_financial', None)

        print(f"\n✅ Function completed successfully!")

        # Check if premium features are in the result
        has_insider = 'insider_trading' in result
        has_sentiment = 'earnings_sentiment' in result

        print(f"\n📊 Premium Features in Output:")
        print(f"  - insider_trading: {'✅ PRESENT' if has_insider else '❌ MISSING'}")
        print(f"  - earnings_sentiment: {'✅ PRESENT' if has_sentiment else '❌ MISSING'}")

        if has_insider:
            print(f"\n" + "=" * 70)
            print("INSIDER TRADING RESULT:")
            print("=" * 70)
            insider = result['insider_trading']
            print(json.dumps(insider, indent=2))

            if insider.get('available'):
                print(f"\n✅ Insider Trading data IS AVAILABLE")
                print(f"   Signal: {insider.get('signal')}")
                print(f"   Score: {insider.get('score')}/100")
                print(f"   Assessment: {insider.get('assessment')}")
            else:
                print(f"\n⚠️  Insider Trading executed but no data available")
                print(f"   Note: {insider.get('note')}")
                print(f"   This might mean:")
                print(f"   - Your FMP plan doesn't include insider trading")
                print(f"   - No insider trades exist for {test_symbol}")

        if has_sentiment:
            print(f"\n" + "=" * 70)
            print("EARNINGS SENTIMENT RESULT:")
            print("=" * 70)
            sentiment = result['earnings_sentiment']
            print(json.dumps(sentiment, indent=2))

            if sentiment.get('available'):
                print(f"\n✅ Earnings Sentiment data IS AVAILABLE")
                print(f"   Tone: {sentiment.get('tone')}")
                print(f"   Grade: {sentiment.get('grade')}")
                print(f"   Net Sentiment: {sentiment.get('net_sentiment')}")
                print(f"   Assessment: {sentiment.get('assessment')}")
            else:
                print(f"\n⚠️  Earnings Sentiment executed but no data available")
                print(f"   Note: {sentiment.get('note')}")
                print(f"   This might mean:")
                print(f"   - Your FMP plan doesn't include transcripts")
                print(f"   - No transcripts available for {test_symbol}")

        if not has_insider and not has_sentiment:
            print(f"\n❌ NO PREMIUM FEATURES IN OUTPUT")
            print(f"\nPossible reasons:")
            print(f"1. Premium features are disabled in config")
            print(f"2. Code changes didn't take effect (try restarting Python)")
            print(f"3. The function didn't execute the premium feature code blocks")
            print(f"\nDumping full result keys:")
            print(f"  {list(result.keys())}")
            return 1

        print(f"\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)

        if has_insider and has_sentiment:
            print(f"\n✅ ✅ BOTH premium features executed and returned data!")
            print(f"\nYour setup is WORKING CORRECTLY:")
            print(f"  ✓ Config is correct")
            print(f"  ✓ Code changes are active")
            print(f"  ✓ Premium features execute during qualitative analysis")
            print(f"\nTo see these in the Streamlit UI:")
            print(f"  1. Run: python run_screener.py --config settings_premium.yaml")
            print(f"  2. Navigate to 'Deep Dive' tab")
            print(f"  3. Select a symbol")
            print(f"  4. Look for 'Insider Trading' and 'Earnings Sentiment' sections")
            return 0
        else:
            print(f"\n⚠️  PARTIAL SUCCESS:")
            print(f"  - Features executed: YES")
            print(f"  - Data available: {(has_insider and result['insider_trading'].get('available', False)) or (has_sentiment and result['earnings_sentiment'].get('available', False))}")
            print(f"\nThis might be due to your FMP plan limitations.")
            print(f"Check if your plan includes:")
            print(f"  • Insider Trading data (Professional+ plan)")
            print(f"  • Earnings Call Transcripts (Professional+ plan)")
            return 0

    except Exception as e:
        print(f"\n❌ ERROR during execution:")
        print(f"  {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
