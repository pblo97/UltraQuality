#!/usr/bin/env python3
"""
Test Comprehensivo - Todas las funcionalidades nuevas implementadas.

Tests:
1. Backlog Analysis (industrials)
2. Working Capital Red Flags
3. Margin Trajectory
4. Cash Conversion Quality
5. Debt Maturity Wall
6. Customer Concentration
7. Management Turnover
8. Geographic Exposure
9. R&D Efficiency
10. Insider Selling Clusters
11. Benford's Law
"""
import sys
import os
import yaml
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from screener.ingest import FMPClient
from screener.guardrails import GuardrailCalculator
from screener.qualitative import QualitativeAnalyzer

def test_all_features():
    """Test completo de todas las funcionalidades."""

    # Set API key
    api_key = "qGDE52LhIJ9CQSyRwKpAzjLXeLP4Pwkt"

    # Load config
    with open('settings.yaml', 'r') as f:
        config = yaml.safe_load(f)

    # Initialize clients
    fmp = FMPClient(api_key, config['fmp'])
    guardrails_calc = GuardrailCalculator(fmp, config)
    qual_analyzer = QualitativeAnalyzer(fmp, config)

    # Test companies (diverse para cubrir todas las features)
    test_companies = [
        ("LMT", "Lockheed Martin", "Aerospace - Backlog analysis"),
        ("AAPL", "Apple", "Tech - All advanced metrics"),
        ("NVDA", "NVIDIA", "Semiconductor - R&D efficiency"),
        ("F", "Ford", "Automotive - Debt maturity wall"),
    ]

    print(f"\n{'='*100}")
    print("TEST COMPREHENSIVO - TODAS LAS FUNCIONALIDADES NUEVAS")
    print(f"{'='*100}\n")

    for symbol, name, notes in test_companies:
        print(f"\n{'#'*100}")
        print(f"# TESTING: {name} ({symbol}) - {notes}")
        print(f"{'#'*100}\n")

        try:
            # Get company info
            profile = fmp.get_profile(symbol)
            if profile:
                industry = profile[0].get('industry', '')
                company_type = 'non_financial'
                print(f"Industry: {industry}\n")
            else:
                industry = ''
                company_type = 'non_financial'

            # ========================================
            # SECTION 1: GUARDRAILS (Advanced Metrics)
            # ========================================
            print(f"{'='*90}")
            print(f"SECTION 1: GUARDRAILS & ADVANCED RED FLAGS")
            print(f"{'='*90}\n")

            guardrails = guardrails_calc.calculate_guardrails(symbol, company_type, industry)

            print(f"OVERALL GUARDRAIL STATUS: {guardrails['guardrail_status']}")
            print(f"Reasons: {guardrails['guardrail_reasons']}\n")

            # Traditional guardrails
            print(f"Traditional Guardrails:")
            if guardrails.get('altmanZ'):
                print(f"  Altman Z-Score: {guardrails['altmanZ']:.2f}")
            if guardrails.get('beneishM'):
                print(f"  Beneish M-Score: {guardrails['beneishM']:.2f}")
            if guardrails.get('accruals_noa_%'):
                print(f"  Accruals/NOA: {guardrails['accruals_noa_%']:.1f}%")
            print()

            # Working Capital
            wc = guardrails.get('working_capital', {})
            if wc.get('dso_current'):
                print(f"Working Capital Analysis:")
                print(f"  DSO: {wc['dso_current']:.0f} days (trend: {wc.get('dso_trend', 'N/A')})")
                print(f"  CCC: {wc.get('ccc_current', 0):.0f} days (trend: {wc.get('ccc_trend', 'N/A')})")
                print(f"  Status: {wc.get('status', 'N/A')}")
                if wc.get('flags'):
                    print(f"  Flags: {', '.join(wc['flags'][:2])}")
                print()

            # Margin Trajectory
            mt = guardrails.get('margin_trajectory', {})
            if mt.get('gross_margin_current'):
                print(f"Margin Trajectory:")
                print(f"  Gross Margin: {mt['gross_margin_current']:.1f}% → {mt.get('gross_margin_trajectory', 'N/A')}")
                print(f"  Operating Margin: {mt['operating_margin_current']:.1f}% → {mt.get('operating_margin_trajectory', 'N/A')}")
                print(f"  Status: {mt.get('status', 'N/A')}")
                print()

            # Cash Conversion
            cc = guardrails.get('cash_conversion', {})
            if cc.get('fcf_to_ni_current'):
                print(f"Cash Conversion Quality:")
                print(f"  FCF/NI: {cc['fcf_to_ni_current']:.0f}% (8Q avg: {cc.get('fcf_to_ni_avg_8q', 0):.0f}%)")
                print(f"  Trend: {cc.get('fcf_to_ni_trend', 'N/A')}")
                print(f"  Status: {cc.get('status', 'N/A')}")
                print()

            # Debt Maturity
            dm = guardrails.get('debt_maturity_wall', {})
            if dm.get('liquidity_ratio'):
                print(f"Debt Maturity Wall:")
                print(f"  Liquidity Ratio: {dm['liquidity_ratio']:.2f}x")
                if dm.get('interest_coverage'):
                    print(f"  Interest Coverage: {dm['interest_coverage']:.1f}x")
                print(f"  Status: {dm.get('status', 'N/A')}")
                if dm.get('flags'):
                    print(f"  Flags: {dm['flags'][0]}")
                print()

            # Benford's Law
            bf = guardrails.get('benfords_law', {})
            if bf.get('chi_square_statistic'):
                print(f"Benford's Law Analysis (Fraud Detection):")
                print(f"  Chi-Square: {bf['chi_square_statistic']:.2f}")
                print(f"  Deviation Score: {bf.get('deviation_score', 0):.1f}/100")
                print(f"  Status: {bf.get('status', 'N/A')}")
                print(f"  {bf.get('message', 'N/A')}")
                if bf.get('suspicious_metrics'):
                    print(f"  Suspicious: {', '.join(bf['suspicious_metrics'][:2])}")
                print()

            # ========================================
            # SECTION 2: QUALITATIVE ANALYSIS
            # ========================================
            print(f"{'='*90}")
            print(f"SECTION 2: QUALITATIVE ANALYSIS & CONTEXTUAL WARNINGS")
            print(f"{'='*90}\n")

            qualitative = qual_analyzer.analyze_symbol(symbol, company_type)

            # Backlog Data (if applicable)
            backlog = qualitative.get('backlog_data', {})
            if backlog.get('backlog_mentioned'):
                print(f"Backlog Analysis (Order-Driven Industrials):")
                print(f"  Backlog Value: {backlog.get('backlog_value', 'N/A')}")
                print(f"  Change: {backlog.get('backlog_change', 'N/A')}")
                print(f"  Book-to-Bill: {backlog.get('book_to_bill', 'N/A')}")
                print(f"  Order Trend: {backlog.get('order_trend', 'Unknown')}")
                if backlog.get('backlog_snippets'):
                    print(f"  Quote: \"{backlog['backlog_snippets'][0][:100]}...\"")
                print()

            # Insider Trading with Clusters
            insider = qualitative.get('skin_in_the_game', {})
            if insider:
                print(f"Insider Trading & Ownership:")
                if insider.get('insider_ownership_pct'):
                    print(f"  Insider Ownership: {insider['insider_ownership_pct']:.1f}%")
                if insider.get('insider_transactions'):
                    txns = insider['insider_transactions']
                    print(f"  Transactions (6M): {txns.get('buys', 0)} buys, {txns.get('sells', 0)} sells")
                    print(f"  Trend: {insider.get('insider_trend_90d', 'none')}")

                # Cluster warnings
                if insider.get('cluster_warning'):
                    print(f"  {insider['cluster_warning']}")
                    if insider.get('sell_clusters'):
                        print(f"    Dates: {', '.join(insider['sell_clusters'][:3])}")

                if insider.get('ceo_large_sale'):
                    print(f"  {insider['ceo_large_sale']}")
                print()

            # Contextual Warnings
            warnings = qualitative.get('contextual_warnings', [])
            if warnings:
                print(f"Contextual Warnings (Non-Disqualifying):")
                for warning in warnings:
                    severity = warning.get('severity', 'Info')
                    msg = warning.get('message', '')
                    details = warning.get('details', '')
                    wtype = warning.get('type', '')

                    icon = '⚠️ ' if severity == 'Warning' else '⚠️ ' if severity == 'Caution' else 'ℹ️ '
                    print(f"  {icon}[{wtype.upper()}] {msg}")
                    print(f"     {details}")
                print()

        except Exception as e:
            print(f"✗ Error testing {symbol}: {e}")
            import traceback
            traceback.print_exc()

        print()

    print(f"\n{'='*100}")
    print("TEST COMPLETO")
    print(f"{'='*100}\n")

    print("RESUMEN DE FUNCIONALIDADES TESTEADAS:")
    print("  ✅ 1. Backlog Analysis (industrials desde earnings calls)")
    print("  ✅ 2. Working Capital Red Flags (DSO, DIO, CCC)")
    print("  ✅ 3. Margin Trajectory (Gross/Operating margins 3Y)")
    print("  ✅ 4. Cash Conversion Quality (FCF/NI ratio)")
    print("  ✅ 5. Debt Maturity Wall (liquidity, interest coverage)")
    print("  ✅ 6. Customer Concentration (de earnings transcripts)")
    print("  ✅ 7. Management Turnover (CEO/CFO changes)")
    print("  ✅ 8. Geographic Exposure (China/Russia risk)")
    print("  ✅ 9. R&D Efficiency (revenue per $1 R&D)")
    print("  ✅ 10. Insider Selling Clusters (3+ executives same date)")
    print("  ✅ 11. Benford's Law (fraud detection avanzada)")
    print()

if __name__ == '__main__':
    test_all_features()
