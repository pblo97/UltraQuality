#!/usr/bin/env python3
"""Debug script to check FMP data scales."""

import os
import yaml
from pathlib import Path
from src.screener.ingest import FMPClient

def main():
    ticker = 'AAPL'

    # Load config
    config_path = Path(__file__).parent / 'settings.yaml'
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    api_key = os.getenv('FMP_API_KEY')
    client = FMPClient(api_key, config['fmp'])

    print(f"Debugging data scales for {ticker}")
    print("=" * 80)

    # Get profile for market cap reference
    profile = client.get_profile(ticker)
    if profile:
        mkt_cap = profile[0].get('mktCap', 0)
        price = profile[0].get('price', 0)
        shares_outstanding_profile = profile[0].get('sharesOutstanding', 0)
        print(f"\nProfile data:")
        print(f"  Market Cap: ${mkt_cap:,.0f}")
        print(f"  Price: ${price:.2f}")
        print(f"  Shares Outstanding (profile): {shares_outstanding_profile:,.0f}")

    # Get balance sheet
    balance = client.get_balance_sheet(ticker, period='annual', limit=1)
    if balance:
        b = balance[0]
        print(f"\nBalance Sheet (most recent):")
        print(f"  Date: {b.get('date')}")
        print(f"  weightedAverageShsOut: {b.get('weightedAverageShsOut', 0):,.0f}")
        print(f"  commonStockSharesOutstanding: {b.get('commonStockSharesOutstanding', 0):,.0f}")
        print(f"  totalDebt: ${b.get('totalDebt', 0):,.0f}")
        print(f"  cashAndCashEquivalents: ${b.get('cashAndCashEquivalents', 0):,.0f}")
        print(f"  totalAssets: ${b.get('totalAssets', 0):,.0f}")
        print(f"  totalEquity: ${b.get('totalEquity', 0):,.0f}")

    # Get income statement
    income = client.get_income_statement(ticker, period='annual', limit=1)
    if income:
        i = income[0]
        print(f"\nIncome Statement (most recent):")
        print(f"  Date: {i.get('date')}")
        print(f"  revenue: ${i.get('revenue', 0):,.0f}")
        print(f"  netIncome: ${i.get('netIncome', 0):,.0f}")
        print(f"  ebitda: ${i.get('ebitda', 0):,.0f}")
        print(f"  eps: ${i.get('eps', 0):.4f}")
        print(f"  epsdiluted: ${i.get('epsdiluted', 0):.4f}")

    # Get cash flow
    cashflow = client.get_cash_flow(ticker, period='annual', limit=1)
    if cashflow:
        c = cashflow[0]
        print(f"\nCash Flow (most recent):")
        print(f"  Date: {c.get('date')}")
        print(f"  operatingCashFlow: ${c.get('operatingCashFlow', 0):,.0f}")
        print(f"  capitalExpenditure: ${c.get('capitalExpenditure', 0):,.0f}")
        print(f"  freeCashFlow: ${c.get('freeCashFlow', 0):,.0f}")

    # Calculate what the scale should be
    if profile and balance and income:
        mkt_cap = profile[0].get('mktCap', 0)
        price = profile[0].get('price', 0)
        shares_balance = balance[0].get('weightedAverageShsOut', 0)
        net_income = income[0].get('netIncome', 0)
        eps = income[0].get('eps', 0)

        print(f"\n" + "=" * 80)
        print(f"SCALE ANALYSIS:")
        print(f"=" * 80)

        # Check if market cap matches price * shares
        if shares_balance > 0:
            implied_price_from_mktcap = mkt_cap / shares_balance
            print(f"\nMarket Cap Check:")
            print(f"  Market Cap: ${mkt_cap:,.0f}")
            print(f"  Shares (balance): {shares_balance:,.0f}")
            print(f"  Implied price (mkt_cap / shares): ${implied_price_from_mktcap:.2f}")
            print(f"  Actual price: ${price:.2f}")
            print(f"  → Ratio: {implied_price_from_mktcap / price:.2f}x")

            if abs(implied_price_from_mktcap / price - 1) < 0.01:
                print(f"  ✓ Market cap and shares are in SAME scale")
            elif abs(implied_price_from_mktcap / price - 1000) < 10:
                print(f"  ⚠ Shares appear to be in ACTUAL count, mkt cap in ACTUAL $")
            elif abs(implied_price_from_mktcap / price - 0.001) < 0.0001:
                print(f"  ⚠ Shares in MILLIONS, mkt cap in ACTUAL $")

        # Check EPS
        if shares_balance > 0 and eps > 0:
            implied_eps = net_income / shares_balance
            print(f"\nEPS Check:")
            print(f"  Net Income: ${net_income:,.0f}")
            print(f"  Shares: {shares_balance:,.0f}")
            print(f"  Implied EPS (net_income / shares): ${implied_eps:.4f}")
            print(f"  Reported EPS: ${eps:.4f}")
            print(f"  → Ratio: {implied_eps / eps:.2f}x")

            if abs(implied_eps / eps - 1) < 0.01:
                print(f"  ✓ Net income and shares are in SAME scale")
            elif abs(implied_eps / eps - 1000000) < 10000:
                print(f"  ⚠ Net income in ACTUAL $, shares in ACTUAL count")
            elif abs(implied_eps / eps - 1000) < 10:
                print(f"  ⚠ Net income in ACTUAL $, shares in THOUSANDS")
            elif abs(implied_eps / eps - 1) < 0.1:
                print(f"  ✓ Net income in MILLIONS, shares in MILLIONS")

if __name__ == '__main__':
    main()
