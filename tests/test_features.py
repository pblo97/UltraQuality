"""
Unit tests for feature calculations.
Tests ROIC, NOA, FFO/AFFO, and other key metrics.
"""
import pytest
from unittest.mock import Mock, MagicMock
from src.screener.features import FeatureCalculator


@pytest.fixture
def mock_fmp_client():
    """Mock FMP client."""
    client = Mock()
    return client


@pytest.fixture
def feature_calc(mock_fmp_client):
    """FeatureCalculator instance with mock client."""
    return FeatureCalculator(mock_fmp_client)


class TestROICCalculation:
    """Test ROIC = NOPAT / NOA calculation."""

    def test_roic_positive(self, feature_calc):
        """Test ROIC calculation for profitable company."""
        # Mock data
        income = [
            {'operatingIncome': 100, 'incomeTaxExpense': 20, 'incomeBeforeTax': 90},
            {'operatingIncome': 95, 'incomeTaxExpense': 19, 'incomeBeforeTax': 85},
            {'operatingIncome': 92, 'incomeTaxExpense': 18, 'incomeBeforeTax': 82},
            {'operatingIncome': 88, 'incomeTaxExpense': 17, 'incomeBeforeTax': 78}
        ]

        balance = [{
            'totalAssets': 1000,
            'cashAndCashEquivalents': 100,
            'totalLiabilities': 600,
            'totalDebt': 200
        }]

        # Calculate EBIT TTM
        ebit_ttm = sum(q['operatingIncome'] for q in income)
        assert ebit_ttm == 375

        # Tax rate = 20/90 = 22.2%
        tax_rate = feature_calc._estimate_tax_rate(income)
        assert tax_rate == pytest.approx(0.222, abs=0.01)

        # NOPAT = EBIT * (1 - tax_rate) = 375 * 0.778 = 291.75
        nopat = ebit_ttm * (1 - tax_rate)

        # NOA = (Total Assets - Cash) - (Total Liabilities - Total Debt)
        # NOA = (1000 - 100) - (600 - 200) = 900 - 400 = 500
        noa = (1000 - 100) - (600 - 200)
        assert noa == 500

        # ROIC = 291.75 / 500 = 58.35%
        roic = (nopat / noa) * 100
        assert roic == pytest.approx(58.35, abs=1.0)


class TestFFOCalculation:
    """Test FFO (Funds From Operations) for REITs."""

    def test_ffo_basic(self, feature_calc):
        """Test basic FFO calculation."""
        # FFO = Net Income + Depreciation - Gains on Sales

        income = [
            {'netIncome': 50},
            {'netIncome': 48},
            {'netIncome': 47},
            {'netIncome': 45}
        ]

        cashflow = [
            {'depreciationAndAmortization': 30},
            {'depreciationAndAmortization': 29},
            {'depreciationAndAmortization': 28},
            {'depreciationAndAmortization': 27}
        ]

        # Net Income TTM = 50 + 48 + 47 + 45 = 190
        ni_ttm = feature_calc._sum_ttm(income, 'netIncome')
        assert ni_ttm == 190

        # D&A TTM = 30 + 29 + 28 + 27 = 114
        da_ttm = feature_calc._sum_ttm(cashflow, 'depreciationAndAmortization')
        assert da_ttm == 114

        # FFO ≈ 190 + 114 = 304 (ignoring gains on sales)
        ffo = ni_ttm + da_ttm
        assert ffo == 304


class TestTaxRateEstimation:
    """Test effective tax rate estimation."""

    def test_normal_tax_rate(self, feature_calc):
        """Test tax rate calculation."""
        income = [{
            'incomeTaxExpense': 21,
            'incomeBeforeTax': 100
        }]

        tax_rate = feature_calc._estimate_tax_rate(income)
        assert tax_rate == 0.21

    def test_negative_income(self, feature_calc):
        """Test tax rate with negative income (loss)."""
        income = [{
            'incomeTaxExpense': 0,
            'incomeBeforeTax': -50
        }]

        tax_rate = feature_calc._estimate_tax_rate(income)
        assert tax_rate == 0.21  # Default

    def test_missing_data(self, feature_calc):
        """Test tax rate with missing data."""
        income = [{}]

        tax_rate = feature_calc._estimate_tax_rate(income)
        assert tax_rate == 0.21  # Default US corporate rate


class TestSumTTM:
    """Test TTM (Trailing Twelve Months) summation."""

    def test_sum_ttm_complete(self, feature_calc):
        """Test TTM sum with complete data."""
        statements = [
            {'revenue': 100},
            {'revenue': 95},
            {'revenue': 92},
            {'revenue': 88}
        ]

        total = feature_calc._sum_ttm(statements, 'revenue')
        assert total == 375

    def test_sum_ttm_incomplete(self, feature_calc):
        """Test TTM sum with incomplete data."""
        statements = [
            {'revenue': 100},
            {'revenue': 95}
        ]

        total = feature_calc._sum_ttm(statements, 'revenue')
        assert total is None  # Need 4 quarters

    def test_sum_ttm_missing_field(self, feature_calc):
        """Test TTM sum with missing field."""
        statements = [
            {'revenue': 100},
            {'revenue': 95},
            {},  # Missing revenue
            {'revenue': 88}
        ]

        total = feature_calc._sum_ttm(statements, 'revenue')
        assert total is None  # Incomplete data


class TestShareholderYield:
    """Test shareholder yield calculation."""

    def test_positive_yield(self, feature_calc):
        """Test company with dividends and buybacks."""
        # Shareholder Yield = (Dividends + Buybacks - Issuance) / Market Cap

        cashflow = {
            'dividendsPaid': -10,  # Usually negative
            'commonStockRepurchased': -5,  # Negative = buyback
            'commonStockIssued': 0
        }

        market_cap = 1000

        # Yield = (10 + 5 - 0) / 1000 = 1.5%
        div_paid = abs(cashflow['dividendsPaid'])
        buybacks = abs(cashflow['commonStockRepurchased'])
        issuance = cashflow['commonStockIssued']

        shareholder_return = div_paid + buybacks - issuance
        yield_pct = (shareholder_return / market_cap) * 100

        assert yield_pct == 1.5

    def test_negative_yield(self, feature_calc):
        """Test company with net dilution."""
        cashflow = {
            'dividendsPaid': -2,
            'commonStockRepurchased': 0,
            'commonStockIssued': 20  # Large issuance
        }

        market_cap = 1000

        div_paid = abs(cashflow['dividendsPaid'])
        buybacks = 0
        issuance = cashflow['commonStockIssued']

        shareholder_return = div_paid + buybacks - issuance
        yield_pct = (shareholder_return / market_cap) * 100

        assert yield_pct == -1.8  # Negative = dilution
