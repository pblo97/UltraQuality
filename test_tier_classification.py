#!/usr/bin/env python3
"""
Análisis del flujo de clasificación de tiers y cálculo de stop loss.
Compara JNJ (defensivo) vs GOOGL (growth) para entender por qué tienen mismo stop.
"""

import sys
sys.path.insert(0, 'src')

# Simular los cálculos sin API
def analyze_tier_classification():
    """Analizar la lógica de clasificación de tiers."""

    print("="*80)
    print("ANÁLISIS DE CLASIFICACIÓN DE TIERS")
    print("="*80)

    # Ejemplos de clasificación
    test_cases = [
        # (symbol, volatility, beta, sector, expected_tier)
        ("JNJ", 15.0, 0.70, "Healthcare", 1),           # Defensivo
        ("GOOGL", 28.0, 1.05, "Technology", 2),         # Core Growth
        ("NVDA", 55.0, 1.80, "Technology", 3),          # Especulativo
        ("KO", 18.0, 0.60, "Consumer Defensive", 1),   # Defensivo
        ("TSLA", 60.0, 2.10, "Consumer Cyclical", 3),  # Especulativo
    ]

    print("\nLÓGICA DE CLASIFICACIÓN:")
    print("  Tier 1: Beta < 0.95 AND Vol < 25%")
    print("  Tier 2: Beta 0.95-1.15 AND Vol 25-45%")
    print("  Tier 3: Beta > 1.15 OR Vol > 45%")
    print()

    for symbol, vol, beta, sector, expected in test_cases:
        # Simular clasificación
        if beta is not None:
            if beta < 0.95 and vol < 25:
                tier = 1
                tier_name = "Tier 1: Defensivo 🐢"
            elif beta > 1.15 or vol > 45:
                tier = 3
                tier_name = "Tier 3: Especulativo 🚀"
            else:
                tier = 2
                tier_name = "Tier 2: Core Growth 🏃"
        else:
            if vol < 25:
                tier = 1
                tier_name = "Tier 1: Defensivo 🐢"
            elif vol > 45:
                tier = 3
                tier_name = "Tier 3: Especulativo 🚀"
            else:
                tier = 2
                tier_name = "Tier 2: Core Growth 🏃"

        status = "✅" if tier == expected else "❌"
        print(f"{status} {symbol:6s} (Vol={vol:5.1f}%, Beta={beta:4.2f}): {tier_name}")
        print(f"         Sector: {sector}")
        print()

def analyze_stop_calculation():
    """Analizar el cálculo de stop loss para diferentes tiers."""

    print("="*80)
    print("ANÁLISIS DE CÁLCULO DE STOP LOSS")
    print("="*80)

    # Simular JNJ vs GOOGL
    scenarios = [
        {
            'symbol': 'JNJ',
            'price': 150.00,
            'tier': 1,
            'atr': 3.00,  # ATR bajo (stock estable)
            'ma_50': 148.00,  # Cerca del precio
            'swing_low': 145.00,
            'ema_20': 149.00,
            'multiplier': 1.8,
            'hard_cap_pct': 8.0,
        },
        {
            'symbol': 'GOOGL',
            'price': 140.00,
            'tier': 2,
            'atr': 4.00,  # ATR más alto (más volátil)
            'ma_50': 138.00,
            'swing_low': 135.00,  # Swing low más bajo
            'ema_20': 139.00,
            'multiplier': 2.5,
            'hard_cap_pct': 15.0,
        }
    ]

    print("\nFÓRMULAS POR TIER:")
    print("  Tier 1: Stop = MAX(Price - 1.8*ATR, Price*0.92, SMA_50)")
    print("  Tier 2: Stop = MAX(Price - 2.5*ATR, Price*0.85, Swing_Low_10d)")
    print("  Tier 3: Stop = MAX(Price - 3.0*ATR, Price*0.75, EMA_20)")
    print()

    for scenario in scenarios:
        symbol = scenario['symbol']
        price = scenario['price']
        tier = scenario['tier']
        atr = scenario['atr']
        ma_50 = scenario['ma_50']
        swing_low = scenario['swing_low']
        ema_20 = scenario['ema_20']
        multiplier = scenario['multiplier']
        hard_cap_pct = scenario['hard_cap_pct']

        print(f"\n{'='*60}")
        print(f"{symbol} (Tier {tier})")
        print(f"{'='*60}")
        print(f"Precio actual: ${price:.2f}")
        print(f"ATR (14d): ${atr:.2f}")
        print(f"MA 50: ${ma_50:.2f}")
        print(f"Swing Low (10d): ${swing_low:.2f}")
        print(f"EMA 20: ${ema_20:.2f}")
        print()

        # Calcular los 3 componentes del stop
        atr_stop = price - (multiplier * atr)
        hard_cap_stop = price * (1 - hard_cap_pct / 100)

        # Anchor depende del tier
        if tier == 1:
            anchor_stop = ma_50
            anchor_name = "SMA 50"
        elif tier == 2:
            anchor_stop = swing_low
            anchor_name = "Swing Low 10d"
        else:
            anchor_stop = ema_20
            anchor_name = "EMA 20"

        # Calcular stop final (MAX de los 3)
        final_stop = max(hard_cap_stop, atr_stop, anchor_stop)

        # Determinar cuál dominó
        if final_stop == hard_cap_stop:
            dominant = f"Hard Cap ({hard_cap_pct}%)"
        elif final_stop == atr_stop:
            dominant = f"ATR-based ({multiplier}x)"
        else:
            dominant = f"Anchor ({anchor_name})"

        # Calcular distancias
        atr_distance_pct = ((atr_stop - price) / price * 100)
        hard_cap_distance_pct = -hard_cap_pct
        anchor_distance_pct = ((anchor_stop - price) / price * 100)
        final_distance_pct = ((final_stop - price) / price * 100)

        print(f"COMPONENTES DEL STOP:")
        print(f"  1. ATR-based ({multiplier}x):  ${atr_stop:7.2f}  ({atr_distance_pct:+6.2f}%)")
        print(f"  2. Hard Cap ({hard_cap_pct}%):    ${hard_cap_stop:7.2f}  ({hard_cap_distance_pct:+6.2f}%)")
        print(f"  3. {anchor_name:16s}: ${anchor_stop:7.2f}  ({anchor_distance_pct:+6.2f}%)")
        print()
        print(f"STOP FINAL = MAX de los 3:")
        print(f"  ➤ ${final_stop:.2f}  ({final_distance_pct:+.2f}%)")
        print(f"  ➤ Dominado por: {dominant}")
        print()

def analyze_problem():
    """Analizar el problema reportado."""

    print("="*80)
    print("ANÁLISIS DEL PROBLEMA: ¿Por qué JNJ y GOOGL tienen mismo stop?")
    print("="*80)
    print()

    print("POSIBLES CAUSAS:")
    print()

    print("1️⃣  MISMA CLASIFICACIÓN DE TIER")
    print("   Si ambos se clasifican en el mismo tier, usarán:")
    print("   - Mismo multiplicador ATR")
    print("   - Mismo hard cap")
    print("   - Misma ancla técnica (tipo)")
    print()

    print("2️⃣  VALORES TÉCNICOS SIMILARES (relativamente)")
    print("   Aunque estén en diferentes tiers, si sus valores")
    print("   relativos al precio son similares:")
    print("   - ATR/Price ratio similar")
    print("   - Ancla/Price ratio similar")
    print("   Entonces los stops pueden ser parecidos.")
    print()

    print("3️⃣  PROBLEMA EN LA LÓGICA DE CÁLCULO")
    print("   El código actual calcula:")
    print()
    print("   tier_1_stop = _calculate_tier_stop(1, price, atr, 1.8, ma_50, swing_low, ema_20, 8.0)")
    print("   tier_2_stop = _calculate_tier_stop(2, price, atr, 2.5, ma_50, swing_low, ema_20, 15.0)")
    print("   tier_3_stop = _calculate_tier_stop(3, price, atr, 3.0, ma_50, swing_low, ema_20, 25.0)")
    print()
    print("   PROBLEMA IDENTIFICADO:")
    print("   ❌ Todos los tiers reciben los MISMOS valores de ma_50, swing_low, ema_20")
    print("   ❌ Aunque el tier selecciona cuál usar, los valores son idénticos")
    print()
    print("   Esto es CORRECTO según la especificación, pero puede causar que:")
    print("   - Si ma_50 está muy cerca del precio (ej: -1.3%)")
    print("   - Y swing_low también está cerca (ej: -3.6%)")
    print("   - Ambos stops pueden ser dominados por sus anclas técnicas")
    print("   - Y resultar en valores similares")
    print()

    print("4️⃣  ANCLA TÉCNICA DOMINANDO EL CÁLCULO")
    print("   Si para ambos activos, la ancla técnica es el valor MÁS ALTO")
    print("   (más cercano al precio), entonces el stop será esa ancla,")
    print("   sin importar el tier.")
    print()
    print("   Ejemplo:")
    print("   JNJ (Tier 1):")
    print("     - ATR stop: -5.4%  = $141.90")
    print("     - Hard cap: -8.0%  = $138.00")
    print("     - MA 50:    -1.3%  = $148.00  ← DOMINA (más alto)")
    print("     → Stop final: $148.00")
    print()
    print("   GOOGL (Tier 2):")
    print("     - ATR stop: -7.1%  = $130.00")
    print("     - Hard cap: -15.0% = $119.00")
    print("     - Swing Low:-3.6%  = $135.00  ← DOMINA (más alto)")
    print("     → Stop final: $135.00")
    print()
    print("   Si ma_50 para JNJ está a -1.3% y swing_low para GOOGL")
    print("   está a -3.6%, los stops son DIFERENTES. Pero si ambos")
    print("   están cerca (ej: -2%), entonces serían similares.")
    print()

    print("="*80)
    print("SOLUCIÓN PROPUESTA:")
    print("="*80)
    print()
    print("El código está implementado CORRECTAMENTE según tu especificación.")
    print("Si JNJ y GOOGL tienen stops similares, es porque:")
    print()
    print("  1. Sus anclas técnicas están a distancias similares del precio")
    print("  2. Las anclas están dominando el cálculo (son el MAX)")
    print()
    print("OPCIONES:")
    print()
    print("A) VERIFICAR DATOS REALES")
    print("   Ejecutar con datos reales de JNJ y GOOGL para ver:")
    print("   - ¿En qué tier se clasifican?")
    print("   - ¿Cuáles son sus valores de ATR, MA50, Swing Low?")
    print("   - ¿Qué componente está dominando?")
    print()
    print("B) AJUSTAR FÓRMULAS SI ES NECESARIO")
    print("   Si quieres que los tiers tengan stops MÁS DIFERENTES:")
    print("   - Ajustar los multiplicadores (ej: 1.5x, 3.0x, 4.5x)")
    print("   - Usar diferentes anclas base (ej: MA20, MA50, MA100)")
    print("   - Cambiar hard caps (ej: 5%, 12%, 20%)")
    print()

if __name__ == '__main__':
    analyze_tier_classification()
    print("\n\n")
    analyze_stop_calculation()
    print("\n\n")
    analyze_problem()
