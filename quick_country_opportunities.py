#!/usr/bin/env python3
"""
Análisis Rápido de Oportunidades por País (Quick Version)

Versión ligera que usa llamadas API rápidas para identificar
países con mejores oportunidades técnicas sin ejecutar el screener completo.

Analiza:
- Número de acciones disponibles por mercado
- Distribución de market cap y volumen
- Métricas agregadas de mercado
- Momentum general del mercado
"""

import os
import sys
import pandas as pd
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'screener'))

from ingest import FMPClient
import yaml

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Mercados soportados
MARKETS = {
    'US': {'name': '🇺🇸 Estados Unidos', 'country': 'US', 'exchanges': ['NYSE', 'NASDAQ']},
    'CA': {'name': '🇨🇦 Canadá', 'country': 'CA', 'exchanges': ['TSX']},
    'BR': {'name': '🇧🇷 Brasil', 'country': 'BR', 'exchanges': ['SAO']},
    'GB': {'name': '🇬🇧 Reino Unido', 'country': 'GB', 'exchanges': ['LSE']},
    'DE': {'name': '🇩🇪 Alemania', 'country': 'DE', 'exchanges': ['XETRA']},
    'IN': {'name': '🇮🇳 India', 'country': 'IN', 'exchanges': ['NSE']},
    'HK': {'name': '🇨🇳 Hong Kong', 'country': 'HK', 'exchanges': ['HKSE']},
    'JP': {'name': '🇯🇵 Japón', 'country': 'JP', 'exchanges': ['JPX']},
}


def analyze_market_quick(fmp_client: FMPClient, country_code: str, market_info: Dict) -> Dict:
    """
    Análisis rápido de un mercado usando stock-screener endpoint.

    Args:
        fmp_client: Cliente FMP
        country_code: Código del país
        market_info: Información del mercado

    Returns:
        Diccionario con métricas del mercado
    """
    logger.info(f"Analizando {market_info['name']}...")

    try:
        # Obtener acciones del mercado con filtros mínimos
        stocks = fmp_client.get_stock_screener(
            market_cap_more_than=500_000_000,  # $500M mínimo
            volume_more_than=1_000_000,  # $1M volumen mínimo
            country=country_code,
            limit=5000
        )

        if not stocks:
            logger.warning(f"No se encontraron acciones para {country_code}")
            return None

        # Convertir a DataFrame para análisis
        df = pd.DataFrame(stocks)

        # Análisis básico
        total_stocks = len(df)

        # Filtrar por calidad mínima (si disponible)
        quality_stocks = 0
        if 'beta' in df.columns:
            # Beta < 1.5 = menos volátiles
            quality_stocks = len(df[df['beta'] < 1.5])

        # Analizar market cap
        avg_market_cap = 0
        median_market_cap = 0
        large_caps = 0
        mid_caps = 0
        small_caps = 0

        if 'marketCap' in df.columns:
            df['marketCap'] = pd.to_numeric(df['marketCap'], errors='coerce')
            avg_market_cap = df['marketCap'].mean()
            median_market_cap = df['marketCap'].median()

            # Clasificación
            large_caps = len(df[df['marketCap'] >= 10_000_000_000])  # $10B+
            mid_caps = len(df[(df['marketCap'] >= 2_000_000_000) &
                             (df['marketCap'] < 10_000_000_000)])  # $2B-$10B
            small_caps = len(df[df['marketCap'] < 2_000_000_000])  # < $2B

        # Analizar volumen
        avg_volume = 0
        high_liquidity = 0

        if 'volume' in df.columns:
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
            avg_volume = df['volume'].mean()
            high_liquidity = len(df[df['volume'] >= 5_000_000])  # $5M+ diario

        # Analizar cambio de precio (si disponible)
        avg_price_change = 0
        positive_momentum = 0

        if 'changesPercentage' in df.columns:
            df['changesPercentage'] = pd.to_numeric(df['changesPercentage'], errors='coerce')
            avg_price_change = df['changesPercentage'].mean()
            positive_momentum = len(df[df['changesPercentage'] > 0])

        # Calcular opportunity score
        opportunity_score = calculate_quick_opportunity_score(
            total_stocks=total_stocks,
            large_caps=large_caps,
            mid_caps=mid_caps,
            high_liquidity=high_liquidity,
            positive_momentum_pct=(positive_momentum / total_stocks * 100) if total_stocks > 0 else 0,
            avg_price_change=avg_price_change
        )

        # Top stocks por market cap
        top_stocks = []
        if 'marketCap' in df.columns and 'symbol' in df.columns:
            df_sorted = df.sort_values('marketCap', ascending=False)
            top_stocks = df_sorted[['symbol', 'companyName', 'marketCap', 'changesPercentage']].head(5).to_dict('records')

        return {
            'country_code': country_code,
            'country_name': market_info['name'],
            'total_stocks': total_stocks,
            'large_caps': large_caps,
            'mid_caps': mid_caps,
            'small_caps': small_caps,
            'high_liquidity': high_liquidity,
            'avg_market_cap': round(avg_market_cap, 0),
            'median_market_cap': round(median_market_cap, 0),
            'avg_volume': round(avg_volume, 0),
            'avg_price_change': round(avg_price_change, 2),
            'positive_momentum': positive_momentum,
            'positive_momentum_pct': round((positive_momentum / total_stocks * 100), 1) if total_stocks > 0 else 0,
            'opportunity_score': opportunity_score,
            'top_stocks': top_stocks
        }

    except Exception as e:
        logger.error(f"Error analizando {country_code}: {e}")
        return None


def calculate_quick_opportunity_score(total_stocks: int, large_caps: int,
                                     mid_caps: int, high_liquidity: int,
                                     positive_momentum_pct: float,
                                     avg_price_change: float) -> float:
    """
    Calcula un score rápido de oportunidad basado en:
    - Tamaño del mercado (30%)
    - Liquidez (20%)
    - Momentum positivo (30%)
    - Cambio de precio promedio (20%)
    """
    # Normalizar métricas
    market_size_score = min(100, (total_stocks / 1000) * 100)  # 1000 stocks = 100 pts
    liquidity_score = min(100, (high_liquidity / total_stocks * 100) * 2) if total_stocks > 0 else 0
    momentum_score = positive_momentum_pct
    price_change_score = min(100, max(0, (avg_price_change + 10) * 5))  # -10% to +10% = 0-100

    # Calcular score ponderado
    score = (
        market_size_score * 0.30 +
        liquidity_score * 0.20 +
        momentum_score * 0.30 +
        price_change_score * 0.20
    )

    return round(score, 1)


def generate_quick_report(results: List[Dict], output_dir: str):
    """
    Genera reporte rápido de oportunidades.
    """
    # Filtrar resultados válidos
    valid_results = [r for r in results if r is not None]

    if not valid_results:
        logger.error("No hay resultados válidos")
        return

    # Ordenar por opportunity_score
    valid_results.sort(key=lambda x: x['opportunity_score'], reverse=True)

    # Generar reporte
    report_path = f"{output_dir}/quick_opportunities_report.txt"

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("ANÁLISIS RÁPIDO DE OPORTUNIDADES POR PAÍS\n")
        f.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")

        # Resumen ejecutivo
        f.write("📊 RESUMEN EJECUTIVO\n")
        f.write("-" * 80 + "\n")
        f.write(f"Países analizados: {len(valid_results)}\n")
        f.write(f"Total acciones disponibles: {sum(r['total_stocks'] for r in valid_results):,}\n")
        f.write(f"Acciones de alta liquidez: {sum(r['high_liquidity'] for r in valid_results):,}\n")
        f.write(f"Large caps (>$10B): {sum(r['large_caps'] for r in valid_results):,}\n\n")

        # Ranking
        f.write("🏆 RANKING DE PAÍSES POR OPORTUNIDADES\n")
        f.write("-" * 80 + "\n\n")

        for i, result in enumerate(valid_results, 1):
            f.write(f"{i}. {result['country_name']} ({result['country_code']})\n")
            f.write(f"   📈 Opportunity Score: {result['opportunity_score']:.1f}/100\n")
            f.write(f"   📊 Total acciones: {result['total_stocks']:,}\n")
            f.write(f"   💰 Large caps: {result['large_caps']} | Mid caps: {result['mid_caps']} | Small caps: {result['small_caps']}\n")
            f.write(f"   💧 Alta liquidez: {result['high_liquidity']} ({(result['high_liquidity']/result['total_stocks']*100):.1f}%)\n")
            f.write(f"   🚀 Momentum positivo: {result['positive_momentum']} ({result['positive_momentum_pct']:.1f}%)\n")
            f.write(f"   📉 Cambio precio promedio: {result['avg_price_change']:.2f}%\n")

            if result['top_stocks']:
                f.write(f"\n   🌟 Top 3 Empresas por Market Cap:\n")
                for stock in result['top_stocks'][:3]:
                    symbol = stock.get('symbol', 'N/A')
                    name = stock.get('companyName', 'N/A')[:40]  # Truncar nombre
                    mcap = stock.get('marketCap', 0)
                    change = stock.get('changesPercentage', 0)
                    f.write(f"      • {symbol}: {name}\n")
                    f.write(f"        Market Cap: ${mcap/1e9:.2f}B | Cambio: {change:.2f}%\n")

            f.write("\n")

        # Recomendaciones
        f.write("\n" + "=" * 80 + "\n")
        f.write("💡 RECOMENDACIONES PARA IDENTIFICAR OPORTUNIDADES TÉCNICAS\n")
        f.write("=" * 80 + "\n\n")

        top_3 = valid_results[:3]
        f.write("🎯 Top 3 mercados recomendados:\n\n")

        for i, result in enumerate(top_3, 1):
            f.write(f"{i}. {result['country_name']}\n")
            f.write(f"   ✅ Ventajas:\n")

            if result['large_caps'] >= 20:
                f.write(f"      - {result['large_caps']} large caps (empresas de calidad establecidas)\n")

            if result['positive_momentum_pct'] > 50:
                f.write(f"      - {result['positive_momentum_pct']:.1f}% del mercado con momentum positivo\n")
            elif result['positive_momentum_pct'] > 40:
                f.write(f"      - Momentum moderado ({result['positive_momentum_pct']:.1f}% positivo)\n")

            if result['high_liquidity'] / result['total_stocks'] > 0.3:
                f.write(f"      - Alta liquidez ({(result['high_liquidity']/result['total_stocks']*100):.1f}% con volumen >$5M)\n")

            f.write(f"\n   📋 Siguientes pasos:\n")
            f.write(f"      1. Ejecutar screener completo: python analyze_country_opportunities.py (solo {result['country_code']})\n")
            f.write(f"      2. Filtrar por sectores específicos de interés\n")
            f.write(f"      3. Aplicar análisis técnico a top candidates\n")
            f.write("\n")

    # JSON
    json_path = f"{output_dir}/quick_opportunities_report.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(valid_results, f, indent=2, ensure_ascii=False)

    logger.info(f"✅ Reporte generado: {report_path}")
    logger.info(f"✅ JSON guardado: {json_path}")

    # Consola
    print("\n" + "=" * 80)
    print("🏆 TOP 5 PAÍSES CON MEJORES OPORTUNIDADES")
    print("=" * 80 + "\n")

    for i, result in enumerate(valid_results[:5], 1):
        print(f"{i}. {result['country_name']}")
        print(f"   📈 Opportunity Score: {result['opportunity_score']:.1f}/100")
        print(f"   📊 Acciones: {result['total_stocks']:,} ({result['large_caps']} large caps)")
        print(f"   🚀 Momentum: {result['positive_momentum_pct']:.1f}% positivo")
        print(f"   💧 Liquidez: {result['high_liquidity']} acciones con alta liquidez")
        print()


def main():
    """
    Función principal - análisis rápido de todos los mercados.
    """
    # Verificar API key
    if not os.getenv('FMP_API_KEY'):
        logger.error("FMP_API_KEY no encontrado. Configura:")
        logger.error("  export FMP_API_KEY=your_api_key")
        sys.exit(1)

    # Cargar config para obtener cliente FMP
    config_path = './settings.yaml'
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Inicializar cliente FMP
    api_key = os.getenv('FMP_API_KEY')
    fmp_client = FMPClient(api_key, config)

    # Crear directorio de salida
    output_dir = './data/quick_country_analysis'
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 80)
    print("ANÁLISIS RÁPIDO DE OPORTUNIDADES POR PAÍS")
    print("=" * 80)
    print(f"\n⏱️  Modo rápido - Solo métricas de mercado (sin screener completo)")
    print(f"🌍 Países a analizar: {len(MARKETS)}")
    print(f"📁 Directorio de salida: {output_dir}\n")

    all_results = []

    # Analizar cada mercado
    for country_code, market_info in MARKETS.items():
        print(f"🌍 {market_info['name']}...", end=" ")

        result = analyze_market_quick(fmp_client, country_code, market_info)

        if result:
            all_results.append(result)
            print(f"✅ {result['total_stocks']} acciones | Score: {result['opportunity_score']:.1f}")
        else:
            print("❌ Error")

    # Generar reporte
    print("\n" + "=" * 80)
    print("Generando reporte...")
    print("=" * 80 + "\n")

    generate_quick_report(all_results, output_dir)

    print(f"\n✅ Análisis completado!")
    print(f"📁 Resultados: {output_dir}/")
    print(f"📊 Reporte: {output_dir}/quick_opportunities_report.txt")


if __name__ == '__main__':
    main()
