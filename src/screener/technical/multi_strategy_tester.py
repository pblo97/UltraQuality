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
    Academic momentum strategies for quality/value stocks.

    Focus on robust, evidence-based strategies:
    1. Momentum Academic Universal (MAIN) - Composite momentum with regime filter
    2. Momentum 12M Academic - 100 years of evidence baseline
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

        # Strategy definitions - Academic momentum only
        self.strategies = {
            'momentum_academic_universal': {
                'name': 'Momentum Academic Universal',
                'description': 'Composite Momentum (12-1m + 6-1m) + Regime Filter + ATR Sizing',
                'priority': 1,  # MAIN STRATEGY
                'params': {
                    'composite_momentum_min': 0,  # Composite > 0%
                    'ma_period': 200,  # Stock trend filter
                    'spy_ma_period': 200,  # Market regime filter (SPY)
                    'use_regime_filter': True,  # Require SPY > MA200
                    'atr_period': 14,  # For position sizing
                    'target_volatility': 0.15,  # 15% target risk
                    'ma200_exit': True,  # Exit if stock < MA200
                    'spy_exit': True,  # Exit if SPY < MA200 (bear market)
                }
            },
            'momentum_12m_academic': {
                'name': 'Momentum 12M Academic',
                'description': 'Baseline: Momentum 12m > 0% (Jegadeesh & Titman 1993-2001)',
                'priority': 2,  # BASELINE COMPARISON
                'params': {
                    'momentum_12m_min': 0,  # Simple momentum > 0%
                    'ma_period': 200,  # Trend filter
                    'spy_ma_period': 200,  # Market regime
                    'use_regime_filter': True,  # Require SPY > MA200
                    'ma200_exit': True,  # Exit if stock < MA200
                    'spy_exit': True,  # Exit if SPY < MA200
                }
            }
        }

    def _calculate_indicators(self, data: pd.DataFrame, strategy_name: str, spy_data: pd.DataFrame = None) -> pd.DataFrame:
        """
        Calculate academic momentum indicators.

        Args:
            data: Stock price data
            strategy_name: Strategy key
            spy_data: SPY data for market regime (optional)
        """
        df = data.copy()
        strategy = self.strategies[strategy_name]
        params = strategy['params']

        # Stock MA200 (trend filter)
        if 'ma_period' in params:
            df['ma_200'] = df['close'].rolling(window=params['ma_period']).mean()

        # Momentum calculations
        if 'momentum_12m_min' in params:
            # Simple momentum 12m (exclude last month to avoid reversal)
            df['momentum_12_1m'] = df['close'].pct_change(252 - 21) * 100  # 12-1 months
            df['momentum_12m'] = df['momentum_12_1m']  # For compatibility

        # Composite momentum (for universal strategy)
        if 'composite_momentum_min' in params:
            # Momentum 12-1 months
            df['momentum_12_1m'] = df['close'].pct_change(252 - 21) * 100
            # Momentum 6-1 months
            df['momentum_6_1m'] = df['close'].pct_change(126 - 21) * 100
            # Composite: 50% each
            df['composite_momentum'] = (0.5 * df['momentum_12_1m']) + (0.5 * df['momentum_6_1m'])

        # ATR for position sizing (volatility targeting)
        if 'atr_period' in params:
            high_low = df['high'] - df['low']
            high_close = np.abs(df['high'] - df['close'].shift())
            low_close = np.abs(df['low'] - df['close'].shift())

            true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            df['atr'] = true_range.rolling(window=params['atr_period']).mean()
            df['atr_pct'] = (df['atr'] / df['close']) * 100  # ATR as % of price

        # SPY regime filter + momentum relativo
        if 'spy_ma_period' in params and spy_data is not None:
            spy_df = spy_data.copy()

            # SPY MA200
            spy_df['spy_ma_200'] = spy_df['close'].rolling(window=params['spy_ma_period']).mean()

            # SPY REGIME MENSUAL (evaluar solo último día del mes)
            # Evita whipsaws en cruces volátiles diarios
            spy_df['date'] = pd.to_datetime(spy_df['date'])
            spy_df['year_month'] = spy_df['date'].dt.to_period('M')

            # Marcar último día de cada mes
            spy_df['is_month_end'] = spy_df.groupby('year_month')['date'].transform(lambda x: x == x.max())

            # Calcular régimen solo en fin de mes
            spy_df['spy_regime_raw'] = spy_df['close'] > spy_df['spy_ma_200']
            spy_df['spy_regime'] = None
            spy_df.loc[spy_df['is_month_end'], 'spy_regime'] = spy_df.loc[spy_df['is_month_end'], 'spy_regime_raw']

            # Forward fill: mantener régimen del último cierre mensual
            spy_df['spy_regime'] = spy_df['spy_regime'].fillna(method='ffill')

            # SPY MOMENTUM (para comparación relativa)
            spy_df['spy_momentum_12_1m'] = spy_df['close'].pct_change(252 - 21) * 100
            spy_df['spy_momentum_6_1m'] = spy_df['close'].pct_change(126 - 21) * 100

            # Merge SPY data to stock data by date
            df = df.merge(
                spy_df[['date', 'spy_ma_200', 'spy_regime', 'spy_momentum_12_1m', 'spy_momentum_6_1m']],
                on='date',
                how='left'
            )

            # Momentum Relativo: Stock momentum - SPY momentum
            if 'momentum_12_1m' in df.columns:
                df['momentum_relative_12m'] = df['momentum_12_1m'] - df['spy_momentum_12_1m']
            if 'momentum_6_1m' in df.columns:
                df['momentum_relative_6m'] = df['momentum_6_1m'] - df['spy_momentum_6_1m']

        return df

    def _check_entry_signal(
        self,
        row: pd.Series,
        strategy_name: str,
        position_open: bool
    ) -> bool:
        """
        Check entry signal (academic momentum strategies).
        """
        if position_open:
            return False

        strategy = self.strategies[strategy_name]
        params = strategy['params']

        # Strategy 1: Momentum Academic Universal (MAIN)
        if strategy_name == 'momentum_academic_universal':
            conditions = []

            # 1. Stock > MA200 (individual trend filter)
            if not pd.isna(row['ma_200']):
                conditions.append(row['close'] > row['ma_200'])
            else:
                return False

            # 2. Composite Momentum > 0%
            if not pd.isna(row['composite_momentum']):
                conditions.append(row['composite_momentum'] > params['composite_momentum_min'])
            else:
                return False

            # 3. Market regime filter (SPY > MA200)
            if params['use_regime_filter']:
                if 'spy_regime' in row and not pd.isna(row['spy_regime']):
                    conditions.append(row['spy_regime'] == True)  # Bull market required
                else:
                    return False  # No SPY data = no entry

            # 4. Momentum Relativo > 0 (Stock momentum > SPY momentum)
            # Evita comprar acciones débiles en mercado fuerte
            if 'momentum_relative_12m' in row and not pd.isna(row['momentum_relative_12m']):
                conditions.append(row['momentum_relative_12m'] > 0)  # Stock outperforms SPY
            # Si no hay datos de SPY momentum, permitir entrada (backward compatibility)

            return all(conditions)

        # Strategy 2: Momentum 12M Academic (BASELINE)
        elif strategy_name == 'momentum_12m_academic':
            conditions = []

            # 1. Stock > MA200
            if not pd.isna(row['ma_200']):
                conditions.append(row['close'] > row['ma_200'])
            else:
                return False

            # 2. Momentum 12m > 0%
            if not pd.isna(row['momentum_12m']):
                conditions.append(row['momentum_12m'] > params['momentum_12m_min'])
            else:
                return False

            # 3. Market regime filter (SPY > MA200)
            if params['use_regime_filter']:
                if 'spy_regime' in row and not pd.isna(row['spy_regime']):
                    conditions.append(row['spy_regime'] == True)
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
        Check exit signal (simple, robust rules).
        """
        strategy = self.strategies[strategy_name]
        params = strategy['params']

        # Exit 1: Stock breaks MA200 (loses trend)
        if params.get('ma200_exit', False):
            if not pd.isna(row['ma_200']) and row['close'] < row['ma_200']:
                return True, "stock_below_ma200"

        # Exit 2: SPY breaks MA200 (bear market)
        if params.get('spy_exit', False):
            if 'spy_regime' in row and not pd.isna(row['spy_regime']):
                if row['spy_regime'] == False:  # SPY < MA200
                    return True, "bear_market_spy"

        return False, ""

    def backtest_strategy(
        self,
        strategy_name: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        use_anchored: bool = False,
        spy_data: pd.DataFrame = None
    ) -> Dict:
        """
        Backtest a single strategy.

        Args:
            strategy_name: Strategy key to backtest
            start_date: Start date for trade simulation
            end_date: End date for trade simulation
            use_anchored: If True, calculate indicators with all data up to end_date
            spy_data: SPY data for market regime filter

        Returns:
            Dictionary with trades, metrics, and equity curve
        """
        logger.info(f"Backtesting strategy: {self.strategies[strategy_name]['name']}")

        # For anchored walk-forward: calculate indicators with all data up to end_date
        # Then filter to simulation range
        if use_anchored and end_date:
            # Calculate indicators with ALL historical data up to end_date
            data_for_indicators = self.prices[self.prices['date'] <= end_date].copy()
            data = self._calculate_indicators(data_for_indicators, strategy_name, spy_data)

            # Now filter to simulation range (for trade execution)
            if start_date:
                data = data[data['date'] >= start_date]
        else:
            # Original behavior: filter first, then calculate
            data = self.prices.copy()
            if start_date:
                data = data[data['date'] >= start_date]
            if end_date:
                data = data[data['date'] <= end_date]

            # Calculate indicators
            data = self._calculate_indicators(data, strategy_name, spy_data)

        # Simulate trades
        trades = []
        position_open = False
        entry_price = 0
        entry_date = None
        max_price = 0
        entry_atr_pct = 0  # Store ATR% at entry for position sizing

        for idx, row in data.iterrows():
            # Check entry
            if not position_open:
                if self._check_entry_signal(row, strategy_name, position_open):
                    position_open = True
                    entry_price = row['close']
                    entry_date = row['date']
                    max_price = row['close']
                    # Store ATR% for position sizing calculation
                    entry_atr_pct = row.get('atr_pct', 0)

            # Check exit
            else:
                # Update max price for trailing stop
                if row['close'] > max_price:
                    max_price = row['close']

                should_exit, exit_reason = self._check_exit_signal(
                    row, entry_price, max_price, strategy_name
                )

                if should_exit:
                    # Calculate position size based on volatility targeting
                    # Target: 15% portfolio volatility
                    # Position Size % = Target Vol / Stock Vol
                    target_vol = 0.15  # 15% target portfolio volatility
                    if entry_atr_pct > 0:
                        # ATR% is daily volatility, annualize it: daily * sqrt(252)
                        annualized_vol = (entry_atr_pct / 100) * (252 ** 0.5)
                        position_size_pct = (target_vol / annualized_vol) * 100 if annualized_vol > 0 else 100
                        # Cap at 100% (full portfolio)
                        position_size_pct = min(100, position_size_pct)
                    else:
                        position_size_pct = 100  # Default if no ATR data

                    trade = {
                        'entry_date': entry_date,
                        'exit_date': row['date'],
                        'entry_price': entry_price,
                        'exit_price': row['close'],
                        'return_pct': ((row['close'] - entry_price) / entry_price) * 100,
                        'holding_days': (row['date'] - entry_date).days,
                        'exit_reason': exit_reason,
                        'max_price': max_price,
                        'atr_pct_at_entry': entry_atr_pct,
                        'position_size_pct': position_size_pct,  # NEW: Volatility-based sizing
                    }
                    trades.append(trade)

                    position_open = False
                    entry_price = 0
                    entry_date = None
                    max_price = 0
                    entry_atr_pct = 0

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
        step_days: int = 30,
        spy_data: pd.DataFrame = None
    ) -> List[Dict]:
        """
        Run walk-forward backtesting for academic momentum strategies.

        Args:
            train_days: Days for training window
            test_days: Days for testing window (out-of-sample)
            step_days: Days to step forward
            spy_data: SPY data for market regime filter (REQUIRED)

        Returns:
            List of dictionaries with walk-forward results for each strategy
        """
        logger.info("Starting walk-forward validation for academic momentum strategies")

        if spy_data is None:
            logger.warning("No SPY data provided - strategies will not use regime filter")

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
                # Use anchored=True so indicators are calculated with all historical data
                train_result = self.backtest_strategy(
                    strategy_key,
                    start_date=train_start,
                    end_date=train_end,
                    use_anchored=True,
                    spy_data=spy_data  # Pass SPY data for regime filter
                )
                in_sample_trades.extend(train_result['trades'])

                # Backtest on test window (out-of-sample)
                # CRITICAL: Use anchored=True to calculate indicators with ALL data up to test_end
                # This ensures momentum_12m (252 days) has enough historical data
                test_result = self.backtest_strategy(
                    strategy_key,
                    start_date=test_start,
                    end_date=test_end,
                    use_anchored=True,
                    spy_data=spy_data  # Pass SPY data for regime filter
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

            # Calculate Risk/Reward ratio for OOS
            oos_rr = abs(out_metrics['avg_win'] / out_metrics['avg_loss']) if out_metrics['avg_loss'] != 0 else 0

            comparison.append({
                'Strategy': result['strategy_name'],
                'Priority': result['priority'],

                # In-Sample (Training)
                'IS Trades': in_metrics['num_trades'],
                'IS Win Rate': f"{in_metrics['win_rate']:.1f}%",
                'IS Sharpe': f"{in_metrics['sharpe_ratio']:.2f}",
                'IS Return': f"{in_metrics['total_return']:.1f}%",

                # Out-of-Sample (Testing) - METRICS FOR TIMING
                'OOS Trades': out_metrics['num_trades'],
                'OOS Win Rate': f"{out_metrics['win_rate']:.1f}%",
                'OOS Avg Win': f"{out_metrics['avg_win']:.2f}%",
                'OOS Avg Loss': f"{out_metrics['avg_loss']:.2f}%",
                'OOS Profit Factor': f"{out_metrics['profit_factor']:.2f}",
                'OOS R/R': f"{oos_rr:.2f}",
                'OOS Sharpe': f"{out_metrics['sharpe_ratio']:.2f}",
                'OOS Return': f"{out_metrics['total_return']:.1f}%",

                # Degradation
                'Win Rate Deg': f"{deg['win_rate']:.2f}x",
                'Sharpe Deg': f"{deg['sharpe_ratio']:.2f}x",
                'Overall Deg': f"{deg['overall']:.2f}x",
            })

        return pd.DataFrame(comparison)

