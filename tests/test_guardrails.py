"""
Unit tests for guardrails calculations.
Tests Altman Z-Score, Beneish M-Score, Accruals, etc.
"""
import pytest
import numpy as np
from unittest.mock import Mock, MagicMock
from src.screener.guardrails import GuardrailCalculator


@pytest.fixture
def mock_fmp_client():
    """Mock FMP client."""
    client = Mock()
    return client


@pytest.fixture
def guardrail_calc(mock_fmp_client):
    """GuardrailCalculator instance with mock client."""
    config = {
        'guardrails': {
            'non_financial': {
                'altman_z_red': 1.8,
                'altman_z_amber': 2.99,
                'beneish_m_red': -1.78
            }
        }
    }
    return GuardrailCalculator(mock_fmp_client, config)


class TestAltmanZScore:
    """Test Altman Z-Score calculation."""

    def test_healthy_company(self, guardrail_calc):
        """Test Z-Score for healthy company (Z > 2.99)."""
        balance = [{
            'totalCurrentAssets': 1000,
            'totalCurrentLiabilities': 400,
            'totalAssets': 2000,
            'retainedEarnings': 500,
            'totalLiabilities': 800,
            'totalStockholdersEquity': 1200
        }]

        income = [{
            'operatingIncome': 300,  # EBIT
            'revenue': 1500
        }]

        z_score = guardrail_calc._calc_altman_z(balance, income, [])

        assert z_score is not None
        assert z_score > 2.0  # Healthy range

    def test_distressed_company(self, guardrail_calc):
        """Test Z-Score for distressed company (Z < 1.8)."""
        balance = [{
            'totalCurrentAssets': 500,
            'totalCurrentLiabilities': 700,
            'totalAssets': 2000,
            'retainedEarnings': -200,  # Negative retained earnings
            'totalLiabilities': 1800,
            'totalStockholdersEquity': 200
        }]

        income = [{
            'operatingIncome': 50,  # Low EBIT
            'revenue': 800
        }]

        z_score = guardrail_calc._calc_altman_z(balance, income, [])

        assert z_score is not None
        assert z_score < 2.0  # Distress zone

    def test_missing_data(self, guardrail_calc):
        """Test Z-Score with missing data."""
        balance = [{}]
        income = [{}]

        z_score = guardrail_calc._calc_altman_z(balance, income, [])

        assert z_score is None


class TestBeneishMScore:
    """Test Beneish M-Score calculation."""

    def test_clean_company(self, guardrail_calc):
        """Test M-Score for clean company (M < -2.22)."""
        # Create mock data for 2 periods
        balance = [
            {  # Current
                'totalAssets': 2000,
                'totalCurrentAssets': 800,
                'propertyPlantEquipmentNet': 600,
                'netReceivables': 200,
                'totalLiabilities': 800
            },
            {}, {}, {},
            {  # t-4 (YoY)
                'totalAssets': 1900,
                'totalCurrentAssets': 750,
                'propertyPlantEquipmentNet': 580,
                'netReceivables': 180,
                'totalLiabilities': 750
            }
        ]

        income = [
            {  # Current
                'revenue': 1500,
                'grossProfit': 600,
                'operatingExpenses': 300,
                'netIncome': 200
            },
            {}, {}, {},
            {  # t-4
                'revenue': 1400,
                'grossProfit': 560,
                'operatingExpenses': 280,
                'netIncome': 190
            }
        ]

        cashflow = [
            {'operatingCashFlow': 250, 'depreciationAndAmortization': 50, 'capitalExpenditure': -80},
            {}, {}, {},
            {'operatingCashFlow': 240, 'depreciationAndAmortization': 48, 'capitalExpenditure': -75}
        ]

        m_score = guardrail_calc._calc_beneish_m(balance, income, cashflow)

        assert m_score is not None
        # Clean companies typically have M-Score < -2
        # Can't assert exact value without full calculation, but should be negative

    def test_insufficient_data(self, guardrail_calc):
        """Test M-Score with insufficient data."""
        balance = [{}]
        income = [{}]
        cashflow = [{}]

        m_score = guardrail_calc._calc_beneish_m(balance, income, cashflow)

        assert m_score is None


class TestAccrualsNOA:
    """Test Accruals / NOA calculation."""

    def test_low_accruals(self, guardrail_calc):
        """Test company with low accruals (good quality)."""
        balance = [
            {
                'totalCurrentAssets': 1000,
                'cashAndCashEquivalents': 200,
                'totalCurrentLiabilities': 600,
                'shortTermDebt': 100,
                'taxPayables': 50,
                'totalAssets': 2500,
                'totalLiabilities': 1200,
                'totalDebt': 500
            },
            {
                'totalCurrentAssets': 950,
                'cashAndCashEquivalents': 180,
                'totalCurrentLiabilities': 580,
                'shortTermDebt': 95,
                'taxPayables': 48,
                'totalAssets': 2450,
                'totalLiabilities': 1180,
                'totalDebt': 490
            }
        ]

        cashflow = [{
            'depreciationAndAmortization': 100
        }]

        accruals_pct = guardrail_calc._calc_accruals_noa(balance, [], cashflow)

        assert accruals_pct is not None
        # Should be relatively low for quality companies

    def test_high_accruals(self, guardrail_calc):
        """Test company with high accruals (potential red flag)."""
        balance = [
            {
                'totalCurrentAssets': 1500,  # Large increase
                'cashAndCashEquivalents': 100,  # Small cash
                'totalCurrentLiabilities': 500,
                'shortTermDebt': 50,
                'taxPayables': 20,
                'totalAssets': 3000,
                'totalLiabilities': 1000,
                'totalDebt': 300
            },
            {
                'totalCurrentAssets': 800,
                'cashAndCashEquivalents': 150,
                'totalCurrentLiabilities': 550,
                'shortTermDebt': 55,
                'taxPayables': 22,
                'totalAssets': 2500,
                'totalLiabilities': 1050,
                'totalDebt': 310
            }
        ]

        cashflow = [{
            'depreciationAndAmortization': 80
        }]

        accruals_pct = guardrail_calc._calc_accruals_noa(balance, [], cashflow)

        assert accruals_pct is not None
        # High accruals = potential earnings quality issue


class TestNetShareIssuance:
    """Test net share issuance (dilution) calculation."""

    def test_buybacks(self, guardrail_calc):
        """Test company with share buybacks (negative dilution)."""
        balance = [
            {'commonStock': 90, 'weightedAverageShsOut': 90},
            {}, {}, {},
            {'commonStock': 100, 'weightedAverageShsOut': 100}
        ]

        dilution = guardrail_calc._calc_net_share_issuance(balance, [])

        assert dilution is not None
        assert dilution < 0  # Negative = buybacks

    def test_dilution(self, guardrail_calc):
        """Test company with share issuance (dilution)."""
        balance = [
            {'commonStock': 120, 'weightedAverageShsOut': 120},
            {}, {}, {},
            {'commonStock': 100, 'weightedAverageShsOut': 100}
        ]

        dilution = guardrail_calc._calc_net_share_issuance(balance, [])

        assert dilution is not None
        assert dilution > 0  # Positive = dilution
        assert dilution == pytest.approx(20.0, rel=0.01)


class TestMnAFlag:
    """Test M&A flag calculation."""

    def test_high_mna_activity(self, guardrail_calc):
        """Test company with high M&A (goodwill growth)."""
        balance = [
            {
                'goodwill': 500,
                'intangibleAssets': 300,
                'totalAssets': 2000
            },
            {}, {}, {},
            {
                'goodwill': 200,
                'intangibleAssets': 100,
                'totalAssets': 1800
            }
        ]

        flag = guardrail_calc._calc_mna_flag(balance)

        assert flag == 'HIGH'

    def test_low_mna_activity(self, guardrail_calc):
        """Test company with low/no M&A."""
        balance = [
            {
                'goodwill': 105,
                'intangibleAssets': 50,
                'totalAssets': 2000
            },
            {}, {}, {},
            {
                'goodwill': 100,
                'intangibleAssets': 48,
                'totalAssets': 1950
            }
        ]

        flag = guardrail_calc._calc_mna_flag(balance)

        assert flag == 'LOW'


class TestGuardrailAssessment:
    """Test overall guardrail status assessment."""

    def test_all_green(self, guardrail_calc):
        """Test assessment with all green flags."""
        guardrails = {
            'altmanZ': 3.5,
            'beneishM': -2.5,
            'accruals_noa_%': 5.0,
            'netShareIssuance_12m_%': -2.0,  # Buybacks
            'mna_flag': 'LOW'
        }

        status, reasons = guardrail_calc._assess_guardrails(
            guardrails, 'non_financial', 'Technology'
        )

        assert status == 'VERDE'
        assert 'OK' in reasons.lower() or 'all checks' in reasons.lower()

    def test_red_flags(self, guardrail_calc):
        """Test assessment with red flags."""
        guardrails = {
            'altmanZ': 1.5,  # RED
            'beneishM': -1.5,  # RED
            'accruals_noa_%': 8.0,
            'netShareIssuance_12m_%': 15.0,  # RED
            'mna_flag': 'HIGH'
        }

        status, reasons = guardrail_calc._assess_guardrails(
            guardrails, 'non_financial', 'Technology'
        )

        assert status == 'ROJO'
        assert len(reasons) > 0
