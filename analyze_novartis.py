#!/usr/bin/env python3
"""
Analyze Novartis (NOVN.SW) guardrails to determine if time decay is warranted.
"""
import sys
import os
import yaml
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from screener.ingest import FMPClient
from screener.guardrails import GuardrailCalculator

def analyze_novartis():
    """Analyze Novartis guardrails."""

    # Set API key
    api_key = "qGDE52LhIJ9CQSyRwKpAzjLXeLP4Pwkt"

    # Load config
    with open('settings.yaml', 'r') as f:
        config = yaml.safe_load(f)

    # Initialize FMP client
    fmp = FMPClient(api_key, config['fmp'])

    # Initialize guardrail calculator
    guardrail_calc = GuardrailCalculator(fmp, config)

    # Novartis ticker
    symbol = "NOVN.SW"  # Swiss Exchange

    print(f"\n{'='*80}")
    print(f"ANALYZING NOVARTIS ({symbol})")
    print(f"{'='*80}\n")

    # Get company profile
    print("Fetching company profile...")
    try:
        profile = fmp.get_profile(symbol)
        if profile:
            print(f"✓ Company: {profile[0].get('companyName', 'N/A')}")
            print(f"  Industry: {profile[0].get('industry', 'N/A')}")
            print(f"  Sector: {profile[0].get('sector', 'N/A')}")
            print(f"  Market Cap: ${profile[0].get('mktCap', 0) / 1e9:.2f}B")
            print(f"  Country: {profile[0].get('country', 'N/A')}")

            industry = profile[0].get('industry', '')
            sector = profile[0].get('sector', '')
        else:
            print("✗ Could not fetch profile")
            industry = 'Healthcare'
            sector = 'Healthcare'
    except Exception as e:
        print(f"✗ Error fetching profile: {e}")
        industry = 'Healthcare'
        sector = 'Healthcare'

    print(f"\n{'-'*80}")
    print("CALCULATING GUARDRAILS")
    print(f"{'-'*80}\n")

    # Calculate guardrails
    try:
        guardrails = guardrail_calc.calculate_guardrails(
            symbol=symbol,
            company_type='non_financial',
            industry=industry
        )

        # Display results
        print("GUARDRAIL RESULTS:")
        print(f"  Status: {guardrails['guardrail_status']}")
        print(f"  Reasons: {guardrails['guardrail_reasons']}")
        print()

        print("DETAILED METRICS:")
        print(f"  Altman Z-Score: {guardrails.get('altmanZ', 'N/A')}")
        if guardrails.get('altmanZ'):
            z = guardrails['altmanZ']
            if z > 2.99:
                print(f"    → ✓ Safe zone (>2.99)")
            elif z > 1.81:
                print(f"    → ⚠ Gray zone (1.81-2.99)")
            else:
                print(f"    → ✗ Distress zone (<1.81)")

        print(f"\n  Beneish M-Score: {guardrails.get('beneishM', 'N/A')}")
        if guardrails.get('beneishM'):
            m = guardrails['beneishM']
            threshold = guardrail_calc._get_beneish_threshold_for_industry(industry)
            print(f"    Industry threshold: {threshold}")
            if m > threshold:
                print(f"    → ✗ Above threshold (manipulation risk)")
            elif m > -2.22:
                print(f"    → ⚠ Borderline")
            else:
                print(f"    → ✓ Low manipulation risk")

        print(f"\n  Accruals/NOA: {guardrails.get('accruals_noa_%', 'N/A')}%")
        if guardrails.get('accruals_noa_%'):
            acc = guardrails['accruals_noa_%']
            if acc > 20:
                print(f"    → ✗ Very high (>20%)")
            elif acc > 15:
                print(f"    → ⚠ Elevated (>15%)")
            else:
                print(f"    → ✓ Normal")

        print(f"\n  Share Dilution (12m): {guardrails.get('netShareIssuance_12m_%', 'N/A')}%")
        if guardrails.get('netShareIssuance_12m_%'):
            dil = guardrails['netShareIssuance_12m_%']
            if dil > 10:
                print(f"    → ✗ High dilution (>10%)")
            elif dil > 5:
                print(f"    → ⚠ Moderate dilution (>5%)")
            elif dil < -5:
                print(f"    → ✓ Buybacks ({dil:.1f}%)")
            else:
                print(f"    → ✓ Minimal")

        print(f"\n  M&A Flag: {guardrails.get('mna_flag', 'N/A')}")

        print(f"\n  Revenue Growth (3Y): {guardrails.get('revenue_growth_3y', 'N/A')}%")
        if guardrails.get('revenue_growth_3y'):
            rev = guardrails['revenue_growth_3y']
            if rev < -5:
                print(f"    → ✗ Declining (< -5%)")
            elif rev < 0:
                print(f"    → ⚠ Flat/declining")
            else:
                print(f"    → ✓ Growing")

        print(f"\n{'-'*80}")
        print("ANALYSIS")
        print(f"{'-'*80}\n")

        # Determine root cause of ROJO
        if guardrails['guardrail_status'] == 'ROJO':
            print("❌ ROJO STATUS - Accounting concerns detected")
            print("\nROOT CAUSE:")

            reasons = guardrails['guardrail_reasons']
            if 'Beneish' in reasons:
                print("  → Primary: Beneish M-Score above industry threshold")
                print("  → This indicates potential earnings manipulation risk")
                print("  → Common in pharma due to R&D accounting complexity")

            if 'Altman' in reasons:
                print("  → Altman Z-Score in distress/gray zone")
                print("  → Indicates bankruptcy risk")

            if 'Dilution' in reasons:
                print("  → High share dilution detected")

            print("\nCONTEXT:")
            print("  Novartis historical FCPA violations (2020):")
            print("    - $345M settlement for books & records violations")
            print("    - Bribery/kickbacks in multiple countries")
            print("    - 3-year DPA monitoring period ended 2023")
            print("\n  Question: Does current Beneish M-Score reflect:")
            print("    A) Ongoing manipulation risk? (BAD)")
            print("    B) Complex pharma accounting? (NEUTRAL)")
            print("    C) Historical issues now remediated? (GOOD)")

        elif guardrails['guardrail_status'] == 'AMBAR':
            print("⚠️  AMBAR STATUS - Some concerns but not critical")
        else:
            print("✓ VERDE STATUS - All guardrails clean")

        print(f"\n{'-'*80}")
        print("RECOMMENDATION")
        print(f"{'-'*80}\n")

        if guardrails['guardrail_status'] == 'ROJO':
            m_score = guardrails.get('beneishM')
            threshold = guardrail_calc._get_beneish_threshold_for_industry(industry)

            if m_score and m_score > threshold:
                excess = m_score - threshold
                print(f"Beneish M-Score: {m_score:.3f}")
                print(f"Industry threshold: {threshold:.3f}")
                print(f"Excess: {excess:.3f}\n")

                if excess < 0.3:
                    print("✓ TIME DECAY RECOMMENDED:")
                    print("  - Score is only slightly above threshold")
                    print("  - Pharma industry has naturally higher M-Scores")
                    print("  - FCPA monitoring period ended (2023)")
                    print("  - Company has implemented remediation")
                    print("\n  Suggested approach:")
                    print("    1. Add industry-adjusted Beneish thresholds")
                    print("    2. Implement FCPA time decay (3-5 year rehabilitation)")
                    print("    3. Move Novartis to AMBAR instead of ROJO")
                else:
                    print("⚠️  TIME DECAY QUESTIONABLE:")
                    print("  - M-Score significantly above threshold")
                    print("  - May indicate ongoing accounting issues")
                    print("  - Recommend deeper manual review")
        else:
            print("No time decay needed - guardrails already clean")

        return guardrails

    except Exception as e:
        print(f"✗ Error calculating guardrails: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == '__main__':
    analyze_novartis()
