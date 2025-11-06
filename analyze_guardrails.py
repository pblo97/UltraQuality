"""
Guardrail Calibration Analysis Tool

Analyzes screener results to help calibrate guardrail thresholds.
Generates detailed reports for each guardrail type with:
- Distribution statistics
- Affected companies by quality tier
- False positive detection
- Calibration recommendations

Usage:
    python analyze_guardrails.py --results output/screener_results.csv
    python analyze_guardrails.py --results output/screener_results.csv --guardrail beneish
"""

import pandas as pd
import numpy as np
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import argparse

class GuardrailAnalyzer:
    """Analyze guardrail effectiveness and calibration."""

    def __init__(self, results_df: pd.DataFrame):
        self.df = results_df.copy()
        self.total_companies = len(self.df)

    @staticmethod
    def _safe_percentage(numerator: float, denominator: float) -> float:
        """Calculate percentage safely, handling division by zero."""
        if denominator == 0 or pd.isna(denominator):
            return 0.0
        return (numerator / denominator) * 100

    def generate_full_report(self) -> str:
        """Generate comprehensive calibration report for all guardrails."""
        report = []
        report.append("=" * 80)
        report.append("GUARDRAIL CALIBRATION ANALYSIS")
        report.append("=" * 80)
        report.append(f"\nTotal Companies Analyzed: {self.total_companies}")
        report.append(f"Date: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("\n")

        # Overall status distribution
        report.append(self._analyze_overall_status())

        # Individual guardrail analysis
        report.append("\n" + "=" * 80)
        report.append("DETAILED GUARDRAIL ANALYSIS")
        report.append("=" * 80)

        report.append(self._analyze_beneish())
        report.append(self._analyze_altman_z())
        report.append(self._analyze_revenue_decline())
        report.append(self._analyze_mna_flag())
        report.append(self._analyze_dilution())
        report.append(self._analyze_accruals())

        # Quality score analysis of blocked companies
        report.append(self._analyze_blocked_quality())

        # Calibration recommendations
        report.append(self._generate_recommendations())

        return "\n".join(report)

    def _analyze_overall_status(self) -> str:
        """Analyze overall guardrail status distribution."""
        lines = []
        lines.append("\n" + "-" * 80)
        lines.append("OVERALL GUARDRAIL STATUS")
        lines.append("-" * 80)

        status_counts = self.df['guardrail_status'].value_counts()
        total = len(self.df)

        for status in ['VERDE', 'AMBAR', 'ROJO']:
            count = status_counts.get(status, 0)
            pct = self._safe_percentage(count, total)
            lines.append(f"{status:8s}: {count:4d} companies ({pct:5.1f}%)")

        # Top guardrail reasons
        lines.append("\nTop 15 Guardrail Reasons:")
        if 'guardrail_reasons' in self.df.columns:
            reasons = self.df['guardrail_reasons'].value_counts().head(15)
            for i, (reason, count) in enumerate(reasons.items(), 1):
                pct = self._safe_percentage(count, total)
                lines.append(f"  {i:2d}. {reason:60s} {count:4d} ({pct:4.1f}%)")

        return "\n".join(lines)

    def _analyze_beneish(self) -> str:
        """Analyze Beneish M-Score distribution and affected companies."""
        lines = []
        lines.append("\n" + "-" * 80)
        lines.append("BENEISH M-SCORE ANALYSIS")
        lines.append("-" * 80)

        if 'beneishM' not in self.df.columns:
            lines.append("⚠️  Beneish M-Score not available in results")
            return "\n".join(lines)

        beneish_df = self.df[self.df['beneishM'].notna()].copy()

        if len(beneish_df) == 0:
            lines.append("⚠️  No companies with Beneish M-Score data")
            return "\n".join(lines)

        # Distribution statistics
        lines.append("\nDistribution Statistics:")
        lines.append(f"  Companies with data: {len(beneish_df)}")
        lines.append(f"  Mean:   {beneish_df['beneishM'].mean():6.2f}")
        lines.append(f"  Median: {beneish_df['beneishM'].median():6.2f}")
        lines.append(f"  Std:    {beneish_df['beneishM'].std():6.2f}")
        lines.append(f"  Min:    {beneish_df['beneishM'].min():6.2f}")
        lines.append(f"  Max:    {beneish_df['beneishM'].max():6.2f}")

        # Percentiles
        lines.append("\nPercentiles:")
        for p in [10, 25, 50, 75, 90, 95, 99]:
            val = beneish_df['beneishM'].quantile(p/100)
            lines.append(f"  P{p:2d}: {val:6.2f}")

        # Companies by threshold zones
        lines.append("\nCompanies by Zone:")
        zones = [
            ("CRITICAL (M > -1.5)", beneish_df['beneishM'] > -1.5),
            ("HIGH RISK (M > -1.78)", (beneish_df['beneishM'] > -1.78) & (beneish_df['beneishM'] <= -1.5)),
            ("MODERATE (M > -2.0)", (beneish_df['beneishM'] > -2.0) & (beneish_df['beneishM'] <= -1.78)),
            ("BORDERLINE (M > -2.22)", (beneish_df['beneishM'] > -2.22) & (beneish_df['beneishM'] <= -2.0)),
            ("CLEAN (M ≤ -2.22)", beneish_df['beneishM'] <= -2.22),
        ]

        for zone_name, mask in zones:
            count = mask.sum()
            pct = self._safe_percentage(count, len(beneish_df))
            lines.append(f"  {zone_name:30s}: {count:4d} ({pct:5.1f}%)")

        # Companies flagged by Beneish (ROJO or AMBAR due to Beneish)
        beneish_flagged = beneish_df[
            beneish_df['guardrail_reasons'].str.contains('Beneish', case=False, na=False)
        ].copy()

        if len(beneish_flagged) > 0:
            lines.append(f"\n⚠️  Companies Flagged by Beneish: {len(beneish_flagged)}")

            # By industry
            lines.append("\nBy Industry:")
            industry_counts = beneish_flagged['industry'].value_counts().head(10)
            for industry, count in industry_counts.items():
                avg_m = beneish_flagged[beneish_flagged['industry'] == industry]['beneishM'].mean()
                lines.append(f"  {industry:40s}: {count:3d} companies (avg M={avg_m:5.2f})")

            # High quality companies blocked by Beneish
            high_quality_blocked = beneish_flagged[
                (beneish_flagged['quality_score_0_100'] >= 70) &
                (beneish_flagged['guardrail_status'] == 'ROJO')
            ].copy()

            if len(high_quality_blocked) > 0:
                lines.append(f"\n🚨 HIGH QUALITY COMPANIES BLOCKED BY BENEISH: {len(high_quality_blocked)}")
                lines.append("    (Quality ≥70, Status=ROJO due to Beneish)")
                lines.append("")
                lines.append(f"{'Ticker':<8} {'Industry':<35} {'Quality':<8} {'Beneish M':<10} {'Status'}")
                lines.append("-" * 80)

                for _, row in high_quality_blocked.sort_values('quality_score_0_100', ascending=False).head(15).iterrows():
                    ticker = row.get('ticker', 'N/A')[:7]
                    industry = row.get('industry', 'N/A')[:34]
                    quality = row.get('quality_score_0_100', 0)
                    beneish = row.get('beneishM', 0)
                    status = row.get('guardrail_status', 'N/A')
                    lines.append(f"{ticker:<8} {industry:<35} {quality:6.1f}   {beneish:6.2f}     {status}")

        return "\n".join(lines)

    def _analyze_altman_z(self) -> str:
        """Analyze Altman Z-Score distribution."""
        lines = []
        lines.append("\n" + "-" * 80)
        lines.append("ALTMAN Z-SCORE ANALYSIS")
        lines.append("-" * 80)

        if 'altmanZ' not in self.df.columns:
            lines.append("⚠️  Altman Z-Score not available in results")
            return "\n".join(lines)

        altman_df = self.df[self.df['altmanZ'].notna()].copy()

        if len(altman_df) == 0:
            lines.append("⚠️  No companies with Altman Z-Score data")
            return "\n".join(lines)

        # Distribution statistics
        lines.append("\nDistribution Statistics:")
        lines.append(f"  Companies with data: {len(altman_df)}")
        lines.append(f"  Mean:   {altman_df['altmanZ'].mean():6.2f}")
        lines.append(f"  Median: {altman_df['altmanZ'].median():6.2f}")
        lines.append(f"  Std:    {altman_df['altmanZ'].std():6.2f}")
        lines.append(f"  Min:    {altman_df['altmanZ'].min():6.2f}")
        lines.append(f"  Max:    {altman_df['altmanZ'].max():6.2f}")

        # Companies by zone
        lines.append("\nCompanies by Zone:")
        zones = [
            ("DISTRESS (Z < 1.8)", altman_df['altmanZ'] < 1.8),
            ("GRAY ZONE (1.8 ≤ Z < 3.0)", (altman_df['altmanZ'] >= 1.8) & (altman_df['altmanZ'] < 3.0)),
            ("SAFE ZONE (Z ≥ 3.0)", altman_df['altmanZ'] >= 3.0),
        ]

        for zone_name, mask in zones:
            count = mask.sum()
            pct = self._safe_percentage(count, len(altman_df))
            lines.append(f"  {zone_name:30s}: {count:4d} ({pct:5.1f}%)")

        # Distress zone companies
        distress = altman_df[altman_df['altmanZ'] < 1.8].copy()

        if len(distress) > 0:
            lines.append(f"\n⚠️  DISTRESS ZONE COMPANIES (Z < 1.8): {len(distress)}")

            # By industry
            lines.append("\nBy Industry:")
            industry_counts = distress['industry'].value_counts().head(10)
            for industry, count in industry_counts.items():
                avg_z = distress[distress['industry'] == industry]['altmanZ'].mean()
                lines.append(f"  {industry:40s}: {count:3d} companies (avg Z={avg_z:5.2f})")

            # Extreme distress (Z < 1.0)
            extreme_distress = distress[distress['altmanZ'] < 1.0].copy()
            if len(extreme_distress) > 0:
                lines.append(f"\n🚨 EXTREME DISTRESS (Z < 1.0): {len(extreme_distress)}")
                lines.append("")
                lines.append(f"{'Ticker':<8} {'Industry':<35} {'Altman Z':<10} {'Quality':<8} {'Status'}")
                lines.append("-" * 80)

                for _, row in extreme_distress.sort_values('altmanZ').head(15).iterrows():
                    ticker = row.get('ticker', 'N/A')[:7]
                    industry = row.get('industry', 'N/A')[:34]
                    z_score = row.get('altmanZ', 0)
                    quality = row.get('quality_score_0_100', 0)
                    status = row.get('guardrail_status', 'N/A')
                    lines.append(f"{ticker:<8} {industry:<35} {z_score:6.2f}     {quality:6.1f}   {status}")

        return "\n".join(lines)

    def _analyze_revenue_decline(self) -> str:
        """Analyze revenue growth and decline patterns."""
        lines = []
        lines.append("\n" + "-" * 80)
        lines.append("REVENUE GROWTH ANALYSIS")
        lines.append("-" * 80)

        if 'revenue_growth_3y' not in self.df.columns:
            lines.append("⚠️  Revenue growth data not available")
            return "\n".join(lines)

        rev_df = self.df[self.df['revenue_growth_3y'].notna()].copy()

        if len(rev_df) == 0:
            lines.append("⚠️  No companies with revenue growth data")
            return "\n".join(lines)

        # Distribution statistics
        lines.append("\nDistribution Statistics (3Y CAGR %):")
        lines.append(f"  Companies with data: {len(rev_df)}")
        lines.append(f"  Mean:   {rev_df['revenue_growth_3y'].mean():6.1f}%")
        lines.append(f"  Median: {rev_df['revenue_growth_3y'].median():6.1f}%")
        lines.append(f"  Std:    {rev_df['revenue_growth_3y'].std():6.1f}%")
        lines.append(f"  Min:    {rev_df['revenue_growth_3y'].min():6.1f}%")
        lines.append(f"  Max:    {rev_df['revenue_growth_3y'].max():6.1f}%")

        # Companies by growth tier
        lines.append("\nCompanies by Growth Tier:")
        tiers = [
            ("DECLINING FAST (< -5%)", rev_df['revenue_growth_3y'] < -5),
            ("DECLINING SLOW (-5% to 0%)", (rev_df['revenue_growth_3y'] >= -5) & (rev_df['revenue_growth_3y'] < 0)),
            ("FLAT (0% to 5%)", (rev_df['revenue_growth_3y'] >= 0) & (rev_df['revenue_growth_3y'] < 5)),
            ("GROWING (5% to 15%)", (rev_df['revenue_growth_3y'] >= 5) & (rev_df['revenue_growth_3y'] < 15)),
            ("HIGH GROWTH (≥ 15%)", rev_df['revenue_growth_3y'] >= 15),
        ]

        for tier_name, mask in tiers:
            count = mask.sum()
            pct = self._safe_percentage(count, len(rev_df))
            avg_quality = rev_df[mask]['quality_score_0_100'].mean() if count > 0 else 0
            lines.append(f"  {tier_name:30s}: {count:4d} ({pct:5.1f}%) - Avg Q: {avg_quality:4.1f}")

        # Declining revenue companies
        declining = rev_df[rev_df['revenue_growth_3y'] < 0].copy()

        if len(declining) > 0:
            lines.append(f"\n⚠️  DECLINING REVENUE COMPANIES: {len(declining)}")

            # By industry
            lines.append("\nBy Industry:")
            industry_counts = declining['industry'].value_counts().head(10)
            for industry, count in industry_counts.items():
                avg_rev = declining[declining['industry'] == industry]['revenue_growth_3y'].mean()
                avg_q = declining[declining['industry'] == industry]['quality_score_0_100'].mean()
                lines.append(f"  {industry:40s}: {count:3d} (rev={avg_rev:5.1f}%, Q={avg_q:4.1f})")

            # High quality companies with declining revenue
            high_quality_declining = declining[declining['quality_score_0_100'] >= 70].copy()

            if len(high_quality_declining) > 0:
                lines.append(f"\n🤔 HIGH QUALITY + DECLINING REVENUE: {len(high_quality_declining)}")
                lines.append("    (May be temporary headwinds or structural decline)")
                lines.append("")
                lines.append(f"{'Ticker':<8} {'Industry':<35} {'Rev 3Y':<8} {'Quality':<8} {'Status'}")
                lines.append("-" * 80)

                for _, row in high_quality_declining.sort_values('quality_score_0_100', ascending=False).head(15).iterrows():
                    ticker = row.get('ticker', 'N/A')[:7]
                    industry = row.get('industry', 'N/A')[:34]
                    rev_growth = row.get('revenue_growth_3y', 0)
                    quality = row.get('quality_score_0_100', 0)
                    status = row.get('guardrail_status', 'N/A')
                    lines.append(f"{ticker:<8} {industry:<35} {rev_growth:6.1f}%  {quality:6.1f}   {status}")

        return "\n".join(lines)

    def _analyze_mna_flag(self) -> str:
        """Analyze M&A / goodwill growth flag."""
        lines = []
        lines.append("\n" + "-" * 80)
        lines.append("M&A / GOODWILL GROWTH ANALYSIS")
        lines.append("-" * 80)

        if 'mna_flag' not in self.df.columns:
            lines.append("⚠️  M&A flag data not available")
            return "\n".join(lines)

        mna_df = self.df[self.df['mna_flag'].notna()].copy()

        if len(mna_df) == 0:
            lines.append("⚠️  No companies with M&A flag data")
            return "\n".join(lines)

        # Distribution
        lines.append("\nM&A Flag Distribution:")
        flag_counts = mna_df['mna_flag'].value_counts()
        total = len(mna_df)

        for flag in ['LOW', 'MODERATE', 'HIGH']:
            count = flag_counts.get(flag, 0)
            pct = self._safe_percentage(count, total)
            avg_quality = mna_df[mna_df['mna_flag'] == flag]['quality_score_0_100'].mean() if count > 0 else 0
            lines.append(f"  {flag:10s}: {count:4d} ({pct:5.1f}%) - Avg Quality: {avg_quality:4.1f}")

        # HIGH M&A flag companies
        high_mna = mna_df[mna_df['mna_flag'] == 'HIGH'].copy()

        if len(high_mna) > 0:
            lines.append(f"\n⚠️  HIGH M&A ACTIVITY COMPANIES: {len(high_mna)}")

            # By industry
            lines.append("\nBy Industry:")
            industry_counts = high_mna['industry'].value_counts().head(10)
            for industry, count in industry_counts.items():
                avg_q = high_mna[high_mna['industry'] == industry]['quality_score_0_100'].mean()
                lines.append(f"  {industry:40s}: {count:3d} companies (avg Q={avg_q:4.1f})")

            # High quality + High M&A
            high_quality_mna = high_mna[high_mna['quality_score_0_100'] >= 70].copy()

            if len(high_quality_mna) > 0:
                lines.append(f"\n💼 HIGH QUALITY + HIGH M&A: {len(high_quality_mna)}")
                lines.append("    (Serial acquirers - may be legitimate strategy)")
                lines.append("")
                lines.append(f"{'Ticker':<8} {'Industry':<35} {'Quality':<8} {'M&A':<6} {'Status'}")
                lines.append("-" * 80)

                for _, row in high_quality_mna.sort_values('quality_score_0_100', ascending=False).head(15).iterrows():
                    ticker = row.get('ticker', 'N/A')[:7]
                    industry = row.get('industry', 'N/A')[:34]
                    quality = row.get('quality_score_0_100', 0)
                    mna = row.get('mna_flag', 'N/A')
                    status = row.get('guardrail_status', 'N/A')
                    lines.append(f"{ticker:<8} {industry:<35} {quality:6.1f}   {mna:<6} {status}")

        return "\n".join(lines)

    def _analyze_dilution(self) -> str:
        """Analyze share dilution patterns."""
        lines = []
        lines.append("\n" + "-" * 80)
        lines.append("SHARE DILUTION ANALYSIS")
        lines.append("-" * 80)

        if 'netShareIssuance_12m_%' not in self.df.columns:
            lines.append("⚠️  Share dilution data not available")
            return "\n".join(lines)

        dil_df = self.df[self.df['netShareIssuance_12m_%'].notna()].copy()

        if len(dil_df) == 0:
            lines.append("⚠️  No companies with dilution data")
            return "\n".join(lines)

        # Distribution statistics
        lines.append("\nDistribution Statistics (12m %):")
        lines.append(f"  Companies with data: {len(dil_df)}")
        lines.append(f"  Mean:   {dil_df['netShareIssuance_12m_%'].mean():6.1f}%")
        lines.append(f"  Median: {dil_df['netShareIssuance_12m_%'].median():6.1f}%")
        lines.append(f"  Std:    {dil_df['netShareIssuance_12m_%'].std():6.1f}%")
        lines.append(f"  Min:    {dil_df['netShareIssuance_12m_%'].min():6.1f}%")
        lines.append(f"  Max:    {dil_df['netShareIssuance_12m_%'].max():6.1f}%")

        # Companies by tier
        lines.append("\nCompanies by Dilution Tier:")
        tiers = [
            ("BUYBACK (< -5%)", dil_df['netShareIssuance_12m_%'] < -5),
            ("NEUTRAL (-5% to 5%)", (dil_df['netShareIssuance_12m_%'] >= -5) & (dil_df['netShareIssuance_12m_%'] <= 5)),
            ("MODERATE DILUTION (5% to 10%)", (dil_df['netShareIssuance_12m_%'] > 5) & (dil_df['netShareIssuance_12m_%'] <= 10)),
            ("HIGH DILUTION (> 10%)", dil_df['netShareIssuance_12m_%'] > 10),
        ]

        for tier_name, mask in tiers:
            count = mask.sum()
            pct = self._safe_percentage(count, len(dil_df))
            lines.append(f"  {tier_name:35s}: {count:4d} ({pct:5.1f}%)")

        # High dilution companies
        high_dilution = dil_df[dil_df['netShareIssuance_12m_%'] > 10].copy()

        if len(high_dilution) > 0:
            lines.append(f"\n⚠️  HIGH DILUTION COMPANIES (>10%): {len(high_dilution)}")

            # Top diluters
            lines.append("\nTop 15 Diluters:")
            lines.append(f"{'Ticker':<8} {'Industry':<35} {'Dilution':<10} {'Quality':<8} {'Status'}")
            lines.append("-" * 80)

            for _, row in high_dilution.sort_values('netShareIssuance_12m_%', ascending=False).head(15).iterrows():
                ticker = row.get('ticker', 'N/A')[:7]
                industry = row.get('industry', 'N/A')[:34]
                dilution = row.get('netShareIssuance_12m_%', 0)
                quality = row.get('quality_score_0_100', 0)
                status = row.get('guardrail_status', 'N/A')
                lines.append(f"{ticker:<8} {industry:<35} {dilution:6.1f}%    {quality:6.1f}   {status}")

        return "\n".join(lines)

    def _analyze_accruals(self) -> str:
        """Analyze accruals/NOA patterns."""
        lines = []
        lines.append("\n" + "-" * 80)
        lines.append("ACCRUALS / NOA ANALYSIS")
        lines.append("-" * 80)

        if 'accruals_noa_%' not in self.df.columns:
            lines.append("⚠️  Accruals data not available")
            return "\n".join(lines)

        acc_df = self.df[self.df['accruals_noa_%'].notna()].copy()

        if len(acc_df) == 0:
            lines.append("⚠️  No companies with accruals data")
            return "\n".join(lines)

        # Distribution statistics
        lines.append("\nDistribution Statistics (%):")
        lines.append(f"  Companies with data: {len(acc_df)}")
        lines.append(f"  Mean:   {acc_df['accruals_noa_%'].mean():6.1f}%")
        lines.append(f"  Median: {acc_df['accruals_noa_%'].median():6.1f}%")
        lines.append(f"  Std:    {acc_df['accruals_noa_%'].std():6.1f}%")
        lines.append(f"  Min:    {acc_df['accruals_noa_%'].min():6.1f}%")
        lines.append(f"  Max:    {acc_df['accruals_noa_%'].max():6.1f}%")

        # High accruals (> 15%)
        high_accruals = acc_df[acc_df['accruals_noa_%'] > 15].copy()

        if len(high_accruals) > 0:
            lines.append(f"\n⚠️  HIGH ACCRUALS COMPANIES (>15%): {len(high_accruals)}")
            lines.append("    (Earnings may not be backed by cash flow)")

            lines.append("\nTop 10 High Accruals:")
            lines.append(f"{'Ticker':<8} {'Industry':<35} {'Accruals':<10} {'Quality':<8} {'Status'}")
            lines.append("-" * 80)

            for _, row in high_accruals.sort_values('accruals_noa_%', ascending=False).head(10).iterrows():
                ticker = row.get('ticker', 'N/A')[:7]
                industry = row.get('industry', 'N/A')[:34]
                accruals = row.get('accruals_noa_%', 0)
                quality = row.get('quality_score_0_100', 0)
                status = row.get('guardrail_status', 'N/A')
                lines.append(f"{ticker:<8} {industry:<35} {accruals:6.1f}%    {quality:6.1f}   {status}")

        return "\n".join(lines)

    def _analyze_blocked_quality(self) -> str:
        """Analyze quality scores of companies blocked by guardrails."""
        lines = []
        lines.append("\n" + "-" * 80)
        lines.append("BLOCKED COMPANIES QUALITY ANALYSIS")
        lines.append("-" * 80)

        rojo = self.df[self.df['guardrail_status'] == 'ROJO'].copy()
        ambar = self.df[self.df['guardrail_status'] == 'AMBAR'].copy()

        lines.append(f"\nROJO Companies: {len(rojo)}")
        if len(rojo) > 0 and 'quality_score_0_100' in rojo.columns:
            lines.append(f"  Avg Quality: {rojo['quality_score_0_100'].mean():5.1f}")
            lines.append(f"  Median Quality: {rojo['quality_score_0_100'].median():5.1f}")

            # High quality ROJO (potential false positives)
            high_q_rojo = rojo[rojo['quality_score_0_100'] >= 80]
            if len(high_q_rojo) > 0:
                lines.append(f"\n  🚨 HIGH QUALITY ROJO (Q≥80): {len(high_q_rojo)} companies")
                lines.append("     These may be false positives worth reviewing:")
                lines.append("")
                lines.append(f"  {'Ticker':<8} {'Industry':<30} {'Quality':<8} {'Reason'}")
                lines.append("  " + "-" * 78)

                for _, row in high_q_rojo.sort_values('quality_score_0_100', ascending=False).head(10).iterrows():
                    ticker = row.get('ticker', 'N/A')[:7]
                    industry = row.get('industry', 'N/A')[:29]
                    quality = row.get('quality_score_0_100', 0)
                    reason = row.get('guardrail_reasons', 'N/A')[:40]
                    lines.append(f"  {ticker:<8} {industry:<30} {quality:6.1f}   {reason}")

        lines.append(f"\nAMBAR Companies: {len(ambar)}")
        if len(ambar) > 0 and 'quality_score_0_100' in ambar.columns:
            lines.append(f"  Avg Quality: {ambar['quality_score_0_100'].mean():5.1f}")
            lines.append(f"  Median Quality: {ambar['quality_score_0_100'].median():5.1f}")

        return "\n".join(lines)

    def _generate_recommendations(self) -> str:
        """Generate calibration recommendations based on analysis."""
        lines = []
        lines.append("\n" + "=" * 80)
        lines.append("CALIBRATION RECOMMENDATIONS")
        lines.append("=" * 80)

        recommendations = []

        # Beneish analysis
        if 'beneishM' in self.df.columns:
            beneish_df = self.df[self.df['beneishM'].notna()]
            high_q_blocked = beneish_df[
                (beneish_df['quality_score_0_100'] >= 80) &
                (beneish_df['guardrail_status'] == 'ROJO') &
                (beneish_df['guardrail_reasons'].str.contains('Beneish', case=False, na=False))
            ]

            if len(high_q_blocked) > 5:
                recommendations.append(
                    f"⚠️  BENEISH: {len(high_q_blocked)} high-quality companies (Q≥80) blocked by Beneish.\n"
                    f"   Consider reviewing industry thresholds or specific cases."
                )
            elif len(high_q_blocked) > 0:
                recommendations.append(
                    f"✅ BENEISH: Only {len(high_q_blocked)} high-quality companies blocked - acceptable rate."
                )
            else:
                recommendations.append(
                    f"✅ BENEISH: No high-quality companies blocked - well calibrated."
                )

        # Altman Z analysis
        if 'altmanZ' in self.df.columns:
            altman_df = self.df[self.df['altmanZ'].notna()]
            distress = altman_df[altman_df['altmanZ'] < 1.8]
            extreme = altman_df[altman_df['altmanZ'] < 1.0]

            pct_distress = self._safe_percentage(len(distress), len(altman_df))
            if pct_distress > 20:
                recommendations.append(
                    f"⚠️  ALTMAN Z: {pct_distress:.1f}% in distress zone - unusually high.\n"
                    f"   May indicate crisis period or need to review industries analyzed."
                )
            else:
                recommendations.append(
                    f"✅ ALTMAN Z: {pct_distress:.1f}% in distress zone - normal range (10-20%)."
                )

            if len(extreme) > 0:
                recommendations.append(
                    f"   📊 {len(extreme)} companies with Z<1.0 (extreme distress) - likely avoid."
                )

        # Revenue decline analysis
        if 'revenue_growth_3y' in self.df.columns:
            rev_df = self.df[self.df['revenue_growth_3y'].notna()]
            declining = rev_df[rev_df['revenue_growth_3y'] < 0]
            high_q_declining = declining[declining['quality_score_0_100'] >= 80]

            pct_declining = self._safe_percentage(len(declining), len(rev_df))
            if pct_declining > 30:
                recommendations.append(
                    f"⚠️  REVENUE: {pct_declining:.1f}% declining - higher than expected.\n"
                    f"   May indicate challenging market conditions."
                )
            else:
                recommendations.append(
                    f"✅ REVENUE: {pct_declining:.1f}% declining - normal range."
                )

            if len(high_q_declining) > 0:
                recommendations.append(
                    f"   🤔 {len(high_q_declining)} high-quality companies with declining revenue.\n"
                    f"      Review for temporary headwinds vs. structural decline."
                )

        # M&A flag analysis
        if 'mna_flag' in self.df.columns:
            mna_df = self.df[self.df['mna_flag'].notna()]
            high_mna = mna_df[mna_df['mna_flag'] == 'HIGH']
            high_q_mna = high_mna[high_mna['quality_score_0_100'] >= 70]

            pct_high_mna = self._safe_percentage(len(high_mna), len(mna_df))
            if pct_high_mna > 15:
                recommendations.append(
                    f"⚠️  M&A FLAG: {pct_high_mna:.1f}% flagged as HIGH M&A.\n"
                    f"   Consider if threshold is too strict (currently triggers on goodwill growth)."
                )
            else:
                recommendations.append(
                    f"✅ M&A FLAG: {pct_high_mna:.1f}% flagged as HIGH - reasonable rate."
                )

            if len(high_q_mna) > 5:
                recommendations.append(
                    f"   💼 {len(high_q_mna)} high-quality serial acquirers (may be legitimate strategy)."
                )

        # Overall recommendations
        lines.append("\n" + "\n".join(recommendations))

        lines.append("\n" + "-" * 80)
        lines.append("NEXT STEPS:")
        lines.append("-" * 80)
        lines.append("1. Review companies in 'HIGH QUALITY ROJO' sections for false positives")
        lines.append("2. Investigate industry patterns - are certain sectors systematically flagged?")
        lines.append("3. Consider adjusting thresholds if >10% of high-quality companies blocked")
        lines.append("4. For M&A flag, review if 'serial acquirers' strategy is valid for your criteria")
        lines.append("5. Monitor false positive rate over time (target: <5% of high-quality companies)")

        return "\n".join(lines)

    def analyze_high_quality_rojo_deep_dive(self) -> str:
        """
        Deep analysis of high-quality companies flagged as ROJO.

        For each company, provides:
        - Detailed business metrics
        - Specific guardrail components causing flags
        - Assessment of whether flag is legitimate or false positive
        - Actionable recommendations
        """
        lines = []
        lines.append("=" * 80)
        lines.append("HIGH-QUALITY ROJO COMPANIES - DEEP DIVE ANALYSIS")
        lines.append("=" * 80)
        lines.append("")
        lines.append("🎯 OBJECTIVE: Determine if flags are LEGITIMATE or FALSE POSITIVES")
        lines.append("")

        # Filter high-quality ROJO
        high_q_rojo = self.df[
            (self.df['quality_score_0_100'] >= 80) &
            (self.df['guardrail_status'] == 'ROJO')
        ].copy()
        high_q_rojo = high_q_rojo.sort_values('quality_score_0_100', ascending=False)

        lines.append(f"Found {len(high_q_rojo)} high-quality ROJO companies (Quality ≥80)")
        lines.append("")

        if len(high_q_rojo) == 0:
            lines.append("✅ No high-quality companies are blocked - calibration looks good!")
            return "\n".join(lines)

        lines.append("-" * 80)
        lines.append("COMPANY-BY-COMPANY ANALYSIS")
        lines.append("-" * 80)

        for idx, row in high_q_rojo.iterrows():
            symbol = row['symbol']
            name = row.get('name', 'N/A')
            industry = row.get('industry', 'N/A')
            quality = row.get('quality_score_0_100', 0)
            composite = row.get('composite_0_100', 0)

            lines.append("")
            lines.append("=" * 80)
            lines.append(f"{symbol} - {name}")
            lines.append("=" * 80)

            # Overview
            lines.append("")
            lines.append("📊 OVERVIEW:")
            lines.append(f"  Industry: {industry}")
            lines.append(f"  Quality Score: {quality:.1f}")
            lines.append(f"  Composite Score: {composite:.1f}")
            market_cap = row.get('marketCap', 0)
            if market_cap:
                lines.append(f"  Market Cap: ${market_cap/1e9:.1f}B")

            # Guardrail flags
            lines.append("")
            lines.append("🚨 GUARDRAIL FLAGS:")
            lines.append(f"  Status: {row.get('guardrail_status', 'N/A')}")
            reasons = str(row.get('guardrail_reasons', 'N/A')).split(';')
            for i, reason in enumerate(reasons, 1):
                lines.append(f"    {i}. {reason.strip()}")

            # Quality metrics
            lines.append("")
            lines.append("📈 BUSINESS QUALITY METRICS:")
            roic = row.get('roic', 0) or 0
            roe = row.get('roe', 0) or 0
            roa = row.get('roa', 0) or 0
            gross_margin = row.get('grossMargin', 0) or 0
            op_margin = row.get('opMargin', 0) or 0
            net_margin = row.get('netMargin', 0) or 0

            lines.append(f"  ROIC: {roic:.1f}%")
            lines.append(f"  ROE:  {roe:.1f}%")
            lines.append(f"  ROA:  {roa:.1f}%")
            lines.append(f"  Gross Margin: {gross_margin:.1f}%")
            lines.append(f"  Operating Margin: {op_margin:.1f}%")
            lines.append(f"  Net Margin: {net_margin:.1f}%")

            # Growth metrics
            lines.append("")
            lines.append("📊 GROWTH METRICS:")
            rev_growth = row.get('revenueGrowth', 0) or 0
            rev_growth_3y = row.get('revenue_growth_3y', 0) or 0
            eps_growth = row.get('epsGrowth', 0) or 0

            lines.append(f"  Revenue Growth: {rev_growth:.1f}%")
            lines.append(f"  Revenue Growth 3Y: {rev_growth_3y:.1f}%")
            lines.append(f"  EPS Growth: {eps_growth:.1f}%")

            # Moat metrics
            lines.append("")
            lines.append("🏰 MOAT METRICS:")
            moat = row.get('moat_score', 0) or 0
            pricing_power = row.get('pricing_power_score', 0) or 0
            roic_persistence = row.get('roic_persistence_score', 0) or 0

            lines.append(f"  Moat Score: {moat:.1f}")
            lines.append(f"  Pricing Power: {pricing_power:.1f}")
            lines.append(f"  ROIC Persistence: {roic_persistence:.1f}")

            # Guardrail details
            lines.append("")
            lines.append("⚠️  GUARDRAIL DETAILS:")
            m_score = row.get('beneishM', None)
            z_score = row.get('altmanZ', None)
            accruals = row.get('accruals_noa_%', None)
            dilution = row.get('netShareIssuance_12m_%', None)
            mna = row.get('mna_flag', None)

            if m_score is not None and pd.notna(m_score):
                lines.append(f"  Beneish M-Score: {m_score:.2f}")
            if z_score is not None and pd.notna(z_score):
                lines.append(f"  Altman Z-Score: {z_score:.2f}")
            if accruals is not None and pd.notna(accruals):
                lines.append(f"  Accruals/NOA: {accruals:.1f}%")
            if dilution is not None and pd.notna(dilution):
                lines.append(f"  Share Dilution: {dilution:.1f}%")
            if mna:
                lines.append(f"  M&A Flag: {mna}")

            # Quality degradation
            lines.append("")
            lines.append("📉 QUALITY TREND:")
            piot = row.get('piotroski_fscore', None)
            piot_delta = row.get('piotroski_fscore_delta', None)
            mohan = row.get('mohanram_gscore', None)
            mohan_delta = row.get('mohanram_gscore_delta', None)
            deg_delta = row.get('quality_degradation_delta', None)

            if piot is not None and pd.notna(piot) and pd.notna(piot_delta):
                lines.append(f"  Piotroski F-Score: {piot:.0f} (Δ {piot_delta:+.0f})")
            if mohan is not None and pd.notna(mohan) and pd.notna(mohan_delta):
                lines.append(f"  Mohanram G-Score: {mohan:.0f} (Δ {mohan_delta:+.0f})")
            if deg_delta is not None and pd.notna(deg_delta):
                if deg_delta < -1:
                    lines.append(f"  Quality Trend: DETERIORATING (Δ {deg_delta:+.0f})")
                elif deg_delta > 1:
                    lines.append(f"  Quality Trend: IMPROVING (Δ {deg_delta:+.0f})")
                else:
                    lines.append(f"  Quality Trend: STABLE (Δ {deg_delta:+.0f})")

            # Analysis and recommendation
            lines.append("")
            lines.append("💡 DETAILED ANALYSIS:")

            # Analyze each guardrail
            has_issues = []
            is_false_positive = []

            # Beneish analysis
            if m_score is not None and pd.notna(m_score):
                if m_score > -1.5:
                    severity = "CRITICAL"
                    has_issues.append(f"Beneish M={m_score:.2f} (CRITICAL)")
                    lines.append(f"  • Beneish M={m_score:.2f} ({severity} manipulation risk)")
                    lines.append(f"    → Flag appears LEGITIMATE - high accounting manipulation risk")
                elif m_score > -1.78:
                    severity = "HIGH"
                    has_issues.append(f"Beneish M={m_score:.2f} (HIGH)")
                    lines.append(f"  • Beneish M={m_score:.2f} ({severity} risk)")

                    # Check if should be permissive
                    industry_lower = industry.lower()
                    if any(kw in industry_lower for kw in ['communication equipment', 'fintech', 'specialty']):
                        is_false_positive.append(f"Beneish borderline for {industry}")
                        lines.append(f"    → Flag may be FALSE POSITIVE - industry ({industry}) often has high M-Scores")
                    else:
                        lines.append(f"    → Flag appears LEGITIMATE - needs further investigation")
                elif m_score > -2.22:
                    severity = "BORDERLINE"
                    lines.append(f"  • Beneish M={m_score:.2f} ({severity})")
                    is_false_positive.append(f"Beneish borderline M={m_score:.2f}")
                    lines.append(f"    → Flag is FALSE POSITIVE - borderline range, likely normal variation")

            # Altman Z analysis
            if z_score is not None and pd.notna(z_score):
                if z_score < 1.8:
                    lines.append(f"  • Altman Z={z_score:.2f} (DISTRESS zone)")

                    # Check if should be exempt
                    industry_lower = industry.lower()
                    exempt_keywords = ['software', 'saas', 'internet', 'utility', 'restaurant',
                                      'oil & gas midstream', 'personal', 'consumer electronics',
                                      'communication equipment', 'electronic gaming']

                    if any(kw in industry_lower for kw in exempt_keywords):
                        is_false_positive.append(f"Altman Z not applicable to {industry}")
                        lines.append(f"    → Flag is FALSE POSITIVE - {industry} should be exempt (asset-light/regulated)")
                    else:
                        has_issues.append(f"Altman Z={z_score:.2f} (distress)")
                        lines.append(f"    → Flag may be LEGITIMATE - check capital structure and business model")
                elif z_score < 3.0:
                    lines.append(f"  • Altman Z={z_score:.2f} (GRAY zone)")
                    lines.append(f"    → Flag is BORDERLINE - may be normal for this industry")

            # Dilution analysis
            if dilution is not None and pd.notna(dilution) and abs(dilution) > 5:
                lines.append(f"  • Share Dilution: {dilution:.1f}%")

                industry_lower = industry.lower()
                growth_keywords = ['biotech', 'pharmaceutical', 'software', 'semiconductor']

                if dilution > 20:
                    has_issues.append(f"Dilution {dilution:.1f}% excessive")
                    lines.append(f"    → Flag appears LEGITIMATE - excessive dilution even for growth company")
                elif dilution > 10:
                    if any(kw in industry_lower for kw in growth_keywords):
                        lines.append(f"    → Flag may be FALSE POSITIVE - growth industry, capital raising expected")
                    else:
                        has_issues.append(f"Dilution {dilution:.1f}% high")
                        lines.append(f"    → Flag appears LEGITIMATE - high dilution for mature company")

            # Overall business quality assessment
            lines.append("")
            lines.append("  • Overall Business Quality:")

            has_excellent_fundamentals = roic > 20 and roe > 15 and op_margin > 15
            has_good_fundamentals = roic > 15 and roe > 12 and op_margin > 10
            has_improving_quality = deg_delta is not None and pd.notna(deg_delta) and deg_delta > 1
            has_deteriorating_quality = deg_delta is not None and pd.notna(deg_delta) and deg_delta < -1

            if has_excellent_fundamentals:
                lines.append(f"    → EXCELLENT fundamentals (ROIC {roic:.0f}%, ROE {roe:.0f}%, Margin {op_margin:.0f}%)")
                if len(is_false_positive) > 0:
                    lines.append(f"    → Strong evidence of FALSE POSITIVES")
            elif has_good_fundamentals:
                lines.append(f"    → GOOD fundamentals (ROIC {roic:.0f}%, ROE {roe:.0f}%, Margin {op_margin:.0f}%)")
                lines.append(f"    → Guardrail flags need case-by-case review")
            else:
                lines.append(f"    → MIXED fundamentals (ROIC {roic:.0f}%, ROE {roe:.0f}%, Margin {op_margin:.0f}%)")
                lines.append(f"    → Guardrail flags may be legitimate warnings")

            if has_deteriorating_quality:
                lines.append(f"    ⚠️  Quality DETERIORATING - guardrails may be early warning signals")
            elif has_improving_quality:
                lines.append(f"    ✅ Quality IMPROVING - some flags may be stale/false positive")

            # Final recommendation
            lines.append("")
            lines.append("🎯 RECOMMENDATION:")

            if has_excellent_fundamentals and len(is_false_positive) >= 2:
                lines.append(f"  ► STRONG FALSE POSITIVE - Consider unblocking")
                lines.append(f"    Reasons:")
                for reason in is_false_positive:
                    lines.append(f"      • {reason}")
                lines.append(f"    Excellent fundamentals suggest flags are technical/industry-specific")
            elif has_excellent_fundamentals and len(is_false_positive) >= 1:
                lines.append(f"  ► LIKELY FALSE POSITIVE - Review for unblocking")
                lines.append(f"    Reasons:")
                for reason in is_false_positive:
                    lines.append(f"      • {reason}")
            elif len(has_issues) >= 2:
                lines.append(f"  ► LEGITIMATE FLAGS - Keep blocked")
                lines.append(f"    Concerns:")
                for issue in has_issues:
                    lines.append(f"      • {issue}")
            elif has_deteriorating_quality:
                lines.append(f"  ► DETERIORATING - Keep blocked")
                lines.append(f"    Quality trend is negative, flags are warning signals")
            else:
                lines.append(f"  ► NEEDS MANUAL REVIEW")
                lines.append(f"    Mixed signals - check company-specific context")
                lines.append(f"    Research: investor presentations, recent news, SEC filings")

        # Summary
        lines.append("")
        lines.append("=" * 80)
        lines.append("SUMMARY & RECOMMENDATIONS")
        lines.append("=" * 80)
        lines.append("")

        # Count recommendations
        strong_fp = 0
        likely_fp = 0
        legitimate = 0
        needs_review = 0

        for idx, row in high_q_rojo.iterrows():
            m_score = row.get('beneishM', None)
            z_score = row.get('altmanZ', None)
            roic = row.get('roic', 0) or 0
            roe = row.get('roe', 0) or 0
            op_margin = row.get('opMargin', 0) or 0

            has_excellent = roic > 20 and roe > 15 and op_margin > 15

            fp_count = 0
            if m_score is not None and pd.notna(m_score) and -2.22 < m_score < -1.78:
                fp_count += 1
            if z_score is not None and pd.notna(z_score) and z_score < 1.8:
                industry_lower = row.get('industry', '').lower()
                if any(kw in industry_lower for kw in ['software', 'internet', 'oil & gas midstream', 'consumer electronics']):
                    fp_count += 1

            if has_excellent and fp_count >= 2:
                strong_fp += 1
            elif has_excellent and fp_count >= 1:
                likely_fp += 1
            elif m_score is not None and m_score > -1.5:
                legitimate += 1
            else:
                needs_review += 1

        lines.append(f"Distribution of Recommendations:")
        lines.append(f"  STRONG FALSE POSITIVE:  {strong_fp} companies")
        lines.append(f"  LIKELY FALSE POSITIVE:  {likely_fp} companies")
        lines.append(f"  LEGITIMATE FLAGS:       {legitimate} companies")
        lines.append(f"  NEEDS MANUAL REVIEW:    {needs_review} companies")
        lines.append("")

        total_fp = strong_fp + likely_fp
        if total_fp > 0:
            lines.append(f"⚠️  {total_fp} companies ({self._safe_percentage(total_fp, len(high_q_rojo)):.0f}%) appear to be false positives")
            lines.append(f"   Consider:")
            lines.append(f"   1. Expanding Altman Z exemptions for asset-light industries")
            lines.append(f"   2. Adjusting Beneish thresholds for industries with naturally high M-Scores")
            lines.append(f"   3. Adding industry-specific context to guardrail evaluation")

        if legitimate > 0:
            lines.append(f"✅ {legitimate} companies have legitimate accounting concerns - correctly blocked")

        lines.append("")
        lines.append("Next Steps:")
        lines.append("1. Review companies marked as 'STRONG FALSE POSITIVE' first")
        lines.append("2. Research 'NEEDS MANUAL REVIEW' companies individually")
        lines.append("3. For confirmed false positives, adjust thresholds or add exemptions")
        lines.append("4. For legitimate flags, consider if risk tolerance should change")

        return "\n".join(lines)


def main():
    """Run guardrail analysis from command line."""
    parser = argparse.ArgumentParser(description='Analyze guardrail calibration')
    parser.add_argument('--results', type=str, required=True, help='Path to screener results CSV')
    parser.add_argument('--output', type=str, help='Output file for report (default: print to console)')
    parser.add_argument('--guardrail', type=str, choices=['beneish', 'altman', 'revenue', 'mna', 'dilution', 'accruals'],
                       help='Analyze specific guardrail only')

    args = parser.parse_args()

    # Load results
    results_path = Path(args.results)
    if not results_path.exists():
        print(f"❌ Error: Results file not found: {results_path}")
        sys.exit(1)

    print(f"Loading results from: {results_path}")
    df = pd.read_csv(results_path)
    print(f"Loaded {len(df)} companies\n")

    # Run analysis
    analyzer = GuardrailAnalyzer(df)

    if args.guardrail:
        # Specific guardrail analysis
        method_map = {
            'beneish': analyzer._analyze_beneish,
            'altman': analyzer._analyze_altman_z,
            'revenue': analyzer._analyze_revenue_decline,
            'mna': analyzer._analyze_mna_flag,
            'dilution': analyzer._analyze_dilution,
            'accruals': analyzer._analyze_accruals,
        }
        report = method_map[args.guardrail]()
    else:
        # Full report
        report = analyzer.generate_full_report()

    # Output
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report)
        print(f"✅ Report saved to: {output_path}")
    else:
        print(report)


if __name__ == '__main__':
    main()
