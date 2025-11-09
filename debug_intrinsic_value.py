"""
Debug script to test intrinsic value calculations
"""
import sys
import yaml
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from screener.ingest import FMPClient
from screener.qualitative import QualitativeAnalyzer

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_intrinsic_value(symbol: str):
    """Test intrinsic value calculation for a specific symbol"""

    # Load config
    with open('settings.yaml', 'r') as f:
        config = yaml.safe_load(f)

    # Get API key from environment or config
    import os
    api_key = os.getenv('FMP_API_KEY') or config['fmp'].get('api_key')

    if not api_key or api_key.startswith('${'):
        print("ERROR: FMP_API_KEY not found in environment")
        return

    print(f"\n{'='*80}")
    print(f"Testing Intrinsic Value Calculation for {symbol}")
    print(f"{'='*80}\n")

    # Initialize clients
    fmp_client = FMPClient(api_key, config['fmp'])
    analyzer = QualitativeAnalyzer(fmp_client, config)

    # Test getting profile and price
    print(f"Step 1: Getting profile for {symbol}...")
    profile = fmp_client.get_profile(symbol)
    print(f"Profile response: {type(profile)}, length: {len(profile) if profile else 0}")

    if profile and len(profile) > 0:
        prof = profile[0]
        print(f"Profile keys: {list(prof.keys())[:15]}")

        # Try different price fields
        price_fields = ['price', 'lastPrice', 'regularMarketPrice', 'previousClose']
        for field in price_fields:
            value = prof.get(field)
            print(f"  {field}: {value}")

        print(f"\nCompany: {prof.get('companyName')}")
        print(f"Sector: {prof.get('sector')}")
        print(f"Industry: {prof.get('industry')}")

    # Test getting financials
    print(f"\nStep 2: Getting financials for {symbol}...")
    income = fmp_client.get_income_statement(symbol, period='annual', limit=2)
    balance = fmp_client.get_balance_sheet(symbol, period='annual', limit=1)
    cashflow = fmp_client.get_cash_flow(symbol, period='annual', limit=2)

    print(f"Income statements: {len(income) if income else 0}")
    print(f"Balance sheets: {len(balance) if balance else 0}")
    print(f"Cash flow statements: {len(cashflow) if cashflow else 0}")

    if income and len(income) > 0:
        print(f"\nLatest income statement keys: {list(income[0].keys())[:20]}")
        print(f"  revenue: {income[0].get('revenue')}")
        print(f"  ebitda: {income[0].get('ebitda')}")
        print(f"  netIncome: {income[0].get('netIncome')}")

    if balance and len(balance) > 0:
        print(f"\nLatest balance sheet keys (first 20): {list(balance[0].keys())[:20]}")
        print(f"  totalDebt: {balance[0].get('totalDebt')}")
        print(f"  cashAndCashEquivalents: {balance[0].get('cashAndCashEquivalents')}")
        print(f"  weightedAverageShsOut: {balance[0].get('weightedAverageShsOut')}")
        print(f"  commonStockSharesOutstanding: {balance[0].get('commonStockSharesOutstanding')}")

    if cashflow and len(cashflow) > 0:
        print(f"\nLatest cash flow keys (first 20): {list(cashflow[0].keys())[:20]}")
        print(f"  operatingCashFlow: {cashflow[0].get('operatingCashFlow')}")
        print(f"  capitalExpenditure: {cashflow[0].get('capitalExpenditure')}")

    # Test DCF calculation directly
    print(f"\nStep 3: Testing DCF calculation...")
    try:
        dcf_value = analyzer._calculate_dcf(symbol, 'non_financial', wacc_override=0.10)
        print(f"DCF Value: {dcf_value}")
        if dcf_value:
            print(f"  Result: ${dcf_value:.2f}")
        else:
            print(f"  Result: None (calculation failed)")
    except Exception as e:
        print(f"DCF ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

    # Test Forward Multiple calculation
    print(f"\nStep 4: Testing Forward Multiple calculation...")
    try:
        forward_value = analyzer._calculate_forward_multiple(symbol, 'non_financial', peers_df=None)
        print(f"Forward Multiple Value: {forward_value}")
        if forward_value:
            print(f"  Result: ${forward_value:.2f}")
        else:
            print(f"  Result: None (calculation failed)")
    except Exception as e:
        print(f"Forward Multiple ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

    # Test full intrinsic value estimation
    print(f"\nStep 5: Testing full intrinsic value estimation...")
    try:
        intrinsic = analyzer._estimate_intrinsic_value(symbol, 'non_financial', peers_df=None)

        print(f"\nIntrinsic Value Results:")
        print(f"  current_price: {intrinsic.get('current_price')}")
        print(f"  dcf_value: {intrinsic.get('dcf_value')}")
        print(f"  forward_multiple_value: {intrinsic.get('forward_multiple_value')}")
        print(f"  weighted_value: {intrinsic.get('weighted_value')}")
        print(f"  upside_downside_%: {intrinsic.get('upside_downside_%')}")
        print(f"  confidence: {intrinsic.get('confidence')}")

        print(f"\nDebug Notes:")
        for note in intrinsic.get('notes', []):
            print(f"  - {note}")

    except Exception as e:
        print(f"Full Estimation ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

    print(f"\n{'='*80}")
    print("Test Complete")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    # Test with a known symbol
    # You can pass symbol as command line argument or use default
    test_symbol = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    test_intrinsic_value(test_symbol)
