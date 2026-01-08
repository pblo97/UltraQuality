"""
Enhanced Technical Analysis V2 - Orthogonal Components (2024)

Complete redesign eliminating redundancies and double-counting.

**NEW ARCHITECTURE: 4 Orthogonal Components**

A) Relative Strength Multi-Timeframe (0-40 pts)
   - RS 12-1 vs SPY: 0-18 pts
   - RS 6-1 vs SPY: 0-12 pts
   - RS 6-1 vs Sector/Industry: 0-10 pts

B) Trend/Structure (0-25 pts)
   - Price > MA200: 0/6 pts
   - MA50 > MA200: 0/6 pts
   - MA200 slope positive: 0/5 pts
   - EMA stack (EMA20 > MA50 > MA200): 0/5 pts
   - Breakout/52W high structure: 0/3 pts

C) Risk Quality (0-20 pts)
   - Sharpe/Sortino 6M: 0-10 pts
   - Max drawdown 6M: 0-6 pts
   - Realized volatility (penalize extremes): 0-4 pts

D) Participation/Volume (0-15 pts)
   - Up-volume vs Down-volume (4-8 weeks): 0-6 pts
   - Distribution days penalty: 0-5 pts
   - Relative volume on breakouts: 0-4 pts

**Formula:** TechScore = RS + Trend + RiskQ + Volume (0-100)

**States (modify action/size, NOT score):**
- Extension State: NORMAL/EXTENDED/STRETCHED/OVEREXTENDED
- Market Regime: BULL/SIDEWAYS/BEAR
- Trend State: UPTREND/DOWNTREND/CHOP

**Position Sizing:**
conviction = clip((TechScore - 60) / 30, 0, 1)
size_adj = conviction × regime_factor × extension_factor
PositionSize = R$/ATR_stop_dist

**Academic Evidence:**
- Jegadeesh & Titman (1993) - Momentum persistence
- Fama & French (2008) - Dissecting anomalies
- Daniel & Moskowitz (2016) - Momentum crashes
- Novy-Marx (2012) - Intermediate-term momentum
- Cooper et al. (2004) - Market states matter
"""

from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta
import logging
import statistics
import numpy as np

logger = logging.getLogger(__name__)


class TechnicalAnalyzerV2:
    """
    Orthogonal technical analysis with no redundancies.

    Eliminates:
    - Double-counting momentum in multiple components
    - Regime as score inflator (now only for sizing)
    - Overlapping sector/market/momentum scores
    """

    # Sector to ETF mapping (unchanged)
    SECTOR_ETFS = {
        'Technology': 'XLK',
        'Healthcare': 'XLV',
        'Financials': 'XLF',
        'Consumer Cyclical': 'XLY',
        'Consumer Defensive': 'XLP',
        'Energy': 'XLE',
        'Industrials': 'XLI',
        'Basic Materials': 'XLB',
        'Real Estate': 'XLRE',
        'Communication Services': 'XLC',
        'Utilities': 'XLU',
        # Aliases
        'Information Technology': 'XLK',
        'Health Care': 'XLV',
        'Financial Services': 'XLF',
        'Consumer Discretionary': 'XLY',
        'Consumer Staples': 'XLP',
        'Materials': 'XLB',
        'Telecommunication Services': 'XLC',
    }

    # Extension State thresholds (% from MA200)
    EXTENSION_THRESHOLDS = {
        'NORMAL': 25,
        'EXTENDED': 40,
        'STRETCHED': 55,
        'OVEREXTENDED': 100,  # > 55%
    }

    # Regime factors for position sizing
    REGIME_FACTORS = {
        'BULL': 1.0,
        'SIDEWAYS': 0.7,
        'BEAR': 0.4,
    }

    # Extension factors for position sizing
    EXTENSION_FACTORS = {
        'NORMAL': 1.0,
        'EXTENDED': 0.7,
        'STRETCHED': 0.4,
        'OVEREXTENDED': 0.2,
    }

    def __init__(self, fmp_client):
        """
        Args:
            fmp_client: FMP client (preferably CachedFMPClient)
        """
        self.fmp = fmp_client
        self._market_regime_cache = None
        self._market_regime_timestamp = None

    # ============================================================================
    # MAIN ANALYSIS METHOD
    # ============================================================================

    def analyze(self, symbol: str, sector: str = None, country: str = 'USA',
                fundamental_score: float = None, guardrails_status: str = None,
                fundamental_decision: str = None, portfolio_value: float = 100000,
                risk_per_trade: float = 0.005) -> Dict:
        """
        Orthogonal technical analysis with state-based position sizing.

        Args:
            symbol: Stock ticker
            sector: Sector name
            country: Country code
            fundamental_score: Fundamental quality score (for context)
            guardrails_status: VERDE/AMBAR/ROJO (for context)
            fundamental_decision: BUY/MONITOR/AVOID (for context)
            portfolio_value: Total portfolio value for sizing
            risk_per_trade: Base risk per trade (default 0.5% = 0.005)

        Returns:
            {
                'score': 0-100 (orthogonal components only),
                'components': {
                    'relative_strength': 0-40,
                    'trend_structure': 0-25,
                    'risk_quality': 0-20,
                    'volume_participation': 0-15
                },
                'states': {
                    'extension': 'NORMAL|EXTENDED|STRETCHED|OVEREXTENDED',
                    'regime': 'BULL|SIDEWAYS|BEAR',
                    'trend': 'UPTREND|DOWNTREND|CHOP'
                },
                'conviction': 0.0-1.0,
                'position_sizing': {
                    'base_risk_usd': float,
                    'conviction_scalar': float,
                    'regime_factor': float,
                    'extension_factor': float,
                    'adjusted_risk_usd': float,
                    'stop_distance_pct': float,
                    'position_size_usd': float,
                    'position_size_shares': int
                },
                'stop_loss': {
                    'method': 'ATR',
                    'atr_14d': float,
                    'atr_multiplier': float,
                    'stop_price': float,
                    'stop_distance_pct': float
                },
                'warnings': [],
                'metadata': {...}
            }
        """
        try:
            logger.info(f"Analyzing {symbol} with TechnicalAnalyzerV2 (orthogonal)")

            # ========== STEP 1: Get price data ==========
            prices = self.fmp.get_historical_prices(symbol, days=300)
            if not prices or len(prices) < 250:
                return {'error': f'Insufficient price data for {symbol}'}

            current_price = prices[0]['close']

            # ========== STEP 2: Get market data (SPY, VIX, Sector) ==========
            spy_prices = self.fmp.get_historical_prices('SPY', days=300)
            sector_etf = self.SECTOR_ETFS.get(sector, 'SPY')
            sector_prices = self.fmp.get_historical_prices(sector_etf, days=300)

            # ========== STEP 3: Calculate components (orthogonal) ==========

            # A) Relative Strength (0-40)
            rs_score, rs_data = self._calculate_relative_strength(
                prices, spy_prices, sector_prices
            )

            # B) Trend/Structure (0-25)
            trend_score, trend_data = self._calculate_trend_structure(prices)

            # C) Risk Quality (0-20)
            risk_score, risk_data = self._calculate_risk_quality(prices)

            # D) Volume/Participation (0-15)
            volume_score, volume_data = self._calculate_volume_participation(prices)

            # Total Score (0-100)
            total_score = rs_score + trend_score + risk_score + volume_score
            total_score = max(0, min(100, total_score))  # Clamp

            # ========== STEP 4: Detect States (for sizing/action) ==========

            # Extension State
            ma_200 = trend_data['ma_200']
            distance_ma200 = ((current_price - ma_200) / ma_200 * 100) if ma_200 > 0 else 0
            extension_state = self._classify_extension_state(distance_ma200)

            # Market Regime
            regime_state, regime_data = self._detect_market_regime()

            # Trend State
            trend_state = trend_data['trend_state']

            # ========== STEP 5: Calculate Conviction ==========
            conviction = self._calculate_conviction(total_score)

            # ========== STEP 6: Position Sizing ==========
            atr_14 = self._calculate_atr(prices, period=14)

            position_sizing = self._calculate_position_size(
                portfolio_value=portfolio_value,
                risk_per_trade=risk_per_trade,
                current_price=current_price,
                conviction=conviction,
                regime_state=regime_state,
                extension_state=extension_state,
                atr_14=atr_14
            )

            # ========== STEP 7: Stop Loss (ATR-based) ==========
            stop_loss = self._calculate_atr_stop_loss(
                current_price=current_price,
                atr_14=atr_14,
                extension_state=extension_state
            )

            # ========== STEP 8: Generate Warnings ==========
            warnings = self._generate_warnings_v2(
                total_score=total_score,
                extension_state=extension_state,
                regime_state=regime_state,
                trend_state=trend_state,
                conviction=conviction,
                distance_ma200=distance_ma200,
                risk_data=risk_data
            )

            # ========== STEP 9: Return comprehensive analysis ==========
            return {
                'score': round(total_score, 1),
                'components': {
                    'relative_strength': round(rs_score, 1),
                    'trend_structure': round(trend_score, 1),
                    'risk_quality': round(risk_score, 1),
                    'volume_participation': round(volume_score, 1)
                },
                'component_details': {
                    'relative_strength': rs_data,
                    'trend_structure': trend_data,
                    'risk_quality': risk_data,
                    'volume_participation': volume_data
                },
                'states': {
                    'extension': extension_state,
                    'regime': regime_state,
                    'trend': trend_state
                },
                'conviction': round(conviction, 3),
                'position_sizing': position_sizing,
                'stop_loss': stop_loss,
                'warnings': warnings,
                'metadata': {
                    'symbol': symbol,
                    'sector': sector,
                    'current_price': current_price,
                    'distance_ma200_pct': round(distance_ma200, 1),
                    'regime_data': regime_data,
                    'analysis_version': 'V2_ORTHOGONAL'
                }
            }

        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}", exc_info=True)
            return {'error': str(e)}

    # ============================================================================
    # COMPONENT A: RELATIVE STRENGTH (0-40 pts)
    # ============================================================================

    def _calculate_relative_strength(
        self,
        prices: List[Dict],
        spy_prices: List[Dict],
        sector_prices: List[Dict]
    ) -> Tuple[float, Dict]:
        """
        Calculate multi-timeframe relative strength (orthogonal momentum).

        Components:
        - RS 12-1 vs SPY: 0-18 pts
        - RS 6-1 vs SPY: 0-12 pts
        - RS 6-1 vs Sector: 0-10 pts

        Total: 0-40 pts

        Evidence:
        - Jegadeesh & Titman (1993): 12M momentum works
        - Novy-Marx (2012): 6M intermediate is strongest
        - Excludes last month to avoid reversals
        """
        try:
            # Get prices at key dates
            price_current = prices[0]['close']
            price_1m = prices[22]['close'] if len(prices) > 22 else price_current
            price_6m = prices[132]['close'] if len(prices) > 132 else price_current
            price_12m = prices[250]['close'] if len(prices) > 250 else price_current

            spy_current = spy_prices[0]['close']
            spy_1m = spy_prices[22]['close'] if len(spy_prices) > 22 else spy_current
            spy_6m = spy_prices[132]['close'] if len(spy_prices) > 132 else spy_current
            spy_12m = spy_prices[250]['close'] if len(spy_prices) > 250 else spy_current

            sector_current = sector_prices[0]['close']
            sector_1m = sector_prices[22]['close'] if len(sector_prices) > 22 else sector_current
            sector_6m = sector_prices[132]['close'] if len(sector_prices) > 132 else sector_current

            # Calculate returns (excluding last month for 12-1)
            stock_ret_12_1 = ((price_1m - price_12m) / price_12m * 100) if price_12m > 0 else 0
            spy_ret_12_1 = ((spy_1m - spy_12m) / spy_12m * 100) if spy_12m > 0 else 0
            rs_12_1 = stock_ret_12_1 - spy_ret_12_1

            # Calculate 6-1 returns
            stock_ret_6_1 = ((price_1m - price_6m) / price_6m * 100) if price_6m > 0 else 0
            spy_ret_6_1 = ((spy_1m - spy_6m) / spy_6m * 100) if spy_6m > 0 else 0
            rs_6_1_spy = stock_ret_6_1 - spy_ret_6_1

            # Calculate 6-1 vs sector
            sector_ret_6_1 = ((sector_1m - sector_6m) / sector_6m * 100) if sector_6m > 0 else 0
            rs_6_1_sector = stock_ret_6_1 - sector_ret_6_1

            # Score using linear interpolation (percentile-based would be better with universe)
            # For now, use thresholds: excellent > 20%, good > 10%, neutral > 0%

            # RS 12-1 vs SPY: 0-18 pts
            score_12_1 = self._score_rs_component(rs_12_1, max_pts=18, threshold=20)

            # RS 6-1 vs SPY: 0-12 pts
            score_6_1_spy = self._score_rs_component(rs_6_1_spy, max_pts=12, threshold=15)

            # RS 6-1 vs Sector: 0-10 pts
            score_6_1_sector = self._score_rs_component(rs_6_1_sector, max_pts=10, threshold=10)

            total_rs = score_12_1 + score_6_1_spy + score_6_1_sector

            return total_rs, {
                'rs_12_1_vs_spy': round(rs_12_1, 1),
                'rs_6_1_vs_spy': round(rs_6_1_spy, 1),
                'rs_6_1_vs_sector': round(rs_6_1_sector, 1),
                'score_12_1': round(score_12_1, 1),
                'score_6_1_spy': round(score_6_1_spy, 1),
                'score_6_1_sector': round(score_6_1_sector, 1),
                'stock_ret_12_1': round(stock_ret_12_1, 1),
                'spy_ret_12_1': round(spy_ret_12_1, 1),
                'stock_ret_6_1': round(stock_ret_6_1, 1),
                'spy_ret_6_1': round(spy_ret_6_1, 1),
                'sector_ret_6_1': round(sector_ret_6_1, 1)
            }

        except Exception as e:
            logger.warning(f"Error calculating relative strength: {e}")
            return 0, {}

    def _score_rs_component(self, rs_pct: float, max_pts: float, threshold: float) -> float:
        """
        Score a single RS component using linear interpolation.

        Args:
            rs_pct: Relative strength percentage
            max_pts: Maximum points for this component
            threshold: Threshold for full points (e.g., 20% = full points)

        Returns:
            Score 0 to max_pts
        """
        if rs_pct >= threshold:
            return max_pts
        elif rs_pct <= -threshold:
            return 0
        else:
            # Linear interpolation: 0% RS = 50% of points
            return max_pts * (0.5 + (rs_pct / (2 * threshold)))

    # ============================================================================
    # COMPONENT B: TREND/STRUCTURE (0-25 pts)
    # ============================================================================

    def _calculate_trend_structure(self, prices: List[Dict]) -> Tuple[float, Dict]:
        """
        Calculate trend structure quality (avoid buying winners with broken structure).

        Components:
        - Price > MA200: 0/6 pts
        - MA50 > MA200: 0/6 pts
        - MA200 slope positive: 0/5 pts
        - EMA stack (EMA20 > MA50 > MA200): 0/5 pts
        - Breakout structure (near 52W high, not vertical): 0/3 pts

        Total: 0-25 pts

        Evidence:
        - Brock et al. (1992): MA200 crossovers predict returns
        - Faber (2007): Trend following reduces drawdowns
        """
        try:
            current_price = prices[0]['close']

            # Calculate moving averages
            ma_200 = statistics.mean(p['close'] for p in prices[:200]) if len(prices) >= 200 else 0
            ma_50 = statistics.mean(p['close'] for p in prices[:50]) if len(prices) >= 50 else 0
            ema_20 = self._calculate_ema(prices, 20)

            # Calculate MA200 slope (10-day change)
            if len(prices) >= 210:
                ma_200_past = statistics.mean(p['close'] for p in prices[10:210])
                ma_200_slope = ((ma_200 - ma_200_past) / ma_200_past / 10 * 100) if ma_200_past > 0 else 0
            else:
                ma_200_slope = 0

            # Get 52-week high
            week_52_high = max(p['high'] for p in prices[:min(250, len(prices))])

            score = 0

            # 1. Price > MA200: 6 pts (binary)
            price_above_ma200 = current_price > ma_200 if ma_200 > 0 else False
            if price_above_ma200:
                score += 6

            # 2. MA50 > MA200: 6 pts (golden cross, binary)
            ma50_above_ma200 = ma_50 > ma_200 if (ma_50 > 0 and ma_200 > 0) else False
            if ma50_above_ma200:
                score += 6

            # 3. MA200 slope positive: 0-5 pts (scaled)
            if ma_200_slope > 0.1:  # > 0.1% per day = strongly rising
                score += 5
            elif ma_200_slope > 0.05:
                score += 3
            elif ma_200_slope > 0:
                score += 1

            # 4. EMA stack: 5 pts (binary)
            ema_stack = (ema_20 > ma_50 > ma_200) if (ema_20 > 0 and ma_50 > 0 and ma_200 > 0) else False
            if ema_stack:
                score += 5

            # 5. Breakout structure: 0-3 pts
            # Near 52W high (within 5%) but not vertical (within 2%)
            distance_to_high = ((week_52_high - current_price) / week_52_high * 100) if week_52_high > 0 else 100
            if distance_to_high <= 2:  # Within 2% of high
                score += 1  # At high but might be overextended
            elif distance_to_high <= 5:  # Within 5% of high
                score += 3  # Sweet spot: near high, room to break out
            elif distance_to_high <= 10:
                score += 2  # Close to high
            elif distance_to_high <= 20:
                score += 1  # Approaching high

            # Determine trend state
            if price_above_ma200 and ma50_above_ma200 and ema_stack:
                trend_state = 'UPTREND'
            elif not price_above_ma200 and ma_50 < ma_200 and ema_20 < ma_50:
                trend_state = 'DOWNTREND'
            else:
                trend_state = 'CHOP'

            return score, {
                'ma_200': round(ma_200, 2),
                'ma_50': round(ma_50, 2),
                'ema_20': round(ema_20, 2),
                'ma_200_slope_pct': round(ma_200_slope, 3),
                'week_52_high': round(week_52_high, 2),
                'distance_to_52w_high_pct': round(distance_to_high, 1),
                'price_above_ma200': price_above_ma200,
                'ma50_above_ma200': ma50_above_ma200,
                'ema_stack': ema_stack,
                'trend_state': trend_state
            }

        except Exception as e:
            logger.warning(f"Error calculating trend structure: {e}")
            return 0, {'trend_state': 'UNKNOWN'}

    def _calculate_ema(self, prices: List[Dict], period: int) -> float:
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return 0

        multiplier = 2 / (period + 1)
        ema = prices[period - 1]['close']  # Start with SMA

        for i in range(period - 2, -1, -1):
            ema = (prices[i]['close'] - ema) * multiplier + ema

        return ema

    # ============================================================================
    # COMPONENT C: RISK QUALITY (0-20 pts)
    # ============================================================================

    def _calculate_risk_quality(self, prices: List[Dict]) -> Tuple[float, Dict]:
        """
        Calculate risk-adjusted quality (avoid fragile momentum).

        Components:
        - Sharpe/Sortino 6M: 0-10 pts
        - Max drawdown 6M: 0-6 pts
        - Realized volatility penalty: 0-4 pts

        Total: 0-20 pts

        Evidence:
        - Daniel & Moskowitz (2016): High-vol momentum crashes
        - Barroso & Santa-Clara (2015): Volatility-managed momentum
        """
        try:
            # Use 6M data (132 days)
            period = min(132, len(prices))
            recent_prices = prices[:period]

            # Calculate daily returns
            returns = []
            for i in range(len(recent_prices) - 1):
                ret = (recent_prices[i]['close'] - recent_prices[i+1]['close']) / recent_prices[i+1]['close']
                returns.append(ret)

            if not returns:
                return 0, {}

            # Sharpe Ratio (6M)
            mean_return = statistics.mean(returns)
            std_return = statistics.stdev(returns) if len(returns) > 1 else 0
            sharpe = (mean_return / std_return * (252 ** 0.5)) if std_return > 0 else 0

            # Sortino Ratio (only downside vol)
            downside_returns = [r for r in returns if r < 0]
            downside_std = statistics.stdev(downside_returns) if len(downside_returns) > 1 else std_return
            sortino = (mean_return / downside_std * (252 ** 0.5)) if downside_std > 0 else 0

            # Max Drawdown (6M)
            peak = recent_prices[-1]['close']
            max_dd = 0
            for price in recent_prices:
                if price['close'] > peak:
                    peak = price['close']
                dd = (peak - price['close']) / peak
                if dd > max_dd:
                    max_dd = dd

            max_dd_pct = max_dd * 100

            # Realized Volatility (annualized)
            realized_vol = std_return * (252 ** 0.5) * 100 if std_return > 0 else 0

            # ===== SCORING =====
            score = 0

            # 1. Sharpe/Sortino 6M: 0-10 pts (use better of two)
            best_ratio = max(sharpe, sortino)
            if best_ratio >= 2.0:
                score += 10
            elif best_ratio >= 1.5:
                score += 8
            elif best_ratio >= 1.0:
                score += 6
            elif best_ratio >= 0.5:
                score += 4
            elif best_ratio >= 0:
                score += 2
            # Negative ratio = 0 pts

            # 2. Max Drawdown 6M: 0-6 pts (lower is better)
            if max_dd_pct < 10:
                score += 6
            elif max_dd_pct < 15:
                score += 5
            elif max_dd_pct < 20:
                score += 4
            elif max_dd_pct < 25:
                score += 3
            elif max_dd_pct < 30:
                score += 2
            elif max_dd_pct < 40:
                score += 1
            # > 40% = 0 pts

            # 3. Realized Volatility: 0-4 pts (penalize EXTREMES, not normal vol)
            # Don't kill momentum leaders, just flag fragile high-vol/low-return
            if realized_vol < 30:
                score += 4  # Low vol
            elif realized_vol < 40:
                score += 3  # Normal
            elif realized_vol < 50:
                score += 2  # Elevated
            elif realized_vol < 70:
                score += 1  # High (momentum leaders often here)
            # > 70% = 0 pts (extreme fragility)

            return score, {
                'sharpe_6m': round(sharpe, 2),
                'sortino_6m': round(sortino, 2),
                'max_drawdown_6m_pct': round(max_dd_pct, 1),
                'realized_vol_pct': round(realized_vol, 1),
                'mean_return_daily': round(mean_return * 100, 3),
                'std_return_daily': round(std_return * 100, 3)
            }

        except Exception as e:
            logger.warning(f"Error calculating risk quality: {e}")
            return 0, {}

    # ============================================================================
    # COMPONENT D: VOLUME/PARTICIPATION (0-15 pts)
    # ============================================================================

    def _calculate_volume_participation(self, prices: List[Dict]) -> Tuple[float, Dict]:
        """
        Calculate institutional participation (confirmation, not alpha).

        Components:
        - Up-volume vs Down-volume (4-8 weeks): 0-6 pts
        - Distribution days penalty: 0-5 pts
        - Relative volume on breakouts: 0-4 pts

        Total: 0-15 pts

        Evidence:
        - Lee & Swaminathan (2000): Volume confirms momentum
        - O'Neil (CANSLIM): Institutional accumulation matters
        """
        try:
            # Use 4-8 weeks (22-44 days)
            period = min(44, len(prices))
            recent_prices = prices[:period]

            # Calculate up-volume vs down-volume
            up_volume = 0
            down_volume = 0
            distribution_days = 0

            for i in range(len(recent_prices) - 1):
                price_change = recent_prices[i]['close'] - recent_prices[i+1]['close']
                volume = recent_prices[i].get('volume', 0)

                if price_change > 0:
                    up_volume += volume
                elif price_change < 0:
                    down_volume += volume

                    # Distribution day: down day with volume > 20d avg
                    if i >= 20:
                        avg_vol_20 = statistics.mean(p.get('volume', 0) for p in recent_prices[i:i+20])
                        if volume > avg_vol_20:
                            distribution_days += 1

            # Accumulation ratio
            total_volume = up_volume + down_volume
            acc_ratio = (up_volume / total_volume) if total_volume > 0 else 0.5

            # Average volume (for relative volume calc)
            avg_volume = statistics.mean(p.get('volume', 0) for p in recent_prices) if recent_prices else 0
            recent_volume = recent_prices[0].get('volume', 0) if recent_prices else 0
            relative_volume = (recent_volume / avg_volume) if avg_volume > 0 else 1.0

            # Check if near breakout (within 5% of 52W high)
            current_price = recent_prices[0]['close']
            week_52_high = max(p['high'] for p in prices[:min(250, len(prices))])
            distance_to_high = ((week_52_high - current_price) / week_52_high * 100) if week_52_high > 0 else 100
            near_breakout = distance_to_high <= 5

            # ===== SCORING =====
            score = 0

            # 1. Up-volume vs Down-volume: 0-6 pts
            if acc_ratio >= 0.65:
                score += 6  # Strong accumulation
            elif acc_ratio >= 0.60:
                score += 5
            elif acc_ratio >= 0.55:
                score += 4
            elif acc_ratio >= 0.50:
                score += 3  # Neutral
            elif acc_ratio >= 0.45:
                score += 2
            elif acc_ratio >= 0.40:
                score += 1
            # < 0.40 = 0 pts (distribution)

            # 2. Distribution days penalty: 0-5 pts (fewer is better)
            if distribution_days == 0:
                score += 5
            elif distribution_days <= 2:
                score += 4
            elif distribution_days <= 4:
                score += 3
            elif distribution_days <= 6:
                score += 2
            elif distribution_days <= 8:
                score += 1
            # > 8 distribution days = 0 pts

            # 3. Relative volume on breakouts: 0-4 pts
            if near_breakout:
                if relative_volume >= 1.5:
                    score += 4  # High volume on breakout
                elif relative_volume >= 1.2:
                    score += 3
                elif relative_volume >= 1.0:
                    score += 2
                elif relative_volume >= 0.8:
                    score += 1
            else:
                # Not near breakout, just check if volume is healthy
                if relative_volume >= 1.0:
                    score += 2
                elif relative_volume >= 0.8:
                    score += 1

            # Volume profile classification
            if acc_ratio >= 0.55:
                volume_profile = 'ACCUMULATION'
            elif acc_ratio >= 0.45:
                volume_profile = 'NEUTRAL'
            else:
                volume_profile = 'DISTRIBUTION'

            return score, {
                'accumulation_ratio': round(acc_ratio, 3),
                'up_volume': up_volume,
                'down_volume': down_volume,
                'distribution_days': distribution_days,
                'avg_volume': round(avg_volume, 0),
                'recent_volume': round(recent_volume, 0),
                'relative_volume': round(relative_volume, 2),
                'near_breakout': near_breakout,
                'volume_profile': volume_profile
            }

        except Exception as e:
            logger.warning(f"Error calculating volume participation: {e}")
            return 0, {'volume_profile': 'UNKNOWN'}

    # ============================================================================
    # STATE DETECTION (not for scoring, for action/sizing)
    # ============================================================================

    def _classify_extension_state(self, distance_ma200: float) -> str:
        """
        Classify extension state based on distance from MA200.

        Returns: NORMAL | EXTENDED | STRETCHED | OVEREXTENDED
        """
        abs_distance = abs(distance_ma200)

        if abs_distance <= self.EXTENSION_THRESHOLDS['NORMAL']:
            return 'NORMAL'
        elif abs_distance <= self.EXTENSION_THRESHOLDS['EXTENDED']:
            return 'EXTENDED'
        elif abs_distance <= self.EXTENSION_THRESHOLDS['STRETCHED']:
            return 'STRETCHED'
        else:
            return 'OVEREXTENDED'

    def _detect_market_regime(self) -> Tuple[str, Dict]:
        """
        Detect market regime: BULL / SIDEWAYS / BEAR

        Uses SPY vs MA200 and VIX levels.
        Cached for 6 hours.
        """
        try:
            # Check cache (6 hour expiry)
            now = datetime.now()
            if (self._market_regime_cache and self._market_regime_timestamp and
                (now - self._market_regime_timestamp).total_seconds() < 6 * 3600):
                return self._market_regime_cache, {}

            # Get SPY and VIX data
            spy_prices = self.fmp.get_historical_prices('SPY', days=210)
            vix_data = self.fmp.get_quote('^VIX')

            if not spy_prices or len(spy_prices) < 200:
                return 'SIDEWAYS', {}

            spy_price = spy_prices[0]['close']
            spy_ma200 = statistics.mean(p['close'] for p in spy_prices[:200])
            spy_vs_ma200 = ((spy_price - spy_ma200) / spy_ma200 * 100) if spy_ma200 > 0 else 0

            vix = vix_data[0]['price'] if vix_data else 20

            # Regime logic
            if spy_price > spy_ma200 and vix < 20:
                regime = 'BULL'
            elif spy_price < spy_ma200 and vix > 30:
                regime = 'BEAR'
            else:
                regime = 'SIDEWAYS'

            # Cache result
            self._market_regime_cache = regime
            self._market_regime_timestamp = now

            return regime, {
                'spy_price': round(spy_price, 2),
                'spy_ma200': round(spy_ma200, 2),
                'spy_vs_ma200_pct': round(spy_vs_ma200, 1),
                'vix': round(vix, 1)
            }

        except Exception as e:
            logger.warning(f"Error detecting market regime: {e}")
            return 'SIDEWAYS', {}

    # ============================================================================
    # CONVICTION & POSITION SIZING
    # ============================================================================

    def _calculate_conviction(self, tech_score: float) -> float:
        """
        Calculate conviction scalar from tech score.

        Formula: conviction = clip((TechScore - 60) / 30, 0, 1)

        60 → 0.0 (no conviction)
        75 → 0.5 (moderate)
        90 → 1.0 (high conviction)
        """
        conviction = (tech_score - 60) / 30
        return max(0.0, min(1.0, conviction))

    def _calculate_position_size(
        self,
        portfolio_value: float,
        risk_per_trade: float,
        current_price: float,
        conviction: float,
        regime_state: str,
        extension_state: str,
        atr_14: float
    ) -> Dict:
        """
        Calculate position size using risk-based approach.

        Formula:
        R$ = portfolio × risk_per_trade
        R$_adj = R$ × conviction × regime_factor × extension_factor
        stop_dist = k × ATR (k depends on extension)
        PositionSize = R$_adj / stop_dist

        Returns position sizing details.
        """
        # Base risk in USD
        base_risk_usd = portfolio_value * risk_per_trade

        # Get factors
        regime_factor = self.REGIME_FACTORS.get(regime_state, 0.7)
        extension_factor = self.EXTENSION_FACTORS.get(extension_state, 1.0)

        # Adjusted risk
        adjusted_risk_usd = base_risk_usd * conviction * regime_factor * extension_factor

        # Stop distance (ATR-based)
        # Adjust k multiplier based on extension
        if extension_state == 'NORMAL':
            k = 2.5
        elif extension_state == 'EXTENDED':
            k = 2.5
        elif extension_state == 'STRETCHED':
            k = 3.0  # More air for stretched
        else:  # OVEREXTENDED
            k = 3.5  # Maximum air

        stop_dist_pct = (k * atr_14) if atr_14 > 0 else 0.10  # Default 10% if no ATR

        # Position size
        position_size_usd = (adjusted_risk_usd / stop_dist_pct) if stop_dist_pct > 0 else 0
        position_size_shares = int(position_size_usd / current_price) if current_price > 0 else 0

        return {
            'base_risk_usd': round(base_risk_usd, 2),
            'conviction_scalar': round(conviction, 3),
            'regime_factor': regime_factor,
            'extension_factor': extension_factor,
            'adjusted_risk_usd': round(adjusted_risk_usd, 2),
            'atr_multiplier': k,
            'stop_distance_pct': round(stop_dist_pct * 100, 2),
            'position_size_usd': round(position_size_usd, 2),
            'position_size_shares': position_size_shares,
            'position_pct_of_portfolio': round((position_size_usd / portfolio_value * 100), 2)
        }

    def _calculate_atr_stop_loss(
        self,
        current_price: float,
        atr_14: float,
        extension_state: str
    ) -> Dict:
        """
        Calculate ATR-based stop loss.

        k multiplier varies by extension state.
        """
        # Adjust k multiplier
        if extension_state == 'NORMAL':
            k = 2.5
        elif extension_state == 'EXTENDED':
            k = 2.5
        elif extension_state == 'STRETCHED':
            k = 3.0
        else:  # OVEREXTENDED
            k = 3.5

        stop_dist_pct = k * atr_14 if atr_14 > 0 else 0.10
        stop_price = current_price * (1 - stop_dist_pct)

        return {
            'method': 'ATR',
            'atr_14d_pct': round(atr_14 * 100, 2),
            'atr_multiplier': k,
            'stop_distance_pct': round(stop_dist_pct * 100, 2),
            'stop_price': round(stop_price, 2),
            'extension_adjusted': True
        }

    def _calculate_atr(self, prices: List[Dict], period: int = 14) -> float:
        """
        Calculate Average True Range as % of current price.

        Returns ATR as decimal (e.g., 0.03 = 3%)
        """
        if len(prices) < period + 1:
            return 0.02  # Default 2%

        try:
            true_ranges = []
            for i in range(period):
                high = prices[i]['high']
                low = prices[i]['low']
                prev_close = prices[i + 1]['close']

                tr = max(
                    high - low,
                    abs(high - prev_close),
                    abs(low - prev_close)
                )
                true_ranges.append(tr)

            atr = statistics.mean(true_ranges)
            current_price = prices[0]['close']

            # Return as percentage
            return (atr / current_price) if current_price > 0 else 0.02

        except Exception as e:
            logger.warning(f"Error calculating ATR: {e}")
            return 0.02

    # ============================================================================
    # WARNINGS & RECOMMENDATIONS
    # ============================================================================

    def _generate_warnings_v2(
        self,
        total_score: float,
        extension_state: str,
        regime_state: str,
        trend_state: str,
        conviction: float,
        distance_ma200: float,
        risk_data: Dict
    ) -> List[Dict]:
        """
        Generate warnings for V2 system.

        Focus on actionable insights, not redundant momentum warnings.
        """
        warnings = []

        # CRITICAL: DOWNTREND veto
        if trend_state == 'DOWNTREND':
            warnings.append({
                'type': 'CRITICAL',
                'category': 'TREND',
                'message': f'🚨 DOWNTREND detected (broken structure). AVOID entry regardless of score ({total_score:.0f}/100).',
                'action': 'Wait for trend repair (price > EMA20 > MA50 > MA200)'
            })

        # CRITICAL: OVEREXTENDED in BEAR market
        if extension_state == 'OVEREXTENDED' and regime_state == 'BEAR':
            warnings.append({
                'type': 'CRITICAL',
                'category': 'EXTENSION',
                'message': f'🚨 OVEREXTENDED in BEAR market ({distance_ma200:+.1f}% from MA200). Extreme crash risk.',
                'action': 'AVOID or exit immediately. Wait for >50% pullback.'
            })

        # HIGH: OVEREXTENDED generally
        if extension_state == 'OVEREXTENDED' and regime_state != 'BEAR':
            warnings.append({
                'type': 'HIGH',
                'category': 'EXTENSION',
                'message': f'⚠️ OVEREXTENDED: {distance_ma200:+.1f}% from MA200. High volatility expected.',
                'action': f'Minimal position (20% normal size). Expect 20-40% swings. Use trailing stop.'
            })

        # HIGH: STRETCHED
        if extension_state == 'STRETCHED':
            warnings.append({
                'type': 'HIGH',
                'category': 'EXTENSION',
                'message': f'⚠️ STRETCHED: {distance_ma200:+.1f}% from MA200. Elevated correction risk.',
                'action': f'Reduced position (40% normal size). Scale-in strategy recommended.'
            })

        # MEDIUM: EXTENDED
        if extension_state == 'EXTENDED':
            warnings.append({
                'type': 'MEDIUM',
                'category': 'EXTENSION',
                'message': f'⚠️ EXTENDED: {distance_ma200:+.1f}% from MA200. Monitor for pullback.',
                'action': f'Moderate position (70% normal size). Consider scaling.'
            })

        # MEDIUM: Low conviction
        if conviction < 0.3 and total_score < 70:
            warnings.append({
                'type': 'MEDIUM',
                'category': 'CONVICTION',
                'message': f'Low conviction setup (score {total_score:.0f}/100, conviction {conviction:.2f}).',
                'action': 'Consider waiting for clearer setup or reduce position size.'
            })

        # MEDIUM: High drawdown risk
        max_dd = risk_data.get('max_drawdown_6m_pct', 0)
        if max_dd > 30:
            warnings.append({
                'type': 'MEDIUM',
                'category': 'RISK',
                'message': f'High recent drawdown: {max_dd:.1f}% in last 6M. Volatility risk.',
                'action': 'Use wider stops. Reduce position size if low risk tolerance.'
            })

        # INFO: BEAR market context
        if regime_state == 'BEAR' and total_score >= 70:
            warnings.append({
                'type': 'INFO',
                'category': 'REGIME',
                'message': f'BEAR market regime. Strong relative strength but broader market risk.',
                'action': 'Reduce position size (40% of normal). Tight stops. Be ready to exit.'
            })

        return warnings
