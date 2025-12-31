#!/usr/bin/env python3
"""
Test script to debug why P/E, PEG, EV/EBIT, EV/FCF are not working
"""

import os
import sys
import logging

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from screener.qualitative import QualitativeAnalyzer
from api.fmp_client import FMPClient

# Setup logging to see ALL debug messages
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s - %(name)s - %(message)s'
)

# Get API key
api_key = os.getenv('FMP_API_KEY')
if not api_key:
    print("ERROR: FMP_API_KEY environment variable not set")
    sys.exit(1)

# Initialize
fmp = FMPClient(api_key)
analyzer = QualitativeAnalyzer(fmp)

# Test symbol - use one from your example
symbol = "AAPL"  # Change this to your test symbol

print(f"\n{'='*80}")
print(f"Testing valuation methods for {symbol}")
print(f"{'='*80}\n")

# Get peers first
print("1. Getting peers...")
peers_data = fmp.get_stock_peers(symbol)
peers_list = []
if peers_data and 'peersList' in peers_data[0]:
    peers_list = peers_data[0]['peersList'][:5]
    print(f"   Found {len(peers_list)} peers: {peers_list}")
else:
    print(f"   No peers found")

# Test each method individually
print("\n2. Testing P/E calculation...")
try:
    pe_value = analyzer._calculate_pe_intrinsic_value(symbol, peers_list)
    print(f"   Result: ${pe_value:.2f}" if pe_value else "   Result: None")
except Exception as e:
    print(f"   ERROR: {e}")

print("\n3. Testing PEG calculation...")
try:
    # Get growth data first
    growth_data = analyzer._calculate_growth_engine_5y(symbol)
    peg_value = analyzer._calculate_peg_intrinsic_value(symbol, growth_data)
    print(f"   Result: ${peg_value:.2f}" if peg_value else "   Result: None")
except Exception as e:
    print(f"   ERROR: {e}")

print("\n4. Testing EV/EBIT calculation...")
try:
    ev_ebit_value = analyzer._calculate_ev_ebit_intrinsic_value(symbol, peers_list)
    print(f"   Result: ${ev_ebit_value:.2f}" if ev_ebit_value else "   Result: None")
except Exception as e:
    print(f"   ERROR: {e}")

print("\n5. Testing EV/FCF calculation...")
try:
    ev_fcf_value = analyzer._calculate_ev_fcf_intrinsic_value(symbol, peers_list)
    print(f"   Result: ${ev_fcf_value:.2f}" if ev_fcf_value else "   Result: None")
except Exception as e:
    print(f"   ERROR: {e}")

print(f"\n{'='*80}")
print("Test complete")
print(f"{'='*80}\n")
