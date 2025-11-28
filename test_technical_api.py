#!/usr/bin/env python3
"""
Quick test script to diagnose technical analysis issues.

Usage:
    python3 test_technical_api.py
"""

import sys
sys.path.insert(0, 'src')

import os
import yaml
from datetime import datetime, timedelta
from screener.ingest import FMPClient
from screener.cache import CachedFMPClient

def load_api_key():
    """Load API key from multiple sources."""
    # Try environment variable first
    api_key = os.environ.get('FMP_API_KEY')
    if api_key:
        print(f"✅ Found API key in environment variable")
        return api_key

    # Try .env file
    if os.path.exists('.env'):
        with open('.env') as f:
            for line in f:
                if line.strip().startswith('FMP_API_KEY='):
                    api_key = line.split('=', 1)[1].strip()
                    if api_key and api_key != 'YOUR_FMP_API_KEY_HERE' and not api_key.startswith('${'):
                        print(f"✅ Found API key in .env file")
                        return api_key

    # Try secrets.toml
    secrets_path = '.streamlit/secrets.toml'
    if os.path.exists(secrets_path):
        # Simple parser (not full TOML)
        with open(secrets_path) as f:
            for line in f:
                if 'fmp_api_key' in line and '=' in line:
                    api_key = line.split('=', 1)[1].strip().strip('"\'')
                    if api_key and api_key != 'YOUR_FMP_API_KEY_HERE':
                        print(f"✅ Found API key in {secrets_path}")
                        return api_key

    print("❌ No API key found!")
    print("\nPlease configure your FMP API key in one of:")
    print("1. Environment variable: export FMP_API_KEY=your_key")
    print("2. .env file: FMP_API_KEY=your_key")
    print("3. .streamlit/secrets.toml: fmp_api_key = \"your_key\"")
    return None


def test_quote_endpoint(fmp, symbol='AAPL'):
    """Test quote endpoint."""
    print(f"\n🔍 Testing quote endpoint for {symbol}...")
    try:
        quote = fmp.get_quote(symbol)
        if quote and len(quote) > 0:
            q = quote[0]
            print(f"✅ Quote endpoint works!")
            print(f"   Price: ${q.get('price', 'N/A')}")
            print(f"   MA200: ${q.get('priceAvg200', 'N/A')}")
            print(f"   MA50: ${q.get('priceAvg50', 'N/A')}")
            print(f"   Volume: {q.get('volume', 'N/A'):,}")
            return True
        else:
            print(f"❌ Quote endpoint returned empty data")
            return False
    except Exception as e:
        print(f"❌ Quote endpoint failed: {e}")
        return False


def test_historical_endpoint(fmp, symbol='AAPL'):
    """Test historical prices endpoint."""
    print(f"\n🔍 Testing historical prices endpoint for {symbol}...")
    try:
        from_date = (datetime.now() - timedelta(days=400)).strftime('%Y-%m-%d')
        print(f"   Requesting data from {from_date}")

        hist_data = fmp.get_historical_prices(symbol, from_date=from_date)

        print(f"   Response type: {type(hist_data)}")

        if isinstance(hist_data, dict):
            print(f"   Response keys: {list(hist_data.keys())}")

            if 'historical' in hist_data:
                records = hist_data['historical']
                print(f"✅ Historical endpoint works!")
                print(f"   Records: {len(records)}")

                if len(records) > 0:
                    latest = records[0]
                    print(f"   Latest record:")
                    print(f"      Date: {latest.get('date', 'N/A')}")
                    print(f"      Close: ${latest.get('close', 'N/A')}")
                    print(f"      Volume: {latest.get('volume', 'N/A'):,}")

                # Check if we have enough data for technical analysis
                if len(records) >= 250:
                    print(f"✅ Sufficient data for full technical analysis (250+ days)")
                else:
                    print(f"⚠️  Only {len(records)} records (need 250+ for full analysis)")

                return True
            else:
                print(f"❌ No 'historical' key in response")
                print(f"   Full response: {hist_data}")
                return False

        elif isinstance(hist_data, list):
            print(f"❌ Got list instead of dict (format error)")
            if len(hist_data) > 0:
                print(f"   First item: {hist_data[0]}")
            return False

        elif hist_data is None:
            print(f"❌ Got None (API error or unauthorized)")
            return False

        else:
            print(f"❌ Unexpected response type")
            print(f"   Response: {hist_data}")
            return False

    except Exception as e:
        print(f"❌ Historical endpoint failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_market_data(fmp):
    """Test market data (SPY, VIX)."""
    print(f"\n🔍 Testing market data (SPY, VIX)...")

    # Test SPY
    try:
        spy_quote = fmp.get_quote('SPY')
        if spy_quote and len(spy_quote) > 0:
            spy = spy_quote[0]
            print(f"✅ SPY quote works")
            print(f"   Price: ${spy.get('price', 'N/A')}")
            print(f"   MA200: ${spy.get('priceAvg200', 'N/A')}")
        else:
            print(f"❌ SPY quote failed")
    except Exception as e:
        print(f"❌ SPY quote error: {e}")

    # Test VIX
    try:
        vix_quote = fmp.get_quote('^VIX')
        if vix_quote and len(vix_quote) > 0:
            vix = vix_quote[0]
            print(f"✅ VIX quote works")
            print(f"   VIX: {vix.get('price', 'N/A')}")
        else:
            print(f"⚠️  VIX quote returned empty (not critical)")
    except Exception as e:
        print(f"⚠️  VIX quote error (not critical): {e}")


def main():
    print("="*60)
    print("Technical Analysis API Diagnostic Tool")
    print("="*60)

    # Load config
    print("\n📋 Loading configuration...")
    with open('settings.yaml') as f:
        config = yaml.safe_load(f)
    print("✅ settings.yaml loaded")

    # Load API key
    api_key = load_api_key()
    if not api_key:
        print("\n❌ Cannot proceed without API key")
        sys.exit(1)

    print(f"   API Key (first 10 chars): {api_key[:10]}...")

    # Initialize clients
    print("\n🔧 Initializing FMP clients...")
    fmp_base = FMPClient(api_key, config['fmp'])
    fmp = CachedFMPClient(fmp_base, cache_dir='.cache_test')
    print("✅ Clients initialized")

    # Run tests
    quote_ok = test_quote_endpoint(fmp)
    hist_ok = test_historical_endpoint(fmp)
    test_market_data(fmp)

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    if quote_ok and hist_ok:
        print("✅ ALL TESTS PASSED")
        print("\nYour API is configured correctly!")
        print("If technical analysis still shows zeros:")
        print("1. Clear cache: rm -rf .cache .cache_test")
        print("2. Restart Streamlit app")
        print("3. Check Streamlit logs for detailed errors")
    elif quote_ok and not hist_ok:
        print("⚠️  PARTIAL SUCCESS")
        print("\nQuote endpoint works, but historical endpoint has issues.")
        print("Possible causes:")
        print("- Rate limit exceeded (check your plan limits)")
        print("- API endpoint changed (report as bug)")
        print("- Network issues")
    else:
        print("❌ TESTS FAILED")
        print("\nYour API configuration has issues.")
        print("Most likely cause: Invalid or missing API key")
        print("\nSteps to fix:")
        print("1. Get a valid API key from https://financialmodelingprep.com")
        print("2. Add to .env file: FMP_API_KEY=your_actual_key")
        print("3. Run this script again")

    print("="*60)


if __name__ == '__main__':
    main()
