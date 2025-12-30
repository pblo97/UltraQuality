#!/usr/bin/env python3
"""
Test script to verify robust_fair_value calculation works
"""
import sys
sys.path.insert(0, '/home/user/UltraQuality')

from src.screener.qualitative import QualitativeAnalyzer
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Create analyzer
analyzer = QualitativeAnalyzer()

# Test data
symbol = "TEST"
valuation_methods_dict = {
    'dcf_value': 100.0,
    'forward_multiple_value': 120.0,
    'pe_value': 110.0
}

confidence_score = {
    'total_score': 75,
    'stability': 0.8,
    'fcf_quality': 0.7,
    'data_richness': 0.9,
    'balance_strength': 0.6,
    'other': 0.5
}

growth_engine = {
    'revenue_growth_5y': {
        'base': 0.10,
        'bear': 0.05,
        'bull': 0.15,
        'weights': {'historical': 0.45, 'fundamental': 0.45, 'consensus': 0.10}
    }
}

print("Testing robust_fair_value calculation...")
print(f"Input methods: {valuation_methods_dict}")
print(f"Confidence score: {confidence_score['total_score']}")

try:
    result = analyzer._calculate_robust_fair_value(
        symbol,
        valuation_methods_dict,
        confidence_score,
        growth_engine
    )

    print("\nResult:")
    if result:
        for key, value in result.items():
            print(f"  {key}: {value}")
    else:
        print("  None returned!")

except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()
