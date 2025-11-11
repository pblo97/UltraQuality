#!/usr/bin/env python3
"""
Simple check to show WHERE to look for premium features.
This helps diagnose the most common problem: looking in the wrong place.
"""

print("\n" + "="*80)
print("WHERE TO LOOK FOR PREMIUM FEATURES - Quick Guide")
print("="*80)

print("""
❌ COMMON MISTAKE: Looking at the WRONG level

When you run qualitative analysis, the output structure is:

summary = analyzer.analyze_symbol('AAPL', 'non_financial', peers_df)

The summary dict looks like this:

{
    'symbol': 'AAPL',
    'as_of': '2024-11-11',
    'business_summary': '...',
    'peers_list': [...],
    'moats': [...],
    'skin_in_the_game': {...},
    'insider_trading': {...},        ← ⚠️  OLD location (deprecated)
    'news_TLDR': [...],
    'recent_news': [...],
    'transcript_TLDR': {...},
    'intrinsic_value': {             ← ✅ PREMIUM FEATURES ARE HERE!
        'target_price': 150.0,
        'upside_%': 25.0,
        'methods': [...],
        'insider_trading': {         ← ✅ THIS IS THE RIGHT ONE!
            'available': true,
            'score': 85,
            'signal': 'Strong Buy',
            ...
        },
        'earnings_sentiment': {      ← ✅ THIS IS THE RIGHT ONE!
            'available': true,
            'tone': 'Very Positive',
            'grade': 'A',
            ...
        }
    }
}

📍 THE KEY POINT:
   Premium features are INSIDE intrinsic_value dict, not at root level!

✅ CORRECT ACCESS:
   result = summary['intrinsic_value']['insider_trading']
   sentiment = summary['intrinsic_value']['earnings_sentiment']

❌ WRONG ACCESS:
   result = summary['insider_trading']        # This might be the OLD deprecated one
   sentiment = summary['earnings_sentiment']  # This doesn't exist at root

""")

print("="*80)
print("HOW TO VERIFY")
print("="*80)

print("""
Option 1: Print the keys to see what's actually there

import json
summary = analyzer.analyze_symbol('AAPL', 'non_financial', peers_df)

print("Root keys:", list(summary.keys()))
print("\\nIntrinsic value keys:", list(summary.get('intrinsic_value', {}).keys()))

# Then look for 'insider_trading' and 'earnings_sentiment' in intrinsic_value


Option 2: Check if features are present

has_iv = 'intrinsic_value' in summary
has_insider = 'insider_trading' in summary.get('intrinsic_value', {})
has_sentiment = 'earnings_sentiment' in summary.get('intrinsic_value', {})

print(f"Has intrinsic_value: {has_iv}")
print(f"Has insider_trading in IV: {has_insider}")
print(f"Has earnings_sentiment in IV: {has_sentiment}")


Option 3: Dump the full structure to JSON

with open('debug_output.json', 'w') as f:
    json.dump(summary, f, indent=2, default=str)

# Then open debug_output.json and search for 'insider_trading'

""")

print("="*80)
print("NEXT STEP")
print("="*80)

print("""
If you have your FMP_API_KEY set, run this to see the actual execution:

    export FMP_API_KEY='your_key'
    python test_premium_flow.py

This will show you EXACTLY what happens when the code runs,
including detailed logs of the premium features execution.

You'll see messages like:
  🔍 Premium config for AAPL: {'enable_insider_trading': True, ...}
  ✓ Insider Trading is ENABLED, calling _analyze_insider_trading(AAPL)...
  ✓ Insider Trading result: available=True
  ✓ Insider Trading added to valuation dict

If you DON'T see those messages, then the config isn't loading correctly.
If you DO see them but still don't see features in output, then you're
looking in the wrong place (see above).
""")

print("="*80)
