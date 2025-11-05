"""
Guardrails: Accounting quality and financial health checks.
- Altman Z-Score (bankruptcy risk)
- Beneish M-Score (earnings manipulation)
- Accruals / NOA (earnings quality)
- Net Share Issuance (dilution)
- Debt maturity & rate mix
- M&A flag (goodwill/intangibles growth)
"""
import logging
import numpy as np
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class GuardrailCalculator:
    """
    Calculate accounting guardrails to flag potential issues:
    - Altman Z-Score (non-financials only)
    - Beneish M-Score (all)
    - Accruals / NOA (non-financials)
    - Dilution (all)
    - Debt metrics (all)
    - M&A flag (all)
    """

    def __init__(self, fmp_client, config: Dict):
        self.fmp = fmp_client
        self.config = config

    def calculate_guardrails(
        self,
        symbol: str,
        company_type: str,
        industry: str
    ) -> Dict:
        """
        Calculate all guardrails for a symbol.

        Returns:
            {
                'altmanZ': float,
                'beneishM': float,
                'accruals_noa_%': float,
                'netShareIssuance_12m_%': float,
                'mna_flag': str,
                'debt_maturity_<24m_%': float,
                'rate_mix_variable_%': float,
                'guardrail_status': 'VERDE|AMBAR|ROJO',
                'guardrail_reasons': str
            }
        """
        result = {
            'altmanZ': None,
            'beneishM': None,
            'accruals_noa_%': None,
            'netShareIssuance_12m_%': None,
            'mna_flag': None,
            'debt_maturity_<24m_%': None,
            'rate_mix_variable_%': None,
            'guardrail_status': 'VERDE',
            'guardrail_reasons': ''
        }

        try:
            # Fetch data
            income = self.fmp.get_income_statement(symbol, period='quarter', limit=8)
            balance = self.fmp.get_balance_sheet(symbol, period='quarter', limit=8)
            cashflow = self.fmp.get_cash_flow(symbol, period='quarter', limit=8)

            if not income or not balance or not cashflow:
                result['guardrail_status'] = 'AMBAR'
                result['guardrail_reasons'] = 'Insufficient data'
                return result

            # Calculate each guardrail
            if company_type == 'non_financial':
                result['altmanZ'] = self._calc_altman_z(balance, income, cashflow)
                result['accruals_noa_%'] = self._calc_accruals_noa(balance, income, cashflow)

            result['beneishM'] = self._calc_beneish_m(balance, income, cashflow)
            result['netShareIssuance_12m_%'] = self._calc_net_share_issuance(balance, cashflow)
            result['mna_flag'] = self._calc_mna_flag(balance)

            # Debt metrics (if available)
            # Note: debt maturity and rate mix require detailed debt schedules (often not in API)
            result['debt_maturity_<24m_%'] = None  # Placeholder
            result['rate_mix_variable_%'] = None  # Placeholder

            # Determine status and reasons
            result['guardrail_status'], result['guardrail_reasons'] = self._assess_guardrails(
                result, company_type, industry
            )

        except Exception as e:
            logger.error(f"Error calculating guardrails for {symbol}: {e}")
            result['guardrail_status'] = 'AMBAR'
            result['guardrail_reasons'] = f'Error: {str(e)[:50]}'

        return result

    # ===========================
    # Altman Z-Score
    # ===========================

    def _calc_altman_z(
        self,
        balance: List[Dict],
        income: List[Dict],
        cashflow: List[Dict]
    ) -> Optional[float]:
        """
        Altman Z-Score for public manufacturing companies:

        Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5

        Where:
        X1 = Working Capital / Total Assets
        X2 = Retained Earnings / Total Assets
        X3 = EBIT / Total Assets
        X4 = Market Value of Equity / Total Liabilities
        X5 = Sales / Total Assets

        Interpretation:
        Z > 2.99: Safe
        1.81 - 2.99: Gray zone
        Z < 1.81: Distress zone

        For service/non-manufacturing: use Altman Z'' variant (different coefficients)
        """
        if not balance or not income:
            return None

        bal = balance[0]
        inc = income[0]

        # Extract components
        current_assets = bal.get('totalCurrentAssets', 0)
        current_liab = bal.get('totalCurrentLiabilities', 0)
        total_assets = bal.get('totalAssets', 0)
        retained_earnings = bal.get('retainedEarnings', 0)
        ebit = inc.get('operatingIncome', 0)  # EBIT proxy
        total_liab = bal.get('totalLiabilities', 0)
        revenue = inc.get('revenue', 0)

        # Market cap (approximate from balance sheet equity + market premium)
        equity_book = bal.get('totalStockholdersEquity', 0)
        # Ideally get market cap from profile, but for Z-score we can use book as proxy
        market_value_equity = equity_book  # Conservative (uses book value)

        if not total_assets or total_assets == 0:
            return None

        # Calculate ratios
        x1 = (current_assets - current_liab) / total_assets  # Working Capital / TA
        x2 = retained_earnings / total_assets
        x3 = ebit / total_assets
        x4 = market_value_equity / total_liab if total_liab > 0 else 0
        x5 = revenue / total_assets

        # Altman Z (original public manufacturing)
        z_score = 1.2*x1 + 1.4*x2 + 3.3*x3 + 0.6*x4 + 1.0*x5

        return z_score

    # ===========================
    # Beneish M-Score
    # ===========================

    def _calc_beneish_m(
        self,
        balance: List[Dict],
        income: List[Dict],
        cashflow: List[Dict]
    ) -> Optional[float]:
        """
        Beneish M-Score: detects earnings manipulation.

        M-Score = -4.84 + 0.920*DSRI + 0.528*GMI + 0.404*AQI + 0.892*SGI
                  + 0.115*DEPI - 0.172*SGAI + 4.679*TATA - 0.327*LVGI

        Where:
        DSRI = Days Sales in Receivables Index = (Receivables_t / Sales_t) / (Receivables_t-1 / Sales_t-1)
        GMI  = Gross Margin Index = GM_t-1 / GM_t
        AQI  = Asset Quality Index = [1 - (CA + PPE) / TA]_t / [1 - (CA + PPE) / TA]_t-1
        SGI  = Sales Growth Index = Sales_t / Sales_t-1
        DEPI = Depreciation Index = (Depr_t-1 / (PPE_t-1 + Depr_t-1)) / (Depr_t / (PPE_t + Depr_t))
        SGAI = SG&A Index = (SG&A_t / Sales_t) / (SG&A_t-1 / Sales_t-1)
        TATA = Total Accruals to Total Assets = (Income - CFO - CFI) / TA
        LVGI = Leverage Index = (TL_t / TA_t) / (TL_t-1 / TA_t-1)

        Interpretation:
        M > -1.78: High likelihood of manipulation (RED flag)
        M < -2.22: Low likelihood
        """
        if len(balance) < 2 or len(income) < 2 or len(cashflow) < 2:
            return None

        # Current period (t)
        bal_t = balance[0]
        inc_t = income[0]
        cf_t = cashflow[0]

        # Prior period (t-1) - use 4 quarters ago for YoY comparison
        bal_t1 = balance[4] if len(balance) > 4 else balance[-1]
        inc_t1 = income[4] if len(income) > 4 else income[-1]
        cf_t1 = cashflow[4] if len(cashflow) > 4 else cashflow[-1]

        try:
            # Extract values
            receivables_t = bal_t.get('netReceivables', 0)
            receivables_t1 = bal_t1.get('netReceivables', 0)
            sales_t = inc_t.get('revenue', 1)
            sales_t1 = inc_t1.get('revenue', 1)

            gross_profit_t = inc_t.get('grossProfit', 0)
            gross_profit_t1 = inc_t1.get('grossProfit', 0)
            gm_t = gross_profit_t / sales_t if sales_t > 0 else 0
            gm_t1 = gross_profit_t1 / sales_t1 if sales_t1 > 0 else 0

            current_assets_t = bal_t.get('totalCurrentAssets', 0)
            current_assets_t1 = bal_t1.get('totalCurrentAssets', 0)
            ppe_t = bal_t.get('propertyPlantEquipmentNet', 0)
            ppe_t1 = bal_t1.get('propertyPlantEquipmentNet', 0)
            total_assets_t = bal_t.get('totalAssets', 1)
            total_assets_t1 = bal_t1.get('totalAssets', 1)

            # Depreciation (from cash flow statement)
            depr_t = cf_t.get('depreciationAndAmortization', 0)
            depr_t1 = cf_t1.get('depreciationAndAmortization', 0)

            # SG&A (use operating expenses as proxy if not available)
            sga_t = inc_t.get('sellingGeneralAndAdministrativeExpenses') or inc_t.get('operatingExpenses', 0)
            sga_t1 = inc_t1.get('sellingGeneralAndAdministrativeExpenses') or inc_t1.get('operatingExpenses', 0)

            # Net income and cash flows
            ni_t = inc_t.get('netIncome', 0)
            cfo_t = cf_t.get('operatingCashFlow', 0)
            cfi_t = cf_t.get('capitalExpenditure', 0)  # Usually negative

            total_liab_t = bal_t.get('totalLiabilities', 0)
            total_liab_t1 = bal_t1.get('totalLiabilities', 0)

            # Calculate indices
            dsri = (receivables_t / sales_t) / (receivables_t1 / sales_t1) if receivables_t1 > 0 and sales_t1 > 0 else 1.0
            gmi = gm_t1 / gm_t if gm_t > 0 else 1.0

            aq_t = 1 - (current_assets_t + ppe_t) / total_assets_t if total_assets_t > 0 else 0
            aq_t1 = 1 - (current_assets_t1 + ppe_t1) / total_assets_t1 if total_assets_t1 > 0 else 0
            aqi = aq_t / aq_t1 if aq_t1 != 0 else 1.0

            sgi = sales_t / sales_t1 if sales_t1 > 0 else 1.0

            depr_rate_t = depr_t / (ppe_t + depr_t) if (ppe_t + depr_t) > 0 else 0
            depr_rate_t1 = depr_t1 / (ppe_t1 + depr_t1) if (ppe_t1 + depr_t1) > 0 else 0
            depi = depr_rate_t1 / depr_rate_t if depr_rate_t > 0 else 1.0

            sgai = (sga_t / sales_t) / (sga_t1 / sales_t1) if sga_t1 > 0 and sales_t1 > 0 else 1.0

            # TATA = (NI - CFO - CFI) / TA (approximation)
            tata = (ni_t - cfo_t - cfi_t) / total_assets_t if total_assets_t > 0 else 0

            lvgi = (total_liab_t / total_assets_t) / (total_liab_t1 / total_assets_t1) if total_liab_t1 > 0 and total_assets_t1 > 0 else 1.0

            # Beneish M-Score
            m_score = (
                -4.84
                + 0.920 * dsri
                + 0.528 * gmi
                + 0.404 * aqi
                + 0.892 * sgi
                + 0.115 * depi
                - 0.172 * sgai
                + 4.679 * tata
                - 0.327 * lvgi
            )

            return m_score

        except Exception as e:
            logger.warning(f"Beneish M-Score calculation error: {e}")
            return None

    # ===========================
    # Accruals / NOA
    # ===========================

    def _calc_accruals_noa(
        self,
        balance: List[Dict],
        income: List[Dict],
        cashflow: List[Dict]
    ) -> Optional[float]:
        """
        Accruals / NOA (Sloan 1996):

        Accruals = ΔCA - ΔCash - ΔCL + ΔSTD + ΔTP - Depreciation
        NOA = Operating Assets - Operating Liabilities
            = (Total Assets - Cash) - (Total Liabilities - Total Debt)

        Accruals / NOA: High accruals relative to net operating assets
        can indicate lower earnings quality.

        Returns: Accruals as % of NOA
        """
        if len(balance) < 2 or len(income) < 2 or len(cashflow) < 2:
            return None

        bal_t = balance[0]
        bal_t1 = balance[1]
        inc_t = income[0]
        cf_t = cashflow[0]

        try:
            # Changes in balance sheet items
            ca_t = bal_t.get('totalCurrentAssets', 0)
            ca_t1 = bal_t1.get('totalCurrentAssets', 0)
            delta_ca = ca_t - ca_t1

            cash_t = bal_t.get('cashAndCashEquivalents', 0)
            cash_t1 = bal_t1.get('cashAndCashEquivalents', 0)
            delta_cash = cash_t - cash_t1

            cl_t = bal_t.get('totalCurrentLiabilities', 0)
            cl_t1 = bal_t1.get('totalCurrentLiabilities', 0)
            delta_cl = cl_t - cl_t1

            # Short-term debt and tax payable
            std_t = bal_t.get('shortTermDebt', 0)
            std_t1 = bal_t1.get('shortTermDebt', 0)
            delta_std = std_t - std_t1

            tp_t = bal_t.get('taxPayables', 0)
            tp_t1 = bal_t1.get('taxPayables', 0)
            delta_tp = tp_t - tp_t1

            # Depreciation
            depreciation = cf_t.get('depreciationAndAmortization', 0)

            # Accruals calculation
            accruals = delta_ca - delta_cash - delta_cl + delta_std + delta_tp - depreciation

            # NOA
            total_assets = bal_t.get('totalAssets', 0)
            total_liabilities = bal_t.get('totalLiabilities', 0)
            total_debt = bal_t.get('totalDebt', 0)

            noa = (total_assets - cash_t) - (total_liabilities - total_debt)

            if noa > 0:
                accruals_pct = (accruals / noa) * 100
                return accruals_pct
            else:
                return None

        except Exception as e:
            logger.warning(f"Accruals/NOA calculation error: {e}")
            return None

    # ===========================
    # Net Share Issuance
    # ===========================

    def _calc_net_share_issuance(
        self,
        balance: List[Dict],
        cashflow: List[Dict]
    ) -> Optional[float]:
        """
        Net Share Issuance % over last 12 months:

        Method 1: (Shares_t - Shares_t-4) / Shares_t-4 * 100
        Method 2: (Stock Issued - Stock Repurchased) / Market Cap * 100

        Returns: % change (positive = dilution, negative = buybacks)
        """
        if len(balance) < 5:
            return None

        # Method 1: Share count change
        shares_t = balance[0].get('commonStock') or balance[0].get('weightedAverageShsOut')
        shares_t4 = balance[4].get('commonStock') or balance[4].get('weightedAverageShsOut')

        if shares_t and shares_t4 and shares_t4 > 0:
            net_issuance_pct = ((shares_t - shares_t4) / shares_t4) * 100
            return net_issuance_pct

        # Method 2: Cash flow from financing
        if cashflow:
            cf = cashflow[0]
            stock_issued = cf.get('commonStockIssued', 0)
            stock_repurchased = cf.get('commonStockRepurchased', 0)  # Usually negative

            # Approximate market cap from balance sheet equity
            equity = balance[0].get('totalStockholdersEquity', 1)
            net_flow = stock_issued + stock_repurchased  # repurchased is negative
            if equity > 0:
                return (net_flow / equity) * 100

        return None

    # ===========================
    # M&A Flag
    # ===========================

    def _calc_mna_flag(self, balance: List[Dict]) -> Optional[str]:
        """
        M&A Flag: detect if company has been actively acquiring (stock-financed).

        Heuristic:
        - High goodwill/intangibles growth over 4 quarters
        - Goodwill + Intangibles > 30% of total assets

        Returns: 'HIGH', 'MODERATE', 'LOW', or None
        """
        if len(balance) < 5:
            return None

        bal_t = balance[0]
        bal_t4 = balance[4]

        goodwill_t = bal_t.get('goodwill', 0)
        intangibles_t = bal_t.get('intangibleAssets', 0)
        goodwill_t4 = bal_t4.get('goodwill', 0)
        intangibles_t4 = bal_t4.get('intangibleAssets', 0)

        total_assets = bal_t.get('totalAssets', 1)

        # Growth in goodwill + intangibles
        gi_t = goodwill_t + intangibles_t
        gi_t4 = goodwill_t4 + intangibles_t4

        if gi_t4 > 0:
            growth_pct = ((gi_t - gi_t4) / gi_t4) * 100
        else:
            growth_pct = 0

        # Ratio to assets
        gi_ratio = (gi_t / total_assets) * 100 if total_assets > 0 else 0

        # Classify
        if growth_pct > 20 and gi_ratio > 30:
            return 'HIGH'
        elif growth_pct > 10 or gi_ratio > 20:
            return 'MODERATE'
        else:
            return 'LOW'

    # ===========================
    # Assessment
    # ===========================

    def _assess_guardrails(
        self,
        guardrails: Dict,
        company_type: str,
        industry: str
    ) -> Tuple[str, str]:
        """
        Assess overall guardrail status (VERDE, AMBAR, ROJO) and reasons.

        Returns: (status, reasons_string)
        """
        reasons = []
        red_flags = 0
        amber_flags = 0

        thresholds = self.config.get('guardrails', {})

        if company_type == 'non_financial':
            cfg = thresholds.get('non_financial', {})

            # Altman Z
            z = guardrails.get('altmanZ')
            if z is not None:
                if z < cfg.get('altman_z_red', 1.8):
                    red_flags += 1
                    reasons.append(f"Altman Z={z:.2f} <1.8 (distress)")
                elif z < cfg.get('altman_z_amber', 2.99):
                    amber_flags += 1
                    reasons.append(f"Altman Z={z:.2f} gray zone")

            # Accruals
            accruals = guardrails.get('accruals_noa_%')
            if accruals is not None:
                # Would need industry distribution to compute percentile
                # Simplified: flag if > 15%
                if accruals > 15:
                    amber_flags += 1
                    reasons.append(f"Accruals/NOA={accruals:.1f}% high")

            # Interest Coverage
            # (Not directly in guardrails dict; would come from features)
            # Placeholder for now

            # Net Debt/EBITDA
            # (Also from features; placeholder)

        elif company_type == 'financial':
            cfg = thresholds.get('financial', {})
            # CET1, efficiency ratio, L/D (from features)
            # Placeholder

        elif company_type == 'reit':
            cfg = thresholds.get('reit', {})
            # FFO payout, occupancy, debt/assets (from features)
            # Placeholder

        # Beneish M-Score (all types)
        m = guardrails.get('beneishM')
        if m is not None:
            if m > -1.78:
                red_flags += 1
                reasons.append(f"Beneish M={m:.2f} >-1.78 (manip.?)")
            elif m > -2.22:
                amber_flags += 1
                reasons.append(f"Beneish M={m:.2f} borderline")

        # Net Share Issuance (all types)
        dilution = guardrails.get('netShareIssuance_12m_%')
        if dilution is not None:
            if dilution > 10:
                red_flags += 1
                reasons.append(f"Dilution={dilution:.1f}% >10%")
            elif dilution > 5:
                amber_flags += 1
                reasons.append(f"Dilution={dilution:.1f}% >5%")

        # M&A Flag
        mna = guardrails.get('mna_flag')
        if mna == 'HIGH':
            amber_flags += 1
            reasons.append("High M&A / goodwill growth")

        # Determine status
        if red_flags > 0:
            status = 'ROJO'
        elif amber_flags > 0:
            status = 'AMBAR'
        else:
            status = 'VERDE'

        if not reasons:
            reasons.append("All checks OK")

        return status, '; '.join(reasons[:3])  # Limit to 3 reasons
