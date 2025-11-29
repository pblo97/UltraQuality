"""
Market Timing Dashboard.

Analyzes macro market conditions:
- % of stocks overextended
- Sector overextension breakdown
- VIX and fear/greed
- Market breadth (advancers vs decliners)
- SPY vs MA200
"""

from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class MarketTimingAnalyzer:
    """
    Analyze macro market conditions for timing decisions.
    """

    def __init__(self, fmp_client):
        """
        Args:
            fmp_client: FMP client for market data
        """
        self.fmp = fmp_client

    def analyze_market_overextension(
        self,
        stocks_list: List[str]
    ) -> Dict:
        """
        Analyze what % of stocks are overextended.

        Args:
            stocks_list: List of stock symbols to analyze

        Returns:
            {
                'overextended_pct': float,  # % >40% above MA200
                'extreme_pct': float,  # % >60% above MA200
                'total_analyzed': int,
                'by_level': {
                    'extreme': int,
                    'high': int,
                    'medium': int,
                    'low': int
                }
            }
        """
        extreme_count = 0
        high_count = 0
        medium_count = 0
        low_count = 0
        total = 0

        for symbol in stocks_list:
            try:
                quote = self.fmp.get_quote(symbol)
                if not quote or len(quote) == 0:
                    continue

                q = quote[0]
                price = q.get('price', 0)
                ma_200 = q.get('priceAvg200', 0)

                if price > 0 and ma_200 > 0:
                    distance = ((price - ma_200) / ma_200 * 100)
                    total += 1

                    if distance > 60:
                        extreme_count += 1
                    elif distance > 40:
                        high_count += 1
                    elif distance > 30:
                        medium_count += 1
                    else:
                        low_count += 1

            except Exception as e:
                logger.debug(f"Error analyzing {symbol}: {e}")
                continue

        if total == 0:
            return {'error': 'No stocks analyzed successfully'}

        overextended_pct = ((high_count + extreme_count) / total * 100)
        extreme_pct = (extreme_count / total * 100)

        return {
            'overextended_pct': round(overextended_pct, 1),
            'extreme_pct': round(extreme_pct, 1),
            'total_analyzed': total,
            'by_level': {
                'extreme': extreme_count,
                'high': high_count,
                'medium': medium_count,
                'low': low_count
            },
            'recommendation': self._get_market_recommendation(overextended_pct, extreme_pct)
        }

    def _get_market_recommendation(self, overextended_pct: float, extreme_pct: float) -> Dict:
        """
        Generate market timing recommendation based on overextension %.

        Args:
            overextended_pct: % of stocks >40% above MA200
            extreme_pct: % of stocks >60% above MA200

        Returns:
            {
                'stance': str,
                'cash_pct': str,
                'message': str
            }
        """
        if extreme_pct > 25 or overextended_pct > 50:
            return {
                'stance': 'DEFENSIVE',
                'cash_pct': '40-60%',
                'message': f'🔴 EXTREME overextension ({overextended_pct:.1f}% of stocks >40% extended). Market correction likely. Raise cash, tighten stops.'
            }
        elif extreme_pct > 15 or overextended_pct > 35:
            return {
                'stance': 'CAUTIOUS',
                'cash_pct': '20-30%',
                'message': f'🟡 HIGH overextension ({overextended_pct:.1f}%). Be selective, prefer quality over momentum.'
            }
        elif extreme_pct > 5 or overextended_pct > 20:
            return {
                'stance': 'NEUTRAL',
                'cash_pct': '10-20%',
                'message': f'🟢 MODERATE overextension ({overextended_pct:.1f}%). Normal bull market conditions.'
            }
        else:
            return {
                'stance': 'AGGRESSIVE',
                'cash_pct': '0-10%',
                'message': f'🟢 LOW overextension ({overextended_pct:.1f}%). Market healthy, opportunity to deploy capital.'
            }

    def analyze_sector_overextension(
        self,
        sectors: List[str] = None
    ) -> Dict:
        """
        Analyze overextension by sector.

        Args:
            sectors: List of sector names (defaults to major sectors)

        Returns:
            {
                'Technology': {'distance_ma200': X, 'level': 'HIGH'},
                'Healthcare': {...},
                ...
            }
        """
        if sectors is None:
            sectors = [
                'Technology',
                'Healthcare',
                'Financials',
                'Consumer Cyclical',
                'Consumer Defensive',
                'Energy',
                'Industrials',
                'Basic Materials',
                'Real Estate',
                'Communication Services',
                'Utilities'
            ]

        sector_etfs = {
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
            'Utilities': 'XLU'
        }

        sector_analysis = {}

        for sector in sectors:
            etf = sector_etfs.get(sector)
            if not etf:
                continue

            try:
                quote = self.fmp.get_quote(etf)
                if not quote or len(quote) == 0:
                    continue

                q = quote[0]
                price = q.get('price', 0)
                ma_200 = q.get('priceAvg200', 0)

                if price > 0 and ma_200 > 0:
                    distance = ((price - ma_200) / ma_200 * 100)

                    if distance > 40:
                        level = 'HIGH'
                    elif distance > 30:
                        level = 'MEDIUM'
                    else:
                        level = 'LOW'

                    sector_analysis[sector] = {
                        'distance_ma200': round(distance, 1),
                        'level': level,
                        'etf': etf,
                        'price': price,
                        'ma_200': ma_200
                    }

            except Exception as e:
                logger.debug(f"Error analyzing sector {sector}: {e}")
                continue

        # Sort by distance descending
        sector_analysis = dict(sorted(
            sector_analysis.items(),
            key=lambda x: x[1]['distance_ma200'],
            reverse=True
        ))

        return sector_analysis

    def get_vix_analysis(self) -> Dict:
        """
        Analyze VIX (volatility index) for fear/greed.

        Returns:
            {
                'vix': float,
                'level': str,
                'market_sentiment': str,
                'recommendation': str
            }
        """
        try:
            vix_quote = self.fmp.get_quote('^VIX')

            if not vix_quote or len(vix_quote) == 0:
                return {'error': 'VIX data not available'}

            vix = vix_quote[0].get('price', 20)

            if vix > 40:
                level = 'EXTREME FEAR'
                sentiment = 'PANIC'
                recommendation = '🟢 Contrarian BUY opportunity - Extreme fear creates opportunity'
            elif vix > 30:
                level = 'HIGH FEAR'
                sentiment = 'FEAR'
                recommendation = '🟡 Market stress elevated - Be selective, wait for stabilization'
            elif vix > 20:
                level = 'ELEVATED'
                sentiment = 'CAUTION'
                recommendation = '🟡 Moderate volatility - Normal risk management'
            elif vix > 15:
                level = 'NORMAL'
                sentiment = 'NEUTRAL'
                recommendation = '🟢 Normal conditions - Standard deployment'
            else:
                level = 'COMPLACENCY'
                sentiment = 'GREED'
                recommendation = '🔴 LOW VIX = Complacency. Prepare for volatility spike'

            return {
                'vix': round(vix, 2),
                'level': level,
                'market_sentiment': sentiment,
                'recommendation': recommendation
            }

        except Exception as e:
            logger.error(f"Error analyzing VIX: {e}")
            return {'error': str(e)}

    def get_market_breadth(self) -> Dict:
        """
        Analyze market breadth.

        Using SPY vs sector ETFs as proxy for breadth.

        Returns:
            {
                'sectors_above_ma200': int,
                'sectors_total': int,
                'breadth_pct': float,
                'health': str
            }
        """
        sector_analysis = self.analyze_sector_overextension()

        sectors_above = sum(1 for s in sector_analysis.values() if s['distance_ma200'] > 0)
        total_sectors = len(sector_analysis)

        if total_sectors == 0:
            return {'error': 'No sector data available'}

        breadth_pct = (sectors_above / total_sectors * 100)

        if breadth_pct >= 80:
            health = 'EXCELLENT'
            message = f'🟢 Strong breadth ({breadth_pct:.0f}% sectors above MA200) - Healthy bull market'
        elif breadth_pct >= 60:
            health = 'GOOD'
            message = f'🟢 Good breadth ({breadth_pct:.0f}% sectors above MA200) - Broad participation'
        elif breadth_pct >= 40:
            health = 'MIXED'
            message = f'🟡 Mixed breadth ({breadth_pct:.0f}% sectors above MA200) - Selective market'
        else:
            health = 'WEAK'
            message = f'🔴 Weak breadth ({breadth_pct:.0f}% sectors above MA200) - Defensive posture recommended'

        return {
            'sectors_above_ma200': sectors_above,
            'sectors_total': total_sectors,
            'breadth_pct': round(breadth_pct, 1),
            'health': health,
            'message': message
        }

    def get_comprehensive_market_analysis(
        self,
        stocks_list: List[str] = None
    ) -> Dict:
        """
        Get comprehensive market timing analysis.

        Args:
            stocks_list: Optional list of stocks to analyze for overextension

        Returns:
            Complete market timing dashboard data
        """
        analysis = {}

        # SPY analysis
        try:
            spy_quote = self.fmp.get_quote('SPY')
            if spy_quote and len(spy_quote) > 0:
                spy = spy_quote[0]
                spy_price = spy.get('price', 0)
                spy_ma200 = spy.get('priceAvg200', 0)

                if spy_price > 0 and spy_ma200 > 0:
                    spy_distance = ((spy_price - spy_ma200) / spy_ma200 * 100)
                    analysis['spy'] = {
                        'price': spy_price,
                        'ma_200': spy_ma200,
                        'distance_ma200': round(spy_distance, 1),
                        'trend': 'BULL' if spy_distance > 0 else 'BEAR'
                    }
        except Exception as e:
            logger.error(f"Error analyzing SPY: {e}")

        # VIX analysis
        analysis['vix'] = self.get_vix_analysis()

        # Market breadth
        analysis['breadth'] = self.get_market_breadth()

        # Sector analysis
        analysis['sectors'] = self.analyze_sector_overextension()

        # Overextension analysis (if stocks provided)
        if stocks_list:
            analysis['overextension'] = self.analyze_market_overextension(stocks_list)

        # Overall recommendation
        analysis['overall_recommendation'] = self._get_overall_recommendation(analysis)

        return analysis

    def _get_overall_recommendation(self, analysis: Dict) -> Dict:
        """
        Generate overall market timing recommendation.

        Args:
            analysis: Complete market analysis

        Returns:
            {
                'stance': str,
                'confidence': str,
                'key_factors': List[str],
                'action': str
            }
        """
        key_factors = []
        risk_score = 0  # Higher = more defensive

        # SPY trend
        spy_data = analysis.get('spy', {})
        if spy_data.get('trend') == 'BEAR':
            risk_score += 3
            key_factors.append(f"🔴 SPY in downtrend ({spy_data.get('distance_ma200', 0):+.1f}% from MA200)")
        elif spy_data.get('distance_ma200', 0) > 10:
            risk_score += 1
            key_factors.append(f"🟡 SPY extended ({spy_data.get('distance_ma200'):+.1f}% from MA200)")

        # VIX
        vix_data = analysis.get('vix', {})
        vix = vix_data.get('vix', 20)
        if vix > 30:
            risk_score += 2
            key_factors.append(f"🔴 High VIX ({vix:.1f}) - Market stress")
        elif vix < 15:
            risk_score += 1
            key_factors.append(f"🟡 Low VIX ({vix:.1f}) - Complacency risk")

        # Breadth
        breadth_data = analysis.get('breadth', {})
        breadth_pct = breadth_data.get('breadth_pct', 50)
        if breadth_pct < 40:
            risk_score += 2
            key_factors.append(f"🔴 Weak breadth ({breadth_pct:.0f}%)")

        # Overextension
        overext_data = analysis.get('overextension', {})
        if 'overextended_pct' in overext_data:
            overext_pct = overext_data['overextended_pct']
            if overext_pct > 40:
                risk_score += 3
                key_factors.append(f"🔴 {overext_pct:.0f}% of stocks overextended")
            elif overext_pct > 25:
                risk_score += 1
                key_factors.append(f"🟡 {overext_pct:.0f}% of stocks overextended")

        # Determine stance
        if risk_score >= 7:
            stance = 'DEFENSIVE'
            confidence = 'HIGH'
            action = 'Raise cash to 40-60%, tighten stops, sell overextended positions'
        elif risk_score >= 5:
            stance = 'CAUTIOUS'
            confidence = 'MEDIUM'
            action = 'Raise cash to 20-30%, be selective, avoid chasing'
        elif risk_score >= 3:
            stance = 'NEUTRAL'
            confidence = 'MEDIUM'
            action = 'Maintain 10-20% cash, normal risk management'
        else:
            stance = 'BULLISH'
            confidence = 'HIGH'
            action = 'Deploy capital, buy quality pullbacks, low cash (0-10%)'

        return {
            'stance': stance,
            'confidence': confidence,
            'risk_score': risk_score,
            'key_factors': key_factors,
            'action': action
        }
