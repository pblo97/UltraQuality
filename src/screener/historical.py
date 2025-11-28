"""
Historical tracking system for financial metrics.

Stores snapshots of key metrics over time to enable:
- Trend analysis (is DSO accelerating?)
- Deterioration detection (when did margins start compressing?)
- Historical comparison (current vs 1Y ago)
- Backtesting of screening criteria

Database: SQLite (simple, no external dependencies)
Schema: metrics_history table with (symbol, date, metric, value, metadata)
"""
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
import logging
from typing import Dict, List, Optional
import pandas as pd

logger = logging.getLogger(__name__)


class HistoricalTracker:
    """
    Track and query historical financial metrics.

    Usage:
        tracker = HistoricalTracker()

        # Save current snapshot
        tracker.save_snapshot('AAPL', guardrails, qualitative)

        # Query historical data
        dso_history = tracker.get_metric_history('AAPL', 'dso', periods=8)
        # Returns: [(date1, value1), (date2, value2), ...]
    """

    def __init__(self, db_path='metrics_history.db'):
        self.db_path = Path(db_path)
        self._init_database()

    def _init_database(self):
        """Initialize SQLite database with schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create metrics_history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS metrics_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                snapshot_date TEXT NOT NULL,
                metric_category TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                metric_value REAL,
                metadata TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, snapshot_date, metric_category, metric_name)
            )
        ''')

        # Create indexes for faster queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_symbol_date
            ON metrics_history(symbol, snapshot_date)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_metric_name
            ON metrics_history(metric_name)
        ''')

        conn.commit()
        conn.close()

        logger.info(f"Historical database initialized at {self.db_path}")

    def save_snapshot(
        self,
        symbol: str,
        guardrails: Dict,
        qualitative: Dict = None,
        snapshot_date: str = None
    ):
        """
        Save a snapshot of metrics for a symbol.

        Args:
            symbol: Stock ticker
            guardrails: Output from GuardrailCalculator
            qualitative: Output from QualitativeAnalyzer (optional)
            snapshot_date: Date string (YYYY-MM-DD), defaults to today
        """
        if snapshot_date is None:
            snapshot_date = datetime.now().strftime('%Y-%m-%d')

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        metrics_to_save = []

        # ===================================
        # GUARDRAILS METRICS
        # ===================================

        # Traditional guardrails
        if guardrails.get('altmanZ') is not None:
            metrics_to_save.append(('guardrails', 'altman_z', guardrails['altmanZ'], None))

        if guardrails.get('beneishM') is not None:
            metrics_to_save.append(('guardrails', 'beneish_m', guardrails['beneishM'], None))

        if guardrails.get('accruals_noa_%') is not None:
            metrics_to_save.append(('guardrails', 'accruals_noa_pct', guardrails['accruals_noa_%'], None))

        # Working Capital
        wc = guardrails.get('working_capital', {})
        if wc.get('dso_current') is not None:
            metrics_to_save.append(('working_capital', 'dso', wc['dso_current'], None))
        if wc.get('dio_current') is not None:
            metrics_to_save.append(('working_capital', 'dio', wc['dio_current'], None))
        if wc.get('ccc_current') is not None:
            metrics_to_save.append(('working_capital', 'ccc', wc['ccc_current'], None))
        if wc.get('status'):
            # Store status as numeric (VERDE=2, AMBAR=1, ROJO=0)
            status_val = {'VERDE': 2, 'AMBAR': 1, 'ROJO': 0}.get(wc['status'], 1)
            metrics_to_save.append(('working_capital', 'status', status_val, None))

        # Margins
        mt = guardrails.get('margin_trajectory', {})
        if mt.get('gross_margin_current') is not None:
            metrics_to_save.append(('margins', 'gross_margin', mt['gross_margin_current'], None))
        if mt.get('operating_margin_current') is not None:
            metrics_to_save.append(('margins', 'operating_margin', mt['operating_margin_current'], None))

        # Cash Conversion
        cc = guardrails.get('cash_conversion', {})
        if cc.get('fcf_to_ni_current') is not None:
            metrics_to_save.append(('cash_conversion', 'fcf_to_ni', cc['fcf_to_ni_current'], None))
        if cc.get('capex_intensity_current') is not None:
            metrics_to_save.append(('cash_conversion', 'capex_intensity', cc['capex_intensity_current'], None))

        # Debt
        dm = guardrails.get('debt_maturity_wall', {})
        if dm.get('liquidity_ratio') is not None:
            metrics_to_save.append(('debt', 'liquidity_ratio', dm['liquidity_ratio'], None))
        if dm.get('interest_coverage') is not None:
            metrics_to_save.append(('debt', 'interest_coverage', dm['interest_coverage'], None))

        # Benford's Law
        bf = guardrails.get('benfords_law', {})
        if bf.get('deviation_score') is not None:
            metrics_to_save.append(('fraud_detection', 'benford_deviation', bf['deviation_score'], None))

        # Overall guardrail status
        if guardrails.get('guardrail_status'):
            status_val = {'VERDE': 2, 'AMBAR': 1, 'ROJO': 0}.get(guardrails['guardrail_status'], 1)
            metrics_to_save.append(('guardrails', 'overall_status', status_val, None))

        # ===================================
        # QUALITATIVE METRICS (if provided)
        # ===================================

        if qualitative:
            # Insider ownership
            insider = qualitative.get('skin_in_the_game', {})
            if insider.get('insider_ownership_pct') is not None:
                metrics_to_save.append(('insider', 'ownership_pct', insider['insider_ownership_pct'], None))

            if insider.get('insider_transactions'):
                txns = insider['insider_transactions']
                buys = txns.get('buys', 0)
                sells = txns.get('sells', 0)
                metrics_to_save.append(('insider', 'buys_6m', buys, None))
                metrics_to_save.append(('insider', 'sells_6m', sells, None))

            # Backlog (if applicable)
            backlog = qualitative.get('backlog_data', {})
            if backlog.get('backlog_mentioned') and backlog.get('order_trend'):
                # Store trend as numeric
                trend_val = {'Positive': 2, 'Stable': 1, 'Declining': 0, 'Unknown': None}.get(backlog['order_trend'])
                if trend_val is not None:
                    metrics_to_save.append(('backlog', 'order_trend', trend_val, None))

        # Insert all metrics
        for category, name, value, metadata in metrics_to_save:
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO metrics_history
                    (symbol, snapshot_date, metric_category, metric_name, metric_value, metadata)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (symbol, snapshot_date, category, name, value, metadata))
            except Exception as e:
                logger.warning(f"Error saving metric {name}: {e}")

        conn.commit()
        conn.close()

        logger.info(f"Saved snapshot for {symbol} on {snapshot_date} ({len(metrics_to_save)} metrics)")

    def get_metric_history(
        self,
        symbol: str,
        metric_name: str,
        periods: int = 8,
        end_date: str = None
    ) -> List[tuple]:
        """
        Get historical values for a specific metric.

        Args:
            symbol: Stock ticker
            metric_name: Metric to query (e.g., 'dso', 'gross_margin')
            periods: Number of historical periods to return
            end_date: End date (YYYY-MM-DD), defaults to today

        Returns:
            List of (date, value) tuples, newest first
        """
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT snapshot_date, metric_value
            FROM metrics_history
            WHERE symbol = ? AND metric_name = ? AND snapshot_date <= ?
            ORDER BY snapshot_date DESC
            LIMIT ?
        ''', (symbol, metric_name, end_date, periods))

        results = cursor.fetchall()
        conn.close()

        return results

    def get_snapshot(
        self,
        symbol: str,
        snapshot_date: str = None
    ) -> Dict:
        """
        Get all metrics for a symbol at a specific date.

        Args:
            symbol: Stock ticker
            snapshot_date: Date (YYYY-MM-DD), defaults to most recent

        Returns:
            Dict of metrics organized by category
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if snapshot_date is None:
            # Get most recent snapshot
            cursor.execute('''
                SELECT DISTINCT snapshot_date
                FROM metrics_history
                WHERE symbol = ?
                ORDER BY snapshot_date DESC
                LIMIT 1
            ''', (symbol,))
            result = cursor.fetchone()
            if not result:
                conn.close()
                return {}
            snapshot_date = result[0]

        cursor.execute('''
            SELECT metric_category, metric_name, metric_value
            FROM metrics_history
            WHERE symbol = ? AND snapshot_date = ?
        ''', (symbol, snapshot_date))

        results = cursor.fetchall()
        conn.close()

        # Organize by category
        snapshot = {}
        for category, name, value in results:
            if category not in snapshot:
                snapshot[category] = {}
            snapshot[category][name] = value

        snapshot['_date'] = snapshot_date
        return snapshot

    def analyze_trend(
        self,
        symbol: str,
        metric_name: str,
        periods: int = 8
    ) -> Dict:
        """
        Analyze trend for a metric (improving/deteriorating/stable).

        Args:
            symbol: Stock ticker
            metric_name: Metric to analyze
            periods: Number of periods to analyze

        Returns:
            Dict with trend analysis:
            {
                'current': float,
                'oldest': float,
                'change': float,
                'change_pct': float,
                'trend': 'Improving'|'Stable'|'Deteriorating',
                'acceleration': bool  # Is trend accelerating?
            }
        """
        history = self.get_metric_history(symbol, metric_name, periods)

        if len(history) < 2:
            return {'trend': 'Unknown', 'reason': 'Insufficient data'}

        values = [v for d, v in history if v is not None]
        if len(values) < 2:
            return {'trend': 'Unknown', 'reason': 'Insufficient data'}

        current = values[0]
        oldest = values[-1]

        change = current - oldest
        change_pct = (change / oldest * 100) if oldest != 0 else 0

        # Determine trend direction
        # For most metrics, lower is better (DSO, DIO, CCC, capex intensity)
        # But some are higher is better (margins, liquidity, coverage, FCF/NI)

        # Default: lower is better
        if change < 0:
            trend = 'Improving'
        elif change > 0:
            trend = 'Deteriorating'
        else:
            trend = 'Stable'

        # Check for acceleration (is change accelerating in recent periods?)
        acceleration = False
        if len(values) >= 4:
            recent_change = values[0] - values[1]
            older_change = values[-2] - values[-1]

            # If both changes have same sign and recent is larger
            if (recent_change * older_change > 0) and (abs(recent_change) > abs(older_change) * 1.5):
                acceleration = True

        return {
            'current': current,
            'oldest': oldest,
            'change': change,
            'change_pct': change_pct,
            'trend': trend,
            'acceleration': acceleration,
            'data_points': len(values)
        }

    def compare_to_historical(
        self,
        symbol: str,
        current_metrics: Dict,
        lookback_quarters: int = 4
    ) -> Dict:
        """
        Compare current metrics to historical average.

        Args:
            symbol: Stock ticker
            current_metrics: Current values (from guardrails/qualitative)
            lookback_quarters: How many quarters to average

        Returns:
            Dict of comparisons
        """
        comparisons = {}

        metric_mappings = {
            'dso': 'working_capital.dso_current',
            'gross_margin': 'margin_trajectory.gross_margin_current',
            'fcf_to_ni': 'cash_conversion.fcf_to_ni_current'
        }

        for metric_name, metric_path in metric_mappings.items():
            history = self.get_metric_history(symbol, metric_name, lookback_quarters + 1)

            if len(history) < 2:
                continue

            # Current value
            current = history[0][1]

            # Historical average (excluding current)
            historical_values = [v for d, v in history[1:] if v is not None]
            if not historical_values:
                continue

            historical_avg = sum(historical_values) / len(historical_values)

            deviation = current - historical_avg
            deviation_pct = (deviation / historical_avg * 100) if historical_avg != 0 else 0

            comparisons[metric_name] = {
                'current': current,
                'historical_avg': historical_avg,
                'deviation': deviation,
                'deviation_pct': deviation_pct,
                'status': 'Worse' if deviation > 0 else 'Better' if deviation < 0 else 'Same'
            }

        return comparisons

    def get_database_stats(self) -> Dict:
        """Get statistics about stored data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Total snapshots
        cursor.execute('SELECT COUNT(DISTINCT symbol || snapshot_date) FROM metrics_history')
        total_snapshots = cursor.fetchone()[0]

        # Total symbols
        cursor.execute('SELECT COUNT(DISTINCT symbol) FROM metrics_history')
        total_symbols = cursor.fetchone()[0]

        # Date range
        cursor.execute('SELECT MIN(snapshot_date), MAX(snapshot_date) FROM metrics_history')
        date_min, date_max = cursor.fetchone()

        # Total metrics
        cursor.execute('SELECT COUNT(*) FROM metrics_history')
        total_metrics = cursor.fetchone()[0]

        conn.close()

        return {
            'total_snapshots': total_snapshots,
            'total_symbols': total_symbols,
            'date_range': f"{date_min} to {date_max}",
            'total_metrics': total_metrics
        }

    def export_to_csv(self, symbol: str, output_file: str):
        """Export historical data for a symbol to CSV."""
        conn = sqlite3.connect(self.db_path)

        query = '''
            SELECT snapshot_date, metric_category, metric_name, metric_value
            FROM metrics_history
            WHERE symbol = ?
            ORDER BY snapshot_date DESC, metric_category, metric_name
        '''

        df = pd.read_sql_query(query, conn, params=(symbol,))
        df.to_csv(output_file, index=False)

        conn.close()
        logger.info(f"Exported {len(df)} records to {output_file}")

        return len(df)
