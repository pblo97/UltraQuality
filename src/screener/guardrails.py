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
            # Fetch data (need 12 quarters for revenue growth trend)
            income = self.fmp.get_income_statement(symbol, period='quarter', limit=12)
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

            # Calculate revenue growth (3-year CAGR) for declining business detection
            result['revenue_growth_3y'] = self._calc_revenue_growth_3y(income)

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

            # Require meaningful NOA to avoid division by small numbers
            # NOA should be at least 10% of total assets for meaningful ratio
            min_noa = total_assets * 0.1

            if noa > min_noa:
                accruals_pct = (accruals / noa) * 100

                # Cap at ±100% to handle edge cases and outliers
                # Accruals >100% of NOA is extremely rare and likely data error
                accruals_pct = max(-100, min(100, accruals_pct))

                return accruals_pct
            else:
                # NOA too small or negative - ratio not meaningful
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

        Method 1: (Shares_t - Shares_t-2) / Shares_t-2 * 100 * 2 (annualized from 6mo)
        Method 2: (Stock Issued - Stock Repurchased) / Equity * 100

        Returns: % change (positive = dilution, negative = buybacks)

        FIXED v2:
        - Use 2-quarter comparison (more reliable than 4-quarter)
        - Detect stock splits (45-55%, 90-110%, etc.)
        - Cross-validate with cash flow method
        - Cap at ±50% (values >50% likely data errors or splits)
        """
        if len(balance) < 3:
            return None

        # Method 1: Share count change (2 quarters = 6 months)
        # IMPORTANT: Use weightedAverageShsOut or commonStockSharesOutstanding
        # DO NOT use 'commonStock' (that's par value, not share count)
        shares_t = (balance[0].get('weightedAverageShsOut') or
                    balance[0].get('commonStockSharesOutstanding') or
                    balance[0].get('weightedAverageShsOutDil'))

        # Use 2-quarter lookback (more reliable than 4-quarter)
        shares_t2 = (balance[2].get('weightedAverageShsOut') or
                     balance[2].get('commonStockSharesOutstanding') or
                     balance[2].get('weightedAverageShsOutDil'))

        method1_result = None
        if shares_t and shares_t2 and shares_t2 > 0:
            # 6-month change
            six_month_pct = ((shares_t - shares_t2) / shares_t2) * 100

            # Annualize (multiply by 2 for 12-month estimate)
            net_issuance_pct = six_month_pct * 2

            # Stock split detection: If close to 50%, 100%, 200%, likely a split
            # Splits should be adjusted by FMP but sometimes aren't
            abs_pct = abs(net_issuance_pct)
            is_likely_split = (
                (45 <= abs_pct <= 55) or    # 3:2 or 2:3 split
                (90 <= abs_pct <= 110) or   # 2:1 or 1:2 split
                (190 <= abs_pct <= 210) or  # 3:1 split
                (290 <= abs_pct <= 310)     # 4:1 split
            )

            if is_likely_split:
                # Likely a stock split, not actual dilution - ignore
                logger.debug(f"Detected potential stock split: {net_issuance_pct:.1f}% change")
                net_issuance_pct = 0.0

            # Cap at ±50% (values >50% after split detection are likely data errors)
            net_issuance_pct = max(-50, min(50, net_issuance_pct))
            method1_result = net_issuance_pct

        # Method 2: Cash flow from financing (validation)
        method2_result = None
        if cashflow and len(cashflow) >= 4:
            # Sum last 4 quarters for annual figure
            total_issued = sum(cf.get('commonStockIssued', 0) for cf in cashflow[:4])
            total_repurchased = sum(cf.get('commonStockRepurchased', 0) for cf in cashflow[:4])

            equity = balance[0].get('totalStockholdersEquity', 1)
            net_flow = total_issued + total_repurchased  # repurchased is negative

            if equity > 0 and abs(net_flow) > 0:
                dilution = (net_flow / equity) * 100
                # Cap at ±50%
                dilution = max(-50, min(50, dilution))
                method2_result = dilution

        # Cross-validation: If both methods available and disagree significantly, prefer Method 2
        if method1_result is not None and method2_result is not None:
            disagreement = abs(method1_result - method2_result)
            if disagreement > 20:
                # Methods disagree by >20pp - likely data quality issue
                # Prefer cash flow method (more reliable)
                logger.debug(f"Dilution methods disagree: M1={method1_result:.1f}%, M2={method2_result:.1f}% - using M2")
                return method2_result
            else:
                # Methods agree - use Method 1 (more precise)
                return method1_result

        # Return whichever method succeeded
        return method1_result if method1_result is not None else method2_result

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

    def _is_altman_z_applicable(self, industry: str, company_type: str) -> bool:
        """
        Determine if Altman Z-Score is applicable for this industry.

        Altman Z-Score was designed in 1968 for manufacturing companies.
        It does NOT apply well to:

        1. Asset-light businesses (Software, SaaS, Internet)
           - Low working capital by design
           - Intangibles not counted in Z-Score formula
           - High growth = low retained earnings initially

        2. Regulated utilities
           - Capital structure dictated by regulators
           - High debt is normal/expected
           - Rate base coverage is better metric

        3. Service businesses with operating leases (post-ASC 842)
           - Restaurants, Hotels, Airlines, Retail
           - Operating leases now on balance sheet = appears high debt
           - Lease-adjusted metrics are better

        4. Financial services
           - Completely different business model
           - Use different metrics (CET1, leverage ratio, etc.)

        Returns: True if Z-Score applicable, False if should skip
        """
        if not industry:
            return True  # Default to applicable if unknown

        # Financial services - use different metrics entirely
        if company_type in ['financial', 'reit']:
            return False

        industry_lower = industry.lower()

        # Asset-light businesses (Software, SaaS, Internet)
        asset_light_keywords = [
            'software', 'saas', 'application', 'infrastructure',
            'information technology', 'internet', 'content',
            'electronic gaming', 'multimedia', 'social media',
            'data & stock exchanges', 'data processing'
        ]

        for keyword in asset_light_keywords:
            if keyword in industry_lower:
                return False

        # Regulated utilities
        utility_keywords = [
            'regulated electric', 'gas utility', 'water utility',
            'electric utility', 'multi-utilities', 'utility'
        ]

        for keyword in utility_keywords:
            if keyword in industry_lower:
                return False

        # Service businesses with operating leases
        operating_lease_keywords = [
            'restaurants', 'hotel', 'lodging', 'resort',
            'airlines', 'airport', 'cruise',
            'rental', 'leasing',
            'retail', 'department store', 'specialty retail',
            'apparel retail', 'discount store'
        ]

        for keyword in operating_lease_keywords:
            if keyword in industry_lower:
                return False

        # Semiconductors and chip manufacturers (capital intensive but different model)
        semiconductor_keywords = [
            'semiconductor', 'chip', 'integrated circuit'
        ]

        for keyword in semiconductor_keywords:
            if keyword in industry_lower:
                return False

        # For all other industries, Z-Score is applicable
        return True

    def _get_beneish_threshold_for_industry(self, industry: str) -> float:
        """
        Get industry-adjusted Beneish M-Score threshold for ROJO classification.

        Academic Foundation:
        - Beneish (1999): Original threshold -2.22 for manipulation detection
        - Omar et al. (2014): Industries with complex revenue recognition have naturally higher M-Scores
        - Repousis (2016): Suggests sector-specific adjustments to reduce false positives
        - Tarjo & Herawati (2015): High-accrual industries require adjusted thresholds

        Threshold Tiers:

        Tier 1 - PERMISSIVE (-1.5): Complex revenue recognition, naturally high accruals
            - Travel/Hospitality: Booking vs. consumption timing, deferred revenue
            - E-commerce/Retail: High receivables, inventory accounting complexity
            - Software/SaaS: Deferred revenue, R&D capitalization
            - Construction: Percentage-of-completion accounting
            - Healthcare/Biotech: R&D capitalization, clinical trial expenses

        Tier 2 - MODERATE (-1.78): Standard accounting practices
            - Industrials/Manufacturing: Traditional accounting
            - Consumer Goods: Standard inventory/revenue recognition
            - Telecommunications/Media: Regulated but complex
            - Energy/Materials: Commodity accounting
            - Real Estate (non-REIT): Property accounting

        Tier 3 - STRICT (-2.0): Highly regulated/standardized accounting
            - Financial Services: GAAP-regulated, accruals well-defined
            - Insurance: Regulated reserves and claims accounting
            - REITs: Standardized FFO/AFFO reporting
            - Utilities: Rate-regulated, stable accounting

        Returns: threshold (lower = more strict, higher = more permissive)
        """
        if not industry:
            return -1.78  # Default to original Beneish threshold

        industry_lower = industry.lower()

        # Tier 1: PERMISSIVE (-1.5) - Complex revenue recognition
        permissive_keywords = [
            'travel', 'hospitality', 'hotel', 'airline', 'cruise', 'leisure', 'resort',
            'ecommerce', 'retail', 'consumer cyclical', 'apparel', 'department store',
            'software', 'saas', 'technology', 'internet', 'information technology',
            'construction', 'engineering', 'contractor', 'infrastructure',
            'healthcare', 'biotechnology', 'pharmaceutical', 'medical', 'biotech',
            'entertainment', 'gaming', 'media production',
            'semiconductor', 'chip', 'integrated circuit',  # High R&D/Capex creates accruals
            'computer hardware', 'hardware equipment', 'communication equipment'  # Capital intensive
        ]

        for keyword in permissive_keywords:
            if keyword in industry_lower:
                return -1.5  # More permissive for complex accounting models

        # Tier 3: STRICT (-2.0) - Regulated accounting
        strict_keywords = [
            'bank', 'financial services', 'insurance', 'asset management',
            'reit', 'real estate investment',
            'utility', 'electric', 'gas utility', 'water utility'
        ]

        for keyword in strict_keywords:
            if keyword in industry_lower:
                return -2.0  # More strict for regulated industries

        # Tier 2: MODERATE (-1.78) - Default for all others
        return -1.78  # Original Beneish threshold

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

            # Altman Z - ONLY if applicable to this industry
            z = guardrails.get('altmanZ')
            if z is not None and self._is_altman_z_applicable(industry, company_type):
                if z < cfg.get('altman_z_red', 1.8):
                    red_flags += 1
                    reasons.append(f"Altman Z={z:.2f} <1.8 (distress)")
                elif z < cfg.get('altman_z_amber', 2.99):
                    amber_flags += 1
                    reasons.append(f"Altman Z={z:.2f} gray zone")

            # Accruals - industry-adjusted threshold
            accruals = guardrails.get('accruals_noa_%')
            if accruals is not None:
                # Tech/growth companies: Higher threshold (20%)
                # Mature/value companies: Standard threshold (15%)
                industry_lower = industry.lower() if industry else ''

                growth_keywords = ['software', 'technology', 'internet', 'biotech',
                                  'semiconductor', 'growth', 'saas']
                is_growth = any(kw in industry_lower for kw in growth_keywords)

                threshold = 20 if is_growth else 15

                if accruals > threshold:
                    amber_flags += 1
                    reasons.append(f"Accruals/NOA={accruals:.1f}% >{threshold}%")

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

        # Beneish M-Score (all types) - INDUSTRY-ADJUSTED THRESHOLDS
        m = guardrails.get('beneishM')
        if m is not None:
            # Get industry-specific threshold for ROJO classification
            rojo_threshold = self._get_beneish_threshold_for_industry(industry)
            amber_threshold = -2.22  # Standard amber threshold (Beneish original)

            if m > rojo_threshold:
                red_flags += 1
                reasons.append(f"Beneish M={m:.2f} >{rojo_threshold:.2f} (manip.?)")
            elif m > amber_threshold:
                amber_flags += 1
                reasons.append(f"Beneish M={m:.2f} borderline")

        # Net Share Issuance (all types) - Industry-adjusted thresholds
        dilution = guardrails.get('netShareIssuance_12m_%')
        if dilution is not None:
            # Industry-specific dilution tolerance
            industry_lower = industry.lower() if industry else ''

            # Growth companies: Higher tolerance (raising capital for growth is normal)
            # Biotech, early-stage tech, high-growth sectors
            growth_high_dilution_keywords = [
                'biotech', 'pharmaceutical', 'drug', 'clinical',
                'genomics', 'life sciences',
                'software - infrastructure', 'software - application',
                'semiconductor', 'solar', 'renewable',
                'electric vehicle', 'aerospace', 'space'
            ]

            # Mature companies: Low tolerance (dilution is red flag)
            # Financials, consumer staples, utilities
            mature_low_dilution_keywords = [
                'bank', 'financial services', 'insurance', 'capital markets',
                'consumer staples', 'household', 'packaged foods', 'beverages',
                'tobacco', 'utilities', 'reit'
            ]

            is_high_growth = any(kw in industry_lower for kw in growth_high_dilution_keywords)
            is_mature = any(kw in industry_lower for kw in mature_low_dilution_keywords)

            if is_high_growth:
                # Growth companies: ROJO >20%, AMBAR >10%
                if dilution > 20:
                    red_flags += 1
                    reasons.append(f"Dilution={dilution:.1f}% >20% (growth co.)")
                elif dilution > 10:
                    amber_flags += 1
                    reasons.append(f"Dilution={dilution:.1f}% >10% (growth co.)")
            elif is_mature:
                # Mature companies: ROJO >5%, AMBAR >2%
                if dilution > 5:
                    red_flags += 1
                    reasons.append(f"Dilution={dilution:.1f}% >5% (mature co.)")
                elif dilution > 2:
                    amber_flags += 1
                    reasons.append(f"Dilution={dilution:.1f}% >2% (mature co.)")
            else:
                # Standard companies: ROJO >10%, AMBAR >5%
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

        # Revenue Decline (Declining Business)
        revenue_growth = guardrails.get('revenue_growth_3y')
        if revenue_growth is not None:
            if revenue_growth < -5:
                # Revenue declining >5% = serious concern (moat erosion)
                amber_flags += 1
                reasons.append(f"Revenue declining {revenue_growth:.1f}% (3Y)")
            elif revenue_growth < 0:
                # Any revenue decline = yellow flag
                amber_flags += 1
                reasons.append(f"Revenue flat/declining {revenue_growth:.1f}% (3Y)")

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

    def _calc_revenue_growth_3y(self, income: List[Dict]) -> Optional[float]:
        """
        Calculate 3-year revenue CAGR.
        Negative growth = declining business (red flag for moat erosion).
        """
        if not income or len(income) < 12:
            return None

        try:
            revenue_latest = income[0].get('revenue', 0)
            revenue_3y_ago = income[11].get('revenue', 0)

            if revenue_latest and revenue_3y_ago and revenue_3y_ago > 0:
                # CAGR formula: (Ending/Beginning)^(1/years) - 1
                growth = ((revenue_latest / revenue_3y_ago) ** (1/3) - 1) * 100
                return growth
            else:
                return None
        except Exception as e:
            logger.warning(f"Error calculating revenue growth: {e}")
            return None
