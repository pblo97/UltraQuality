"""
Earnings Data Fetcher

Fetches earnings history, estimates, and calendar data using FMP API.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


def fetch_earnings_data(ticker: str, fmp_client=None) -> Dict[str, Any]:
    """
    Fetch comprehensive earnings data for a ticker using FMP.

    Args:
        ticker: Stock symbol
        fmp_client: FMP client instance (CachedFMPClient or FMPClient)

    Returns:
        Dict with:
        - next_earnings_date: datetime
        - timing: BMO/AMC
        - earnings_history: List of past earnings
        - estimates: Current estimates
    """
    result = {
        'next_earnings_date': None,
        'timing': 'UNKNOWN',
        'earnings_history': [],
        'estimates': {}
    }

    if not fmp_client:
        logger.warning("No FMP client provided for earnings data")
        return result

    try:
        # Get earnings calendar for next earnings date
        today = datetime.now()
        three_months = today + timedelta(days=90)

        from_date = today.strftime('%Y-%m-%d')
        to_date = three_months.strftime('%Y-%m-%d')

        try:
            calendar = fmp_client.get_earnings_calendar(from_date=from_date, to_date=to_date)
            if calendar:
                # Filter for this symbol
                symbol_earnings = [e for e in calendar if e.get('symbol', '').upper() == ticker.upper()]
                if symbol_earnings:
                    next_earning = symbol_earnings[0]
                    earning_date_str = next_earning.get('date')
                    if earning_date_str:
                        try:
                            result['next_earnings_date'] = datetime.strptime(earning_date_str, '%Y-%m-%d')
                        except:
                            result['next_earnings_date'] = earning_date_str

                    # Get timing (BMO = Before Market Open, AMC = After Market Close)
                    timing = next_earning.get('time', 'UNKNOWN')
                    if timing:
                        timing_upper = timing.upper()
                        if 'BMO' in timing_upper or 'BEFORE' in timing_upper:
                            result['timing'] = 'BMO'
                        elif 'AMC' in timing_upper or 'AFTER' in timing_upper:
                            result['timing'] = 'AMC'
                        else:
                            result['timing'] = timing
        except Exception as e:
            logger.debug(f"Could not get earnings calendar for {ticker}: {e}")

        # Get historical earnings
        try:
            # Try to get historical earnings data
            historical = fmp_client.get_earnings_surprises(ticker)
            if historical:
                history = []
                for item in historical[:8]:  # Last 8 quarters
                    try:
                        date_str = item.get('date')
                        eps_estimate = item.get('estimatedEarning')
                        eps_actual = item.get('actualEarningResult')

                        # Calculate surprise and beat
                        beat = None
                        surprise_percent = None
                        if eps_estimate is not None and eps_actual is not None:
                            try:
                                eps_est = float(eps_estimate)
                                eps_act = float(eps_actual)
                                beat = eps_act > eps_est
                                if eps_est != 0:
                                    surprise_percent = ((eps_act - eps_est) / abs(eps_est)) * 100
                            except:
                                pass

                        history.append({
                            'date': datetime.strptime(date_str, '%Y-%m-%d') if date_str else datetime.now(),
                            'eps_estimate': float(eps_estimate) if eps_estimate else None,
                            'eps_actual': float(eps_actual) if eps_actual else None,
                            'surprise_percent': surprise_percent,
                            'beat': beat,
                            'price_move': 0,
                            'move_percent': 0,
                            'price_before': 0,
                            'price_after': 0
                        })
                    except Exception as e:
                        logger.debug(f"Error parsing earnings history item: {e}")
                        continue

                result['earnings_history'] = history

                # Add price moves around earnings dates
                result['earnings_history'] = _add_price_moves_fmp(ticker, result['earnings_history'], fmp_client)
        except Exception as e:
            logger.debug(f"Could not get earnings history for {ticker}: {e}")

        # Get analyst estimates
        try:
            estimates = fmp_client.get_analyst_estimates(ticker)
            if estimates and len(estimates) > 0:
                latest = estimates[0]
                result['estimates'] = {
                    'eps_estimate': latest.get('estimatedEpsAvg'),
                    'eps_low': latest.get('estimatedEpsLow'),
                    'eps_high': latest.get('estimatedEpsHigh'),
                    'revenue_estimate': latest.get('estimatedRevenueAvg'),
                    'num_analysts': latest.get('numberAnalystEstimatedEps', 0),
                    'revision_trend': 'STABLE',  # Would need historical estimates to determine
                    'revision_30d_change': None
                }
        except Exception as e:
            logger.debug(f"Could not get analyst estimates for {ticker}: {e}")

        return result

    except Exception as e:
        logger.error(f"Error fetching earnings data for {ticker}: {e}")
        return result


def _add_price_moves_fmp(ticker: str, history: List[Dict], fmp_client) -> List[Dict]:
    """
    Add price movement data around each historical earnings date using FMP.
    """
    if not history or not fmp_client:
        return history

    try:
        # Get enough price history to cover all earnings
        oldest_date = min(h['date'] for h in history if h.get('date'))
        start_date = (oldest_date - timedelta(days=10)).strftime('%Y-%m-%d')

        prices = fmp_client.get_historical_prices(ticker, from_date=start_date)
        if not prices or 'historical' not in prices:
            return history

        price_data = {p['date']: p['close'] for p in prices.get('historical', [])}

        for h in history:
            try:
                earnings_date = h['date']
                if not earnings_date:
                    continue

                earnings_str = earnings_date.strftime('%Y-%m-%d')

                # Find closest trading days before and after earnings
                for offset in range(1, 6):
                    before_date = (earnings_date - timedelta(days=offset)).strftime('%Y-%m-%d')
                    if before_date in price_data:
                        h['price_before'] = price_data[before_date]
                        break

                for offset in range(1, 6):
                    after_date = (earnings_date + timedelta(days=offset)).strftime('%Y-%m-%d')
                    if after_date in price_data:
                        h['price_after'] = price_data[after_date]
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


def fetch_earnings_data_simple(ticker: str, fmp_client=None, profile_data: Dict = None) -> Dict[str, Any]:
    """
    Simplified earnings data fetch using profile data that's already available.

    Args:
        ticker: Stock symbol
        fmp_client: FMP client (optional, for additional data)
        profile_data: Profile data from FMP get_profile() call

    Returns:
        Dict with earnings info
    """
    result = {
        'next_earnings_date': None,
        'timing': 'UNKNOWN',
        'earnings_history': [],
        'estimates': {}
    }

    # Try to get from profile data first (already fetched)
    if profile_data:
        earnings_str = profile_data.get('earningsAnnouncement')
        if earnings_str:
            try:
                # Parse the earnings date string
                result['next_earnings_date'] = datetime.fromisoformat(earnings_str.replace('Z', '+00:00'))
            except:
                try:
                    result['next_earnings_date'] = datetime.strptime(earnings_str[:10], '%Y-%m-%d')
                except:
                    pass

    # If we have FMP client, get more data
    if fmp_client:
        full_data = fetch_earnings_data(ticker, fmp_client)
        # Merge, preferring already fetched data
        if full_data['next_earnings_date'] and not result['next_earnings_date']:
            result['next_earnings_date'] = full_data['next_earnings_date']
        result['timing'] = full_data.get('timing', result['timing'])
        result['earnings_history'] = full_data.get('earnings_history', [])
        result['estimates'] = full_data.get('estimates', {})

    return result
