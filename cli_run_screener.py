#!/usr/bin/env python3
"""
Convenience script to run UltraQuality screener.

Usage:
    python run_screener.py                    # Run full screening
    python run_screener.py --symbol AAPL      # Qualitative analysis for AAPL
    python run_screener.py --help             # Show help
"""
import sys
import os
from pathlib import Path
import argparse
import json
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from screener.orchestrator import ScreenerPipeline

# Load environment variables
load_dotenv()


def main():
    parser = argparse.ArgumentParser(
        description='UltraQuality: Quality + Value Investment Screener',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full screening pipeline
  python run_screener.py

  # Run with custom config
  python run_screener.py --config my_settings.yaml

  # Qualitative analysis for specific symbol
  python run_screener.py --symbol MSFT

  # Qualitative analysis with output file
  python run_screener.py --symbol AAPL --output aapl_analysis.json
"""
    )

    parser.add_argument(
        '--config',
        default='settings.yaml',
        help='Path to configuration file (default: settings.yaml)'
    )

    parser.add_argument(
        '--symbol',
        help='Run on-demand qualitative analysis for symbol (e.g., AAPL)'
    )

    parser.add_argument(
        '--output',
        help='Output file for qualitative analysis (JSON)'
    )

    args = parser.parse_args()

    # Verify API key
    api_key = os.getenv('FMP_API_KEY')
    if not api_key or api_key.startswith('your_'):
        print("ERROR: FMP_API_KEY not set!")
        print("\nPlease set your API key:")
        print("  1. Copy .env.example to .env")
        print("  2. Edit .env and add your API key")
        print("  3. Get API key at: https://financialmodelingprep.com")
        sys.exit(1)

    # Verify config exists
    if not Path(args.config).exists():
        print(f"ERROR: Config file not found: {args.config}")
        sys.exit(1)

    print("=" * 80)
    print("UltraQuality Screener v1.0")
    print("=" * 80)

    try:
        # Initialize pipeline
        pipeline = ScreenerPipeline(args.config)

        if args.symbol:
            # On-demand qualitative analysis
            print(f"\nRunning qualitative analysis for {args.symbol}...")
            print("-" * 80)

            summary = pipeline.get_qualitative_analysis(args.symbol)

            if not summary:
                print(f"\nERROR: Symbol {args.symbol} not found in screener results.")
                print("Run full screening first to analyze symbols.")
                sys.exit(1)

            # Display summary
            print(f"\n{'='*80}")
            print(f"QUALITATIVE ANALYSIS: {args.symbol}")
            print(f"{'='*80}\n")

            print(f"Business Summary:")
            print(f"  {summary.get('business_summary', 'N/A')}\n")

            print(f"Peers: {', '.join(summary.get('peers_list', []))}\n")

            moats = summary.get('moats', {})
            print(f"Competitive Moats:")
            for moat_type, value in moats.items():
                if moat_type != 'notes':
                    print(f"  {moat_type}: {value}")
            print(f"  Notes: {moats.get('notes', '')}\n")

            skin = summary.get('skin_in_the_game', {})
            print(f"Skin in the Game:")
            print(f"  Insider trend (90d): {skin.get('insider_trend_90d', 'N/A')}")
            print(f"  Net share issuance: {skin.get('net_share_issuance_12m_%', 'N/A')}%")
            print(f"  Assessment: {skin.get('assessment', 'N/A')}\n")

            news = summary.get('news_TLDR', [])
            if news:
                print(f"Recent News (Top 3):")
                for i, item in enumerate(news[:3], 1):
                    print(f"  {i}. {item}")
                print()

            risks = summary.get('top_risks', [])
            if risks:
                print(f"Top Risks:")
                for i, risk in enumerate(risks, 1):
                    print(f"  {i}. {risk.get('risk', 'N/A')}")
                    print(f"     Probability: {risk.get('prob', 'N/A')}, Severity: {risk.get('severity', 'N/A')}")
                    print(f"     Trigger: {risk.get('trigger', 'N/A')}")
                print()

            # Save to file if requested
            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(summary, f, indent=2)
                print(f"✓ Full analysis saved to {args.output}\n")

        else:
            # Run full screening pipeline
            print("\nRunning full screening pipeline...")
            print("This may take several minutes depending on universe size.\n")

            output_csv = pipeline.run()

            print(f"\n{'='*80}")
            print(f"✓ SCREENING COMPLETE")
            print(f"{'='*80}")
            print(f"\nResults: {output_csv}")
            print(f"\nTo analyze a specific symbol:")
            print(f"  python run_screener.py --symbol TICKER\n")

    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        sys.exit(1)

    except Exception as e:
        print(f"\n{'='*80}")
        print(f"ERROR: {e}")
        print(f"{'='*80}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
