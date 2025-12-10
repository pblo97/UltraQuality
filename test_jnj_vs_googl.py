#!/usr/bin/env python3
"""
Test específico para comparar JNJ vs GOOGL y entender por qué tienen el mismo stop.
"""

import sys
sys.path.insert(0, 'src')

def simulate_stop_calculation(
    symbol, price, beta, volatility, sector,
    atr, ma_50, swing_low, ema_20
):
    """Simular el cálculo de stop loss sin API."""

    print(f"\n{'='*70}")
    print(f"{symbol} - Simulación de Stop Loss")
    print(f"{'='*70}")

    # PASO 1: Clasificación de Tier
    print(f"\n📊 DATOS DE ENTRADA:")
    print(f"   Precio actual: ${price:.2f}")
    print(f"   Beta: {beta:.2f}")
    print(f"   Volatilidad: {volatility:.1f}%")
    print(f"   Sector: {sector}")
    print(f"   ATR (14d): ${atr:.2f} ({atr/price*100:.2f}% del precio)")
    print(f"   MA 50: ${ma_50:.2f} ({(ma_50-price)/price*100:+.2f}%)")
    print(f"   Swing Low (10d): ${swing_low:.2f} ({(swing_low-price)/price*100:+.2f}%)")
    print(f"   EMA 20: ${ema_20:.2f} ({(ema_20-price)/price*100:+.2f}%)")

    # PASO 2: Clasificar tier
    if beta < 0.95 and volatility < 25:
        tier = 1
        tier_name = "Tier 1: Defensivo 🐢"
        initial_mult = 1.8
        hard_cap_pct = 8.0
        anchor_name = "MA 50"
        anchor_value = ma_50
    elif beta > 1.15 or volatility > 45:
        tier = 3
        tier_name = "Tier 3: Especulativo 🚀"
        initial_mult = 3.0
        hard_cap_pct = 25.0
        anchor_name = "EMA 20"
        anchor_value = ema_20
    else:
        tier = 2
        tier_name = "Tier 2: Core Growth 🏃"
        initial_mult = 2.5
        hard_cap_pct = 15.0
        anchor_name = "Swing Low 10d"
        anchor_value = swing_low

    print(f"\n🎯 CLASIFICACIÓN:")
    print(f"   Tier: {tier} - {tier_name}")
    print(f"   Multiplicador Inicial: {initial_mult}x")
    print(f"   Hard Cap: -{hard_cap_pct}%")
    print(f"   Ancla Técnica: {anchor_name}")

    # PASO 3: Calcular componentes del stop
    atr_stop = price - (initial_mult * atr)
    hard_cap_stop = price * (1 - hard_cap_pct / 100)
    anchor_stop = anchor_value if anchor_value > 0 else price * (1 - hard_cap_pct / 100)

    # PASO 4: Stop final = MAX de los 3
    final_stop = max(hard_cap_stop, atr_stop, anchor_stop)

    # Determinar cuál dominó
    if final_stop == hard_cap_stop:
        dominant = f"Hard Cap (-{hard_cap_pct}%)"
    elif final_stop == atr_stop:
        dominant = f"ATR-based ({initial_mult}x)"
    else:
        dominant = f"Anchor ({anchor_name})"

    # Calcular distancias
    atr_distance_pct = ((atr_stop - price) / price * 100)
    hard_cap_distance_pct = -hard_cap_pct
    anchor_distance_pct = ((anchor_stop - price) / price * 100)
    final_distance_pct = ((final_stop - price) / price * 100)

    print(f"\n🔢 CÁLCULO DEL STOP:")
    print(f"   1. ATR-based ({initial_mult}x ATR):  ${atr_stop:7.2f}  ({atr_distance_pct:+6.2f}%)")
    print(f"   2. Hard Cap (-{hard_cap_pct}%):       ${hard_cap_stop:7.2f}  ({hard_cap_distance_pct:+6.2f}%)")
    print(f"   3. {anchor_name:20s}: ${anchor_stop:7.2f}  ({anchor_distance_pct:+6.2f}%)")
    print(f"\n   ➤ STOP FINAL = MAX(ATR, HardCap, Anchor)")
    print(f"   ➤ ${final_stop:.2f}  ({final_distance_pct:+.2f}%)")
    print(f"   ➤ Dominado por: {dominant}")

    return {
        'tier': tier,
        'tier_name': tier_name,
        'final_stop': final_stop,
        'final_distance_pct': final_distance_pct,
        'dominant': dominant
    }


def main():
    print("="*70)
    print("COMPARACIÓN: JNJ vs GOOGL - Stop Loss Calculation")
    print("="*70)

    # Datos realistas de JNJ
    jnj_result = simulate_stop_calculation(
        symbol="JNJ",
        price=150.00,
        beta=0.70,
        volatility=15.0,  # Baja volatilidad
        sector="Healthcare",
        atr=3.00,         # ATR bajo
        ma_50=148.00,     # MA50 cerca del precio (-1.3%)
        swing_low=145.00,
        ema_20=149.00
    )

    # Datos realistas de GOOGL
    googl_result = simulate_stop_calculation(
        symbol="GOOGL",
        price=140.00,
        beta=1.05,
        volatility=28.0,  # Volatilidad moderada
        sector="Technology",
        atr=4.00,         # ATR más alto
        ma_50=138.00,
        swing_low=135.00,  # Swing low más bajo (-3.6%)
        ema_20=139.00
    )

    # Comparación final
    print(f"\n{'='*70}")
    print("COMPARACIÓN FINAL")
    print(f"{'='*70}")

    print(f"\nJNJ:")
    print(f"  Tier: {jnj_result['tier']} - {jnj_result['tier_name']}")
    print(f"  Stop: ${jnj_result['final_stop']:.2f} ({jnj_result['final_distance_pct']:+.2f}%)")
    print(f"  Dominado por: {jnj_result['dominant']}")

    print(f"\nGOOGL:")
    print(f"  Tier: {googl_result['tier']} - {googl_result['tier_name']}")
    print(f"  Stop: ${googl_result['final_stop']:.2f} ({googl_result['final_distance_pct']:+.2f}%)")
    print(f"  Dominado por: {googl_result['dominant']}")

    # Análisis
    print(f"\n{'='*70}")
    print("ANÁLISIS")
    print(f"{'='*70}")

    if jnj_result['tier'] == googl_result['tier']:
        print("\n❌ PROBLEMA ENCONTRADO:")
        print("   ¡Ambos están en el MISMO TIER!")
        print("   Esto no debería pasar si Beta y Volatilidad son correctos.")
        print("\n   Verificar:")
        print("   - ¿Es correcta la Beta de GOOGL? (debería ser ~1.0-1.1)")
        print("   - ¿Es correcta la Volatilidad de GOOGL? (debería ser 25-35%)")
    else:
        print("\n✅ Clasificación correcta:")
        print(f"   JNJ está en Tier {jnj_result['tier']}")
        print(f"   GOOGL está en Tier {googl_result['tier']}")

    stop_diff = abs(jnj_result['final_distance_pct'] - googl_result['final_distance_pct'])

    if stop_diff < 1.0:
        print(f"\n⚠️  Los stops son MUY SIMILARES (diferencia: {stop_diff:.2f}%)")
        print("\n   POSIBLES CAUSAS:")
        print("   1. Las anclas técnicas están a distancias similares del precio")
        print(f"      - JNJ: {jnj_result['dominant']}")
        print(f"      - GOOGL: {googl_result['dominant']}")
        print("\n   2. Ambas anclas están dominando el cálculo (son el MAX)")
        print("\n   SOLUCIÓN:")
        print("   - Esto es NORMAL si las anclas están cerca del precio")
        print("   - Los stops se separarán cuando las condiciones técnicas cambien")
        print("   - En fases de lifecycle diferentes (Breakeven, Climax), también serán diferentes")
    elif stop_diff < 3.0:
        print(f"\n✅ Los stops son DIFERENTES pero cercanos (diferencia: {stop_diff:.2f}%)")
        print("   Esto es normal y esperado.")
    else:
        print(f"\n✅ Los stops son SIGNIFICATIVAMENTE DIFERENTES (diferencia: {stop_diff:.2f}%)")
        print("   El sistema está funcionando correctamente.")

    print(f"\n{'='*70}")
    print("RECOMENDACIONES")
    print(f"{'='*70}")
    print("\n1. Verificar con datos REALES de API:")
    print("   - Beta actual de JNJ y GOOGL")
    print("   - Volatilidad calculada (últimos 12 meses)")
    print("   - Valores de MA50, Swing Low, EMA20")
    print("\n2. Si los stops son similares con datos reales:")
    print("   - Es porque las anclas técnicas están cerca del precio")
    print("   - Esto cambiará cuando las condiciones cambien")
    print("\n3. Para hacer stops MÁS DIFERENTES entre tiers:")
    print("   - Aumentar diferencia entre multipliers (ej: 1.5x, 3.5x, 5.0x)")
    print("   - Usar anclas más separadas (ej: MA20, MA100, EMA50)")
    print("   - Ajustar hard caps (ej: 5%, 15%, 30%)")

if __name__ == '__main__':
    main()
