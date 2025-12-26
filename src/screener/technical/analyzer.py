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

    def analyze(self, symbol: str, sector: str = None, country: str = 'USA',
                fundamental_score: float = None, guardrails_status: str = None,
                fundamental_decision: str = None) -> Dict:
        """
        Enhanced technical analysis with 7 improvements.

        Args:
            symbol: Stock ticker (e.g., 'AAPL')
            sector: Company sector (e.g., 'Technology')
            country: Market country (default: 'USA')
            fundamental_score: Composite fundamental score 0-100 (optional, for position sizing)
            guardrails_status: Guardrails status 'VERDE'/'AMBER'/'ROJO' (optional, for position sizing)
            fundamental_decision: Decision 'BUY'/'MONITOR'/'AVOID' (optional, for position sizing)

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

            # 13. Calculate EMA20 for market state detection (FIX #7)
            # We need this BEFORE signal generation to detect DOWNTREND state
            ema_20 = self._calculate_ema_20(prices)

            # 14. Detect market state EARLY (for signal veto logic - FIX #7)
            # Quick detection without full stop loss calculation
            # This prevents BUY signals on stocks with broken structure
            week_52_high = q.get('yearHigh', 0)
            beta = q.get('beta', None)
            market_state_early, _, _ = self._detect_market_state(
                prices=prices,
                current_price=price,
                entry_price=None,  # No entry yet (just analyzing)
                days_in_position=0,
                ma_50=ma_50,
                ema_20=ema_20,
                rsi=None,
                week_52_high=week_52_high,
                tier=2  # Default to tier 2 for detection
            )

            # 15. Generate warnings (including overextension)
            warnings = self._generate_warnings(
                momentum_data, volume_data, sector_data, market_data, regime_data
            )
            warnings.extend(overext_warnings)  # Add overextension warnings

            # 16. Generate signal (FIX #6 + FIX #7: Pass overextension_risk AND market_state for veto logic)
            signal = self._generate_signal(
                total_score,
                trend_data,
                market_regime,
                overextension_risk,
                market_state=market_state_early  # FIX #7: Pass market state for DOWNTREND veto
            )

            # 17. Generate risk management recommendations (NEW)
            # Get additional data for SmartDynamicStopLoss (week_52_high, beta already defined above)

            # Calculate REAL ATR (14-day) as % of price
            # THIS IS DAILY VOLATILITY, NOT ANNUALIZED!
            # JNJ (Tortuga): ~1.0-1.5%
            # NVDA (Cohete): ~3-5%
            # Meme Stock: >15%
            atr_pct = self._calculate_atr(prices, period=14)
            if atr_pct is not None:
                logger.debug(f"{symbol}: ATR(14) = {atr_pct:.2f}% (daily volatility)")

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
                sector=sector,
                # Enhanced position sizing parameters
                momentum_12m=momentum_data.get('12m', 0),
                sector_status=sector_data.get('status', 'NEUTRAL'),
                market_status=market_data.get('status', 'NEUTRAL'),
                momentum_consistency=momentum_data.get('consistency', 'N/A'),
                atr_pct=atr_pct,
                # Fundamental data (passed from analyze() parameters)
                fundamental_score=fundamental_score,
                guardrails_status=guardrails_status,
                fundamental_decision=fundamental_decision
            )

            # 18. Detect contradictions and add warnings (FIX #3)
            # Check for inconsistencies between signal and components
            market_state_final = risk_mgmt_recs.get('stop_loss', {}).get('market_state', 'UNKNOWN')
            volume_profile = volume_data.get('profile', 'UNKNOWN')
            momentum_consistency = momentum_data.get('consistency', 'N/A')

            # CRITICAL contradictions
            if signal == 'BUY' and market_state_final == 'DOWNTREND':
                warnings.append({
                    'type': 'CRITICAL',
                    'message': '🚨 CONTRADICCIÓN CRÍTICA: BUY signal pero Stop Loss State = DOWNTREND. '
                              'Estructura rota detectada (Price < EMA20 < MA50). NO comprar.',
                    'action': 'DO NOT ENTER - Wait for structure to repair'
                })

            if signal == 'SELL' and market_state_final == 'POWER_TREND':
                warnings.append({
                    'type': 'CRITICAL',
                    'message': '🚨 CONTRADICCIÓN CRÍTICA: SELL signal pero Stop Loss State = POWER_TREND. '
                              'Tendencia fuerte activa. Revisar manualmente.',
                    'action': 'MANUAL REVIEW REQUIRED - Strong trend contradicts sell signal'
                })

            # WARNING level contradictions
            if signal == 'BUY' and volume_profile == 'DISTRIBUTION':
                warnings.append({
                    'type': 'WARNING',
                    'message': '⚠️ ALERTA: BUY signal pero Volume Profile = DISTRIBUTION. '
                              'Instituciones vendiendo. Proceder con cautela.',
                    'action': 'Consider reduced position size'
                })

            if signal == 'BUY' and market_state_final == 'CHOPPY_SIDEWAYS':
                warnings.append({
                    'type': 'WARNING',
                    'message': '⚠️ ALERTA: BUY signal pero Stop Loss State = CHOPPY/SIDEWAYS. '
                              'Sin momentum direccional claro. Esperar confirmación.',
                    'action': 'Wait for clearer trend development'
                })

            if signal == 'BUY' and momentum_consistency == 'WEAK':
                warnings.append({
                    'type': 'WARNING',
                    'message': '⚠️ ALERTA: BUY signal con Momentum Consistency = WEAK. '
                              'Momentum débil en múltiples timeframes. Score puede estar inflado artificialmente.',
                    'action': 'Review component breakdown - check if score is artificially inflated'
                })

            if signal == 'SELL' and momentum_consistency == 'STRONG':
                warnings.append({
                    'type': 'WARNING',
                    'message': '⚠️ ALERTA: SELL signal pero Momentum Consistency = STRONG. '
                              'Momentum fuerte debería generar score ≥ 60. Revisar.',
                    'action': 'Manual review - strong momentum contradicts low score'
                })

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

    def _generate_signal(self, score: float, trend_data: Dict, regime: str,
                        overextension_risk: int = 0, market_state: str = None) -> str:
        """
        Generate BUY/HOLD/SELL signal.

        Rules (in priority order):
        - VETO #1: market_state = DOWNTREND → SELL (broken structure - highest priority)
        - VETO #2: overextension_risk > 6 AND score < 80 → HOLD (wait for pullback)
        - BUY: score >= 75 AND uptrend
        - HOLD: score 50-75 OR mixed signals
        - SELL: score < 50

        FIX #6: Overextension Risk Veto
        - IF overextension_risk > 6 (EXTREME) AND score < 80 → Force HOLD
        - Only allow BUY with EXTREME overextension if score is exceptional (≥80)
        - Prevents buying into parabolic moves that are due for 20-40% correction

        FIX #7: DOWNTREND State Veto (CRITICAL)
        - IF market_state = DOWNTREND → Force SELL regardless of score
        - Prevents BUY signals on stocks with broken structure (Price < EMA20 < MA50)
        - Stop Loss State Machine is more sophisticated than basic MA200 trend check

        Args:
            score: Technical score 0-100
            trend_data: Trend analysis dictionary
            regime: Market regime (BULL/BEAR/SIDEWAYS)
            overextension_risk: Overextension risk score 0-10
            market_state: SmartDynamicStopLoss state (DOWNTREND, POWER_TREND, etc.)

        Returns:
            'BUY' | 'HOLD' | 'SELL'
        """
        # FIX #7: VETO #1 - DOWNTREND state (HIGHEST PRIORITY)
        # If structure is broken (Price < EMA20 < MA50), DO NOT allow BUY
        if market_state == 'DOWNTREND':
            logger.warning(f"🚨 DOWNTREND VETO applied: Broken structure detected. "
                          f"Forcing SELL even if score={score:.0f}/100 and trend=UPTREND. "
                          f"State Machine detected: Price < EMA20 < MA50")
            return 'SELL'

        is_uptrend = trend_data.get('status') == 'UPTREND'

        # FIX #6: VETO #2 - Overextension veto - Force HOLD if extreme overextension + non-exceptional score
        if overextension_risk > 6 and score < 80:
            logger.info(f"⚠️ Overextension veto applied: risk={overextension_risk}/10, score={score:.0f}/100. "
                       f"Forcing HOLD instead of BUY (wait for pullback to MA200)")
            return 'HOLD'  # Wait for better entry

        # Standard rules
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
            if is_momentum_leader:
                # FIX: Momentum leaders still need visibility at 40%+
                # Show informative warning but lower risk score
                risk_score += 1
                warnings.append({
                    'type': 'LOW',
                    'message': f'Extended momentum: {distance_ma200:+.1f}% from MA200. Strong trend confirmed - Monitor with trailing stop (EMA 20).'
                })
            else:
                # Regular stocks: higher risk
                risk_score += 2
                warnings.append({
                    'type': 'MEDIUM',
                    'message': f'Significant overextension: {distance_ma200:+.1f}% from MA200 (>40%). Possible 10-20% pullback.'
                })
        elif abs_distance > 30:
            if is_momentum_leader:
                # FIX: Show informative message even for leaders
                risk_score += 1
                warnings.append({
                    'type': 'LOW',
                    'message': f'Good momentum: {distance_ma200:+.1f}% from MA200. Quality Leader - Continue holding with trailing stop.'
                })
            else:
                # Regular stocks: caution needed
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
    # ATR CALCULATION (for Position Sizing)
    # ============================================================================

    def _calculate_atr(self, prices: List[Dict], period: int = 14) -> float:
        """
        Calculate Average True Range (ATR) as % of current price.

        ATR measures DAILY volatility using actual intraday range:
        - True Range = max(high - low, abs(high - prev_close), abs(low - prev_close))
        - ATR = moving average of TR over period days
        - ATR% = (ATR / current_price) * 100

        THIS IS NOT ANNUALIZED VOLATILITY!

        Examples:
        - JNJ (Tier 1 Tortuga): ATR ~1.0-1.5% (se mueve $2-3 por día)
        - NVDA (Tier 3 Cohete): ATR ~3-5% (se mueve $25-40 por día)
        - Meme Stock: ATR >15% (se mueve >15% por día)

        Args:
            prices: List of price dicts with 'high', 'low', 'close' (chronological order)
            period: ATR period (default: 14 days)

        Returns:
            ATR as % of current price (e.g., 1.5 means stock moves ~1.5% per day on average)
            None if insufficient data
        """
        if not prices or len(prices) < period + 1:
            return None

        # Get most recent prices (need period+1 for prev_close calculation)
        recent_prices = prices[-(period+1):]

        true_ranges = []
        for i in range(1, len(recent_prices)):
            current = recent_prices[i]
            previous = recent_prices[i-1]

            high = current.get('high', 0)
            low = current.get('low', 0)
            prev_close = previous.get('close', 0)

            if high == 0 or low == 0 or prev_close == 0:
                continue

            # True Range = max(high-low, abs(high-prev_close), abs(low-prev_close))
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)

        if not true_ranges or len(true_ranges) < period:
            return None

        # ATR = simple moving average of last 'period' true ranges
        atr_value = sum(true_ranges[-period:]) / period

        # Get current price
        current_price = recent_prices[-1].get('close', 0)
        if current_price == 0:
            return None

        # ATR as % of price
        atr_pct = (atr_value / current_price) * 100

        return atr_pct

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
        sector: str = None,
        # Additional technical data for enhanced position sizing
        momentum_12m: float = None,
        sector_status: str = None,
        market_status: str = None,
        momentum_consistency: str = None,
        atr_pct: float = None,
        # Fundamental data for position sizing
        fundamental_score: float = None,
        guardrails_status: str = None,
        fundamental_decision: str = None
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

        # ========== 1. STOP LOSS (SmartDynamicStopLoss) - CALCULATE FIRST ==========
        # This is the SOURCE OF TRUTH for market state detection
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

        # Extract market state for veto checking
        market_state = recommendations['stop_loss'].get('market_state', 'UNKNOWN')

        # Define veto states (absolute no-entry conditions)
        VETO_STATES = ['DOWNTREND', 'PARABOLIC_CLIMAX']
        is_veto = market_state in VETO_STATES

        # ========== 2. POSITION SIZING (with veto awareness) ==========
        recommendations['position_sizing'] = self._generate_position_sizing(
            signal, overextension_risk, sharpe, volatility, market_regime,
            market_state=market_state,
            is_veto=is_veto,
            # Enhanced position sizing parameters (now passed from analyze() method)
            fundamental_score=fundamental_score,
            guardrails_status=guardrails_status,
            fundamental_decision=fundamental_decision,
            momentum_12m=momentum_12m,
            sector_status=sector_status,
            market_status=market_status,
            volume_profile=volume_profile,
            momentum_consistency=momentum_consistency,
            atr_pct=atr_pct
        )

        # ========== 3. ENTRY STRATEGY (with veto awareness and structural levels) ==========
        # Extract EMA 20 from stop loss data (if available)
        stop_loss_params = recommendations['stop_loss'].get('parameters', {})
        ema_20_value = stop_loss_params.get('ema_20', None)
        if isinstance(ema_20_value, str) and ema_20_value == 'N/A':
            ema_20_value = None
        elif isinstance(ema_20_value, (int, float)):
            ema_20_value = float(ema_20_value)

        recommendations['entry_strategy'] = self._generate_entry_strategy(
            signal, overextension_risk, distance_ma200, price, ma_50, ma_200,
            market_state=market_state,
            is_veto=is_veto,
            prices=prices,
            ema_20=ema_20_value,
            week_52_high=week_52_high
        )

        # ========== 4. PROFIT TAKING (Tier-Based Asymmetric Strategy) ==========
        # Extract market_state and stop_loss info for profit taking decisions
        market_state = recommendations['stop_loss'].get('state', 'UNKNOWN')
        stop_loss_pct = recommendations['stop_loss'].get('stop_loss_pct', 0)

        recommendations['profit_taking'] = self._generate_profit_targets(
            signal=signal,
            distance_ma200=distance_ma200,
            overextension_risk=overextension_risk,
            ma_200=ma_200,
            price=price,
            # Pass fundamental data for tier determination
            fundamental_score=fundamental_score,
            guardrails_status=guardrails_status,
            # Pass market state for PARABOLIC_CLIMAX detection
            market_state=market_state,
            # Pass stop loss for R-multiple calculation
            stop_loss_pct=stop_loss_pct
        )

        # ========== 5. OPTIONS STRATEGIES ==========
        recommendations['options_strategies'] = self._generate_options_strategies(
            signal, overextension_risk, volatility, distance_ma200, volume_profile,
            price, sharpe, market_regime
        )

        return recommendations

    def _calculate_state_penalty(self, market_state, volume_profile=None, sector_status=None,
                                  market_status=None, sharpe=None, momentum_consistency=None):
        """
        Calculate penalty/bonus for SmartDynamicStopLoss state.

        For ENTRY_BREAKOUT, classifies as Strong/Moderate/Weak based on confirmations.
        """
        # States with fixed penalties
        FIXED_PENALTIES = {
            'POWER_TREND': 0,  # Ideal - no penalty
            'PULLBACK_FLAG': -1,  # Buying dip - minimal penalty
            'BLUE_SKY_ATH': -2,  # No resistance but overheating risk
            'CHOPPY_SIDEWAYS': -5,  # Wait for confirmation
            # DOWNTREND and PARABOLIC_CLIMAX handled as VETO in main function
        }

        if market_state in FIXED_PENALTIES:
            return FIXED_PENALTIES[market_state]

        # ENTRY_BREAKOUT requires strength classification
        if market_state == 'ENTRY_BREAKOUT':
            # Calculate breakout strength score
            score = 0

            # Volume confirmation (+2 points)
            if volume_profile == 'STRONG':
                score += 2
            elif volume_profile == 'MODERATE':
                score += 1

            # Sector strength (+1 point)
            if sector_status == 'LEADING':
                score += 1

            # Market strength (+1 point)
            if market_status == 'OUTPERFORMING':
                score += 1

            # Risk-adjusted returns (+1 point)
            if sharpe and sharpe > 1.5:
                score += 1

            # Momentum consistency (+1 point)
            if momentum_consistency in ['STRONG', 'MODERATE']:
                score += 1

            # Classification
            if score >= 4:
                return -1  # STRONG BREAKOUT
            elif score >= 2:
                return -2  # MODERATE BREAKOUT
            else:
                return -4  # WEAK BREAKOUT

        # Unknown state - neutral
        return 0

    def _generate_position_sizing(self, signal, overextension_risk, sharpe, volatility, market_regime,
                                   market_state=None, is_veto=False,
                                   # Optional fundamental data for enhanced sizing
                                   fundamental_score=None, guardrails_status=None, fundamental_decision=None,
                                   # Additional technical data for penalties
                                   momentum_12m=None, sector_status=None, market_status=None, volume_profile=None,
                                   momentum_consistency=None, atr_pct=None):
        """
        Penalty-Based Position Sizing System.

        **Framework:**
        1. BASE allocation by quality (Elite 10%, High 5%, Medium 3%, Low 1%)
        2. Apply PENALTIES for technical risks (subtract %)
        3. Apply BONUSES for technical strength (add %)
        4. Floor at 0%, ceiling at BASE %

        Args:
            market_state: Current market state from SmartDynamicStopLoss
            is_veto: True if market state is in VETO_STATES (DOWNTREND, PARABOLIC_CLIMAX)
            fundamental_score: Composite score 0-100 (optional)
            guardrails_status: VERDE/AMBAR/ROJO (optional)
            fundamental_decision: BUY/MONITOR/AVOID (optional)
            momentum_12m: 12-month return % (optional)
            sector_status: LEADING/NEUTRAL/LAGGING/DOWNTREND (optional)
            market_status: OUTPERFORMING/NEUTRAL/UNDERPERFORMING/WEAK (optional)
            volume_profile: STRONG/MODERATE/WEAK/DECLINING (optional)
            momentum_consistency: Consistency rating (optional)
            atr_pct: ATR as % of price (optional)
        """
        # ========== STEP 1: VETO CHECKS (Absolute No-Entry) ==========

        # VETO A: Dangerous Market State
        if is_veto:
            veto_messages = {
                'DOWNTREND': 'Price < SMA 50 - Broken structure. Wait for recovery above SMA 50.',
                'PARABOLIC_CLIMAX': 'Vertical move unsustainable. High probability of significant correction. Wait for pullback to support.'
            }
            return {
                'recommended_size': '0%',
                'base_pct': 0,
                'final_pct': 0,
                'penalties': [f"VETO: {market_state}"],
                'bonuses': [],
                'rationale': f'🛑 VETO: {market_state} - {veto_messages.get(market_state, "Dangerous market state detected")}',
                'veto_active': True,
                'calculation_breakdown': f"VETO: {market_state} → 0%"
            }

        # VETO B: Extreme Volatility (Meme Stock Territory)
        if atr_pct and atr_pct > 15:
            return {
                'recommended_size': '0%',
                'base_pct': 0,
                'final_pct': 0,
                'penalties': [f"VETO: Meme Stock (ATR {atr_pct:.1f}%)"],
                'bonuses': [],
                'rationale': f'🛑 VETO: Extreme volatility (ATR {atr_pct:.1f}%) - Meme stock territory. Use options instead.',
                'veto_active': True,
                'calculation_breakdown': f"VETO: ATR {atr_pct:.1f}% > 15% → 0%"
            }

        # ========== STEP 2: BASE ALLOCATION (by Quality) ==========

        base_pct = 0
        quality_tier = "UNKNOWN"

        # DEBUG: Log what fundamental data we received
        logger.info(f"Position Sizing DEBUG - fundamental_score: {fundamental_score}, guardrails_status: {guardrails_status}, fundamental_decision: {fundamental_decision}")

        if fundamental_score is not None and guardrails_status and fundamental_decision:
            # Full fundamental data available - use precise tiering
            logger.info(f"Using PRECISE tiering with full fundamental data")
            if fundamental_score > 85 and guardrails_status == 'VERDE' and fundamental_decision == 'BUY':
                base_pct = 10
                quality_tier = "💎 ELITE"
            elif fundamental_score > 70 and guardrails_status in ['VERDE', 'AMBAR'] and fundamental_decision == 'BUY':
                base_pct = 5
                quality_tier = "🥇 HIGH"
            elif fundamental_score > 60 and fundamental_decision in ['BUY', 'MONITOR']:
                base_pct = 3
                quality_tier = "🥈 MEDIUM"
            else:
                base_pct = 1
                quality_tier = "🥉 LOW"
        elif fundamental_score is not None:
            # Partial fundamental data - use score-based tiering
            logger.info(f"Using SCORE-BASED tiering (score={fundamental_score})")
            if fundamental_score > 85:
                base_pct = 10
                quality_tier = "💎 ELITE"
            elif fundamental_score > 70:
                base_pct = 5
                quality_tier = "🥇 HIGH"
            elif fundamental_score > 60:
                base_pct = 3
                quality_tier = "🥈 MEDIUM"
            else:
                base_pct = 1
                quality_tier = "🥉 LOW"
        else:
            # Fallback: estimate quality from technical signal only
            logger.info(f"Using ESTIMATED tiering (no fundamental data)")
            if signal == 'BUY' and sharpe > 2.0:
                base_pct = 8  # Assume high quality
                quality_tier = "🥇 HIGH (estimated)"
            elif signal == 'BUY':
                base_pct = 5  # Assume medium quality
                quality_tier = "🥈 MEDIUM (estimated)"
            elif signal == 'HOLD':
                base_pct = 3
                quality_tier = "🥈 MEDIUM (estimated)"
            else:
                base_pct = 0
                quality_tier = "AVOID"

        # ========== STEP 3: PENALTIES & BONUSES ==========

        adjusted_pct = base_pct
        penalties = []
        bonuses = []

        # A. SmartDynamicStopLoss State Penalty
        if market_state:
            state_penalty = self._calculate_state_penalty(market_state, volume_profile, sector_status,
                                                          market_status, sharpe, momentum_consistency)
            if state_penalty != 0:
                adjusted_pct += state_penalty  # state_penalty is negative or positive
                if state_penalty < 0:
                    penalties.append(f"{market_state}: {state_penalty:+.1f}%")
                else:
                    bonuses.append(f"{market_state}: {state_penalty:+.1f}%")

        # B. Momentum Penalty (overheating risk)
        # FIX #10: Don't double-penalize for Momentum + Pullback
        # Logic: If in PULLBACK_FLAG state, the high momentum is ALREADY correcting
        # Penalizing both is contradictory - the pullback IS the correction
        if momentum_12m is not None:
            mom_penalty = 0

            # EXCEPTION: If in PULLBACK state, waive momentum penalty
            # The pullback itself indicates healthy correction of overheating
            is_pullback_state = market_state in ['PULLBACK_FLAG', 'CHOPPY_SIDEWAYS']

            if is_pullback_state and momentum_12m > 50:
                # Stock is correcting high momentum - this is GOOD timing, not risky
                # No penalty applied
                bonuses.append(f"Pullback after +{momentum_12m:.0f}% run: Perfect entry (penalty waived)")
            elif momentum_12m > 150:
                mom_penalty = -3
                penalties.append(f"Momentum +{momentum_12m:.0f}%: -3%")
            elif momentum_12m > 100:
                mom_penalty = -2
                penalties.append(f"Momentum +{momentum_12m:.0f}%: -2%")
            elif momentum_12m > 50:
                mom_penalty = -1
                penalties.append(f"Momentum +{momentum_12m:.0f}%: -1%")
            elif momentum_12m < 0:
                mom_penalty = -2
                penalties.append(f"Momentum {momentum_12m:.0f}%: -2%")
            adjusted_pct += mom_penalty

        # C. Volatility Penalty/Bonus
        if atr_pct is not None:
            vol_adjustment = 0
            if atr_pct >= 10:  # 10-15% ATR → PARTIAL VETO (handled separately)
                vol_adjustment = -999  # Signal for division by 2
                penalties.append(f"ATR {atr_pct:.1f}%: ÷2 (PARTIAL VETO)")
            elif atr_pct >= 8:
                vol_adjustment = -4
                penalties.append(f"ATR {atr_pct:.1f}%: -4%")
            elif atr_pct >= 5:
                vol_adjustment = -2
                penalties.append(f"ATR {atr_pct:.1f}%: -2%")
            elif atr_pct >= 3:
                vol_adjustment = -1
                penalties.append(f"ATR {atr_pct:.1f}%: -1%")
            elif atr_pct < 2:
                vol_adjustment = 1
                bonuses.append(f"Low Volatility (ATR {atr_pct:.1f}%): +1%")

            if vol_adjustment != -999:
                adjusted_pct += vol_adjustment

        # D. Sharpe Ratio Bonus/Penalty
        if sharpe is not None:
            sharpe_adjustment = 0
            if sharpe > 2.5:
                sharpe_adjustment = 2
                bonuses.append(f"Sharpe {sharpe:.2f}: +2%")
            elif sharpe > 2.0:
                sharpe_adjustment = 1
                bonuses.append(f"Sharpe {sharpe:.2f}: +1%")
            elif 1.0 <= sharpe <= 2.0:
                sharpe_adjustment = 0  # Normal
            elif 0.5 <= sharpe < 1.0:
                sharpe_adjustment = -1
                penalties.append(f"Sharpe {sharpe:.2f}: -1%")
            elif 0 <= sharpe < 0.5:
                sharpe_adjustment = -2
                penalties.append(f"Sharpe {sharpe:.2f}: -2%")
            elif sharpe < 0:
                sharpe_adjustment = -3
                penalties.append(f"Sharpe {sharpe:.2f}: -3%")
            adjusted_pct += sharpe_adjustment

        # E. Sector Relative Strength
        if sector_status:
            if sector_status == 'LEADING':
                adjusted_pct += 1
                bonuses.append(f"Sector LEADING: +1%")
            elif sector_status == 'LAGGING':
                adjusted_pct -= 1
                penalties.append(f"Sector LAGGING: -1%")
            elif sector_status == 'DOWNTREND':
                adjusted_pct -= 3
                penalties.append(f"Sector DOWNTREND: -3%")

        # F. Market Relative Strength
        if market_status:
            if market_status == 'OUTPERFORMING':
                adjusted_pct += 1
                bonuses.append(f"vs SPY OUTPERFORMING: +1%")
            elif market_status == 'UNDERPERFORMING':
                adjusted_pct -= 1
                penalties.append(f"vs SPY UNDERPERFORMING: -1%")
            elif market_status == 'WEAK':
                adjusted_pct -= 2
                penalties.append(f"vs SPY WEAK: -2%")

        # G. Volume Profile
        if volume_profile:
            if volume_profile == 'STRONG':
                pass  # No adjustment - normal
            elif volume_profile == 'MODERATE':
                adjusted_pct -= 1
                penalties.append(f"Volume MODERATE: -1%")
            elif volume_profile == 'WEAK':
                adjusted_pct -= 2
                penalties.append(f"Volume WEAK: -2%")
            elif volume_profile == 'DECLINING':
                adjusted_pct -= 3
                penalties.append(f"Volume DECLINING: -3%")

        # ========== STEP 4: FLOOR & CEILING ==========

        # Cap at base % (no bonuses can exceed base allocation)
        if adjusted_pct > base_pct:
            adjusted_pct = base_pct

        # Floor at 0% or 1% minimum viable
        final_pct = max(0, adjusted_pct)

        # If below 1%, consider it 0% (not worth the position)
        if 0 < final_pct < 1:
            final_pct = 0
            penalties.append("Below 1% minimum → 0%")

        # ========== STEP 5: VOLATILITY PARTIAL VETO (÷2) ==========

        # Check if ATR triggered partial veto
        if atr_pct and 10 <= atr_pct <= 15:
            final_pct = final_pct / 2
            penalties.append(f"⚠️ PARTIAL VETO: Position halved due to ATR {atr_pct:.1f}%")

        # ========== STEP 6: BEAR MARKET OVERRIDE ==========

        bear_market_adjustment = False
        if market_regime == 'BEAR':
            final_pct = final_pct / 2
            bear_market_adjustment = True

        # ========== STEP 7: BUILD RESPONSE ==========

        # Build rationale
        rationale_parts = [f"{quality_tier} Quality → BASE {base_pct}%"]

        if penalties:
            rationale_parts.append(f"Penalties: {', '.join(penalties)}")
        if bonuses:
            rationale_parts.append(f"Bonuses: {', '.join(bonuses)}")

        if bear_market_adjustment:
            rationale_parts.append("⚠️ Bear Market: Position halved")

        rationale_parts.append(f"FINAL: {final_pct:.1f}% of portfolio")

        if final_pct == 0:
            if len(penalties) > 0:
                reason = "Technical conditions unfavorable"
            else:
                reason = "No entry signal"
        elif final_pct >= base_pct * 0.9:
            reason = "Strong setup - full allocation"
        elif final_pct >= base_pct * 0.7:
            reason = "Good setup - moderate allocation"
        elif final_pct >= base_pct * 0.5:
            reason = "Cautious allocation - multiple concerns"
        else:
            reason = "Reduced allocation - significant risks"

        return {
            'recommended_size': f'{final_pct:.1f}%',
            'base_pct': base_pct,
            'final_pct': final_pct,
            'quality_tier': quality_tier,
            'penalties': penalties,
            'bonuses': bonuses,
            'bear_market_adjustment': bear_market_adjustment,
            'rationale': reason,
            'calculation_breakdown': ' | '.join(rationale_parts),
            'veto_active': False
        }

    def _generate_entry_strategy(self, signal, overextension_risk, distance_ma200, price, ma_50, ma_200,
                                  market_state=None, is_veto=False, prices=None, ema_20=None, week_52_high=None):
        """
        STATE-BASED Entry Strategy - Institutional Grade

        Instead of arbitrary percentages, uses STRUCTURAL LEVELS based on market state:
        - SNIPER: Limit orders at support levels (PULLBACK_FLAG)
        - BREAKOUT: Buy stops above resistance (ENTRY_BREAKOUT)
        - PYRAMID: Add to winners (POWER_TREND)

        Args:
            market_state: Current market state from SmartDynamicStopLoss
            is_veto: True if market state is in VETO_STATES (DOWNTREND, PARABOLIC_CLIMAX)
            prices: Historical price data for calculating structural levels
            ema_20: 20-day EMA (support level)
            week_52_high: 52-week high (resistance)
        """
        # VETO CHECK: If dangerous market state detected, NO ENTRY
        if is_veto:
            veto_messages = {
                'DOWNTREND': 'Price < SMA 50 - Broken structure. Wait for recovery above SMA 50.',
                'PARABOLIC_CLIMAX': 'Vertical move unsustainable (momentum crashes research: Daniel & Moskowitz 2016). Wait for pullback to support levels (MA50, swing low).'
            }
            return {
                'strategy': 'NO ENTRY - STATE MACHINE VETO',
                'rationale': veto_messages.get(market_state, 'Dangerous market state detected'),
                'market_state': market_state,
                'veto_active': True
            }

        # NORMAL LOGIC: No veto active
        if signal == 'SELL':
            return {
                'strategy': 'NO ENTRY',
                'rationale': 'Wait for technical improvement',
                'strategy_type': 'NONE'
            }

        # ========== CALCULATE STRUCTURAL LEVELS ==========

        # Calculate yesterday's high (resistance for breakouts)
        yesterday_high = prices[-2]['high'] if prices and len(prices) >= 2 else price * 1.02

        # Calculate swing low (support level for limit orders)
        swing_low_20 = self._calculate_swing_low_20(prices) if prices else price * 0.95

        # Use EMA 20 as primary support level (institutional level)
        support_ema20 = ema_20 if ema_20 and ema_20 > 0 else price * 0.97

        # Use SMA 50 as secondary support (major institutional level)
        support_sma50 = ma_50 if ma_50 > 0 else price * 0.95

        # Invalidation level (below which setup breaks)
        invalidation = swing_low_20 * 0.97 if swing_low_20 > 0 else price * 0.92

        # ========== STATE-BASED STRATEGY SELECTION ==========

        # STRATEGY 1: SUPPORT SNIPER (for pullbacks/corrections)
        if market_state in ['PULLBACK_FLAG', 'CHOPPY_SIDEWAYS']:
            return {
                'strategy': 'SUPPORT SNIPER',
                'strategy_type': 'SNIPER',
                'state': market_state,
                'rationale': 'Stock in pullback. Buy at support levels with limit orders. Preserve dry powder for optimal entry.',
                'tranches': [
                    {
                        'number': 1,
                        'size': '60%',
                        'order_type': 'MARKET',
                        'price': price,
                        'trigger': 'Enter now to secure position',
                        'is_primary': True
                    },
                    {
                        'number': 2,
                        'size': '40%',
                        'order_type': 'LIMIT',
                        'price': support_ema20,
                        'trigger': f'Touch of EMA 20 at ${support_ema20:.2f} (institutional support)',
                        'is_primary': False
                    }
                ],
                'invalidation': {
                    'price': invalidation,
                    'action': f'Cancel Tranche #2 and execute stop loss on Tranche #1 if price falls below ${invalidation:.2f}'
                },
                'structural_levels': {
                    'support_primary': support_ema20,
                    'support_secondary': support_sma50,
                    'invalidation': invalidation
                }
            }

        # STRATEGY 2: BREAKOUT CONFIRMATION (for new highs/breakouts)
        elif market_state in ['ENTRY_BREAKOUT', 'BLUE_SKY_ATH']:
            breakout_trigger = yesterday_high * 1.01  # 1% above yesterday's high
            return {
                'strategy': 'MOMENTUM CONFIRMATION',
                'strategy_type': 'BREAKOUT',
                'state': market_state,
                'rationale': 'Breakout in progress. Enter with confirmation to avoid false breakouts. Average up on strength.',
                'tranches': [
                    {
                        'number': 1,
                        'size': '50%',
                        'order_type': 'MARKET',
                        'price': price,
                        'trigger': 'Enter with half position. Controlled risk.',
                        'is_primary': True
                    },
                    {
                        'number': 2,
                        'size': '50%',
                        'order_type': 'STOP BUY',
                        'price': breakout_trigger,
                        'trigger': f'Only if breaks above ${breakout_trigger:.2f} (yesterday high +1%). Confirms strength.',
                        'is_primary': False
                    }
                ],
                'invalidation': {
                    'price': support_sma50,
                    'action': f'Cancel Tranche #2 if price fails to break resistance. Exit if falls below ${support_sma50:.2f}'
                },
                'structural_levels': {
                    'resistance': yesterday_high,
                    'breakout_trigger': breakout_trigger,
                    'support_fallback': support_sma50
                }
            }

        # STRATEGY 3: TREND PYRAMID (for established uptrends)
        elif market_state == 'POWER_TREND':
            new_high_trigger = week_52_high * 1.005 if week_52_high else price * 1.02  # 0.5% above 52w high
            return {
                'strategy': 'TREND PYRAMID',
                'strategy_type': 'PYRAMID',
                'state': market_state,
                'rationale': 'Strong uptrend established. Enter with discipline. Add ONLY on new highs (average up). Don\'t chase.',
                'tranches': [
                    {
                        'number': 1,
                        'size': '50%',
                        'order_type': 'MARKET',
                        'price': price,
                        'trigger': 'Enter with half position now',
                        'is_primary': True
                    },
                    {
                        'number': 2,
                        'size': '50%',
                        'order_type': 'STOP BUY',
                        'price': new_high_trigger,
                        'trigger': f'Add ONLY if confirms new high above ${new_high_trigger:.2f}. Winner adding.',
                        'is_primary': False
                    }
                ],
                'invalidation': {
                    'price': support_sma50,
                    'action': f'Exit all if trend breaks below SMA 50 at ${support_sma50:.2f}'
                },
                'structural_levels': {
                    'resistance': new_high_trigger,
                    'support_major': support_sma50,
                    'support_minor': support_ema20
                }
            }

        # FALLBACK: For undefined states, use conservative approach
        else:
            return {
                'strategy': 'CONSERVATIVE ENTRY',
                'strategy_type': 'CONSERVATIVE',
                'state': market_state or 'UNKNOWN',
                'rationale': f'Undefined state ({market_state}). Using conservative 2-tranche approach.',
                'tranches': [
                    {
                        'number': 1,
                        'size': '60%',
                        'order_type': 'MARKET',
                        'price': price,
                        'trigger': 'Enter majority now',
                        'is_primary': True
                    },
                    {
                        'number': 2,
                        'size': '40%',
                        'order_type': 'LIMIT',
                        'price': support_ema20,
                        'trigger': f'Reserve for pullback to ${support_ema20:.2f}',
                        'is_primary': False
                    }
                ],
                'invalidation': {
                    'price': invalidation,
                    'action': f'Exit if falls below ${invalidation:.2f}'
                },
                'structural_levels': {
                    'support': support_ema20,
                    'invalidation': invalidation
                }
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

    def _calculate_adx(self, prices: List[Dict], period: int = 14) -> float:
        """
        Calculate Average Directional Index (ADX) - Trend Strength Indicator.

        ADX > 25: Strong trend (use trailing stops, let it run)
        ADX < 20: Weak trend / choppy (tighten stops, exit soon)

        ADX measures trend strength regardless of direction.

        Args:
            prices: Historical price data
            period: Lookback period (default 14)

        Returns:
            ADX value (0-100)
        """
        try:
            if len(prices) < period * 2:
                return 0

            # Calculate +DM and -DM (Directional Movement)
            plus_dm = []
            minus_dm = []
            tr_list = []

            for i in range(1, min(len(prices), period * 2)):
                high = prices[-i]['high']
                low = prices[-i]['low']
                close = prices[-i]['close']
                prev_high = prices[-(i+1)]['high']
                prev_low = prices[-(i+1)]['low']
                prev_close = prices[-(i+1)]['close']

                # True Range
                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                tr_list.append(tr)

                # Directional Movement
                up_move = high - prev_high
                down_move = prev_low - low

                if up_move > down_move and up_move > 0:
                    plus_dm.append(up_move)
                    minus_dm.append(0)
                elif down_move > up_move and down_move > 0:
                    minus_dm.append(down_move)
                    plus_dm.append(0)
                else:
                    plus_dm.append(0)
                    minus_dm.append(0)

            if not tr_list or sum(tr_list[:period]) == 0:
                return 0

            # Smooth using Wilder's smoothing (EMA-like)
            smoothed_tr = sum(tr_list[:period])
            smoothed_plus_dm = sum(plus_dm[:period])
            smoothed_minus_dm = sum(minus_dm[:period])

            # Calculate +DI and -DI
            plus_di = (smoothed_plus_dm / smoothed_tr) * 100 if smoothed_tr > 0 else 0
            minus_di = (smoothed_minus_dm / smoothed_tr) * 100 if smoothed_tr > 0 else 0

            # Calculate DX
            di_sum = plus_di + minus_di
            di_diff = abs(plus_di - minus_di)
            dx = (di_diff / di_sum) * 100 if di_sum > 0 else 0

            # ADX is smoothed average of DX (simplified - using single DX value)
            return round(dx, 1)

        except Exception as e:
            logger.warning(f"Error calculating ADX: {e}")
            return 0

    def _calculate_sma_slope(self, prices: List[Dict], period: int = 50) -> float:
        """
        Calculate the slope of SMA (angle of trend).

        Positive slope: Uptrend
        Near zero: Sideways/flat
        Negative slope: Downtrend

        Args:
            prices: Historical price data
            period: SMA period (default 50)

        Returns:
            Slope as percentage change per day
        """
        try:
            if len(prices) < period + 10:
                return 0

            # Calculate current SMA
            current_sma = statistics.mean(p['close'] for p in prices[-period:])

            # Calculate SMA from 10 days ago
            past_sma = statistics.mean(p['close'] for p in prices[-(period+10):-10])

            if past_sma == 0:
                return 0

            # Slope = (current - past) / past / days
            slope = ((current_sma - past_sma) / past_sma / 10) * 100

            return round(slope, 3)

        except Exception as e:
            logger.warning(f"Error calculating SMA slope: {e}")
            return 0

    def _detect_market_state(
        self,
        prices: List[Dict],
        current_price: float,
        entry_price: float = None,
        days_in_position: int = 0,
        ma_50: float = 0,
        ema_20: float = 0,
        rsi: float = None,
        week_52_high: float = 0,
        tier: int = 2
    ) -> Tuple[str, str]:
        """
        🧠 STATE MACHINE - Detect current market state for the stock.

        This is the brain of the stop loss system. Instead of applying the same
        rule always, this detects the current "battle phase" and adapts the strategy.

        7 CRITICAL STATES (checked in priority order):

        0. DOWNTREND - Broken structure, avoid or exit
        1. ENTRY_BREAKOUT - Just bought, fighting to break out
        2. PARABOLIC_CLIMAX - Vertical move, unsustainable
        3. BLUE_SKY_ATH - All-time high, no resistance above
        4. POWER_TREND - Strong trending move (let it run)
        5. PULLBACK_FLAG - Healthy pullback in uptrend
        6. CHOPPY_SIDEWAYS - Going nowhere (exit soon)

        Args:
            prices: Historical price data
            current_price: Current price
            entry_price: Entry price (if in position)
            days_in_position: Days holding (if in position)
            ma_50: 50-day SMA
            ema_20: 20-day EMA
            rsi: RSI indicator
            week_52_high: 52-week high
            tier: Risk tier (1=Defensive, 2=Core, 3=Speculative)

        Returns:
            (state_name, state_emoji, rationale)
        """
        try:
            # Calculate needed indicators
            highest_high_20 = max(p['high'] for p in prices[-20:]) if len(prices) >= 20 else current_price
            adx = self._calculate_adx(prices)
            sma_slope = self._calculate_sma_slope(prices, 50)
            ema_10 = self._calculate_ema_10(prices)

            # Distance to entry (if we have one)
            entry_distance_pct = 0
            if entry_price and entry_price > 0:
                entry_distance_pct = ((current_price - entry_price) / entry_price * 100)

            # Distance to SMA 50
            sma50_distance_pct = 0
            if ma_50 > 0:
                sma50_distance_pct = ((current_price - ma_50) / ma_50 * 100)

            # STATE 0: DOWNTREND (Radioactive - Avoid or Exit) ▼
            # CRITICAL: Check FIRST if stock is in confirmed downtrend
            # Price < EMA20 < MA50 = broken structure
            if (ema_20 > 0 and
                ma_50 > 0 and
                current_price < ema_20 and
                ema_20 < ma_50):
                return (
                    "DOWNTREND",
                    "▼",
                    f"Broken structure: Price (${current_price:.2f}) < EMA20 (${ema_20:.2f}) < MA50 (${ma_50:.2f}). AVOID or EXIT."
                )

            # Alternative downtrend detection: Price well below both MAs
            if (ma_50 > 0 and
                current_price < ma_50 * 0.97 and  # More than 3% below MA50
                sma_slope < -0.05):  # AND MA50 is falling
                return (
                    "DOWNTREND",
                    "▼",
                    f"Downtrend confirmed: Price {sma50_distance_pct:.1f}% below MA50, MA50 falling. Do NOT enter."
                )

            # STATE 1: ENTRY_BREAKOUT (Highest Risk - Initial Fight) ⊚
            # Only trigger if we have a position AND price is actually trying to break out (positive momentum)
            if (entry_price and
                days_in_position < 10 and
                abs(entry_distance_pct) < 5 and
                entry_distance_pct >= 0):  # Must be at or above entry (not falling)
                return (
                    "ENTRY_BREAKOUT",
                    "⊚",
                    f"Just entered {days_in_position}d ago. Fighting to break out ({entry_distance_pct:+.1f}% from entry). Max risk zone."
                )

            # STATE 2A: MOMENTUM OVERRIDE - "Tortuga Parabólica" ⚠
            # CRITICAL: Detect when a Tier 1/2 (stable stock) starts behaving like Nvidia (vertical move)
            # When a "boring" stock suddenly goes parabolic, it needs parabolic rules regardless of distance to MA50
            #
            # Criteria for "Turtle Going Parabolic":
            # - Tier 1 or 2 (normally stable companies)
            # - ADX > 30 (very strong trend for a defensive stock)
            # - Price > EMA10 > EMA20 (perfect alignment = surfing the wave)
            # - At or near ATH (breaking into new territory)
            #
            # Action: Use EMA 10 as trailing stop (ignore ATR which is too small for vertical moves)
            if (tier <= 2 and  # Only applies to "stable" stocks
                adx > 30 and  # Very strong trend (unusual for Tier 1/2)
                ema_10 > 0 and ema_20 > 0 and
                current_price > ema_10 and ema_10 > ema_20 and  # Perfect alignment
                week_52_high > 0 and current_price >= 0.95 * week_52_high):  # Near/at ATH
                return (
                    "PARABOLIC_CLIMAX",
                    "⚠",
                    f"MOMENTUM OVERRIDE: Tier {tier} stock in vertical move (ADX={adx:.1f}). Price > EMA10 (${ema_10:.2f}) > EMA20. Surf the EMA10, exit if breaks."
                )

            # STATE 2B: PARABOLIC_CLIMAX (Standard Detection - Vertical Euforia) ⚠
            # Tier-specific thresholds for overextension
            climax_threshold = 20 if tier <= 2 else 30
            if (rsi and rsi > 75) or (ma_50 > 0 and sma50_distance_pct > climax_threshold):
                return (
                    "PARABOLIC_CLIMAX",
                    "⚠",
                    f"Vertical move! RSI={rsi or 'N/A'}, {sma50_distance_pct:+.1f}% above MA50. Unsustainable. Lock profits NOW."
                )

            # STATE 3: BLUE_SKY_ATH (All-Time High - No Resistance) ★
            if week_52_high > 0 and current_price >= 0.98 * week_52_high:
                return (
                    "BLUE_SKY_ATH",
                    "★",
                    f"At ATH (${week_52_high:.2f}). No resistance above. Price discovery mode. Use breakout pivot stop."
                )

            # STATE 4: POWER_TREND (Strong Trend - Let It Run) ↑
            # Price > EMA20 > SMA50 AND strong ADX
            if (current_price > ema_20 > 0 and
                ema_20 > ma_50 > 0 and
                adx > 25):
                return (
                    "POWER_TREND",
                    "↑",
                    f"Strong uptrend (ADX={adx:.1f}). Price > EMA20 > MA50. Let winners run with wide stop."
                )

            # STATE 5: PULLBACK_FLAG (Healthy Rest - Give It Air) ◐
            # Price pulled back but still above MA50, volume declining
            if (current_price < highest_high_20 and
                current_price > ma_50 > 0 and
                ma_50 > 0 and
                sma50_distance_pct > 0):
                return (
                    "PULLBACK_FLAG",
                    "◐",
                    f"Healthy pullback. Price < 20d high but > MA50 ({sma50_distance_pct:+.1f}%). Not noise - give it air."
                )

            # STATE 6: CHOPPY_SIDEWAYS (Dead Money - Exit Soon) ↔
            # Flat SMA50 slope AND low ADX
            if abs(sma_slope) < 0.1 and adx < 20:
                return (
                    "CHOPPY_SIDEWAYS",
                    "↔",
                    f"Sideways grind (ADX={adx:.1f}, Slope={sma_slope:.2f}%). Dead money. Exit if > 20 days here."
                )

            # DEFAULT: Analyze technical structure for non-positioned stocks
            # If price is above MA50, it's a pullback candidate
            if current_price > ma_50 > 0:
                return (
                    "PULLBACK_FLAG",
                    "◐",
                    f"Price above MA50 ({sma50_distance_pct:+.1f}%) but no strong trend signal. Monitor for entry."
                )
            # If below MA50 or flat, it's choppy/weak
            else:
                return (
                    "CHOPPY_SIDEWAYS",
                    "↔",
                    f"Weak structure (ADX={adx:.1f}, below MA50). Monitor or avoid. Use tight stops if entering."
                )

        except Exception as e:
            logger.error(f"Error detecting market state: {e}")
            return ("ENTRY_BREAKOUT", "⊚", "Error in state detection, using conservative default.")

    def _calculate_state_aware_stop(
        self,
        state: str,
        tier: int,
        current_price: float,
        atr: float,
        prices: List[Dict],
        ma_50: float = 0,
        ema_10: float = 0,
        swing_low_20: float = 0,
        entry_price: float = None,
        week_52_high: float = 0
    ) -> Tuple[float, str]:
        """
        Calculate stop loss based on detected market state.

        Each state has its own optimal stop strategy:

        STATE 1 - ENTRY_BREAKOUT 🎯:
            Hard Stop = MAX(3x ATR, Breakout Candle Low)
            Logic: If it falls back into base, the breakout failed. Exit immediately.

        STATE 2 - PARABOLIC_CLIMAX 🔥:
            Tight Trailing = MIN(EMA 10, Yesterday's Low)
            Logic: Lock in gains ASAP. This won't last. Ignore tiers.

        STATE 3 - BLUE_SKY_ATH 🌌:
            Breakout Pivot = Old Resistance (which is now support)
            Logic: Use the breakout level as support. If it breaks, rally failed.

        STATE 4 - POWER_TREND 🚀:
            Chandelier Exit = Price - (Multiplier * ATR)
            Tier 1: 2.0x ATR | Tier 2: 3.0x ATR | Tier 3: 3.5x ATR
            Logic: Let winners run. Wide stop to avoid whipsaws.

        STATE 0 - DOWNTREND 💀:
            Exit Stop = Entry price (if in position) OR don't enter
            Logic: Broken technical structure. Exit ASAP if holding. Avoid if not.

        STATE 5 - PULLBACK_FLAG 🚩:
            Structure Hold = MAX(SMA 50, Swing Low 20d)
            Logic: Don't exit on noise. Respect structural support.

        STATE 6 - CHOPPY_SIDEWAYS 💤:
            Range Break = Lowest Low of Range (Swing Low 20d)
            Logic: If range breaks down, exit. Otherwise wait for time-based exit.

        Args:
            state: Market state ('ENTRY_BREAKOUT', 'POWER_TREND', etc.)
            tier: Risk tier (1=Defensive, 2=Core, 3=Speculative)
            current_price: Current price
            atr: 14-day ATR
            prices: Historical price data
            ma_50: 50-day SMA
            ema_10: 10-day EMA
            swing_low_20: 20-day swing low
            entry_price: Entry price (if in position)
            week_52_high: 52-week high

        Returns:
            (stop_price, stop_rationale)
        """
        try:
            if state == "DOWNTREND":
                # Downtrend: Exit if holding, avoid if not
                if entry_price and entry_price > 0:
                    # If in position: Exit at entry price (breakeven) or current - 2% (take the loss)
                    breakeven_stop = entry_price
                    loss_stop = current_price * 0.98
                    stop_price = max(breakeven_stop, loss_stop)  # Try for breakeven, accept 2% loss if needed

                    rationale = f"DOWNTREND detected. Exit at ${stop_price:.2f} (breakeven or -2%). Structure broken, cut losses."
                else:
                    # Not in position: Discourage entry, but if forced, tight 1x ATR stop
                    stop_price = current_price - (1.0 * atr)
                    rationale = f"DOWNTREND: Do NOT enter. If forced, TIGHT stop at ${stop_price:.2f} (1x ATR only). High risk."

                return (stop_price, rationale)

            elif state == "ENTRY_BREAKOUT":
                # Hard Stop: Use 3x ATR or breakout candle low
                atr_stop = current_price - (3.0 * atr)

                # Breakout candle low (assuming last significant low)
                breakout_low = swing_low_20 if swing_low_20 > 0 else atr_stop

                stop_price = max(atr_stop, breakout_low)
                rationale = f"Hard stop at ${stop_price:.2f} (3x ATR or breakout low). If it fails, exit fast."

                return (stop_price, rationale)

            elif state == "PARABOLIC_CLIMAX":
                # 🔥 Parabolic moves require different strategies based on tier:
                # - Tier 1/2 (Tortugas): Anchor to EMA 10 ONLY (ignore ATR/yesterday low)
                #   → Reason: ATR is small on "boring" stocks. EMA 10 is the electric floor.
                # - Tier 3 (Cohetes): Use tightest of EMA 10, yesterday low, or 1.5x ATR
                #   → Reason: High volatility stocks can gap down. Need yesterday low protection.

                if tier <= 2:
                    # "TORTUGA PARABÓLICA" MODE: Surf the EMA 10
                    # "Olvida el ATR. Olvida la SMA 50. Tu único Dios ahora es la EMA 10."
                    if ema_10 > 0 and ema_10 < current_price:
                        stop_price = ema_10 * 0.995  # Small 0.5% buffer below EMA 10
                    else:
                        # Fallback if EMA 10 not available
                        stop_price = current_price - (1.5 * atr)

                    # Ensure stop is never above current price
                    stop_price = min(stop_price, current_price * 0.98)

                    distance_pct = ((current_price - stop_price) / current_price) * 100
                    rationale = f"PARABOLIC Tier {tier}: Surfing EMA10 at ${stop_price:.2f} (-{distance_pct:.1f}%). Exit ONLY if breaks EMA10."

                else:
                    # "COHETE PARABÓLICO" MODE: Use tightest stop (EMA 10, yesterday low, or 1.5x ATR)
                    yesterday_low = prices[-1]['low'] if prices else current_price * 0.97
                    tight_atr_stop = current_price - (1.5 * atr)

                    # Use tighter of EMA 10, yesterday's low, or 1.5x ATR (all must be below price)
                    candidates = []
                    if ema_10 > 0 and ema_10 < current_price:
                        candidates.append(ema_10)
                    if yesterday_low < current_price:
                        candidates.append(yesterday_low)
                    candidates.append(tight_atr_stop)

                    stop_price = max(candidates)  # Use highest (but still below current price)

                    # Add small 0.3% buffer to avoid false triggers
                    stop_price = stop_price * 0.997

                    # Ensure stop is never above current price
                    stop_price = min(stop_price, current_price * 0.98)

                    rationale = f"TIGHT stop at ${stop_price:.2f} (EMA10/yesterday low/1.5xATR). Lock profits NOW!"

                return (stop_price, rationale)

            elif state == "BLUE_SKY_ATH":
                # 🌌 At All-Time High: CRITICAL - Breakouts almost ALWAYS retest
                # NEVER put stop at exact breakout level. Use volatility buffer.

                # Old ATH becomes support REFERENCE (not the stop itself)
                ath_support = week_52_high * 0.98 if week_52_high > 0 else current_price * 0.95

                # Buffer for retest: Subtract 1 ATR minimum (more for high-vol stocks)
                # Tier 1: 1.0x ATR | Tier 2: 1.25x ATR | Tier 3: 1.5x ATR
                # Rule: "In Tier 3, never < 1 ATR distance unless emergency exit"
                atr_buffers = {1: 1.0, 2: 1.25, 3: 1.5}
                atr_buffer_multiplier = atr_buffers.get(tier, 1.0)

                ath_with_buffer = ath_support - (atr_buffer_multiplier * atr)

                # Alternative: EMA 10 (key trend anchor for ATH breakouts)
                ema_10_stop = ema_10 * 0.995 if ema_10 > 0 and ema_10 < current_price else current_price * 0.90

                # Use whichever is CLOSER to current price (more conservative)
                # This allows EMA 10 to override if it's tighter but still reasonable
                stop_price = max(ath_with_buffer, ema_10_stop)

                # Ensure never above price (safety check)
                if stop_price >= current_price:
                    stop_price = current_price * 0.95  # Fallback to -5% if calculation error

                # Distance for reporting
                distance_pct = ((current_price - stop_price) / current_price) * 100

                rationale = f"ATH breakout w/ retest buffer at ${stop_price:.2f} (-{distance_pct:.1f}%). Using EMA10 or ATH-{atr_buffer_multiplier}xATR. Allow natural pullback."

                return (stop_price, rationale)

            elif state == "POWER_TREND":
                # Chandelier Exit: Tier-specific wide stops
                # Tier 1: 2.0x | Tier 2: 3.0x | Tier 3: 3.5x
                multipliers = {1: 2.0, 2: 3.0, 3: 3.5}
                multiplier = multipliers.get(tier, 3.0)

                stop_price = current_price - (multiplier * atr)

                rationale = f"Chandelier stop at ${stop_price:.2f} ({multiplier}x ATR). Let the trend run!"

                return (stop_price, rationale)

            elif state == "PULLBACK_FLAG":
                # FIX #11: Don't use too-tight stops for high volatility stocks
                # Problem: MA50 might be very close to price, but volatility is high
                # Solution: Use WIDEST of MA50, SwingLow20, or volatility-based minimum

                # Calculate volatility-based minimum stop distance
                # Rule: Min stop distance = 2.5x ATR for vol > 40%, 2.0x ATR for vol > 30%, 1.5x ATR otherwise
                if volatility > 40:
                    min_atr_multiplier = 2.5
                elif volatility > 30:
                    min_atr_multiplier = 2.0
                else:
                    min_atr_multiplier = 1.5

                volatility_floor = current_price - (min_atr_multiplier * atr)

                # Structure Hold: SMA 50 or Swing Low 20d
                # Give it air - don't exit on healthy pullbacks
                candidates = [volatility_floor]  # Always include volatility floor

                if ma_50 > 0 and ma_50 < current_price:
                    candidates.append(ma_50)
                if swing_low_20 > 0 and swing_low_20 < current_price:
                    candidates.append(swing_low_20)

                # Use LOWEST (widest stop) to give stock breathing room
                structure_support = min(candidates)

                # Add 0.5% buffer
                stop_price = structure_support * 0.995

                # Calculate actual distance for rationale
                stop_distance_pct = ((current_price - stop_price) / current_price) * 100

                rationale = f"Structure hold at ${stop_price:.2f} (-{stop_distance_pct:.1f}%). " \
                           f"Using widest of MA50/SwingLow20/{min_atr_multiplier}xATR (vol={volatility:.0f}%). " \
                           f"Give pullback air to breathe."

                return (stop_price, rationale)

            elif state == "CHOPPY_SIDEWAYS":
                # Range Break: Swing Low 20d (exit if range breaks)
                if swing_low_20 > 0:
                    stop_price = swing_low_20 * 0.995  # 0.5% buffer
                else:
                    # Fallback to tight 2x ATR
                    stop_price = current_price - (2.0 * atr)

                rationale = f"Range break stop at ${stop_price:.2f}. Exit if breaks range OR after 20 days sideways."

                return (stop_price, rationale)

            else:
                # Default fallback (shouldn't happen)
                stop_price = current_price - (2.5 * atr)
                rationale = f"Default stop at ${stop_price:.2f}"
                return (stop_price, rationale)

        except Exception as e:
            logger.error(f"Error calculating state-aware stop: {e}")
            # Safe fallback
            return (current_price - (2.5 * atr), "Error - using 2.5x ATR fallback")

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
        # Tier configurations (RISK-BASED: volatility + beta classification)
        TIER_1_CONFIG = {
            'name': 'RISK TIER 1: Defensivo 🐢',
            'initial_multiplier': 1.8,
            'trailing_multiplier': 2.0,
            'hard_cap_pct': 8.0,
            'anchor': 'SMA 50',
            'description': 'Low volatility, stable price movement'
        }

        TIER_2_CONFIG = {
            'name': 'RISK TIER 2: Core Growth 🏃',
            'initial_multiplier': 2.5,
            'trailing_multiplier': 3.0,
            'hard_cap_pct': 15.0,
            'anchor': 'Swing Low 10d',
            'description': 'Moderate volatility, balanced risk/reward'
        }

        TIER_3_CONFIG = {
            'name': 'RISK TIER 3: Especulativo 🚀',
            'initial_multiplier': 3.0,
            'trailing_multiplier': 3.5,
            'hard_cap_pct': 25.0,
            'anchor': 'EMA 20',
            'description': 'High volatility, aggressive trading'
        }

        # Classification logic
        if beta is not None:
            # Use Beta + Volatility Matrix (preferred)
            if beta < 0.95 and volatility < 20:  # STRICTER: was 25, now 20
                return 1, TIER_1_CONFIG['name'], TIER_1_CONFIG
            elif beta > 1.15 or volatility > 45:
                return 3, TIER_3_CONFIG['name'], TIER_3_CONFIG
            else:
                return 2, TIER_2_CONFIG['name'], TIER_2_CONFIG
        else:
            # Fallback: Use Volatility only
            if volatility < 20:  # STRICTER: was 25, now 20
                tier = 1
                config = TIER_1_CONFIG
            elif volatility > 45:
                tier = 3
                config = TIER_3_CONFIG
            else:
                tier = 2
                config = TIER_2_CONFIG

            # Sector adjustments (heuristic)
            defensive_sectors = ['Utilities', 'Consumer Defensive', 'Consumer Staples', 'Healthcare']
            speculative_sectors = ['Technology', 'Communication Services', 'Energy']
            big_tech_sectors = ['Technology', 'Communication Services']  # Big Tech is ALWAYS Tier 2

            # PRIORITY 1: Big Tech override (MSFT, GOOGL, AAPL, etc.)
            # Big Tech should NEVER be Tier 1, even with low volatility
            if sector in big_tech_sectors and tier == 1 and volatility >= 20:
                tier = 2
                config = TIER_2_CONFIG

            # PRIORITY 2: Force defensive sectors to Tier 1
            if sector in defensive_sectors and tier > 1 and volatility < 20:
                tier = 1
                config = TIER_1_CONFIG

            # PRIORITY 3: Force speculative sectors to Tier 3 if high volatility
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

            # ========== STEP 4: STATE MACHINE - Detect Market State & Calculate Stop ==========
            # 🧠 This is the brain: detect what the stock is doing NOW and adapt strategy

            # Special check: Zombie Killer (dead money override - highest priority)
            if entry_price and entry_price > 0 and days_in_position > 20:
                current_gain_pct = ((current_price - entry_price) / entry_price * 100)
                if abs(current_gain_pct) < 2:
                    # Override everything - this is dead money
                    market_state = "CHOPPY_SIDEWAYS"
                    state_emoji = "↔"
                    active_stop_price = max(entry_price, swing_low_20 if swing_low_20 > 0 else swing_low_10)
                    active_stop_pct = ((active_stop_price - current_price) / current_price * 100)
                    state_rationale = f"ZOMBIE KILLER: Dead money for {days_in_position} days. Exit at ${active_stop_price:.2f} or NOW."
                else:
                    # Not zombie - detect normal state
                    market_state, state_emoji, state_rationale = self._detect_market_state(
                        prices, current_price, entry_price, days_in_position,
                        ma_50, ema_20, rsi, week_52_high, tier_num
                    )

                    # Calculate stop based on detected state
                    active_stop_price, stop_rationale = self._calculate_state_aware_stop(
                        market_state, tier_num, current_price, atr_14, prices,
                        ma_50, ema_10, swing_low_20, entry_price, week_52_high
                    )
                    active_stop_pct = ((active_stop_price - current_price) / current_price * 100)
                    state_rationale = f"{state_rationale} | {stop_rationale}"
            else:
                # No entry price or recent entry - detect state
                market_state, state_emoji, state_rationale = self._detect_market_state(
                    prices, current_price, entry_price, days_in_position,
                    ma_50, ema_20, rsi, week_52_high, tier_num
                )

                # Calculate stop based on detected state
                active_stop_price, stop_rationale = self._calculate_state_aware_stop(
                    market_state, tier_num, current_price, atr_14, prices,
                    ma_50, ema_10, swing_low_20, entry_price, week_52_high
                )
                active_stop_pct = ((active_stop_price - current_price) / current_price * 100)
                state_rationale = f"{state_rationale} | {stop_rationale}"

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

                # Market State (State Machine)
                'market_state': market_state,
                'state_emoji': state_emoji,
                'state_rationale': state_rationale,

                # Backward compatibility
                'lifecycle_phase': f"{market_state} {state_emoji}",
                'lifecycle_note': state_rationale,

                # Active Stop (The one to use NOW)
                'active_stop': {
                    'price': f'${active_stop_price:.2f}',
                    'distance': f'{active_stop_pct:.1f}%',
                    'rationale': state_rationale
                },

                # Numeric fields for risk-based position sizing calculations
                'stop_loss_pct': abs(active_stop_pct),  # Absolute distance to stop (e.g., 5.1 from -5.1%)
                'current_price': current_price,  # Current stock price for share calculation

                # Base Parameters (State Machine uses additional indicators)
                'parameters': {
                    'atr_14': round(atr_14, 2),
                    'highest_high_22': round(highest_high_22, 2),
                    'swing_low_10': round(swing_low_10, 2),
                    'swing_low_20': round(swing_low_20, 2),  # More robust
                    'ema_20': round(ema_20, 2) if ema_20 > 0 else 'N/A',
                    'ema_10': round(ema_10, 2) if ema_10 > 0 else 'N/A',  # For climax stops
                    'adx': round(self._calculate_adx(prices), 1),  # Trend strength
                    'sma_slope': round(self._calculate_sma_slope(prices, 50), 3),  # Trend direction
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
                    f"🧠 State Machine: {market_state} {state_emoji}",
                    state_rationale,
                    "Context-aware stops: 6 states (ENTRY_BREAKOUT, POWER_TREND, PARABOLIC_CLIMAX, BLUE_SKY_ATH, PULLBACK_FLAG, CHOPPY_SIDEWAYS)",
                    "Each state uses optimal stop strategy for current market conditions",
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
            stop = max(hard_cap_stop, atr_stop)
            # CRITICAL: Stop loss MUST be below current price
            return min(stop, price * 0.99)

        elif phase == 'trailing':
            # Trailing Phase: Long-term anchors with 0.5% buffer
            # Buffer prevents algorithmic stop hunting
            buffer = 0.995  # 0.5% buffer

            if tier == 1:
                # Tier 1 (Defensive): Use SMA 50
                anchor = (ma_50 * buffer) if ma_50 > 0 and ma_50 < price else price * 0.92
            elif tier == 2:
                # Tier 2 (Core Growth): Use Swing Low 20d (more robust than 10d)
                anchor = (swing_low_20 * buffer) if swing_low_20 > 0 and swing_low_20 < price else price * 0.85
            else:  # tier == 3
                # Tier 3 (Speculative): Use EMA 10 (faster response)
                anchor = (ema_10 * buffer) if ema_10 > 0 and ema_10 < price else price * 0.75

            stop = max(hard_cap_stop, atr_stop, anchor)
            # CRITICAL: Stop loss MUST be below current price
            return min(stop, price * 0.99)

        elif phase == 'climax':
            # Climax Phase: Tight EMA 10 with 0.75% buffer
            # Protect profits but allow for normal pullback
            buffer = 0.9925  # 0.75% buffer
            ema_stop = (ema_10 * buffer) if ema_10 > 0 and ema_10 < price else price * 0.95
            tight_atr = price - (1.5 * atr)  # Tighter than normal

            stop = max(tight_atr, ema_stop)
            # CRITICAL: Stop loss MUST be below current price
            return min(stop, price * 0.98)

        else:
            # Breakeven/zombie phases handled in main method
            # Fallback to simple calculation
            stop = max(hard_cap_stop, atr_stop)
            # CRITICAL: Stop loss MUST be below current price
            return min(stop, price * 0.99)

    def _generate_profit_targets(self, signal, distance_ma200, overextension_risk, ma_200, price,
                                  fundamental_score=None, guardrails_status=None, market_state=None,
                                  stop_loss_pct=None):
        """
        Professional asymmetric Take Profit strategies based on company quality tier.

        Philosophy: Different companies require different exit strategies.
        - Compounders (Tier 1): Hold forever with trailing stop
        - Quality Value (Tier 2): Swing trade with 3R rule
        - Speculative (Tier 3): Aggressive scaling out with 2R rule

        Args:
            fundamental_score: Quality score (0-100) to determine tier
            guardrails_status: VERDE/AMBAR/ROJO for tier classification
            market_state: Current market state (PARABOLIC_CLIMAX, POWER_TREND, etc.)
            stop_loss_pct: Stop loss percentage (e.g., -5.1%) for R calculation
        """
        if signal == 'SELL':
            return {'strategy': 'NO POSITION', 'tier': 'N/A', 'targets': []}

        # ========== DETERMINE QUALITY TIER ==========
        tier = self._determine_quality_tier(fundamental_score, guardrails_status)

        # Calculate R (Risk per share) for R-multiple targets
        # R = Distance from entry to stop loss
        risk_pct = abs(stop_loss_pct) if stop_loss_pct else 10.0  # Default 10% if not available

        # ========== EMERGENCY OVERRIDE: PARABOLIC_CLIMAX ==========
        # Regardless of tier, if in parabolic climax, take immediate action
        if market_state == 'PARABOLIC_CLIMAX' or overextension_risk >= 5:
            return {
                'strategy': '🔥 EMERGENCY EXIT (Parabolic Climax Detected)',
                'tier': tier,
                'tier_name': self._get_tier_name(tier),
                'market_state': market_state,
                'action': 'SELL 50-75% NOW',
                'targets': [
                    {
                        'level': 'TP1 (NOW)',
                        'percent': 50,
                        'price': price,
                        'rationale': 'Parabolic climax detected - extreme euphoria unsustainable'
                    },
                    {
                        'level': 'TP2 (+5-10%)',
                        'percent': 25,
                        'price': price * 1.075,
                        'rationale': 'Final squeeze before reversal - sell into strength'
                    }
                ],
                'keep_pct': 25,
                'keep_stop': 'Very tight stop (EMA 10 or -5% from highs)',
                'rationale': f'🔥 PARABOLIC CLIMAX: {distance_ma200:+.1f}% above MA200. History shows violent reversals follow parabolic moves. "Bulls make money, bears make money, pigs get slaughtered."',
                'override': True
            }

        # ========== TIER 1: THE COMPOUNDER (Elite Companies) ==========
        if tier == 1:
            # Exception: Reduce position slightly if market becomes euphoric
            if overextension_risk >= 3 and distance_ma200 > 30:
                return {
                    'strategy': 'THE COMPOUNDER (Light Trim Only)',
                    'tier': tier,
                    'tier_name': 'TIER 1 - Elite Compounder',
                    'philosophy': '"Let winners run" - The biggest mistake is selling great companies too early',
                    'take_profit_fixed': 'NONE',
                    'action': 'TRIM 10-20% ONLY (Optional)',
                    'targets': [
                        {
                            'level': 'Optional Trim',
                            'percent': '10-20%',
                            'price': price,
                            'rationale': 'Mild overextension - trim to rebalance, NOT to exit'
                        }
                    ],
                    'keep_pct': '80-90%',
                    'keep_stop': 'SMA 50 or SMA 200 (wide trailing stop)',
                    'rationale': f'Elite companies (score: {fundamental_score:.0f}) compound wealth over decades. Amazon/Costco/Microsoft owners who sold at "+50%" missed 1000%+ gains. Only trim for rebalancing.',
                    'examples': 'Amazon +150,000% (1997-2024), Costco +52,000%, Microsoft +288,000%',
                    'override': False
                }
            else:
                # Normal case: hold with trailing stop
                return {
                    'strategy': 'THE COMPOUNDER (Hold with Trailing Stop)',
                    'tier': tier,
                    'tier_name': 'TIER 1 - Elite Compounder',
                    'philosophy': '"Let winners run" - Never sell a great company in a bull market',
                    'take_profit_fixed': 'NONE',
                    'action': 'HOLD (No selling)',
                    'targets': [],
                    'keep_pct': 100,
                    'keep_stop': 'SMA 50 or SMA 200 trailing stop',
                    'exit_only_if': [
                        'SMA 50 crosses below SMA 200 (Death Cross)',
                        'Fundamental deterioration (M-Score spike, insider selling surge)',
                        'Business model disruption (new technology, regulation)'
                    ],
                    'rationale': f'Elite company (score: {fundamental_score:.0f}, {guardrails_status}). These are "forever holds" barring fundamental changes. Market will scare you out - don\'t let it.',
                    'examples': 'Holding Nvidia since 2020 = +2000%. Holding Microsoft since 2010 = +1200%',
                    'override': False
                }

        # ========== TIER 2: THE SWING (Quality at Reasonable Price) ==========
        elif tier == 2:
            # Calculate 3R target (3 times the risk)
            tp1_price = price * (1 + (risk_pct * 3) / 100)

            return {
                'strategy': 'THE SWING (3R Rule)',
                'tier': tier,
                'tier_name': 'TIER 2 - Quality Value Momentum',
                'philosophy': '"Pay the risk, let the rest run" - Lock in gains while keeping upside',
                'take_profit_rule': '3R (3 times Risk)',
                'risk_r': f'{risk_pct:.1f}%',
                'action': 'Partial scaling at targets',
                'targets': [
                    {
                        'level': f'TP1 (3R = {risk_pct*3:.0f}%)',
                        'percent': 33,
                        'price': tp1_price,
                        'r_multiple': 3,
                        'rationale': 'Secured 3x your risk - now playing with house money'
                    }
                ],
                'keep_pct': 67,
                'keep_stop': 'Move stop to breakeven, then trailing stop (SMA 50 or -12% from highs)',
                'rationale': f'Quality company (score: {fundamental_score:.0f}) but not elite. Use 3R rule to lock gains while letting 2/3 run. If reaches 3R ({tp1_price:.2f}), you\'ve already won.',
                'free_ride': 'After TP1, remaining position is "free" (zero risk)',
                'override': False
            }

        # ========== TIER 3: THE SNIPER (Speculative / Lower Quality) ==========
        else:  # tier == 3
            # Calculate 2R and 4R targets
            tp1_price = price * (1 + (risk_pct * 2) / 100)
            tp2_price = price * (1 + (risk_pct * 4) / 100)

            # Additional aggressive exit if RSI > 80 or extreme overextension
            aggressive_exit = overextension_risk >= 3 or distance_ma200 > 25

            return {
                'strategy': 'THE SNIPER (Aggressive Scaling)',
                'tier': tier,
                'tier_name': 'TIER 3 - Speculative',
                'philosophy': '"The last dollar, let someone else make it" - Greed kills in speculative trades',
                'take_profit_rule': '2R/4R Ladder',
                'risk_r': f'{risk_pct:.1f}%',
                'action': 'AGGRESSIVE SCALING OUT',
                'targets': [
                    {
                        'level': f'TP1 (2R = {risk_pct*2:.0f}%)',
                        'percent': 50,
                        'price': tp1_price,
                        'r_multiple': 2,
                        'rationale': 'Recover capital fast - speculative trades reverse quickly'
                    },
                    {
                        'level': f'TP2 (4R = {risk_pct*4:.0f}%)',
                        'percent': 25,
                        'price': tp2_price,
                        'r_multiple': 4,
                        'rationale': 'Lock in further gains - don\'t get greedy'
                    }
                ],
                'keep_pct': 25,
                'keep_stop': 'VERY TIGHT: EMA 10 or -5% from highs (Moonbag)',
                'rationale': f'Speculative stock (score: {f"{fundamental_score:.0f}" if fundamental_score is not None else "N/A"}, {guardrails_status}). These "go up the elevator, down the window". Take profits aggressively.',
                'warning': 'If RSI > 80 or parabolic move, sell 75-100% IMMEDIATELY' if aggressive_exit else None,
                'override': False
            }

    def _determine_quality_tier(self, fundamental_score, guardrails_status):
        """
        Determine company quality tier for Take Profit strategy selection.

        Tier 1 (Compounder): Elite companies with moats - hold forever
        Tier 2 (Swing): Quality companies - swing trade with 3R
        Tier 3 (Sniper): Speculative - aggressive scaling with 2R

        Returns: 1, 2, or 3
        """
        # Default to Tier 3 if no fundamental data
        if fundamental_score is None:
            return 3

        # Tier 1: Elite Compounders (Score > 85 AND VERDE guardrails)
        if fundamental_score >= 85 and guardrails_status == 'VERDE':
            return 1

        # Tier 1: Also include ultra-high quality even with AMBAR (score > 90)
        if fundamental_score >= 90:
            return 1

        # Tier 2: High Quality (Score 70-85 OR Score > 85 with AMBAR)
        if fundamental_score >= 70:
            return 2

        # Tier 2: Medium quality with clean guardrails (Score 60-70 AND VERDE)
        if fundamental_score >= 60 and guardrails_status == 'VERDE':
            return 2

        # Tier 3: Everything else (Speculative)
        return 3

    def _get_tier_name(self, tier):
        """Get human-readable tier name for QUALITY-BASED classification."""
        tier_names = {
            1: 'QUALITY TIER 1 - Elite Compounder',
            2: 'QUALITY TIER 2 - Quality Value Momentum',
            3: 'QUALITY TIER 3 - Speculative'
        }
        return tier_names.get(tier, 'Unknown')

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
