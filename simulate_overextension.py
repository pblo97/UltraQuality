#!/usr/bin/env python3
"""
Simulate overextension risk calculation with example data.
Shows how the system works WITHOUT needing API key.
"""

def calculate_overextension_risk(distance_ma200, volatility, momentum_1m, momentum_6m):
    """
    Simulate the _detect_overextension_risk method.
    Returns: (risk_score, warnings)
    """
    risk_score = 0
    warnings = []

    # 1. Distance from MA200 (most important)
    abs_distance = abs(distance_ma200)

    if abs_distance > 60:
        risk_score += 4
        warnings.append({
            'type': 'HIGH',
            'message': f'EXTREME overextension: {distance_ma200:+.1f}% from MA200 (>60%). High probability of 20-40% pullback.'
        })
    elif abs_distance > 50:
        risk_score += 3
        warnings.append({
            'type': 'HIGH',
            'message': f'Severe overextension: {distance_ma200:+.1f}% from MA200 (>50%). Expect 15-30% correction soon.'
        })
    elif abs_distance > 40:
        risk_score += 2
        warnings.append({
            'type': 'MEDIUM',
            'message': f'Significant overextension: {distance_ma200:+.1f}% from MA200 (>40%). Possible 10-20% pullback.'
        })
    elif abs_distance > 30:
        risk_score += 1
        warnings.append({
            'type': 'LOW',
            'message': f'Moderate overextension: {distance_ma200:+.1f}% from MA200 (>30%). Monitor for reversal signals.'
        })

    # 2. Volatility + Recent momentum (parabolic move detection)
    if volatility > 40 and momentum_1m > 15:
        risk_score += 2
        warnings.append({
            'type': 'HIGH',
            'message': f'Parabolic move detected: +{momentum_1m:.1f}% in 1M with {volatility:.1f}% volatility. Crash risk elevated.'
        })
    elif volatility > 35 and momentum_1m > 10:
        risk_score += 1
        warnings.append({
            'type': 'MEDIUM',
            'message': f'High volatility momentum: +{momentum_1m:.1f}% in 1M with {volatility:.1f}% vol. Risk of sharp reversal.'
        })

    # 3. Extreme momentum (blow-off top detection)
    if momentum_1m > 25:
        risk_score += 1
        warnings.append({
            'type': 'HIGH',
            'message': f'Blow-off top signal: +{momentum_1m:.1f}% in just 1 month. Likely unsustainable.'
        })

    # 4. Exhaustion check
    if momentum_6m > 30 and momentum_1m < 0:
        warnings.append({
            'type': 'MEDIUM',
            'message': f'Momentum exhaustion: Strong 6M (+{momentum_6m:.1f}%) but negative 1M ({momentum_1m:+.1f}%). Trend may be weakening.'
        })

    return risk_score, warnings


# Example stocks with different overextension levels
examples = [
    {
        'symbol': 'COST (Costco)',
        'distance_ma200': 15.2,  # 15% above MA200 - NOT overextended
        'volatility': 22.5,
        'momentum_1m': 3.2,
        'momentum_6m': 12.5,
    },
    {
        'symbol': 'AAPL (Apple)',
        'distance_ma200': 25.8,  # 26% above MA200 - slightly elevated
        'volatility': 28.3,
        'momentum_1m': 5.1,
        'momentum_6m': 18.2,
    },
    {
        'symbol': 'NVDA (NVIDIA) - Example 1',
        'distance_ma200': 42.5,  # 43% above MA200 - OVEREXTENDED
        'volatility': 45.2,
        'momentum_1m': 12.3,
        'momentum_6m': 35.8,
    },
    {
        'symbol': 'NVDA (NVIDIA) - Example 2 (más extremo)',
        'distance_ma200': 58.0,  # 58% above MA200 - EXTREME (como GOOG antes)
        'volatility': 48.5,
        'momentum_1m': 18.5,
        'momentum_6m': 52.3,
    },
    {
        'symbol': 'MSTR (MicroStrategy) - Parabolic',
        'distance_ma200': 75.2,  # 75% above MA200 - EXTREME
        'volatility': 85.3,      # Very high volatility
        'momentum_1m': 28.7,     # Parabolic 1M move
        'momentum_6m': 95.5,
    },
]

print("="*80)
print("OVEREXTENSION RISK SIMULATION")
print("="*80)
print("\nEsto muestra cómo funciona el cálculo de overextension risk")
print("con datos de ejemplo (no requiere API key)\n")

for example in examples:
    symbol = example['symbol']
    distance = example['distance_ma200']
    volatility = example['volatility']
    mom_1m = example['momentum_1m']
    mom_6m = example['momentum_6m']

    print("="*80)
    print(f"📊 {symbol}")
    print("="*80)

    print(f"\n📏 Inputs:")
    print(f"   Distance from MA200: {distance:+.1f}%")
    print(f"   Volatility (12M):    {volatility:.1f}%")
    print(f"   Momentum 1M:         {mom_1m:+.1f}%")
    print(f"   Momentum 6M:         {mom_6m:+.1f}%")

    # Calculate
    risk_score, warnings = calculate_overextension_risk(distance, volatility, mom_1m, mom_6m)

    # Determine level
    if risk_score >= 5:
        level = 'EXTREME 🔴🔴🔴'
    elif risk_score >= 3:
        level = 'HIGH 🔴🔴'
    elif risk_score >= 1:
        level = 'MEDIUM 🟡'
    else:
        level = 'LOW ✅'

    print(f"\n⚠️  RESULT:")
    print(f"   Overextension Risk: {risk_score}/7")
    print(f"   Level: {level}")

    if warnings:
        print(f"\n⚠️  Warnings ({len(warnings)}):")
        for w in warnings:
            icon = '🔴' if w['type'] == 'HIGH' else '🟡' if w['type'] == 'MEDIUM' else '🔵'
            print(f"   {icon} [{w['type']}] {w['message']}")

    # Show what strategy would be recommended
    print(f"\n🎯 Recommended Entry Strategy:")
    if risk_score >= 5:
        print(f"   SCALE-IN (3 tranches): 25% / 35% / 40%")
        print(f"   Rationale: EXTREME overextension - wait for pullback")
    elif risk_score >= 3:
        print(f"   SCALE-IN (2 tranches): 60% / 40%")
        print(f"   Rationale: HIGH overextension - reserve capital")
    else:
        print(f"   FULL ENTRY NOW")
        print(f"   Rationale: Low overextension - favorable setup")

    print()

print("="*80)
print("CONCLUSIÓN")
print("="*80)
print("""
Si ves "0/7 LOW" en Streamlit, significa que el stock NO está sobreextendido.

Esto es CORRECTO para stocks como:
- COST (Costco): +15% sobre MA200 → Risk 0/7 ✅
- XOM (Exxon): +10-20% sobre MA200 → Risk 0/7 ✅
- JPM (JP Morgan): +5-15% sobre MA200 → Risk 0/7 ✅

Para ver el Risk Management en acción, necesitas stocks SOBREEXTENDIDOS:
- Distance from MA200 > 40%
- O con momentum parabólico

Ejemplo: Si NVDA está +58% sobre MA200 → Risk 4-5/7 (HIGH/EXTREME)

¿Qué % de MA200 tiene el stock que probaste en Streamlit?
Mira en "Trend Analysis" → "Distance from MA200"
""")
