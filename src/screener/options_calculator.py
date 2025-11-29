"""
Options P&L Calculator with Greeks.

Calculates:
- Break-even prices
- Max profit/loss
- Expected value
- Probability of profit
- Greeks (Delta, Theta, Vega, Gamma)

Using Black-Scholes-Merton model for pricing.
"""

import math
from typing import Dict, Tuple
from scipy.stats import norm
import logging

logger = logging.getLogger(__name__)


class OptionsCalculator:
    """
    Calculate options metrics and Greeks using Black-Scholes model.
    """

    def __init__(self, risk_free_rate: float = 0.05):
        """
        Args:
            risk_free_rate: Risk-free rate (annual, default 5%)
        """
        self.risk_free_rate = risk_free_rate

    def black_scholes(
        self,
        stock_price: float,
        strike: float,
        time_to_expiry: float,  # in years
        volatility: float,  # annual volatility (e.g., 0.30 for 30%)
        option_type: str = 'call'
    ) -> float:
        """
        Calculate option price using Black-Scholes model.

        Args:
            stock_price: Current stock price
            strike: Strike price
            time_to_expiry: Time to expiration in years
            volatility: Annual volatility (0.30 = 30%)
            option_type: 'call' or 'put'

        Returns:
            Option price
        """
        if time_to_expiry <= 0:
            # At expiration
            if option_type == 'call':
                return max(stock_price - strike, 0)
            else:
                return max(strike - stock_price, 0)

        d1 = (math.log(stock_price / strike) + (self.risk_free_rate + 0.5 * volatility ** 2) * time_to_expiry) / (volatility * math.sqrt(time_to_expiry))
        d2 = d1 - volatility * math.sqrt(time_to_expiry)

        if option_type == 'call':
            price = stock_price * norm.cdf(d1) - strike * math.exp(-self.risk_free_rate * time_to_expiry) * norm.cdf(d2)
        else:  # put
            price = strike * math.exp(-self.risk_free_rate * time_to_expiry) * norm.cdf(-d2) - stock_price * norm.cdf(-d1)

        return price

    def calculate_greeks(
        self,
        stock_price: float,
        strike: float,
        time_to_expiry: float,
        volatility: float,
        option_type: str = 'call'
    ) -> Dict:
        """
        Calculate option Greeks.

        Returns:
            {
                'delta': float,
                'gamma': float,
                'theta': float (per day),
                'vega': float (per 1% change in vol),
            }
        """
        if time_to_expiry <= 0:
            return {'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0}

        d1 = (math.log(stock_price / strike) + (self.risk_free_rate + 0.5 * volatility ** 2) * time_to_expiry) / (volatility * math.sqrt(time_to_expiry))
        d2 = d1 - volatility * math.sqrt(time_to_expiry)

        # Delta
        if option_type == 'call':
            delta = norm.cdf(d1)
        else:
            delta = norm.cdf(d1) - 1

        # Gamma (same for call and put)
        gamma = norm.pdf(d1) / (stock_price * volatility * math.sqrt(time_to_expiry))

        # Theta (per day)
        if option_type == 'call':
            theta = (-(stock_price * norm.pdf(d1) * volatility) / (2 * math.sqrt(time_to_expiry))
                     - self.risk_free_rate * strike * math.exp(-self.risk_free_rate * time_to_expiry) * norm.cdf(d2))
        else:
            theta = (-(stock_price * norm.pdf(d1) * volatility) / (2 * math.sqrt(time_to_expiry))
                     + self.risk_free_rate * strike * math.exp(-self.risk_free_rate * time_to_expiry) * norm.cdf(-d2))

        theta_per_day = theta / 365

        # Vega (per 1% change in volatility)
        vega = stock_price * norm.pdf(d1) * math.sqrt(time_to_expiry) / 100

        return {
            'delta': round(delta, 3),
            'gamma': round(gamma, 4),
            'theta': round(theta_per_day, 3),
            'vega': round(vega, 3)
        }

    def covered_call_analysis(
        self,
        stock_price: float,
        strike: float,
        days_to_expiry: int,
        volatility: float
    ) -> Dict:
        """
        Analyze covered call strategy.

        Args:
            stock_price: Current stock price
            strike: Call strike price
            days_to_expiry: Days to expiration
            volatility: Annual volatility (e.g., 0.30 for 30%)

        Returns:
            {
                'premium': float,
                'max_profit': float,
                'max_profit_pct': float,
                'break_even': float,
                'annualized_return': float,
                'probability_profit': float
            }
        """
        time_to_expiry = days_to_expiry / 365

        # Calculate call premium
        premium = self.black_scholes(stock_price, strike, time_to_expiry, volatility, 'call')

        # Max profit = premium + (strike - stock_price) if assigned
        max_profit = premium + max(strike - stock_price, 0)
        max_profit_pct = (max_profit / stock_price) * 100

        # Break-even = stock_price - premium (downside protection)
        break_even = stock_price - premium

        # Annualized return (if held to expiration and assigned)
        annualized_return = (max_profit_pct / days_to_expiry) * 365

        # Probability of profit = probability stock stays above break-even
        # Using normal distribution approximation
        expected_return = self.risk_free_rate
        std_dev = volatility * math.sqrt(time_to_expiry)
        z_score = (math.log(break_even / stock_price) - expected_return * time_to_expiry) / std_dev
        prob_profit = 1 - norm.cdf(z_score)

        return {
            'premium': round(premium, 2),
            'premium_pct': round((premium / stock_price) * 100, 2),
            'max_profit': round(max_profit, 2),
            'max_profit_pct': round(max_profit_pct, 2),
            'break_even': round(break_even, 2),
            'annualized_return': round(annualized_return, 1),
            'probability_profit': round(prob_profit * 100, 1),
            'greeks': self.calculate_greeks(stock_price, strike, time_to_expiry, volatility, 'call')
        }

    def protective_put_analysis(
        self,
        stock_price: float,
        strike: float,
        days_to_expiry: int,
        volatility: float
    ) -> Dict:
        """
        Analyze protective put strategy.

        Args:
            stock_price: Current stock price
            strike: Put strike price
            days_to_expiry: Days to expiration
            volatility: Annual volatility

        Returns:
            Analysis dict
        """
        time_to_expiry = days_to_expiry / 365

        # Calculate put premium (cost)
        premium = self.black_scholes(stock_price, strike, time_to_expiry, volatility, 'put')

        # Max loss = (stock_price - strike) + premium
        max_loss = (stock_price - strike) + premium
        max_loss_pct = (max_loss / stock_price) * 100

        # Break-even on upside = stock_price + premium
        break_even_up = stock_price + premium

        # Cost as % of stock price
        cost_pct = (premium / stock_price) * 100

        # Annualized cost
        annualized_cost = (cost_pct / days_to_expiry) * 365

        return {
            'premium_cost': round(premium, 2),
            'cost_pct': round(cost_pct, 2),
            'max_loss': round(max_loss, 2),
            'max_loss_pct': round(max_loss_pct, 2),
            'break_even_upside': round(break_even_up, 2),
            'annualized_cost': round(annualized_cost, 1),
            'protection_level': round((1 - strike/stock_price) * 100, 1),
            'greeks': self.calculate_greeks(stock_price, strike, time_to_expiry, volatility, 'put')
        }

    def collar_analysis(
        self,
        stock_price: float,
        put_strike: float,
        call_strike: float,
        days_to_expiry: int,
        volatility: float
    ) -> Dict:
        """
        Analyze collar strategy (long put + short call).

        Args:
            stock_price: Current stock price
            put_strike: Put strike (protection)
            call_strike: Call strike (cap)
            days_to_expiry: Days to expiration
            volatility: Annual volatility

        Returns:
            Analysis dict
        """
        time_to_expiry = days_to_expiry / 365

        # Long put cost
        put_cost = self.black_scholes(stock_price, put_strike, time_to_expiry, volatility, 'put')

        # Short call credit
        call_credit = self.black_scholes(stock_price, call_strike, time_to_expiry, volatility, 'call')

        # Net cost/credit
        net_cost = put_cost - call_credit

        # Max profit = (call_strike - stock_price) - net_cost
        max_profit = (call_strike - stock_price) - net_cost
        max_profit_pct = (max_profit / stock_price) * 100

        # Max loss = (stock_price - put_strike) + net_cost
        max_loss = (stock_price - put_strike) + net_cost
        max_loss_pct = (max_loss / stock_price) * 100

        return {
            'put_cost': round(put_cost, 2),
            'call_credit': round(call_credit, 2),
            'net_cost': round(net_cost, 2),
            'is_credit': net_cost < 0,
            'max_profit': round(max_profit, 2),
            'max_profit_pct': round(max_profit_pct, 2),
            'max_loss': round(max_loss, 2),
            'max_loss_pct': round(max_loss_pct, 2),
            'range': f"${put_strike:.2f} to ${call_strike:.2f}",
            'range_pct': round(((call_strike - put_strike) / stock_price) * 100, 1)
        }

    def cash_secured_put_analysis(
        self,
        stock_price: float,
        strike: float,
        days_to_expiry: int,
        volatility: float
    ) -> Dict:
        """
        Analyze cash-secured put strategy (sell put).

        Args:
            stock_price: Current stock price
            strike: Put strike price
            days_to_expiry: Days to expiration
            volatility: Annual volatility

        Returns:
            Analysis dict
        """
        time_to_expiry = days_to_expiry / 365

        # Calculate put premium (credit received)
        premium = self.black_scholes(stock_price, strike, time_to_expiry, volatility, 'put')

        # Max profit = premium
        max_profit = premium
        max_profit_pct = (premium / strike) * 100  # ROI on cash secured

        # Max loss = strike - premium (if stock goes to 0)
        max_loss = strike - premium

        # Break-even = strike - premium
        break_even = strike - premium

        # Annualized return
        annualized_return = (max_profit_pct / days_to_expiry) * 365

        # Probability of profit (stock stays above strike)
        expected_return = self.risk_free_rate
        std_dev = volatility * math.sqrt(time_to_expiry)
        z_score = (math.log(strike / stock_price) - expected_return * time_to_expiry) / std_dev
        prob_not_assigned = norm.cdf(z_score)  # Probability stock stays above strike
        prob_profit = prob_not_assigned  # If not assigned, keep full premium

        return {
            'premium_credit': round(premium, 2),
            'premium_pct': round(max_profit_pct, 2),
            'max_profit': round(max_profit, 2),
            'max_loss': round(max_loss, 2),
            'break_even': round(break_even, 2),
            'effective_entry': round(break_even, 2),
            'discount_pct': round(((stock_price - break_even) / stock_price) * 100, 1),
            'annualized_return': round(annualized_return, 1),
            'probability_profit': round(prob_profit * 100, 1),
            'greeks': self.calculate_greeks(stock_price, strike, time_to_expiry, volatility, 'put')
        }

    def vertical_spread_analysis(
        self,
        stock_price: float,
        long_strike: float,
        short_strike: float,
        days_to_expiry: int,
        volatility: float,
        spread_type: str = 'bull_put'
    ) -> Dict:
        """
        Analyze vertical spread (bull put spread, bear call spread, etc.).

        Args:
            stock_price: Current stock price
            long_strike: Strike of option bought
            short_strike: Strike of option sold
            days_to_expiry: Days to expiration
            volatility: Annual volatility
            spread_type: 'bull_put', 'bear_call', 'bull_call', 'bear_put'

        Returns:
            Analysis dict
        """
        time_to_expiry = days_to_expiry / 365

        if spread_type in ['bull_put', 'bear_put']:
            option_type = 'put'
        else:
            option_type = 'call'

        # Long option (bought)
        long_premium = self.black_scholes(stock_price, long_strike, time_to_expiry, volatility, option_type)

        # Short option (sold)
        short_premium = self.black_scholes(stock_price, short_strike, time_to_expiry, volatility, option_type)

        # Net credit/debit
        if spread_type in ['bull_put', 'bear_call']:
            # Credit spreads
            net_credit = short_premium - long_premium
            max_profit = net_credit
            max_loss = abs(short_strike - long_strike) - net_credit
        else:
            # Debit spreads
            net_debit = long_premium - short_premium
            max_loss = net_debit
            max_profit = abs(short_strike - long_strike) - net_debit

        # Calculate probabilities
        if spread_type == 'bull_put':
            # Profit if stock stays above short strike
            z_score = (math.log(short_strike / stock_price) - self.risk_free_rate * time_to_expiry) / (volatility * math.sqrt(time_to_expiry))
            prob_profit = norm.cdf(z_score)
        else:
            # Simplified - would need more complex calc for each type
            prob_profit = 0.60  # Placeholder

        return {
            'long_strike': long_strike,
            'short_strike': short_strike,
            'long_premium': round(long_premium, 2),
            'short_premium': round(short_premium, 2),
            'net_credit' if spread_type in ['bull_put', 'bear_call'] else 'net_debit':
                round(abs(short_premium - long_premium), 2),
            'max_profit': round(max_profit, 2),
            'max_loss': round(max_loss, 2),
            'risk_reward_ratio': round(max_profit / max_loss, 2) if max_loss > 0 else 0,
            'probability_profit': round(prob_profit * 100, 1)
        }
