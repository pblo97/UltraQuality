"""
Earnings Risk Analyzer Module

Evaluates the risk of adverse price movement around earnings announcements.
Combines technical, fundamental, and options-based metrics.

Risk Score Components:
- Technical Extension (30%): Distance from MA200/MA50
- Valuation Risk (25%): P/E, EV/EBITDA vs historical
- Prior Momentum (20%): Returns 1-3 months before earnings
- Historical Pattern (15%): Average move in last 8 earnings
- IV vs Realized (10%): Options implied vs actual moves
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
import numpy as np


class EarningsRiskLevel(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


@dataclass
class EarningsHistoryItem:
    """Single earnings event with price reaction"""
    date: datetime
    eps_estimate: Optional[float]
    eps_actual: Optional[float]
    surprise_percent: Optional[float]
    price_before: float
    price_after: float
    move_percent: float
    beat: Optional[bool]


@dataclass
class ExtensionRisk:
    """Technical extension risk assessment"""
    distance_ma200: float  # % distance from MA200
    distance_ma50: float   # % distance from MA50
    distance_52w_high: float  # % from 52-week high
    score: float  # 0-100
    level: str  # LOW/MEDIUM/HIGH


@dataclass
class ValuationRisk:
    """Valuation-based risk assessment"""
    pe_current: Optional[float]
    pe_historical: Optional[float]  # 5-year average
    pe_ratio: Optional[float]  # current/historical
    ev_ebitda: Optional[float]
    ps_ratio: Optional[float]  # Price/Sales
    score: float  # 0-100
    level: str


@dataclass
class MomentumRisk:
    """Pre-earnings momentum risk"""
    return_1m: float  # 1-month return
    return_3m: float  # 3-month return
    return_to_earnings: float  # Return since last earnings
    score: float  # 0-100
    level: str


@dataclass
class HistoricalEarningsRisk:
    """Risk based on historical earnings reactions"""
    avg_move: float  # Average absolute move
    avg_positive_move: float
    avg_negative_move: float
    beat_rate: float  # % of beats
    drop_after_beat_rate: float  # % of times dropped even after beat
    consistency: str  # Pattern: VOLATILE, STABLE, UNKNOWN
    score: float  # 0-100
    level: str
    history: List[EarningsHistoryItem]


@dataclass
class OptionsRisk:
    """Options-implied risk assessment"""
    implied_move: float  # Expected move from options
    iv_30d: Optional[float]  # 30-day implied volatility
    iv_percentile: Optional[float]  # IV percentile (0-100)
    historical_vs_implied: Optional[float]  # Ratio of actual vs implied moves
    score: float  # 0-100
    level: str


@dataclass
class EarningsExpectations:
    """Market expectations for upcoming earnings"""
    eps_estimate: Optional[float]
    eps_estimate_low: Optional[float]
    eps_estimate_high: Optional[float]
    revenue_estimate: Optional[float]
    num_analysts: int
    whisper_number: Optional[float]  # Unofficial expectation
    revision_trend: str  # UP, DOWN, STABLE
    revision_percent: Optional[float]  # % change in estimates last 30 days


@dataclass
class EarningsRiskAssessment:
    """Complete earnings risk assessment"""
    ticker: str
    earnings_date: Optional[datetime]
    days_until_earnings: Optional[int]
    timing: str  # BMO (Before Market Open), AMC (After Market Close)

    # Component risks
    extension_risk: ExtensionRisk
    valuation_risk: ValuationRisk
    momentum_risk: MomentumRisk
    historical_risk: HistoricalEarningsRisk
    options_risk: OptionsRisk

    # Expectations
    expectations: Optional[EarningsExpectations]

    # Final score
    total_score: float  # 0-100
    risk_level: EarningsRiskLevel

    # Recommendations
    warnings: List[str]
    position_adjustment: float  # Multiplier for position size (0.5-1.0)
    recommendation: str


class EarningsRiskAnalyzer:
    """
    Analyzes earnings-related risk for a stock.

    Weights:
    - Extension: 30%
    - Valuation: 25%
    - Momentum: 20%
    - Historical: 15%
    - Options/IV: 10%
    """

    WEIGHTS = {
        'extension': 0.30,
        'valuation': 0.25,
        'momentum': 0.20,
        'historical': 0.15,
        'options': 0.10
    }

    def __init__(self):
        pass

    def analyze(
        self,
        ticker: str,
        price_data: Dict[str, Any],
        fundamental_data: Dict[str, Any],
        earnings_data: Dict[str, Any],
        options_data: Optional[Dict[str, Any]] = None
    ) -> EarningsRiskAssessment:
        """
        Perform complete earnings risk analysis.

        Args:
            ticker: Stock symbol
            price_data: Dict with current_price, ma50, ma200, high_52w, returns
            fundamental_data: Dict with P/E, EV/EBITDA, etc.
            earnings_data: Dict with earnings_date, history, estimates
            options_data: Optional dict with IV, expected move
        """
        # Get earnings date info
        earnings_date = earnings_data.get('next_earnings_date')
        days_until = self._calculate_days_until(earnings_date)
        timing = earnings_data.get('timing', 'UNKNOWN')

        # Calculate component risks
        extension_risk = self._calculate_extension_risk(price_data)
        valuation_risk = self._calculate_valuation_risk(fundamental_data)
        momentum_risk = self._calculate_momentum_risk(price_data)
        historical_risk = self._calculate_historical_risk(earnings_data)
        options_risk = self._calculate_options_risk(options_data, price_data, historical_risk)

        # Get expectations
        expectations = self._parse_expectations(earnings_data)

        # Calculate total score
        total_score = (
            extension_risk.score * self.WEIGHTS['extension'] +
            valuation_risk.score * self.WEIGHTS['valuation'] +
            momentum_risk.score * self.WEIGHTS['momentum'] +
            historical_risk.score * self.WEIGHTS['historical'] +
            options_risk.score * self.WEIGHTS['options']
        )

        # Determine risk level
        risk_level = self._score_to_level(total_score)

        # Generate warnings and recommendations
        warnings = self._generate_warnings(
            extension_risk, valuation_risk, momentum_risk,
            historical_risk, options_risk, days_until
        )

        position_adjustment = self._calculate_position_adjustment(total_score, days_until)
        recommendation = self._generate_recommendation(
            total_score, risk_level, days_until, historical_risk
        )

        return EarningsRiskAssessment(
            ticker=ticker,
            earnings_date=earnings_date,
            days_until_earnings=days_until,
            timing=timing,
            extension_risk=extension_risk,
            valuation_risk=valuation_risk,
            momentum_risk=momentum_risk,
            historical_risk=historical_risk,
            options_risk=options_risk,
            expectations=expectations,
            total_score=total_score,
            risk_level=risk_level,
            warnings=warnings,
            position_adjustment=position_adjustment,
            recommendation=recommendation
        )

    def _calculate_days_until(self, earnings_date: Optional[datetime]) -> Optional[int]:
        """Calculate days until earnings"""
        if not earnings_date:
            return None
        if isinstance(earnings_date, str):
            try:
                earnings_date = datetime.strptime(earnings_date, '%Y-%m-%d')
            except:
                return None
        delta = earnings_date - datetime.now()
        return max(0, delta.days)

    def _calculate_extension_risk(self, price_data: Dict) -> ExtensionRisk:
        """
        Calculate risk from technical extension.

        Thresholds:
        - >40% above MA200: Extreme risk
        - >25% above MA200: High risk
        - >15% above MA200: Medium risk
        - <15% above MA200: Low risk
        """
        current_price = price_data.get('current_price', 0)
        ma200 = price_data.get('ma200', current_price)
        ma50 = price_data.get('ma50', current_price)
        high_52w = price_data.get('high_52w', current_price)

        # Calculate distances
        dist_ma200 = ((current_price - ma200) / ma200 * 100) if ma200 > 0 else 0
        dist_ma50 = ((current_price - ma50) / ma50 * 100) if ma50 > 0 else 0
        dist_high = ((high_52w - current_price) / high_52w * 100) if high_52w > 0 else 0

        # Score based on MA200 distance (primary) and MA50 (secondary)
        if dist_ma200 >= 40:
            score = 90 + min(10, (dist_ma200 - 40) / 2)  # 90-100
        elif dist_ma200 >= 25:
            score = 70 + (dist_ma200 - 25) / 15 * 20  # 70-90
        elif dist_ma200 >= 15:
            score = 40 + (dist_ma200 - 15) / 10 * 30  # 40-70
        elif dist_ma200 >= 5:
            score = 20 + (dist_ma200 - 5) / 10 * 20  # 20-40
        else:
            score = max(0, dist_ma200 / 5 * 20)  # 0-20

        # Adjust for proximity to 52w high (adds risk)
        if dist_high < 5:  # Within 5% of 52w high
            score = min(100, score + 10)

        level = self._score_to_level_str(score)

        return ExtensionRisk(
            distance_ma200=round(dist_ma200, 2),
            distance_ma50=round(dist_ma50, 2),
            distance_52w_high=round(dist_high, 2),
            score=round(score, 1),
            level=level
        )

    def _calculate_valuation_risk(self, fundamental_data: Dict) -> ValuationRisk:
        """
        Calculate risk from expensive valuation.

        Uses P/E ratio vs historical average as primary metric.
        """
        pe_current = fundamental_data.get('pe_ratio')
        pe_historical = fundamental_data.get('pe_5y_avg', fundamental_data.get('sector_pe'))
        ev_ebitda = fundamental_data.get('ev_ebitda')
        ps_ratio = fundamental_data.get('price_to_sales')

        score = 50  # Default medium score
        pe_ratio = None

        if pe_current and pe_historical and pe_historical > 0:
            pe_ratio = pe_current / pe_historical

            if pe_ratio >= 2.0:
                score = 90 + min(10, (pe_ratio - 2.0) * 10)
            elif pe_ratio >= 1.5:
                score = 70 + (pe_ratio - 1.5) / 0.5 * 20
            elif pe_ratio >= 1.2:
                score = 50 + (pe_ratio - 1.2) / 0.3 * 20
            elif pe_ratio >= 1.0:
                score = 30 + (pe_ratio - 1.0) / 0.2 * 20
            elif pe_ratio >= 0.8:
                score = 20 + (pe_ratio - 0.8) / 0.2 * 10
            else:
                score = pe_ratio / 0.8 * 20
        elif pe_current:
            # No historical, use absolute thresholds
            if pe_current > 50:
                score = 80
            elif pe_current > 30:
                score = 60
            elif pe_current > 20:
                score = 40
            else:
                score = 20

        # Adjust for EV/EBITDA if available
        if ev_ebitda:
            if ev_ebitda > 30:
                score = min(100, score + 10)
            elif ev_ebitda > 20:
                score = min(100, score + 5)

        level = self._score_to_level_str(score)

        return ValuationRisk(
            pe_current=pe_current,
            pe_historical=pe_historical,
            pe_ratio=round(pe_ratio, 2) if pe_ratio else None,
            ev_ebitda=ev_ebitda,
            ps_ratio=ps_ratio,
            score=round(score, 1),
            level=level
        )

    def _calculate_momentum_risk(self, price_data: Dict) -> MomentumRisk:
        """
        Calculate risk from pre-earnings momentum.

        High momentum before earnings = high expectations = risk of disappointment.
        """
        return_1m = price_data.get('return_1m', 0)
        return_3m = price_data.get('return_3m', 0)
        return_since_earnings = price_data.get('return_since_last_earnings', return_3m)

        # Primary: 3-month return
        if return_3m >= 40:
            score = 90 + min(10, (return_3m - 40) / 10)
        elif return_3m >= 30:
            score = 75 + (return_3m - 30) / 10 * 15
        elif return_3m >= 20:
            score = 55 + (return_3m - 20) / 10 * 20
        elif return_3m >= 10:
            score = 35 + (return_3m - 10) / 10 * 20
        elif return_3m >= 0:
            score = 20 + return_3m / 10 * 15
        else:
            # Negative returns = lower expectations = lower risk
            score = max(0, 20 + return_3m)  # -20% return = 0 score

        # Adjust for 1-month acceleration
        if return_1m > 15:
            score = min(100, score + 10)
        elif return_1m > 10:
            score = min(100, score + 5)

        level = self._score_to_level_str(score)

        return MomentumRisk(
            return_1m=round(return_1m, 2),
            return_3m=round(return_3m, 2),
            return_to_earnings=round(return_since_earnings, 2),
            score=round(score, 1),
            level=level
        )

    def _calculate_historical_risk(self, earnings_data: Dict) -> HistoricalEarningsRisk:
        """
        Calculate risk based on historical earnings reactions.

        Analyzes last 8 earnings events for patterns.
        """
        history_raw = earnings_data.get('earnings_history', [])

        # Parse history into structured format
        history = []
        moves = []
        beats = []
        drops_after_beat = 0

        for item in history_raw[:8]:  # Last 8 quarters
            try:
                move = item.get('price_move', item.get('move_percent', 0))
                beat = item.get('beat')

                history.append(EarningsHistoryItem(
                    date=item.get('date', datetime.now()),
                    eps_estimate=item.get('eps_estimate'),
                    eps_actual=item.get('eps_actual'),
                    surprise_percent=item.get('surprise_percent'),
                    price_before=item.get('price_before', 0),
                    price_after=item.get('price_after', 0),
                    move_percent=move,
                    beat=beat
                ))

                moves.append(abs(move))
                if beat is not None:
                    beats.append(beat)
                    if beat and move < 0:
                        drops_after_beat += 1
            except:
                continue

        if not moves:
            # No history available
            return HistoricalEarningsRisk(
                avg_move=0,
                avg_positive_move=0,
                avg_negative_move=0,
                beat_rate=0,
                drop_after_beat_rate=0,
                consistency='UNKNOWN',
                score=50,  # Neutral
                level='MEDIUM',
                history=[]
            )

        avg_move = np.mean(moves)
        positive_moves = [m for m, h in zip(moves, history) if h.move_percent > 0]
        negative_moves = [m for m, h in zip(moves, history) if h.move_percent < 0]

        avg_positive = np.mean(positive_moves) if positive_moves else 0
        avg_negative = np.mean(negative_moves) if negative_moves else 0

        beat_rate = sum(beats) / len(beats) * 100 if beats else 0
        drop_after_beat_rate = drops_after_beat / sum(beats) * 100 if sum(beats) > 0 else 0

        # Determine consistency
        move_std = np.std(moves)
        if move_std > 8:
            consistency = 'VOLATILE'
        elif move_std < 3:
            consistency = 'STABLE'
        else:
            consistency = 'MODERATE'

        # Score based on average move magnitude and volatility
        if avg_move >= 10:
            score = 80 + min(20, (avg_move - 10) / 5 * 10)
        elif avg_move >= 7:
            score = 60 + (avg_move - 7) / 3 * 20
        elif avg_move >= 5:
            score = 40 + (avg_move - 5) / 2 * 20
        elif avg_move >= 3:
            score = 25 + (avg_move - 3) / 2 * 15
        else:
            score = avg_move / 3 * 25

        # Adjust for drop-after-beat pattern (dangerous)
        if drop_after_beat_rate > 50:
            score = min(100, score + 15)
        elif drop_after_beat_rate > 30:
            score = min(100, score + 10)

        level = self._score_to_level_str(score)

        return HistoricalEarningsRisk(
            avg_move=round(avg_move, 2),
            avg_positive_move=round(avg_positive, 2),
            avg_negative_move=round(avg_negative, 2),
            beat_rate=round(beat_rate, 1),
            drop_after_beat_rate=round(drop_after_beat_rate, 1),
            consistency=consistency,
            score=round(score, 1),
            level=level,
            history=history
        )

    def _calculate_options_risk(
        self,
        options_data: Optional[Dict],
        price_data: Dict,
        historical_risk: HistoricalEarningsRisk
    ) -> OptionsRisk:
        """
        Calculate risk from options-implied expectations.

        Expected Move ≈ price × IV × sqrt(days/365)
        """
        if not options_data:
            # Estimate from historical if no options data
            implied_move = historical_risk.avg_move if historical_risk.avg_move > 0 else 5.0
            return OptionsRisk(
                implied_move=implied_move,
                iv_30d=None,
                iv_percentile=None,
                historical_vs_implied=None,
                score=50,  # Neutral without data
                level='MEDIUM'
            )

        iv_30d = options_data.get('iv_30d')
        iv_percentile = options_data.get('iv_percentile')
        expected_move = options_data.get('expected_move')

        # Calculate expected move if not provided
        if not expected_move and iv_30d:
            current_price = price_data.get('current_price', 100)
            days_to_earnings = 7  # Assume 1 week
            expected_move = current_price * (iv_30d / 100) * np.sqrt(days_to_earnings / 365)
            expected_move = (expected_move / current_price) * 100  # As percentage

        implied_move = expected_move if expected_move else 5.0

        # Compare historical actual moves vs implied
        hist_vs_implied = None
        if historical_risk.avg_move > 0 and implied_move > 0:
            hist_vs_implied = historical_risk.avg_move / implied_move

        # Score based on IV percentile (high IV = high expectations)
        if iv_percentile:
            if iv_percentile >= 80:
                score = 75 + (iv_percentile - 80) / 20 * 25
            elif iv_percentile >= 60:
                score = 50 + (iv_percentile - 60) / 20 * 25
            elif iv_percentile >= 40:
                score = 30 + (iv_percentile - 40) / 20 * 20
            else:
                score = iv_percentile / 40 * 30
        else:
            score = 50  # Neutral

        # Adjust if stock typically moves more than implied (opportunity vs risk)
        if hist_vs_implied and hist_vs_implied > 1.3:
            # Stock moves more than expected - could be opportunity or risk
            score = min(100, score + 10)

        level = self._score_to_level_str(score)

        return OptionsRisk(
            implied_move=round(implied_move, 2),
            iv_30d=round(iv_30d, 1) if iv_30d else None,
            iv_percentile=round(iv_percentile, 1) if iv_percentile else None,
            historical_vs_implied=round(hist_vs_implied, 2) if hist_vs_implied else None,
            score=round(score, 1),
            level=level
        )

    def _parse_expectations(self, earnings_data: Dict) -> Optional[EarningsExpectations]:
        """Parse earnings expectations from data"""
        estimates = earnings_data.get('estimates', {})
        if not estimates:
            return None

        return EarningsExpectations(
            eps_estimate=estimates.get('eps_estimate'),
            eps_estimate_low=estimates.get('eps_low'),
            eps_estimate_high=estimates.get('eps_high'),
            revenue_estimate=estimates.get('revenue_estimate'),
            num_analysts=estimates.get('num_analysts', 0),
            whisper_number=estimates.get('whisper'),
            revision_trend=estimates.get('revision_trend', 'STABLE'),
            revision_percent=estimates.get('revision_30d_change')
        )

    def _score_to_level(self, score: float) -> EarningsRiskLevel:
        """Convert score to risk level enum"""
        if score >= 70:
            return EarningsRiskLevel.HIGH
        elif score >= 50:
            return EarningsRiskLevel.MEDIUM
        elif score >= 30:
            return EarningsRiskLevel.LOW
        else:
            return EarningsRiskLevel.LOW

    def _score_to_level_str(self, score: float) -> str:
        """Convert score to risk level string"""
        if score >= 70:
            return 'HIGH'
        elif score >= 40:
            return 'MEDIUM'
        else:
            return 'LOW'

    def _generate_warnings(
        self,
        extension: ExtensionRisk,
        valuation: ValuationRisk,
        momentum: MomentumRisk,
        historical: HistoricalEarningsRisk,
        options: OptionsRisk,
        days_until: Optional[int]
    ) -> List[str]:
        """Generate specific warnings based on risk factors"""
        warnings = []

        # Extension warnings
        if extension.distance_ma200 >= 40:
            warnings.append(f"EXTREME extension: +{extension.distance_ma200:.1f}% above MA200")
        elif extension.distance_ma200 >= 25:
            warnings.append(f"High extension: +{extension.distance_ma200:.1f}% above MA200")

        if extension.distance_52w_high < 3:
            warnings.append("Trading near 52-week high - elevated expectations")

        # Valuation warnings
        if valuation.pe_ratio and valuation.pe_ratio >= 1.5:
            warnings.append(f"Valuation {valuation.pe_ratio:.1f}x historical P/E - requires perfect results")

        # Momentum warnings
        if momentum.return_3m >= 30:
            warnings.append(f"Strong pre-earnings rally (+{momentum.return_3m:.1f}% in 3mo) - profit-taking risk")
        elif momentum.return_1m >= 15:
            warnings.append(f"Recent acceleration (+{momentum.return_1m:.1f}% in 1mo) - high expectations priced in")

        # Historical warnings
        if historical.drop_after_beat_rate >= 40:
            warnings.append(f"History: Drops {historical.drop_after_beat_rate:.0f}% of time even after beating estimates")

        if historical.consistency == 'VOLATILE' and historical.avg_move >= 7:
            warnings.append(f"Highly volatile on earnings: avg ±{historical.avg_move:.1f}% move")

        # Options/IV warnings
        if options.iv_percentile and options.iv_percentile >= 80:
            warnings.append(f"IV at {options.iv_percentile:.0f}th percentile - market expects big move")

        # Time proximity
        if days_until is not None:
            if days_until <= 3:
                warnings.append("IMMINENT: Earnings within 3 days - consider reducing/hedging")
            elif days_until <= 7:
                warnings.append("Earnings within 1 week - elevated risk period")

        return warnings

    def _calculate_position_adjustment(self, score: float, days_until: Optional[int]) -> float:
        """
        Calculate position size adjustment multiplier.

        Returns 0.5-1.0 based on risk score and proximity.
        """
        # Base adjustment from score
        if score >= 80:
            base = 0.5
        elif score >= 60:
            base = 0.65
        elif score >= 40:
            base = 0.8
        else:
            base = 1.0

        # Further reduction if earnings imminent
        if days_until is not None:
            if days_until <= 3:
                base *= 0.7
            elif days_until <= 7:
                base *= 0.85

        return round(max(0.5, min(1.0, base)), 2)

    def _generate_recommendation(
        self,
        score: float,
        level: EarningsRiskLevel,
        days_until: Optional[int],
        historical: HistoricalEarningsRisk
    ) -> str:
        """Generate actionable recommendation"""

        if days_until is None:
            return "No upcoming earnings date found. Monitor for announcements."

        if days_until > 30:
            return "Earnings >30 days away. Normal position sizing appropriate."

        if score >= 70:
            if days_until <= 7:
                return "HIGH RISK: Consider closing or significantly reducing position before earnings."
            else:
                return "HIGH RISK: Plan to reduce position size as earnings approach."

        elif score >= 50:
            if days_until <= 7:
                return "MODERATE RISK: Consider reducing position 20-35% or using protective puts."
            else:
                return "MODERATE RISK: Monitor closely, prepare hedging strategy."

        elif score >= 30:
            if historical.avg_move >= 5:
                return f"LOW-MEDIUM RISK: Expect ±{historical.avg_move:.1f}% move. Size accordingly."
            else:
                return "LOW RISK: Standard position sizing acceptable."

        else:
            return "LOW RISK: Favorable risk profile for earnings hold."


def get_earnings_risk_summary(assessment: EarningsRiskAssessment) -> Dict[str, Any]:
    """Convert assessment to dictionary for UI display"""
    return {
        'ticker': assessment.ticker,
        'earnings_date': assessment.earnings_date.strftime('%Y-%m-%d') if assessment.earnings_date else None,
        'days_until': assessment.days_until_earnings,
        'timing': assessment.timing,
        'total_score': assessment.total_score,
        'risk_level': assessment.risk_level.value,
        'position_adjustment': assessment.position_adjustment,
        'recommendation': assessment.recommendation,
        'warnings': assessment.warnings,
        'components': {
            'extension': {
                'score': assessment.extension_risk.score,
                'level': assessment.extension_risk.level,
                'ma200_distance': assessment.extension_risk.distance_ma200,
                'ma50_distance': assessment.extension_risk.distance_ma50,
            },
            'valuation': {
                'score': assessment.valuation_risk.score,
                'level': assessment.valuation_risk.level,
                'pe_ratio': assessment.valuation_risk.pe_ratio,
                'pe_current': assessment.valuation_risk.pe_current,
            },
            'momentum': {
                'score': assessment.momentum_risk.score,
                'level': assessment.momentum_risk.level,
                'return_1m': assessment.momentum_risk.return_1m,
                'return_3m': assessment.momentum_risk.return_3m,
            },
            'historical': {
                'score': assessment.historical_risk.score,
                'level': assessment.historical_risk.level,
                'avg_move': assessment.historical_risk.avg_move,
                'beat_rate': assessment.historical_risk.beat_rate,
                'drop_after_beat': assessment.historical_risk.drop_after_beat_rate,
                'consistency': assessment.historical_risk.consistency,
            },
            'options': {
                'score': assessment.options_risk.score,
                'level': assessment.options_risk.level,
                'implied_move': assessment.options_risk.implied_move,
                'iv_percentile': assessment.options_risk.iv_percentile,
            }
        },
        'expectations': {
            'eps_estimate': assessment.expectations.eps_estimate if assessment.expectations else None,
            'revision_trend': assessment.expectations.revision_trend if assessment.expectations else None,
            'num_analysts': assessment.expectations.num_analysts if assessment.expectations else 0,
        } if assessment.expectations else None
    }
