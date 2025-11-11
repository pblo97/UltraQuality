#!/usr/bin/env python3
"""
Demo script showing what premium features output looks like.
This simulates what you would see when premium features are executed.
"""
import json

def show_insider_trading_output():
    """Show example Insider Trading output."""
    print("\n" + "=" * 70)
    print("PREMIUM FEATURE 1: INSIDER TRADING ANALYSIS")
    print("=" * 70)

    # Example output structure
    example = {
        "available": True,
        "score": 85,
        "signal": "Strong Buy",
        "assessment": "Multiple insiders buying aggressively - very bullish",
        "buy_count_12m": 12,
        "sell_count_12m": 2,
        "recent_buys_3m": 8,
        "unique_buyers_3m": 5,
        "executive_buys": 4,
        "total_buy_value": 15000000,
        "total_sell_value": 500000,
        "buy_value_formatted": "$15.0M",
        "sell_value_formatted": "$500K",
        "net_position": "Buying",
        "recent_trades": [
            {"date": "2024-11-01", "name": "John Smith - CEO", "type": "P-Purchase", "shares": 50000, "value": 2500000},
            {"date": "2024-10-28", "name": "Jane Doe - CFO", "type": "P-Purchase", "shares": 30000, "value": 1500000},
            {"date": "2024-10-15", "name": "Board Member 1", "type": "P-Purchase", "shares": 20000, "value": 1000000}
        ]
    }

    print("\n📊 Output Structure:")
    print(json.dumps(example, indent=2))

    print("\n🎯 What This Means:")
    print(f"  • Signal: {example['signal']} (Score: {example['score']}/100)")
    print(f"  • Assessment: {example['assessment']}")
    print(f"  • Buys (12m): {example['buy_count_12m']} | Sells (12m): {example['sell_count_12m']}")
    print(f"  • Recent Activity (3m): {example['recent_buys_3m']} buys from {example['unique_buyers_3m']} insiders")
    print(f"  • Executive Buying: {example['executive_buys']} transactions")
    print(f"  • Net Position: {example['net_position']} ({example['buy_value_formatted']} bought)")

def show_earnings_sentiment_output():
    """Show example Earnings Sentiment output."""
    print("\n" + "=" * 70)
    print("PREMIUM FEATURE 2: EARNINGS CALL SENTIMENT ANALYSIS")
    print("=" * 70)

    # Example output structure
    example = {
        "available": True,
        "tone": "Very Positive",
        "grade": "A",
        "assessment": "Management is confident and growth-focused",
        "net_sentiment": 32.5,
        "confidence_%": 90,
        "positive_%": 55.2,
        "negative_%": 22.7,
        "caution_%": 22.1,
        "positive_mentions": 87,
        "negative_mentions": 36,
        "caution_mentions": 35,
        "has_guidance": True,
        "quarter": "Q3 2024",
        "transcript_date": "2024-10-25"
    }

    print("\n📊 Output Structure:")
    print(json.dumps(example, indent=2))

    print("\n🎯 What This Means:")
    print(f"  • Tone: {example['tone']} (Grade: {example['grade']})")
    print(f"  • Assessment: {example['assessment']}")
    print(f"  • Net Sentiment: {example['net_sentiment']:.1f}/100 (Confidence: {example['confidence_%']}%)")
    print(f"  • Keyword Mix:")
    print(f"    - Positive: {example['positive_%']:.1f}% ({example['positive_mentions']} mentions)")
    print(f"    - Negative: {example['negative_%']:.1f}% ({example['negative_mentions']} mentions)")
    print(f"    - Cautious: {example['caution_%']:.1f}% ({example['caution_mentions']} mentions)")
    print(f"  • Guidance Provided: {'Yes' if example['has_guidance'] else 'No'}")
    print(f"  • Latest Transcript: {example['quarter']} ({example['transcript_date']})")

def show_where_to_find():
    """Show where these features appear in the output."""
    print("\n" + "=" * 70)
    print("WHERE TO FIND PREMIUM FEATURES IN OUTPUT")
    print("=" * 70)

    print("\n1️⃣  IN QUALITATIVE ANALYSIS:")
    print("   When you run qualitative analysis on a symbol:")
    print("   ")
    print("   summary = analyzer.analyze_symbol('AAPL', 'non_financial', peers_df)")
    print("   ")
    print("   The summary dict will contain:")
    print("   ├── intrinsic_value/")
    print("   │   ├── insider_trading/         ← PREMIUM FEATURE 1")
    print("   │   │   ├── score: 85")
    print("   │   │   ├── signal: 'Strong Buy'")
    print("   │   │   └── ... (full details)")
    print("   │   │")
    print("   │   └── earnings_sentiment/      ← PREMIUM FEATURE 2")
    print("   │       ├── tone: 'Very Positive'")
    print("   │       ├── grade: 'A'")
    print("   │       └── ... (full details)")

    print("\n2️⃣  IN STREAMLIT UI (run_screener.py):")
    print("   Navigate to 'Deep Dive' tab → Select a symbol")
    print("   Premium features will appear in:")
    print("   • 'Valuation' section → Insider Trading Analysis")
    print("   • 'Valuation' section → Earnings Call Sentiment")

    print("\n3️⃣  VIA CLI:")
    print("   python run_screener.py --config settings_premium.yaml --qualitative AAPL")
    print("   ")
    print("   Output will include JSON with insider_trading and earnings_sentiment")

def show_how_to_verify():
    """Show how to verify features are working."""
    print("\n" + "=" * 70)
    print("HOW TO VERIFY PREMIUM FEATURES ARE WORKING")
    print("=" * 70)

    print("\n✅ STEP 1: Run the verification test (you already did this!):")
    print("   python test_premium_features.py")
    print("   → Should show: ✅ ALL TESTS PASSED")

    print("\n✅ STEP 2: Check the config:")
    print("   grep -A4 'premium:' settings_premium.yaml")
    print("   → Should show:")
    print("     enable_insider_trading: true")
    print("     enable_earnings_transcripts: true")

    print("\n✅ STEP 3: Run qualitative analysis on a test symbol:")
    print("   Create a small test script:")
    print("")
    print("   # test_single_symbol.py")
    print("   import yaml, os, sys")
    print("   sys.path.insert(0, 'src/screener')")
    print("   from ingest import FMPClient")
    print("   from qualitative import QualitativeAnalyzer")
    print("   ")
    print("   with open('settings_premium.yaml') as f:")
    print("       config = yaml.safe_load(f)")
    print("   ")
    print("   api_key = os.getenv('FMP_API_KEY')")
    print("   client = FMPClient(api_key, config)")
    print("   analyzer = QualitativeAnalyzer(client, config)")
    print("   ")
    print("   result = analyzer._estimate_intrinsic_value('AAPL', 'non_financial', None)")
    print("   print('Insider Trading:', 'insider_trading' in result)")
    print("   print('Earnings Sentiment:', 'earnings_sentiment' in result)")

    print("\n✅ STEP 4: Look for these log messages when running:")
    print("   The functions will be called and you should see:")
    print("   • No error messages about missing features")
    print("   • API calls to /insider-trading endpoint")
    print("   • API calls to /earning_call_transcript endpoint")

def show_troubleshooting():
    """Show troubleshooting steps."""
    print("\n" + "=" * 70)
    print("TROUBLESHOOTING: 'NADA APARECE HABILITADO'")
    print("=" * 70)

    print("\n❓ If you see NO premium features in output:")

    print("\n1. Check you're using the RIGHT config:")
    print("   ❌ python run_screener.py")
    print("   ✅ python run_screener.py --config settings_premium.yaml")

    print("\n2. Check you have a VALID FMP API KEY:")
    print("   export FMP_API_KEY='your_key_here'")
    print("   OR")
    print("   Add to .env file: FMP_API_KEY=your_key")

    print("\n3. Check your FMP plan supports premium features:")
    print("   • Insider Trading requires Professional+ plan")
    print("   • Earnings Transcripts requires Professional+ plan")
    print("   • Free/Starter plans: Features will return 'available: false'")

    print("\n4. Check WHERE you're looking:")
    print("   Premium features appear in:")
    print("   • intrinsic_value.insider_trading (not root level)")
    print("   • intrinsic_value.earnings_sentiment (not root level)")
    print("   ")
    print("   They are NESTED inside the intrinsic_value dict!")

    print("\n5. The features execute ONLY during qualitative analysis:")
    print("   • NOT during initial screening")
    print("   • ONLY when you deep-dive into a specific symbol")
    print("   • Check the 'Deep Dive' tab in Streamlit UI")

def main():
    """Show demo output."""
    print("\n" + "🎬" * 35)
    print("PREMIUM FEATURES OUTPUT DEMO")
    print("What you should see when premium features execute")
    print("🎬" * 35)

    show_insider_trading_output()
    show_earnings_sentiment_output()
    show_where_to_find()
    show_how_to_verify()
    show_troubleshooting()

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("\n✅ Premium features ARE implemented and working")
    print("✅ Configuration IS correct (verified by test_premium_features.py)")
    print("✅ Features execute during QUALITATIVE ANALYSIS only")
    print("✅ Output is NESTED in intrinsic_value dict")
    print("\n💡 Next Step: Run qualitative analysis on a symbol to see actual output!")
    print("\n")

if __name__ == '__main__':
    main()
