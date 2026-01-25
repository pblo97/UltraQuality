#!/usr/bin/env python3
"""
Análisis de Oportunidades Técnicas por País

Este script analiza múltiples mercados para identificar qué países
tienen las mejores oportunidades técnicas basándose en:
- Número de oportunidades BUY
- Calidad promedio de las acciones
- Señales técnicas fuertes
- Momentum del mercado
"""

import os
import sys
import yaml
import pandas as pd
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'screener'))

from orchestrator import ScreenerPipeline

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Mercados soportados según MULTI_COUNTRY_SUPPORT.md
SUPPORTED_MARKETS = {
    'US': {
        'name': '🇺🇸 Estados Unidos',
        'exchanges': ['NYSE', 'NASDAQ'],
        'country_code': 'US',
        'min_market_cap': 2_000_000_000,  # $2B
        'min_volume': 5_000_000  # $5M
    },
    'CA': {
        'name': '🇨🇦 Canadá',
        'exchanges': ['TSX'],
        'country_code': 'CA',
        'min_market_cap': 500_000_000,  # $500M (menor que US)
        'min_volume': 2_000_000  # $2M
    },
    'BR': {
        'name': '🇧🇷 Brasil',
        'exchanges': ['SAO'],
        'country_code': 'BR',
        'min_market_cap': 500_000_000,
        'min_volume': 2_000_000
    },
    'GB': {
        'name': '🇬🇧 Reino Unido',
        'exchanges': ['LSE'],
        'country_code': 'GB',
        'min_market_cap': 1_000_000_000,  # £1B equiv
        'min_volume': 3_000_000
    },
    'DE': {
        'name': '🇩🇪 Alemania',
        'exchanges': ['XETRA'],
        'country_code': 'DE',
        'min_market_cap': 1_000_000_000,
        'min_volume': 3_000_000
    },
    'IN': {
        'name': '🇮🇳 India',
        'exchanges': ['NSE'],
        'country_code': 'IN',
        'min_market_cap': 500_000_000,
        'min_volume': 2_000_000
    },
    'HK': {
        'name': '🇨🇳 Hong Kong',
        'exchanges': ['HKSE'],
        'country_code': 'HK',
        'min_market_cap': 1_000_000_000,
        'min_volume': 3_000_000
    },
    'JP': {
        'name': '🇯🇵 Japón',
        'exchanges': ['JPX'],
        'country_code': 'JP',
        'min_market_cap': 1_000_000_000,
        'min_volume': 3_000_000
    }
}


def create_country_config(base_config_path: str, country_code: str, output_dir: str) -> str:
    """
    Crea una configuración temporal para un país específico.

    Args:
        base_config_path: Ruta al settings.yaml base
        country_code: Código del país (US, CA, BR, etc.)
        output_dir: Directorio para guardar resultados

    Returns:
        Ruta al archivo de configuración temporal
    """
    # Cargar config base
    with open(base_config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Modificar para el país específico
    market = SUPPORTED_MARKETS[country_code]
    config['universe']['countries'] = [market['country_code']]
    config['universe']['exchanges'] = market['exchanges']
    config['universe']['min_market_cap'] = market['min_market_cap']
    config['universe']['min_avg_dollar_vol_3m'] = market['min_volume']

    # Reducir top_k para países más pequeños
    if country_code in ['BR', 'IN', 'HK', 'JP', 'DE']:
        config['universe']['top_k'] = 200  # Menos acciones que US

    # Output específico por país
    config['output']['csv_path'] = f"{output_dir}/{country_code}_screener_results.csv"

    # Guardar config temporal
    temp_config_path = f"{output_dir}/{country_code}_config.yaml"
    with open(temp_config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)

    return temp_config_path


def analyze_country_results(csv_path: str, country_code: str) -> Dict:
    """
    Analiza los resultados del screener para un país.

    Args:
        csv_path: Ruta al CSV de resultados
        country_code: Código del país

    Returns:
        Diccionario con métricas del país
    """
    if not os.path.exists(csv_path):
        logger.warning(f"No se encontró archivo de resultados para {country_code}: {csv_path}")
        return None

    try:
        df = pd.read_csv(csv_path)

        if df.empty:
            logger.warning(f"No hay datos para {country_code}")
            return None

        # Análisis básico
        total_stocks = len(df)
        buy_signals = len(df[df['decision'] == 'BUY']) if 'decision' in df.columns else 0
        monitor_signals = len(df[df['decision'] == 'MONITOR']) if 'decision' in df.columns else 0

        # Métricas de calidad
        avg_quality = df['quality_score_0_100'].mean() if 'quality_score_0_100' in df.columns else 0
        avg_value = df['value_score_0_100'].mean() if 'value_score_0_100' in df.columns else 0
        avg_composite = df['composite_0_100'].mean() if 'composite_0_100' in df.columns else 0

        # Top stocks
        top_stocks = []
        if 'composite_0_100' in df.columns and 'ticker' in df.columns:
            df_sorted = df.sort_values('composite_0_100', ascending=False)
            top_stocks = df_sorted[['ticker', 'name', 'composite_0_100', 'decision']].head(5).to_dict('records')

        # Métricas técnicas (si están disponibles)
        technical_buy = 0
        avg_technical_score = 0
        if 'technical_signal' in df.columns:
            technical_buy = len(df[df['technical_signal'] == 'BUY'])
        if 'technical_score' in df.columns:
            avg_technical_score = df['technical_score'].mean()

        return {
            'country_code': country_code,
            'country_name': SUPPORTED_MARKETS[country_code]['name'],
            'total_stocks': total_stocks,
            'buy_signals': buy_signals,
            'monitor_signals': monitor_signals,
            'buy_percentage': (buy_signals / total_stocks * 100) if total_stocks > 0 else 0,
            'avg_quality_score': round(avg_quality, 1),
            'avg_value_score': round(avg_value, 1),
            'avg_composite_score': round(avg_composite, 1),
            'technical_buy': technical_buy,
            'avg_technical_score': round(avg_technical_score, 1),
            'top_stocks': top_stocks,
            'opportunity_score': calculate_opportunity_score(
                buy_signals, total_stocks, avg_quality, avg_composite
            )
        }
    except Exception as e:
        logger.error(f"Error analizando resultados de {country_code}: {e}")
        return None


def calculate_opportunity_score(buy_signals: int, total_stocks: int,
                                avg_quality: float, avg_composite: float) -> float:
    """
    Calcula un score de oportunidad basado en múltiples factores.

    Score = (buy_ratio * 40) + (avg_quality * 0.3) + (avg_composite * 0.3)
    """
    if total_stocks == 0:
        return 0

    buy_ratio = buy_signals / total_stocks
    score = (buy_ratio * 40) + (avg_quality * 0.3) + (avg_composite * 0.3)
    return round(score, 1)


def generate_report(results: List[Dict], output_dir: str):
    """
    Genera un reporte comparativo de oportunidades por país.
    """
    # Filtrar resultados válidos
    valid_results = [r for r in results if r is not None]

    if not valid_results:
        logger.error("No hay resultados válidos para generar reporte")
        return

    # Ordenar por opportunity_score
    valid_results.sort(key=lambda x: x['opportunity_score'], reverse=True)

    # Generar reporte en texto
    report_path = f"{output_dir}/country_opportunities_report.txt"

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("ANÁLISIS DE OPORTUNIDADES TÉCNICAS POR PAÍS\n")
        f.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")

        # Resumen ejecutivo
        f.write("📊 RESUMEN EJECUTIVO\n")
        f.write("-" * 80 + "\n")
        f.write(f"Países analizados: {len(valid_results)}\n")
        f.write(f"Total de acciones analizadas: {sum(r['total_stocks'] for r in valid_results)}\n")
        f.write(f"Total de señales BUY: {sum(r['buy_signals'] for r in valid_results)}\n\n")

        # Ranking de países
        f.write("🏆 RANKING DE PAÍSES POR OPORTUNIDADES\n")
        f.write("-" * 80 + "\n\n")

        for i, result in enumerate(valid_results, 1):
            f.write(f"{i}. {result['country_name']} ({result['country_code']})\n")
            f.write(f"   Opportunity Score: {result['opportunity_score']}/100\n")
            f.write(f"   Acciones analizadas: {result['total_stocks']}\n")
            f.write(f"   Señales BUY: {result['buy_signals']} ({result['buy_percentage']:.1f}%)\n")
            f.write(f"   Señales MONITOR: {result['monitor_signals']}\n")
            f.write(f"   Calidad promedio: {result['avg_quality_score']}/100\n")
            f.write(f"   Score compuesto promedio: {result['avg_composite_score']}/100\n")

            if result['top_stocks']:
                f.write(f"\n   🌟 Top 3 Acciones:\n")
                for stock in result['top_stocks'][:3]:
                    ticker = stock.get('ticker', 'N/A')
                    name = stock.get('name', 'N/A')
                    score = stock.get('composite_0_100', 0)
                    decision = stock.get('decision', 'N/A')
                    f.write(f"      • {ticker}: {name} - Score: {score:.1f} ({decision})\n")

            f.write("\n")

        # Análisis detallado
        f.write("\n" + "=" * 80 + "\n")
        f.write("📈 ANÁLISIS DETALLADO POR PAÍS\n")
        f.write("=" * 80 + "\n\n")

        for result in valid_results:
            f.write(f"\n{result['country_name']} ({result['country_code']})\n")
            f.write("-" * 80 + "\n")
            f.write(f"Total de acciones: {result['total_stocks']}\n")
            f.write(f"Señales BUY: {result['buy_signals']} ({result['buy_percentage']:.1f}%)\n")
            f.write(f"Señales MONITOR: {result['monitor_signals']}\n")
            f.write(f"Calidad promedio: {result['avg_quality_score']}/100\n")
            f.write(f"Valor promedio: {result['avg_value_score']}/100\n")
            f.write(f"Score compuesto: {result['avg_composite_score']}/100\n")

            if result.get('technical_buy', 0) > 0:
                f.write(f"Señales técnicas BUY: {result['technical_buy']}\n")
                f.write(f"Score técnico promedio: {result['avg_technical_score']}/100\n")

            if result['top_stocks']:
                f.write(f"\nTop 5 Acciones:\n")
                for j, stock in enumerate(result['top_stocks'], 1):
                    ticker = stock.get('ticker', 'N/A')
                    name = stock.get('name', 'N/A')
                    score = stock.get('composite_0_100', 0)
                    decision = stock.get('decision', 'N/A')
                    f.write(f"  {j}. {ticker}: {name}\n")
                    f.write(f"     Score: {score:.1f} - Decisión: {decision}\n")

            f.write("\n")

        # Recomendaciones
        f.write("\n" + "=" * 80 + "\n")
        f.write("💡 RECOMENDACIONES\n")
        f.write("=" * 80 + "\n\n")

        top_3_countries = valid_results[:3]
        f.write("Mejores mercados para explorar oportunidades:\n\n")
        for i, result in enumerate(top_3_countries, 1):
            f.write(f"{i}. {result['country_name']}\n")
            f.write(f"   - {result['buy_signals']} oportunidades BUY identificadas\n")
            f.write(f"   - Calidad promedio: {result['avg_quality_score']}/100\n")

            if result['buy_percentage'] > 10:
                f.write(f"   - ✅ Alta proporción de oportunidades ({result['buy_percentage']:.1f}%)\n")
            elif result['buy_percentage'] > 5:
                f.write(f"   - ⚠️  Proporción moderada de oportunidades ({result['buy_percentage']:.1f}%)\n")
            else:
                f.write(f"   - ⚠️  Baja proporción de oportunidades ({result['buy_percentage']:.1f}%)\n")

            f.write("\n")

    # Guardar también en JSON para procesamiento posterior
    json_path = f"{output_dir}/country_opportunities_report.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(valid_results, f, indent=2, ensure_ascii=False)

    logger.info(f"✅ Reporte generado en: {report_path}")
    logger.info(f"✅ Datos JSON guardados en: {json_path}")

    # Imprimir resumen en consola
    print("\n" + "=" * 80)
    print("🏆 TOP 5 PAÍSES CON MEJORES OPORTUNIDADES TÉCNICAS")
    print("=" * 80 + "\n")

    for i, result in enumerate(valid_results[:5], 1):
        print(f"{i}. {result['country_name']}")
        print(f"   Opportunity Score: {result['opportunity_score']}/100")
        print(f"   Señales BUY: {result['buy_signals']} ({result['buy_percentage']:.1f}%)")
        print(f"   Calidad promedio: {result['avg_quality_score']}/100")
        print()


def main():
    """
    Función principal que ejecuta el análisis para todos los países.
    """
    # Verificar API key
    if not os.getenv('FMP_API_KEY'):
        logger.error("FMP_API_KEY no encontrado. Configura la variable de entorno:")
        logger.error("  export FMP_API_KEY=your_api_key")
        sys.exit(1)

    # Crear directorio de salida
    output_dir = './data/country_analysis'
    os.makedirs(output_dir, exist_ok=True)

    base_config_path = './settings.yaml'

    print("=" * 80)
    print("ANÁLISIS DE OPORTUNIDADES TÉCNICAS POR PAÍS")
    print("=" * 80)
    print(f"\nPaíses a analizar: {len(SUPPORTED_MARKETS)}")
    print(f"Directorio de salida: {output_dir}")
    print()

    # Resultados para cada país
    all_results = []

    # Analizar cada país
    for country_code, market_info in SUPPORTED_MARKETS.items():
        print(f"\n🌍 Analizando: {market_info['name']} ({country_code})...")
        print("-" * 80)

        try:
            # Crear configuración temporal para este país
            country_config_path = create_country_config(
                base_config_path,
                country_code,
                output_dir
            )

            logger.info(f"Configuración creada: {country_config_path}")

            # Ejecutar screener
            pipeline = ScreenerPipeline(country_config_path)
            output_csv = pipeline.run()

            logger.info(f"Screener completado para {country_code}: {output_csv}")

            # Analizar resultados
            results = analyze_country_results(output_csv, country_code)

            if results:
                all_results.append(results)
                print(f"✅ {country_code}: {results['buy_signals']} oportunidades BUY encontradas")
            else:
                print(f"⚠️  {country_code}: Sin resultados")

        except Exception as e:
            logger.error(f"Error analizando {country_code}: {e}")
            print(f"❌ {country_code}: Error - {e}")
            continue

    # Generar reporte final
    print("\n" + "=" * 80)
    print("Generando reporte comparativo...")
    print("=" * 80 + "\n")

    generate_report(all_results, output_dir)

    print(f"\n✅ Análisis completado!")
    print(f"📁 Resultados guardados en: {output_dir}/")
    print(f"📊 Reporte: {output_dir}/country_opportunities_report.txt")


if __name__ == '__main__':
    main()
