#!/usr/bin/env python3
"""
Test FMP API connectivity and API key validity.
"""
import os
import sys
import requests


def test_fmp_connection():
    """Test FMP API connection and key validity."""

    print("=" * 60)
    print("FMP API Connection Test")
    print("=" * 60)
    print()

    # Try to get API key from multiple sources
    api_key = None
    source = None

    # 1. Streamlit secrets
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and 'FMP_API_KEY' in st.secrets:
            api_key = st.secrets['FMP_API_KEY']
            source = "Streamlit secrets"
    except (ImportError, FileNotFoundError):
        pass

    # 2. Environment variable
    if not api_key:
        api_key = os.getenv('FMP_API_KEY')
        if api_key:
            source = "Environment variable"

    # 3. .env file
    if not api_key:
        try:
            from dotenv import load_dotenv
            load_dotenv()
            api_key = os.getenv('FMP_API_KEY')
            if api_key:
                source = ".env file"
        except ImportError:
            pass

    if not api_key or api_key.startswith('your_') or api_key.startswith('${'):
        print("❌ API key not found or invalid")
        print()
        print("Please set FMP_API_KEY via one of:")
        print("  1. Streamlit secrets: Add FMP_API_KEY to .streamlit/secrets.toml")
        print("  2. Environment: export FMP_API_KEY='your_key'")
        print("  3. .env file: echo 'FMP_API_KEY=your_key' > .env")
        print()
        print("Get a key at: https://financialmodelingprep.com")
        return False

    print(f"✓ API key found ({source})")
    print(f"  Key: {api_key[:10]}...{api_key[-4:]}")
    print()

    # Test connection
    print("Testing connection to FMP API...")

    test_url = "https://financialmodelingprep.com/api/v3/profile/AAPL"

    try:
        response = requests.get(
            test_url,
            params={'apikey': api_key},
            timeout=10
        )

        print(f"  HTTP Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()

            # Check for error in response
            if isinstance(data, dict) and 'Error Message' in data:
                print(f"❌ API Error: {data['Error Message']}")
                print()
                print("Common issues:")
                print("  1. Invalid API key")
                print("  2. API key expired")
                print("  3. Plan limits exceeded")
                print("  4. Key not activated yet")
                return False

            if isinstance(data, list) and len(data) > 0:
                company = data[0]
                print(f"  Company: {company.get('companyName', 'N/A')}")
                print(f"  Symbol: {company.get('symbol', 'N/A')}")
                print(f"  Sector: {company.get('sector', 'N/A')}")
                print()
                print("✅ API connection successful!")
                print()
                print("Your FMP account info:")
                print(f"  Plan: Check at https://financialmodelingprep.com/developer/docs")
                print(f"  Rate limit: Varies by plan (see website)")
                return True
            else:
                print("❌ Unexpected response format")
                print(f"  Response: {data}")
                return False

        elif response.status_code == 401:
            print("❌ Authentication failed (401 Unauthorized)")
            print()
            print("Your API key is invalid or expired.")
            print("Get a new key at: https://financialmodelingprep.com")
            return False

        elif response.status_code == 403:
            print("❌ Access forbidden (403)")
            print()
            print("Possible issues:")
            print("  1. Plan limits exceeded (upgrade plan)")
            print("  2. This endpoint not available in your plan")
            print("  3. IP restriction (check account settings)")
            return False

        elif response.status_code == 429:
            print("❌ Rate limit exceeded (429)")
            print()
            print("You've made too many requests.")
            print("Wait a few minutes or upgrade your plan.")
            return False

        else:
            print(f"❌ HTTP Error {response.status_code}")
            print(f"  Response: {response.text[:200]}")
            return False

    except requests.exceptions.Timeout:
        print("❌ Connection timeout")
        print()
        print("Check your internet connection.")
        return False

    except requests.exceptions.ConnectionError:
        print("❌ Connection error")
        print()
        print("Cannot reach financialmodelingprep.com")
        print("Check your internet connection and firewall.")
        return False

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def test_bulk_endpoint():
    """Test bulk profile endpoint (used by screener)."""

    api_key = None

    # Get API key (same logic as above)
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and 'FMP_API_KEY' in st.secrets:
            api_key = st.secrets['FMP_API_KEY']
    except:
        pass

    if not api_key:
        api_key = os.getenv('FMP_API_KEY')

    if not api_key:
        try:
            from dotenv import load_dotenv
            load_dotenv()
            api_key = os.getenv('FMP_API_KEY')
        except:
            pass

    if not api_key:
        return

    print()
    print("Testing bulk profile endpoint (used by screener)...")

    url = "https://financialmodelingprep.com/api/v3/profile-bulk"

    try:
        response = requests.get(
            url,
            params={'apikey': api_key, 'part': 0},
            timeout=15
        )

        if response.status_code == 200:
            data = response.json()

            if isinstance(data, dict) and 'Error Message' in data:
                print(f"❌ API Error: {data['Error Message']}")
                print()
                print("The bulk profile endpoint is not available in your plan.")
                print("Upgrade to a paid plan or use the free endpoint (slower).")
                return False

            if isinstance(data, list) and len(data) > 0:
                print(f"✓ Bulk endpoint works! Got {len(data)} profiles")
                print(f"  First company: {data[0].get('companyName', 'N/A')}")
                return True
            else:
                print(f"⚠️  Bulk endpoint returned empty data")
                return False
        else:
            print(f"⚠️  Bulk endpoint error: HTTP {response.status_code}")
            print()
            print("Bulk endpoint might not be available in free plan.")
            print("The screener will still work but will be slower.")
            return False

    except Exception as e:
        print(f"⚠️  Could not test bulk endpoint: {e}")
        return False


if __name__ == '__main__':
    print()
    success = test_fmp_connection()

    if success:
        test_bulk_endpoint()
        print()
        print("=" * 60)
        print("✅ All tests passed! Ready to run screener.")
        print()
        print("Next step:")
        print("  python run_screener.py")
        print("=" * 60)
        sys.exit(0)
    else:
        print()
        print("=" * 60)
        print("❌ Tests failed. Fix the issues above first.")
        print("=" * 60)
        sys.exit(1)
