"""
Peer/Sector relative comparison for financial metrics.

Provides context to metrics by comparing against sector peers:
- "DSO = 64 days" → "DSO = 64 days (85th percentile, worse than 85% of peers)"
- "Gross Margin = 45%" → "Gross Margin = 45% (sector avg: 38%, +7pp advantage)"

Uses existing peer data + calculates fresh metrics for comparison set.
"""
import logging
from typing import Dict, List, Optional
import numpy as np

logger = logging.getLogger(__name__)


class PeerComparator:
    """
    Compare company metrics against sector peers.

    Usage:
        comparator = PeerComparator(fmp_client, guardrails_calc)

        # Get peer comparison for a company
        comparison = comparator.compare_to_peers(
            symbol='AAPL',
            guardrails=current_guardrails,
            peers_list=['MSFT', 'GOOGL', 'META', 'AMZN']
        )

        # Returns:
        # {
        #     'dso': {
        #         'value': 64,
        #         'peer_avg': 48,
        #         'peer_median': 45,
        #         'percentile': 85,  # Worse than 85% of peers
        #         'status': 'WORSE'
        #     },
        #     ...
        # }
    """

    def __init__(self, fmp_client, guardrails_calc):
        self.fmp = fmp_client
        self.guardrails_calc = guardrails_calc

    def compare_to_peers(
        self,
        symbol: str,
        guardrails: Dict,
        peers_list: List[str],
        industry: str = ''
    ) -> Dict:
        """
        Compare company's metrics against peer group.

        Args:
            symbol: Company ticker
            guardrails: Company's guardrails output
            peers_list: List of peer tickers
            industry: Industry (for context)

        Returns:
            Dict of comparisons by metric
        """
        if not peers_list or len(peers_list) < 3:
            logger.warning(f"Insufficient peers for comparison ({len(peers_list)})")
            return {}

        # Calculate guardrails for all peers
        peer_guardrails = {}

        for peer in peers_list[:10]:  # Limit to 10 peers for performance
            if peer == symbol:
                continue

            try:
                peer_gr = self.guardrails_calc.calculate_guardrails(
                    peer,
                    'non_financial',  # Simplification
                    industry
                )
                peer_guardrails[peer] = peer_gr
            except Exception as e:
                logger.debug(f"Error calculating guardrails for peer {peer}: {e}")
                continue

        if len(peer_guardrails) < 2:
            logger.warning(f"Insufficient peer data for comparison")
            return {}

        # Extract metrics for comparison
        comparisons = {}

        # Metrics to compare
        metrics_config = {
            # Working Capital
            'dso': {
                'path': ['working_capital', 'dso_current'],
                'lower_is_better': True,
                'label': 'DSO (Days)',
                'format': '.0f'
            },
            'ccc': {
                'path': ['working_capital', 'ccc_current'],
                'lower_is_better': True,
                'label': 'Cash Conversion Cycle (Days)',
                'format': '.0f'
            },
            # Margins
            'gross_margin': {
                'path': ['margin_trajectory', 'gross_margin_current'],
                'lower_is_better': False,
                'label': 'Gross Margin (%)',
                'format': '.1f'
            },
            'operating_margin': {
                'path': ['margin_trajectory', 'operating_margin_current'],
                'lower_is_better': False,
                'label': 'Operating Margin (%)',
                'format': '.1f'
            },
            # Cash Conversion
            'fcf_to_ni': {
                'path': ['cash_conversion', 'fcf_to_ni_current'],
                'lower_is_better': False,
                'label': 'FCF/NI Ratio (%)',
                'format': '.0f'
            },
            # Debt
            'liquidity_ratio': {
                'path': ['debt_maturity_wall', 'liquidity_ratio'],
                'lower_is_better': False,
                'label': 'Liquidity Ratio',
                'format': '.2f'
            },
            # Traditional
            'altman_z': {
                'path': ['altmanZ'],
                'lower_is_better': False,
                'label': 'Altman Z-Score',
                'format': '.2f'
            },
            'beneish_m': {
                'path': ['beneishM'],
                'lower_is_better': True,  # More negative is better
                'label': 'Beneish M-Score',
                'format': '.2f'
            }
        }

        for metric_key, config in metrics_config.items():
            # Get company value
            company_value = self._extract_metric(guardrails, config['path'])
            if company_value is None:
                continue

            # Get peer values
            peer_values = []
            for peer, peer_gr in peer_guardrails.items():
                peer_val = self._extract_metric(peer_gr, config['path'])
                if peer_val is not None:
                    peer_values.append(peer_val)

            if len(peer_values) < 2:
                continue

            # Calculate statistics
            peer_avg = np.mean(peer_values)
            peer_median = np.median(peer_values)
            peer_std = np.std(peer_values)

            # Calculate percentile (where does company rank?)
            percentile = self._calculate_percentile(company_value, peer_values)

            # Determine if better/worse
            if config['lower_is_better']:
                # Lower is better (DSO, CCC, Beneish)
                if company_value < peer_median:
                    status = 'BETTER'
                elif company_value > peer_median * 1.2:
                    status = 'WORSE'
                else:
                    status = 'AVERAGE'

                # Percentile interpretation (for lower-is-better, low percentile is good)
                performance = 'BETTER' if percentile < 50 else 'WORSE'

            else:
                # Higher is better (Margins, Altman Z, Liquidity)
                if company_value > peer_median:
                    status = 'BETTER'
                elif company_value < peer_median * 0.8:
                    status = 'WORSE'
                else:
                    status = 'AVERAGE'

                # Percentile interpretation (for higher-is-better, high percentile is good)
                performance = 'BETTER' if percentile > 50 else 'WORSE'

            # Calculate difference
            diff = company_value - peer_avg
            diff_pct = (diff / peer_avg * 100) if peer_avg != 0 else 0

            comparisons[metric_key] = {
                'value': company_value,
                'label': config['label'],
                'peer_avg': peer_avg,
                'peer_median': peer_median,
                'peer_std': peer_std,
                'peer_count': len(peer_values),
                'percentile': percentile,
                'difference': diff,
                'difference_pct': diff_pct,
                'status': status,
                'performance': performance,
                'format': config['format']
            }

        return comparisons

    def _extract_metric(self, data: Dict, path: List[str]) -> Optional[float]:
        """Extract nested metric from dict by path."""
        current = data
        for key in path:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        return current if isinstance(current, (int, float)) else None

    def _calculate_percentile(self, value: float, peer_values: List[float]) -> float:
        """
        Calculate percentile rank.

        Returns: 0-100, where 100 means better than all peers.
        """
        if not peer_values:
            return 50.0

        # Count how many peers are worse
        worse_count = sum(1 for pv in peer_values if pv < value)
        percentile = (worse_count / len(peer_values)) * 100

        return percentile

    def format_comparison(self, metric_key: str, comparison: Dict) -> str:
        """
        Format comparison result as human-readable string.

        Example outputs:
        - "DSO: 64 days (peer avg: 48, 85th percentile) ⚠️  WORSE"
        - "Gross Margin: 45.2% (peer avg: 38.1%, +7.1pp) ✅ BETTER"
        """
        if not comparison:
            return ""

        value = comparison['value']
        peer_avg = comparison['peer_avg']
        percentile = comparison['percentile']
        status = comparison['status']
        label = comparison['label']
        fmt = comparison['format']

        # Format values
        value_str = f"{value:{fmt}}"
        peer_avg_str = f"{peer_avg:{fmt}}"

        # Status icon
        icon = '✅' if status == 'BETTER' else '⚠️ ' if status == 'WORSE' else 'ℹ️ '

        # Build message
        msg = f"{label}: {value_str} (peer avg: {peer_avg_str}, {percentile:.0f}th percentile) {icon} {status}"

        return msg

    def get_summary_comparison(
        self,
        symbol: str,
        guardrails: Dict,
        peers_list: List[str],
        industry: str = ''
    ) -> Dict:
        """
        Get high-level summary of how company compares to peers.

        Returns:
        {
            'overall_rank': 'Top Quartile' | 'Above Average' | 'Below Average' | 'Bottom Quartile',
            'strengths': List[str],  # Metrics where company is better
            'weaknesses': List[str],  # Metrics where company is worse
            'score': 0-100  # Composite percentile score
        }
        """
        comparisons = self.compare_to_peers(symbol, guardrails, peers_list, industry)

        if not comparisons:
            return {'overall_rank': 'Unknown', 'strengths': [], 'weaknesses': [], 'score': None}

        # Calculate strengths/weaknesses
        strengths = []
        weaknesses = []

        percentiles = []

        for metric_key, comp in comparisons.items():
            percentiles.append(comp['percentile'])

            if comp['status'] == 'BETTER':
                strengths.append(comp['label'])
            elif comp['status'] == 'WORSE':
                weaknesses.append(comp['label'])

        # Overall score (average percentile)
        overall_score = np.mean(percentiles) if percentiles else 50

        # Determine overall rank
        if overall_score >= 75:
            overall_rank = 'Top Quartile'
        elif overall_score >= 50:
            overall_rank = 'Above Average'
        elif overall_score >= 25:
            overall_rank = 'Below Average'
        else:
            overall_rank = 'Bottom Quartile'

        return {
            'overall_rank': overall_rank,
            'strengths': strengths[:3],  # Top 3
            'weaknesses': weaknesses[:3],  # Top 3
            'score': overall_score,
            'peer_count': len(peers_list)
        }
