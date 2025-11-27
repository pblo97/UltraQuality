#!/usr/bin/env python3
"""
Test backlog analysis functionality with order-driven industrial companies.
"""
import sys
import os
import yaml
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from screener.ingest import FMPClient
from screener.qualitative import QualitativeAnalyzer

def test_backlog_analysis():
    """Test backlog extraction on aerospace & defense companies."""

    # Set API key
    api_key = "qGDE52LhIJ9CQSyRwKpAzjLXeLP4Pwkt"

    # Load config
    with open('settings.yaml', 'r') as f:
        config = yaml.safe_load(f)

    # Initialize FMP client
    fmp = FMPClient(api_key, config['fmp'])

    # Initialize qualitative analyzer
    qual_analyzer = QualitativeAnalyzer(fmp, config)

    # Test companies (order-driven industrials)
    test_companies = [
        ("LMT", "Lockheed Martin - Aerospace & Defense"),
        ("BA", "Boeing - Aerospace"),
        ("RTX", "Raytheon Technologies - Defense"),
        ("NOC", "Northrop Grumman - Defense"),
        ("CAT", "Caterpillar - Heavy Equipment"),
    ]

    print(f"\n{'='*80}")
    print("TESTING BACKLOG ANALYSIS FROM EARNINGS CALLS")
    print(f"{'='*80}\n")

    for symbol, description in test_companies:
        print(f"\n{'-'*80}")
        print(f"TESTING: {description} ({symbol})")
        print(f"{'-'*80}\n")

        try:
            # Get company profile for industry
            profile = fmp.get_profile(symbol)
            if profile:
                industry = profile[0].get('industry', '')
                print(f"Industry: {industry}")
            else:
                industry = 'Aerospace & Defense'
                print(f"Industry: {industry} (default)")

            # Extract backlog data
            backlog_data = qual_analyzer._extract_backlog_data(symbol, industry)

            # Display results
            print(f"\nBACKLOG ANALYSIS RESULTS:")
            print(f"  Backlog Mentioned: {backlog_data['backlog_mentioned']}")

            if backlog_data['backlog_mentioned']:
                print(f"  Backlog Value: {backlog_data.get('backlog_value', 'N/A')}")
                print(f"  Backlog Change: {backlog_data.get('backlog_change', 'N/A')}")
                print(f"  Book-to-Bill: {backlog_data.get('book_to_bill', 'N/A')}")
                print(f"  Backlog Duration: {backlog_data.get('backlog_duration', 'N/A')}")
                print(f"  Order Trend: {backlog_data['order_trend']}")

                if backlog_data.get('backlog_snippets'):
                    print(f"\n  KEY QUOTES:")
                    for i, snippet in enumerate(backlog_data['backlog_snippets'], 1):
                        print(f"    {i}. {snippet[:150]}...")
            else:
                print(f"  → No backlog data found in latest earnings call")

            # Analysis
            print(f"\n  INTERPRETATION:")
            if backlog_data['backlog_mentioned']:
                if backlog_data['order_trend'] == 'Positive':
                    print(f"    ✓ POSITIVE - Strong order momentum")
                    if backlog_data.get('book_to_bill'):
                        btb = float(backlog_data['book_to_bill'].replace('x', ''))
                        if btb > 1.0:
                            print(f"    ✓ Book-to-Bill {btb:.2f}x indicates orders exceeding revenue")
                elif backlog_data['order_trend'] == 'Declining':
                    print(f"    ⚠️  WARNING - Declining order book")
                    print(f"    → May signal weakening demand or end of cycle")
                elif backlog_data['order_trend'] == 'Stable':
                    print(f"    → NEUTRAL - Steady order flow")
                else:
                    print(f"    → Backlog mentioned but trend unclear")
            else:
                print(f"    → Not applicable (company may not report backlog)")
                print(f"    → Or backlog not discussed in latest earnings call")

        except Exception as e:
            print(f"✗ Error analyzing {symbol}: {e}")
            import traceback
            traceback.print_exc()

        print()

    print(f"\n{'='*80}")
    print("TEST COMPLETE")
    print(f"{'='*80}\n")

    print("NOTES:")
    print("  - Backlog analysis only runs for order-driven industries")
    print("  - Industries: Aerospace, Defense, Heavy Equipment, Capital Goods, etc.")
    print("  - Data extracted from latest earnings call transcript")
    print("  - Metrics: Backlog value, YoY change, Book-to-Bill ratio, Duration")
    print("  - Order trend: Positive / Stable / Declining based on qualitative signals")
    print()

if __name__ == '__main__':
    test_backlog_analysis()
