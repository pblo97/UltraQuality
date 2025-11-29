"""
Backtesting module for overextension risk strategies.

Validates risk management strategies with historical data:
- How often do overextended stocks correct?
- Average correction magnitude
- Time to correction
- Scale-in strategy performance vs full entry
"""

from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import statistics
import logging

logger = logging.getLogger(__name__)


class OverextensionBacktester:
    """
    Backtest overextension risk detection and entry strategies.
    """

    def __init__(self, fmp_client):
        """
        Args:
            fmp_client: FMP client for fetching historical data
        """
        self.fmp = fmp_client

    def analyze_historical_overextensions(
        self,
        symbol: str,
        lookback_days: int = 730  # 2 years
    ) -> Dict:
        """
        Analyze all historical instances where stock was overextended.

        Args:
            symbol: Stock symbol
            lookback_days: How far back to look

        Returns:
            {
                'instances': int,
                'avg_correction_pct': float,
                'max_correction_pct': float,
                'min_correction_pct': float,
                'avg_days_to_correction': int,
                'correction_rate': float (0-1),
                'details': List[Dict]
            }
        """
        try:
            # Fetch historical data
            from_date = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
            hist_data = self.fmp.get_historical_prices(symbol, from_date=from_date)

            if not hist_data or 'historical' not in hist_data:
                return {'error': 'No historical data available'}

            prices = hist_data['historical'][::-1]  # Chronological order

            if len(prices) < 250:
                return {'error': 'Insufficient data (need 250+ days)'}

            # Find all instances where stock was >40% above MA200
            overextension_instances = []

            for i in range(250, len(prices)):
                # Calculate MA200 at this point
                ma_200 = sum(p['close'] for p in prices[i-200:i]) / 200
                current_price = prices[i]['close']
                distance_pct = ((current_price - ma_200) / ma_200 * 100)

                # If overextended (>40% above MA200)
                if distance_pct > 40:
                    # Look ahead to find correction
                    correction_found = False
                    days_to_correction = 0
                    max_correction = 0

                    for j in range(i + 1, min(i + 120, len(prices))):  # Look ahead 120 days max
                        future_price = prices[j]['close']
                        drawdown = ((future_price - current_price) / current_price * 100)

                        if drawdown < max_correction:
                            max_correction = drawdown

                        # Correction = pullback to MA200 or -15% drop
                        if future_price <= ma_200 or drawdown <= -15:
                            correction_found = True
                            days_to_correction = j - i
                            break

                    if correction_found or abs(max_correction) > 10:  # Include significant drawdowns
                        overextension_instances.append({
                            'date': prices[i]['date'],
                            'price': current_price,
                            'ma_200': ma_200,
                            'distance_pct': distance_pct,
                            'correction_pct': max_correction,
                            'days_to_correction': days_to_correction if correction_found else None,
                            'corrected_to_ma200': correction_found
                        })

                    # Skip ahead to avoid counting same overextension period multiple times
                    if correction_found:
                        i = j + 30  # Skip 30 days after correction

            # Calculate statistics
            if not overextension_instances:
                return {
                    'instances': 0,
                    'message': f'No overextension instances (>40% above MA200) found in {lookback_days} days'
                }

            corrections = [inst['correction_pct'] for inst in overextension_instances]
            correction_rate = sum(1 for inst in overextension_instances if inst['corrected_to_ma200']) / len(overextension_instances)

            days_to_corr = [inst['days_to_correction'] for inst in overextension_instances if inst['days_to_correction'] is not None]

            return {
                'instances': len(overextension_instances),
                'avg_correction_pct': statistics.mean(corrections) if corrections else 0,
                'median_correction_pct': statistics.median(corrections) if corrections else 0,
                'max_correction_pct': min(corrections) if corrections else 0,
                'min_correction_pct': max(corrections) if corrections else 0,
                'avg_days_to_correction': int(statistics.mean(days_to_corr)) if days_to_corr else None,
                'median_days_to_correction': int(statistics.median(days_to_corr)) if days_to_corr else None,
                'correction_rate': correction_rate,
                'details': overextension_instances[-10:]  # Last 10 instances
            }

        except Exception as e:
            logger.error(f"Error backtesting {symbol}: {e}", exc_info=True)
            return {'error': str(e)}

    def backtest_scale_in_strategy(
        self,
        symbol: str,
        overextension_date: str,
        entry_price: float,
        ma_50: float,
        ma_200: float
    ) -> Dict:
        """
        Backtest scale-in strategy performance vs full entry.

        Compares:
        - Full entry NOW (100% at current price)
        - Scale-in 2 tranches (60% now, 40% at -10%)
        - Scale-in 3 tranches (25% now, 35% at MA50, 40% at MA200)

        Args:
            symbol: Stock symbol
            overextension_date: Date when stock was overextended
            entry_price: Price at overextension
            ma_50: MA50 at that time
            ma_200: MA200 at that time

        Returns:
            {
                'full_entry_return': float,
                'scale_in_2_return': float,
                'scale_in_3_return': float,
                'best_strategy': str,
                'holding_period_days': int
            }
        """
        try:
            # Fetch historical data from overextension date + 180 days
            target_date = datetime.strptime(overextension_date, '%Y-%m-%d')
            end_date = (target_date + timedelta(days=180)).strftime('%Y-%m-%d')

            hist_data = self.fmp.get_historical_prices(
                symbol,
                from_date=overextension_date,
                to_date=end_date
            )

            if not hist_data or 'historical' not in hist_data:
                return {'error': 'No historical data available'}

            prices = hist_data['historical'][::-1]  # Chronological

            if len(prices) < 30:
                return {'error': 'Insufficient forward data'}

            # Strategy 1: Full entry at entry_price
            full_entry_avg_price = entry_price

            # Strategy 2: Scale-in 2 tranches (60% now, 40% at -10%)
            tranche_2_price = entry_price * 0.90
            scale_in_2_filled = [0.60]  # 60% filled immediately
            scale_in_2_avg = entry_price * 0.60

            # Strategy 3: Scale-in 3 tranches (25% now, 35% at MA50, 40% at MA200)
            scale_in_3_filled = [0.25]  # 25% filled immediately
            scale_in_3_avg = entry_price * 0.25

            # Simulate filling additional tranches
            for i, price_data in enumerate(prices[1:]):  # Skip first day (entry)
                price = price_data['close']

                # Check if tranche 2 of scale-in-2 filled
                if len(scale_in_2_filled) == 1 and price <= tranche_2_price:
                    scale_in_2_filled.append(0.40)
                    scale_in_2_avg = (scale_in_2_avg + price * 0.40) / sum(scale_in_2_filled)

                # Check if tranches of scale-in-3 filled
                if len(scale_in_3_filled) == 1 and price <= ma_50:
                    scale_in_3_filled.append(0.35)
                    scale_in_3_avg = (scale_in_3_avg + price * 0.35) / sum(scale_in_3_filled)
                elif len(scale_in_3_filled) == 2 and price <= ma_200:
                    scale_in_3_filled.append(0.40)
                    scale_in_3_avg = (scale_in_3_avg + price * 0.40) / sum(scale_in_3_filled)

            # Calculate returns at end of period (180 days or latest available)
            exit_price = prices[-1]['close']
            holding_days = len(prices) - 1

            full_entry_return = ((exit_price - full_entry_avg_price) / full_entry_avg_price * 100)

            # Scale-in returns weighted by filled percentage
            scale_in_2_filled_pct = sum(scale_in_2_filled)
            if scale_in_2_filled_pct > 0:
                scale_in_2_return = ((exit_price - scale_in_2_avg) / scale_in_2_avg * 100) * scale_in_2_filled_pct
            else:
                scale_in_2_return = 0

            scale_in_3_filled_pct = sum(scale_in_3_filled)
            if scale_in_3_filled_pct > 0:
                scale_in_3_return = ((exit_price - scale_in_3_avg) / scale_in_3_avg * 100) * scale_in_3_filled_pct
            else:
                scale_in_3_return = 0

            # Determine best strategy
            returns = {
                'Full Entry': full_entry_return,
                'Scale-in 2': scale_in_2_return,
                'Scale-in 3': scale_in_3_return
            }
            best_strategy = max(returns, key=returns.get)

            return {
                'full_entry_return': round(full_entry_return, 2),
                'full_entry_avg_price': round(full_entry_avg_price, 2),
                'scale_in_2_return': round(scale_in_2_return, 2),
                'scale_in_2_avg_price': round(scale_in_2_avg, 2),
                'scale_in_2_filled_pct': round(scale_in_2_filled_pct * 100, 1),
                'scale_in_3_return': round(scale_in_3_return, 2),
                'scale_in_3_avg_price': round(scale_in_3_avg, 2),
                'scale_in_3_filled_pct': round(scale_in_3_filled_pct * 100, 1),
                'best_strategy': best_strategy,
                'holding_period_days': holding_days,
                'exit_price': round(exit_price, 2)
            }

        except Exception as e:
            logger.error(f"Error backtesting scale-in for {symbol}: {e}", exc_info=True)
            return {'error': str(e)}

    def calculate_strategy_win_rate(
        self,
        instances: List[Dict],
        strategy: str = 'scale_in_3'
    ) -> Dict:
        """
        Calculate win rate for a given strategy across multiple instances.

        Args:
            instances: List of backtest results
            strategy: 'full_entry', 'scale_in_2', or 'scale_in_3'

        Returns:
            {
                'win_rate': float,
                'avg_return': float,
                'best_return': float,
                'worst_return': float
            }
        """
        if not instances:
            return {'error': 'No instances to analyze'}

        returns_key = f'{strategy}_return'
        returns = [inst[returns_key] for inst in instances if returns_key in inst]

        if not returns:
            return {'error': f'No returns found for {strategy}'}

        wins = sum(1 for r in returns if r > 0)
        win_rate = wins / len(returns)

        return {
            'win_rate': round(win_rate * 100, 1),
            'avg_return': round(statistics.mean(returns), 2),
            'median_return': round(statistics.median(returns), 2),
            'best_return': round(max(returns), 2),
            'worst_return': round(min(returns), 2),
            'total_instances': len(returns)
        }
