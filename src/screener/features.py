"""
Feature calculation for Value and Quality metrics.
Handles Non-Financials, Financials, and REITs separately.
"""
import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class FeatureCalculator:
    """
    Calculate Value and Quality metrics for different company types:
    - Non-Financials: ROIC, EV/EBIT, gross profits/assets, etc.
    - Financials: ROA, ROE, NIM, efficiency ratio, etc.
    - REITs: FFO, AFFO, occupancy, etc.
    """

    def __init__(self, fmp_client):
        self.fmp = fmp_client

    def calculate_features(self, symbol: str, company_type: str) -> Dict:
        """
        Main entry point: calculate all features for a symbol.

        Args:
            symbol: Stock ticker
            company_type: 'non_financial', 'financial', 'reit', or 'utility'

        Returns:
            Dict with all calculated metrics (None for N/A)
        """
        try:
            if company_type == 'non_financial':
                return self._calc_non_financial(symbol)
            elif company_type == 'financial':
                return self._calc_financial(symbol)
            elif company_type == 'reit':
                return self._calc_reit(symbol)
            elif company_type == 'utility':
                return self._calc_utility(symbol)
            else:
                logger.warning(f"Unknown company type '{company_type}' for {symbol}")
                return {}

        except Exception as e:
            logger.error(f"Error calculating features for {symbol}: {e}")
            return {}

    # =====================================
    # NON-FINANCIALS
    # =====================================

    def _calc_non_financial(self, symbol: str) -> Dict:
        """
        Non-Financial companies (manufacturing, services, tech, consumer, etc.)

        Value Metrics:
        - ev_ebit_ttm: EV / EBIT (TTM)
        - ev_fcf_ttm: EV / Free Cash Flow (TTM)
        - pe_ttm: Price / Earnings (TTM)
        - pb_ttm: Price / Book (TTM)
        - shareholder_yield_%: (Dividends + Buybacks - Issuance) / Market Cap

        Quality Metrics:
        - roic_%: Return on Invested Capital = NOPAT / NOA
        - roic_persistence: Std dev of ROIC over 4 quarters (lower = more stable)
        - grossProfits_to_assets: Gross Profit / Total Assets (Novy-Marx)
        - fcf_margin_%: FCF / Revenue
        - cfo_to_ni: Cash from Operations / Net Income
        - netDebt_ebitda: (Total Debt - Cash) / EBITDA
        - interestCoverage: EBIT / Interest Expense
        - fixedChargeCoverage: (EBIT + Lease Expense) / (Interest + Lease)
        """
        features = {}

        # Get data from FMP
        try:
            profile = self.fmp.get_profile(symbol)
            metrics_ttm = self.fmp.get_key_metrics_ttm(symbol)
            ratios_ttm = self.fmp.get_ratios_ttm(symbol)
            ev_data = self.fmp.get_enterprise_values(symbol, limit=4)
            # Fetch 12 quarters for growth/trend analysis (3 years)
            income = self.fmp.get_income_statement(symbol, period='quarter', limit=12)
            balance = self.fmp.get_balance_sheet(symbol, period='quarter', limit=12)
            cashflow = self.fmp.get_cash_flow(symbol, period='quarter', limit=12)

            # Check if we got minimal required data
            if not profile or not income or len(income) < 4:
                logger.warning(f"Insufficient data for {symbol}: profile={bool(profile)}, income quarters={len(income) if income else 0}")
                return features

        except Exception as e:
            logger.warning(f"Failed to fetch data for {symbol}: {e}")
            return features

        # Extract latest values
        prof = profile[0] if profile else {}
        met = metrics_ttm[0] if metrics_ttm else {}
        rat = ratios_ttm[0] if ratios_ttm else {}
        ev = ev_data[0] if ev_data else {}
        inc = income[0] if income else {}
        bal = balance[0] if balance else {}
        cf = cashflow[0] if cashflow else {}

        # ============ PERFORMANCE OPTIMIZATION ============
        # Cache all TTM calculations upfront (avoids 29+ iterations over same data)
        ttm_cache = {
            # Income statement TTM
            'ebit': self._sum_ttm(income, 'operatingIncome'),
            'ebitda': self._sum_ttm(income, 'ebitda'),
            'gross_profit': self._sum_ttm(income, 'grossProfit'),
            'revenue': self._sum_ttm(income, 'revenue'),
            'net_income': self._sum_ttm(income, 'netIncome'),
            'interest_expense': self._sum_ttm(income, 'interestExpense'),
            'interest_income': self._sum_ttm(income, 'interestIncome'),
            'opex': self._sum_ttm(income, 'operatingExpenses'),
            # Cash flow TTM
            'fcf': self._sum_ttm(cashflow, 'freeCashFlow'),
            'cfo': self._sum_ttm(cashflow, 'operatingCashFlow'),
            'capex': abs(self._sum_ttm(cashflow, 'capitalExpenditure')),
            'dividends_paid': abs(self._sum_ttm(cashflow, 'dividendsPaid') or 0),
            'buybacks': abs(self._sum_ttm(cashflow, 'commonStockRepurchased') or 0),
            'da': self._sum_ttm(cashflow, 'depreciationAndAmortization'),
            # Quarterly slices for growth calculations
            'ni_last_4q': self._sum_ttm(income[0:4], 'netIncome') if len(income) >= 4 else None,
            'ni_prev_4q': self._sum_ttm(income[4:8], 'netIncome') if len(income) >= 8 else None,
        }
        # ==================================================

        # === VALUE METRICS (Modern Yields) ===
        # Using yields (inverted multiples) per Greenblatt, Novy-Marx research
        # Higher yields = better value

        # Calculate base components
        market_cap = prof.get('mktCap') or met.get('marketCap')
        ebit_ttm = ttm_cache['ebit']
        ebitda_ttm = ttm_cache['ebitda']
        total_debt = bal.get('totalDebt', 0)

        # CRITICAL FIX: Include Short Term Investments (Google, Apple, Microsoft)
        # These are liquid assets that should reduce EV just like cash
        cash = bal.get('cashAndCashEquivalents', 0)
        short_term_investments = bal.get('shortTermInvestments', 0)
        total_liquid_assets = cash + short_term_investments

        # EV = Market Cap + Debt - Liquid Assets (Cash + ST Investments)
        ev = market_cap + total_debt - total_liquid_assets if market_cap else None

        # Store components for debugging
        features['cash_and_equivalents'] = cash
        features['short_term_investments'] = short_term_investments
        features['total_liquid_assets'] = total_liquid_assets

        # Free Cash Flow & Operating Cash Flow (TTM) - Use cached values
        fcf_ttm = ttm_cache['fcf']
        cfo_ttm = ttm_cache['cfo']
        capex_ttm = ttm_cache['capex']

        # 1. Earnings Yield = EBIT / EV (Greenblatt Magic Formula)
        if ev and ev > 0 and ebit_ttm and ebit_ttm > 0:
            features['earnings_yield'] = (ebit_ttm / ev) * 100
        else:
            features['earnings_yield'] = None

        # 2. FCF Yield = FCF / EV (Modern standard)
        if ev and ev > 0 and fcf_ttm and fcf_ttm > 0:
            features['fcf_yield'] = (fcf_ttm / ev) * 100
        else:
            features['fcf_yield'] = None

        # 3. CFO Yield = Operating Cash Flow / EV (Stable alternative)
        if ev and ev > 0 and cfo_ttm and cfo_ttm > 0:
            features['cfo_yield'] = (cfo_ttm / ev) * 100
        else:
            features['cfo_yield'] = None

        # 4. Gross Profit Yield = Gross Profit / EV (Novy-Marx) - Use cached value
        gross_profit_ttm = ttm_cache['gross_profit']
        if ev and ev > 0 and gross_profit_ttm and gross_profit_ttm > 0:
            features['gross_profit_yield'] = (gross_profit_ttm / ev) * 100
        else:
            features['gross_profit_yield'] = None

        # 5. EBITDA-CAPEX Yield = (EBITDA - CAPEX) / EV (O'Shaughnessy)
        if ev and ev > 0 and ebitda_ttm:
            ebitda_minus_capex = ebitda_ttm - capex_ttm
            if ebitda_minus_capex > 0:
                features['ebitda_capex_yield'] = (ebitda_minus_capex / ev) * 100
            else:
                features['ebitda_capex_yield'] = None
        else:
            features['ebitda_capex_yield'] = None

        # Shareholder Yield % = (Dividends + Net Buybacks - Issuance) / Market Cap
        div_paid = abs(cf.get('dividendsPaid', 0))  # Usually negative
        stock_repurchase = abs(cf.get('commonStockRepurchased', 0)) if cf.get('commonStockRepurchased', 0) < 0 else 0
        stock_issued = cf.get('commonStockIssued', 0) if cf.get('commonStockIssued', 0) > 0 else 0
        shareholder_return = div_paid + stock_repurchase - stock_issued

        if market_cap and market_cap > 0:
            features['shareholder_yield_%'] = (shareholder_return / market_cap) * 100
        else:
            features['shareholder_yield_%'] = None

        # Legacy metrics (keep for backward compatibility but not used in scoring)
        features['ev_ebit_ttm'] = ev / ebit_ttm if ev and ebit_ttm and ebit_ttm > 0 else None
        features['ev_fcf_ttm'] = ev / fcf_ttm if ev and fcf_ttm and fcf_ttm > 0 else None
        features['pe_ttm'] = met.get('peRatioTTM') or rat.get('priceEarningsRatioTTM')
        features['pb_ttm'] = met.get('pbRatioTTM') or rat.get('priceToBookRatioTTM')

        # === NEW: PEG RATIO (Price/Earnings to Growth) ===
        # Critical for Growth stocks - normalizes P/E by growth rate
        # PEG < 1.0 = Ganga, < 1.5 = GARP, > 2.0 = Sobrevalorado
        pe_ratio = features['pe_ttm']
        if pe_ratio and pe_ratio > 0 and len(income) >= 8:
            # Calculate earnings growth: Last 4Q vs Previous 4Q (YoY) - Use cached values
            earnings_last_4q = ttm_cache['ni_last_4q']
            earnings_prev_4q = ttm_cache['ni_prev_4q']

            if earnings_last_4q and earnings_prev_4q and earnings_prev_4q > 0:
                earnings_growth = ((earnings_last_4q - earnings_prev_4q) / abs(earnings_prev_4q)) * 100
                # PEG Ratio = P/E / Growth Rate
                if earnings_growth > 0:  # Only calculate for positive growth
                    features['peg_ratio'] = pe_ratio / earnings_growth
                else:
                    features['peg_ratio'] = None  # Negative growth = N/A
            else:
                features['peg_ratio'] = None
        else:
            features['peg_ratio'] = None

        # === NEW: VALUATION SCORE COMBINADO (Academic Quant) ===
        # Ponderado: 40% EV/EBIT + 30% PEG + 30% FCF Yield
        # Para evitar falsos negativos en Growth stocks
        valuation_components = []

        # 1. EV/EBIT Score (Acquirer's Multiple)
        # Target: EV/EBIT < 15x (Earnings Yield > 6.67%)
        if features['earnings_yield'] and features['earnings_yield'] > 0:
            # Convert yield to score: 0-100 (6.67% yield = 100 pts)
            ev_ebit_score = min(100, (features['earnings_yield'] / 6.67) * 100)
            valuation_components.append(('ev_ebit', ev_ebit_score, 0.40))

        # 2. PEG Score (Growth-adjusted)
        # Target: PEG < 1.5
        if features['peg_ratio'] and features['peg_ratio'] > 0:
            # Lower PEG = better score
            if features['peg_ratio'] < 1.0:
                peg_score = 100  # Ganga
            elif features['peg_ratio'] < 1.5:
                peg_score = 80  # GARP (Growth at Reasonable Price)
            elif features['peg_ratio'] < 2.0:
                peg_score = 50  # Fair
            else:
                peg_score = max(0, 50 - ((features['peg_ratio'] - 2.0) * 20))  # Penalty
            valuation_components.append(('peg', peg_score, 0.30))

        # 3. FCF Yield Score
        # Target: FCF Yield > 5% (above risk-free rate ~4%)
        if features['fcf_yield'] and features['fcf_yield'] > 0:
            fcf_score = min(100, (features['fcf_yield'] / 5.0) * 100)
            valuation_components.append(('fcf', fcf_score, 0.30))

        # Calculate weighted valuation score
        if valuation_components:
            total_weight = sum(w for _, _, w in valuation_components)
            weighted_score = sum(score * (weight / total_weight) for _, score, weight in valuation_components)
            features['valuation_score'] = round(weighted_score, 1)
            features['valuation_components'] = {name: round(score, 1) for name, score, _ in valuation_components}
        else:
            features['valuation_score'] = None
            features['valuation_components'] = {}

        # NOTE: Quality-adjusted yields will be calculated later in scoring.py
        # after ROIC is computed, since ROIC depends on data not yet available here

        # === QUALITY METRICS ===

        # ROIC = NOPAT / NOA
        # NOPAT = EBIT * (1 - Tax Rate)
        # NOA = Operating Assets - Operating Liabilities
        #     = Total Assets - Cash - (Total Liabilities - Total Debt)
        tax_rate = self._estimate_tax_rate(income)
        nopat = ebit_ttm * (1 - tax_rate) if ebit_ttm else None

        total_assets = bal.get('totalAssets')
        total_liabilities = bal.get('totalLiabilities')

        if total_assets and total_liabilities and total_debt is not None and cash is not None:
            operating_liabilities = total_liabilities - total_debt
            noa = total_assets - cash - operating_liabilities
            if noa > 0 and nopat is not None:
                features['roic_%'] = (nopat / noa) * 100
            else:
                features['roic_%'] = None
        else:
            features['roic_%'] = None

        # ROIC Persistence (std dev of quarterly ROIC, lower = better)
        roic_quarterly = []
        for i in range(min(4, len(income))):
            ebit_q = income[i].get('operatingIncome', 0)
            tax_q = self._estimate_tax_rate([income[i]])
            nopat_q = ebit_q * (1 - tax_q)

            assets_q = balance[i].get('totalAssets', 0) if i < len(balance) else 0
            liab_q = balance[i].get('totalLiabilities', 0) if i < len(balance) else 0
            debt_q = balance[i].get('totalDebt', 0) if i < len(balance) else 0
            cash_q = balance[i].get('cashAndCashEquivalents', 0) if i < len(balance) else 0

            if assets_q and liab_q:
                noa_q = assets_q - cash_q - (liab_q - debt_q)
                if noa_q > 0:
                    roic_quarterly.append((nopat_q / noa_q) * 100)

        if len(roic_quarterly) >= 3:
            features['roic_persistence'] = np.std(roic_quarterly)
        else:
            features['roic_persistence'] = None

        # Gross Profits / Assets (Novy-Marx) - Use cached value
        gross_profit_ttm = ttm_cache['gross_profit']
        if gross_profit_ttm and total_assets and total_assets > 0:
            features['grossProfits_to_assets'] = (gross_profit_ttm / total_assets) * 100
        else:
            features['grossProfits_to_assets'] = None

        # FCF Margin % = FCF / Revenue - Use cached values
        revenue_ttm = ttm_cache['revenue']
        if fcf_ttm and revenue_ttm and revenue_ttm > 0:
            features['fcf_margin_%'] = (fcf_ttm / revenue_ttm) * 100
        else:
            features['fcf_margin_%'] = None

        # CFO / Net Income - Use cached values
        cfo_ttm = ttm_cache['cfo']
        ni_ttm = ttm_cache['net_income']
        if cfo_ttm and ni_ttm and ni_ttm != 0:
            features['cfo_to_ni'] = cfo_ttm / ni_ttm
        else:
            features['cfo_to_ni'] = None

        # Net Debt / EBITDA - Use cached value
        ebitda_ttm = ttm_cache['ebitda']
        net_debt = total_debt - cash if total_debt is not None and cash is not None else None
        if net_debt is not None and ebitda_ttm and ebitda_ttm > 0:
            features['netDebt_ebitda'] = net_debt / ebitda_ttm
        else:
            features['netDebt_ebitda'] = None

        # Interest Coverage = EBIT / Interest Expense - Use cached value
        interest_ttm = ttm_cache['interest_expense']
        if ebit_ttm and interest_ttm and interest_ttm > 0:
            features['interestCoverage'] = ebit_ttm / interest_ttm
        else:
            features['interestCoverage'] = None

        # === QUALITY STABILITY METRICS ===
        # Lower volatility = higher quality (Mohanram, Asness)

        # ROA Stability = std(ROA) / mean(ROA) over last 4 quarters (lower is better)
        roa_quarterly = []
        for i in range(min(4, len(income))):
            ni_q = income[i].get('netIncome', 0)
            assets_q = balance[i].get('totalAssets', 0) if i < len(balance) else 0
            if assets_q and assets_q > 0:
                roa_quarterly.append((ni_q / assets_q) * 100)

        if len(roa_quarterly) >= 3:
            mean_roa = np.mean(roa_quarterly)
            if mean_roa != 0:
                features['roa_stability'] = np.std(roa_quarterly) / abs(mean_roa)
            else:
                features['roa_stability'] = None
        else:
            features['roa_stability'] = None

        # Calculate TTM ROA while we have the data
        if ni_ttm and total_assets and total_assets > 0:
            features['roa_%'] = (ni_ttm / total_assets) * 100
        else:
            features['roa_%'] = None

        # FCF Stability = std(FCF) / mean(FCF) over last 4 quarters (lower is better)
        fcf_quarterly = []
        for i in range(min(4, len(cashflow))):
            fcf_q = cashflow[i].get('freeCashFlow', 0)
            fcf_quarterly.append(fcf_q)

        if len(fcf_quarterly) >= 3:
            mean_fcf = np.mean(fcf_quarterly)
            if mean_fcf != 0:
                features['fcf_stability'] = np.std(fcf_quarterly) / abs(mean_fcf)
            else:
                features['fcf_stability'] = None
        else:
            features['fcf_stability'] = None

        # Cash ROA = CFO / Assets (Piotroski - cash-based profitability)
        if cfo_ttm and total_assets and total_assets > 0:
            features['cash_roa'] = (cfo_ttm / total_assets) * 100
        else:
            features['cash_roa'] = None

        # === MOMENTUM & TREND METRICS ===
        # Detect declining businesses (revenue falling, ROIC eroding, margins contracting)

        # 1. Revenue Growth (3-year CAGR)
        if len(income) >= 12:
            revenue_latest = income[0].get('revenue', 0)
            revenue_3y_ago = income[11].get('revenue', 0)

            if revenue_latest and revenue_3y_ago and revenue_3y_ago > 0:
                # CAGR formula: (Ending/Beginning)^(1/years) - 1
                features['revenue_growth_3y'] = ((revenue_latest / revenue_3y_ago) ** (1/3) - 1) * 100
            else:
                features['revenue_growth_3y'] = None
        else:
            features['revenue_growth_3y'] = None

        # 2. ROIC Trend (compare recent 4Q vs previous 4Q)
        # Positive = ROIC improving, Negative = ROIC eroding
        if len(roic_quarterly) >= 8:
            roic_recent = np.mean(roic_quarterly[:4])  # Most recent 4Q
            roic_previous = np.mean(roic_quarterly[4:8])  # Previous 4Q

            if roic_previous != 0:
                features['roic_trend'] = ((roic_recent - roic_previous) / abs(roic_previous)) * 100
            else:
                features['roic_trend'] = None
        else:
            features['roic_trend'] = None

        # 3. Gross Margin Trend (compare recent 4Q vs previous 4Q)
        # Positive = margins expanding, Negative = margins contracting
        gross_margins_quarterly = []
        for i in range(min(8, len(income))):
            revenue_q = income[i].get('revenue', 0)
            gross_profit_q = income[i].get('grossProfit', 0)
            if revenue_q and revenue_q > 0:
                gross_margins_quarterly.append((gross_profit_q / revenue_q) * 100)

        if len(gross_margins_quarterly) >= 8:
            gm_recent = np.mean(gross_margins_quarterly[:4])
            gm_previous = np.mean(gross_margins_quarterly[4:8])

            if gm_previous != 0:
                features['margin_trend'] = ((gm_recent - gm_previous) / abs(gm_previous)) * 100
            else:
                features['margin_trend'] = None
        else:
            features['margin_trend'] = None

        # === QUALITY DEGRADATION SCORES ===
        # Use appropriate score based on company type (Value vs Growth)

        # Calculate P/B to classify
        book_value = bal.get('totalStockholdersEquity', 0)
        price_to_book = (market_cap / book_value) if book_value and book_value > 0 else None

        # Piotroski F-Score (for Value stocks: P/B < 1.5)
        features['piotroski_fscore'], features['piotroski_fscore_delta'] = self._calc_piotroski_delta(
            income, balance, cashflow
        )

        # Mohanram G-Score (for Growth stocks: P/B >= 1.5)
        features['mohanram_gscore'], features['mohanram_gscore_delta'] = self._calc_mohanram_delta(
            income, balance, cashflow, price_to_book
        )

        # Determine which score to use for blocking decisions
        if price_to_book and price_to_book < 1.5:
            features['quality_degradation_type'] = 'VALUE'
            features['quality_degradation_score'] = features['piotroski_fscore']
            features['quality_degradation_delta'] = features['piotroski_fscore_delta']
        else:
            features['quality_degradation_type'] = 'GROWTH'
            features['quality_degradation_score'] = features['mohanram_gscore']
            features['quality_degradation_delta'] = features['mohanram_gscore_delta']

        # === MOAT SCORE (Competitive Advantages) ===
        # Quantitative proxies using only FMP data - no LLMs, $0 cost
        # Based on: Pricing Power, Operating Leverage, ROIC Persistence

        # 1. Pricing Power (30% weight) - Gross Margin analysis
        features['pricing_power_score'] = self._calc_pricing_power(
            income, balance, symbol
        )

        # 2. Operating Leverage (25% weight) - Scale economies
        features['operating_leverage_score'] = self._calc_operating_leverage(
            income
        )

        # 3. ROIC Persistence (20% weight) - Quality durability
        features['roic_persistence_score'] = self._calc_roic_persistence(
            roic_quarterly
        )

        # Composite Moat Score (0-100)
        moat_components = [
            features['pricing_power_score'],
            features['operating_leverage_score'],
            features['roic_persistence_score']
        ]

        # Only calculate if we have at least 2 of 3 components
        valid_components = [x for x in moat_components if x is not None]
        if len(valid_components) >= 2:
            base_moat_score = (
                (features['pricing_power_score'] or 50) * 0.30 +
                (features['operating_leverage_score'] or 50) * 0.25 +
                (features['roic_persistence_score'] or 50) * 0.20 +
                50 * 0.25  # Remaining 25% defaulted to median (future: add more components)
            )

            # === MOMENTUM PENALTIES ===
            # Penalize moat score if business is declining (revenue down, ROIC eroding, margins contracting)
            # This prevents "false positives" of companies with high historical metrics but deteriorating fundamentals

            penalty_multiplier = 1.0

            # 1. Revenue Decline Penalty
            if features['revenue_growth_3y'] is not None and features['revenue_growth_3y'] < 0:
                # Declining revenue = moat erosion
                penalty_multiplier *= 0.80  # 20% penalty

            # 2. ROIC Erosion Penalty
            if features['roic_trend'] is not None and features['roic_trend'] < -10:
                # ROIC declining >10% = competitive position weakening
                penalty_multiplier *= 0.85  # 15% penalty

            # 3. Margin Contraction Penalty
            if features['margin_trend'] is not None and features['margin_trend'] < -5:
                # Gross margin contracting >5% = pricing power loss
                penalty_multiplier *= 0.85  # 15% penalty

            # Apply penalties (multiplicative)
            features['moat_score'] = base_moat_score * penalty_multiplier
        else:
            features['moat_score'] = None

        # Fixed Charge Coverage = (EBIT + Operating Leases) / (Interest + Operating Leases)
        # Simplified: assume operating lease ~= operatingExpenses * 0.1 (rough proxy)
        # For better accuracy, would need footnote data (not in standard API)
        features['fixedChargeCoverage'] = None  # Placeholder (requires lease detail)

        # Placeholder for non-financial-specific fields
        features['p_tangibleBook'] = None
        features['roe_%'] = None
        features['efficiency_ratio'] = None
        features['nim_%'] = None
        features['combined_ratio_%'] = None
        features['cet1_or_leverage_ratio_%'] = None
        features['loans_to_deposits'] = None
        features['p_ffo'] = None
        features['p_affo'] = None
        features['ffo_payout_%'] = None
        features['affo_payout_%'] = None
        features['sameStoreNOI_growth_%'] = None
        features['occupancy_%'] = None
        features['netDebt_ebitda_re'] = None
        features['debt_to_grossAssets_%'] = None
        features['securedDebt_%'] = None

        return features

    # =====================================
    # FINANCIALS (Banks, Insurance, etc.)
    # =====================================

    def _calc_financial(self, symbol: str) -> Dict:
        """
        Financial companies (banks, insurance, asset management, etc.)

        Value Metrics:
        - pe_ttm: Price / Earnings
        - pb_ttm: Price / Book
        - p_tangibleBook: Price / Tangible Book Value
        - dividendYield_%
        - netShareIssuance_% (dilution)

        Quality Metrics:
        - roa_%: Return on Assets
        - roe_%: Return on Equity
        - efficiency_ratio: Operating Expenses / Revenue (lower is better)
        - nim_%: Net Interest Margin (banks)
        - combined_ratio_%: (Loss Ratio + Expense Ratio) for insurance
        - cet1_or_leverage_ratio_%: CET1 capital ratio (banks) or leverage
        - loans_to_deposits: Loan/Deposit ratio (banks)
        """
        features = {}

        try:
            profile = self.fmp.get_profile(symbol)
            metrics_ttm = self.fmp.get_key_metrics_ttm(symbol)
            ratios_ttm = self.fmp.get_ratios_ttm(symbol)
            income = self.fmp.get_income_statement(symbol, period='quarter', limit=4)
            balance = self.fmp.get_balance_sheet(symbol, period='quarter', limit=4)
            cashflow = self.fmp.get_cash_flow(symbol, period='quarter', limit=4)

            # Check if we got minimal required data
            if not profile or not income or len(income) < 4:
                logger.warning(f"Insufficient data for financial {symbol}: profile={bool(profile)}, income quarters={len(income) if income else 0}")
                return features

        except Exception as e:
            logger.warning(f"Failed to fetch financial data for {symbol}: {e}")
            return features

        prof = profile[0] if profile else {}
        met = metrics_ttm[0] if metrics_ttm else {}
        rat = ratios_ttm[0] if ratios_ttm else {}
        inc = income[0] if income else {}
        bal = balance[0] if balance else {}
        cf = cashflow[0] if cashflow else {}

        # === VALUE METRICS ===

        features['pe_ttm'] = met.get('peRatioTTM') or rat.get('priceEarningsRatioTTM')
        features['pb_ttm'] = met.get('pbRatioTTM') or rat.get('priceToBookRatioTTM')

        # P / Tangible Book = Market Cap / (Total Equity - Intangibles - Goodwill)
        market_cap = prof.get('mktCap') or met.get('marketCap')
        equity = bal.get('totalStockholdersEquity', 0)
        intangibles = bal.get('intangibleAssets', 0)
        goodwill = bal.get('goodwill', 0)
        tangible_book = equity - intangibles - goodwill

        if market_cap and tangible_book and tangible_book > 0:
            features['p_tangibleBook'] = market_cap / tangible_book
        else:
            features['p_tangibleBook'] = None

        # Dividend Yield
        features['dividendYield_%'] = prof.get('lastDiv') or None  # Annual div / price

        # Net Share Issuance (calculated later in guardrails, placeholder here)
        features['netShareIssuance_%'] = None

        # === NEW: VALUATION SCORE PARA FINANCIERAS ===
        # Basado en P/TBV, ROE, Dividend Yield (academia bancaria)
        # Ver: Fama-French banking factors, Credit Suisse Global Investment Returns Yearbook
        financial_val_components = []

        # 1. P/TBV Absoluto Score
        # Target: P/TBV < 1.0 (trade below tangible book = ganga)
        # P/TBV > 2.0 (premium quality o sobrevalorado)
        if features['p_tangibleBook'] and features['p_tangibleBook'] > 0:
            p_tbv = features['p_tangibleBook']
            if p_tbv < 1.0:
                p_tbv_score = 100  # Trade below book (distressed o value trap)
            elif p_tbv < 1.5:
                p_tbv_score = 80  # Fair value
            elif p_tbv < 2.0:
                p_tbv_score = 60  # Moderado
            else:
                # Penalty por cada 0.5x sobre 2.0
                p_tbv_score = max(0, 60 - ((p_tbv - 2.0) / 0.5) * 20)
            financial_val_components.append(('p_tbv', p_tbv_score, 0.40))

        # 2. ROE Adjustment (CRITICAL for banks)
        # No sirve P/TBV < 1.0 si ROE = 2% (value trap)
        # ROE alto justifica P/TBV alto
        # Regla: P/TBV Fair = ROE / 10 (e.g., ROE 15% → P/TBV 1.5x)
        if features['p_tangibleBook'] and features['roe_%']:
            p_tbv = features['p_tangibleBook']
            roe = features['roe_%']
            fair_p_tbv = roe / 10  # Fair value múltiple basado en ROE

            # Calculate mispricing: actual vs fair
            if fair_p_tbv > 0:
                mispricing = ((fair_p_tbv - p_tbv) / fair_p_tbv) * 100
                # Positive mispricing = undervalued (fair > actual)
                # Target: 20%+ undervalued = 100 pts
                if mispricing > 20:
                    roe_adj_score = 100
                elif mispricing > 10:
                    roe_adj_score = 80
                elif mispricing > 0:
                    roe_adj_score = 60
                elif mispricing > -10:
                    roe_adj_score = 40
                else:
                    roe_adj_score = max(0, 40 + (mispricing + 10) * 2)  # Penalty
                financial_val_components.append(('roe_adj', roe_adj_score, 0.40))

        # 3. Dividend Yield Score
        # Target: 5-7% sostenible (evidencia de cash generation real)
        if features['dividendYield_%'] and features['dividendYield_%'] > 0:
            div_yield = features['dividendYield_%']
            if div_yield >= 5:
                div_score = 100  # Excellent yield
            elif div_yield >= 3:
                div_score = 60 + ((div_yield - 3) / 2) * 40  # Linear 3-5%
            else:
                div_score = max(0, (div_yield / 3) * 60)  # Below 3%
            financial_val_components.append(('dividend', div_score, 0.20))

        # Calculate weighted valuation score for financials
        if financial_val_components:
            total_weight = sum(w for _, _, w in financial_val_components)
            weighted_score = sum(score * (weight / total_weight) for _, score, weight in financial_val_components)
            features['valuation_score'] = round(weighted_score, 1)
            features['valuation_components'] = {name: round(score, 1) for name, score, _ in financial_val_components}
        else:
            features['valuation_score'] = None
            features['valuation_components'] = {}

        # === QUALITY METRICS ===

        # ROA = Net Income / Total Assets
        ni_ttm = self._sum_ttm(income, 'netIncome')
        total_assets = bal.get('totalAssets')
        if ni_ttm and total_assets and total_assets > 0:
            features['roa_%'] = (ni_ttm / total_assets) * 100
        else:
            features['roa_%'] = None

        # ROE = Net Income / Shareholders Equity
        if ni_ttm and equity and equity > 0:
            features['roe_%'] = (ni_ttm / equity) * 100
        else:
            features['roe_%'] = None

        # Efficiency Ratio = Operating Expenses / Revenue (banks use this)
        revenue_ttm = self._sum_ttm(income, 'revenue')
        opex_ttm = self._sum_ttm(income, 'operatingExpenses')
        if opex_ttm and revenue_ttm and revenue_ttm > 0:
            features['efficiency_ratio'] = (opex_ttm / revenue_ttm) * 100
        else:
            features['efficiency_ratio'] = None

        # NIM (Net Interest Margin) for banks = Net Interest Income / Avg Earning Assets
        # Proxy: (Interest Income - Interest Expense) / Total Assets
        # FMP might have 'interestIncome' and 'interestExpense' for banks
        interest_income_ttm = self._sum_ttm(income, 'interestIncome')
        interest_expense_ttm = self._sum_ttm(income, 'interestExpense')
        if interest_income_ttm and interest_expense_ttm is not None and total_assets:
            net_interest_income = interest_income_ttm - interest_expense_ttm
            features['nim_%'] = (net_interest_income / total_assets) * 100
        else:
            features['nim_%'] = None

        # Combined Ratio (insurance) = (Incurred Losses + Expenses) / Earned Premiums
        # FMP might not have granular insurance metrics; placeholder
        features['combined_ratio_%'] = None

        # CET1 / Leverage Ratio (banks)
        # FMP doesn't expose CET1 directly; would need regulatory filings
        # Proxy: Tier 1 Capital Ratio or simple Equity / Assets
        if equity and total_assets and total_assets > 0:
            features['cet1_or_leverage_ratio_%'] = (equity / total_assets) * 100
        else:
            features['cet1_or_leverage_ratio_%'] = None

        # Loans to Deposits (banks)
        # FMP balance sheet might have 'netLoans' and 'deposits'
        loans = bal.get('netLoans') or bal.get('netReceivables')  # Fallback
        deposits = bal.get('shortTermDebt')  # Placeholder (not always accurate)
        # Note: For proper L/D ratio, need bank-specific line items
        features['loans_to_deposits'] = None

        # Null out non-financial fields
        features['ev_ebit_ttm'] = None
        features['ev_fcf_ttm'] = None
        features['shareholder_yield_%'] = None
        features['roic_%'] = None
        features['roic_persistence'] = None
        features['grossProfits_to_assets'] = None
        features['fcf_margin_%'] = None
        features['cfo_to_ni'] = None
        features['netDebt_ebitda'] = None
        features['interestCoverage'] = None
        features['fixedChargeCoverage'] = None
        features['p_ffo'] = None
        features['p_affo'] = None
        features['ffo_payout_%'] = None
        features['affo_payout_%'] = None
        features['sameStoreNOI_growth_%'] = None
        features['occupancy_%'] = None
        features['netDebt_ebitda_re'] = None
        features['debt_to_grossAssets_%'] = None
        features['securedDebt_%'] = None

        return features

    # =====================================
    # REITs
    # =====================================

    def _calc_reit(self, symbol: str) -> Dict:
        """
        Real Estate Investment Trusts (REITs)

        Value Metrics:
        - p_ffo: Price / Funds From Operations
        - p_affo: Price / Adjusted Funds From Operations
        - dividendYield_%

        Quality Metrics:
        - ffo_payout_%: Dividends / FFO
        - affo_payout_%: Dividends / AFFO
        - sameStoreNOI_growth_%: Same-store NOI growth
        - occupancy_%: Property occupancy rate
        - netDebt_ebitda_re: Net Debt / EBITDA (RE adjusted)
        - debt_to_grossAssets_%: Total Debt / Gross Assets
        - securedDebt_%: Secured Debt / Total Debt
        """
        features = {}

        try:
            profile = self.fmp.get_profile(symbol)
            metrics_ttm = self.fmp.get_key_metrics_ttm(symbol)
            ratios_ttm = self.fmp.get_ratios_ttm(symbol)
            income = self.fmp.get_income_statement(symbol, period='quarter', limit=4)
            balance = self.fmp.get_balance_sheet(symbol, period='quarter', limit=4)
            cashflow = self.fmp.get_cash_flow(symbol, period='quarter', limit=4)

            # Check if we got minimal required data
            if not profile or not income or len(income) < 4:
                logger.warning(f"Insufficient data for REIT {symbol}: profile={bool(profile)}, income quarters={len(income) if income else 0}")
                return features

        except Exception as e:
            logger.warning(f"Failed to fetch REIT data for {symbol}: {e}")
            return features

        prof = profile[0] if profile else {}
        met = metrics_ttm[0] if metrics_ttm else {}
        rat = ratios_ttm[0] if ratios_ttm else {}
        inc = income[0] if income else {}
        bal = balance[0] if balance else {}
        cf = cashflow[0] if cashflow else {}

        # === Calculate FFO & AFFO ===
        # FFO = Net Income + Depreciation & Amortization - Gains on Sales of Property
        # AFFO = FFO - Recurring Capex (maintenance capex)

        ni_ttm = self._sum_ttm(income, 'netIncome')
        da_ttm = self._sum_ttm(cashflow, 'depreciationAndAmortization')

        # Gains on sales (not always available; use 0 if missing)
        # FMP income statement might have 'otherNonOperatingIncomeExpenses'
        gains_on_sales = 0  # Placeholder

        ffo = ni_ttm + da_ttm - gains_on_sales if ni_ttm and da_ttm else None

        # AFFO: FFO - maintenance capex
        # Capex from cash flow statement
        capex_ttm = abs(self._sum_ttm(cashflow, 'capitalExpenditure'))
        maintenance_capex = capex_ttm * 0.5  # Rough estimate: 50% is maintenance
        affo = ffo - maintenance_capex if ffo else None

        # P/FFO and P/AFFO
        market_cap = prof.get('mktCap') or met.get('marketCap')
        shares = prof.get('volAvg') or bal.get('commonStock')  # Shares outstanding proxy

        if ffo and market_cap:
            features['p_ffo'] = market_cap / ffo if ffo > 0 else None
        else:
            features['p_ffo'] = None

        if affo and market_cap:
            features['p_affo'] = market_cap / affo if affo > 0 else None
        else:
            features['p_affo'] = None

        # Dividend Yield
        features['dividendYield_%'] = prof.get('lastDiv')

        # === QUALITY METRICS ===

        # FFO Payout Ratio = Dividends / FFO
        div_paid_ttm = abs(self._sum_ttm(cashflow, 'dividendsPaid'))
        if ffo and ffo > 0:
            features['ffo_payout_%'] = (div_paid_ttm / ffo) * 100
        else:
            features['ffo_payout_%'] = None

        # AFFO Payout
        if affo and affo > 0:
            features['affo_payout_%'] = (div_paid_ttm / affo) * 100
        else:
            features['affo_payout_%'] = None

        # Same-Store NOI Growth (not in standard FMP; would need supplemental disclosure)
        features['sameStoreNOI_growth_%'] = None

        # Occupancy % (not in standard FMP; would need property-level data)
        features['occupancy_%'] = None

        # Net Debt / EBITDA (RE-adjusted)
        total_debt = bal.get('totalDebt', 0)
        cash = bal.get('cashAndCashEquivalents', 0)
        net_debt = total_debt - cash
        ebitda_ttm = self._sum_ttm(income, 'ebitda')

        if ebitda_ttm and ebitda_ttm > 0:
            features['netDebt_ebitda_re'] = net_debt / ebitda_ttm
        else:
            features['netDebt_ebitda_re'] = None

        # Debt to Gross Assets %
        total_assets = bal.get('totalAssets')
        if total_debt and total_assets and total_assets > 0:
            features['debt_to_grossAssets_%'] = (total_debt / total_assets) * 100
        else:
            features['debt_to_grossAssets_%'] = None

        # Secured Debt % (not granular in FMP; placeholder)
        features['securedDebt_%'] = None

        # Null out non-REIT fields
        features['pe_ttm'] = None
        features['pb_ttm'] = None
        features['ev_ebit_ttm'] = None
        features['ev_fcf_ttm'] = None
        features['shareholder_yield_%'] = None
        features['p_tangibleBook'] = None
        features['roic_%'] = None
        features['roic_persistence'] = None
        features['grossProfits_to_assets'] = None
        features['fcf_margin_%'] = None
        features['cfo_to_ni'] = None
        features['netDebt_ebitda'] = None
        features['interestCoverage'] = None
        features['fixedChargeCoverage'] = None
        features['roa_%'] = None
        features['roe_%'] = None
        features['efficiency_ratio'] = None
        features['nim_%'] = None
        features['combined_ratio_%'] = None
        features['cet1_or_leverage_ratio_%'] = None
        features['loans_to_deposits'] = None

        return features

    # =====================================
    # UTILITIES
    # =====================================

    def _calc_utility(self, symbol: str) -> Dict:
        """
        Utilities (Regulated Electric, Gas, Water, Telecom)

        Key differences from non-financials:
        - Asset-heavy, capital-intensive, regulated
        - ROIC typically LOW (4-8%) due to regulation
        - ROE regulated by CPUC/FERC (typically 9-12%)
        - Stability > Growth
        - Rate of Return (ROR) model
        - Focus: Dividend yield, regulatory assets, stable cash flows

        Research: Utilities should NOT use ROIC benchmarks from unregulated companies
        """
        features = {}

        income = self.fmp.get_income_statement(symbol, period='quarter', limit=8)
        balance = self.fmp.get_balance_sheet(symbol, period='quarter', limit=8)
        cashflow = self.fmp.get_cash_flow_statement(symbol, period='quarter', limit=8)

        if not income or not balance or not cashflow:
            return {}

        # === VALUE METRICS ===

        market_cap = balance[0].get('marketCap', 0)
        total_debt = balance[0].get('totalDebt', 0)
        cash = balance[0].get('cashAndCashEquivalents', 0)
        enterprise_value = market_cap + total_debt - cash if market_cap else 0

        features['market_cap'] = market_cap
        features['enterprise_value'] = enterprise_value

        # EV/EBITDA (preferred for capital-intensive)
        ebitda_ttm = self._sum_ttm(income, 'ebitda')
        features['ev_ebitda_ttm'] = enterprise_value / ebitda_ttm if enterprise_value and ebitda_ttm and ebitda_ttm > 0 else None

        # P/E
        earnings_ttm = self._sum_ttm(income, 'netIncome')
        shares = balance[0].get('weightedAverageShsOut') or 1
        eps_ttm = earnings_ttm / shares if earnings_ttm and shares else None
        price = balance[0].get('price', 0)
        features['pe_ttm'] = price / eps_ttm if price and eps_ttm and eps_ttm > 0 else None

        # P/B
        book_value = balance[0].get('totalStockholdersEquity', 0)
        book_per_share = book_value / shares if shares else None
        features['pb_ttm'] = price / book_per_share if price and book_per_share and book_per_share > 0 else None

        # Dividend Yield (critical for utilities)
        dividends_ttm = abs(self._sum_ttm(cashflow, 'dividendsPaid') or 0)
        features['dividend_yield_%'] = (dividends_ttm / market_cap) * 100 if market_cap else None

        # Shareholder Yield (dividends + buybacks)
        buybacks_ttm = abs(self._sum_ttm(cashflow, 'commonStockRepurchased') or 0)
        shareholder_payout = dividends_ttm + buybacks_ttm
        features['shareholder_yield_%'] = (shareholder_payout / market_cap) * 100 if market_cap else None

        # === QUALITY METRICS (Utility-Specific) ===

        # ROE (more relevant than ROIC for utilities)
        # Regulated utilities target ROE of 9-12%
        avg_equity = (balance[0].get('totalStockholdersEquity', 0) + balance[1].get('totalStockholdersEquity', 0)) / 2 if len(balance) > 1 else balance[0].get('totalStockholdersEquity', 0)

        if earnings_ttm and avg_equity and avg_equity > 0:
            features['roe_%'] = (earnings_ttm / avg_equity) * 100
        else:
            features['roe_%'] = None

        # ROA (supplementary)
        avg_assets = (balance[0].get('totalAssets', 0) + balance[1].get('totalAssets', 0)) / 2 if len(balance) > 1 else balance[0].get('totalAssets', 0)

        if earnings_ttm and avg_assets and avg_assets > 0:
            features['roa_%'] = (earnings_ttm / avg_assets) * 100
        else:
            features['roa_%'] = None

        # ROIC (for consistency, but NOT used in scoring for utilities)
        # Utilities will have low ROIC by design - this is EXPECTED
        features['roic_%'] = None  # Explicitly None - not applicable
        features['roic_persistence'] = None

        # Operating Cash Flow Margin (stability indicator)
        revenue_ttm = self._sum_ttm(income, 'revenue')
        ocf_ttm = self._sum_ttm(cashflow, 'operatingCashFlow')

        features['ocf_margin_%'] = (ocf_ttm / revenue_ttm) * 100 if ocf_ttm and revenue_ttm and revenue_ttm > 0 else None

        # FCF Margin (after capex)
        capex_ttm = abs(self._sum_ttm(cashflow, 'capitalExpenditure') or 0)
        fcf_ttm = ocf_ttm - capex_ttm if ocf_ttm else None

        features['fcf_margin_%'] = (fcf_ttm / revenue_ttm) * 100 if fcf_ttm and revenue_ttm and revenue_ttm > 0 else None

        # Regulated Asset Base / Total Assets (utility-specific quality metric)
        # Higher = more regulated, lower risk
        property_plant_equipment = balance[0].get('propertyPlantEquipmentNet', 0)
        total_assets = balance[0].get('totalAssets', 0)

        features['regulated_asset_ratio'] = (property_plant_equipment / total_assets) if total_assets > 0 else None

        # === LEVERAGE ===

        # Debt/Equity (utilities typically 1.0-2.0x)
        equity = balance[0].get('totalStockholdersEquity', 0)
        features['debt_to_equity'] = total_debt / equity if equity > 0 else None

        # Debt/EBITDA (coverage)
        features['netDebt_ebitda'] = (total_debt - cash) / ebitda_ttm if ebitda_ttm and ebitda_ttm > 0 else None

        # Interest Coverage
        interest_expense = abs(self._sum_ttm(income, 'interestExpense') or 0)
        ebit_ttm = self._sum_ttm(income, 'operatingIncome')

        features['interestCoverage'] = ebit_ttm / interest_expense if ebit_ttm and interest_expense > 0 else None

        # === REGULATORY STABILITY SCORE ===
        # Utility-specific: Higher = more stable, lower risk
        # Factors: ROE within regulated range (9-12%), stable dividend, manageable debt

        stability_score = 50  # Base

        if features['roe_%']:
            if 9 <= features['roe_%'] <= 12:
                stability_score += 20  # Within regulated target
            elif 7 <= features['roe_%'] <= 14:
                stability_score += 10  # Close to target
            else:
                stability_score -= 10  # Outside normal range

        if features['dividend_yield_%'] and features['dividend_yield_%'] >= 3:
            stability_score += 15  # Strong dividend

        if features['debt_to_equity']:
            if features['debt_to_equity'] <= 2.0:
                stability_score += 15  # Manageable debt
            elif features['debt_to_equity'] > 3.0:
                stability_score -= 20  # High leverage risk

        features['utility_stability_score'] = max(0, min(100, stability_score))

        # === MOAT SCORE ===
        # Utilities have natural monopolies (regulatory moats)
        # Base score: 70 (regulatory barriers to entry)
        # Adjusted by stability

        moat_base = 70  # Regulatory moat

        if features['regulated_asset_ratio'] and features['regulated_asset_ratio'] > 0.7:
            moat_base += 10  # High regulated asset base

        if features['utility_stability_score'] >= 70:
            moat_base += 10  # Financial stability adds to moat

        features['moat_score'] = min(100, moat_base)

        # === PRICING POWER & OPERATING LEVERAGE ===
        # For utilities, these are regulated - set to moderate defaults
        features['pricing_power_score'] = 50  # Regulated prices
        features['operating_leverage_score'] = 50  # Fixed asset base
        features['roic_persistence_score'] = None  # Not applicable

        # === QUALITY DEGRADATION (Piotroski) ===
        # Use Piotroski for utilities (value-oriented, not growth)
        features['piotroski_fscore'] = self._calculate_piotroski(income, balance, cashflow)
        features['piotroski_fscore_delta'] = None  # Placeholder
        features['mohanram_gscore'] = None  # Not applicable (utilities are value, not growth)
        features['mohanram_gscore_delta'] = None

        features['quality_degradation_type'] = 'VALUE'
        features['quality_degradation_score'] = features['piotroski_fscore']
        features['quality_degradation_delta'] = features['piotroski_fscore_delta']

        # === PROFITABILITY & TREND ===
        features['grossProfits_to_assets'] = None  # Not standard for utilities
        features['gross_margin_%'] = None
        features['roic_trend'] = None
        features['gross_margin_trend'] = None
        features['revenue_growth_ttm_%'] = None  # Typically low/stable

        # === NOT APPLICABLE FOR UTILITIES ===
        features['fcf_yield'] = None
        features['ebitda_capex_yield'] = None
        features['ev_ebit_ttm'] = None
        features['ev_fcf_ttm'] = None
        features['roic_stability'] = None
        features['efficiency_ratio'] = None
        features['nim_%'] = None
        features['combined_ratio_%'] = None
        features['cet1_or_leverage_ratio_%'] = None
        features['loans_to_deposits'] = None
        features['p_ffo'] = None
        features['ffo_payout_%'] = None
        features['occupancy_%'] = None
        features['p_tangibleBook'] = None

        return features

    # =====================================
    # HELPERS
    # =====================================

    def _sum_ttm(self, statements: List[Dict], field: str) -> Optional[float]:
        """Sum a field over the last 4 quarters (TTM)."""
        if not statements or len(statements) < 4:
            return None

        total = 0
        for i in range(4):
            val = statements[i].get(field, 0)
            if val is None:
                return None
            total += val

        return total

    def _estimate_tax_rate(self, income_statements: List[Dict]) -> float:
        """
        Estimate effective tax rate from income statement.
        Tax Rate = Income Tax Expense / Income Before Tax
        Default to 21% if unable to calculate.
        """
        if not income_statements:
            return 0.21

        inc = income_statements[0]
        tax_expense = inc.get('incomeTaxExpense', 0)
        income_before_tax = inc.get('incomeBeforeTax', 0)

        if income_before_tax and income_before_tax > 0:
            return tax_expense / income_before_tax

        return 0.21  # US corporate rate default

    def _calc_pricing_power(self, income: List[Dict], balance: List[Dict], symbol: str) -> Optional[float]:
        """
        Calculate Pricing Power Score (0-100) based on Gross Margin analysis.

        Components:
        1. Gross Margin Level (40%) - Absolute GM% vs benchmarks
        2. Gross Margin Trend (30%) - Expanding/stable/declining
        3. Gross Margin Stability (30%) - Consistency over time

        High score = High, stable, expanding gross margins (pricing power)
        """
        if not income or len(income) < 4:
            return None

        try:
            # Calculate quarterly gross margins for last 8 quarters (or available)
            gross_margins = []
            for i in range(min(8, len(income))):
                revenue = income[i].get('revenue', 0)
                gross_profit = income[i].get('grossProfit', 0)

                if revenue and revenue > 0:
                    gm = (gross_profit / revenue) * 100
                    gross_margins.append(gm)

            if len(gross_margins) < 4:
                return None

            # === Component 1: Gross Margin Level (40%) ===
            # Benchmark: 40%+ = excellent, 30-40% = good, 20-30% = average, <20% = low
            avg_gm = np.mean(gross_margins)

            if avg_gm >= 40:
                level_score = 100
            elif avg_gm >= 30:
                level_score = 70 + (avg_gm - 30) * 3  # Linear 70-100
            elif avg_gm >= 20:
                level_score = 40 + (avg_gm - 20) * 3  # Linear 40-70
            else:
                level_score = max(0, avg_gm * 2)  # Linear 0-40

            # === Component 2: Gross Margin Trend (30%) ===
            # Compare recent 4Q average vs older 4Q average
            if len(gross_margins) >= 8:
                recent_gm = np.mean(gross_margins[:4])  # Most recent 4Q
                older_gm = np.mean(gross_margins[4:8])  # Previous 4Q

                if older_gm > 0:
                    gm_change_pct = ((recent_gm - older_gm) / older_gm) * 100

                    # Expanding margins = good (pricing power)
                    if gm_change_pct >= 5:
                        trend_score = 100
                    elif gm_change_pct >= 0:
                        trend_score = 70 + (gm_change_pct * 6)  # Linear 70-100
                    elif gm_change_pct >= -5:
                        trend_score = 40 + ((gm_change_pct + 5) * 6)  # Linear 40-70
                    else:
                        trend_score = max(0, 40 + (gm_change_pct + 5) * 8)
                else:
                    trend_score = 50  # Neutral if can't calculate
            else:
                # Only have 4-7 quarters - use simple linear regression
                x = np.arange(len(gross_margins))
                slope, _ = np.polyfit(x, gross_margins, 1)

                # Slope > 0.5 = expanding, < -0.5 = declining
                if slope >= 0.5:
                    trend_score = 100
                elif slope >= 0:
                    trend_score = 70 + (slope * 60)
                elif slope >= -0.5:
                    trend_score = 40 + ((slope + 0.5) * 60)
                else:
                    trend_score = max(0, 40 + (slope + 0.5) * 80)

            # === Component 3: Gross Margin Stability (30%) ===
            # Lower CV = more consistent = better (pricing power)
            std_gm = np.std(gross_margins)
            cv_gm = std_gm / abs(avg_gm) if avg_gm != 0 else 1.0

            # CV < 0.05 = very stable, 0.05-0.15 = stable, 0.15-0.30 = moderate, >0.30 = volatile
            if cv_gm <= 0.05:
                stability_score = 100
            elif cv_gm <= 0.15:
                stability_score = 70 + (0.15 - cv_gm) * 300  # Linear 70-100
            elif cv_gm <= 0.30:
                stability_score = 40 + (0.30 - cv_gm) * 200  # Linear 40-70
            else:
                stability_score = max(0, 40 - (cv_gm - 0.30) * 100)

            # === Composite Pricing Power Score ===
            pricing_power = (
                level_score * 0.40 +
                trend_score * 0.30 +
                stability_score * 0.30
            )

            return round(pricing_power, 2)

        except Exception as e:
            logger.warning(f"Error calculating pricing power for {symbol}: {e}")
            return None

    def _calc_operating_leverage(self, income: List[Dict]) -> Optional[float]:
        """
        Calculate Operating Leverage Score (0-100) based on OI growth vs Revenue growth.

        Operating Leverage = Operating Income Growth / Revenue Growth

        Leverage > 1.5x = excellent (scale economies, strong moat)
        Leverage 1.0-1.5x = good (some operating leverage)
        Leverage 0.5-1.0x = average
        Leverage < 0.5x = poor (costs growing faster than revenue)
        """
        if not income or len(income) < 8:
            return None

        try:
            # Get 3-year CAGR for Operating Income and Revenue
            # Use quarterly data: Q0 (latest) vs Q12 (3 years ago)
            if len(income) < 12:
                # Use available data (at least 8 quarters = 2 years)
                recent = income[0]
                old = income[-1]
            else:
                recent = income[0]
                old = income[11]  # 12 quarters ago = 3 years

            recent_oi = recent.get('operatingIncome', 0)
            recent_rev = recent.get('revenue', 0)
            old_oi = old.get('operatingIncome', 0)
            old_rev = old.get('revenue', 0)

            if not all([recent_oi, recent_rev, old_oi, old_rev]) or old_oi <= 0 or old_rev <= 0:
                return None

            # Calculate growth rates
            oi_growth = ((recent_oi / old_oi) - 1) * 100
            rev_growth = ((recent_rev / old_rev) - 1) * 100

            # Operating leverage ratio
            if rev_growth > 1.0:  # Avoid division by near-zero
                leverage_ratio = oi_growth / rev_growth
            else:
                # If revenue is flat/declining but OI growing = excellent
                if oi_growth > 5:
                    leverage_ratio = 2.0  # Treat as excellent
                else:
                    return 50  # Neutral if both flat

            # Convert to score (0-100)
            if leverage_ratio >= 1.5:
                score = 100
            elif leverage_ratio >= 1.0:
                score = 70 + (leverage_ratio - 1.0) * 60  # Linear 70-100
            elif leverage_ratio >= 0.5:
                score = 40 + (leverage_ratio - 0.5) * 60  # Linear 40-70
            else:
                score = max(0, leverage_ratio * 80)  # Linear 0-40

            return round(score, 2)

        except Exception as e:
            logger.warning(f"Error calculating operating leverage: {e}")
            return None

    def _calc_roic_persistence(self, roic_quarterly: List[float]) -> Optional[float]:
        """
        Calculate ROIC Persistence Score (0-100) based on ROIC stability.

        Components:
        1. ROIC Level (50%) - Absolute ROIC% (higher is better)
        2. ROIC Stability (50%) - Consistency over 8 quarters (lower CV is better)

        High score = High, stable ROIC (durable competitive advantage)
        """
        if not roic_quarterly or len(roic_quarterly) < 4:
            return None

        try:
            # === Component 1: ROIC Level (50%) ===
            avg_roic = np.mean(roic_quarterly)

            # Benchmark: 25%+ = excellent, 15-25% = good, 10-15% = average, <10% = poor
            if avg_roic >= 25:
                level_score = 100
            elif avg_roic >= 15:
                level_score = 70 + (avg_roic - 15) * 3  # Linear 70-100
            elif avg_roic >= 10:
                level_score = 40 + (avg_roic - 10) * 6  # Linear 40-70
            else:
                level_score = max(0, avg_roic * 4)  # Linear 0-40

            # === Component 2: ROIC Stability (50%) ===
            # Lower CV = more consistent = better (durable moat)
            std_roic = np.std(roic_quarterly)
            cv_roic = std_roic / abs(avg_roic) if avg_roic != 0 else 1.0

            # CV < 0.10 = very stable, 0.10-0.25 = stable, 0.25-0.50 = moderate, >0.50 = volatile
            if cv_roic <= 0.10:
                stability_score = 100
            elif cv_roic <= 0.25:
                stability_score = 70 + (0.25 - cv_roic) * 200  # Linear 70-100
            elif cv_roic <= 0.50:
                stability_score = 40 + (0.50 - cv_roic) * 120  # Linear 40-70
            else:
                stability_score = max(0, 40 - (cv_roic - 0.50) * 80)

            # === Composite ROIC Persistence Score ===
            persistence = (
                level_score * 0.50 +
                stability_score * 0.50
            )

            return round(persistence, 2)

        except Exception as e:
            logger.warning(f"Error calculating ROIC persistence: {e}")
            return None

    def _calc_piotroski_delta(self, income: List[Dict], balance: List[Dict],
                              cashflow: List[Dict]) -> Tuple[Optional[int], Optional[int]]:
        """
        Calculate Piotroski F-Score and delta (change from 1 year ago).

        F-Score = 9 binary signals (0-9 total):
        - Profitability (4): ROA>0, CFO>0, ΔROA>0, Accrual<0
        - Leverage/Liquidity (3): ΔDebt<0, ΔCurrentRatio>0, NoEquityIssue
        - Operating Efficiency (2): ΔGrossMargin>0, ΔAssetTurnover>0

        Delta = F-Score(now) - F-Score(1Y ago)
        - Delta < 0: Quality deteriorating
        - Delta = 0: Quality stable
        - Delta > 0: Quality improving

        Returns: (fscore_current, fscore_delta)
        """
        if not income or not balance or not cashflow:
            return None, None

        if len(income) < 8 or len(balance) < 8 or len(cashflow) < 8:
            return None, None  # Need 2 years of data (8Q)

        try:
            # Calculate F-Score for current year (Q0-Q3)
            fscore_current = self._calc_fscore(
                income[:4], balance[:4], cashflow[:4],
                income[4:8], balance[4:8], cashflow[4:8]  # Previous year for deltas
            )

            # Calculate F-Score for 1 year ago (Q4-Q7)
            fscore_1y_ago = self._calc_fscore(
                income[4:8], balance[4:8], cashflow[4:8],
                income[8:12] if len(income) >= 12 else None,
                balance[8:12] if len(balance) >= 12 else None,
                cashflow[8:12] if len(cashflow) >= 12 else None
            )

            if fscore_current is not None and fscore_1y_ago is not None:
                delta = fscore_current - fscore_1y_ago
                return fscore_current, delta
            else:
                return fscore_current, None

        except Exception as e:
            logger.warning(f"Error calculating Piotroski delta: {e}")
            return None, None

    def _calc_fscore(self, income_current: List[Dict], balance_current: List[Dict],
                     cashflow_current: List[Dict],
                     income_prev: Optional[List[Dict]], balance_prev: Optional[List[Dict]],
                     cashflow_prev: Optional[List[Dict]]) -> Optional[int]:
        """
        Calculate Piotroski F-Score for a period.

        Returns score 0-9 (higher = better quality).
        """
        try:
            score = 0

            # Sum TTM values
            ni = sum(q.get('netIncome', 0) for q in income_current)
            assets = balance_current[0].get('totalAssets', 0)
            cfo = sum(q.get('operatingCashFlow', 0) for q in cashflow_current)
            revenue = sum(q.get('revenue', 0) for q in income_current)
            gross_profit = sum(q.get('grossProfit', 0) for q in income_current)

            # 1. ROA > 0 (Profitability)
            if assets and assets > 0:
                roa = ni / assets
                if roa > 0:
                    score += 1

                # 3. ΔROA > 0 (ROA improving)
                if income_prev and balance_prev:
                    ni_prev = sum(q.get('netIncome', 0) for q in income_prev)
                    assets_prev = balance_prev[0].get('totalAssets', 0)
                    if assets_prev and assets_prev > 0:
                        roa_prev = ni_prev / assets_prev
                        if roa > roa_prev:
                            score += 1

            # 2. CFO > 0 (Cash profitability)
            if cfo > 0:
                score += 1

            # 4. Accrual < 0 (CFO > Net Income = quality earnings)
            if cfo > ni:
                score += 1

            # 5. ΔDebt < 0 (Leverage decreasing)
            if balance_prev:
                debt = balance_current[0].get('totalDebt', 0)
                debt_prev = balance_prev[0].get('totalDebt', 0)
                if debt < debt_prev:
                    score += 1

            # 6. ΔCurrent Ratio > 0 (Liquidity improving)
            if balance_prev:
                current_assets = balance_current[0].get('totalCurrentAssets', 0)
                current_liab = balance_current[0].get('totalCurrentLiabilities', 0)
                current_assets_prev = balance_prev[0].get('totalCurrentAssets', 0)
                current_liab_prev = balance_prev[0].get('totalCurrentLiabilities', 0)

                if current_liab and current_liab > 0 and current_liab_prev and current_liab_prev > 0:
                    cr = current_assets / current_liab
                    cr_prev = current_assets_prev / current_liab_prev
                    if cr > cr_prev:
                        score += 1

            # 7. No new equity issued (Shares outstanding not increasing)
            if balance_prev:
                shares = balance_current[0].get('commonStock', 0)
                shares_prev = balance_prev[0].get('commonStock', 0)
                if shares <= shares_prev:
                    score += 1

            # 8. ΔGross Margin > 0 (Operating efficiency improving)
            if income_prev and revenue > 0:
                gm = (gross_profit / revenue) * 100
                revenue_prev = sum(q.get('revenue', 0) for q in income_prev)
                gross_profit_prev = sum(q.get('grossProfit', 0) for q in income_prev)
                if revenue_prev > 0:
                    gm_prev = (gross_profit_prev / revenue_prev) * 100
                    if gm > gm_prev:
                        score += 1

            # 9. ΔAsset Turnover > 0 (Asset productivity improving)
            if balance_prev and revenue > 0 and assets > 0:
                turnover = revenue / assets
                revenue_prev = sum(q.get('revenue', 0) for q in income_prev)
                assets_prev = balance_prev[0].get('totalAssets', 0)
                if assets_prev and assets_prev > 0:
                    turnover_prev = revenue_prev / assets_prev
                    if turnover > turnover_prev:
                        score += 1

            return score

        except Exception as e:
            logger.warning(f"Error calculating F-Score: {e}")
            return None

    def _calc_mohanram_delta(self, income: List[Dict], balance: List[Dict],
                              cashflow: List[Dict], price_to_book: Optional[float]) -> Tuple[Optional[int], Optional[int]]:
        """
        Calculate Mohanram G-Score and delta (for Growth stocks).

        G-Score = 8 binary signals (0-8 total):
        - Profitability (3): ROA>median, CFO>median, ROA variance low
        - Growth/Investment (3): R&D>0, Capex>avg, Revenue growth>avg
        - Efficiency (2): Accrual quality, Gross margin improving

        Delta = G-Score(now) - G-Score(1Y ago)
        - Delta < 0: Quality deteriorating
        - Delta = 0: Quality stable
        - Delta > 0: Quality improving

        Returns: (gscore_current, gscore_delta)
        """
        if not income or not balance or not cashflow:
            return None, None

        if len(income) < 8 or len(balance) < 8 or len(cashflow) < 8:
            return None, None  # Need 2 years of data

        try:
            # Calculate G-Score for current year (Q0-Q3)
            gscore_current = self._calc_gscore(
                income[:4], balance[:4], cashflow[:4],
                income[4:8], balance[4:8], cashflow[4:8]
            )

            # Calculate G-Score for 1 year ago (Q4-Q7)
            gscore_1y_ago = self._calc_gscore(
                income[4:8], balance[4:8], cashflow[4:8],
                income[8:12] if len(income) >= 12 else None,
                balance[8:12] if len(balance) >= 12 else None,
                cashflow[8:12] if len(cashflow) >= 12 else None
            )

            if gscore_current is not None and gscore_1y_ago is not None:
                delta = gscore_current - gscore_1y_ago
                return gscore_current, delta
            else:
                return gscore_current, None

        except Exception as e:
            logger.warning(f"Error calculating Mohanram delta: {e}")
            return None, None

    def _calc_gscore(self, income_current: List[Dict], balance_current: List[Dict],
                     cashflow_current: List[Dict],
                     income_prev: Optional[List[Dict]], balance_prev: Optional[List[Dict]],
                     cashflow_prev: Optional[List[Dict]]) -> Optional[int]:
        """
        Calculate Mohanram G-Score for a period (Growth stocks).

        Returns score 0-8 (higher = better quality for growth).
        """
        try:
            score = 0

            # Sum TTM values
            ni = sum(q.get('netIncome', 0) for q in income_current)
            assets = balance_current[0].get('totalAssets', 0)
            cfo = sum(q.get('operatingCashFlow', 0) for q in cashflow_current)
            revenue = sum(q.get('revenue', 0) for q in income_current)
            gross_profit = sum(q.get('grossProfit', 0) for q in income_current)

            # === Profitability Signals (3) ===

            # 1. ROA > benchmark (15% for growth)
            if assets and assets > 0:
                roa = (ni / assets) * 100
                if roa > 15:  # Growth benchmark
                    score += 1

            # 2. CFO/Assets > benchmark (10%)
            if assets and assets > 0:
                cfo_ratio = (cfo / assets) * 100
                if cfo_ratio > 10:
                    score += 1

            # 3. ROA variability low (if have history)
            if income_prev and balance_prev and len(income_current) >= 4:
                # Calculate ROA for last 4Q
                roa_quarters = []
                for i in range(4):
                    ni_q = income_current[i].get('netIncome', 0)
                    assets_q = balance_current[i].get('totalAssets', 0) if i < len(balance_current) else 0
                    if assets_q and assets_q > 0:
                        roa_quarters.append((ni_q / assets_q) * 100)

                if len(roa_quarters) >= 3:
                    cv_roa = np.std(roa_quarters) / abs(np.mean(roa_quarters)) if np.mean(roa_quarters) != 0 else 99
                    if cv_roa < 0.15:  # Low variability = stable
                        score += 1

            # === Growth/Investment Signals (3) ===

            # 4. R&D intensity (R&D/Sales > 0)
            rd_expense = sum(q.get('researchAndDevelopmentExpenses', 0) for q in income_current)
            if rd_expense and revenue and revenue > 0:
                rd_ratio = (rd_expense / revenue) * 100
                if rd_ratio > 5:  # Significant R&D investment
                    score += 1

            # 5. Capex intensity (Capex/Sales > 5%)
            capex = sum(q.get('capitalExpenditure', 0) for q in cashflow_current)
            if capex and revenue and revenue > 0:
                capex_ratio = (abs(capex) / revenue) * 100  # Capex usually negative
                if capex_ratio > 5:  # Investing in growth
                    score += 1

            # 6. Revenue growth > 10% (strong growth)
            if income_prev and revenue > 0:
                revenue_prev = sum(q.get('revenue', 0) for q in income_prev)
                if revenue_prev and revenue_prev > 0:
                    rev_growth = ((revenue / revenue_prev) - 1) * 100
                    if rev_growth > 10:  # Double-digit growth
                        score += 1

            # === Efficiency Signals (2) ===

            # 7. Accrual quality (CFO > NI = quality earnings)
            if cfo > ni:
                score += 1

            # 8. Gross margin improving
            if income_prev and revenue > 0:
                gm = (gross_profit / revenue) * 100
                revenue_prev = sum(q.get('revenue', 0) for q in income_prev)
                gross_profit_prev = sum(q.get('grossProfit', 0) for q in income_prev)
                if revenue_prev > 0:
                    gm_prev = (gross_profit_prev / revenue_prev) * 100
                    if gm > gm_prev:  # Margin expansion
                        score += 1

            return score

        except Exception as e:
            logger.warning(f"Error calculating G-Score: {e}")
            return None
