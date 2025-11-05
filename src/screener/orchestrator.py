"""
Main orchestrator pipeline for Quality + Value screener.

Pipeline stages:
1. Screener: Get universe and classify companies
2. Preliminary ranking: Select Top-K for deep analysis
3. Features: Calculate Value & Quality metrics for Top-K
4. Guardrails: Accounting quality checks
5. Scoring: Normalize by industry and score
6. Export: Generate CSV with all results
"""
import logging
import os
import sys
import yaml
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from ingest import FMPClient
from features import FeatureCalculator
from guardrails import GuardrailCalculator
from scoring import ScoringEngine
from qualitative import QualitativeAnalyzer

logger = logging.getLogger(__name__)


class ScreenerPipeline:
    """
    End-to-end pipeline for Quality+Value screening.
    """

    def __init__(self, config_path: str):
        """Initialize pipeline with configuration."""
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        # Setup logging
        self._setup_logging()

        # Initialize FMP client
        # Try multiple sources for API key (in order of priority):
        # 1. Streamlit secrets (if available)
        # 2. Environment variable
        # 3. Config file
        api_key = None

        try:
            import streamlit as st
            if hasattr(st, 'secrets'):
                # Try FMP_API_KEY first (correct name)
                if 'FMP_API_KEY' in st.secrets:
                    api_key = st.secrets['FMP_API_KEY']
                    logger.info(f"✓ Using API key from Streamlit secrets: FMP_API_KEY={api_key[:10]}...{api_key[-4:]}")
                # Fallback to FMP (common mistake)
                elif 'FMP' in st.secrets:
                    api_key = st.secrets['FMP']
                    logger.warning(f"⚠️  Found 'FMP' in secrets (should be 'FMP_API_KEY'). Using anyway: {api_key[:10]}...{api_key[-4:]}")
                else:
                    available_keys = list(st.secrets.keys())
                    logger.error(f"❌ FMP_API_KEY not found in Streamlit secrets. Available keys: {available_keys}")
        except (ImportError, FileNotFoundError) as e:
            logger.debug(f"Streamlit not available or secrets not found: {e}")

        if not api_key:
            api_key = os.getenv('FMP_API_KEY')
            if api_key:
                logger.info(f"✓ Using API key from environment variable: {api_key[:10]}...{api_key[-4:]}")

        if not api_key:
            api_key = self.config['fmp'].get('api_key')
            if api_key and not api_key.startswith('${'):
                logger.info(f"✓ Using API key from config file: {api_key[:10]}...{api_key[-4:]}")

        if not api_key or api_key.startswith('${'):
            raise ValueError(
                "FMP_API_KEY not found. Set it via:\n"
                "  1. Streamlit secrets: Add 'FMP_API_KEY = \"your_key\"' (NOT 'FMP')\n"
                "  2. Environment variable: export FMP_API_KEY=your_key\n"
                "  3. .env file: FMP_API_KEY=your_key"
            )

        self.fmp = FMPClient(api_key, self.config['fmp'])
        logger.info("FMP client initialized")

        # Initialize calculators
        self.features = FeatureCalculator(self.fmp)
        self.guardrails = GuardrailCalculator(self.fmp, self.config)
        self.scoring = ScoringEngine(self.config)
        self.qualitative = QualitativeAnalyzer(self.fmp, self.config)

        # State
        self.df_universe = None
        self.df_topk = None
        self.df_final = None

    def _setup_logging(self):
        """Configure logging."""
        log_config = self.config.get('logging', {})
        log_level = log_config.get('level', 'INFO')
        log_dir = log_config.get('log_dir', './logs')
        log_file = log_config.get('log_file', 'screener.log')

        Path(log_dir).mkdir(parents=True, exist_ok=True)

        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(f"{log_dir}/{log_file}"),
                logging.StreamHandler()
            ]
        )

    def run(self):
        """
        Execute full pipeline.

        Returns: Path to output CSV
        """
        logger.info("=" * 80)
        logger.info("Starting UltraQuality Screener Pipeline")
        logger.info("=" * 80)

        start_time = datetime.now()

        try:
            # Stage 1: Screener (Universe)
            logger.info("\n[Stage 1/6] Building universe...")
            self._build_universe()

            # Stage 2: Preliminary Ranking (Top-K)
            logger.info("\n[Stage 2/6] Selecting Top-K for deep analysis...")
            self._select_topk()

            # Stage 3: Features (Value & Quality metrics)
            logger.info("\n[Stage 3/6] Calculating features for Top-K...")
            self._calculate_features()

            # Stage 4: Guardrails (Accounting quality)
            logger.info("\n[Stage 4/6] Calculating guardrails...")
            self._calculate_guardrails()

            # Stage 5: Scoring & Normalization
            logger.info("\n[Stage 5/6] Scoring and normalization...")
            self._score_universe()

            # Stage 6: Export
            logger.info("\n[Stage 6/6] Exporting results...")
            output_path = self._export_results()

            # Log metrics
            self._log_metrics(start_time)

            logger.info(f"\n{'='*80}")
            logger.info(f"Pipeline complete! Results: {output_path}")
            logger.info(f"{'='*80}\n")

            return output_path

        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            raise

    # ===================================
    # STAGE 1: SCREENER (Universe)
    # ===================================

    def _build_universe(self):
        """
        Build universe of stocks matching criteria.
        Classify as non_financial, financial, or REIT.
        """
        universe_config = self.config['universe']
        countries = universe_config.get('countries', ['US'])
        exchanges = universe_config.get('exchanges', [])
        min_mcap = universe_config.get('min_market_cap', 500_000_000)
        min_vol = universe_config.get('min_avg_dollar_vol_3m', 5_000_000)

        logger.info(f"Filters: min_mcap=${min_mcap:,.0f}, min_vol=${min_vol:,.0f}")
        logger.info(f"Countries: {countries}, Exchanges: {exchanges or 'All'}")

        # Fetch universe using profile-bulk
        # FMP profile-bulk uses pagination with 'part' parameter
        all_profiles = []

        for part in range(5):  # Fetch first 5 parts (covers most US stocks)
            try:
                logger.info(f"Fetching profile-bulk part {part}...")

                profiles = self.fmp._request(
                    'profile-bulk',
                    params={'part': part},
                    cache=self.fmp.cache_universe
                )

                if not profiles:
                    logger.warning(f"Part {part} returned empty - stopping pagination")
                    break

                if isinstance(profiles, dict) and 'Error Message' in profiles:
                    logger.error(f"FMP API Error: {profiles['Error Message']}")
                    raise ValueError(f"FMP API Error: {profiles['Error Message']}")

                all_profiles.extend(profiles)
                logger.info(f"✓ Fetched {len(profiles)} profiles from part {part} (total: {len(all_profiles)})")

            except Exception as e:
                logger.error(f"Failed to fetch part {part}: {type(e).__name__}: {e}")
                if part == 0:
                    # If first request fails, show detailed error
                    logger.error(f"First request failed - this indicates a problem with API access")
                    logger.error(f"Try manually: curl 'https://financialmodelingprep.com/api/v3/profile-bulk?part=0&apikey=YOUR_KEY'")
                break

        if not all_profiles:
            raise ValueError(
                "No profiles fetched. Possible causes:\n"
                f"  1. API endpoint returned empty (try different endpoint)\n"
                f"  2. Network/firewall blocking FMP\n"
                f"  3. API key lacks access to profile-bulk endpoint\n"
                f"  4. Check logs above for HTTP status codes"
            )

        # Convert to DataFrame
        df = pd.DataFrame(all_profiles)

        logger.info(f"Total profiles fetched: {len(df)}")

        # Filter by country
        if countries:
            df = df[df['country'].isin(countries)]
            logger.info(f"After country filter: {len(df)}")

        # Filter by exchange
        if exchanges:
            df = df[df['exchangeShortName'].isin(exchanges)]
            logger.info(f"After exchange filter: {len(df)}")

        # Filter by market cap
        df = df[df['mktCap'] >= min_mcap]
        logger.info(f"After market cap filter: {len(df)}")

        # Calculate avgDollarVol_3m (simplified: use volume * price)
        # For accurate 3m avg, would need historical data
        # Placeholder: use current volume * price as proxy
        df['avgDollarVol_3m'] = df['volAvg'] * df['price']
        df = df[df['avgDollarVol_3m'] >= min_vol]
        logger.info(f"After volume filter: {len(df)}")

        # Classify companies
        df['is_financial'] = df.apply(self._classify_financial, axis=1)
        df['is_REIT'] = df.apply(self._classify_reit, axis=1)
        df['is_utility'] = df.apply(self._classify_utility, axis=1)

        # Standardize columns
        df = df.rename(columns={
            'symbol': 'ticker',
            'companyName': 'name',
            'exchangeShortName': 'exchange',
            'mktCap': 'marketCap',
            'volAvg': 'freeFloat'  # Approximate (FMP doesn't expose exact float in profile)
        })

        # Select relevant columns
        columns = [
            'ticker', 'name', 'country', 'exchange', 'sector', 'industry',
            'marketCap', 'avgDollarVol_3m', 'freeFloat',
            'is_financial', 'is_REIT', 'is_utility'
        ]

        self.df_universe = df[columns].copy()

        logger.info(f"Universe built: {len(self.df_universe)} stocks")
        logger.info(f"  Non-financials: {(~self.df_universe['is_financial']).sum()}")
        logger.info(f"  Financials: {(self.df_universe['is_financial'] & ~self.df_universe['is_REIT']).sum()}")
        logger.info(f"  REITs: {self.df_universe['is_REIT'].sum()}")

    def _classify_financial(self, row) -> bool:
        """Classify if company is a financial."""
        sector = (row.get('sector') or '').lower()
        industry = (row.get('industry') or '').lower()

        financial_keywords = ['bank', 'insurance', 'asset management', 'brokerage',
                              'diversified financial', 'credit services', 'capital markets']

        if 'financial' in sector:
            return True

        for kw in financial_keywords:
            if kw in industry:
                return True

        return False

    def _classify_reit(self, row) -> bool:
        """Classify if company is a REIT."""
        industry = (row.get('industry') or '').lower()
        return 'reit' in industry

    def _classify_utility(self, row) -> bool:
        """Classify if company is a utility."""
        sector = (row.get('sector') or '').lower()
        return 'utilities' in sector or 'utility' in sector

    # ===================================
    # STAGE 2: TOP-K SELECTION
    # ===================================

    def _select_topk(self):
        """
        Preliminary ranking to select Top-K for deep analysis.
        Use simple heuristics (low P/E, high yield, etc.) to avoid fetching
        full data for entire universe.
        """
        top_k = self.config['universe']['top_k']

        # Fetch basic ratios for universe (use ratios-ttm in batches)
        # For simplicity, use marketCap as proxy for now
        # In production: fetch ratios-ttm-bulk or key-metrics-ttm-bulk

        # Simple heuristic: rank by marketCap (larger = more liquid)
        df = self.df_universe.copy()
        df['prelim_rank'] = df['marketCap'].rank(ascending=False)

        # Select top K
        self.df_topk = df.nsmallest(top_k, 'prelim_rank').copy()

        logger.info(f"Selected Top-{top_k} stocks for deep analysis")

    # ===================================
    # STAGE 3: FEATURES
    # ===================================

    def _calculate_features(self):
        """Calculate Value & Quality features for Top-K."""
        results = []

        for idx, row in self.df_topk.iterrows():
            symbol = row['ticker']
            company_type = self._get_company_type(row)

            logger.info(f"Calculating features for {symbol} ({company_type})...")

            try:
                features = self.features.calculate_features(symbol, company_type)
                features['ticker'] = symbol
                results.append(features)

            except Exception as e:
                logger.error(f"Failed to calculate features for {symbol}: {e}")
                # Add empty row
                results.append({'ticker': symbol})

        # Merge features with universe data
        df_features = pd.DataFrame(results)
        self.df_topk = self.df_topk.merge(df_features, on='ticker', how='left')

        logger.info(f"Features calculated for {len(results)} stocks")

    # ===================================
    # STAGE 4: GUARDRAILS
    # ===================================

    def _calculate_guardrails(self):
        """Calculate accounting guardrails for Top-K."""
        results = []

        for idx, row in self.df_topk.iterrows():
            symbol = row['ticker']
            company_type = self._get_company_type(row)
            industry = row.get('industry', '')

            logger.info(f"Calculating guardrails for {symbol}...")

            try:
                guardrails = self.guardrails.calculate_guardrails(
                    symbol, company_type, industry
                )
                guardrails['ticker'] = symbol
                results.append(guardrails)

            except Exception as e:
                logger.error(f"Failed to calculate guardrails for {symbol}: {e}")
                results.append({
                    'ticker': symbol,
                    'guardrail_status': 'AMBAR',
                    'guardrail_reasons': f'Error: {str(e)[:50]}'
                })

        # Merge guardrails
        df_guardrails = pd.DataFrame(results)
        self.df_topk = self.df_topk.merge(df_guardrails, on='ticker', how='left')

        logger.info(f"Guardrails calculated for {len(results)} stocks")

    # ===================================
    # STAGE 5: SCORING
    # ===================================

    def _score_universe(self):
        """Score and rank Top-K."""
        self.df_final = self.scoring.score_universe(self.df_topk)

        # Sort by composite score
        self.df_final = self.df_final.sort_values('composite_0_100', ascending=False)

        logger.info("Scoring complete")
        logger.info(f"  BUY: {(self.df_final['decision'] == 'BUY').sum()}")
        logger.info(f"  MONITOR: {(self.df_final['decision'] == 'MONITOR').sum()}")
        logger.info(f"  AVOID: {(self.df_final['decision'] == 'AVOID').sum()}")

    # ===================================
    # STAGE 6: EXPORT
    # ===================================

    def _export_results(self) -> str:
        """Export results to CSV."""
        output_path = self.config['output']['csv_path']

        # Define column order (as specified in requirements)
        columns = [
            'ticker', 'name', 'country', 'exchange', 'sector', 'industry',
            'marketCap', 'avgDollarVol_3m', 'freeFloat',
            'is_financial', 'is_REIT', 'is_utility',
            # Value (non-fin)
            'ev_ebit_ttm', 'ev_fcf_ttm', 'pe_ttm', 'pb_ttm', 'shareholder_yield_%',
            # Value (fin)
            'p_tangibleBook',
            # Value (REIT)
            'p_ffo', 'p_affo',
            # Quality (non-fin)
            'roic_%', 'roic_persistence', 'grossProfits_to_assets', 'fcf_margin_%', 'cfo_to_ni',
            'netDebt_ebitda', 'interestCoverage', 'fixedChargeCoverage',
            # Quality (fin)
            'roa_%', 'roe_%', 'efficiency_ratio', 'nim_%', 'combined_ratio_%',
            'cet1_or_leverage_ratio_%', 'loans_to_deposits',
            # Quality (REIT)
            'ffo_payout_%', 'affo_payout_%', 'sameStoreNOI_growth_%', 'occupancy_%',
            'netDebt_ebitda_re', 'debt_to_grossAssets_%', 'securedDebt_%',
            # Guardrails
            'altmanZ', 'beneishM', 'accruals_noa_%', 'netShareIssuance_12m_%',
            'mna_flag', 'debt_maturity_<24m_%', 'rate_mix_variable_%',
            'guardrail_status', 'guardrail_reasons',
            # Scores & decision
            'value_score_0_100', 'quality_score_0_100', 'composite_0_100',
            'decision', 'notes_short'
        ]

        # Ensure all columns exist (fill missing with None)
        for col in columns:
            if col not in self.df_final.columns:
                self.df_final[col] = None

        # Export
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        self.df_final[columns].to_csv(output_file, index=False)

        logger.info(f"Results exported to {output_path}")

        return str(output_file)

    # ===================================
    # METRICS & LOGGING
    # ===================================

    def _log_metrics(self, start_time: datetime):
        """Log pipeline metrics."""
        elapsed = (datetime.now() - start_time).total_seconds()

        metrics = self.fmp.get_metrics()

        logger.info("\n" + "=" * 80)
        logger.info("PIPELINE METRICS")
        logger.info("=" * 80)
        logger.info(f"Total runtime: {elapsed:.1f}s")
        logger.info(f"Total API requests: {metrics['total_requests']}")
        logger.info(f"Cached responses: {metrics['total_cached']}")
        logger.info(f"Cache hit rate: {metrics['cache_stats']['symbol']['hit_rate']:.1%}")
        logger.info("\nRequests by endpoint:")
        for endpoint, count in sorted(metrics['requests_by_endpoint'].items(), key=lambda x: -x[1])[:10]:
            logger.info(f"  {endpoint}: {count}")

        if metrics['errors']:
            logger.warning(f"\nErrors encountered: {len(metrics['errors'])}")

        # Save metrics to JSON
        import json
        metrics_path = self.config['output'].get('metrics_log_path', './logs/pipeline_metrics.json')
        Path(metrics_path).parent.mkdir(parents=True, exist_ok=True)

        with open(metrics_path, 'w') as f:
            json.dump({
                'runtime_seconds': elapsed,
                'timestamp': datetime.now().isoformat(),
                'metrics': metrics
            }, f, indent=2)

        logger.info(f"\nMetrics saved to {metrics_path}")
        logger.info("=" * 80)

    # ===================================
    # HELPERS
    # ===================================

    def _get_company_type(self, row) -> str:
        """Determine company type for metric calculation."""
        if row.get('is_REIT', False):
            return 'reit'
        elif row.get('is_financial', False):
            return 'financial'
        else:
            return 'non_financial'

    def get_qualitative_analysis(self, symbol: str) -> Dict:
        """
        On-demand qualitative analysis for a symbol.
        To be called from UI/CLI after screening.
        """
        logger.info(f"Running qualitative analysis for {symbol}")

        # Find symbol in final results
        row = self.df_final[self.df_final['ticker'] == symbol]

        if row.empty:
            logger.warning(f"Symbol {symbol} not found in screener results")
            return {}

        row = row.iloc[0]
        company_type = self._get_company_type(row)

        # Run qualitative analysis
        return self.qualitative.analyze_symbol(symbol, company_type, self.df_final)


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='UltraQuality Screener Pipeline')
    parser.add_argument('--config', default='settings.yaml', help='Path to config file')
    parser.add_argument('--qualitative', help='Run qualitative analysis for symbol (after screening)')

    args = parser.parse_args()

    # Run pipeline
    pipeline = ScreenerPipeline(args.config)

    if args.qualitative:
        # On-demand qualitative analysis
        summary = pipeline.get_qualitative_analysis(args.qualitative)

        if summary:
            import json
            print(json.dumps(summary, indent=2))
    else:
        # Full pipeline
        output = pipeline.run()
        print(f"\n✓ Screening complete. Results: {output}")


if __name__ == '__main__':
    main()
