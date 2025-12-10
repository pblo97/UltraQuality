"""
Enhanced Technical Analysis Based on Academic Evidence (2024)

Implements ONLY indicators with solid academic evidence:

**Base Indicators** (Original):
- Momentum 12M (Jegadeesh & Titman 1993, Moskowitz 2012)
- Sector Relative Strength (Bretscher 2023, Arnott 2024)
- Trend MA200 (Brock et al. 1992)
- Volume confirmation (basic)

**NEW Enhancements** (2024):
1. Market Regime Detection (Cooper 2004, Blin 2022) - Context matters
2. Multi-Timeframe Momentum (Novy-Marx 2012) - 1M, 3M, 6M, 12M
3. Risk-Adjusted Momentum (Daniel & Moskowitz 2016) - Sharpe ratio
4. Relative Strength vs Market (Blitz 2011) - vs SPY not just sector
5. Volume Profile (Lee & Swaminathan 2000) - Accumulation/Distribution

**Explicitly EXCLUDED** (no post-2010 evidence):
- RSI, MACD, Stochastic, Fibonacci, Bollinger Bands
"""

from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta
import logging
import statistics

logger = logging.getLogger(__name__)


class EnhancedTechnicalAnalyzer:
    """
    Evidence-based technical analysis with 2024 enhancements.

    **NEW Scoring System: 0-100**

    Base Components (60 pts):
    - 25 pts: Multi-Timeframe Momentum (12M, 6M, 3M, 1M consistency)
    - 15 pts: Sector Relative Strength
    - 10 pts: Market Relative Strength (vs SPY)
    - 10 pts: Trend (MA200)

    Risk Adjustments (25 pts):
    - 15 pts: Risk-Adjusted Return (Sharpe-based)
    - 10 pts: Volume Profile (accumulation/distribution)

    Market Regime Bonus/Penalty (±15 pts):
    - Bull Market: +10 pts for momentum stocks
    - Bear Market: -10 pts for momentum stocks
    - Sideways: No adjustment
    """

    # Sector to ETF mapping
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

    # Market regime thresholds
    VIX_BULL_THRESHOLD = 20
    VIX_BEAR_THRESHOLD = 30

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

    def analyze(self, symbol: str, sector: str = None, country: str = 'USA') -> Dict:
        """
        Enhanced technical analysis with 7 improvements.

        Args:
            symbol: Stock ticker (e.g., 'AAPL')
            sector: Company sector (e.g., 'Technology')
            country: Market country (default: 'USA')

        Returns:
            {
                'score': 0-100,
                'signal': 'BUY' | 'HOLD' | 'SELL',
                'market_regime': 'BULL' | 'BEAR' | 'SIDEWAYS',
                'momentum_12m': float,
                'momentum_6m': float,
                'momentum_3m': float,
                'momentum_1m': float,
                'momentum_consistency': str,
                'sharpe_12m': float,
                'trend': 'UPTREND' | 'DOWNTREND' | 'NEUTRAL',
                'sector_relative': float,
                'market_relative': float,
                'volume_profile': str ('ACCUMULATION' | 'DISTRIBUTION' | 'NEUTRAL'),
                'warnings': List[Dict],
                'components': Dict (detailed breakdown),
            }
        """
        try:
            logger.info(f"Starting enhanced technical analysis for {symbol}")

            # 1. Fetch current quote
            quote = self.fmp.get_quote(symbol)
            if not quote or len(quote) == 0:
                logger.error(f"{symbol}: No quote data available")
                return self._null_result(symbol, "No quote data available")
            q = quote[0]
            logger.debug(f"{symbol}: Quote data retrieved, price={q.get('price', 0)}")

            # 2. Fetch historical prices (for multi-timeframe & volatility)
            from_date = (datetime.now() - timedelta(days=400)).strftime('%Y-%m-%d')
            logger.debug(f"{symbol}: Fetching historical prices from {from_date}")

            hist_data = self.fmp.get_historical_prices(symbol, from_date=from_date)
            logger.debug(f"{symbol}: Historical data type={type(hist_data)}, data={str(hist_data)[:200]}...")

            if not hist_data:
                logger.error(f"{symbol}: hist_data is None or empty")
                return self._null_result(symbol, "No historical data available (null response)")

            if isinstance(hist_data, dict) and 'historical' not in hist_data:
                logger.error(f"{symbol}: hist_data dict but no 'historical' key. Keys: {list(hist_data.keys())}")
                return self._null_result(symbol, f"No historical data available (missing 'historical' key, got: {list(hist_data.keys())})")

            if isinstance(hist_data, list):
                logger.error(f"{symbol}: hist_data is a list (expected dict with 'historical' key)")
                return self._null_result(symbol, "Historical data format error (got list instead of dict)")

            prices = hist_data['historical'][::-1]  # Reverse to chronological order
            logger.info(f"{symbol}: Got {len(prices)} historical price records")

            # 3. Detect market regime (BULL/BEAR/SIDEWAYS)
            market_regime, regime_data = self._detect_market_regime()

            # 4. Calculate multi-timeframe momentum
            momentum_scores, momentum_data = self._analyze_multi_timeframe_momentum(prices)

            # 5. Calculate risk-adjusted momentum (Sharpe)
            risk_score, risk_data = self._analyze_risk_adjusted_momentum(prices)

            # 6. Analyze sector relative strength
            sector_score, sector_data = self._analyze_sector_relative(
                symbol, prices, sector, country
            )

            # 7. Analyze market relative strength (vs SPY)
            market_score, market_data = self._analyze_market_relative(prices)

            # 8. Analyze trend (MA200)
            price = q.get('price', 0)
            ma_50 = q.get('priceAvg50', 0)
            ma_200 = q.get('priceAvg200', 0)
            trend_score, trend_data = self._analyze_trend(price, ma_50, ma_200)

            # 9. Analyze volume profile (accumulation/distribution)
            volume_score, volume_data = self._analyze_volume_profile(prices)

            # 10. Apply market regime adjustment
            regime_adjustment = self._calculate_regime_adjustment(
                market_regime, momentum_data, trend_data
            )

            # 11. Calculate total score
            total_score = (
                momentum_scores +
                risk_score +
                sector_score +
                market_score +
                trend_score +
                volume_score +
                regime_adjustment
            )

            total_score = max(0, min(100, total_score))  # Clamp to 0-100

            # 12. Detect overextension risk (NEW)
            # IMPORTANT: Pass total_score to filter warnings for strong momentum leaders
            overextension_risk, overext_warnings = self._detect_overextension_risk(
                trend_data.get('distance_ma200', 0),
                risk_data.get('volatility', 0),
                momentum_data.get('1m', 0),
                momentum_data.get('6m', 0),
                technical_score=total_score  # NEW: Quality Momentum Leaders exception
            )

            # 13. Generate warnings (including overextension)
            warnings = self._generate_warnings(
                momentum_data, volume_data, sector_data, market_data, regime_data
            )
            warnings.extend(overext_warnings)  # Add overextension warnings

            # 14. Generate signal
            signal = self._generate_signal(total_score, trend_data, market_regime)

            # 15. Generate risk management recommendations (NEW)
            # Get additional data for SmartDynamicStopLoss
            week_52_high = q.get('yearHigh', 0)
            beta = q.get('beta', None)

            risk_mgmt_recs = self._generate_risk_management_recommendations(
                symbol=symbol,
                price=price,
                ma_50=ma_50,
                ma_200=ma_200,
                total_score=total_score,
                signal=signal,
                overextension_risk=overextension_risk,
                distance_ma200=trend_data.get('distance_ma200', 0),
                volatility=risk_data.get('volatility', 0),
                sharpe=risk_data.get('sharpe', 0),
                volume_profile=volume_data.get('profile', 'UNKNOWN'),
                market_regime=market_regime,
                # SmartDynamicStopLoss parameters
                prices=prices,
                week_52_high=week_52_high,
                beta=beta,
                sector=sector
            )

            return {
                'score': round(total_score, 1),
                'signal': signal,

                # Market context
                'market_regime': market_regime,
                'regime_confidence': regime_data.get('confidence', 'medium'),

                # Momentum (multi-timeframe)
                'momentum_12m': momentum_data.get('12m', 0),
                'momentum_6m': momentum_data.get('6m', 0),
                'momentum_3m': momentum_data.get('3m', 0),
                'momentum_1m': momentum_data.get('1m', 0),
                'momentum_consistency': momentum_data.get('consistency', 'N/A'),
                'momentum_status': momentum_data.get('status', 'N/A'),

                # Risk metrics
                'sharpe_12m': risk_data.get('sharpe', 0),
                'volatility_12m': risk_data.get('volatility', 0),
                'risk_adjusted_status': risk_data.get('status', 'N/A'),

                # Relative strength
                'sector_relative': sector_data.get('relative_strength', 0),
                'sector_status': sector_data.get('status', 'UNKNOWN'),
                'market_relative': market_data.get('relative_strength', 0),
                'market_status': market_data.get('status', 'N/A'),

                # Trend
                'trend': trend_data.get('status', 'UNKNOWN'),
                'distance_from_ma200': trend_data.get('distance_ma200', 0),
                'golden_cross': trend_data.get('golden_cross', False),

                # Volume
                'volume_profile': volume_data.get('profile', 'UNKNOWN'),
                'volume_trend': volume_data.get('trend', 'N/A'),
                'accumulation_ratio': volume_data.get('accumulation_ratio', 0),

                # Warnings & metadata
                'warnings': warnings,
                'timestamp': datetime.now().isoformat(),

                # Overextension risk (NEW)
                'overextension_risk': overextension_risk,
                'overextension_level': 'EXTREME' if overextension_risk >= 6 else
                                      'HIGH' if overextension_risk >= 4 else
                                      'MEDIUM' if overextension_risk >= 2 else 'LOW',

                # Risk management recommendations (NEW)
                'risk_management': risk_mgmt_recs,

                # Component scores (for transparency)
                'component_scores': {
                    'momentum': momentum_scores,
                    'risk_adjusted': risk_score,
                    'sector_relative': sector_score,
                    'market_relative': market_score,
                    'trend': trend_score,
                    'volume': volume_score,
                    'regime_adjustment': regime_adjustment,
                }
            }

        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}", exc_info=True)
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return self._null_result(symbol, f"Analysis error: {str(e)}")

    # ============================================================================
    # 1. MARKET REGIME DETECTION
    # ============================================================================

    def _detect_market_regime(self) -> Tuple[str, Dict]:
        """
        Detect current market regime: BULL, BEAR, or SIDEWAYS.

        Evidence: Cooper et al. (2004), Blin et al. (2022)
        - Momentum works +20% better in bull markets
        - In bear markets, momentum decays 60% (crowding)

        Logic (REAL-TIME):
        - BULL: SPY > MA200 AND VIX < 20
        - BEAR: SPY < MA200 AND VIX > 30
        - SIDEWAYS: Everything else

        NOTE: Para BACKTESTING, usar evaluación MENSUAL (último día del mes)
        para evitar whipsaws en cruces volátiles. Ver multi_strategy_tester.py.

        Returns:
            regime: 'BULL' | 'BEAR' | 'SIDEWAYS'
            data: {
                'spy_vs_ma200': float (%),
                'vix': float,
                'confidence': 'high' | 'medium' | 'low'
            }
        """
        # Cache for 6 hours (market regime doesn't change that fast)
        if self._market_regime_cache and self._market_regime_timestamp:
            age = datetime.now() - self._market_regime_timestamp
            if age < timedelta(hours=6):
                return self._market_regime_cache

        try:
            # Fetch SPY quote
            spy_quote = self.fmp.get_quote('SPY')
            if not spy_quote:
                return 'SIDEWAYS', {'error': 'No SPY data', 'confidence': 'low'}

            spy = spy_quote[0]
            spy_price = spy.get('price', 0)
            spy_ma200 = spy.get('priceAvg200', 0)
            spy_vs_ma = ((spy_price - spy_ma200) / spy_ma200 * 100) if spy_ma200 > 0 else 0

            # Fetch VIX quote
            vix_quote = self.fmp.get_quote('^VIX')
            vix_value = 20  # Default neutral
            if vix_quote and len(vix_quote) > 0:
                vix_value = vix_quote[0].get('price', 20)

            # Determine regime
            if spy_vs_ma > 0 and vix_value < self.VIX_BULL_THRESHOLD:
                regime = 'BULL'
                confidence = 'high' if (spy_vs_ma > 3 and vix_value < 15) else 'medium'
            elif spy_vs_ma < 0 and vix_value > self.VIX_BEAR_THRESHOLD:
                regime = 'BEAR'
                confidence = 'high' if (spy_vs_ma < -3 and vix_value > 35) else 'medium'
            else:
                regime = 'SIDEWAYS'
                confidence = 'medium'

            result = (regime, {
                'spy_vs_ma200': round(spy_vs_ma, 2),
                'vix': round(vix_value, 2),
                'confidence': confidence
            })

            # Cache result
            self._market_regime_cache = result
            self._market_regime_timestamp = datetime.now()

            return result

        except Exception as e:
            logger.warning(f"Error detecting market regime: {e}")
            return 'SIDEWAYS', {'error': str(e), 'confidence': 'low'}

    # ============================================================================
    # 2. MULTI-TIMEFRAME MOMENTUM
    # ============================================================================

    def _analyze_multi_timeframe_momentum(self, prices: List[Dict]) -> Tuple[float, Dict]:
        """
        Calculate momentum across multiple timeframes: 1M, 3M, 6M, 12M.

        Evidence: Novy-Marx (2012) - "Intermediate momentum" (6-12M) is strongest
        - 12M momentum: Long-term trend
        - 6M momentum: Intermediate (most predictive)
        - 3M momentum: Recent acceleration
        - 1M momentum: Short-term reversal detection

        Scoring (25 pts total):
        - 10 pts: 12M return
        - 8 pts: 6M return
        - 5 pts: 3M return
        - 2 pts: Consistency bonus (all aligned)

        Returns:
            score: 0-25
            data: {
                '12m': float, '6m': float, '3m': float, '1m': float,
                'consistency': 'HIGH' | 'MEDIUM' | 'LOW',
                'status': str
            }
        """
        try:
            logger.debug(f"Multi-timeframe momentum: Got {len(prices)} price records")

            if len(prices) < 250:
                logger.warning(f"Insufficient data for momentum: {len(prices)} < 250")
                return 0, {'error': f'Insufficient data ({len(prices)} < 250)', '12m': 0, '6m': 0, '3m': 0, '1m': 0, 'consistency': 'N/A', 'status': 'N/A'}

            # Get prices at specific dates
            # NOTE: Para 6M y 12M, excluimos el último mes para evitar reversión (Jegadeesh & Titman)
            current_price = prices[-1]['close']
            price_1m_ago = prices[-22]['close'] if len(prices) >= 22 else current_price  # Hace 1 mes
            price_3m = prices[-66]['close'] if len(prices) >= 66 else current_price
            price_6m = prices[-132]['close'] if len(prices) >= 132 else current_price
            price_12m = prices[-250]['close'] if len(prices) >= 250 else current_price

            # Calculate returns
            ret_1m = ((current_price - price_1m_ago) / price_1m_ago * 100) if price_1m_ago > 0 else 0  # 1 mes normal
            ret_3m = ((current_price - price_3m) / price_3m * 100) if price_3m > 0 else 0  # 3 meses normal
            # Momentum 6-1m: desde hace 6 meses hasta hace 1 mes (excluye mes actual)
            ret_6m = ((price_1m_ago - price_6m) / price_6m * 100) if price_6m > 0 else 0
            # Momentum 12-1m: desde hace 12 meses hasta hace 1 mes (excluye mes actual)
            ret_12m = ((price_1m_ago - price_12m) / price_12m * 100) if price_12m > 0 else 0

            # Score each timeframe
            score_12m = self._score_return(ret_12m, max_return=60) * 10  # 0-10 pts
            score_6m = self._score_return(ret_6m, max_return=30) * 8     # 0-8 pts
            score_3m = self._score_return(ret_3m, max_return=15) * 5     # 0-5 pts

            # Consistency bonus: All positive OR all negative (directional clarity)
            positive_count = sum([ret_12m > 0, ret_6m > 0, ret_3m > 0, ret_1m > 0])
            if positive_count == 4:
                consistency = 'HIGH'
                consistency_bonus = 2  # All bullish
            elif positive_count == 0:
                consistency = 'HIGH'
                consistency_bonus = -2  # All bearish (penalty)
            elif positive_count >= 3:
                consistency = 'MEDIUM'
                consistency_bonus = 1
            else:
                consistency = 'LOW'
                consistency_bonus = 0

            total_score = score_12m + score_6m + score_3m + consistency_bonus

            # Status
            if ret_6m > 15:
                status = 'STRONG'
            elif ret_6m > 5:
                status = 'POSITIVE'
            elif ret_6m > -5:
                status = 'NEUTRAL'
            elif ret_6m > -15:
                status = 'NEGATIVE'
            else:
                status = 'WEAK'

            return max(0, min(25, total_score)), {
                '12m': round(ret_12m, 1),
                '6m': round(ret_6m, 1),
                '3m': round(ret_3m, 1),
                '1m': round(ret_1m, 1),
                'consistency': consistency,
                'status': status
            }

        except Exception as e:
            logger.error(f"Error calculating multi-timeframe momentum: {e}", exc_info=True)
            return 0, {
                'error': str(e),
                '12m': 0,
                '6m': 0,
                '3m': 0,
                '1m': 0,
                'consistency': 'N/A',
                'status': 'ERROR'
            }

    # ============================================================================
    # 3. RISK-ADJUSTED MOMENTUM (SHARPE)
    # ============================================================================

    def _analyze_risk_adjusted_momentum(self, prices: List[Dict]) -> Tuple[float, Dict]:
        """
        Calculate risk-adjusted return (Sharpe-based momentum).

        Evidence: Daniel & Moskowitz (2016) - "Momentum Crashes"
        - High-volatility momentum is dangerous
        - Sharpe ratio predicts better than raw return
        - Risk-adjusted momentum avoids crashes

        Scoring (15 pts):
        - Sharpe > 2.0: 15 pts (excellent)
        - Sharpe 1.5-2.0: 12 pts
        - Sharpe 1.0-1.5: 9 pts
        - Sharpe 0.5-1.0: 6 pts
        - Sharpe < 0.5: 0-3 pts

        Returns:
            score: 0-15
            data: {
                'sharpe': float,
                'volatility': float (annualized %),
                'status': str
            }
        """
        try:
            if len(prices) < 250:
                return 0, {'error': 'Insufficient data'}

            # Calculate daily returns for past 12 months
            daily_returns = []
            for i in range(len(prices) - 250, len(prices) - 1):
                ret = (prices[i + 1]['close'] - prices[i]['close']) / prices[i]['close']
                daily_returns.append(ret)

            # Calculate metrics
            mean_return = statistics.mean(daily_returns)
            volatility = statistics.stdev(daily_returns)

            # Annualize
            annual_return = mean_return * 252 * 100  # to %
            annual_volatility = volatility * (252 ** 0.5) * 100  # to %

            # Sharpe ratio (assuming 0% risk-free rate for simplicity)
            sharpe = (mean_return / volatility) * (252 ** 0.5) if volatility > 0 else 0

            # Score based on Sharpe
            if sharpe >= 2.0:
                score = 15
                status = 'EXCELLENT'
            elif sharpe >= 1.5:
                score = 12
                status = 'GOOD'
            elif sharpe >= 1.0:
                score = 9
                status = 'MODERATE'
            elif sharpe >= 0.5:
                score = 6
                status = 'WEAK'
            elif sharpe >= 0:
                score = 3
                status = 'POOR'
            else:
                score = 0
                status = 'NEGATIVE'

            return score, {
                'sharpe': round(sharpe, 2),
                'volatility': round(annual_volatility, 1),
                'annualized_return': round(annual_return, 1),
                'status': status
            }

        except Exception as e:
            logger.error(f"Error calculating risk-adjusted momentum: {e}", exc_info=True)
            return 0, {
                'error': str(e),
                'sharpe': 0,
                'volatility': 0,
                'annualized_return': 0,
                'status': 'ERROR'
            }

    # ============================================================================
    # 4. SECTOR RELATIVE STRENGTH
    # ============================================================================

    def _analyze_sector_relative(
        self, symbol: str, prices: List[Dict], sector: str, country: str
    ) -> Tuple[float, Dict]:
        """
        Analyze sector relative strength.

        Evidence: Bretscher et al. (2023) - Sector momentum = 60% of total momentum

        Scoring (15 pts):
        - 10 pts: Sector absolute performance (6M)
        - 5 pts: Stock vs sector outperformance

        Returns:
            score: 0-15
            data: {...}
        """
        try:
            if not sector or country != 'USA':
                return 0, {'status': 'UNKNOWN', 'relative_strength': 0}

            sector_etf = self.SECTOR_ETFS.get(sector)
            if not sector_etf:
                return 0, {'status': 'UNKNOWN', 'sector': sector}

            # Get stock 6M return
            if len(prices) < 132:
                return 0, {'error': 'Insufficient data'}

            stock_current = prices[-1]['close']
            stock_6m_ago = prices[-132]['close']
            stock_ret_6m = ((stock_current - stock_6m_ago) / stock_6m_ago * 100) if stock_6m_ago > 0 else 0

            # Get sector ETF 6M return
            from_date = (datetime.now() - timedelta(days=200)).strftime('%Y-%m-%d')
            sector_hist = self.fmp.get_historical_prices(sector_etf, from_date=from_date)

            if not sector_hist or 'historical' not in sector_hist:
                return 0, {'error': 'No sector data'}

            sector_prices = sector_hist['historical'][::-1]
            if len(sector_prices) < 132:
                return 0, {'error': 'Insufficient sector data'}

            sector_current = sector_prices[-1]['close']
            sector_6m_ago = sector_prices[-132]['close']
            sector_ret_6m = ((sector_current - sector_6m_ago) / sector_6m_ago * 100) if sector_6m_ago > 0 else 0

            # Calculate relative strength
            relative_strength = stock_ret_6m - sector_ret_6m

            # Score sector absolute (0-10 pts)
            sector_score = self._score_return(sector_ret_6m, max_return=20) * 10

            # Score relative outperformance (0-5 pts)
            relative_score = self._score_return(relative_strength, max_return=10) * 5

            total_score = sector_score + relative_score

            # Status
            if sector_ret_6m > 10:
                status = 'HOT'
            elif sector_ret_6m > 0:
                status = 'GOOD'
            elif sector_ret_6m > -10:
                status = 'NEUTRAL'
            else:
                status = 'COLD'

            return max(0, min(15, total_score)), {
                'sector_return_6m': round(sector_ret_6m, 1),
                'stock_return_6m': round(stock_ret_6m, 1),
                'relative_strength': round(relative_strength, 1),
                'sector_etf': sector_etf,
                'status': status
            }

        except Exception as e:
            logger.error(f"Error analyzing sector relative: {e}", exc_info=True)
            return 0, {
                'error': str(e),
                'sector_return_6m': 0,
                'stock_return_6m': 0,
                'relative_strength': 0,
                'sector_etf': 'N/A',
                'status': 'ERROR'
            }

    # ============================================================================
    # 5. MARKET RELATIVE STRENGTH (vs SPY)
    # ============================================================================

    def _analyze_market_relative(self, prices: List[Dict]) -> Tuple[float, Dict]:
        """
        Analyze relative strength vs market (SPY).

        Evidence: Blitz et al. (2011) - Market-relative momentum

        Scoring (10 pts):
        - Outperform SPY by >10% in 6M: 10 pts
        - Outperform SPY by 0-10%: 5-10 pts
        - Underperform SPY: 0-5 pts

        Returns:
            score: 0-10
            data: {...}
        """
        try:
            if len(prices) < 132:
                return 0, {'error': 'Insufficient data'}

            # Get stock 6M return
            stock_current = prices[-1]['close']
            stock_6m_ago = prices[-132]['close']
            stock_ret_6m = ((stock_current - stock_6m_ago) / stock_6m_ago * 100) if stock_6m_ago > 0 else 0

            # Get SPY 6M return
            from_date = (datetime.now() - timedelta(days=200)).strftime('%Y-%m-%d')
            spy_hist = self.fmp.get_historical_prices('SPY', from_date=from_date)

            if not spy_hist or 'historical' not in spy_hist:
                return 0, {'error': 'No SPY data'}

            spy_prices = spy_hist['historical'][::-1]
            if len(spy_prices) < 132:
                return 0, {'error': 'Insufficient SPY data'}

            spy_current = spy_prices[-1]['close']
            spy_6m_ago = spy_prices[-132]['close']
            spy_ret_6m = ((spy_current - spy_6m_ago) / spy_6m_ago * 100) if spy_6m_ago > 0 else 0

            # Calculate relative strength
            relative_strength = stock_ret_6m - spy_ret_6m

            # Score (0-10 pts)
            score = self._score_return(relative_strength, max_return=20) * 10

            # Status
            if relative_strength > 10:
                status = 'OUTPERFORMER'
            elif relative_strength > 0:
                status = 'BEATING_MARKET'
            elif relative_strength > -10:
                status = 'INLINE'
            else:
                status = 'UNDERPERFORMER'

            return max(0, min(10, score)), {
                'market_return_6m': round(spy_ret_6m, 1),
                'stock_return_6m': round(stock_ret_6m, 1),
                'relative_strength': round(relative_strength, 1),
                'status': status
            }

        except Exception as e:
            logger.error(f"Error analyzing market relative: {e}", exc_info=True)
            return 0, {
                'error': str(e),
                'market_return_6m': 0,
                'stock_return_6m': 0,
                'relative_strength': 0,
                'status': 'ERROR'
            }

    # ============================================================================
    # 6. TREND ANALYSIS (MA200)
    # ============================================================================

    def _analyze_trend(self, price: float, ma_50: float, ma_200: float) -> Tuple[float, Dict]:
        """
        Analyze trend using moving averages.

        Evidence: Brock et al. (1992) - MA200 cross predictive

        Scoring (10 pts):
        - Price > MA200 + Golden Cross: 10 pts
        - Price > MA200: 7 pts
        - Price < MA200: 0-3 pts

        Returns:
            score: 0-10
            data: {...}
        """
        if price == 0 or ma_200 == 0:
            return 0, {'status': 'UNKNOWN', 'distance_ma200': 0, 'golden_cross': False}

        distance_ma200 = ((price - ma_200) / ma_200 * 100)
        golden_cross = ma_50 > ma_200 if (ma_50 > 0 and ma_200 > 0) else False

        if price > ma_200:
            if golden_cross:
                score = 10
                status = 'UPTREND'
            else:
                score = 7
                status = 'UPTREND'
        else:
            # Below MA200
            score = max(0, 5 + distance_ma200 / 5)  # Penalty for distance below
            status = 'DOWNTREND'

        return score, {
            'status': status,
            'distance_ma200': round(distance_ma200, 1),
            'golden_cross': golden_cross
        }

    # ============================================================================
    # 7. VOLUME PROFILE (ACCUMULATION/DISTRIBUTION)
    # ============================================================================

    def _analyze_volume_profile(self, prices: List[Dict]) -> Tuple[float, Dict]:
        """
        Analyze volume profile to detect accumulation/distribution.

        Evidence: Lee & Swaminathan (2000) - Volume momentum interaction

        Metrics:
        - Volume on up days vs down days
        - Volume trend (increasing/decreasing)

        Scoring (10 pts):
        - Accumulation (vol on up days > down days): 7-10 pts
        - Neutral: 4-6 pts
        - Distribution (vol on down days > up days): 0-3 pts

        Returns:
            score: 0-10
            data: {...}
        """
        try:
            if len(prices) < 66:  # Need 3 months
                return 0, {'error': 'Insufficient data'}

            # Analyze last 3 months
            recent_prices = prices[-66:]

            vol_on_up_days = 0
            vol_on_down_days = 0

            for i in range(1, len(recent_prices)):
                price_change = recent_prices[i]['close'] - recent_prices[i - 1]['close']
                volume = recent_prices[i].get('volume', 0)

                if price_change > 0:
                    vol_on_up_days += volume
                elif price_change < 0:
                    vol_on_down_days += volume

            # Calculate accumulation ratio
            total_vol = vol_on_up_days + vol_on_down_days
            accumulation_ratio = (vol_on_up_days / total_vol) if total_vol > 0 else 0.5

            # Determine profile
            if accumulation_ratio > 0.55:
                profile = 'ACCUMULATION'
                score = 7 + (accumulation_ratio - 0.55) * 20  # 7-10 pts
            elif accumulation_ratio > 0.45:
                profile = 'NEUTRAL'
                score = 4 + (accumulation_ratio - 0.45) * 20  # 4-6 pts
            else:
                profile = 'DISTRIBUTION'
                score = accumulation_ratio * 8  # 0-3 pts

            # Volume trend
            recent_vol = sum(p.get('volume', 0) for p in prices[-22:]) / 22
            older_vol = sum(p.get('volume', 0) for p in prices[-66:-44]) / 22
            volume_trend = 'INCREASING' if recent_vol > older_vol * 1.1 else \
                          'DECREASING' if recent_vol < older_vol * 0.9 else 'STABLE'

            return max(0, min(10, score)), {
                'profile': profile,
                'accumulation_ratio': round(accumulation_ratio, 2),
                'volume_trend': volume_trend,
                'vol_up_days': vol_on_up_days,
                'vol_down_days': vol_on_down_days
            }

        except Exception as e:
            logger.error(f"Error analyzing volume profile: {e}", exc_info=True)
            return 0, {
                'error': str(e),
                'profile': 'ERROR',
                'accumulation_ratio': 0,
                'volume_trend': 'N/A',
                'vol_up_days': 0,
                'vol_down_days': 0
            }

    # ============================================================================
    # REGIME ADJUSTMENT
    # ============================================================================

    def _calculate_regime_adjustment(
        self, regime: str, momentum_data: Dict, trend_data: Dict
    ) -> float:
        """
        Adjust score based on market regime.

        Evidence: Cooper et al. (2004), Blin et al. (2022)
        - Momentum 20% more effective in bull markets
        - Momentum 60% less effective in bear markets

        Adjustments:
        - BULL + positive momentum: +10 pts
        - BULL + negative momentum: 0 pts
        - BEAR + positive momentum: -10 pts (fade the rally)
        - BEAR + negative momentum: 0 pts
        - SIDEWAYS: No adjustment

        Returns:
            adjustment: -10 to +10 pts
        """
        if regime == 'SIDEWAYS':
            return 0

        # Check if momentum is positive
        momentum_positive = momentum_data.get('6m', 0) > 0

        if regime == 'BULL':
            if momentum_positive and trend_data.get('status') == 'UPTREND':
                return 10  # Bull + momentum = strong
            else:
                return 0

        elif regime == 'BEAR':
            if momentum_positive:
                return -10  # Bear market rally = trap
            else:
                return 0  # Bear + negative momentum = normal

        return 0

    # ============================================================================
    # WARNINGS
    # ============================================================================

    def _generate_warnings(
        self,
        momentum_data: Dict,
        volume_data: Dict,
        sector_data: Dict,
        market_data: Dict,
        regime_data: Dict
    ) -> List[Dict]:
        """
        Generate warnings based on analysis.

        Returns:
            List of {'type': 'HIGH'|'MEDIUM'|'LOW', 'message': str}
        """
        warnings = []

        # Momentum inconsistency
        if momentum_data.get('consistency') == 'LOW':
            warnings.append({
                'type': 'MEDIUM',
                'message': f"Momentum inconsistency: 1M={momentum_data.get('1m')}%, 12M={momentum_data.get('12m')}%"
            })

        # Distribution warning
        if volume_data.get('profile') == 'DISTRIBUTION':
            warnings.append({
                'type': 'HIGH',
                'message': f"Volume distribution detected (ratio={volume_data.get('accumulation_ratio')})"
            })

        # Cold sector warning
        if sector_data.get('status') == 'COLD':
            warnings.append({
                'type': 'MEDIUM',
                'message': f"Cold sector: {sector_data.get('sector_etf')} down {sector_data.get('sector_return_6m')}% in 6M"
            })

        # Market underperformance
        if market_data.get('status') == 'UNDERPERFORMER':
            warnings.append({
                'type': 'LOW',
                'message': f"Underperforming market by {abs(market_data.get('relative_strength'))}%"
            })

        # Bear market warning
        if regime_data.get('confidence') != 'low':
            spy_vs_ma = regime_data.get('spy_vs_ma200', 0)
            vix = regime_data.get('vix', 20)
            if spy_vs_ma < -5 or vix > 30:
                warnings.append({
                    'type': 'HIGH',
                    'message': f"Bear market conditions: SPY {spy_vs_ma:.1f}% vs MA200, VIX {vix:.1f}"
                })

        return warnings

    # ============================================================================
    # SIGNAL GENERATION
    # ============================================================================

    def _generate_signal(self, score: float, trend_data: Dict, regime: str) -> str:
        """
        Generate BUY/HOLD/SELL signal.

        Rules:
        - BUY: score >= 75 AND uptrend
        - HOLD: score 50-75 OR mixed signals
        - SELL: score < 50

        Returns:
            'BUY' | 'HOLD' | 'SELL'
        """
        is_uptrend = trend_data.get('status') == 'UPTREND'

        if score >= 75 and is_uptrend:
            return 'BUY'
        elif score >= 50:
            return 'HOLD'
        else:
            return 'SELL'

    # ============================================================================
    # OVEREXTENSION RISK DETECTION (NEW)
    # ============================================================================

    def _detect_overextension_risk(
        self,
        distance_ma200: float,
        volatility: float,
        momentum_1m: float,
        momentum_6m: float,
        technical_score: float = 0
    ) -> Tuple[int, List[Dict]]:
        """
        Detect overextension risk based on distance from MA200, volatility, and momentum.

        Evidence:
        - George & Hwang (2004) - 52-week high proximity increases near-term reversal risk
        - Daniel & Moskowitz (2016) - High-volatility momentum prone to crashes
        - De Bondt & Thaler (1985) - Extreme price movements tend to revert

        NEW EXCEPTION: Quality Momentum Leaders (technical_score > 80)
        - Overextension is a FEATURE not a BUG for strong momentum
        - Filter warnings to avoid missing big winners
        - Academia: "Let your winners run" (Jegadeesh & Titman)

        Risk scoring (0-7 scale):
        - 0-1: LOW risk
        - 2-4: MEDIUM risk
        - 5-6: HIGH risk
        - 7+: EXTREME risk

        Returns:
            risk_score: 0-7
            warnings: List of warning dicts
        """
        risk_score = 0
        warnings = []

        # QUALITY MOMENTUM LEADER EXCEPTION
        # If technical score > 80 (strong momentum + trend + relative strength)
        # Filter or soften warnings - overextension is strength, not weakness
        is_momentum_leader = technical_score > 80

        # 1. Distance from MA200 (most important)
        abs_distance = abs(distance_ma200)

        if abs_distance > 60:
            if is_momentum_leader:
                # Momentum leaders can sustain >60% - use trailing stop instead
                risk_score += 1  # Reduced from 4
                warnings.append({
                    'type': 'LOW',
                    'message': f'Strong momentum: {distance_ma200:+.1f}% from MA200. Quality Leader - Use Trailing Stop (EMA 20) instead of exiting.'
                })
            else:
                risk_score += 4
                warnings.append({
                    'type': 'HIGH',
                    'message': f'EXTREME overextension: {distance_ma200:+.1f}% from MA200 (>60%). High probability of 20-40% pullback.'
                })
        elif abs_distance > 50:
            if is_momentum_leader:
                risk_score += 1  # Reduced from 3
                warnings.append({
                    'type': 'LOW',
                    'message': f'Extended momentum: {distance_ma200:+.1f}% from MA200. Strong trend - Hold with trailing stop.'
                })
            else:
                risk_score += 3
                warnings.append({
                    'type': 'HIGH',
                    'message': f'Severe overextension: {distance_ma200:+.1f}% from MA200 (>50%). Expect 15-30% correction soon.'
                })
        elif abs_distance > 40:
            if not is_momentum_leader:
                # Only warn for non-leaders
                risk_score += 2
                warnings.append({
                    'type': 'MEDIUM',
                    'message': f'Significant overextension: {distance_ma200:+.1f}% from MA200 (>40%). Possible 10-20% pullback.'
                })
        elif abs_distance > 30:
            if not is_momentum_leader:
                # Only warn for non-leaders
                risk_score += 1
                warnings.append({
                    'type': 'LOW',
                    'message': f'Moderate overextension: {distance_ma200:+.1f}% from MA200 (>30%). Monitor for reversal signals.'
                })

        # 2. Volatility + Recent momentum (parabolic move detection)
        if volatility > 40 and momentum_1m > 15:
            risk_score += 2
            warnings.append({
                'type': 'HIGH',
                'message': f'Parabolic move detected: +{momentum_1m:.1f}% in 1M with {volatility:.1f}% volatility. Crash risk elevated (Daniel & Moskowitz 2016).'
            })
        elif volatility > 35 and momentum_1m > 10:
            risk_score += 1
            warnings.append({
                'type': 'MEDIUM',
                'message': f'High volatility momentum: +{momentum_1m:.1f}% in 1M with {volatility:.1f}% vol. Risk of sharp reversal.'
            })

        # 3. Extreme momentum (blow-off top detection)
        if momentum_1m > 25:
            risk_score += 1
            warnings.append({
                'type': 'HIGH',
                'message': f'Blow-off top signal: +{momentum_1m:.1f}% in just 1 month. Likely unsustainable.'
            })

        # 4. Exhaustion check (strong 6M but weak 1M = losing steam)
        if momentum_6m > 30 and momentum_1m < 0:
            warnings.append({
                'type': 'MEDIUM',
                'message': f'Momentum exhaustion: Strong 6M (+{momentum_6m:.1f}%) but negative 1M ({momentum_1m:+.1f}%). Trend may be weakening.'
            })

        return risk_score, warnings

    # ============================================================================
    # RISK MANAGEMENT RECOMMENDATIONS (NEW)
    # ============================================================================

    def _generate_risk_management_recommendations(
        self,
        symbol: str,
        price: float,
        ma_50: float,
        ma_200: float,
        total_score: float,
        signal: str,
        overextension_risk: int,
        distance_ma200: float,
        volatility: float,
        sharpe: float,
        volume_profile: str,
        market_regime: str,
        # SmartDynamicStopLoss parameters
        prices: List[Dict] = None,
        week_52_high: float = 0,
        beta: float = None,
        sector: str = None
    ) -> Dict:
        """
        Generate comprehensive risk management and options strategies recommendations.

        Evidence:
        - Black & Scholes (1973) - Options pricing foundations
        - Whaley (2002) - Covered call vs buy-write
        - Shastri & Tandon (1986) - Protective put effectiveness
        - McIntyre & Jackson (2007) - Collar strategy performance

        Returns:
            {
                'position_sizing': {...},
                'entry_strategy': {...},
                'stop_loss': {...},
                'profit_taking': {...},
                'options_strategies': [...]
            }
        """
        recommendations = {}

        # ========== 1. POSITION SIZING ==========
        recommendations['position_sizing'] = self._generate_position_sizing(
            signal, overextension_risk, sharpe, volatility, market_regime
        )

        # ========== 2. ENTRY STRATEGY ==========
        recommendations['entry_strategy'] = self._generate_entry_strategy(
            signal, overextension_risk, distance_ma200, price, ma_50, ma_200
        )

        # ========== 3. STOP LOSS (SmartDynamicStopLoss) ==========
        if prices and len(prices) > 0:
            # Use SmartDynamicStopLoss (advanced adaptive system)
            recommendations['stop_loss'] = self._generate_smart_stop_loss(
                prices=prices,
                current_price=price,
                ma_50=ma_50,
                ma_200=ma_200,
                volatility=volatility,
                week_52_high=week_52_high,
                beta=beta,
                sector=sector,
                # Lifecycle parameters (not available in initial analysis, set to None)
                entry_price=None,
                days_in_position=0,
                current_return_pct=0,
                rsi=None
            )
        else:
            # Fallback to legacy method if no price data
            recommendations['stop_loss'] = self._generate_stop_loss(
                price, ma_50, ma_200, volatility, distance_ma200
            )

        # ========== 4. PROFIT TAKING ==========
        recommendations['profit_taking'] = self._generate_profit_targets(
            signal, distance_ma200, overextension_risk, ma_200, price
        )

        # ========== 5. OPTIONS STRATEGIES ==========
        recommendations['options_strategies'] = self._generate_options_strategies(
            signal, overextension_risk, volatility, distance_ma200, volume_profile,
            price, sharpe, market_regime
        )

        return recommendations

    def _generate_position_sizing(self, signal, overextension_risk, sharpe, volatility, market_regime):
        """Position sizing based on risk and quality."""
        if signal == 'BUY' and overextension_risk <= 1 and sharpe > 1.5:
            return {
                'recommended_size': '100%',
                'rationale': 'Full position - Strong technical + low overextension + excellent risk-adjusted returns',
                'max_portfolio_weight': '10-15%'
            }
        elif signal == 'BUY' and overextension_risk >= 3:
            return {
                'recommended_size': '50-70%',
                'rationale': f'Reduced position - Overextension risk {overextension_risk}/7. Reserve capital for pullback entry',
                'max_portfolio_weight': '5-8%'
            }
        elif signal == 'BUY':
            return {
                'recommended_size': '75-100%',
                'rationale': 'Standard position - Moderate risk/reward profile',
                'max_portfolio_weight': '8-12%'
            }
        elif signal == 'HOLD':
            return {
                'recommended_size': '50%',
                'rationale': 'Half position - Wait for clearer signal or better entry',
                'max_portfolio_weight': '5-7%'
            }
        else:  # SELL
            return {
                'recommended_size': '0%',
                'rationale': 'No position - Technical setup unfavorable',
                'max_portfolio_weight': '0%'
            }

    def _generate_entry_strategy(self, signal, overextension_risk, distance_ma200, price, ma_50, ma_200):
        """Entry strategy recommendations."""
        if signal == 'SELL':
            return {
                'strategy': 'NO ENTRY',
                'rationale': 'Wait for technical improvement'
            }

        # Determine expected pullback based on distance from MA200 (consistent with warnings)
        abs_distance = abs(distance_ma200)

        if abs_distance > 60:
            # EXTREME: >60% from MA200 → expect 20-40% correction
            return {
                'strategy': 'SCALE-IN (3 tranches)',
                'tranche_1': f'20% NOW at ${price:.2f} (minimal momentum entry)',
                'tranche_2': f'30% on 20% pullback to ${price*0.80:.2f}',
                'tranche_3': f'50% on 30% pullback to ${price*0.70:.2f}',
                'rationale': f'EXTREME overextension ({distance_ma200:+.1f}% from MA200) - expect 20-40% correction. Most capital reserved for deep pullback.'
            }
        elif abs_distance > 50:
            # SEVERE: >50% from MA200 → expect 15-30% correction
            pullback_15pct = price * 0.85
            pullback_25pct = price * 0.75
            return {
                'strategy': 'SCALE-IN (2 tranches)',
                'tranche_1': f'40% NOW at ${price:.2f}',
                'tranche_2': f'60% on 15-25% pullback to ${pullback_25pct:.2f}-${pullback_15pct:.2f}',
                'rationale': f'Severe overextension ({distance_ma200:+.1f}% from MA200) - expect 15-30% correction. Reserve majority for pullback.'
            }
        elif abs_distance > 40:
            # SIGNIFICANT: >40% from MA200 → expect 10-20% pullback
            pullback_10pct = price * 0.90
            pullback_15pct = price * 0.85
            return {
                'strategy': 'SCALE-IN (2 tranches)',
                'tranche_1': f'60% NOW at ${price:.2f}',
                'tranche_2': f'40% on 10-15% pullback to ${pullback_15pct:.2f}-${pullback_10pct:.2f}',
                'rationale': f'Significant overextension ({distance_ma200:+.1f}% from MA200) - possible 10-20% pullback. Reserve capital for likely dip.'
            }
        elif overextension_risk >= 3:
            # Moderate overextension based on other factors (volatility, momentum)
            pullback_8pct = price * 0.92
            pullback_12pct = price * 0.88
            return {
                'strategy': 'SCALE-IN (2 tranches)',
                'tranche_1': f'70% NOW at ${price:.2f}',
                'tranche_2': f'30% on 8-12% pullback to ${pullback_12pct:.2f}-${pullback_8pct:.2f}',
                'rationale': f'Moderate overextension risk ({overextension_risk}/7). Small reserve for potential consolidation.'
            }
        else:
            # Low overextension - full entry acceptable
            return {
                'strategy': 'FULL ENTRY NOW',
                'entry_price': f'${price:.2f}',
                'rationale': f'Low overextension risk ({overextension_risk}/7). Technical setup favorable for immediate entry.'
            }

    # ============================================================================
    # SMART DYNAMIC STOP LOSS - Parameter Calculation Methods
    # ============================================================================

    def _calculate_atr_14(self, prices: List[Dict]) -> float:
        """
        Calculate 14-day Average True Range (ATR).

        ATR = Average of True Range over 14 periods
        True Range = max(High - Low, |High - Previous Close|, |Low - Previous Close|)

        Args:
            prices: List of historical price dicts with 'high', 'low', 'close'

        Returns:
            ATR value (float)
        """
        try:
            if len(prices) < 15:
                # Fallback: approximate ATR from volatility
                return 0

            true_ranges = []
            for i in range(1, min(15, len(prices))):
                high = prices[-i]['high']
                low = prices[-i]['low']
                prev_close = prices[-(i+1)]['close']

                tr = max(
                    high - low,
                    abs(high - prev_close),
                    abs(low - prev_close)
                )
                true_ranges.append(tr)

            return statistics.mean(true_ranges) if true_ranges else 0

        except Exception as e:
            logger.warning(f"Error calculating ATR: {e}")
            return 0

    def _calculate_highest_high_22(self, prices: List[Dict]) -> float:
        """
        Calculate highest high in last 22 trading days (approximately 1 month).

        Args:
            prices: List of historical price dicts

        Returns:
            Highest high price (float)
        """
        try:
            if len(prices) < 22:
                return prices[-1]['high'] if prices else 0

            recent_prices = prices[-22:]
            return max(p['high'] for p in recent_prices)

        except Exception as e:
            logger.warning(f"Error calculating highest high: {e}")
            return 0

    def _calculate_swing_low_10(self, prices: List[Dict]) -> float:
        """
        Calculate swing low (lowest low) in last 10 trading days.

        Args:
            prices: List of historical price dicts

        Returns:
            Lowest low price (float)
        """
        try:
            if len(prices) < 10:
                return prices[-1]['low'] if prices else 0

            recent_prices = prices[-10:]
            return min(p['low'] for p in recent_prices)

        except Exception as e:
            logger.warning(f"Error calculating swing low 10: {e}")
            return 0

    def _calculate_swing_low_20(self, prices: List[Dict]) -> float:
        """
        Calculate swing low (lowest low) in last 20 trading days.
        More robust than 10-day for avoiding stop hunting.

        Args:
            prices: List of historical price dicts

        Returns:
            Lowest low price (float)
        """
        try:
            if len(prices) < 20:
                return prices[-1]['low'] if prices else 0

            recent_prices = prices[-20:]
            return min(p['low'] for p in recent_prices)

        except Exception as e:
            logger.warning(f"Error calculating swing low 20: {e}")
            return 0

    def _calculate_ema_10(self, prices: List[Dict]) -> float:
        """
        Calculate 10-day Exponential Moving Average.
        Faster than EMA 20, used for climax stops.

        EMA formula: EMA_today = Price_today * k + EMA_yesterday * (1-k)
        where k = 2 / (N + 1)

        Args:
            prices: List of historical price dicts

        Returns:
            EMA 10 value (float)
        """
        try:
            if len(prices) < 10:
                return 0

            period = 10
            k = 2 / (period + 1)

            # Start with SMA for first EMA value
            ema = statistics.mean(p['close'] for p in prices[-20:-10]) if len(prices) >= 20 else prices[-10]['close']

            # Calculate EMA for last 10 days
            for i in range(-10, 0):
                ema = prices[i]['close'] * k + ema * (1 - k)

            return ema

        except Exception as e:
            logger.warning(f"Error calculating EMA 10: {e}")
            return 0

    def _calculate_ema_20(self, prices: List[Dict]) -> float:
        """
        Calculate 20-day Exponential Moving Average.

        EMA formula: EMA_today = Price_today * k + EMA_yesterday * (1-k)
        where k = 2 / (N + 1)

        Args:
            prices: List of historical price dicts

        Returns:
            EMA 20 value (float)
        """
        try:
            if len(prices) < 20:
                return 0

            # Get last 20+ prices for accurate calculation
            period = 20
            k = 2 / (period + 1)

            # Start with SMA for first EMA value
            ema = statistics.mean(p['close'] for p in prices[-40:-20]) if len(prices) >= 40 else prices[-20]['close']

            # Calculate EMA for last 20 days
            for i in range(-20, 0):
                ema = prices[i]['close'] * k + ema * (1 - k)

            return ema

        except Exception as e:
            logger.warning(f"Error calculating EMA 20: {e}")
            return 0

    def _check_ath_proximity(self, current_price: float, week_52_high: float) -> bool:
        """
        Check if current price is within 2% of All-Time High (52-week high).

        Args:
            current_price: Current stock price
            week_52_high: 52-week high price

        Returns:
            True if price >= 0.98 * 52_week_high
        """
        if week_52_high == 0:
            return False
        return current_price >= 0.98 * week_52_high

    def _classify_risk_tier(
        self,
        volatility: float,
        beta: float = None,
        sector: str = None
    ) -> Tuple[int, str, Dict]:
        """
        Classify asset into Risk Tier based on behavioral characteristics.

        Tiers:
        - Tier 1 (Defensivo 🐢): Low volatility, stable companies (e.g., Cisco, utilities)
        - Tier 2 (Core Growth 🏃): Moderate volatility, balanced growth (e.g., Google, Apple)
        - Tier 3 (Especulativo 🚀): High volatility, high beta (e.g., Nvidia, crypto)

        Classification Logic (Priority Order):
        1. If Beta available: Use Beta + Volatility Matrix
        2. Else: Use Volatility + Sector heuristics

        Args:
            volatility: Annualized volatility (%)
            beta: Stock beta (optional, preferred)
            sector: Stock sector (fallback)

        Returns:
            (tier_number, tier_name, tier_config)
        """
        # Tier configurations
        TIER_1_CONFIG = {
            'name': 'Tier 1: Defensivo 🐢',
            'initial_multiplier': 1.8,
            'trailing_multiplier': 2.0,
            'hard_cap_pct': 8.0,
            'anchor': 'SMA 50',
            'description': 'Low volatility, stable companies'
        }

        TIER_2_CONFIG = {
            'name': 'Tier 2: Core Growth 🏃',
            'initial_multiplier': 2.5,
            'trailing_multiplier': 3.0,
            'hard_cap_pct': 15.0,
            'anchor': 'Swing Low 10d',
            'description': 'Moderate volatility, balanced growth'
        }

        TIER_3_CONFIG = {
            'name': 'Tier 3: Especulativo 🚀',
            'initial_multiplier': 3.0,
            'trailing_multiplier': 3.5,
            'hard_cap_pct': 25.0,
            'anchor': 'EMA 20',
            'description': 'High volatility, high momentum'
        }

        # Classification logic
        if beta is not None:
            # Use Beta + Volatility Matrix (preferred)
            if beta < 0.95 and volatility < 25:
                return 1, TIER_1_CONFIG['name'], TIER_1_CONFIG
            elif beta > 1.15 or volatility > 45:
                return 3, TIER_3_CONFIG['name'], TIER_3_CONFIG
            else:
                return 2, TIER_2_CONFIG['name'], TIER_2_CONFIG
        else:
            # Fallback: Use Volatility only
            if volatility < 25:
                tier = 1
                config = TIER_1_CONFIG
            elif volatility > 45:
                tier = 3
                config = TIER_3_CONFIG
            else:
                tier = 2
                config = TIER_2_CONFIG

            # Sector adjustments (heuristic)
            defensive_sectors = ['Utilities', 'Consumer Defensive', 'Consumer Staples']
            speculative_sectors = ['Technology', 'Communication Services', 'Energy']

            if sector in defensive_sectors and tier > 1:
                tier = 1
                config = TIER_1_CONFIG
            elif sector in speculative_sectors and tier < 3 and volatility > 35:
                tier = 3
                config = TIER_3_CONFIG

            return tier, config['name'], config

    def _generate_stop_loss(self, price, ma_50, ma_200, volatility, distance_ma200):
        """
        LEGACY stop loss method - kept for backward compatibility.

        NEW: Use _generate_smart_stop_loss for SmartDynamicStopLoss implementation.
        This method provides simple 3-tier stops based on volatility and MAs.
        """
        # Dynamic stop based on volatility (Wilder's ATR concept)
        # Rule of thumb: 2x volatility for stop distance
        volatility_stop_pct = min(volatility / 252**0.5 * 2, 15)  # Max 15%

        stops = {
            'aggressive': {
                'level': f'${ma_50:.2f}',
                'distance': f'{((ma_50-price)/price*100):+.1f}%',
                'rationale': 'Trailing stop under MA50. Tight but may get whipsawed in volatile markets.'
            },
            'moderate': {
                'level': f'${price * (1 - volatility_stop_pct/100):.2f}',
                'distance': f'-{volatility_stop_pct:.1f}%',
                'rationale': f'Volatility-based stop (2x daily vol). Accounts for {volatility:.1f}% annualized volatility.'
            },
            'conservative': {
                'level': f'${ma_200:.2f}',
                'distance': f'{((ma_200-price)/price*100):+.1f}%',
                'rationale': 'Trailing stop under MA200. Wide stop, preserves position through normal volatility.'
            }
        }

        # Recommended stop based on profile
        if distance_ma200 > 40:
            recommended = 'aggressive'
        elif volatility > 35:
            recommended = 'moderate'
        else:
            recommended = 'conservative'

        return {
            'recommended': recommended,
            'stops': stops,
            'note': 'Use trailing stops - adjust as price moves in your favor. Never move stop against you.'
        }

    def _generate_smart_stop_loss(
        self,
        prices: List[Dict],
        current_price: float,
        ma_50: float,
        ma_200: float,
        volatility: float,
        week_52_high: float,
        beta: float = None,
        sector: str = None,
        # Lifecycle parameters (optional - for position management)
        entry_price: float = None,
        days_in_position: int = 0,
        current_return_pct: float = 0,
        rsi: float = None
    ) -> Dict:
        """
        SmartDynamicStopLoss - Advanced adaptive stop loss system.

        Features:
        1. Risk Tier Classification (Defensivo, Core Growth, Especulativo)
        2. ATR-based dynamic stops with tier-specific multipliers
        3. Lifecycle management (Entry, Breakeven, Profit Locking, Zombie Killer)
        4. Technical anchors (SMA 50, Swing Low, EMA 20)

        Args:
            prices: Historical price data
            current_price: Current stock price
            ma_50: 50-day moving average
            ma_200: 200-day moving average
            volatility: Annualized volatility (%)
            week_52_high: 52-week high for ATH check
            beta: Stock beta (optional but recommended)
            sector: Stock sector (for tier classification)
            entry_price: Entry price (for lifecycle management)
            days_in_position: Days holding position
            current_return_pct: Current return %
            rsi: RSI indicator (for profit locking phase)

        Returns:
            Dict with stop loss recommendations and lifecycle phase
        """
        try:
            # ========== STEP 1: Calculate Base Parameters ==========
            atr_14 = self._calculate_atr_14(prices)
            highest_high_22 = self._calculate_highest_high_22(prices)
            swing_low_10 = self._calculate_swing_low_10(prices)
            swing_low_20 = self._calculate_swing_low_20(prices)  # Option D: More robust
            ema_20 = self._calculate_ema_20(prices)
            ema_10 = self._calculate_ema_10(prices)  # Option D: For climax stops
            is_ath = self._check_ath_proximity(current_price, week_52_high)

            # Fallback if ATR calculation failed (use volatility approximation)
            if atr_14 == 0 and current_price > 0 and volatility > 0:
                atr_14 = current_price * (volatility / 100) * 0.3
            elif atr_14 == 0:
                atr_14 = current_price * 0.05  # 5% fallback

            # ========== STEP 2: Classify Risk Tier ==========
            tier_num, tier_name, tier_config = self._classify_risk_tier(
                volatility, beta, sector
            )

            initial_mult = tier_config['initial_multiplier']
            trailing_mult = tier_config['trailing_multiplier']
            hard_cap = tier_config['hard_cap_pct']

            # ========== STEP 3: ATH Adjustment (Reduce multiplier at breakout) ==========
            if is_ath:
                # At ATH breakout, reduce multiplier by 0.5 for tighter exit
                initial_mult = max(1.0, initial_mult - 0.5)
                trailing_mult = max(1.5, trailing_mult - 0.5)
                ath_note = "⚠️ ATH Breakout: Tighter stop (multiplier reduced 0.5x)"
            else:
                ath_note = ""

            # ========== STEP 4: Determine Lifecycle Phase (Option D) ==========
            # Restructured to use phase-aware stops with buffer to prevent stop hunting
            lifecycle_phase = "Entry (Risk On 🎯)"
            active_stop_price = 0
            active_stop_pct = 0
            lifecycle_note = ""

            if entry_price and entry_price > 0:
                current_gain_pct = ((current_price - entry_price) / entry_price * 100)

                # Phase D: Zombie Killer (check first - highest priority)
                if days_in_position > 20 and abs(current_gain_pct) < 2:
                    lifecycle_phase = "Zombie Killer (Time ⏱️)"
                    # Exit dead money - stop at entry or swing low 10d
                    active_stop_price = max(entry_price, swing_low_10)
                    active_stop_pct = ((active_stop_price - current_price) / current_price * 100)
                    lifecycle_note = f"Dead money for {days_in_position} days. Free up capital. Stop at ${active_stop_price:.2f}"

                # Phase C: Climax (profit protection)
                elif current_gain_pct > 30 or (rsi and rsi > 75):
                    lifecycle_phase = "Profit Locking (Clímax 💰)"
                    # Use phase='climax' for tight EMA 10 stop with 0.75% buffer
                    active_stop_price = self._calculate_tier_stop_smart(
                        tier_num, current_price, atr_14, 1.5,
                        ma_50, swing_low_20, ema_10, hard_cap,
                        phase='climax'
                    )
                    active_stop_pct = ((active_stop_price - current_price) / current_price * 100)
                    lifecycle_note = f"Climax detected (Return: {current_gain_pct:+.1f}%, RSI: {rsi or 'N/A'}). Lock in gains with tight stop."

                # Phase B: Breakeven (free ride - 1.5x initial risk)
                elif current_gain_pct >= 10:  # ~10% = 1.5x typical initial risk
                    lifecycle_phase = "Breakeven (Free Ride 🛡️)"
                    active_stop_price = entry_price
                    active_stop_pct = ((active_stop_price - current_price) / current_price * 100)
                    lifecycle_note = f"Risk eliminated! Stop moved to entry ${entry_price:.2f}. Playing with house money."

                # Phase A2: Trailing (trend following after initial period)
                elif days_in_position > 5 and current_gain_pct > 2:
                    lifecycle_phase = "Trailing (Trend Following 🏄)"
                    # Use phase='trailing' for long anchors (20d) with 0.5% buffer
                    active_stop_price = self._calculate_tier_stop_smart(
                        tier_num, current_price, atr_14, trailing_mult,
                        ma_50, swing_low_20, ema_10, hard_cap,
                        phase='trailing'
                    )
                    active_stop_pct = ((active_stop_price - current_price) / current_price * 100)
                    lifecycle_note = f"Position maturing. Trailing stop using long-term anchors with anti-hunting buffer."

                # Phase A1: Entry (initial protection)
                else:
                    lifecycle_phase = "Entry (Risk On 🎯)"
                    # Use phase='entry' for ATR + Hard Cap only (no tight anchors)
                    active_stop_price = self._calculate_tier_stop_smart(
                        tier_num, current_price, atr_14, initial_mult,
                        ma_50, swing_low_20, ema_10, hard_cap,
                        phase='entry'
                    )
                    active_stop_pct = ((active_stop_price - current_price) / current_price * 100)
                    lifecycle_note = f"Initial stop using {tier_name} parameters. ATR-based for breathing room."
            else:
                # No entry price - recommend initial stop
                lifecycle_phase = "Entry (Risk On 🎯)"
                active_stop_price = self._calculate_tier_stop_smart(
                    tier_num, current_price, atr_14, initial_mult,
                    ma_50, swing_low_20, ema_10, hard_cap,
                    phase='entry'
                )
                active_stop_pct = ((active_stop_price - current_price) / current_price * 100)
                lifecycle_note = f"Recommended initial stop for {tier_name}. ATR-based for breathing room."

            # ========== STEP 5: Calculate Alternative Stops ==========
            # Calculate stops for all tiers for comparison (using 'entry' phase)
            tier_1_stop = self._calculate_tier_stop_smart(1, current_price, atr_14, 1.8, ma_50, swing_low_20, ema_10, 8.0, phase='entry')
            tier_2_stop = self._calculate_tier_stop_smart(2, current_price, atr_14, 2.5, ma_50, swing_low_20, ema_10, 15.0, phase='entry')
            tier_3_stop = self._calculate_tier_stop_smart(3, current_price, atr_14, 3.0, ma_50, swing_low_20, ema_10, 25.0, phase='entry')

            # ========== STEP 6: Build Response ==========
            return {
                # Classification
                'tier': tier_num,
                'tier_name': tier_name,
                'tier_description': tier_config['description'],

                # Lifecycle
                'lifecycle_phase': lifecycle_phase,
                'lifecycle_note': lifecycle_note,

                # Active Stop (The one to use NOW)
                'active_stop': {
                    'price': f'${active_stop_price:.2f}',
                    'distance': f'{active_stop_pct:.1f}%',
                    'rationale': lifecycle_note or f"Initial {tier_name} stop"
                },

                # Base Parameters (Option D includes new indicators)
                'parameters': {
                    'atr_14': round(atr_14, 2),
                    'highest_high_22': round(highest_high_22, 2),
                    'swing_low_10': round(swing_low_10, 2),
                    'swing_low_20': round(swing_low_20, 2),  # Option D: More robust
                    'ema_20': round(ema_20, 2) if ema_20 > 0 else 'N/A',
                    'ema_10': round(ema_10, 2) if ema_10 > 0 else 'N/A',  # Option D: For climax
                    'is_ath_breakout': is_ath,
                    'ath_note': ath_note
                },

                # Tier-specific stops (for reference - shows Entry phase behavior)
                'tier_stops': {
                    'tier_1_defensive': {
                        'price': f'${tier_1_stop:.2f}',
                        'distance': f'{((tier_1_stop - current_price) / current_price * 100):.1f}%',
                        'formula': 'Entry: MAX(Price - 1.8*ATR, Price*0.92) | Trailing: MAX(ATR, SMA_50 * 0.995)'
                    },
                    'tier_2_core_growth': {
                        'price': f'${tier_2_stop:.2f}',
                        'distance': f'{((tier_2_stop - current_price) / current_price * 100):.1f}%',
                        'formula': 'Entry: MAX(Price - 2.5*ATR, Price*0.85) | Trailing: MAX(ATR, Swing_Low_20d * 0.995)'
                    },
                    'tier_3_speculative': {
                        'price': f'${tier_3_stop:.2f}',
                        'distance': f'{((tier_3_stop - current_price) / current_price * 100):.1f}%',
                        'formula': 'Entry: MAX(Price - 3.0*ATR, Price*0.75) | Trailing: MAX(ATR, EMA_10 * 0.995)'
                    }
                },

                # Configuration
                'config': {
                    'initial_multiplier': initial_mult,
                    'trailing_multiplier': trailing_mult,
                    'hard_cap_pct': hard_cap,
                    'anchor': tier_config['anchor']
                },

                # Notes
                'notes': [
                    f"Classified as {tier_name} based on volatility ({volatility:.1f}%) and beta ({beta or 'N/A'})",
                    f"Current lifecycle phase: {lifecycle_phase}",
                    "Option D (Hybrid): Entry=ATR only | Trailing=Long anchors+0.5% buffer | Climax=EMA10+0.75% buffer",
                    "Anti-hunting buffers prevent algorithmic stop hunting",
                    "Use trailing stops - move up as price rises, never down",
                    ath_note if ath_note else None
                ]
            }

        except Exception as e:
            logger.error(f"Error generating smart stop loss: {e}", exc_info=True)
            # Fallback to legacy method
            return self._generate_stop_loss(current_price, ma_50, ma_200, volatility,
                                           ((current_price - ma_200) / ma_200 * 100) if ma_200 > 0 else 0)

    def _calculate_tier_stop(
        self,
        tier: int,
        price: float,
        atr: float,
        multiplier: float,
        ma_50: float,
        swing_low: float,
        ema_20: float,
        hard_cap_pct: float
    ) -> float:
        """
        Calculate stop loss for a specific tier using tier-specific formula.

        Formulas:
        - Tier 1: MAX(Price - 1.8*ATR, Price*0.92, SMA_50)
        - Tier 2: MAX(Price - 2.5*ATR, Price*0.85, Swing_Low_10d)
        - Tier 3: MAX(Price - 3.0*ATR, Price*0.75, EMA_20)

        Returns:
            Stop loss price (float)
        """
        # Calculate ATR-based stop
        atr_stop = price - (multiplier * atr)

        # Calculate hard cap stop
        hard_cap_stop = price * (1 - hard_cap_pct / 100)

        # Calculate anchor stop (tier-specific)
        if tier == 1:
            anchor_stop = ma_50 if ma_50 > 0 else price * 0.92
        elif tier == 2:
            anchor_stop = swing_low if swing_low > 0 else price * 0.85
        else:  # tier == 3
            anchor_stop = ema_20 if ema_20 > 0 else price * 0.75

        # Return MAX of all three, but respect hard cap as minimum
        return max(hard_cap_stop, atr_stop, anchor_stop)

    def _calculate_tier_stop_smart(
        self,
        tier: int,
        price: float,
        atr: float,
        multiplier: float,
        ma_50: float,
        swing_low_20: float,
        ema_10: float,
        hard_cap_pct: float,
        phase: str = 'entry'
    ) -> float:
        """
        Smart stop loss with phase-aware anchor selection and buffer.

        This method implements Option D (Hybrid Complete) from OPCIONES_BUFFER_STOPLOSS.md
        to prevent stop hunting while maintaining appropriate protection.

        Phase Logic:
        - 'entry': ATR + Hard Cap only (no tight anchors, gives position breathing room)
        - 'trailing': Long-term anchors (20d) with 0.5% buffer to avoid stop hunting
        - 'climax': Tight EMA 10 with 0.75% buffer for profit protection

        Args:
            tier: Risk tier (1=Defensive, 2=Core Growth, 3=Speculative)
            price: Current price
            atr: 14-day ATR
            multiplier: ATR multiplier for this tier
            ma_50: 50-day SMA
            swing_low_20: 20-day swing low (more robust than 10d)
            ema_10: 10-day EMA (faster than 20d for climax)
            hard_cap_pct: Maximum allowed stop loss %
            phase: Lifecycle phase ('entry', 'trailing', 'climax')

        Returns:
            Stop loss price (float)
        """
        # Calculate ATR-based stop
        atr_stop = price - (multiplier * atr)

        # Calculate hard cap stop
        hard_cap_stop = price * (1 - hard_cap_pct / 100)

        # === PHASE-SPECIFIC LOGIC ===
        if phase == 'entry':
            # Entry Phase: ATR + Hard Cap only (no anchors)
            # Give the position breathing room to avoid premature stop-outs
            return max(hard_cap_stop, atr_stop)

        elif phase == 'trailing':
            # Trailing Phase: Long-term anchors with 0.5% buffer
            # Buffer prevents algorithmic stop hunting
            buffer = 0.995  # 0.5% buffer

            if tier == 1:
                # Tier 1 (Defensive): Use SMA 50
                anchor = (ma_50 * buffer) if ma_50 > 0 else price * 0.92
            elif tier == 2:
                # Tier 2 (Core Growth): Use Swing Low 20d (more robust than 10d)
                anchor = (swing_low_20 * buffer) if swing_low_20 > 0 else price * 0.85
            else:  # tier == 3
                # Tier 3 (Speculative): Use EMA 10 (faster response)
                anchor = (ema_10 * buffer) if ema_10 > 0 else price * 0.75

            return max(hard_cap_stop, atr_stop, anchor)

        elif phase == 'climax':
            # Climax Phase: Tight EMA 10 with 0.75% buffer
            # Protect profits but allow for normal pullback
            buffer = 0.9925  # 0.75% buffer
            ema_stop = (ema_10 * buffer) if ema_10 > 0 else price * 0.95
            tight_atr = price - (1.5 * atr)  # Tighter than normal

            return max(tight_atr, ema_stop)

        else:
            # Breakeven/zombie phases handled in main method
            # Fallback to simple calculation
            return max(hard_cap_stop, atr_stop)

    def _generate_profit_targets(self, signal, distance_ma200, overextension_risk, ma_200, price):
        """Profit taking recommendations."""
        if signal == 'SELL':
            return {'strategy': 'NO POSITION', 'targets': []}

        if overextension_risk >= 5 or distance_ma200 > 50:
            # Already overextended - take profits
            return {
                'strategy': 'LADDER SELLS (Scale out)',
                'sell_25_pct': 'NOW (lock in gains from overextended move)',
                'sell_25_pct_2': f'+10% from current (${price*1.10:.2f})',
                'sell_50_pct': f'If reaches {distance_ma200*1.2:.0f}% above MA200 (extreme euphoria)',
                'rationale': f'Already {distance_ma200:+.1f}% extended. Preserve gains vs being greedy. History shows extreme moves reverse quickly.'
            }
        elif overextension_risk >= 3:
            return {
                'strategy': 'PARTIAL PROFIT TAKING',
                'sell_25_pct': '+15-20% from entry',
                'sell_25_pct_2': '+30-40% from entry',
                'keep_50_pct': 'Runner with trailing stop',
                'rationale': 'Moderate overextension - lock in some gains while letting winners run with protection.'
            }
        else:
            return {
                'strategy': 'TRAILING STOP (Let winners run)',
                'target_1': '+25% from entry (optional partial)',
                'target_2': '+50% from entry (optional partial)',
                'trailing_stop': 'MA50 or 15% from highs',
                'rationale': 'Low overextension + strong momentum = let it run with trailing stop protection.'
            }

    def _generate_options_strategies(
        self, signal, overextension_risk, volatility, distance_ma200, volume_profile,
        price, sharpe, market_regime
    ):
        """
        Generate options strategies recommendations.

        Evidence-based options strategies:
        1. Covered Call - Generate income on overextended positions (Whaley 2002)
        2. Protective Put - Downside protection for strong holdings (Shastri & Tandon 1986)
        3. Collar - Low-cost protection (McIntyre & Jackson 2007)
        4. Cash-Secured Put - Entry at discount (Hemler & Miller 1997)
        5. Vertical Spread - Defined risk/reward (Hull 2017)
        """
        strategies = []

        # === Strategy 1: COVERED CALL (for overextended or neutral positions) ===
        if signal in ['BUY', 'HOLD'] and (overextension_risk >= 3 or distance_ma200 > 30):
            strategies.append({
                'name': 'COVERED CALL (Income generation)',
                'when': 'After establishing stock position OR if already own shares',
                'structure': 'Own 100 shares + Sell 1 Call (30-45 DTE)',
                'strike': f'~5-10% OTM (${price*1.07:.2f} area)',
                'premium': f'Collect ~{min(volatility/4, 5):.1f}% of stock price (~${price * min(volatility/400, 0.05):.2f}/share)',
                'rationale': f'Stock {distance_ma200:+.1f}% extended - likely consolidation ahead. Generate {min(volatility*12, 60):.0f}% annualized income while waiting.',
                'risk': 'Caps upside if stock continues rally. Can roll up/out if needed.',
                'evidence': 'Whaley (2002) - Covered calls outperform buy-hold in sideways/slightly up markets'
            })

        # === Strategy 2: PROTECTIVE PUT (for strong holdings with crash risk) ===
        if signal == 'BUY' and sharpe > 1.5 and (overextension_risk >= 4 or market_regime == 'BEAR'):
            strategies.append({
                'name': 'PROTECTIVE PUT (Downside protection)',
                'when': 'After establishing stock position',
                'structure': 'Own 100 shares + Buy 1 Put (60-90 DTE)',
                'strike': f'~10% OTM (${price*0.90:.2f} area)',
                'cost': f'~{min(volatility/3, 8):.1f}% of stock price (~${price * min(volatility/300, 0.08):.2f}/share)',
                'rationale': f'Strong fundamental (high Sharpe {sharpe:.2f}) but overextension risk {overextension_risk}/7. Protect gains vs 20-40% correction.',
                'benefit': f'Limits loss to ~10-12% while keeping unlimited upside',
                'evidence': 'Shastri & Tandon (1986) - Protective puts reduce downside risk by 40-60% in corrections'
            })

        # === Strategy 3: COLLAR (low-cost protection) ===
        if signal == 'BUY' and overextension_risk >= 3 and volatility > 30:
            strategies.append({
                'name': 'COLLAR (Zero/low-cost protection)',
                'when': 'After establishing stock position',
                'structure': 'Own 100 shares + Buy Put (10% OTM) + Sell Call (10% OTM)',
                'example': f'Buy ${price*0.90:.2f} Put + Sell ${price*1.10:.2f} Call (same expiry)',
                'cost': '$0-50 net (call premium offsets put cost)',
                'rationale': f'High volatility ({volatility:.1f}%) makes puts expensive. Collar provides protection for free/cheap.',
                'benefit': 'Locks in min 8-10% gain, caps upside at 10%, costs nearly nothing',
                'evidence': 'McIntyre & Jackson (2007) - Collars reduce volatility 70% with minimal cost'
            })

        # === Strategy 4: CASH-SECURED PUT (entry at discount) ===
        if signal == 'BUY' and overextension_risk >= 3 and volume_profile != 'DISTRIBUTION':
            strategies.append({
                'name': 'CASH-SECURED PUT (Entry at discount)',
                'when': 'INSTEAD of buying stock now - wait for pullback',
                'structure': 'Sell 1 Put (30-45 DTE) + Hold cash to buy if assigned',
                'strike': f'5-10% OTM (${price*0.92:.2f} area)',
                'premium': f'Collect ~{min(volatility/5, 4):.1f}% (~${price * min(volatility/500, 0.04):.2f}/share)',
                'outcome_1': f'Stock stays above ${price*0.92:.2f} → Keep premium, repeat next month',
                'outcome_2': f'Stock falls below ${price*0.92:.2f} → Buy at discount + keep premium = effective entry ${price*0.88:.2f}',
                'rationale': f'Overextension {overextension_risk}/7 suggests pullback likely. Get paid to wait for better entry.',
                'evidence': 'Hemler & Miller (1997) - Short puts at support levels profitable 65-70% of time'
            })

        # === Strategy 5: BULL PUT SPREAD (defined risk entry) ===
        if signal == 'BUY' and overextension_risk <= 2 and volume_profile == 'ACCUMULATION':
            strategies.append({
                'name': 'BULL PUT SPREAD (Defined risk/reward)',
                'when': 'Bullish but want defined risk',
                'structure': 'Sell Put (strike A) + Buy Put (strike B), where A > B',
                'example': f'Sell ${price*0.95:.2f} Put + Buy ${price*0.90:.2f} Put (30-45 DTE)',
                'credit': f'Collect ~{min(volatility/8, 3):.1f}% (~${price * min(volatility/800, 0.03):.2f}/share)',
                'max_profit': 'Credit received (if stock stays above A)',
                'max_loss': f'~${price*0.05:.2f}/share (if stock drops below B)',
                'rationale': f'Strong technical (low overextension) + accumulation. High probability trade with defined risk.',
                'evidence': 'Hull (2017) - Vertical spreads offer 60-70% win rate at 1SD strikes'
            })

        # === Strategy 6: LONG CALL (leverage for strong setups) ===
        if signal == 'BUY' and overextension_risk <= 1 and sharpe > 2.0 and volume_profile == 'ACCUMULATION':
            strategies.append({
                'name': 'LONG CALL (Leverage strong momentum)',
                'when': 'Alternative to stock for smaller accounts or leverage',
                'structure': 'Buy Call (60-90 DTE, at-the-money or slightly ITM)',
                'strike': f'ATM ${price:.2f} or slightly ITM ${price*0.97:.2f}',
                'cost': f'~{min(volatility/2.5, 12):.1f}% of stock price (~${price * min(volatility/250, 0.12):.2f}/share)',
                'leverage': '~10-15x leverage vs buying 100 shares',
                'rationale': f'Exceptional setup (Sharpe {sharpe:.2f}, low overext, accumulation). Use leverage but risk only premium.',
                'risk': 'Can lose 100% of premium. Only use 2-5% of portfolio on this trade.',
                'note': 'Buy minimum 60 DTE to avoid rapid theta decay'
            })

        # === Strategy 7: IRON CONDOR (overextended + high vol) ===
        if overextension_risk >= 5 and volatility > 40:
            strategies.append({
                'name': 'IRON CONDOR (Profit from consolidation)',
                'when': 'Expect stock to consolidate after parabolic move',
                'structure': 'Sell Call spread + Sell Put spread (both OTM)',
                'example': f'Stock ${price:.2f}: Sell ${price*1.12:.2f}/${price*1.17:.2f} Call spread + Sell ${price*0.88:.2f}/${price*0.83:.2f} Put spread',
                'credit': f'Collect ~{min(volatility/6, 6):.1f}% (~${price * min(volatility/600, 0.06):.2f}/share)',
                'max_profit': 'Full credit if stock stays in range',
                'rationale': f'Extreme overextension ({distance_ma200:+.1f}%) + high vol ({volatility:.1f}%) = likely consolidation. Profit from range-bound action.',
                'evidence': 'High IV after parabolic moves = ideal time for premium selling'
            })

        return strategies

    # ============================================================================
    # HELPER METHODS
    # ============================================================================

    def _score_return(self, return_pct: float, max_return: float = 50) -> float:
        """
        Convert return % to score 0-1.

        Args:
            return_pct: Return percentage
            max_return: Max return for score=1.0

        Returns:
            score: 0.0 to 1.0
        """
        if return_pct >= max_return:
            return 1.0
        elif return_pct <= -max_return:
            return 0.0
        else:
            # Linear interpolation
            return 0.5 + (return_pct / (2 * max_return))

    def _null_result(self, symbol: str, reason: str) -> Dict:
        """Return null result when analysis fails."""
        return {
            'score': 0,
            'signal': 'SELL',
            'market_regime': 'UNKNOWN',
            'momentum_12m': 0,
            'momentum_6m': 0,
            'momentum_3m': 0,
            'momentum_1m': 0,
            'momentum_consistency': 'UNKNOWN',
            'sharpe_12m': 0,
            'trend': 'UNKNOWN',
            'sector_relative': 0,
            'market_relative': 0,
            'volume_profile': 'UNKNOWN',
            'warnings': [{'type': 'HIGH', 'message': reason}],
            'timestamp': datetime.now().isoformat(),
            'error': reason
        }


# Backward compatibility alias
TechnicalAnalyzer = EnhancedTechnicalAnalyzer
