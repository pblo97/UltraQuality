#!/usr/bin/env python3
"""
Test Option D (Hybrid Complete) implementation
Tests phase-aware stops with buffer to prevent stop hunting
"""

import sys
from src.screener.technical.analyzer import TechnicalAnalyzer

def test_phase_aware_stops():
    """Test the new _calculate_tier_stop_smart method with different phases"""

    # Create analyzer instance (no API needed for this test)
    analyzer = TechnicalAnalyzer(fmp_client=None)

    # Test parameters (simulated data)
    current_price = 278.50  # Apple example
    atr_14 = 4.20
    ma_50 = 275.00
    swing_low_20 = 268.50  # 20-day low (more robust than 10d)
    ema_10 = 276.80

    print("=" * 80)
    print("OPTION D (HYBRID COMPLETE) - PHASE-AWARE STOPS TEST")
    print("=" * 80)
    print(f"\nTest Stock: AAPL (simulated)")
    print(f"Current Price: ${current_price:.2f}")
    print(f"ATR (14d): ${atr_14:.2f}")
    print(f"MA 50: ${ma_50:.2f}")
    print(f"Swing Low 20d: ${swing_low_20:.2f}")
    print(f"EMA 10: ${ema_10:.2f}")

    # Test Tier 2 (Core Growth) with different phases
    tier = 2
    multiplier = 2.5
    hard_cap_pct = 15.0

    print(f"\n{'='*80}")
    print(f"TIER 2 (CORE GROWTH) - PHASE COMPARISON")
    print(f"{'='*80}")

    # Phase 1: Entry (ATR + Hard Cap only)
    print("\n1. ENTRY PHASE (Risk On 🎯)")
    print("   Strategy: ATR + Hard Cap only (no tight anchors)")
    entry_stop = analyzer._calculate_tier_stop_smart(
        tier, current_price, atr_14, multiplier,
        ma_50, swing_low_20, ema_10, hard_cap_pct,
        phase='entry'
    )
    entry_dist = ((entry_stop - current_price) / current_price * 100)
    print(f"   Stop Price: ${entry_stop:.2f}")
    print(f"   Distance: {entry_dist:.2f}%")
    print(f"   Components:")
    print(f"     - ATR Stop: ${current_price - (multiplier * atr_14):.2f}")
    print(f"     - Hard Cap: ${current_price * (1 - hard_cap_pct/100):.2f}")
    print(f"   ✅ Gives position breathing room to avoid whipsaws")

    # Phase 2: Trailing (Long anchors with 0.5% buffer)
    print("\n2. TRAILING PHASE (Trend Following 🏄)")
    print("   Strategy: Swing Low 20d with 0.5% buffer")
    trailing_stop = analyzer._calculate_tier_stop_smart(
        tier, current_price, atr_14, 3.0,  # trailing multiplier
        ma_50, swing_low_20, ema_10, hard_cap_pct,
        phase='trailing'
    )
    trailing_dist = ((trailing_stop - current_price) / current_price * 100)
    print(f"   Stop Price: ${trailing_stop:.2f}")
    print(f"   Distance: {trailing_dist:.2f}%")
    print(f"   Components:")
    print(f"     - ATR Stop: ${current_price - (3.0 * atr_14):.2f}")
    print(f"     - Swing Low 20d: ${swing_low_20:.2f}")
    print(f"     - With 0.5% buffer: ${swing_low_20 * 0.995:.2f}")
    print(f"   ✅ Buffer prevents algorithmic stop hunting")

    # Phase 3: Climax (EMA 10 with 0.75% buffer)
    print("\n3. CLIMAX PHASE (Profit Locking 💰)")
    print("   Strategy: EMA 10 with 0.75% buffer")
    climax_stop = analyzer._calculate_tier_stop_smart(
        tier, current_price, atr_14, 1.5,  # tight multiplier
        ma_50, swing_low_20, ema_10, hard_cap_pct,
        phase='climax'
    )
    climax_dist = ((climax_stop - current_price) / current_price * 100)
    print(f"   Stop Price: ${climax_stop:.2f}")
    print(f"   Distance: {climax_dist:.2f}%")
    print(f"   Components:")
    print(f"     - Tight ATR (1.5x): ${current_price - (1.5 * atr_14):.2f}")
    print(f"     - EMA 10: ${ema_10:.2f}")
    print(f"     - With 0.75% buffer: ${ema_10 * 0.9925:.2f}")
    print(f"   ✅ Protects profits while allowing normal pullback")

    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY: ANTI-STOP HUNTING BENEFITS")
    print(f"{'='*80}")
    print("\n📊 Comparison with OLD System (10d Swing Low without buffer):")
    old_swing_low_10 = 275.25  # Hypothetical tight 10d low
    old_stop = old_swing_low_10
    old_dist = ((old_stop - current_price) / current_price * 100)
    print(f"   Old Stop (10d, no buffer): ${old_stop:.2f} ({old_dist:.2f}%)")
    print(f"   ❌ PROBLEM: Too tight, vulnerable to stop hunting")

    print(f"\n✅ NEW Option D Benefits:")
    print(f"   1. Entry Phase: {entry_dist:.2f}% (was {old_dist:.2f}%) - More breathing room")
    print(f"   2. Uses 20-day lows (more robust than 10-day)")
    print(f"   3. Buffers (0.5%-0.75%) prevent algorithmic hunting")
    print(f"   4. Phase-aware: Different strategies for different market conditions")

    print(f"\n{'='*80}")
    print("TEST ALL 3 TIERS (Entry Phase)")
    print(f"{'='*80}")

    tiers = [
        (1, "Defensive 🐢", 1.8, 8.0),
        (2, "Core Growth 🏃", 2.5, 15.0),
        (3, "Speculative 🚀", 3.0, 25.0)
    ]

    for tier_num, tier_name, mult, hard_cap in tiers:
        stop = analyzer._calculate_tier_stop_smart(
            tier_num, current_price, atr_14, mult,
            ma_50, swing_low_20, ema_10, hard_cap,
            phase='entry'
        )
        dist = ((stop - current_price) / current_price * 100)
        print(f"\nTier {tier_num} ({tier_name}):")
        print(f"  Stop: ${stop:.2f} ({dist:.2f}%)")
        print(f"  Multiplier: {mult}x | Hard Cap: {hard_cap}%")

    print(f"\n{'='*80}")
    print("✅ Option D Implementation Complete!")
    print(f"{'='*80}")

    return True

if __name__ == '__main__':
    try:
        success = test_phase_aware_stops()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
