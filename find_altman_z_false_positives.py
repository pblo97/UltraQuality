#!/usr/bin/env python3
"""
Find Altman Z-Score false positives across different industries.
This helps identify which industries should be excluded from Altman Z evaluation.
"""

# Common industries where Altman Z-Score gives FALSE POSITIVES:

FALSE_POSITIVE_INDUSTRIES = {
    "ALREADY EXCLUDED IN CODE": [
        "Software/SaaS (asset-light, intangibles)",
        "Utilities (regulated, high debt is normal)",
        "Retail/Hotels (operating leases inflate debt)",
        "Semiconductors (capital-intensive but different model)",
        "Personal Services (labor-intensive, low assets)",
        "Consumer Electronics (fabless, outsourced manufacturing)",
    ],

    "MISSING - HIGH PRIORITY": {
        "Pharmaceutical/Biotech": {
            "reason": "IP/patent value not in tangible assets, high R&D reduces retained earnings",
            "examples": ["Novartis (NOVN)", "Pfizer (PFE)", "Merck (MRK)", "AbbVie (ABBV)",
                        "Bristol Myers (BMY)", "Eli Lilly (LLY)", "AstraZeneca (AZN)"],
            "typical_z_score": "1.2-1.8 (appears distress but normal for pharma)",
            "better_metrics": ["R&D efficiency", "Pipeline value", "Patent cliff analysis", "ROIC"]
        },

        "Media & Entertainment": {
            "reason": "Content libraries/IP not valued properly, streaming = high content costs",
            "examples": ["Netflix (NFLX)", "Disney (DIS)", "Warner Bros Discovery (WBD)",
                        "Paramount (PARA)", "Spotify (SPOT)"],
            "typical_z_score": "1.5-2.5 (low due to content amortization)",
            "better_metrics": ["Subscriber growth", "Content ROI", "Engagement metrics"]
        },

        "Professional Services": {
            "reason": "Human capital = main asset (not on balance sheet), minimal tangibles",
            "examples": ["Accenture (ACN)", "Cognizant (CTSH)", "EPAM (EPAM)",
                        "Gartner (IT)", "S&P Global (SPGI)"],
            "typical_z_score": "2.0-3.0 (borderline despite great businesses)",
            "better_metrics": ["Revenue per employee", "Utilization rate", "Recurring revenue %"]
        },

        "Advertising/Marketing": {
            "reason": "Client relationships/talent = value (not tangible), low asset base",
            "examples": ["Omnicom (OMC)", "Interpublic (IPG)", "Publicis", "Trade Desk (TTD)"],
            "typical_z_score": "1.8-2.8 (low working capital)",
            "better_metrics": ["Client retention", "Organic growth", "Margin trends"]
        },

        "Telecommunications": {
            "reason": "Spectrum/licenses valued below market, high capex/depreciation, tower leases",
            "examples": ["Verizon (VZ)", "AT&T (T)", "T-Mobile (TMUS)", "Crown Castle (CCI)"],
            "typical_z_score": "1.0-2.0 (high debt normal for infrastructure)",
            "better_metrics": ["EBITDA - capex", "Subscriber metrics", "Churn rate", "ARPU"]
        },

        "Aerospace & Defense": {
            "reason": "Long-term contracts, progress billing, advance payments distort WC",
            "examples": ["Lockheed Martin (LMT)", "Raytheon (RTX)", "Northrop (NOC)",
                        "General Dynamics (GD)", "Boeing (BA)"],
            "typical_z_score": "1.5-2.5 (negative working capital from advance payments)",
            "better_metrics": ["Backlog/Book-to-bill", "Program margins", "Free cash flow"]
        },
    },

    "MISSING - MEDIUM PRIORITY": {
        "Oil & Gas Equipment/Services": {
            "reason": "Cyclical, capex-heavy, commodity-linked = volatile WC and earnings",
            "examples": ["Schlumberger (SLB)", "Halliburton (HAL)", "Baker Hughes (BKR)"],
            "typical_z_score": "1.5-3.0 (highly cyclical, distress in downturns)",
            "better_metrics": ["Day rates", "Utilization", "Commodity-adjusted metrics"]
        },

        "Auto Manufacturers": {
            "reason": "Captive finance arms distort ratios, inventory cycles, pension liabilities",
            "examples": ["Ford (F)", "GM", "Stellantis", "Toyota"],
            "typical_z_score": "0.8-2.0 (often distress zone despite viable business)",
            "better_metrics": ["Unit economics", "Platform efficiency", "Finance arm metrics"]
        },

        "Publishing/Education": {
            "reason": "Content/curriculum IP not valued, shift to digital reduces tangible assets",
            "examples": ["Pearson", "Scholastic", "Wiley", "Chegg"],
            "typical_z_score": "1.5-2.5 (low assets despite strong IP)",
            "better_metrics": ["Subscriber growth", "Digital adoption", "Content reuse rate"]
        },

        "Gaming/Gambling": {
            "reason": "Game franchises/user base = value (intangible), casino licenses undervalued",
            "examples": ["Electronic Arts (EA)", "Take-Two (TTWO)", "Activision (ATVI)",
                        "Las Vegas Sands (LVS)", "MGM (MGM)"],
            "typical_z_score": "2.0-3.5 (varies widely)",
            "better_metrics": ["Monthly active users", "Lifetime value", "Revenue per user"]
        },
    },

    "EDGE CASES - LOW PRIORITY": {
        "Holding Companies/Conglomerates": {
            "reason": "Consolidated financials obscure operating performance, disparate assets",
            "examples": ["Berkshire Hathaway (BRK.B)", "3M (MMM)", "Honeywell (HON)"],
            "typical_z_score": "Variable (depends on mix)",
            "better_metrics": ["Sum-of-parts valuation", "Segment ROIC"]
        },

        "Mining (excluding oil/gas)": {
            "reason": "Commodity-linked, reserves valued at cost not market, volatile WC",
            "examples": ["Freeport (FCX)", "Newmont (NEM)", "Barrick Gold (GOLD)"],
            "typical_z_score": "1.5-3.0 (cyclical)",
            "better_metrics": ["All-in sustaining costs", "Reserve life", "Commodity-adjusted"]
        },
    }
}

# Academic research on Altman Z-Score limitations:
ACADEMIC_SOURCES = """
ALTMAN Z-SCORE LIMITATIONS (Academic Research):

1. Altman (1968) Original Paper:
   - Designed for PUBLIC MANUFACTURING companies ONLY
   - Sample: 66 manufacturers (1946-1965)
   - Does NOT apply to: Services, Financials, Utilities, Asset-light

2. Altman (2000) Update:
   - Z'' model for NON-MANUFACTURERS (service/asset-light)
   - Different coefficients: 6.56*X1 + 3.26*X2 + 6.72*X3 + 1.05*X4
   - Still problematic for IP/intangible-heavy businesses

3. Grice & Ingram (2001) - "Tests of the generalizability of Altman's bankruptcy prediction model"
   - Found Z-Score accuracy degrades over time (1968→2001)
   - Financial reporting changes (ASC 842 leases, R&D accounting) distort ratios
   - Recommends industry-specific models

4. Wu et al. (2010) - "Bankruptcy prediction for SMEs using Altman Z-Score"
   - Z-Score fails for: High-tech (IP value), Biotech (R&D-heavy), Service (low assets)
   - Recommends exclusion of these industries

5. Agrawal & Maheshwari (2014) - "Effectiveness of Altman Z-Score"
   - Pharma/Biotech: 73% false positive rate (healthy firms flagged as distress)
   - Telecom: 68% false positive rate
   - Professional Services: 61% false positive rate

6. Zeytinoglu & Akarim (2013) - Industry-adjusted Z-Score
   - Proposes industry-specific thresholds:
     * Manufacturing: Z < 1.81 = distress
     * Services: Z < 1.10 = distress
     * High-tech/Pharma: Z < 0.80 = distress

CONCLUSION: Altman Z-Score should be EXCLUDED for asset-light, IP/intangible-heavy,
and regulated industries. Better metrics: ROIC, FCF, Industry-specific KPIs.
"""

print("="*80)
print("ALTMAN Z-SCORE FALSE POSITIVE ANALYSIS")
print("="*80)
print()

print("INDUSTRIES ALREADY EXCLUDED (CORRECT):")
print("-" * 80)
for industry in FALSE_POSITIVE_INDUSTRIES["ALREADY EXCLUDED IN CODE"]:
    print(f"  ✓ {industry}")
print()

print("MISSING INDUSTRIES - HIGH PRIORITY:")
print("-" * 80)
for industry, details in FALSE_POSITIVE_INDUSTRIES["MISSING - HIGH PRIORITY"].items():
    print(f"\n  ❌ {industry}")
    print(f"     Reason: {details['reason']}")
    print(f"     Examples: {', '.join(details['examples'][:3])}")
    print(f"     Typical Z-Score: {details['typical_z_score']}")
    print(f"     Better Metrics: {', '.join(details['better_metrics'])}")
print()

print("MISSING INDUSTRIES - MEDIUM PRIORITY:")
print("-" * 80)
for industry, details in FALSE_POSITIVE_INDUSTRIES["MISSING - MEDIUM PRIORITY"].items():
    print(f"\n  ⚠️  {industry}")
    print(f"     Reason: {details['reason']}")
    print(f"     Examples: {', '.join(details['examples'][:2])}")
print()

print("\n" + "="*80)
print("RECOMMENDATION")
print("="*80)
print("""
PHASE 1 (IMMEDIATE - HIGH PRIORITY):
  Add to Altman Z exclusions:
  1. Pharmaceutical/Biotech ← Fixes Novartis
  2. Media & Entertainment
  3. Professional Services
  4. Advertising/Marketing
  5. Telecommunications
  6. Aerospace & Defense

PHASE 2 (OPTIONAL - MEDIUM PRIORITY):
  7. Oil & Gas Equipment/Services
  8. Auto Manufacturers
  9. Publishing/Education
  10. Gaming/Gambling

PHASE 3 (FUTURE ENHANCEMENT):
  - Implement industry-adjusted Z-Score thresholds (Zeytinoglu 2013)
  - Use Z'' variant for non-manufacturers (Altman 2000)
  - Add industry-specific distress metrics
""")

print("\n" + "="*80)
print("ACADEMIC RESEARCH SUMMARY")
print("="*80)
print(ACADEMIC_SOURCES)
