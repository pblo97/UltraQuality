"""
Hierarchical Market Regime System (2024)

PRINCIPIO RECTOR:
Ninguna señal de stock tiene valor fuera de su entorno.
El sistema decide primero DÓNDE es estadísticamente válido operar,
luego QUÉ activos tienen edge, y recién al final CUÁNDO entrar.

ARQUITECTURA JERÁRQUICA:
CAPA 0 - Kill Switch Sistémico
CAPA 1 - Régimen Global (cross-market alignment)
CAPA 2 - Régimen Regional
CAPA 3 - Régimen Sectorial
CAPA 4 - Breadth (global + sectorial)
CAPA 5 - Contexto de Mercado (volatilidad, drawdown, fatiga)
CAPA 7 - Ajuste de Convicción por Entorno

Academic Evidence:
- Cooper et al. (2004): Momentum 20% better in bull, 60% worse in bear
- Daniel & Moskowitz (2016): Momentum crashes in market stress
- Blin et al. (2022): Cross-market regime matters more than single index
"""

from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta
from enum import Enum
import logging
import statistics

logger = logging.getLogger(__name__)


class GlobalRegime(Enum):
    """Global market regime states."""
    BULL = "GLOBAL_BULL"
    AMBIGUOUS = "GLOBAL_AMBIGUOUS"
    BEAR = "GLOBAL_BEAR"


class BreadthState(Enum):
    """Market breadth states."""
    POSITIVE = "POSITIVE"
    MIXED = "MIXED"
    NEGATIVE = "NEGATIVE"


class RegionalRegime(Enum):
    """Regional regime states."""
    BULL = "REGIONAL_BULL"
    NEUTRAL = "REGIONAL_NEUTRAL"
    BEAR = "REGIONAL_BEAR"


class SectorRegime(Enum):
    """Sector regime states."""
    LEADING = "SECTOR_LEADING"
    NEUTRAL = "SECTOR_NEUTRAL"
    LAGGING = "SECTOR_LAGGING"


class MarketRegimeSystem:
    """
    Hierarchical Market Regime Detection System.

    Implements 8-layer architecture for signal validation:
    - Layers 0-5: Environmental filters (regime, breadth, context)
    - Layer 6: Asset score (handled by analyzer)
    - Layer 7: Conviction adjustment
    - Layer 8: Signal generation
    """

    # ============================================================================
    # CAPA 1: Global Regime - Reference Markets
    # ============================================================================

    GLOBAL_PROXIES = {
        'USA': 'SPY',
        'EUROPE': 'FEZ',
        'EMERGING': 'EEM',
        'ASIA': 'AAXJ',
    }

    VIX_SYMBOL = '^VIX'

    # ============================================================================
    # CAPA 2: Regional Mapping
    # ============================================================================

    REGION_MAPPING = {
        # USA
        'US': 'USA', 'USA': 'USA',
        # Europe
        'DE': 'EUROPE', 'FR': 'EUROPE', 'GB': 'EUROPE', 'UK': 'EUROPE',
        'ES': 'EUROPE', 'IT': 'EUROPE', 'NL': 'EUROPE', 'CH': 'EUROPE',
        'SE': 'EUROPE', 'NO': 'EUROPE', 'DK': 'EUROPE', 'FI': 'EUROPE',
        'BE': 'EUROPE', 'AT': 'EUROPE', 'IE': 'EUROPE', 'PT': 'EUROPE',
        # Asia Developed
        'JP': 'ASIA', 'HK': 'ASIA', 'SG': 'ASIA', 'AU': 'ASIA', 'NZ': 'ASIA',
        'KR': 'ASIA', 'TW': 'ASIA',
        # Emerging Markets
        'CN': 'EMERGING', 'IN': 'EMERGING', 'BR': 'EMERGING', 'MX': 'EMERGING',
        'ZA': 'EMERGING', 'RU': 'EMERGING', 'TR': 'EMERGING', 'ID': 'EMERGING',
        'TH': 'EMERGING', 'MY': 'EMERGING', 'PH': 'EMERGING', 'VN': 'EMERGING',
        'CL': 'EMERGING', 'CO': 'EMERGING', 'PE': 'EMERGING', 'AR': 'EMERGING',
        'PL': 'EMERGING', 'CZ': 'EMERGING', 'HU': 'EMERGING',
        'SA': 'EMERGING', 'AE': 'EMERGING', 'QA': 'EMERGING', 'EG': 'EMERGING',
    }

    REGION_ETFS = {
        'USA': 'SPY',
        'EUROPE': 'FEZ',
        'ASIA': 'AAXJ',
        'EMERGING': 'EEM',
    }

    # ============================================================================
    # CAPA 3: Sector ETFs
    # ============================================================================

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

    # ============================================================================
    # Thresholds (objective, not interpretative)
    # ============================================================================

    VIX_THRESHOLD = 25  # Above = risk-off signal
    DRAWDOWN_WARNING = 10  # %
    DRAWDOWN_PARTIAL_VETO = 15  # %
    DRAWDOWN_FULL_VETO = 20  # %
    RALLY_FATIGUE_THRESHOLD = 20  # % in 6M = fatigue
    SECTOR_DRAWDOWN_MAX = 15  # %

    # Breadth thresholds
    BREADTH_POSITIVE_THRESHOLD = 60  # %
    BREADTH_NEGATIVE_THRESHOLD = 40  # %

    # Conviction multipliers
    CONVICTION_MULTIPLIERS = {
        'GLOBAL_BULL': 1.0,
        'GLOBAL_AMBIGUOUS': 0.7,
        'GLOBAL_BEAR': 0.0,  # Kill switch
        'BREADTH_POSITIVE': 1.0,
        'BREADTH_MIXED': 0.6,
        'BREADTH_NEGATIVE': 0.0,  # Veto
        'DRAWDOWN_WARNING': 0.7,
        'DRAWDOWN_PARTIAL': 0.3,
        'DRAWDOWN_FULL': 0.0,  # Risk-off
        'SECTOR_LEADING': 1.0,
        'SECTOR_NEUTRAL': 0.8,
        'SECTOR_LAGGING': 0.5,
    }

    def __init__(self, fmp_client):
        """
        Args:
            fmp_client: FMP client (preferably CachedFMPClient)
        """
        self.fmp = fmp_client
        self._cache = {}
        self._cache_timestamp = None
        self._cache_ttl = 6 * 3600  # 6 hours

    def _get_from_date(self, days: int) -> str:
        """Convert days lookback to from_date string."""
        from_date = datetime.now() - timedelta(days=days)
        return from_date.strftime('%Y-%m-%d')

    def _is_cache_valid(self) -> bool:
        """Check if cache is still valid."""
        if not self._cache or not self._cache_timestamp:
            return False
        elapsed = (datetime.now() - self._cache_timestamp).total_seconds()
        return elapsed < self._cache_ttl

    def _get_price_data(self, symbol: str, days: int = 300) -> List[Dict]:
        """Get historical prices sorted by date descending."""
        try:
            from_date = self._get_from_date(days)
            data = self.fmp.get_historical_prices(symbol, from_date=from_date)
            if not data or 'historical' not in data:
                return []
            prices = sorted(data['historical'], key=lambda x: x['date'], reverse=True)
            return prices
        except Exception as e:
            logger.warning(f"Error getting price data for {symbol}: {e}")
            return []

    def _calculate_ma(self, prices: List[Dict], period: int) -> Optional[float]:
        """Calculate simple moving average."""
        if len(prices) < period:
            return None
        return statistics.mean(p['close'] for p in prices[:period])

    def _calculate_momentum(self, prices: List[Dict], months: int) -> Optional[float]:
        """Calculate momentum over N months (approx 21 trading days per month)."""
        days = months * 21
        if len(prices) < days + 1:
            return None
        current = prices[0]['close']
        past = prices[min(days, len(prices) - 1)]['close']
        if past <= 0:
            return None
        return ((current - past) / past) * 100

    def _calculate_drawdown_from_ath(self, prices: List[Dict], lookback_days: int = 252) -> float:
        """Calculate current drawdown from ATH."""
        if not prices:
            return 0.0

        lookback = min(lookback_days, len(prices))
        highs = [p['high'] for p in prices[:lookback]]
        if not highs:
            return 0.0

        ath = max(highs)
        current = prices[0]['close']

        if ath <= 0:
            return 0.0

        return ((ath - current) / ath) * 100

    # ============================================================================
    # CAPA 0: KILL SWITCH SISTÉMICO
    # ============================================================================

    def check_kill_switch(self) -> Tuple[bool, str]:
        """
        CAPA 0: Kill Switch Sistémico.

        If GLOBAL_REGIME == BEAR: block_all_new_entries()
        No parciales, no excepciones, no "pero esta es buena".

        Returns:
            (is_active, reason)
        """
        global_regime = self.get_global_regime()

        if global_regime['regime'] == GlobalRegime.BEAR:
            return True, f"Kill Switch ACTIVE: Global Bear Market (alignment={global_regime['alignment_score']}/5)"

        return False, "Kill Switch inactive"

    # ============================================================================
    # CAPA 1: RÉGIMEN GLOBAL (Cross-Market Alignment)
    # ============================================================================

    def get_global_regime(self) -> Dict:
        """
        CAPA 1: Régimen Global con Alignment Score.

        NO solo SPY - usa comparativa cross-market:
        +1 si SPY > MA200
        +1 si FEZ > MA200
        +1 si EEM > MA200
        +1 si retorno SPY 3-6M > 0
        +1 si VIX < 25

        Clasificación:
        - 4-5: GLOBAL_BULL
        - 2-3: GLOBAL_AMBIGUOUS
        - 0-1: GLOBAL_BEAR

        Returns:
            {
                'regime': GlobalRegime,
                'alignment_score': 0-5,
                'components': {...},
                'details': {...}
            }
        """
        # Check cache
        if self._is_cache_valid() and 'global_regime' in self._cache:
            return self._cache['global_regime']

        alignment_score = 0
        components = {}
        details = {}

        try:
            # Component 1: SPY > MA200
            spy_prices = self._get_price_data('SPY', days=300)
            if spy_prices and len(spy_prices) >= 200:
                spy_price = spy_prices[0]['close']
                spy_ma200 = self._calculate_ma(spy_prices, 200)
                spy_above_ma200 = spy_price > spy_ma200 if spy_ma200 else False
                if spy_above_ma200:
                    alignment_score += 1
                components['spy_above_ma200'] = spy_above_ma200
                details['spy'] = {
                    'price': round(spy_price, 2),
                    'ma200': round(spy_ma200, 2) if spy_ma200 else None,
                    'distance_pct': round(((spy_price - spy_ma200) / spy_ma200 * 100), 1) if spy_ma200 else None
                }

            # Component 2: FEZ (Europe) > MA200
            fez_prices = self._get_price_data('FEZ', days=300)
            if fez_prices and len(fez_prices) >= 200:
                fez_price = fez_prices[0]['close']
                fez_ma200 = self._calculate_ma(fez_prices, 200)
                fez_above_ma200 = fez_price > fez_ma200 if fez_ma200 else False
                if fez_above_ma200:
                    alignment_score += 1
                components['fez_above_ma200'] = fez_above_ma200
                details['fez'] = {
                    'price': round(fez_price, 2),
                    'ma200': round(fez_ma200, 2) if fez_ma200 else None
                }

            # Component 3: EEM (Emerging) > MA200
            eem_prices = self._get_price_data('EEM', days=300)
            if eem_prices and len(eem_prices) >= 200:
                eem_price = eem_prices[0]['close']
                eem_ma200 = self._calculate_ma(eem_prices, 200)
                eem_above_ma200 = eem_price > eem_ma200 if eem_ma200 else False
                if eem_above_ma200:
                    alignment_score += 1
                components['eem_above_ma200'] = eem_above_ma200
                details['eem'] = {
                    'price': round(eem_price, 2),
                    'ma200': round(eem_ma200, 2) if eem_ma200 else None
                }

            # Component 4: SPY momentum 3-6M > 0
            if spy_prices:
                spy_mom_3m = self._calculate_momentum(spy_prices, 3)
                spy_mom_6m = self._calculate_momentum(spy_prices, 6)
                # Average of 3M and 6M momentum
                if spy_mom_3m is not None and spy_mom_6m is not None:
                    avg_momentum = (spy_mom_3m + spy_mom_6m) / 2
                    momentum_positive = avg_momentum > 0
                    if momentum_positive:
                        alignment_score += 1
                    components['spy_momentum_positive'] = momentum_positive
                    details['spy_momentum'] = {
                        '3m_pct': round(spy_mom_3m, 1),
                        '6m_pct': round(spy_mom_6m, 1),
                        'avg_pct': round(avg_momentum, 1)
                    }

            # Component 5: VIX < 25
            vix_data = self.fmp.get_quote('^VIX')
            vix = vix_data[0]['price'] if vix_data else 20
            vix_low = vix < self.VIX_THRESHOLD
            if vix_low:
                alignment_score += 1
            components['vix_below_threshold'] = vix_low
            details['vix'] = {
                'value': round(vix, 1),
                'threshold': self.VIX_THRESHOLD
            }

        except Exception as e:
            logger.error(f"Error calculating global regime: {e}")
            # Default to ambiguous on error
            alignment_score = 2

        # Classify regime
        if alignment_score >= 4:
            regime = GlobalRegime.BULL
        elif alignment_score <= 1:
            regime = GlobalRegime.BEAR
        else:
            regime = GlobalRegime.AMBIGUOUS

        result = {
            'regime': regime,
            'alignment_score': alignment_score,
            'max_score': 5,
            'components': components,
            'details': details
        }

        # Update cache
        self._cache['global_regime'] = result
        self._cache_timestamp = datetime.now()

        return result

    # ============================================================================
    # CAPA 2: RÉGIMEN REGIONAL
    # ============================================================================

    def get_regional_regime(self, country: str) -> Dict:
        """
        CAPA 2: Régimen Regional.

        Cada activo hereda su región.
        Regla: El régimen regional no puede ser BEAR aunque el global sea AMBIGUOUS.

        Args:
            country: Country code (US, DE, BR, etc.)

        Returns:
            {
                'regime': RegionalRegime,
                'region': str,
                'etf': str,
                'above_ma200': bool,
                'details': {...}
            }
        """
        region = self.REGION_MAPPING.get(country, 'USA')
        etf = self.REGION_ETFS.get(region, 'SPY')

        cache_key = f'regional_{region}'
        if self._is_cache_valid() and cache_key in self._cache:
            return self._cache[cache_key]

        try:
            prices = self._get_price_data(etf, days=300)
            if not prices or len(prices) < 200:
                return {
                    'regime': RegionalRegime.NEUTRAL,
                    'region': region,
                    'etf': etf,
                    'above_ma200': None,
                    'details': {'error': 'Insufficient data'}
                }

            current_price = prices[0]['close']
            ma200 = self._calculate_ma(prices, 200)
            above_ma200 = current_price > ma200 if ma200 else None

            # Determine regime
            if above_ma200:
                regime = RegionalRegime.BULL
            elif above_ma200 is False:
                regime = RegionalRegime.BEAR
            else:
                regime = RegionalRegime.NEUTRAL

            result = {
                'regime': regime,
                'region': region,
                'etf': etf,
                'above_ma200': above_ma200,
                'details': {
                    'price': round(current_price, 2),
                    'ma200': round(ma200, 2) if ma200 else None,
                    'distance_pct': round(((current_price - ma200) / ma200 * 100), 1) if ma200 else None
                }
            }

            self._cache[cache_key] = result
            return result

        except Exception as e:
            logger.error(f"Error calculating regional regime for {region}: {e}")
            return {
                'regime': RegionalRegime.NEUTRAL,
                'region': region,
                'etf': etf,
                'above_ma200': None,
                'details': {'error': str(e)}
            }

    # ============================================================================
    # CAPA 3: RÉGIMEN SECTORIAL
    # ============================================================================

    def get_sector_regime(self, sector: str) -> Dict:
        """
        CAPA 3: Régimen Sectorial.

        Condiciones mínimas:
        - Sector > MA200
        - Retorno sector 3-6M > SPY
        - Drawdown sector < 15%

        Si el sector falla -> no hay trade, aunque el stock sea perfecto.

        Args:
            sector: Sector name (Technology, Healthcare, etc.)

        Returns:
            {
                'regime': SectorRegime,
                'sector': str,
                'etf': str,
                'conditions': {
                    'above_ma200': bool,
                    'outperforming_spy': bool,
                    'drawdown_ok': bool
                },
                'all_conditions_met': bool,
                'details': {...}
            }
        """
        etf = self.SECTOR_ETFS.get(sector, 'XLK')

        cache_key = f'sector_{sector}'
        if self._is_cache_valid() and cache_key in self._cache:
            return self._cache[cache_key]

        conditions = {
            'above_ma200': None,
            'outperforming_spy': None,
            'drawdown_ok': None
        }
        details = {}

        try:
            # Get sector data
            sector_prices = self._get_price_data(etf, days=300)
            if not sector_prices or len(sector_prices) < 200:
                return {
                    'regime': SectorRegime.NEUTRAL,
                    'sector': sector,
                    'etf': etf,
                    'conditions': conditions,
                    'all_conditions_met': False,
                    'details': {'error': 'Insufficient sector data'}
                }

            # Condition 1: Sector > MA200
            sector_price = sector_prices[0]['close']
            sector_ma200 = self._calculate_ma(sector_prices, 200)
            conditions['above_ma200'] = sector_price > sector_ma200 if sector_ma200 else False
            details['sector'] = {
                'price': round(sector_price, 2),
                'ma200': round(sector_ma200, 2) if sector_ma200 else None,
                'distance_pct': round(((sector_price - sector_ma200) / sector_ma200 * 100), 1) if sector_ma200 else None
            }

            # Condition 2: Sector momentum > SPY momentum (3-6M)
            sector_mom_3m = self._calculate_momentum(sector_prices, 3)
            sector_mom_6m = self._calculate_momentum(sector_prices, 6)

            spy_prices = self._get_price_data('SPY', days=300)
            spy_mom_3m = self._calculate_momentum(spy_prices, 3) if spy_prices else 0
            spy_mom_6m = self._calculate_momentum(spy_prices, 6) if spy_prices else 0

            if sector_mom_3m is not None and sector_mom_6m is not None:
                sector_avg_mom = (sector_mom_3m + sector_mom_6m) / 2
                spy_avg_mom = (spy_mom_3m + spy_mom_6m) / 2 if spy_mom_3m and spy_mom_6m else 0
                conditions['outperforming_spy'] = sector_avg_mom > spy_avg_mom
                details['momentum'] = {
                    'sector_3m': round(sector_mom_3m, 1),
                    'sector_6m': round(sector_mom_6m, 1),
                    'sector_avg': round(sector_avg_mom, 1),
                    'spy_avg': round(spy_avg_mom, 1),
                    'relative': round(sector_avg_mom - spy_avg_mom, 1)
                }

            # Condition 3: Drawdown < 15%
            sector_dd = self._calculate_drawdown_from_ath(sector_prices)
            conditions['drawdown_ok'] = sector_dd < self.SECTOR_DRAWDOWN_MAX
            details['drawdown'] = {
                'current_pct': round(sector_dd, 1),
                'threshold_pct': self.SECTOR_DRAWDOWN_MAX
            }

            # Determine regime
            all_met = all(v for v in conditions.values() if v is not None)

            if all_met:
                regime = SectorRegime.LEADING
            elif conditions['above_ma200'] and conditions['drawdown_ok']:
                regime = SectorRegime.NEUTRAL
            else:
                regime = SectorRegime.LAGGING

            result = {
                'regime': regime,
                'sector': sector,
                'etf': etf,
                'conditions': conditions,
                'all_conditions_met': all_met,
                'details': details
            }

            self._cache[cache_key] = result
            return result

        except Exception as e:
            logger.error(f"Error calculating sector regime for {sector}: {e}")
            return {
                'regime': SectorRegime.NEUTRAL,
                'sector': sector,
                'etf': etf,
                'conditions': conditions,
                'all_conditions_met': False,
                'details': {'error': str(e)}
            }

    # ============================================================================
    # CAPA 4: BREADTH (Global + Sectorial)
    # ============================================================================

    def get_global_breadth(self) -> Dict:
        """
        CAPA 4: Breadth Global.

        % sectores sobre MA200:
        - >60%: POSITIVE
        - 40-60%: MIXED
        - <40%: NEGATIVE

        Returns:
            {
                'state': BreadthState,
                'sectors_above_ma200': int,
                'total_sectors': int,
                'breadth_pct': float,
                'sector_details': {...}
            }
        """
        cache_key = 'global_breadth'
        if self._is_cache_valid() and cache_key in self._cache:
            return self._cache[cache_key]

        sector_details = {}
        sectors_above = 0
        total_sectors = 0

        # Core sector ETFs (no aliases)
        core_sectors = {
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
        }

        for sector, etf in core_sectors.items():
            try:
                prices = self._get_price_data(etf, days=300)
                if prices and len(prices) >= 200:
                    current = prices[0]['close']
                    ma200 = self._calculate_ma(prices, 200)
                    above = current > ma200 if ma200 else False

                    total_sectors += 1
                    if above:
                        sectors_above += 1

                    sector_details[sector] = {
                        'etf': etf,
                        'above_ma200': above,
                        'distance_pct': round(((current - ma200) / ma200 * 100), 1) if ma200 else None
                    }
            except Exception as e:
                logger.warning(f"Error analyzing breadth for {sector}: {e}")

        if total_sectors == 0:
            return {
                'state': BreadthState.MIXED,
                'sectors_above_ma200': 0,
                'total_sectors': 0,
                'breadth_pct': 50.0,
                'sector_details': {},
                'error': 'No sector data available'
            }

        breadth_pct = (sectors_above / total_sectors) * 100

        if breadth_pct >= self.BREADTH_POSITIVE_THRESHOLD:
            state = BreadthState.POSITIVE
        elif breadth_pct < self.BREADTH_NEGATIVE_THRESHOLD:
            state = BreadthState.NEGATIVE
        else:
            state = BreadthState.MIXED

        result = {
            'state': state,
            'sectors_above_ma200': sectors_above,
            'total_sectors': total_sectors,
            'breadth_pct': round(breadth_pct, 1),
            'sector_details': sector_details
        }

        self._cache[cache_key] = result
        return result

    def get_sector_breadth(self, sector: str) -> Dict:
        """
        CAPA 4b: Breadth Sectorial.

        Calcula el breadth dentro de un sector usando sub-ETFs.

        Args:
            sector: Sector name (Technology, Healthcare, etc.)

        Returns:
            {
                'state': BreadthState,
                'sub_etfs_above': int,
                'total_sub_etfs': int,
                'breadth_pct': float,
                'details': {...}
            }
        """
        # Sub-ETFs por sector (subsectores/industrias)
        SECTOR_SUB_ETFS = {
            'Technology': ['SOXX', 'IGV', 'SKYY', 'HACK', 'FINX'],  # Semis, Software, Cloud, Cyber, Fintech
            'Healthcare': ['IBB', 'XBI', 'IHI', 'XHS'],  # Biotech, Biotech Small, Devices, Services
            'Financials': ['KBE', 'KIE', 'KRE', 'IAK'],  # Banks, Insurance, Regional Banks, Insurance
            'Consumer Cyclical': ['XRT', 'XHB', 'IBUY', 'PEJ'],  # Retail, Homebuilders, Online Retail, Leisure
            'Consumer Defensive': ['PBJ', 'FXG'],  # Food & Bev, Staples
            'Energy': ['XOP', 'OIH', 'AMLP'],  # E&P, Oil Services, MLPs
            'Industrials': ['ITA', 'XAR', 'JETS'],  # Aerospace, Aerospace/Defense, Airlines
            'Basic Materials': ['GDX', 'SLV', 'COPX'],  # Gold Miners, Silver, Copper
            'Communication Services': ['SOCL', 'NXTG'],  # Social Media, NextGen Comm
            'Utilities': ['TAN', 'FAN', 'NLR'],  # Solar, Wind, Nuclear
            'Real Estate': ['VNQ', 'MORT', 'REM'],  # REITs, Mortgage REITs, Mortgage
        }

        # Aliases
        SECTOR_SUB_ETFS['Information Technology'] = SECTOR_SUB_ETFS['Technology']
        SECTOR_SUB_ETFS['Health Care'] = SECTOR_SUB_ETFS['Healthcare']

        cache_key = f'sector_breadth_{sector}'
        if self._is_cache_valid() and cache_key in self._cache:
            return self._cache[cache_key]

        sub_etfs = SECTOR_SUB_ETFS.get(sector, [])
        if not sub_etfs:
            return {
                'state': BreadthState.MIXED,
                'sub_etfs_above': 0,
                'total_sub_etfs': 0,
                'breadth_pct': 50.0,
                'details': {},
                'note': f'No sub-ETFs defined for {sector}'
            }

        above_count = 0
        total_count = 0
        details = {}

        for etf in sub_etfs:
            try:
                prices = self._get_price_data(etf, days=300)
                if prices and len(prices) >= 200:
                    current = prices[0]['close']
                    ma200 = self._calculate_ma(prices, 200)
                    above = current > ma200 if ma200 else False

                    total_count += 1
                    if above:
                        above_count += 1

                    details[etf] = {
                        'above_ma200': above,
                        'distance_pct': round(((current - ma200) / ma200 * 100), 1) if ma200 else None
                    }
            except Exception as e:
                logger.warning(f"Error analyzing sector breadth ETF {etf}: {e}")

        if total_count == 0:
            return {
                'state': BreadthState.MIXED,
                'sub_etfs_above': 0,
                'total_sub_etfs': 0,
                'breadth_pct': 50.0,
                'details': {},
                'note': f'No data available for {sector} sub-ETFs'
            }

        breadth_pct = (above_count / total_count) * 100

        if breadth_pct >= self.BREADTH_POSITIVE_THRESHOLD:
            state = BreadthState.POSITIVE
        elif breadth_pct < self.BREADTH_NEGATIVE_THRESHOLD:
            state = BreadthState.NEGATIVE
        else:
            state = BreadthState.MIXED

        result = {
            'state': state,
            'sub_etfs_above': above_count,
            'total_sub_etfs': total_count,
            'breadth_pct': round(breadth_pct, 1),
            'details': details
        }

        self._cache[cache_key] = result
        return result

    # ============================================================================
    # CAPA 5: CONTEXTO DE MERCADO (Drawdown, Fatiga)
    # ============================================================================

    def get_market_context(self) -> Dict:
        """
        CAPA 5: Contexto de Mercado.

        - Drawdown del mercado (SPY from ATH)
        - Fatiga de rally (>20% en <6M)
        - Volatilidad (VIX level)

        Returns:
            {
                'drawdown': {
                    'current_pct': float,
                    'state': 'NORMAL'|'WARNING'|'PARTIAL_VETO'|'FULL_VETO'
                },
                'fatigue': {
                    'rally_6m_pct': float,
                    'is_fatigued': bool
                },
                'volatility': {
                    'vix': float,
                    'state': 'LOW'|'NORMAL'|'ELEVATED'|'HIGH'|'EXTREME'
                },
                'overall_context': 'FAVORABLE'|'CAUTIOUS'|'DEFENSIVE'|'RISK_OFF'
            }
        """
        cache_key = 'market_context'
        if self._is_cache_valid() and cache_key in self._cache:
            return self._cache[cache_key]

        result = {
            'drawdown': {'current_pct': 0, 'state': 'NORMAL'},
            'fatigue': {'rally_6m_pct': 0, 'is_fatigued': False},
            'volatility': {'vix': 20, 'state': 'NORMAL'},
            'overall_context': 'FAVORABLE'
        }

        try:
            # Drawdown analysis
            spy_prices = self._get_price_data('SPY', days=300)
            if spy_prices:
                dd = self._calculate_drawdown_from_ath(spy_prices)
                result['drawdown']['current_pct'] = round(dd, 1)

                if dd >= self.DRAWDOWN_FULL_VETO:
                    result['drawdown']['state'] = 'FULL_VETO'
                elif dd >= self.DRAWDOWN_PARTIAL_VETO:
                    result['drawdown']['state'] = 'PARTIAL_VETO'
                elif dd >= self.DRAWDOWN_WARNING:
                    result['drawdown']['state'] = 'WARNING'
                else:
                    result['drawdown']['state'] = 'NORMAL'

                # Fatigue analysis
                rally_6m = self._calculate_momentum(spy_prices, 6)
                if rally_6m is not None:
                    result['fatigue']['rally_6m_pct'] = round(rally_6m, 1)
                    result['fatigue']['is_fatigued'] = rally_6m > self.RALLY_FATIGUE_THRESHOLD

            # Volatility analysis
            vix_data = self.fmp.get_quote('^VIX')
            vix = vix_data[0]['price'] if vix_data else 20
            result['volatility']['vix'] = round(vix, 1)

            if vix >= 40:
                result['volatility']['state'] = 'EXTREME'
            elif vix >= 30:
                result['volatility']['state'] = 'HIGH'
            elif vix >= 25:
                result['volatility']['state'] = 'ELEVATED'
            elif vix >= 15:
                result['volatility']['state'] = 'NORMAL'
            else:
                result['volatility']['state'] = 'LOW'

            # Overall context
            if result['drawdown']['state'] == 'FULL_VETO':
                result['overall_context'] = 'RISK_OFF'
            elif result['drawdown']['state'] == 'PARTIAL_VETO' or result['volatility']['state'] in ('HIGH', 'EXTREME'):
                result['overall_context'] = 'DEFENSIVE'
            elif result['drawdown']['state'] == 'WARNING' or result['volatility']['state'] == 'ELEVATED' or result['fatigue']['is_fatigued']:
                result['overall_context'] = 'CAUTIOUS'
            else:
                result['overall_context'] = 'FAVORABLE'

        except Exception as e:
            logger.error(f"Error calculating market context: {e}")

        self._cache[cache_key] = result
        return result

    # ============================================================================
    # CAPA 7: AJUSTE DE CONVICCIÓN POR ENTORNO
    # ============================================================================

    def calculate_environment_multiplier(
        self,
        country: str = 'USA',
        sector: str = None
    ) -> Dict:
        """
        CAPA 7: Ajuste de Convicción por Entorno.

        final_score = raw_score × regime_mult × breadth_mult × drawdown_mult × sector_mult

        Args:
            country: Country code for regional regime
            sector: Sector name for sector regime

        Returns:
            {
                'final_multiplier': float (0.0-1.0),
                'components': {
                    'regime_multiplier': float,
                    'breadth_multiplier': float,
                    'drawdown_multiplier': float,
                    'sector_multiplier': float
                },
                'vetoes': [],
                'warnings': [],
                'can_trade': bool
            }
        """
        components = {}
        vetoes = []
        warnings = []

        # CAPA 0: Kill Switch
        kill_switch_active, kill_reason = self.check_kill_switch()
        if kill_switch_active:
            return {
                'final_multiplier': 0.0,
                'components': {'kill_switch': 0.0},
                'vetoes': [kill_reason],
                'warnings': [],
                'can_trade': False
            }

        # CAPA 1: Global Regime
        global_regime = self.get_global_regime()
        regime_mult = self.CONVICTION_MULTIPLIERS.get(global_regime['regime'].value, 0.7)
        components['regime_multiplier'] = regime_mult

        if global_regime['regime'] == GlobalRegime.AMBIGUOUS:
            warnings.append(f"Global Ambiguous (alignment={global_regime['alignment_score']}/5): Higher thresholds required")

        # CAPA 2: Regional Regime
        # Rule: Regional BEAR only blocks if Global is also BEAR
        # If Global is AMBIGUOUS, regional BEAR becomes a warning, not a veto
        regional = self.get_regional_regime(country)
        if regional['regime'] == RegionalRegime.BEAR:
            if global_regime['regime'] == GlobalRegime.BEAR:
                # Both global and regional are BEAR → hard veto
                vetoes.append(f"Regional Bear Market ({regional['region']})")
                components['regional_veto'] = True
            elif global_regime['regime'] == GlobalRegime.AMBIGUOUS:
                # Global AMBIGUOUS + Regional BEAR → warning only (not veto)
                warnings.append(f"Regional weakness ({regional['region']}): Extra caution advised")
                components['regional_warning'] = True

        # CAPA 4: Breadth
        breadth = self.get_global_breadth()
        breadth_mult = self.CONVICTION_MULTIPLIERS.get(f'BREADTH_{breadth["state"].name}', 0.6)
        components['breadth_multiplier'] = breadth_mult

        if breadth['state'] == BreadthState.NEGATIVE:
            vetoes.append(f"Negative Breadth ({breadth['breadth_pct']:.0f}% sectors above MA200)")
        elif breadth['state'] == BreadthState.MIXED:
            warnings.append(f"Mixed Breadth ({breadth['breadth_pct']:.0f}%): Conviction reduced 40%")

        # CAPA 5: Drawdown
        context = self.get_market_context()
        dd_state = context['drawdown']['state']
        if dd_state == 'FULL_VETO':
            drawdown_mult = 0.0
            vetoes.append(f"Market Drawdown >{self.DRAWDOWN_FULL_VETO}% (Risk-Off)")
        elif dd_state == 'PARTIAL_VETO':
            drawdown_mult = 0.3
            warnings.append(f"Market Drawdown >{self.DRAWDOWN_PARTIAL_VETO}% (Partial Veto)")
        elif dd_state == 'WARNING':
            drawdown_mult = 0.7
            warnings.append(f"Market Drawdown >{self.DRAWDOWN_WARNING}% (Caution)")
        else:
            drawdown_mult = 1.0
        components['drawdown_multiplier'] = drawdown_mult

        # Fatigue warning
        if context['fatigue']['is_fatigued']:
            warnings.append(f"Rally Fatigue: +{context['fatigue']['rally_6m_pct']:.0f}% in 6M")

        # CAPA 3: Sector Regime (if provided)
        sector_mult = 1.0
        if sector:
            sector_regime = self.get_sector_regime(sector)
            if sector_regime['regime'] == SectorRegime.LAGGING:
                sector_mult = 0.5
                warnings.append(f"Sector Lagging ({sector}): Conviction reduced 50%")
            elif sector_regime['regime'] == SectorRegime.NEUTRAL:
                sector_mult = 0.8
            else:
                sector_mult = 1.0

            if not sector_regime['all_conditions_met'] and sector_regime['regime'] != SectorRegime.LEADING:
                failed_conditions = [k for k, v in sector_regime['conditions'].items() if v is False]
                if failed_conditions:
                    warnings.append(f"Sector conditions not met: {', '.join(failed_conditions)}")

            # CAPA 4b: Sector Breadth
            sector_breadth = self.get_sector_breadth(sector)
            if sector_breadth['total_sub_etfs'] > 0:
                components['sector_breadth'] = {
                    'state': sector_breadth['state'].value,
                    'pct': sector_breadth['breadth_pct']
                }
                if sector_breadth['state'] == BreadthState.NEGATIVE:
                    sector_mult *= 0.7
                    warnings.append(f"Sector breadth weak ({sector}): {sector_breadth['breadth_pct']:.0f}% sub-industries above MA200")
                elif sector_breadth['state'] == BreadthState.MIXED:
                    sector_mult *= 0.85
                    warnings.append(f"Sector breadth mixed ({sector}): {sector_breadth['breadth_pct']:.0f}%")

        components['sector_multiplier'] = sector_mult

        # Calculate final multiplier
        if vetoes:
            final_mult = 0.0
            can_trade = False
        else:
            final_mult = regime_mult * breadth_mult * drawdown_mult * sector_mult
            final_mult = max(0.0, min(1.0, final_mult))
            can_trade = final_mult > 0

        return {
            'final_multiplier': round(final_mult, 3),
            'components': components,
            'vetoes': vetoes,
            'warnings': warnings,
            'can_trade': can_trade
        }

    # ============================================================================
    # FULL ENVIRONMENT ANALYSIS
    # ============================================================================

    def get_full_environment(self, country: str = 'USA', sector: str = None) -> Dict:
        """
        Get complete hierarchical environment analysis.

        Combines all layers for comprehensive view.

        Args:
            country: Country code
            sector: Sector name (optional)

        Returns:
            Full environment analysis with all layers
        """
        global_regime = self.get_global_regime()
        regional_regime = self.get_regional_regime(country)
        sector_regime = self.get_sector_regime(sector) if sector else None
        breadth = self.get_global_breadth()
        context = self.get_market_context()
        multiplier = self.calculate_environment_multiplier(country, sector)

        # Determine entry matrix position
        entry_matrix = self._determine_entry_matrix(
            global_regime=global_regime['regime'],
            breadth=breadth['state'],
            sector_regime=sector_regime['regime'] if sector_regime else None
        )

        return {
            'layers': {
                'capa_0_kill_switch': {
                    'active': global_regime['regime'] == GlobalRegime.BEAR,
                    'reason': 'Global Bear Market' if global_regime['regime'] == GlobalRegime.BEAR else None
                },
                'capa_1_global_regime': global_regime,
                'capa_2_regional_regime': regional_regime,
                'capa_3_sector_regime': sector_regime,
                'capa_4_breadth': breadth,
                'capa_5_market_context': context,
                'capa_7_conviction_adjustment': multiplier
            },
            'entry_matrix': entry_matrix,
            'summary': {
                'can_trade': multiplier['can_trade'],
                'final_multiplier': multiplier['final_multiplier'],
                'vetoes': multiplier['vetoes'],
                'warnings': multiplier['warnings']
            }
        }

    def _determine_entry_matrix(
        self,
        global_regime: GlobalRegime,
        breadth: BreadthState,
        sector_regime: SectorRegime = None
    ) -> Dict:
        """
        Determine position in entry decision matrix.

        Matrix from specification:
        - Global Bull + Breadth + Sector fuerte: Normal threshold, full size
        - Global Bull + Breadth MIXED: High threshold, reduced size
        - Global Ambiguous + Sector líder: Very high threshold, small size
        - Global Ambiguous + Breadth NEG: No entry
        - Global Bear: No entry
        """
        # Default
        result = {
            'entries_allowed': False,
            'threshold': 'BLOCKED',
            'size': 'NONE',
            'description': 'No trades allowed'
        }

        if global_regime == GlobalRegime.BEAR:
            result = {
                'entries_allowed': False,
                'threshold': 'BLOCKED',
                'size': 'NONE',
                'description': 'Kill Switch Active - No new entries'
            }

        elif global_regime == GlobalRegime.AMBIGUOUS:
            if breadth == BreadthState.NEGATIVE:
                result = {
                    'entries_allowed': False,
                    'threshold': 'BLOCKED',
                    'size': 'NONE',
                    'description': 'Ambiguous regime + Negative breadth - No entries'
                }
            elif sector_regime == SectorRegime.LEADING:
                result = {
                    'entries_allowed': True,
                    'threshold': 'VERY_HIGH',
                    'min_score': 90,
                    'size': 'SMALL',
                    'size_pct': 30,
                    'description': 'Exceptional setups only in leading sectors'
                }
            else:
                result = {
                    'entries_allowed': True,
                    'threshold': 'VERY_HIGH',
                    'min_score': 90,
                    'size': 'MINIMAL',
                    'size_pct': 20,
                    'description': 'Only exceptional setups (score >= 90)'
                }

        elif global_regime == GlobalRegime.BULL:
            if breadth == BreadthState.POSITIVE and sector_regime in (SectorRegime.LEADING, None):
                result = {
                    'entries_allowed': True,
                    'threshold': 'NORMAL',
                    'min_score': 75,
                    'size': 'FULL',
                    'size_pct': 100,
                    'description': 'Full deployment - Optimal conditions'
                }
            elif breadth == BreadthState.MIXED:
                result = {
                    'entries_allowed': True,
                    'threshold': 'HIGH',
                    'min_score': 80,
                    'size': 'REDUCED',
                    'size_pct': 60,
                    'description': 'Higher bar required - Mixed breadth'
                }
            else:  # NEGATIVE breadth in BULL
                result = {
                    'entries_allowed': True,
                    'threshold': 'HIGH',
                    'min_score': 85,
                    'size': 'SMALL',
                    'size_pct': 40,
                    'description': 'Selective entries only - Narrow market'
                }

        return result
