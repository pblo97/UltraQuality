"""
Análisis Técnico Basado en Evidencia (2024)

Implementa solo indicadores con evidencia académica sólida:
- Momentum 12M (Jegadeesh & Titman 1993, Moskowitz 2012)
- Sector Relative Strength (Bretscher 2023, Arnott 2024)
- Trend MA200 (Brock et al. 1992)
- Volume confirmation (básico)

NO incluye: RSI, MACD, Stochastic, Fibonacci (sin evidencia post-2010)
"""

from typing import Dict, Optional, List
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class TechnicalAnalyzer:
    """
    Análisis técnico minimalista y basado en evidencia.

    Score: 0-100
    - 35 pts: Momentum 12 meses individual
    - 25 pts: Sector Relative Strength
    - 25 pts: Trend (MA200)
    - 15 pts: Volume confirmation
    """

    # Mapeo de sectores a ETFs (USA principalmente)
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
        # Aliases comunes
        'Information Technology': 'XLK',
        'Health Care': 'XLV',
        'Financial Services': 'XLF',
        'Consumer Discretionary': 'XLY',
        'Consumer Staples': 'XLP',
        'Materials': 'XLB',
        'Telecommunication Services': 'XLC',
    }

    def __init__(self, fmp_client):
        """
        Args:
            fmp_client: Cliente FMP (puede ser CachedFMPClient)
        """
        self.fmp = fmp_client

    def analyze(self, symbol: str, sector: str = None, country: str = 'USA') -> Dict:
        """
        Analiza aspectos técnicos de una empresa.

        Args:
            symbol: Ticker de la empresa (ej: 'AAPL')
            sector: Sector de la empresa (ej: 'Technology')
            country: País (default: 'USA')

        Returns:
            {
                'score': 0-100,
                'signal': 'BUY' | 'HOLD' | 'SELL',
                'momentum_12m': float (% return),
                'trend': 'UPTREND' | 'DOWNTREND' | 'NEUTRAL',
                'distance_from_ma200': float (%),
                'sector_status': str,
                'warnings': [list of warning messages],
                'timestamp': datetime
            }
        """
        try:
            # Fetch data (1 endpoint, cacheado)
            quote = self.fmp.get_quote(symbol)

            if not quote or len(quote) == 0:
                return self._null_result(symbol, "No quote data available")

            q = quote[0]

            # Extract data
            price = q.get('price', 0)
            change_1y = q.get('changesPercentage', 0)  # Already calculated by FMP!
            ma_200 = q.get('priceAvg200', 0)
            ma_50 = q.get('priceAvg50', 0)
            volume = q.get('volume', 0)
            avg_volume = q.get('avgVolume', 1)

            # Calculate 6M return for sector comparison
            change_6m = change_1y * 0.5  # Rough approximation (FMP doesn't have 6M directly)

            # Calculate components
            momentum_score, momentum_data = self._analyze_momentum(change_1y)
            sector_score, sector_data = self._analyze_sector_strength(
                symbol, change_6m, sector, country
            )
            trend_score, trend_data = self._analyze_trend(price, ma_50, ma_200)
            volume_score, volume_data = self._analyze_volume(volume, avg_volume)

            # Total score
            total_score = momentum_score + sector_score + trend_score + volume_score

            # Warnings
            warnings = self._generate_warnings(
                change_1y, price, ma_200, volume, avg_volume, sector_data
            )

            # Signal
            signal = self._generate_signal(total_score, trend_data['status'], sector_data)

            return {
                'score': min(total_score, 100),
                'signal': signal,

                # Momentum details
                'momentum_12m': change_1y,
                'momentum_status': momentum_data['status'],

                # Sector details
                'sector': sector_data.get('sector_name', 'Unknown'),
                'sector_momentum_6m': sector_data.get('sector_return', 0),
                'relative_strength': sector_data.get('relative_strength', 0),
                'sector_status': sector_data.get('status', 'UNKNOWN'),

                # Trend details
                'trend': trend_data['status'],
                'distance_from_ma200': trend_data['distance_ma200'],
                'golden_cross': trend_data['golden_cross'],

                # Volume details
                'volume_status': volume_data['status'],
                'volume_ratio': volume_data['ratio'],

                # Warnings
                'warnings': warnings,
                'timestamp': datetime.now().isoformat(),

                # Component scores (for debugging)
                'component_scores': {
                    'momentum': momentum_score,
                    'sector': sector_score,
                    'trend': trend_score,
                    'volume': volume_score
                }
            }

        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {str(e)}")
            return self._null_result(symbol, f"Error: {str(e)}")

    def _analyze_momentum(self, change_1y: float) -> tuple:
        """
        Analiza momentum de 12 meses.

        Evidencia: Jegadeesh & Titman (1993), Moskowitz (2012)

        Returns:
            (score: 0-35, data: dict)
        """
        score = 0

        if change_1y >= 20:
            score = 35
            status = 'VERY_STRONG'
        elif change_1y >= 15:
            score = 30
            status = 'STRONG'
        elif change_1y >= 10:
            score = 22
            status = 'MODERATE'
        elif change_1y >= 5:
            score = 13
            status = 'WEAK_POSITIVE'
        elif change_1y >= 0:
            score = 5
            status = 'NEUTRAL'
        else:
            score = 0
            status = 'NEGATIVE'

        return score, {
            'status': status,
            'value': change_1y
        }

    def _analyze_sector_strength(self, symbol: str, stock_return_6m: float,
                                 sector: str = None, country: str = 'USA') -> tuple:
        """
        Analiza fortaleza relativa vs sector.

        Evidencia: Bretscher et al. (2023), Arnott (2024)
        - Sector momentum importa 60% del total momentum
        - Relative strength predice outperformance

        Returns:
            (score: 0-25, data: dict)
        """
        score = 0

        # Si no hay sector, score neutral
        if not sector:
            return 12, {
                'sector_name': 'Unknown',
                'sector_return': 0,
                'relative_strength': 0,
                'status': 'UNKNOWN'
            }

        # Get sector ETF
        sector_etf = self.SECTOR_ETFS.get(sector)

        if not sector_etf:
            # Sector no mapeado, score neutral
            return 12, {
                'sector_name': sector,
                'sector_return': 0,
                'relative_strength': 0,
                'status': 'NO_ETF_AVAILABLE'
            }

        try:
            # Get sector ETF performance
            sector_quote = self.fmp.get_quote(sector_etf)
            if not sector_quote or len(sector_quote) == 0:
                return 12, {
                    'sector_name': sector,
                    'sector_etf': sector_etf,
                    'sector_return': 0,
                    'relative_strength': 0,
                    'status': 'NO_DATA'
                }

            # Sector return (using 1Y as proxy for 6M)
            sector_return_6m = sector_quote[0].get('changesPercentage', 0) * 0.5

            # Relative strength
            relative_strength = stock_return_6m - sector_return_6m

            # Score based on:
            # 1. Sector absolute momentum (40% of 25pts = 10pts)
            # 2. Relative strength (60% of 25pts = 15pts)

            # 1. Sector momentum (10 pts)
            if sector_return_6m > 15:
                score += 10  # Hot sector
                sector_status = 'HOT_SECTOR'
            elif sector_return_6m > 5:
                score += 7   # Positive sector
                sector_status = 'POSITIVE_SECTOR'
            elif sector_return_6m > 0:
                score += 5   # Weak positive
                sector_status = 'NEUTRAL_SECTOR'
            elif sector_return_6m > -10:
                score += 2   # Weak sector
                sector_status = 'WEAK_SECTOR'
            else:
                score += 0   # Cold sector
                sector_status = 'COLD_SECTOR'

            # 2. Relative strength (15 pts)
            if relative_strength > 10:
                score += 15  # Strong outperformer
                relative_status = 'STRONG_OUTPERFORMER'
            elif relative_strength > 5:
                score += 12  # Outperformer
                relative_status = 'OUTPERFORMER'
            elif relative_strength > 0:
                score += 8   # Slight outperformer
                relative_status = 'SLIGHT_OUTPERFORMER'
            elif relative_strength > -5:
                score += 4   # Slight underperformer
                relative_status = 'SLIGHT_UNDERPERFORMER'
            elif relative_strength > -10:
                score += 2   # Underperformer
                relative_status = 'UNDERPERFORMER'
            else:
                score += 0   # Strong underperformer
                relative_status = 'STRONG_UNDERPERFORMER'

            # Combined status
            if 'OUTPERFORMER' in relative_status and 'HOT' in sector_status:
                status = 'EXCELLENT'  # Best case
            elif 'OUTPERFORMER' in relative_status:
                status = 'GOOD'
            elif 'COLD' in sector_status:
                status = 'AVOID'
            else:
                status = 'NEUTRAL'

            return score, {
                'sector_name': sector,
                'sector_etf': sector_etf,
                'sector_return': sector_return_6m,
                'stock_return': stock_return_6m,
                'relative_strength': relative_strength,
                'sector_status': sector_status,
                'relative_status': relative_status,
                'status': status
            }

        except Exception as e:
            logger.warning(f"Error fetching sector data for {sector}: {str(e)}")
            # Error, neutral score
            return 12, {
                'sector_name': sector,
                'sector_return': 0,
                'relative_strength': 0,
                'status': 'ERROR',
                'error': str(e)
            }

    def _analyze_trend(self, price: float, ma_50: float, ma_200: float) -> tuple:
        """
        Analiza tendencia usando Moving Averages.

        Evidencia: Brock et al. (1992)

        Returns:
            (score: 0-25, data: dict)
        """
        score = 0

        if not ma_200 or ma_200 == 0:
            return 12, {
                'status': 'NO_DATA',
                'distance_ma200': 0,
                'golden_cross': False
            }

        # Calculate distances
        distance_ma200 = ((price - ma_200) / ma_200 * 100)
        golden_cross = (ma_50 > ma_200) if (ma_50 and ma_200) else False

        # Determine trend
        if price > ma_200:
            # Uptrend
            if distance_ma200 < 5:
                score = 15
                status = 'UPTREND_EARLY'
            elif distance_ma200 < 20:
                score = 25
                status = 'UPTREND'
            elif distance_ma200 < 30:
                score = 18
                status = 'UPTREND_EXTENDED'
            else:
                score = 10
                status = 'UPTREND_OVEREXTENDED'

            # Bonus for golden cross
            if golden_cross:
                score += 3
                score = min(score, 25)  # Cap at 25

        elif price > ma_200 * 0.95:
            score = 10
            status = 'NEUTRAL'

        else:
            # Downtrend
            score = 0
            if price < ma_200 * 0.90:
                status = 'DOWNTREND_STRONG'
            else:
                status = 'DOWNTREND'

        return score, {
            'status': status,
            'distance_ma200': distance_ma200,
            'golden_cross': golden_cross
        }

    def _analyze_volume(self, volume: int, avg_volume: int) -> tuple:
        """
        Analiza volumen para confirmación.

        Returns:
            (score: 0-15, data: dict)
        """
        if avg_volume == 0 or avg_volume is None:
            return 7, {'status': 'UNKNOWN', 'ratio': 0}

        ratio = volume / avg_volume

        if ratio >= 1.5:
            score = 15
            status = 'VERY_HIGH'
        elif ratio >= 1.2:
            score = 12
            status = 'HIGH'
        elif ratio >= 0.8:
            score = 8
            status = 'NORMAL'
        elif ratio >= 0.5:
            score = 4
            status = 'LOW'
        else:
            score = 0
            status = 'VERY_LOW'

        return score, {
            'status': status,
            'ratio': ratio
        }

    def _generate_warnings(self, change_1y: float, price: float,
                          ma_200: float, volume: int, avg_volume: int,
                          sector_data: dict) -> list:
        """
        Genera warnings basados en condiciones de riesgo.
        """
        warnings = []

        # 1. Meme stock detection
        if change_1y > 100:
            warnings.append({
                'type': 'MEME_STOCK_RISK',
                'severity': 'HIGH',
                'message': f'Extreme 1Y gain (+{change_1y:.0f}%). Possible meme stock or bubble.'
            })

        # 2. Sobreextensión vs MA200
        if ma_200 and price > ma_200:
            distance = (price - ma_200) / ma_200 * 100
            if distance > 30:
                warnings.append({
                    'type': 'OVEREXTENDED',
                    'severity': 'MEDIUM',
                    'message': f'Price {distance:.0f}% above MA200. Potential pullback risk.'
                })

        # 3. Downtrend fuerte
        if ma_200 and price < ma_200 * 0.85:
            warnings.append({
                'type': 'STRONG_DOWNTREND',
                'severity': 'HIGH',
                'message': 'Price >15% below MA200. Strong downtrend.'
            })

        # 4. Low volume
        if avg_volume and volume < avg_volume * 0.5:
            warnings.append({
                'type': 'LOW_VOLUME',
                'severity': 'LOW',
                'message': 'Volume 50% below average. Weak signal reliability.'
            })

        # 5. Sector warnings
        if sector_data.get('status') == 'AVOID':
            warnings.append({
                'type': 'COLD_SECTOR',
                'severity': 'HIGH',
                'message': f"Sector {sector_data.get('sector_name', '')} is weak ({sector_data.get('sector_return', 0):+.0f}% 6M)."
            })

        if 'UNDERPERFORMER' in sector_data.get('relative_status', ''):
            warnings.append({
                'type': 'RELATIVE_WEAKNESS',
                'severity': 'MEDIUM',
                'message': f"Underperforming sector by {abs(sector_data.get('relative_strength', 0)):.0f}%."
            })

        return warnings

    def _generate_signal(self, score: int, trend: str, sector_data: dict) -> str:
        """
        Genera señal de trading basada en score y trend.
        """
        # SELL if cold sector
        if sector_data.get('status') == 'AVOID':
            return 'SELL'

        # SELL if downtrend
        if 'DOWNTREND' in trend:
            return 'SELL'

        # BUY if excellent sector + high score
        if sector_data.get('status') == 'EXCELLENT' and score >= 70:
            return 'BUY'

        # BUY if high score
        if score >= 75:
            return 'BUY'

        # HOLD
        if score >= 50:
            return 'HOLD'

        return 'SELL'

    def _null_result(self, symbol: str, reason: str) -> Dict:
        """
        Resultado nulo cuando no hay datos.
        """
        return {
            'score': 50,  # Neutral
            'signal': 'HOLD',
            'momentum_12m': 0,
            'momentum_status': 'UNKNOWN',
            'sector': 'Unknown',
            'sector_momentum_6m': 0,
            'relative_strength': 0,
            'sector_status': 'UNKNOWN',
            'trend': 'UNKNOWN',
            'distance_from_ma200': 0,
            'golden_cross': False,
            'volume_status': 'UNKNOWN',
            'volume_ratio': 0,
            'warnings': [{
                'type': 'NO_DATA',
                'severity': 'HIGH',
                'message': reason
            }],
            'timestamp': datetime.now().isoformat(),
            'component_scores': {
                'momentum': 0,
                'sector': 0,
                'trend': 0,
                'volume': 0
            }
        }
