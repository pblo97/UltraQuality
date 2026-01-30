"""
Earnings Data Fetcher

Fetches earnings history, estimates, and calendar data from various sources.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


def fetch_earnings_data(ticker: str, yf_ticker=None) -> Dict[str, Any]:
    """
    Fetch comprehensive earnings data for a ticker.

    Returns:
        Dict with:
        - next_earnings_date: datetime
        - timing: BMO/AMC
        - earnings_history: List of past earnings
        - estimates: Current estimates
    """
    try:
        import yfinance as yf

        if yf_ticker is None:
            yf_ticker = yf.Ticker(ticker)

        result = {
            'next_earnings_date': None,
            'timing': 'UNKNOWN',
            'earnings_history': [],
            'estimates': {}
        }

        # Get earnings calendar
        try:
            calendar = yf_ticker.calendar
            if calendar is not None and not calendar.empty if hasattr(calendar, 'empty') else calendar:
                if isinstance(calendar, dict):
                    earnings_date = calendar.get('Earnings Date')
                    if earnings_date:
                        if isinstance(earnings_date, list) and len(earnings_date) > 0:
                            result['next_earnings_date'] = earnings_date[0]
                        else:
                            result['next_earnings_date'] = earnings_date
                else:
                    # DataFrame format
                    if 'Earnings Date' in calendar.columns:
                        dates = calendar['Earnings Date'].values
                        if len(dates) > 0:
                            result['next_earnings_date'] = dates[0]
        except Exception as e:
            logger.debug(f"Could not get calendar for {ticker}: {e}")

        # Get earnings history
        try:
            earnings = yf_ticker.earnings_history
            if earnings is not None and not earnings.empty if hasattr(earnings, 'empty') else earnings:
                history = []
                for idx, row in earnings.iterrows():
                    try:
                        eps_estimate = row.get('epsEstimate', row.get('Earnings Estimate'))
                        eps_actual = row.get('epsActual', row.get('Reported EPS'))
                        surprise = row.get('surprisePercent', row.get('Surprise(%)'))

                        # Calculate if beat
                        beat = None
                        if eps_estimate is not None and eps_actual is not None:
                            beat = eps_actual > eps_estimate

                        history.append({
                            'date': idx if isinstance(idx, datetime) else datetime.now(),
                            'eps_estimate': float(eps_estimate) if eps_estimate else None,
                            'eps_actual': float(eps_actual) if eps_actual else None,
                            'surprise_percent': float(surprise) if surprise else None,
                            'beat': beat,
                            'price_move': 0,  # Will be filled by price analysis
                            'price_before': 0,
                            'price_after': 0
                        })
                    except Exception as e:
                        logger.debug(f"Error parsing earnings row: {e}")
                        continue

                result['earnings_history'] = history[:8]  # Last 8 quarters
        except Exception as e:
            logger.debug(f"Could not get earnings history for {ticker}: {e}")

        # Try to get price moves around historical earnings
        result['earnings_history'] = _add_price_moves(ticker, result['earnings_history'], yf_ticker)

        # Get analyst estimates
        try:
            info = yf_ticker.info
            if info:
                result['estimates'] = {
                    'eps_estimate': info.get('forwardEps'),
                    'eps_low': None,
                    'eps_high': None,
                    'revenue_estimate': info.get('revenueEstimate'),
                    'num_analysts': info.get('numberOfAnalystOpinions', 0),
                    'revision_trend': _determine_revision_trend(info),
                    'revision_30d_change': None
                }
        except Exception as e:
            logger.debug(f"Could not get estimates for {ticker}: {e}")

        return result

    except ImportError:
        logger.warning("yfinance not available for earnings data")
        return {
            'next_earnings_date': None,
            'timing': 'UNKNOWN',
            'earnings_history': [],
            'estimates': {}
        }
    except Exception as e:
        logger.error(f"Error fetching earnings data for {ticker}: {e}")
        return {
            'next_earnings_date': None,
            'timing': 'UNKNOWN',
            'earnings_history': [],
            'estimates': {}
        }


def _add_price_moves(ticker: str, history: List[Dict], yf_ticker) -> List[Dict]:
    """
    Add price movement data around each historical earnings date.
    """
    if not history:
        return history

    try:
        # Get enough price history to cover all earnings
        oldest_date = min(h['date'] for h in history if h.get('date'))
        start_date = oldest_date - timedelta(days=10)

        hist = yf_ticker.history(start=start_date, end=datetime.now())
        if hist.empty:
            return history

        for h in history:
            try:
                earnings_date = h['date']
                if not earnings_date:
                    continue

                # Find closest trading days before and after earnings
                before_date = earnings_date - timedelta(days=1)
                after_date = earnings_date + timedelta(days=1)

                # Get prices (handle weekends/holidays)
                for offset in range(5):
                    check_date = before_date - timedelta(days=offset)
                    if check_date in hist.index:
                        h['price_before'] = float(hist.loc[check_date, 'Close'])
                        break

                for offset in range(5):
                    check_date = after_date + timedelta(days=offset)
                    if check_date in hist.index:
                        h['price_after'] = float(hist.loc[check_date, 'Close'])
                        break

                # Calculate move
                if h['price_before'] > 0 and h['price_after'] > 0:
                    h['price_move'] = ((h['price_after'] - h['price_before']) /
                                       h['price_before'] * 100)
                    h['move_percent'] = h['price_move']

            except Exception as e:
                logger.debug(f"Error calculating price move: {e}")
                continue

        return history

    except Exception as e:
        logger.debug(f"Error adding price moves: {e}")
        return history


def _determine_revision_trend(info: Dict) -> str:
    """Determine analyst revision trend from available data"""
    # This is a simplified version - would need more data sources for accurate tracking
    recommendation = info.get('recommendationMean', 3)
    if recommendation < 2:
        return 'UP'
    elif recommendation > 3.5:
        return 'DOWN'
    return 'STABLE'


def prepare_earnings_analysis_data(
    ticker: str,
    price_data: Dict[str, Any],
    fundamental_data: Dict[str, Any],
    yf_ticker=None
) -> tuple:
    """
    Prepare all data needed for earnings risk analysis.

    Returns:
        Tuple of (price_data, fundamental_data, earnings_data, options_data)
    """
    # Fetch earnings specific data
    earnings_data = fetch_earnings_data(ticker, yf_ticker)

    # Enhance price data with returns if not present
    if 'return_1m' not in price_data:
        price_data['return_1m'] = price_data.get('momentum_1m', 0)
    if 'return_3m' not in price_data:
        price_data['return_3m'] = price_data.get('momentum_3m', 0)

    # Options data (would need separate options API)
    options_data = None
    try:
        if yf_ticker:
            # Try to get options data
            options = yf_ticker.options
            if options:
                # Get nearest expiry
                nearest = options[0]
                chain = yf_ticker.option_chain(nearest)
                if chain:
                    # Calculate approximate IV from ATM options
                    calls = chain.calls
                    current_price = price_data.get('current_price', 0)
                    if not calls.empty and current_price > 0:
                        # Find ATM option
                        atm_idx = (calls['strike'] - current_price).abs().idxmin()
                        atm_call = calls.loc[atm_idx]
                        iv = atm_call.get('impliedVolatility', 0) * 100

                        options_data = {
                            'iv_30d': iv,
                            'iv_percentile': None,  # Would need historical IV data
                            'expected_move': current_price * (iv / 100) * 0.16  # ~1 week
                        }
    except Exception as e:
        logger.debug(f"Could not fetch options data: {e}")

    return price_data, fundamental_data, earnings_data, options_data
