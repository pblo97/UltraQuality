#!/usr/bin/env python3
"""
Test advanced red flags functionality.
Tests: Working Capital, Margin Trajectory, Cash Conversion, Debt Maturity Wall
"""
import sys
import os
import yaml
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from screener.ingest import FMPClient
from screener.guardrails import GuardrailCalculator

def test_advanced_red_flags():
    """Test advanced red flags on diverse companies."""

    # Set API key
    api_key = "qGDE52LhIJ9CQSyRwKpAzjLXeLP4Pwkt"

    # Load config
    with open('settings.yaml', 'r') as f:
        config = yaml.safe_load(f)

    # Initialize FMP client
    fmp = FMPClient(api_key, config['fmp'])

    # Initialize guardrails calculator
    guardrails_calc = GuardrailCalculator(fmp, config)

    # Test companies (diverse mix to test different flags)
    test_companies = [
        ("AAPL", "Apple", "Technology - Strong moat, should have good metrics"),
        ("TSLA", "Tesla", "Automotive - Growth company, high capex"),
        ("GME", "GameStop", "Retail - Potential working capital issues"),
        ("F", "Ford", "Automotive - Cyclical, debt concerns"),
        ("NFLX", "Netflix", "Streaming - Cash conversion test"),
        ("T", "AT&T", "Telecom - High debt, margin pressure"),
    ]

    print(f"\n{'='*100}")
    print("TESTING ADVANCED RED FLAGS")
    print(f"{'='*100}\n")

    for symbol, name, notes in test_companies:
        print(f"\n{'-'*100}")
        print(f"TESTING: {name} ({symbol})")
        print(f"Notes: {notes}")
        print(f"{'-'*100}\n")

        try:
            # Get company profile for industry
            profile = fmp.get_profile(symbol)
            if profile:
                industry = profile[0].get('industry', '')
                company_type = 'non_financial'  # Simplification for test
                print(f"Industry: {industry}")
            else:
                industry = ''
                company_type = 'non_financial'
                print(f"Industry: Unknown")

            # Calculate guardrails (including advanced metrics)
            guardrails = guardrails_calc.calculate_guardrails(symbol, company_type, industry)

            # Display results
            print(f"\n{'='*60}")
            print(f"OVERALL STATUS: {guardrails['guardrail_status']}")
            print(f"Reasons: {guardrails['guardrail_reasons']}")
            print(f"{'='*60}\n")

            # 1. Working Capital Red Flags
            wc = guardrails.get('working_capital', {})
            print(f"1. WORKING CAPITAL ANALYSIS:")
            print(f"   Status: {wc.get('status', 'N/A')}")
            if wc.get('dso_current'):
                print(f"   DSO (Days Sales Outstanding): {wc['dso_current']:.0f} days")
                print(f"   DSO Trend: {wc.get('dso_trend', 'Unknown')}")
            if wc.get('dio_current'):
                print(f"   DIO (Days Inventory Outstanding): {wc['dio_current']:.0f} days")
                print(f"   DIO Trend: {wc.get('dio_trend', 'Unknown')}")
            if wc.get('ccc_current'):
                print(f"   Cash Conversion Cycle: {wc['ccc_current']:.0f} days")
                print(f"   CCC Trend: {wc.get('ccc_trend', 'Unknown')}")
                if wc.get('ccc_change_8q'):
                    print(f"   CCC Change (8Q): {wc['ccc_change_8q']:.0f} days")
            if wc.get('flags'):
                print(f"   ⚠️  Flags:")
                for flag in wc['flags']:
                    print(f"      - {flag}")
            print()

            # 2. Margin Trajectory
            mt = guardrails.get('margin_trajectory', {})
            print(f"2. MARGIN TRAJECTORY:")
            print(f"   Status: {mt.get('status', 'N/A')}")
            if mt.get('gross_margin_current'):
                print(f"   Gross Margin: {mt['gross_margin_current']:.1f}% (now) vs "
                      f"{mt.get('gross_margin_3y_ago', 0):.1f}% (3Y ago)")
                print(f"   Change: {mt.get('gross_margin_change', 0):.0f} bps")
                print(f"   Trajectory: {mt.get('gross_margin_trajectory', 'Unknown')}")
            if mt.get('operating_margin_current'):
                print(f"   Operating Margin: {mt['operating_margin_current']:.1f}% (now) vs "
                      f"{mt.get('operating_margin_3y_ago', 0):.1f}% (3Y ago)")
                print(f"   Change: {mt.get('operating_margin_change', 0):.0f} bps")
                print(f"   Trajectory: {mt.get('operating_margin_trajectory', 'Unknown')}")
            if mt.get('signals'):
                print(f"   Signals:")
                for signal in mt['signals']:
                    print(f"      {signal}")
            print()

            # 3. Cash Conversion Quality
            cc = guardrails.get('cash_conversion', {})
            print(f"3. CASH CONVERSION QUALITY:")
            print(f"   Status: {cc.get('status', 'N/A')}")
            if cc.get('fcf_to_ni_current'):
                print(f"   FCF/Net Income: {cc['fcf_to_ni_current']:.0f}% (current)")
                print(f"   FCF/NI Avg (8Q): {cc.get('fcf_to_ni_avg_8q', 0):.0f}%")
                print(f"   Trend: {cc.get('fcf_to_ni_trend', 'Unknown')}")
            if cc.get('fcf_to_revenue_current'):
                print(f"   FCF/Revenue: {cc['fcf_to_revenue_current']:.1f}%")
            if cc.get('capex_intensity_current'):
                print(f"   Capex Intensity: {cc['capex_intensity_current']:.1f}%")
            if cc.get('flags'):
                print(f"   ⚠️  Flags:")
                for flag in cc['flags']:
                    print(f"      - {flag}")
            print()

            # 4. Debt Maturity Wall
            dm = guardrails.get('debt_maturity_wall', {})
            print(f"4. DEBT MATURITY WALL:")
            print(f"   Status: {dm.get('status', 'N/A')}")
            if dm.get('short_term_debt_pct'):
                print(f"   Short-term Debt: {dm['short_term_debt_pct']:.0f}% of total debt")
            if dm.get('debt_due_12m'):
                print(f"   Debt Due 12M: ${dm['debt_due_12m']/1e9:.1f}B")
            if dm.get('cash_and_equivalents'):
                print(f"   Cash: ${dm['cash_and_equivalents']/1e9:.1f}B")
            if dm.get('liquidity_ratio'):
                print(f"   Liquidity Ratio (Cash/ST Debt): {dm['liquidity_ratio']:.2f}x")
            if dm.get('interest_coverage'):
                print(f"   Interest Coverage: {dm['interest_coverage']:.1f}x")
            if dm.get('flags'):
                print(f"   ⚠️  Flags:")
                for flag in dm['flags']:
                    print(f"      - {flag}")
            print()

            # Traditional guardrails (for comparison)
            print(f"TRADITIONAL GUARDRAILS:")
            if guardrails.get('altmanZ'):
                print(f"   Altman Z: {guardrails['altmanZ']:.2f}")
            if guardrails.get('beneishM'):
                print(f"   Beneish M: {guardrails['beneishM']:.2f}")
            if guardrails.get('accruals_noa_%'):
                print(f"   Accruals/NOA: {guardrails['accruals_noa_%']:.1f}%")
            if guardrails.get('netShareIssuance_12m_%'):
                print(f"   Net Share Issuance: {guardrails['netShareIssuance_12m_%']:.1f}%")
            print()

        except Exception as e:
            print(f"✗ Error analyzing {symbol}: {e}")
            import traceback
            traceback.print_exc()

        print()

    print(f"\n{'='*100}")
    print("TEST COMPLETE")
    print(f"{'='*100}\n")

    print("SUMMARY OF METRICS:")
    print("  1. Working Capital: DSO, DIO, DPO, Cash Conversion Cycle + Trends")
    print("  2. Margin Trajectory: Gross/Operating margin trends over 3Y")
    print("  3. Cash Conversion: FCF/NI ratio, capex intensity, quality trends")
    print("  4. Debt Maturity Wall: ST debt %, liquidity ratio, interest coverage")
    print()

if __name__ == '__main__':
    test_advanced_red_flags()
