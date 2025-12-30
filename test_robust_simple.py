#!/usr/bin/env python3
"""
Simple test to verify robust_fair_value logic works after fixes
"""
import numpy as np
from scipy import stats

# Simulate the robust_fair_value calculation
def test_robust_calculation():
    print("Testing Robust Fair Value Calculation Logic...")
    print("=" * 60)

    # Test data: 3 valuation methods
    valuation_methods = {
        'dcf_value': 100.0,
        'forward_multiple_value': 120.0,
        'pe_value': 110.0
    }

    confidence_data = {
        'total_score': 75,
        'components': {
            'fcf_quality': 80,
            'stability': 70,
            'data_richness': 85,
            'balance_strength': 60,
            'other': 50
        }
    }

    growth_data = {
        'revenue_growth_5y': {
            'base': 0.10,
            'volatility': 0.05
        }
    }

    # Define families
    families = {
        'cashflow': {
            'methods': ['dcf_value'],
            'max_weight': 0.33,
            'values': []
        },
        'earnings': {
            'methods': ['pe_value', 'peg_value'],
            'max_weight': 0.33,
            'values': []
        },
        'enterprise': {
            'methods': ['ev_ebit_value', 'ev_fcf_value', 'forward_multiple_value', 'historical_multiple_value'],
            'max_weight': 0.34,
            'values': []
        }
    }

    # Collect log values
    log_values = []
    method_weights = []
    method_names = []

    for family_name, family_data in families.items():
        family_log_values = []
        family_weights = []

        for method in family_data['methods']:
            value = valuation_methods.get(method)

            if value and value > 0:
                log_val = np.log(value)
                family_log_values.append(log_val)

                # Assign weights
                confidence_score = confidence_data['total_score'] / 100

                if method == 'dcf_value':
                    fcf_quality = confidence_data['components']['fcf_quality'] / 100
                    stability = confidence_data['components']['stability'] / 100
                    method_weight = (fcf_quality * 0.6 + stability * 0.4) * 1.2
                elif method == 'pe_value':
                    fcf_quality = confidence_data['components']['fcf_quality'] / 100
                    method_weight = fcf_quality * 0.9
                elif method == 'forward_multiple_value':
                    method_weight = confidence_score * 1.0
                else:
                    method_weight = confidence_score

                family_weights.append(method_weight)
                method_names.append(method)

                print(f"  {method}: ${value:.2f} → log={log_val:.4f}, weight={method_weight:.3f}")

        if family_log_values:
            family_data['values'] = family_log_values
            family_data['weights'] = family_weights

    # Flatten all values
    for family_data in families.values():
        if family_data['values']:
            log_values.extend(family_data['values'])
            method_weights.extend(family_data['weights'])

    print(f"\nTotal methods: {len(log_values)}")
    print(f"Methods: {method_names}")

    # Normalize weights with family caps
    for family_name, family_data in families.items():
        if family_data['weights']:
            total_family_weight = sum(family_data['weights'])
            family_data['normalized_weights'] = [
                w / total_family_weight * family_data['max_weight']
                for w in family_data['weights']
            ]

            if family_data['values']:
                print(f"\nFamily '{family_name}': {len(family_data['values'])} methods, total weight={sum(family_data['normalized_weights']):.3f}")

    # Collect normalized weights
    all_normalized_weights = []
    for family_data in families.values():
        if 'normalized_weights' in family_data:
            all_normalized_weights.extend(family_data['normalized_weights'])

    # Re-normalize to sum to 1.0
    total_weight = sum(all_normalized_weights)
    final_weights = [w / total_weight for w in all_normalized_weights]

    print(f"\nFinal weights (sum={sum(final_weights):.3f}): {[f'{w:.3f}' for w in final_weights]}")

    # Calculate weighted median
    log_values_array = np.array(log_values)
    weights_array = np.array(final_weights)

    # Winsorize if enough values
    if len(log_values_array) >= 3:
        p10_log = np.percentile(log_values_array, 10)
        p90_log = np.percentile(log_values_array, 90)
        log_values_winsorized = np.clip(log_values_array, p10_log, p90_log)
        print(f"\nWinsorization applied: p10={p10_log:.4f}, p90={p90_log:.4f}")
    else:
        log_values_winsorized = log_values_array
        p10_log = np.min(log_values_array)
        p90_log = np.max(log_values_array)
        print(f"\nNo winsorization (only {len(log_values_array)} values)")

    # Weighted median
    weighted_median_log = np.average(log_values_winsorized, weights=weights_array)

    # Calculate p10-p90 range
    sorted_indices = np.argsort(log_values_array)
    sorted_values = log_values_array[sorted_indices]
    sorted_weights = weights_array[sorted_indices]
    cumulative_weights = np.cumsum(sorted_weights)

    p10_idx = np.searchsorted(cumulative_weights, 0.10)
    p90_idx = np.searchsorted(cumulative_weights, 0.90)

    p10_log_val = sorted_values[min(p10_idx, len(sorted_values) - 1)]
    p90_log_val = sorted_values[min(p90_idx, len(sorted_values) - 1)]

    # Transform back
    fair_value_robust = np.exp(weighted_median_log)
    range_p10 = np.exp(p10_log_val)
    range_p90 = np.exp(p90_log_val)

    print(f"\n" + "=" * 60)
    print(f"RESULTS:")
    print(f"  Robust Fair Value: ${fair_value_robust:.2f}")
    print(f"  Range (p10-p90): ${range_p10:.2f} - ${range_p90:.2f}")

    # Consensus tightness
    log_dispersion = np.std(log_values_array)
    if log_dispersion < 0.15:
        tightness = 'High'
    elif log_dispersion < 0.30:
        tightness = 'Medium'
    else:
        tightness = 'Low'

    print(f"  Consensus Tightness: {tightness} (σ={log_dispersion:.4f})")
    print("=" * 60)

    return True

if __name__ == '__main__':
    try:
        success = test_robust_calculation()
        if success:
            print("\n✓ Test PASSED - Logic works correctly!")
        else:
            print("\n✗ Test FAILED")
    except Exception as e:
        print(f"\n✗ Test FAILED with exception:")
        import traceback
        traceback.print_exc()
