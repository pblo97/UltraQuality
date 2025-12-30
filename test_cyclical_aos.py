#!/usr/bin/env python3
"""
Test script to diagnose cyclical analysis data for AOS
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.screener.ingest import FMPClient

def test_aos_data():
    """Test what data FMP returns for AOS"""

    # Get API key from environment
    api_key = os.getenv('FMP_API_KEY')
    if not api_key:
        print("ERROR: FMP_API_KEY environment variable not set")
        print("Set it with: export FMP_API_KEY=your_key")
        return

    # Create minimal config
    config = {
        'fmp': {
            'api_key': api_key,
            'base_url': 'https://financialmodelingprep.com/api/v3',
            'premium': True
        }
    }

    fmp = FMPClient(api_key=api_key, config=config)
    symbol = 'AOS'

    print("=" * 80)
    print(f"CYCLICAL DATA DIAGNOSTIC FOR {symbol}")
    print("=" * 80)

    # Test 1: Profile (for P/E fallback)
    print("\n1. PROFILE DATA (P/E Fallback):")
    profile = fmp.get_profile(symbol)
    if profile and len(profile) > 0:
        print(f"   ✓ Profile found")
        print(f"   - PE: {profile[0].get('pe', 'N/A')}")
        print(f"   - Beta: {profile[0].get('beta', 'N/A')}")
        print(f"   - Sector: {profile[0].get('sector', 'N/A')}")
    else:
        print(f"   ✗ No profile data")

    # Test 2: Key Metrics (for P/E and P/B)
    print("\n2. KEY METRICS (P/E Paradox + P/B Bands):")
    key_metrics = fmp.get_key_metrics(symbol, period='annual', limit=5)
    if key_metrics:
        print(f"   ✓ Found {len(key_metrics)} years of key metrics")
        pe_values = []
        pb_values = []
        for i, m in enumerate(key_metrics):
            date = m.get('date', 'Unknown')
            pe = m.get('peRatio', None)
            pb = m.get('pbRatio', None)
            print(f"   - {date}: P/E={pe}, P/B={pb}")
            if pe:
                pe_values.append(pe)
            if pb:
                pb_values.append(pb)

        print(f"\n   Summary: {len(pe_values)} P/E values, {len(pb_values)} P/B values")
        if len(pb_values) >= 3:
            print(f"   ✓ ENOUGH for P/B Bands (need 3+)")
        else:
            print(f"   ✗ NOT ENOUGH for P/B Bands (need 3, got {len(pb_values)})")
    else:
        print(f"   ✗ No key metrics data")

    # Test 3: Financial Ratios (for DIO)
    print("\n3. FINANCIAL RATIOS (Inventory DIO):")
    ratios = fmp.get_financial_ratios(symbol, period='annual', limit=4)
    if ratios:
        print(f"   ✓ Found {len(ratios)} years of financial ratios")
        dio_values = []
        for i, r in enumerate(ratios):
            date = r.get('date', 'Unknown')
            dio = r.get('daysOfInventoryOutstanding', None)
            print(f"   - {date}: DIO={dio}")
            if dio is not None:
                dio_values.append(dio)

        print(f"\n   Summary: {len(dio_values)} DIO values")
        if len(dio_values) >= 2:
            print(f"   ✓ ENOUGH for DIO analysis (need 2+)")
        else:
            print(f"   ✗ NOT ENOUGH for DIO analysis (need 2, got {len(dio_values)})")
    else:
        print(f"   ✗ No financial ratios data")

    # Test 4: Income Statement (for Operating Margin)
    print("\n4. INCOME STATEMENT (Operating Margin):")
    income = fmp.get_income_statement(symbol, period='annual', limit=5)
    if income:
        print(f"   ✓ Found {len(income)} years of income statements")
        margin_values = []
        for i, stmt in enumerate(income):
            date = stmt.get('date', 'Unknown')
            revenue = stmt.get('revenue', 0)
            op_income = stmt.get('operatingIncome', 0)
            if revenue and revenue != 0:
                margin = (op_income / revenue) * 100
                print(f"   - {date}: Revenue=${revenue:,.0f}, OpIncome=${op_income:,.0f}, Margin={margin:.1f}%")
                margin_values.append(margin)
            else:
                print(f"   - {date}: No revenue data")

        print(f"\n   Summary: {len(margin_values)} margin values")
        if len(margin_values) >= 3:
            print(f"   ✓ ENOUGH for Margin analysis (need 3+)")
        else:
            print(f"   ✗ NOT ENOUGH for Margin analysis (need 3, got {len(margin_values)})")
    else:
        print(f"   ✗ No income statement data")

    print("\n" + "=" * 80)
    print("DIAGNOSIS COMPLETE")
    print("=" * 80)

if __name__ == '__main__':
    test_aos_data()
