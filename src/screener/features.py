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
            company_type: 'non_financial', 'financial', or 'reit'

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
            income = self.fmp.get_income_statement(symbol, period='quarter', limit=4)
            balance = self.fmp.get_balance_sheet(symbol, period='quarter', limit=4)
            cashflow = self.fmp.get_cash_flow(symbol, period='quarter', limit=4)

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

        # === VALUE METRICS (Modern Yields) ===
        # Using yields (inverted multiples) per Greenblatt, Novy-Marx research
        # Higher yields = better value

        # Calculate base components
        market_cap = prof.get('mktCap') or met.get('marketCap')
        ebit_ttm = self._sum_ttm(income, 'operatingIncome')
        ebitda_ttm = self._sum_ttm(income, 'ebitda')
        total_debt = bal.get('totalDebt', 0)
        cash = bal.get('cashAndCashEquivalents', 0)
        ev = market_cap + total_debt - cash if market_cap else None

        # Free Cash Flow & Operating Cash Flow (TTM)
        fcf_ttm = self._sum_ttm(cashflow, 'freeCashFlow')
        cfo_ttm = self._sum_ttm(cashflow, 'operatingCashFlow')
        capex_ttm = abs(self._sum_ttm(cashflow, 'capitalExpenditure'))  # Usually negative

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

        # 4. Gross Profit Yield = Gross Profit / EV (Novy-Marx)
        gross_profit_ttm = self._sum_ttm(income, 'grossProfit')
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

        # Gross Profits / Assets (Novy-Marx)
        gross_profit_ttm = self._sum_ttm(income, 'grossProfit')
        if gross_profit_ttm and total_assets and total_assets > 0:
            features['grossProfits_to_assets'] = (gross_profit_ttm / total_assets) * 100
        else:
            features['grossProfits_to_assets'] = None

        # FCF Margin % = FCF / Revenue
        revenue_ttm = self._sum_ttm(income, 'revenue')
        if fcf_ttm and revenue_ttm and revenue_ttm > 0:
            features['fcf_margin_%'] = (fcf_ttm / revenue_ttm) * 100
        else:
            features['fcf_margin_%'] = None

        # CFO / Net Income
        cfo_ttm = self._sum_ttm(cashflow, 'operatingCashFlow')
        ni_ttm = self._sum_ttm(income, 'netIncome')
        if cfo_ttm and ni_ttm and ni_ttm != 0:
            features['cfo_to_ni'] = cfo_ttm / ni_ttm
        else:
            features['cfo_to_ni'] = None

        # Net Debt / EBITDA
        ebitda_ttm = self._sum_ttm(income, 'ebitda')
        net_debt = total_debt - cash if total_debt is not None and cash is not None else None
        if net_debt is not None and ebitda_ttm and ebitda_ttm > 0:
            features['netDebt_ebitda'] = net_debt / ebitda_ttm
        else:
            features['netDebt_ebitda'] = None

        # Interest Coverage = EBIT / Interest Expense
        interest_ttm = self._sum_ttm(income, 'interestExpense')
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
