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

from .market_regime import (
    MarketRegimeSystem,
    GlobalRegime,
    BreadthState,
    RegionalRegime,
    SectorRegime
)

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

    # Regime factors for position sizing (updated for hierarchical system)
    REGIME_FACTORS = {
        'BULL': 1.0,
        'GLOBAL_BULL': 1.0,
        'SIDEWAYS': 0.75,
        'AMBIGUOUS': 0.7,
        'GLOBAL_AMBIGUOUS': 0.7,
        'BEAR': 0.5,
        'GLOBAL_BEAR': 0.0,  # Kill switch
    }

    # Extension factors for position sizing
    EXTENSION_FACTORS = {
        'NORMAL': 1.0,
        'EXTENDED': 0.7,
        'STRETCHED': 0.4,
        'OVEREXTENDED': 0.2,
    }

    # Emerging markets with limited data availability
    EMERGING_MARKETS = {
        # Asia-Pacific
        'IN', 'ID', 'TH', 'MY', 'PH', 'VN', 'PK', 'BD',
        # Latin America
        'MX', 'BR', 'CL', 'AR', 'CO',
        # Eastern Europe
        'PL', 'CZ', 'HU', 'RU',
        # Middle East & Africa
        'ZA', 'EG', 'TR', 'SA', 'AE', 'QA'
    }

    # Minimum data requirements by market type
    MIN_DAYS_DEVELOPED = 250  # ~12 months trading days
    MIN_DAYS_EMERGING = 90    # ~4 months trading days (reduced for data availability)

    def __init__(self, fmp_client):
        """
        Args:
            fmp_client: FMP client (preferably CachedFMPClient)
        """
        self.fmp = fmp_client
        self._market_regime_cache = None
        self._market_regime_timestamp = None
        # Hierarchical Market Regime System
        self.regime_system = MarketRegimeSystem(fmp_client)

    def _get_from_date(self, days: int) -> str:
        """
        Helper to convert days lookback to from_date string for FMP API.

        Args:
            days: Number of days to look back

        Returns:
            Date string in YYYY-MM-DD format
        """
        from_date = datetime.now() - timedelta(days=days)
        return from_date.strftime('%Y-%m-%d')

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
            # Determine minimum data requirements based on market
            is_emerging = country in self.EMERGING_MARKETS
            min_days_required = self.MIN_DAYS_EMERGING if is_emerging else self.MIN_DAYS_DEVELOPED
            lookback_days = 150 if is_emerging else 365  # Reduced lookback for emerging markets

            logger.info(f"Market type: {'Emerging' if is_emerging else 'Developed'} ({country}), min days: {min_days_required}")

            from_date = self._get_from_date(days=lookback_days)

            price_data = self.fmp.get_historical_prices(symbol, from_date=from_date)
            if not price_data or 'historical' not in price_data:
                return {'error': f'No price data returned for {symbol}'}

            prices = price_data.get('historical', [])
            if not prices or len(prices) < min_days_required:
                return {'error': f'Insufficient price data for {symbol} (got {len(prices)} days, need {min_days_required}+ for {country})'}

            # Sort by date descending (newest first) - FMP returns oldest first
            prices = sorted(prices, key=lambda x: x['date'], reverse=True)
            current_price = prices[0]['close']

            # ========== STEP 2: Get market data (SPY, VIX, Sector) ==========
            spy_data = self.fmp.get_historical_prices('SPY', from_date=from_date)
            spy_prices = sorted(spy_data.get('historical', []), key=lambda x: x['date'], reverse=True) if spy_data else []

            sector_etf = self.SECTOR_ETFS.get(sector, 'SPY')
            sector_data = self.fmp.get_historical_prices(sector_etf, from_date=from_date)
            sector_prices = sorted(sector_data.get('historical', []), key=lambda x: x['date'], reverse=True) if sector_data else []

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

            # Market Regime (hierarchical system)
            regime_state, regime_data = self._detect_market_regime(country=country, sector=sector)

            # Trend State
            trend_state = trend_data['trend_state']

            # ========== STEP 4b: Environment Multiplier (CAPA 7) ==========
            # Calculate hierarchical environment adjustment
            environment_multiplier = self.regime_system.calculate_environment_multiplier(
                country=country,
                sector=sector
            )

            # ========== STEP 5: Calculate Conviction ==========
            # Get volume profile from volume component
            volume_profile = volume_data.get('volume_profile', 'UNKNOWN')

            conviction_result = self._calculate_conviction(
                tech_score=total_score,
                regime_state=regime_state,
                extension_state=extension_state,
                volume_profile=volume_profile,
                environment_multiplier=environment_multiplier
            )
            conviction = conviction_result['conviction']

            # ========== STEP 5b: Generate Signal (CAPA 8) ==========
            signal_result = self._generate_signal(
                total_score=total_score,
                conviction=conviction,
                regime_state=regime_state,
                trend_state=trend_state,
                environment_multiplier=environment_multiplier
            )

            # ========== STEP 6: Position Sizing ==========
            atr_14 = self._calculate_atr(prices, period=14)

            # Check if ATR is available (fallback if missing data)
            if atr_14 == 0 or atr_14 is None:
                # Fallback: use 2% of price as proxy
                atr_14 = current_price * 0.02
                logger.warning(f"{symbol}: ATR unavailable, using 2% price fallback")

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
                risk_data=risk_data,
                environment_multiplier=environment_multiplier
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
                'signal': signal_result,  # CAPA 8: Signal generation
                'conviction': round(conviction, 3),
                'conviction_breakdown': conviction_result,  # Include full breakdown
                'environment': {
                    'can_trade': environment_multiplier['can_trade'],
                    'multiplier': environment_multiplier['final_multiplier'],
                    'vetoes': environment_multiplier['vetoes'],
                    'warnings': environment_multiplier['warnings'],
                    'components': environment_multiplier['components']
                },
                'volume_profile': volume_profile,  # Make available at top level
                'position_sizing': position_sizing,
                'stop_loss': stop_loss,
                'warnings': warnings,
                'metadata': {
                    'symbol': symbol,
                    'sector': sector,
                    'country': country,
                    'current_price': current_price,
                    'distance_ma200_pct': round(distance_ma200, 1),
                    'regime_data': regime_data,
                    'analysis_version': 'V2_HIERARCHICAL_REGIME'
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

    def _detect_market_regime(self, country: str = 'USA', sector: str = None) -> Tuple[str, Dict]:
        """
        Detect market regime using hierarchical system.

        Uses cross-market alignment (not just SPY):
        - SPY > MA200 (+1)
        - FEZ > MA200 (+1)
        - EEM > MA200 (+1)
        - SPY momentum 3-6M > 0 (+1)
        - VIX < 25 (+1)

        Score 4-5: GLOBAL_BULL
        Score 2-3: GLOBAL_AMBIGUOUS
        Score 0-1: GLOBAL_BEAR

        Cached for 6 hours.
        """
        try:
            # Get full hierarchical regime analysis
            global_regime = self.regime_system.get_global_regime()

            # Map to legacy format for backwards compatibility
            regime_enum = global_regime['regime']
            if regime_enum == GlobalRegime.BULL:
                regime = 'BULL'
            elif regime_enum == GlobalRegime.BEAR:
                regime = 'BEAR'
            else:
                regime = 'AMBIGUOUS'  # Replaces SIDEWAYS

            # Build detailed regime data
            regime_data = {
                'global_regime': regime_enum.value,
                'alignment_score': global_regime['alignment_score'],
                'max_score': global_regime['max_score'],
                'components': global_regime['components'],
            }

            # Add SPY details for compatibility
            spy_details = global_regime.get('details', {}).get('spy', {})
            if spy_details:
                regime_data['spy_price'] = spy_details.get('price')
                regime_data['spy_ma200'] = spy_details.get('ma200')
                regime_data['spy_vs_ma200_pct'] = spy_details.get('distance_pct')

            vix_details = global_regime.get('details', {}).get('vix', {})
            if vix_details:
                regime_data['vix'] = vix_details.get('value')

            # Add regional regime if country specified
            if country:
                regional = self.regime_system.get_regional_regime(country)
                regime_data['regional'] = {
                    'regime': regional['regime'].value,
                    'region': regional['region'],
                    'above_ma200': regional['above_ma200']
                }

            # Add sector regime if specified
            if sector:
                sector_regime = self.regime_system.get_sector_regime(sector)
                regime_data['sector'] = {
                    'regime': sector_regime['regime'].value,
                    'conditions': sector_regime['conditions'],
                    'all_conditions_met': sector_regime['all_conditions_met']
                }

            # Add breadth
            breadth = self.regime_system.get_global_breadth()
            regime_data['breadth'] = {
                'state': breadth['state'].value,
                'pct': breadth['breadth_pct'],
                'sectors_above': breadth['sectors_above_ma200'],
                'total': breadth['total_sectors']
            }

            # Add market context
            context = self.regime_system.get_market_context()
            regime_data['context'] = context

            return regime, regime_data

        except Exception as e:
            logger.warning(f"Error detecting market regime: {e}")
            return 'AMBIGUOUS', {'error': str(e)}

    # ============================================================================
    # CONVICTION & POSITION SIZING
    # ============================================================================

    def _calculate_conviction(
        self,
        tech_score: float,
        regime_state: str,
        extension_state: str,
        volume_profile: str,
        environment_multiplier: Dict = None
    ) -> Dict:
        """
        Calculate conviction with integrated factors: setup × market × timing × data × environment.

        CAPA 7: Ajuste de Convicción por Entorno
        final_score = raw_score × regime_mult × breadth_mult × drawdown_mult × sector_mult

        Args:
            tech_score: Technical score (0-100)
            regime_state: BULL/AMBIGUOUS/BEAR
            extension_state: NORMAL/EXTENDED/STRETCHED/OVEREXTENDED
            volume_profile: ACCUMULATION/NEUTRAL/DISTRIBUTION/UNKNOWN
            environment_multiplier: Dict from MarketRegimeSystem.calculate_environment_multiplier()

        Returns:
            Dict with conviction and factors breakdown
        """
        # 1. Setup strength (tech score mapped to 0-1)
        setup_strength = (tech_score - 60) / 30
        setup_strength = max(0.0, min(1.0, setup_strength))

        # 2. Market factor (from hierarchical regime)
        market_factor = self.REGIME_FACTORS.get(regime_state, 0.7)

        # 3. Timing factor (by extension)
        timing_factors = {
            'NORMAL': 1.0,
            'EXTENDED': 0.8,
            'STRETCHED': 0.55,
            'OVEREXTENDED': 0.35
        }
        timing_factor = timing_factors.get(extension_state, 0.8)

        # 4. Data quality factor
        data_factor = 1.0
        if volume_profile == 'UNKNOWN':
            data_factor *= 0.85  # 15% reduction for missing volume

        # 5. Environment factor (CAPA 7 - NEW)
        # Incorporates: regime, breadth, drawdown, sector
        if environment_multiplier and environment_multiplier.get('final_multiplier') is not None:
            env_factor = environment_multiplier['final_multiplier']
            env_components = environment_multiplier.get('components', {})
        else:
            env_factor = 1.0
            env_components = {}

        # Final conviction = setup × timing × data × environment
        # Note: market_factor is now embedded in env_factor via regime_multiplier
        # We keep it separate for backwards compatibility in breakdown
        final_conviction = setup_strength * timing_factor * data_factor * env_factor
        final_conviction = max(0.0, min(1.0, final_conviction))

        return {
            'conviction': round(final_conviction, 3),
            'setup_strength': round(setup_strength, 3),
            'market_factor': round(market_factor, 2),
            'timing_factor': round(timing_factor, 2),
            'data_factor': round(data_factor, 2),
            'environment_factor': round(env_factor, 3),
            'environment_components': env_components
        }

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

        # Build rationale
        rationale_parts = []
        rationale_parts.append(f"Base risk ${base_risk_usd:,.0f} ({risk_per_trade*100:.1f}% of portfolio)")
        rationale_parts.append(f"Adjusted by conviction {conviction:.2f}× regime {regime_factor:.2f}× extension {extension_factor:.2f} = ${adjusted_risk_usd:,.0f}")
        rationale_parts.append(f"Stop distance {stop_dist_pct*100:.1f}% ({k:.1f}× ATR)")
        rationale_parts.append(f"Final position: ${position_size_usd:,.0f} ({position_size_usd/portfolio_value*100:.1f}% of portfolio, {position_size_shares} shares)")

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
            'position_pct_of_portfolio': round((position_size_usd / portfolio_value * 100), 2),
            'rationale': ' → '.join(rationale_parts)
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
        risk_data: Dict,
        environment_multiplier: Dict = None
    ) -> List[Dict]:
        """
        Generate warnings for V2 system with hierarchical regime integration.

        Focus on actionable insights from the 8-layer architecture.
        """
        warnings = []

        # ========== ENVIRONMENT VETOES (CAPA 0-5) ==========
        if environment_multiplier:
            # Add vetoes as CRITICAL warnings
            for veto in environment_multiplier.get('vetoes', []):
                warnings.append({
                    'type': 'CRITICAL',
                    'category': 'ENVIRONMENT',
                    'message': f'🚨 VETO: {veto}',
                    'action': 'NO new entries allowed. Wait for conditions to improve.'
                })

            # Add environment warnings as HIGH/MEDIUM
            for env_warning in environment_multiplier.get('warnings', []):
                warnings.append({
                    'type': 'HIGH',
                    'category': 'ENVIRONMENT',
                    'message': f'⚠️ {env_warning}',
                    'action': 'Adjust position size according to environment multiplier.'
                })

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

        # INFO: AMBIGUOUS market context (replaces SIDEWAYS)
        if regime_state == 'AMBIGUOUS':
            if total_score >= 90:
                warnings.append({
                    'type': 'INFO',
                    'category': 'REGIME',
                    'message': f'AMBIGUOUS regime. Exceptional setup (score {total_score:.0f}) may proceed with caution.',
                    'action': 'Small position only (20-30% normal). Sector must be leading.'
                })
            else:
                warnings.append({
                    'type': 'MEDIUM',
                    'category': 'REGIME',
                    'message': f'AMBIGUOUS regime. Score {total_score:.0f} below 90 threshold.',
                    'action': 'HOLD - Wait for clearer market alignment or exceptional setup.'
                })

        return warnings

    # ============================================================================
    # CAPA 8: SIGNAL GENERATION
    # ============================================================================

    def _generate_signal(
        self,
        total_score: float,
        conviction: float,
        regime_state: str,
        trend_state: str,
        environment_multiplier: Dict
    ) -> Dict:
        """
        CAPA 8: Generate trading signal based on hierarchical rules.

        Rules (hard):
        - if GLOBAL_AMBIGUOUS and final_score < 90: HOLD
        - if GLOBAL_BULL and final_score >= 80: BUY
        - if any veto active: HOLD (or AVOID)

        Returns:
            {
                'signal': 'BUY'|'HOLD'|'AVOID',
                'reason': str,
                'min_score_required': int,
                'can_enter': bool,
                'position_size_pct': int
            }
        """
        vetoes = environment_multiplier.get('vetoes', [])
        can_trade = environment_multiplier.get('can_trade', True)
        env_mult = environment_multiplier.get('final_multiplier', 1.0)

        # Default result
        result = {
            'signal': 'HOLD',
            'reason': 'Default HOLD',
            'min_score_required': 75,
            'can_enter': False,
            'position_size_pct': 0
        }

        # Rule 1: Any veto active -> AVOID
        if vetoes or not can_trade:
            result = {
                'signal': 'AVOID',
                'reason': f"Environment veto: {vetoes[0] if vetoes else 'No trade allowed'}",
                'min_score_required': 999,  # Impossible
                'can_enter': False,
                'position_size_pct': 0
            }
            return result

        # Rule 2: DOWNTREND -> AVOID
        if trend_state == 'DOWNTREND':
            result = {
                'signal': 'AVOID',
                'reason': 'DOWNTREND detected - broken structure',
                'min_score_required': 999,
                'can_enter': False,
                'position_size_pct': 0
            }
            return result

        # Rule 3: BEAR market -> AVOID (should be caught by veto, but safety)
        if regime_state == 'BEAR':
            result = {
                'signal': 'AVOID',
                'reason': 'BEAR market regime - Kill Switch active',
                'min_score_required': 999,
                'can_enter': False,
                'position_size_pct': 0
            }
            return result

        # Rule 4: AMBIGUOUS regime
        if regime_state == 'AMBIGUOUS':
            min_score = 90  # Very high bar
            if total_score >= min_score:
                result = {
                    'signal': 'BUY',
                    'reason': f'Exceptional setup in AMBIGUOUS regime (score {total_score:.0f} >= {min_score})',
                    'min_score_required': min_score,
                    'can_enter': True,
                    'position_size_pct': int(30 * env_mult)  # Small position
                }
            else:
                result = {
                    'signal': 'HOLD',
                    'reason': f'AMBIGUOUS regime requires score >= {min_score} (got {total_score:.0f})',
                    'min_score_required': min_score,
                    'can_enter': False,
                    'position_size_pct': 0
                }
            return result

        # Rule 5: BULL regime - normal thresholds
        if regime_state == 'BULL':
            # Adjust threshold based on conviction
            if conviction >= 0.7:
                min_score = 75
            elif conviction >= 0.5:
                min_score = 80
            else:
                min_score = 85

            if total_score >= min_score:
                result = {
                    'signal': 'BUY',
                    'reason': f'BULL regime + score {total_score:.0f} >= {min_score}',
                    'min_score_required': min_score,
                    'can_enter': True,
                    'position_size_pct': int(100 * env_mult)
                }
            else:
                result = {
                    'signal': 'HOLD',
                    'reason': f'Score {total_score:.0f} below threshold {min_score} for current conviction',
                    'min_score_required': min_score,
                    'can_enter': False,
                    'position_size_pct': 0
                }
            return result

        # Fallback for UPTREND without clear regime
        if trend_state == 'UPTREND' and total_score >= 80:
            result = {
                'signal': 'BUY',
                'reason': f'UPTREND + score {total_score:.0f} >= 80',
                'min_score_required': 80,
                'can_enter': True,
                'position_size_pct': int(60 * env_mult)
            }
        else:
            result = {
                'signal': 'HOLD',
                'reason': f'Waiting for better setup (score: {total_score:.0f}, trend: {trend_state})',
                'min_score_required': 80,
                'can_enter': False,
                'position_size_pct': 0
            }

        return result
