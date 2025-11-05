"""
Scoring module: normalize metrics by industry and calculate Value/Quality scores.
"""
import logging
import pandas as pd
import numpy as np
from scipy import stats
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


class ScoringEngine:
    """
    - Normalize metrics by industry (z-scores)
    - Calculate Value and Quality scores (0-100)
    - Composite score and decision logic
    """

    def __init__(self, config: Dict):
        self.config = config
        self.w_value = config.get('scoring', {}).get('weight_value', 0.5)
        self.w_quality = config.get('scoring', {}).get('weight_quality', 0.5)
        self.threshold_buy = config.get('scoring', {}).get('threshold_buy', 75)
        self.threshold_monitor = config.get('scoring', {}).get('threshold_monitor', 60)
        self.exclude_reds = config.get('scoring', {}).get('exclude_reds', True)

    def score_universe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Score entire universe DataFrame.

        Input columns expected:
        - ticker, industry, is_financial, is_REIT
        - Value metrics: ev_ebit_ttm, pe_ttm, pb_ttm, shareholder_yield_%, etc.
        - Quality metrics: roic_%, grossProfits_to_assets, etc.
        - guardrail_status

        Output: adds columns value_score_0_100, quality_score_0_100, composite_0_100, decision, notes_short
        """
        logger.info("Starting scoring and normalization...")

        # Group by company type for different metric sets
        df_nonfin = df[df['is_financial'] == False].copy()
        df_fin = df[df['is_financial'] == True].copy()

        # Score each group
        if not df_nonfin.empty:
            df_nonfin = self._score_non_financials(df_nonfin)

        if not df_fin.empty:
            df_fin = self._score_financials(df_fin)

        # Merge back
        df_scored = pd.concat([df_nonfin, df_fin], ignore_index=True)

        # Decision logic
        df_scored = self._apply_decision_logic(df_scored)

        # Generate notes
        df_scored['notes_short'] = df_scored.apply(self._generate_notes, axis=1)

        logger.info(f"Scoring complete: {len(df_scored)} symbols scored")

        return df_scored

    # =====================================
    # NON-FINANCIALS
    # =====================================

    def _score_non_financials(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Score non-financial companies.

        Value signals: ev_ebit_ttm, ev_fcf_ttm, pe_ttm, pb_ttm, shareholder_yield_%
        Quality signals: roic_%, grossProfits_to_assets, fcf_margin_%, cfo_to_ni,
                         netDebt_ebitda (inverted), interestCoverage

        Lower is better for valuation multiples (except shareholder_yield).
        Higher is better for quality metrics (except netDebt_ebitda).
        """
        # Normalize by industry
        value_metrics = ['ev_ebit_ttm', 'ev_fcf_ttm', 'pe_ttm', 'pb_ttm']
        value_higher_better = ['shareholder_yield_%']

        quality_metrics = ['roic_%', 'grossProfits_to_assets', 'fcf_margin_%', 'cfo_to_ni', 'interestCoverage']
        quality_lower_better = ['netDebt_ebitda']

        # Normalize value metrics (lower = better, so invert z-score)
        df = self._normalize_by_industry(df, value_metrics, higher_is_better=False)
        df = self._normalize_by_industry(df, value_higher_better, higher_is_better=True)

        # Normalize quality metrics
        df = self._normalize_by_industry(df, quality_metrics, higher_is_better=True)
        df = self._normalize_by_industry(df, quality_lower_better, higher_is_better=False)

        # Aggregate scores
        all_value_cols = [f"{m}_zscore" for m in value_metrics + value_higher_better]
        all_quality_cols = [f"{m}_zscore" for m in quality_metrics + quality_lower_better]

        df['value_score_0_100'] = df[all_value_cols].mean(axis=1, skipna=True).apply(self._zscore_to_percentile)
        df['quality_score_0_100'] = df[all_quality_cols].mean(axis=1, skipna=True).apply(self._zscore_to_percentile)

        # Composite
        df['composite_0_100'] = (
            self.w_value * df['value_score_0_100'] +
            self.w_quality * df['quality_score_0_100']
        )

        return df

    # =====================================
    # FINANCIALS (Banks, Insurance, etc.)
    # =====================================

    def _score_financials(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Score financial companies.

        Value: pe_ttm, pb_ttm, p_tangibleBook, dividendYield_%
        Quality: roa_%, roe_%, efficiency_ratio (lower=better), nim_%, cet1_or_leverage_ratio_%
        """
        # Check if REIT
        df_reit = df[df['is_REIT'] == True].copy()
        df_fin_only = df[df['is_REIT'] == False].copy()

        if not df_reit.empty:
            df_reit = self._score_reits(df_reit)

        if not df_fin_only.empty:
            # Value metrics
            value_metrics = ['pe_ttm', 'pb_ttm', 'p_tangibleBook']
            value_higher_better = ['dividendYield_%']

            # Quality metrics
            quality_metrics = ['roa_%', 'roe_%', 'nim_%', 'cet1_or_leverage_ratio_%']
            quality_lower_better = ['efficiency_ratio']

            df_fin_only = self._normalize_by_industry(df_fin_only, value_metrics, higher_is_better=False)
            df_fin_only = self._normalize_by_industry(df_fin_only, value_higher_better, higher_is_better=True)
            df_fin_only = self._normalize_by_industry(df_fin_only, quality_metrics, higher_is_better=True)
            df_fin_only = self._normalize_by_industry(df_fin_only, quality_lower_better, higher_is_better=False)

            all_value_cols = [f"{m}_zscore" for m in value_metrics + value_higher_better]
            all_quality_cols = [f"{m}_zscore" for m in quality_metrics + quality_lower_better]

            df_fin_only['value_score_0_100'] = df_fin_only[all_value_cols].mean(axis=1, skipna=True).apply(self._zscore_to_percentile)
            df_fin_only['quality_score_0_100'] = df_fin_only[all_quality_cols].mean(axis=1, skipna=True).apply(self._zscore_to_percentile)

            df_fin_only['composite_0_100'] = (
                self.w_value * df_fin_only['value_score_0_100'] +
                self.w_quality * df_fin_only['quality_score_0_100']
            )

        # Merge REITs and financials back
        return pd.concat([df_fin_only, df_reit], ignore_index=True)

    # =====================================
    # REITs
    # =====================================

    def _score_reits(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Score REITs.

        Value: p_ffo, p_affo, dividendYield_% (higher=better)
        Quality: ffo_payout_% (lower=better), occupancy_%, netDebt_ebitda_re (lower=better)
        """
        value_metrics = ['p_ffo', 'p_affo']
        value_higher_better = ['dividendYield_%']

        quality_metrics = ['occupancy_%']
        quality_lower_better = ['ffo_payout_%', 'netDebt_ebitda_re']

        df = self._normalize_by_industry(df, value_metrics, higher_is_better=False)
        df = self._normalize_by_industry(df, value_higher_better, higher_is_better=True)
        df = self._normalize_by_industry(df, quality_metrics, higher_is_better=True)
        df = self._normalize_by_industry(df, quality_lower_better, higher_is_better=False)

        all_value_cols = [f"{m}_zscore" for m in value_metrics + value_higher_better]
        all_quality_cols = [f"{m}_zscore" for m in quality_metrics + quality_lower_better]

        df['value_score_0_100'] = df[all_value_cols].mean(axis=1, skipna=True).apply(self._zscore_to_percentile)
        df['quality_score_0_100'] = df[all_quality_cols].mean(axis=1, skipna=True).apply(self._zscore_to_percentile)

        df['composite_0_100'] = (
            self.w_value * df['value_score_0_100'] +
            self.w_quality * df['quality_score_0_100']
        )

        return df

    # =====================================
    # NORMALIZATION
    # =====================================

    def _normalize_by_industry(
        self,
        df: pd.DataFrame,
        metrics: List[str],
        higher_is_better: bool
    ) -> pd.DataFrame:
        """
        Normalize metrics by industry using z-scores.

        Args:
            df: DataFrame with 'industry' column
            metrics: List of metric column names
            higher_is_better: If True, higher values are better (positive z-score)
                              If False, lower values are better (invert z-score)

        Returns:
            DataFrame with new columns: {metric}_zscore
        """
        for metric in metrics:
            if metric not in df.columns:
                logger.warning(f"Metric '{metric}' not found in DataFrame")
                continue

            # Group by industry and calculate z-scores
            df[f'{metric}_zscore'] = df.groupby('industry')[metric].transform(
                lambda x: self._robust_zscore(x, higher_is_better)
            )

        return df

    def _robust_zscore(self, series: pd.Series, higher_is_better: bool) -> pd.Series:
        """
        Calculate robust z-score for a series.
        Uses median and MAD (Median Absolute Deviation) to handle outliers.
        """
        # Drop NaNs
        clean = series.dropna()

        if len(clean) < 3:
            # Not enough data for normalization
            return pd.Series(0, index=series.index)

        # Median and MAD
        median = clean.median()
        mad = np.median(np.abs(clean - median))

        if mad == 0:
            # All values are the same
            return pd.Series(0, index=series.index)

        # Z-score = (x - median) / (1.4826 * MAD)
        # Factor 1.4826 makes MAD consistent with std dev for normal distribution
        z_scores = (series - median) / (1.4826 * mad)

        # Invert if lower is better
        if not higher_is_better:
            z_scores = -z_scores

        # Cap extreme z-scores at ±3
        z_scores = z_scores.clip(-3, 3)

        return z_scores

    def _zscore_to_percentile(self, z: float) -> float:
        """
        Convert z-score to percentile (0-100 scale).
        Z-score of 0 = 50th percentile.
        Z-score of +2 = ~97.7th percentile.
        Z-score of -2 = ~2.3rd percentile.
        """
        if pd.isna(z):
            return 50.0  # Neutral if missing

        percentile = stats.norm.cdf(z) * 100
        return percentile

    # =====================================
    # DECISION LOGIC
    # =====================================

    def _apply_decision_logic(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply decision rules:
        - composite >= 75 AND VERDE → BUY
        - 60-75 OR AMBAR → MONITOR
        - < 60 OR ROJO → AVOID
        - If exclude_reds=True, force ROJO → AVOID
        """
        def decide(row):
            composite = row.get('composite_0_100', 0)
            status = row.get('guardrail_status', 'AMBAR')

            if self.exclude_reds and status == 'ROJO':
                return 'AVOID'

            if composite >= self.threshold_buy and status == 'VERDE':
                return 'BUY'
            elif composite >= self.threshold_monitor or status == 'AMBAR':
                return 'MONITOR'
            else:
                return 'AVOID'

        df['decision'] = df.apply(decide, axis=1)

        return df

    # =====================================
    # NOTES GENERATION
    # =====================================

    def _generate_notes(self, row: pd.Series) -> str:
        """
        Generate concise notes (140-200 chars) explaining the score.
        Format: "Reason1; Reason2; Reason3"
        """
        notes = []

        # Value signal
        if row.get('is_financial', False):
            if row.get('pe_ttm'):
                pct = self._percentile_label(row.get('value_score_0_100', 50))
                notes.append(f"P/E {pct}")
        else:
            if row.get('ev_ebit_ttm'):
                pct = self._percentile_label(row.get('value_score_0_100', 50))
                notes.append(f"EV/EBIT {pct}")

        # Quality signal
        if not row.get('is_financial', False):
            roic = row.get('roic_%')
            if roic and roic > 15:
                notes.append(f"ROIC {roic:.1f}%")
            elif roic:
                notes.append(f"ROIC {roic:.1f}% low")
        else:
            roe = row.get('roe_%')
            if roe and roe > 12:
                notes.append(f"ROE {roe:.1f}%")

        # Guardrails
        status = row.get('guardrail_status', 'N/A')
        if status == 'VERDE':
            notes.append("Acct. OK")
        else:
            reasons = row.get('guardrail_reasons', '')
            # Take first reason only
            if reasons:
                first_reason = reasons.split(';')[0][:30]
                notes.append(first_reason)

        # Combine
        note_str = '; '.join(notes[:3])

        # Truncate to 200 chars
        if len(note_str) > 200:
            note_str = note_str[:197] + '...'

        return note_str

    def _percentile_label(self, pct: float) -> str:
        """Convert percentile to label (e.g., p10, p50, p90)."""
        if pct < 20:
            return "p<20"
        elif pct < 40:
            return "p20-40"
        elif pct < 60:
            return "p40-60"
        elif pct < 80:
            return "p60-80"
        else:
            return "p>80"
