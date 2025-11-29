"""
Portfolio tracking module with risk management alerts.

Tracks:
- User positions with entry prices
- Current overextension risk
- Price alerts (MA50, MA200, stop loss levels)
- Scale-in opportunities
- Profit taking levels
"""

import json
import os
from typing import Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class PortfolioTracker:
    """
    Track portfolio positions and generate risk management alerts.
    """

    def __init__(self, portfolio_file: str = 'portfolio.json'):
        """
        Args:
            portfolio_file: Path to portfolio JSON file
        """
        self.portfolio_file = portfolio_file
        self.positions = self._load_portfolio()

    def _load_portfolio(self) -> Dict:
        """Load portfolio from file."""
        if os.path.exists(self.portfolio_file):
            try:
                with open(self.portfolio_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading portfolio: {e}")
                return {}
        return {}

    def _save_portfolio(self):
        """Save portfolio to file."""
        try:
            with open(self.portfolio_file, 'w') as f:
                json.dump(self.positions, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving portfolio: {e}")

    def add_position(
        self,
        symbol: str,
        entry_price: float,
        quantity: int,
        entry_date: str = None,
        notes: str = ""
    ):
        """
        Add a new position to portfolio.

        Args:
            symbol: Stock symbol
            entry_price: Entry price
            quantity: Number of shares
            entry_date: Entry date (YYYY-MM-DD)
            notes: Optional notes
        """
        if entry_date is None:
            entry_date = datetime.now().strftime('%Y-%m-%d')

        self.positions[symbol] = {
            'entry_price': entry_price,
            'quantity': quantity,
            'entry_date': entry_date,
            'notes': notes,
            'tranches': [
                {
                    'date': entry_date,
                    'price': entry_price,
                    'quantity': quantity,
                    'pct': 100
                }
            ],
            'added_at': datetime.now().isoformat()
        }
        self._save_portfolio()

    def add_tranche(
        self,
        symbol: str,
        price: float,
        quantity: int,
        date: str = None
    ):
        """
        Add additional tranche to existing position (scale-in).

        Args:
            symbol: Stock symbol
            price: Purchase price
            quantity: Number of shares
            date: Purchase date
        """
        if symbol not in self.positions:
            raise ValueError(f"{symbol} not in portfolio. Add position first.")

        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')

        position = self.positions[symbol]

        # Calculate new average price
        total_cost = position['entry_price'] * position['quantity'] + price * quantity
        total_quantity = position['quantity'] + quantity
        new_avg_price = total_cost / total_quantity

        # Update position
        position['entry_price'] = new_avg_price
        position['quantity'] = total_quantity

        # Add tranche record
        total_qty_before = sum(t['quantity'] for t in position['tranches'])
        pct = (quantity / (total_qty_before + quantity)) * 100

        position['tranches'].append({
            'date': date,
            'price': price,
            'quantity': quantity,
            'pct': round(pct, 1)
        })

        self._save_portfolio()

    def remove_position(self, symbol: str):
        """Remove position from portfolio."""
        if symbol in self.positions:
            del self.positions[symbol]
            self._save_portfolio()

    def get_position(self, symbol: str) -> Optional[Dict]:
        """Get position details."""
        return self.positions.get(symbol)

    def get_all_positions(self) -> Dict:
        """Get all positions."""
        return self.positions

    def generate_alerts(
        self,
        symbol: str,
        current_price: float,
        ma_50: float,
        ma_200: float,
        overextension_risk: int,
        risk_management: Dict
    ) -> List[Dict]:
        """
        Generate alerts for a position based on current market data.

        Args:
            symbol: Stock symbol
            current_price: Current market price
            ma_50: 50-day MA
            ma_200: 200-day MA
            overextension_risk: Current overextension risk (0-7)
            risk_management: Risk management recommendations

        Returns:
            List of alert dicts with {type, priority, message}
        """
        alerts = []

        position = self.get_position(symbol)
        if not position:
            return alerts

        entry_price = position['entry_price']
        pnl_pct = ((current_price - entry_price) / entry_price * 100)

        # Alert 1: Price near MA50 (scale-in opportunity)
        entry_strategy = risk_management.get('entry_strategy', {})
        if 'tranche_2' in entry_strategy and abs(current_price - ma_50) / ma_50 < 0.02:
            # Within 2% of MA50
            alerts.append({
                'type': 'SCALE_IN',
                'priority': 'HIGH',
                'message': f'🎯 {symbol} near MA50 (${ma_50:.2f})! Consider adding tranche 2 (scale-in opportunity)'
            })

        # Alert 2: Price near MA200 (major support/scale-in)
        if 'tranche_3' in entry_strategy and abs(current_price - ma_200) / ma_200 < 0.03:
            # Within 3% of MA200
            alerts.append({
                'type': 'SCALE_IN',
                'priority': 'HIGH',
                'message': f'🎯 {symbol} near MA200 (${ma_200:.2f})! Major scale-in opportunity (tranche 3)'
            })

        # Alert 3: Stop loss triggered
        stop_loss = risk_management.get('stop_loss', {})
        recommended_stop = stop_loss.get('recommended', 'moderate')
        stops = stop_loss.get('stops', {})

        if recommended_stop in stops:
            stop_data = stops[recommended_stop]
            stop_level_str = stop_data.get('level', '')
            if '$' in stop_level_str:
                try:
                    stop_level = float(stop_level_str.replace('$', '').split()[0].replace(',', ''))
                    if current_price <= stop_level:
                        alerts.append({
                            'type': 'STOP_LOSS',
                            'priority': 'CRITICAL',
                            'message': f'🔴 {symbol} STOP LOSS TRIGGERED! Price ${current_price:.2f} ≤ Stop ${stop_level:.2f}. Consider exiting position.'
                        })
                except:
                    pass

        # Alert 4: Profit target hit
        profit_taking = risk_management.get('profit_taking', {})
        if pnl_pct >= 25 and profit_taking.get('strategy') == 'TRAILING STOP (Let winners run)':
            alerts.append({
                'type': 'PROFIT_TARGET',
                'priority': 'MEDIUM',
                'message': f'💰 {symbol} up {pnl_pct:+.1f}%! Consider taking partial profits or tightening stop.'
            })
        elif pnl_pct >= 15 and 'LADDER SELLS' in profit_taking.get('strategy', ''):
            alerts.append({
                'type': 'PROFIT_TARGET',
                'priority': 'HIGH',
                'message': f'💰 {symbol} up {pnl_pct:+.1f}%! Ladder sell strategy: Consider selling 25% to lock gains.'
            })

        # Alert 5: Overextension risk changed significantly
        if overextension_risk >= 5:
            alerts.append({
                'type': 'RISK_INCREASE',
                'priority': 'HIGH',
                'message': f'⚠️ {symbol} overextension risk now EXTREME ({overextension_risk}/7)! High probability of 20-40% correction.'
            })
        elif overextension_risk >= 3:
            alerts.append({
                'type': 'RISK_INCREASE',
                'priority': 'MEDIUM',
                'message': f'⚠️ {symbol} overextension risk now HIGH ({overextension_risk}/7). Possible 10-20% pullback.'
            })

        # Alert 6: Overextension improved (good for adding)
        if overextension_risk <= 1 and pnl_pct < -10:
            alerts.append({
                'type': 'RISK_DECREASE',
                'priority': 'MEDIUM',
                'message': f'✅ {symbol} overextension risk now LOW ({overextension_risk}/7). Pullback created better entry opportunity.'
            })

        return alerts

    def get_portfolio_summary(
        self,
        current_prices: Dict[str, float]
    ) -> Dict:
        """
        Get portfolio summary with current values.

        Args:
            current_prices: Dict of {symbol: current_price}

        Returns:
            {
                'total_value': float,
                'total_cost': float,
                'total_pnl': float,
                'total_pnl_pct': float,
                'positions_count': int,
                'positions': List[Dict]
            }
        """
        total_value = 0
        total_cost = 0
        positions_details = []

        for symbol, position in self.positions.items():
            current_price = current_prices.get(symbol, position['entry_price'])
            cost = position['entry_price'] * position['quantity']
            value = current_price * position['quantity']
            pnl = value - cost
            pnl_pct = (pnl / cost * 100) if cost > 0 else 0

            total_value += value
            total_cost += cost

            positions_details.append({
                'symbol': symbol,
                'quantity': position['quantity'],
                'entry_price': position['entry_price'],
                'current_price': current_price,
                'cost': cost,
                'value': value,
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                'entry_date': position['entry_date'],
                'tranches': len(position.get('tranches', []))
            })

        total_pnl = total_value - total_cost
        total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0

        # Sort by PnL %
        positions_details.sort(key=lambda x: x['pnl_pct'], reverse=True)

        return {
            'total_value': round(total_value, 2),
            'total_cost': round(total_cost, 2),
            'total_pnl': round(total_pnl, 2),
            'total_pnl_pct': round(total_pnl_pct, 2),
            'positions_count': len(self.positions),
            'positions': positions_details
        }
