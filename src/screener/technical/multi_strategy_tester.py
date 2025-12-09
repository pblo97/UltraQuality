"""
Multi-Strategy Backtester - Simple Price-Based Strategies

Based on academic research (2024):
- "Primary price-based features consistently outperformed technical indicators"
- "Simple strategies often outperform complex technical indicator strategies"
- Avoid overfitting by using minimal indicators

NO RSI, NO MACD, NO Bollinger Bands - solo precio y volumen.

References:
- arxiv.org/html/2412.15448v1 (Dec 2024)
- ScienceDirect 2024 - Backtest overfitting study
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class MultiStrategyTester:
    """
    Tests 3 SIMPLE strategies on quality/value stocks.

    Strategies:
    1. Price-Volume Simple (PRIORITY) - Literature-backed best performer
    2. Pullback Simple - Price action only
    3. Momentum Puro - Baseline comparison
    """

    def __init__(self, prices_df: pd.DataFrame):
        """
        Initialize tester.

        Args:
            prices_df: DataFrame with columns ['date', 'close', 'high', 'low', 'volume']
        """
        self.prices = prices_df.copy()
        self.prices['date'] = pd.to_datetime(self.prices['date'])
        self.prices = self.prices.sort_values('date').reset_index(drop=True)

        # Strategy definitions
        self.strategies = {
            'price_volume_simple': {
                'name': 'Price-Volume Simple',
                'description': 'Precio > MA200 + Volumen alto + Momentum 3m positivo',
                'priority': 1,  # MÁXIMA PRIORIDAD
                'params': {
                    'trailing_stop_pct': 15,  # Dai et al. (2021)
                    'volume_multiplier': 1.5,  # Volumen > 1.5x promedio
                    'ma_period': 200,
                    'momentum_3m_min': 0,  # Momentum 3 meses > 0%
                    'ma200_exit_days': 3,  # 3 días consecutivos debajo
                }
            },
            'pullback_simple': {
                'name': 'Pullback Simple',
                'description': 'Uptrend + Pullback a MA50 + Volumen',
                'priority': 2,
                'params': {
                    'trailing_stop_pct': 15,
                    'ma_long': 200,  # Define uptrend
                    'ma_short': 50,  # Nivel de pullback
                    'pullback_tolerance': 0.02,  # 2% de la MA50
                    'volume_multiplier': 1.0,  # Volumen normal
                }
            },
            'momentum_puro': {
                'name': 'Momentum Puro',
                'description': 'Momentum 12m + MA200 (baseline)',
                'priority': 3,
                'params': {
                    'trailing_stop_pct': 15,
                    'momentum_12m_min': 5,  # >5% anual
                    'momentum_3m_exit': -5,  # Sale si momentum 3m < -5%
                    'ma_period': 200,
                }
            }
        }

    def _calculate_indicators(self, data: pd.DataFrame, strategy_name: str) -> pd.DataFrame:
        """
        Calculate ONLY the indicators needed for the specific strategy.
        No RSI, no MACD, no BB - solo precio y volumen.
        """
        df = data.copy()
        strategy = self.strategies[strategy_name]
        params = strategy['params']

        # Indicadores comunes (precio)
        if 'ma_period' in params:
            df['ma_200'] = df['close'].rolling(window=params['ma_period']).mean()

        if 'ma_long' in params:
            df['ma_200'] = df['close'].rolling(window=params['ma_long']).mean()
        if 'ma_short' in params:
            df['ma_50'] = df['close'].rolling(window=params['ma_short']).mean()

        # Momentum
        if 'momentum_12m_min' in params or 'momentum_3m_min' in params:
            df['momentum_12m'] = df['close'].pct_change(252) * 100  # 252 trading days = 1 año
            df['momentum_3m'] = df['close'].pct_change(63) * 100   # 63 trading days = 3 meses

        # Volumen promedio
        if 'volume_multiplier' in params:
            df['avg_volume_20d'] = df['volume'].rolling(window=20).mean()

        # Tracking de días consecutivos debajo de MA200
        if 'ma200_exit_days' in params:
            df['below_ma200'] = df['close'] < df['ma_200']
            df['days_below_ma200'] = 0

            consecutive_days = 0
            days_below = []
            for below in df['below_ma200']:
                if below:
                    consecutive_days += 1
                else:
                    consecutive_days = 0
                days_below.append(consecutive_days)
            df['days_below_ma200'] = days_below

        return df

    def _check_entry_signal(
        self,
        row: pd.Series,
        strategy_name: str,
        position_open: bool
    ) -> bool:
        """
        Check entry signal for specific strategy.
        Returns True if should enter position.
        """
        if position_open:
            return False

        strategy = self.strategies[strategy_name]
        params = strategy['params']

        # Strategy 1: Price-Volume Simple (PRIORITY)
        if strategy_name == 'price_volume_simple':
            # Todas las condiciones deben cumplirse
            conditions = []

            # 1. Precio > MA200
            if not pd.isna(row['ma_200']):
                conditions.append(row['close'] > row['ma_200'])
            else:
                return False  # Necesita MA200

            # 2. Volumen > 1.5x promedio
            if not pd.isna(row['avg_volume_20d']) and row['avg_volume_20d'] > 0:
                conditions.append(row['volume'] > params['volume_multiplier'] * row['avg_volume_20d'])
            else:
                conditions.append(True)  # Si no hay datos de volumen, ignora esta condición

            # 3. Momentum 3m > 0%
            if not pd.isna(row['momentum_3m']):
                conditions.append(row['momentum_3m'] > params['momentum_3m_min'])
            else:
                return False  # Necesita momentum

            return all(conditions)

        # Strategy 2: Pullback Simple
        elif strategy_name == 'pullback_simple':
            conditions = []

            # 1. Uptrend: Precio > MA200
            if not pd.isna(row['ma_200']):
                conditions.append(row['close'] > row['ma_200'])
            else:
                return False

            # 2. Pullback a MA50: precio toca MA50 (±2%)
            if not pd.isna(row['ma_50']):
                distance_to_ma50 = abs(row['close'] - row['ma_50']) / row['ma_50']
                conditions.append(distance_to_ma50 <= params['pullback_tolerance'])
            else:
                return False

            # 3. Volumen normal o alto
            if not pd.isna(row['avg_volume_20d']) and row['avg_volume_20d'] > 0:
                conditions.append(row['volume'] >= params['volume_multiplier'] * row['avg_volume_20d'])
            else:
                conditions.append(True)

            return all(conditions)

        # Strategy 3: Momentum Puro (baseline)
        elif strategy_name == 'momentum_puro':
            conditions = []

            # 1. Momentum 12m > 5%
            if not pd.isna(row['momentum_12m']):
                conditions.append(row['momentum_12m'] > params['momentum_12m_min'])
            else:
                return False

            # 2. Precio > MA200
            if not pd.isna(row['ma_200']):
                conditions.append(row['close'] > row['ma_200'])
            else:
                return False

            return all(conditions)

        return False

    def _check_exit_signal(
        self,
        row: pd.Series,
        entry_price: float,
        max_price: float,
        strategy_name: str
    ) -> Tuple[bool, str]:
        """
        Check exit signal for specific strategy.
        Returns (should_exit, exit_reason).
        """
        strategy = self.strategies[strategy_name]
        params = strategy['params']

        # Trailing stop (común a todas las estrategias)
        trailing_stop_pct = params['trailing_stop_pct']
        trailing_stop_price = max_price * (1 - trailing_stop_pct / 100)

        if row['close'] <= trailing_stop_price:
            return True, f"trailing_stop_{trailing_stop_pct}pct"

        # Strategy-specific exits

        # Strategy 1: Price-Volume Simple
        if strategy_name == 'price_volume_simple':
            # Exit: 3 días consecutivos debajo de MA200
            if 'days_below_ma200' in row and row['days_below_ma200'] >= params['ma200_exit_days']:
                return True, "below_ma200_3days"

        # Strategy 2: Pullback Simple
        elif strategy_name == 'pullback_simple':
            # Exit: Precio rompe MA200 a la baja
            if not pd.isna(row['ma_200']) and row['close'] < row['ma_200']:
                return True, "break_ma200"

        # Strategy 3: Momentum Puro
        elif strategy_name == 'momentum_puro':
            # Exit: Momentum 3m < -5%
            if not pd.isna(row['momentum_3m']) and row['momentum_3m'] < params['momentum_3m_exit']:
                return True, "momentum_deterioration"

        return False, ""

    def backtest_strategy(
        self,
        strategy_name: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict:
        """
        Backtest a single strategy.

        Returns:
            Dictionary with trades, metrics, and equity curve
        """
        logger.info(f"Backtesting strategy: {self.strategies[strategy_name]['name']}")

        # Filter date range
        data = self.prices.copy()
        if start_date:
            data = data[data['date'] >= start_date]
        if end_date:
            data = data[data['date'] <= end_date]

        # Calculate indicators
        data = self._calculate_indicators(data, strategy_name)

        # Simulate trades
        trades = []
        position_open = False
        entry_price = 0
        entry_date = None
        max_price = 0

        for idx, row in data.iterrows():
            # Check entry
            if not position_open:
                if self._check_entry_signal(row, strategy_name, position_open):
                    position_open = True
                    entry_price = row['close']
                    entry_date = row['date']
                    max_price = row['close']

            # Check exit
            else:
                # Update max price for trailing stop
                if row['close'] > max_price:
                    max_price = row['close']

                should_exit, exit_reason = self._check_exit_signal(
                    row, entry_price, max_price, strategy_name
                )

                if should_exit:
                    trade = {
                        'entry_date': entry_date,
                        'exit_date': row['date'],
                        'entry_price': entry_price,
                        'exit_price': row['close'],
                        'return_pct': ((row['close'] - entry_price) / entry_price) * 100,
                        'holding_days': (row['date'] - entry_date).days,
                        'exit_reason': exit_reason,
                        'max_price': max_price,
                    }
                    trades.append(trade)

                    position_open = False
                    entry_price = 0
                    entry_date = None
                    max_price = 0

        # Calculate metrics
        metrics = self._calculate_metrics(trades)

        return {
            'strategy_name': self.strategies[strategy_name]['name'],
            'strategy_key': strategy_name,
            'description': self.strategies[strategy_name]['description'],
            'priority': self.strategies[strategy_name]['priority'],
            'trades': trades,
            'metrics': metrics,
            'num_trades': len(trades)
        }

    def _calculate_metrics(self, trades: List[Dict]) -> Dict:
        """Calculate performance metrics from trades."""
        if not trades:
            return {
                'total_return': 0,
                'sharpe_ratio': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'max_drawdown': 0,
                'num_trades': 0,
                'avg_trade_duration': 0,
                'avg_win': 0,
                'avg_loss': 0,
            }

        returns = [t['return_pct'] for t in trades]
        wins = [r for r in returns if r > 0]
        losses = [r for r in returns if r <= 0]

        # Total return (compounded)
        total_return = np.prod([1 + r/100 for r in returns]) - 1

        # Sharpe ratio (annualized)
        if len(returns) > 1:
            avg_return = np.mean(returns)
            std_return = np.std(returns, ddof=1)
            if std_return > 0:
                sharpe_ratio = (avg_return / std_return) * np.sqrt(252 / np.mean([t['holding_days'] for t in trades]))
            else:
                sharpe_ratio = 0
        else:
            sharpe_ratio = 0

        # Win rate
        win_rate = (len(wins) / len(trades)) * 100 if trades else 0

        # Profit factor
        total_wins = sum(wins) if wins else 0
        total_losses = abs(sum(losses)) if losses else 0
        profit_factor = total_wins / total_losses if total_losses > 0 else (float('inf') if total_wins > 0 else 0)

        # Max drawdown
        cumulative = np.cumprod([1 + r/100 for r in returns])
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = np.min(drawdown) * 100 if len(drawdown) > 0 else 0

        return {
            'total_return': total_return * 100,
            'sharpe_ratio': sharpe_ratio,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'max_drawdown': max_drawdown,
            'num_trades': len(trades),
            'avg_trade_duration': np.mean([t['holding_days'] for t in trades]) if trades else 0,
            'avg_win': np.mean(wins) if wins else 0,
            'avg_loss': np.mean(losses) if losses else 0,
        }

    def run_all_strategies(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Run all 3 strategies and return results sorted by priority.

        Returns:
            List of results dictionaries, sorted by priority (1 = highest)
        """
        results = []

        for strategy_key in self.strategies.keys():
            result = self.backtest_strategy(strategy_key, start_date, end_date)
            results.append(result)

        # Sort by priority (1 first)
        results.sort(key=lambda x: x['priority'])

        return results

    def compare_strategies(self, results: List[Dict]) -> pd.DataFrame:
        """
        Create comparison table of all strategies.

        Returns:
            DataFrame with metrics comparison
        """
        comparison = []

        for result in results:
            metrics = result['metrics']
            comparison.append({
                'Strategy': result['strategy_name'],
                'Description': result['description'],
                'Trades': metrics['num_trades'],
                'Win Rate (%)': f"{metrics['win_rate']:.1f}%",
                'Total Return (%)': f"{metrics['total_return']:.1f}%",
                'Sharpe Ratio': f"{metrics['sharpe_ratio']:.2f}",
                'Profit Factor': f"{metrics['profit_factor']:.2f}",
                'Max Drawdown (%)': f"{metrics['max_drawdown']:.1f}%",
                'Avg Win (%)': f"{metrics['avg_win']:.2f}%",
                'Avg Loss (%)': f"{metrics['avg_loss']:.2f}%",
                'Avg Days': f"{metrics['avg_trade_duration']:.0f}",
            })

        return pd.DataFrame(comparison)

    def _generate_windows(
        self,
        train_days: int,
        test_days: int,
        step_days: int
    ) -> List[Tuple[datetime, datetime, datetime, datetime]]:
        """
        Generate walk-forward windows (anchored).

        Returns:
            List of tuples: (train_start, train_end, test_start, test_end)
        """
        windows = []
        min_date = self.prices['date'].min()
        max_date = self.prices['date'].max()

        # Start from min_date + train_days
        current_train_end_idx = train_days

        while current_train_end_idx + test_days < len(self.prices):
            train_start = min_date
            train_end = self.prices.iloc[current_train_end_idx]['date']
            test_start = self.prices.iloc[current_train_end_idx + 1]['date']
            test_end_idx = min(current_train_end_idx + test_days, len(self.prices) - 1)
            test_end = self.prices.iloc[test_end_idx]['date']

            windows.append((train_start, train_end, test_start, test_end))

            # Step forward
            current_train_end_idx += step_days

        return windows

    def run_walk_forward_all_strategies(
        self,
        train_days: int = 250,
        test_days: int = 60,
        step_days: int = 30
    ) -> List[Dict]:
        """
        Run walk-forward backtesting for all 3 strategies.

        This provides out-of-sample validation to detect overfitting.

        Args:
            train_days: Days for training window
            test_days: Days for testing window (out-of-sample)
            step_days: Days to step forward

        Returns:
            List of dictionaries with walk-forward results for each strategy
        """
        logger.info("Starting walk-forward validation for all strategies")

        # Generate walk-forward windows
        windows = self._generate_windows(train_days, test_days, step_days)
        logger.info(f"Generated {len(windows)} walk-forward windows")

        results = []

        for strategy_key in self.strategies.keys():
            strategy = self.strategies[strategy_key]
            logger.info(f"Testing strategy: {strategy['name']}")

            # Collect all trades separated by in-sample and out-of-sample
            in_sample_trades = []
            out_sample_trades = []

            for window_idx, (train_start, train_end, test_start, test_end) in enumerate(windows):
                # Backtest on training window (in-sample)
                train_result = self.backtest_strategy(
                    strategy_key,
                    start_date=train_start,
                    end_date=train_end
                )
                in_sample_trades.extend(train_result['trades'])

                # Backtest on test window (out-of-sample)
                test_result = self.backtest_strategy(
                    strategy_key,
                    start_date=test_start,
                    end_date=test_end
                )
                out_sample_trades.extend(test_result['trades'])

            # Calculate metrics for in-sample and out-of-sample
            in_sample_metrics = self._calculate_metrics(in_sample_trades)
            out_sample_metrics = self._calculate_metrics(out_sample_trades)

            # Calculate degradation ratio
            degradation = self._calculate_degradation(in_sample_metrics, out_sample_metrics)

            # Store results
            results.append({
                'strategy_name': strategy['name'],
                'strategy_key': strategy_key,
                'description': strategy['description'],
                'priority': strategy['priority'],
                'in_sample_metrics': in_sample_metrics,
                'out_sample_metrics': out_sample_metrics,
                'degradation': degradation,
                'num_windows': len(windows),
                'in_sample_trades': in_sample_trades,
                'out_sample_trades': out_sample_trades,
            })

        # Sort by priority
        results.sort(key=lambda x: x['priority'])

        return results

    def _calculate_degradation(self, in_sample: Dict, out_sample: Dict) -> Dict:
        """
        Calculate degradation ratio (out-of-sample / in-sample).

        Lower degradation = better generalization.
        """
        degradation = {}

        metrics_to_check = [
            'sharpe_ratio',
            'total_return',
            'win_rate',
            'profit_factor',
            'max_drawdown',
            'num_trades',
            'avg_trade_duration'
        ]

        for metric in metrics_to_check:
            in_val = in_sample.get(metric, 0)
            out_val = out_sample.get(metric, 0)

            # Handle special case: max_drawdown (more negative is worse)
            if metric == 'max_drawdown':
                if in_val < 0:
                    degradation[metric] = out_val / in_val
                else:
                    degradation[metric] = 1.0
            # Handle division by zero
            elif in_val != 0:
                degradation[metric] = out_val / in_val
            else:
                degradation[metric] = 0.0 if out_val == 0 else float('inf')

        # Calculate overall degradation (average of key metrics)
        key_metrics = ['sharpe_ratio', 'win_rate', 'profit_factor']
        valid_degradations = [degradation[m] for m in key_metrics if degradation[m] not in [0, float('inf')]]

        if valid_degradations:
            degradation['overall'] = np.mean(valid_degradations)
        else:
            degradation['overall'] = 0.0

        return degradation

    def compare_walk_forward_results(self, results: List[Dict]) -> pd.DataFrame:
        """
        Create comparison table with walk-forward results.

        Shows in-sample, out-of-sample, and degradation for each strategy.

        Returns:
            DataFrame with walk-forward metrics comparison
        """
        comparison = []

        for result in results:
            in_metrics = result['in_sample_metrics']
            out_metrics = result['out_sample_metrics']
            deg = result['degradation']

            comparison.append({
                'Strategy': result['strategy_name'],
                'Priority': result['priority'],

                # In-Sample (Training)
                'IS Trades': in_metrics['num_trades'],
                'IS Win Rate': f"{in_metrics['win_rate']:.1f}%",
                'IS Sharpe': f"{in_metrics['sharpe_ratio']:.2f}",
                'IS Return': f"{in_metrics['total_return']:.1f}%",

                # Out-of-Sample (Testing)
                'OOS Trades': out_metrics['num_trades'],
                'OOS Win Rate': f"{out_metrics['win_rate']:.1f}%",
                'OOS Sharpe': f"{out_metrics['sharpe_ratio']:.2f}",
                'OOS Return': f"{out_metrics['total_return']:.1f}%",

                # Degradation
                'Win Rate Deg': f"{deg['win_rate']:.2f}x",
                'Sharpe Deg': f"{deg['sharpe_ratio']:.2f}x",
                'Overall Deg': f"{deg['overall']:.2f}x",
            })

        return pd.DataFrame(comparison)

