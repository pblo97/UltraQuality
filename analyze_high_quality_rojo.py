#!/usr/bin/env python3
"""
Deep analysis of high-quality ROJO companies to determine if flags are legitimate.

For each company, analyzes:
- Beneish M-Score components (which ratios are problematic)
- Quality metrics (ROIC, ROE, margins, growth)
- Altman Z components
- Moat characteristics
- Industry context
"""

import pandas as pd
import sys
from pathlib import Path

def analyze_high_quality_rojo(csv_path: str):
    """Analyze high-quality companies flagged as ROJO."""

    print("="*80)
    print("HIGH-QUALITY ROJO COMPANIES - DEEP ANALYSIS")
    print("="*80)
    print()
    print("Objective: Determine if flags are LEGITIMATE or FALSE POSITIVES")
    print()

    # Load results
    df = pd.read_csv(csv_path)

    # Filter high-quality ROJO
    high_q_rojo = df[(df['quality_score_0_100'] >= 80) & (df['guardrail_status'] == 'ROJO')].copy()
    high_q_rojo = high_q_rojo.sort_values('quality_score_0_100', ascending=False)

    print(f"Found {len(high_q_rojo)} high-quality ROJO companies (Q≥80)")
    print()

    # Define columns to analyze
    analysis_cols = [
        'symbol', 'name', 'industry',
        'quality_score_0_100', 'composite_0_100',
        'guardrail_status', 'guardrail_reasons',
        # Guardrail metrics
        'beneishM', 'altmanZ', 'accruals_noa_%', 'netShareIssuance_12m_%',
        'mna_flag', 'revenue_growth_3y',
        # Quality metrics
        'roic', 'roe', 'roa',
        'grossMargin', 'opMargin', 'netMargin',
        'revenueGrowth', 'epsGrowth',
        # Moat metrics
        'moat_score', 'pricing_power_score', 'roic_persistence_score',
        # Degradation scores
        'piotroski_fscore', 'piotroski_fscore_delta',
        'mohanram_gscore', 'mohanram_gscore_delta',
        'quality_degradation_score', 'quality_degradation_delta',
        # Valuation
        'peRatio', 'pbRatio', 'marketCap'
    ]

    # Select available columns
    available_cols = [col for col in analysis_cols if col in df.columns]
    analysis_df = high_q_rojo[available_cols]

    print("-"*80)
    print("COMPANY-BY-COMPANY ANALYSIS")
    print("-"*80)
    print()

    for idx, row in analysis_df.iterrows():
        print(f"\n{'='*80}")
        print(f"{row['symbol']} - {row.get('name', 'N/A')}")
        print(f"{'='*80}")

        print(f"\n📊 OVERVIEW:")
        print(f"  Industry: {row['industry']}")
        print(f"  Quality Score: {row['quality_score_0_100']:.1f}")
        print(f"  Composite Score: {row['composite_0_100']:.1f}")
        print(f"  Market Cap: ${row.get('marketCap', 0)/1e9:.1f}B")

        print(f"\n🚨 GUARDRAIL FLAGS:")
        print(f"  Status: {row['guardrail_status']}")
        reasons = str(row['guardrail_reasons']).split(';')
        for i, reason in enumerate(reasons, 1):
            print(f"    {i}. {reason.strip()}")

        print(f"\n📈 QUALITY METRICS:")
        print(f"  ROIC: {row.get('roic', 0):.1f}%")
        print(f"  ROE:  {row.get('roe', 0):.1f}%")
        print(f"  ROA:  {row.get('roa', 0):.1f}%")
        print(f"  Gross Margin: {row.get('grossMargin', 0):.1f}%")
        print(f"  Operating Margin: {row.get('opMargin', 0):.1f}%")
        print(f"  Net Margin: {row.get('netMargin', 0):.1f}%")

        print(f"\n📊 GROWTH METRICS:")
        print(f"  Revenue Growth: {row.get('revenueGrowth', 0):.1f}%")
        print(f"  Revenue Growth 3Y: {row.get('revenue_growth_3y', 0):.1f}%")
        print(f"  EPS Growth: {row.get('epsGrowth', 0):.1f}%")

        print(f"\n🏰 MOAT METRICS:")
        print(f"  Moat Score: {row.get('moat_score', 0):.1f}")
        print(f"  Pricing Power: {row.get('pricing_power_score', 0):.1f}")
        print(f"  ROIC Persistence: {row.get('roic_persistence_score', 0):.1f}")

        print(f"\n⚠️  GUARDRAIL DETAILS:")
        print(f"  Beneish M-Score: {row.get('beneishM', 'N/A')}")
        print(f"  Altman Z-Score: {row.get('altmanZ', 'N/A')}")
        print(f"  Accruals/NOA: {row.get('accruals_noa_%', 'N/A')}")
        print(f"  Share Dilution: {row.get('netShareIssuance_12m_%', 'N/A')}")
        print(f"  M&A Flag: {row.get('mna_flag', 'N/A')}")

        print(f"\n📉 QUALITY DEGRADATION:")
        piot = row.get('piotroski_fscore', None)
        piot_delta = row.get('piotroski_fscore_delta', None)
        mohan = row.get('mohanram_gscore', None)
        mohan_delta = row.get('mohanram_gscore_delta', None)

        if piot is not None and pd.notna(piot):
            print(f"  Piotroski F-Score: {piot:.0f} (Δ {piot_delta:+.0f})")
        if mohan is not None and pd.notna(mohan):
            print(f"  Mohanram G-Score: {mohan:.0f} (Δ {mohan_delta:+.0f})")

        deg_score = row.get('quality_degradation_score', None)
        deg_delta = row.get('quality_degradation_delta', None)
        if deg_score is not None and pd.notna(deg_score):
            print(f"  Degradation Score: {deg_score:.0f} (Δ {deg_delta:+.0f})")

        print(f"\n💡 ANALYSIS:")

        # Analyze Beneish
        m_score = row.get('beneishM', None)
        if m_score is not None and pd.notna(m_score):
            if m_score > -1.5:
                severity = "CRITICAL"
            elif m_score > -1.78:
                severity = "HIGH"
            elif m_score > -2.0:
                severity = "MODERATE"
            else:
                severity = "BORDERLINE"

            print(f"  • Beneish M={m_score:.2f} ({severity})")
            if m_score > -1.78:
                print(f"    → Flag appears LEGITIMATE - high manipulation risk")
            else:
                print(f"    → Flag may be FALSE POSITIVE - borderline range")

        # Analyze Altman Z
        z_score = row.get('altmanZ', None)
        if z_score is not None and pd.notna(z_score):
            if z_score < 1.8:
                print(f"  • Altman Z={z_score:.2f} (DISTRESS)")
                # Check if should be exempt
                industry = row['industry'].lower()
                if any(kw in industry for kw in ['software', 'saas', 'internet', 'utility', 'restaurant']):
                    print(f"    → Flag is FALSE POSITIVE - asset-light business (should be exempt)")
                elif any(kw in industry for kw in ['oil & gas midstream', 'personal', 'consumer electronics']):
                    print(f"    → Flag is FALSE POSITIVE - industry not suitable for Altman Z")
                else:
                    print(f"    → Flag may be LEGITIMATE - check capital structure")
            elif z_score < 3.0:
                print(f"  • Altman Z={z_score:.2f} (GRAY ZONE)")
                print(f"    → Flag is BORDERLINE - needs context")

        # Analyze dilution
        dilution = row.get('netShareIssuance_12m_%', None)
        if dilution is not None and pd.notna(dilution):
            if abs(dilution) > 10:
                print(f"  • Dilution={dilution:.1f}%")
                if dilution > 20:
                    print(f"    → Flag appears LEGITIMATE - excessive dilution")
                elif dilution > 10:
                    industry = row['industry'].lower()
                    if any(kw in industry for kw in ['biotech', 'pharmaceutical', 'software']):
                        print(f"    → Flag may be FALSE POSITIVE - growth industry (capital raising normal)")
                    else:
                        print(f"    → Flag appears LEGITIMATE - high dilution for mature company")

        # Analyze quality metrics
        roic = row.get('roic', 0)
        roe = row.get('roe', 0)
        margins = row.get('opMargin', 0)

        print(f"\n  • Business Quality:")
        if roic > 20 and roe > 15 and margins > 15:
            print(f"    → EXCELLENT fundamentals (ROIC {roic:.0f}%, ROE {roe:.0f}%, Margin {margins:.0f}%)")
            print(f"    → Guardrail flags likely FALSE POSITIVES")
        elif roic > 15 and roe > 12 and margins > 10:
            print(f"    → GOOD fundamentals (ROIC {roic:.0f}%, ROE {roe:.0f}%, Margin {margins:.0f}%)")
            print(f"    → Guardrail flags need investigation")
        else:
            print(f"    → MIXED fundamentals (ROIC {roic:.0f}%, ROE {roe:.0f}%, Margin {margins:.0f}%)")
            print(f"    → Guardrail flags may be LEGITIMATE")

        # Degradation analysis
        if deg_delta is not None and pd.notna(deg_delta):
            if deg_delta < -1:
                print(f"  • Quality Degradation: Δ {deg_delta:+.0f}")
                print(f"    → DETERIORATING - guardrail flags may be early warning")
            elif deg_delta > 1:
                print(f"  • Quality Improvement: Δ {deg_delta:+.0f}")
                print(f"    → IMPROVING - guardrail flags may be stale/false positive")

        print(f"\n🎯 RECOMMENDATION:")

        # Decision logic
        has_excellent_fundamentals = roic > 20 and roe > 15 and margins > 15
        has_borderline_beneish = m_score is not None and -2.22 < m_score < -1.78
        has_exempt_altman = z_score is not None and z_score < 1.8 and any(
            kw in row['industry'].lower() for kw in
            ['software', 'internet', 'utility', 'oil & gas midstream', 'consumer electronics', 'personal']
        )

        if has_excellent_fundamentals and (has_borderline_beneish or has_exempt_altman):
            print(f"  ► FALSE POSITIVE - Consider unblocking")
            print(f"    Excellent fundamentals + borderline/inappropriate flags")
        elif roic < 10 or m_score is not None and m_score > -1.5:
            print(f"  ► LEGITIMATE FLAG - Keep blocked")
            print(f"    Weak fundamentals or critical accounting concerns")
        else:
            print(f"  ► NEEDS MANUAL REVIEW")
            print(f"    Mixed signals - check company-specific context")

    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}\n")

    # Summary statistics
    print("Distribution by primary flag:")
    for reason in analysis_df['guardrail_reasons'].value_counts().head(5).items():
        print(f"  {reason[0][:60]}: {reason[1]} companies")

    print(f"\nAverage metrics for high-quality ROJO:")
    print(f"  ROIC: {analysis_df['roic'].mean():.1f}%")
    print(f"  ROE: {analysis_df['roe'].mean():.1f}%")
    print(f"  Operating Margin: {analysis_df['opMargin'].mean():.1f}%")
    print(f"  Revenue Growth: {analysis_df['revenueGrowth'].mean():.1f}%")

    # Export detailed CSV
    output_path = Path(csv_path).parent / 'high_quality_rojo_analysis.csv'
    analysis_df.to_csv(output_path, index=False)
    print(f"\n✓ Detailed data exported to: {output_path}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python analyze_high_quality_rojo.py <results.csv>")
        sys.exit(1)

    analyze_high_quality_rojo(sys.argv[1])
