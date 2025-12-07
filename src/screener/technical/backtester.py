"""
Walk-Forward Backtesting Framework

Metodología:
- Grid search parameter optimization
- Anchored walk-forward windows
- Out-of-sample validation
- Overfitting detection

Basado en:
- Han, Zhou & Zhu (2016) - Taming Momentum Crashes
- Dai (2021) - Risk reduction using trailing stop-loss rules
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class WalkForwardBacktester:
    """
    Walk-forward optimization framework for momentum strategies.

    Features:
    - Grid search parameter optimization
    - Anchored walk-forward windows
    - Trade-by-trade simulation
    - Out-of-sample validation
    - Overfitting detection
    """

    def __init__(self, prices_df: pd.DataFrame):
        """
        Initialize backtester.

        Args:
            prices_df: DataFrame with columns ['date', 'close', 'high', 'low', 'volume']
        """
        self.prices = prices_df.copy()
        self.prices['date'] = pd.to_datetime(self.prices['date'])
        self.prices = self.prices.sort_values('date').reset_index(drop=True)

    def run_walk_forward(
        self,
        parameter_grid: Dict,
        train_days: int = 250,
        test_days: int = 60,
        step_days: int = 30
    ) -> Dict:
        """
        Run complete walk-forward analysis.

        Args:
            parameter_grid: Dictionary of parameters to optimize
            train_days: Days for training window
            test_days: Days for testing window
            step_days: Days to step forward

        Returns:
            Complete results dictionary
        """
        logger.info("Starting walk-forward optimization...")

        # Default parameters (median values from typical grid)
        default_params = {
            'trailing_stop_pct': 10,
            'momentum_threshold': -5,
            'ma200_days_below': 5,
            'momentum_entry_min': 5
        }

        results = {
            'windows': [],
            'optimal_params': default_params.copy(),
            'in_sample_metrics': {},
            'out_sample_metrics': {},
            'degradation_ratio': {},
            'equity_curve': pd.DataFrame(),
            'all_trades': [],
            'parameter_stability': {}
        }

        # Generate walk-forward windows
        windows = self._generate_windows(train_days, test_days, step_days)
        logger.info(f"Generated {len(windows)} walk-forward windows")

        all_window_results = []

        for i, (train_start, train_end, test_start, test_end) in enumerate(windows):
            logger.info(f"Processing window {i+1}/{len(windows)}")

            # Get train and test data
            train_data = self.prices[
                (self.prices['date'] >= train_start) &
                (self.prices['date'] <= train_end)
            ].copy()

            # For test data, include 252 days before test_start for indicator warmup
            # (momentum_12m needs 252 days of history)
            test_warmup_start = test_start - timedelta(days=252)
            test_data_with_warmup = self.prices[
                (self.prices['date'] >= test_warmup_start) &
                (self.prices['date'] <= test_end)
            ].copy()

            # Mark the actual test period (for filtering after indicators calculated)
            test_period_start_idx = len(test_data_with_warmup[test_data_with_warmup['date'] < test_start])

            if len(train_data) < 100 or len(test_data_with_warmup) < 20:
                logger.warning(f"Insufficient data in window {i+1}, skipping")
                continue

            # Optimize parameters on training data
            best_params, best_score = self._optimize_parameters(train_data, parameter_grid)

            # Calculate test period size (actual test days, not including warmup)
            test_period_days = (test_end - test_start).days

            # Debug: Log what's happening in this window
            logger.info(f"🔍 Window {i+1}/{len(windows)} - Train: {len(train_data)} rows, Test: {test_period_days} days ({len(test_data_with_warmup)} with warmup)")
            logger.info(f"   Best params: {best_params}")
            logger.info(f"   Best score: {best_score:.2f}")

            # Backtest on training data (in-sample)
            train_trades, train_equity = self._backtest_strategy(train_data, best_params)
            train_metrics = self._calculate_metrics(train_trades, train_equity)

            logger.info(f"   Train trades: {len(train_trades)}, Sharpe: {train_metrics.get('sharpe_ratio', 0):.2f}")

            # Backtest on test data (out-of-sample)
            # Use data with warmup to calculate indicators properly
            test_trades_all, test_equity_all = self._backtest_strategy(test_data_with_warmup, best_params)

            # Debug: Log trades before filtering
            logger.info(f"   Test (before filter): {len(test_trades_all)} trades generated from warmup period")

            # Filter trades to only those that ENTER in the actual test period
            # (We want to test if the strategy generates valid entry signals in out-of-sample period)
            test_trades = [t for t in test_trades_all if t['entry_date'] >= test_start and t['entry_date'] <= test_end]

            # Debug: Show if filtering removed trades
            if len(test_trades_all) > 0 and len(test_trades) == 0:
                logger.warning(f"   ⚠️ All {len(test_trades_all)} test trades filtered out! Trades entered in warmup period.")
                if test_trades_all:
                    first_entry = test_trades_all[0]['entry_date']
                    last_entry = test_trades_all[-1]['entry_date']
                    logger.warning(f"   Trade entry date range: {first_entry} to {last_entry}")
                    logger.warning(f"   Test period: {test_start} to {test_end}")
                    logger.info(f"   → These trades entered BEFORE test period started (in warmup)")
            elif len(test_trades) > 0:
                logger.info(f"   ✅ {len(test_trades)} trades entered during test period")

            # Filter equity curve to test period only
            test_equity = test_equity_all[test_equity_all['date'] >= test_start].copy()

            test_metrics = self._calculate_metrics(test_trades, test_equity)

            logger.info(f"   Test trades: {len(test_trades)} (from {len(test_trades_all)} total), Sharpe: {test_metrics.get('sharpe_ratio', 0):.2f}")

            # Store window results
            window_result = {
                'window_id': i,
                'train_period': (train_start, train_end),
                'test_period': (test_start, test_end),
                'best_params': best_params,
                'train_metrics': train_metrics,
                'test_metrics': test_metrics,
                'train_trades': train_trades,
                'test_trades': test_trades,
                'degradation': self._calculate_degradation(train_metrics, test_metrics)
            }

            all_window_results.append(window_result)
            results['all_trades'].extend(test_trades)  # Only out-of-sample trades

        if not all_window_results:
            logger.error("No valid windows processed")
            return results

        # Aggregate results across all windows
        results['windows'] = all_window_results
        results['optimal_params'] = self._aggregate_best_params(all_window_results)
        results['in_sample_metrics'] = self._aggregate_metrics([w['train_metrics'] for w in all_window_results])
        results['out_sample_metrics'] = self._aggregate_metrics([w['test_metrics'] for w in all_window_results])
        results['degradation_ratio'] = self._aggregate_degradation([w['degradation'] for w in all_window_results])
        results['parameter_stability'] = self._analyze_parameter_stability(all_window_results)

        # Build combined equity curve
        results['equity_curve'] = self._build_equity_curve(all_window_results)

        logger.info("Walk-forward optimization complete")
        return results

    def _generate_windows(
        self,
        train_days: int,
        test_days: int,
        step_days: int
    ) -> List[Tuple]:
        """Generate anchored walk-forward windows."""
        windows = []

        start_date = self.prices['date'].min()
        end_date = self.prices['date'].max()

        current_train_end = start_date + timedelta(days=train_days)

        while current_train_end + timedelta(days=test_days) <= end_date:
            train_start = start_date
            train_end = current_train_end
            test_start = train_end + timedelta(days=1)
            test_end = test_start + timedelta(days=test_days)

            windows.append((train_start, train_end, test_start, test_end))

            # Step forward (anchored, so only test period moves)
            current_train_end += timedelta(days=step_days)

        return windows

    def _optimize_parameters(
        self,
        train_data: pd.DataFrame,
        parameter_grid: Dict
    ) -> Tuple[Dict, float]:
        """
        Grid search optimization on training data.

        Returns:
            (best_params, best_score)
        """
        from itertools import product

        # Generate all parameter combinations
        param_names = list(parameter_grid.keys())
        param_values = list(parameter_grid.values())

        best_score = -np.inf
        best_params = None

        for combination in product(*param_values):
            params = dict(zip(param_names, combination))

            # Backtest with these parameters
            trades, equity = self._backtest_strategy(train_data, params)

            if not trades:
                continue

            metrics = self._calculate_metrics(trades, equity)

            # Multi-objective score
            score = self._calculate_combined_score(metrics)

            if score > best_score:
                best_score = score
                best_params = params.copy()

        # If no valid parameters found, use median values from grid
        if best_params is None:
            logger.warning("No valid parameters found in grid search, using median values")
            best_params = {}
            for param_name, param_vals in zip(param_names, param_values):
                best_params[param_name] = np.median(param_vals)
            best_score = 0

        return best_params, best_score

    def _backtest_strategy(
        self,
        data: pd.DataFrame,
        params: Dict
    ) -> Tuple[List[Dict], pd.DataFrame]:
        """
        Backtest momentum strategy with given parameters.

        Returns:
            (trades, equity_curve)
        """
        # Calculate indicators
        data = data.copy()
        data = self._calculate_indicators(data)

        trades = []
        in_position = False
        entry_price = 0
        entry_date = None
        highest_price = 0
        days_below_ma200 = 0  # Track consecutive days below MA200

        equity = []  # Equity curve (one value per data row)
        current_equity = 10000  # Starting capital
        position_size = 0

        # Debug counters
        entry_signals = 0
        exit_signals = 0
        skipped_no_momentum = 0
        immediate_exits = 0  # Track exits on same/next day

        for i in range(len(data)):
            row = data.iloc[i]

            # Check entry conditions
            if not in_position:
                # Debug: Check why entry signals fail
                if pd.isna(row['momentum_12m']):
                    skipped_no_momentum += 1

                if self._check_entry_signal(row, params):
                    entry_signals += 1
                    in_position = True
                    entry_price = row['close']
                    entry_date = row['date']
                    highest_price = entry_price
                    position_size = current_equity  # Full position
                    days_below_ma200 = 0  # Reset counter

                    # Debug: Log entry for troubleshooting
                    logger.debug(f"      ENTRY: {row['date']} @ ${entry_price:.2f}, momentum={row.get('momentum_12m', 0):.1f}%")

            # Check exit conditions
            elif in_position:
                highest_price = max(highest_price, row['high'])

                # Update days below MA200 counter
                if not pd.isna(row['ma_200']) and row['close'] < row['ma_200']:
                    days_below_ma200 += 1
                else:
                    days_below_ma200 = 0  # Reset if back above

                exit_signal, exit_reason = self._check_exit_signal(
                    row, params, entry_price, highest_price, days_below_ma200
                )

                if exit_signal:
                    exit_signals += 1

                    # Track immediate exits (0-1 day duration)
                    duration = (row['date'] - entry_date).days
                    if duration <= 1:
                        immediate_exits += 1

                    # Debug: Log exit for troubleshooting
                    logger.debug(f"      EXIT: {row['date']} @ ${row['close']:.2f}, Duration={duration}d, Reason={exit_reason}")

                    # Close trade
                    exit_price = row['close']
                    pnl = (exit_price - entry_price) / entry_price
                    position_value = position_size * (1 + pnl)

                    trade = {
                        'entry_date': entry_date,
                        'exit_date': row['date'],
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'return_pct': pnl * 100,
                        'duration_days': duration,
                        'exit_reason': exit_reason
                    }

                    trades.append(trade)
                    current_equity = position_value
                    in_position = False
                    days_below_ma200 = 0  # Reset counter

            # Update equity curve
            if in_position:
                current_value = position_size * (row['close'] / entry_price)
                equity.append(current_value)
            else:
                equity.append(current_equity)

        # Debug logging
        logger.info(f"🔍 DEBUG Backtest: {len(data)} rows → {len(trades)} trades")
        logger.info(f"   Entry signals: {entry_signals}, Exit signals: {exit_signals}")
        logger.info(f"   Immediate exits (≤1 day): {immediate_exits}/{exit_signals if exit_signals > 0 else 0}")
        logger.info(f"   Skipped (no momentum_12m): {skipped_no_momentum}/{len(data)}")

        # If we have entries but no completed trades, investigate
        if entry_signals > 0 and len(trades) == 0:
            logger.warning(f"   ⚠️ {entry_signals} entries generated but 0 completed trades!")
            logger.warning(f"   This suggests positions are still open at end of backtest period")

        if len(data) > 0:
            logger.info(f"   Date range: {data.iloc[0]['date']} to {data.iloc[-1]['date']}")
            valid_momentum = data['momentum_12m'].notna().sum()
            logger.info(f"   Valid momentum rows: {valid_momentum}/{len(data)} ({valid_momentum/len(data)*100:.1f}%)")
            if valid_momentum > 0:
                logger.info(f"   Momentum 12M range: {data['momentum_12m'].min():.1f}% to {data['momentum_12m'].max():.1f}%")
                logger.info(f"   Entry threshold: {params.get('momentum_entry_min', 0)}%")

        equity_df = pd.DataFrame({
            'date': data['date'],
            'equity': equity
        })

        return trades, equity_df

    def _calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators needed for strategy."""
        # Momentum 12M, 6M, 3M, 1M
        data['momentum_12m'] = data['close'].pct_change(252) * 100
        data['momentum_6m'] = data['close'].pct_change(126) * 100
        data['momentum_3m'] = data['close'].pct_change(63) * 100
        data['momentum_1m'] = data['close'].pct_change(21) * 100

        # Moving averages
        data['ma_50'] = data['close'].rolling(50).mean()
        data['ma_200'] = data['close'].rolling(200).mean()

        # Distance from MA200
        data['distance_ma200'] = ((data['close'] - data['ma_200']) / data['ma_200'] * 100)

        return data

    def _check_entry_signal(self, row: pd.Series, params: Dict) -> bool:
        """Check if entry conditions are met."""
        # Momentum-based entry
        if pd.isna(row['momentum_12m']):
            return False

        conditions = [
            row['momentum_12m'] > params.get('momentum_entry_min', 0),
            row['close'] > row['ma_200'] if not pd.isna(row['ma_200']) else True,
        ]

        return all(conditions)

    def _check_exit_signal(
        self,
        row: pd.Series,
        params: Dict,
        entry_price: float,
        highest_price: float,
        days_below_ma200: int
    ) -> Tuple[bool, str]:
        """Check if exit conditions are met."""
        # Trailing stop
        trailing_stop_pct = params.get('trailing_stop_pct', 10) / 100
        stop_price = highest_price * (1 - trailing_stop_pct)

        if row['close'] < stop_price:
            return True, f"Trailing stop ({params.get('trailing_stop_pct')}%)"

        # Momentum deterioration
        if not pd.isna(row['momentum_12m']):
            momentum_threshold = params.get('momentum_threshold', -5)
            if row['momentum_12m'] < momentum_threshold:
                return True, f"Momentum deterioration (<{momentum_threshold}%)"

        # Below MA200 for X consecutive days
        ma200_days_threshold = params.get('ma200_days_below', 5)
        if days_below_ma200 >= ma200_days_threshold:
            return True, f"Below MA200 for {days_below_ma200} days"

        return False, None

    def _calculate_metrics(
        self,
        trades: List[Dict],
        equity: pd.DataFrame
    ) -> Dict:
        """Calculate performance metrics."""
        if not trades:
            return {
                'sharpe_ratio': 0,
                'total_return': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'max_drawdown': 0,
                'num_trades': 0,
                'avg_trade_duration': 0,
                'avg_win': 0,
                'avg_loss': 0
            }

        returns = [t['return_pct'] / 100 for t in trades]

        # Sharpe ratio (annualized)
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0

        # Total return
        total_return = ((equity['equity'].iloc[-1] / equity['equity'].iloc[0]) - 1) * 100

        # Win rate
        wins = [r for r in returns if r > 0]
        win_rate = len(wins) / len(returns) * 100 if returns else 0

        # Profit factor
        gross_profit = sum([r for r in returns if r > 0])
        gross_loss = abs(sum([r for r in returns if r < 0]))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Max drawdown
        equity_values = equity['equity'].values
        running_max = np.maximum.accumulate(equity_values)
        drawdown = (equity_values - running_max) / running_max * 100
        max_drawdown = drawdown.min()

        # Average trade duration
        avg_duration = np.mean([t['duration_days'] for t in trades])

        return {
            'sharpe_ratio': sharpe,
            'total_return': total_return,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'max_drawdown': max_drawdown,
            'num_trades': len(trades),
            'avg_trade_duration': avg_duration,
            'avg_win': np.mean([r*100 for r in returns if r > 0]) if wins else 0,
            'avg_loss': np.mean([r*100 for r in returns if r < 0]) if any(r < 0 for r in returns) else 0
        }

    def _calculate_combined_score(self, metrics: Dict) -> float:
        """
        Multi-objective scoring function.

        Balance between Sharpe, drawdown, win rate, and profit factor.
        """
        sharpe = metrics['sharpe_ratio']
        dd = metrics['max_drawdown']
        wr = metrics['win_rate'] / 100
        pf = min(metrics['profit_factor'], 5) / 5  # Cap at 5

        # Penalty for too few trades
        num_trades = metrics['num_trades']
        trade_penalty = min(num_trades / 10, 1.0)  # Want at least 10 trades

        score = (
            sharpe * 0.40 +
            (1 + dd/100) * 0.25 +  # Less drawdown is better
            wr * 0.20 +
            pf * 0.15
        ) * trade_penalty

        return score

    def _calculate_degradation(
        self,
        train_metrics: Dict,
        test_metrics: Dict
    ) -> Dict:
        """Calculate degradation from in-sample to out-of-sample."""
        degradation = {}

        for key in ['sharpe_ratio', 'win_rate', 'profit_factor']:
            if train_metrics[key] > 0:
                deg = test_metrics[key] / train_metrics[key]
            else:
                deg = 0
            degradation[key] = deg

        # Overall degradation score
        degradation['overall'] = np.mean(list(degradation.values()))

        return degradation

    def _aggregate_best_params(self, window_results: List[Dict]) -> Dict:
        """Find most stable parameters across windows."""
        # Mode (most common) for each parameter
        all_params = [w['best_params'] for w in window_results if w['best_params']]

        if not all_params:
            # Return default parameters if no valid params found
            return {
                'trailing_stop_pct': 10,
                'momentum_threshold': -5,
                'ma200_days_below': 5,
                'momentum_entry_min': 5
            }

        aggregated = {}
        param_names = all_params[0].keys()

        for param in param_names:
            values = [p[param] for p in all_params if param in p and p[param] is not None]
            if values:
                # Use median for numerical stability
                aggregated[param] = np.median(values)
            else:
                # Default value if no valid values found
                aggregated[param] = 10 if 'stop' in param else 5

        return aggregated

    def _aggregate_metrics(self, metrics_list: List[Dict]) -> Dict:
        """Average metrics across windows."""
        if not metrics_list:
            return {}

        aggregated = {}
        metric_names = metrics_list[0].keys()

        for metric in metric_names:
            values = [m[metric] for m in metrics_list if not np.isnan(m.get(metric, np.nan))]
            aggregated[metric] = np.mean(values) if values else 0

        return aggregated

    def _aggregate_degradation(self, degradation_list: List[Dict]) -> Dict:
        """Average degradation across windows."""
        return self._aggregate_metrics(degradation_list)

    def _analyze_parameter_stability(self, window_results: List[Dict]) -> Dict:
        """Analyze how stable parameters are across windows."""
        all_params = [w['best_params'] for w in window_results]

        stability = {}
        param_names = all_params[0].keys()

        for param in param_names:
            values = [p[param] for p in all_params]
            stability[param] = {
                'mean': np.mean(values),
                'std': np.std(values),
                'min': np.min(values),
                'max': np.max(values),
                'cv': np.std(values) / np.mean(values) if np.mean(values) > 0 else 0  # Coefficient of variation
            }

        return stability

    def _build_equity_curve(self, window_results: List[Dict]) -> pd.DataFrame:
        """Build combined equity curve from out-of-sample periods."""
        equity_curves = []

        for w in window_results:
            test_start, test_end = w['test_period']

            # Include warmup period for proper indicator calculation
            test_warmup_start = test_start - timedelta(days=252)
            test_data_with_warmup = self.prices[
                (self.prices['date'] >= test_warmup_start) &
                (self.prices['date'] <= test_end)
            ].copy()

            # Run backtest with warmup data
            _, equity_all = self._backtest_strategy(test_data_with_warmup, w['best_params'])

            # Filter equity curve to actual test period
            equity = equity_all[equity_all['date'] >= test_start].copy()

            if not equity.empty:
                equity_curves.append(equity)

        if not equity_curves:
            return pd.DataFrame()

        # Concatenate all equity curves
        combined = pd.concat(equity_curves, ignore_index=True)

        return combined
