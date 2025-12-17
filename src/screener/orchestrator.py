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

        self.fmp = FMPClient(api_key, self.config)  # Pass full config for cache & premium settings
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
        self._using_sample_data = False  # Flag if we had to use hardcoded sample symbols

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

        # Fetch universe using stock-screener endpoint
        # This is more reliable than profile-bulk and works with all plans
        all_profiles = []

        logger.info("Using stock-screener endpoint (more reliable than profile-bulk)")

        try:
            # Query by country codes (2-letter ISO) or exchange codes
            # Country codes: US, CA, UK, IN, BR, JP, etc. (recommended for filtering)
            # Exchange codes: TSX, LSE, NSE, HKSE, etc. (less commonly used)

            if countries and countries != ['US']:
                # Use country parameter for international markets
                # This is more reliable than exchange codes
                for country in countries:
                    logger.info(f"Fetching from country: {country}")
                    profiles = self.fmp.get_stock_screener(
                        market_cap_more_than=min_mcap,
                        volume_more_than=min_vol // 1000,  # API expects volume in thousands
                        country=country,  # Country code (US, CA, UK, IN, etc.)
                        limit=10000  # Maximum results
                    )

                    if profiles:
                        all_profiles.extend(profiles)
                        logger.info(f"✓ Fetched {len(profiles)} profiles from country {country}")
                    else:
                        logger.warning(f"Country {country} returned empty - trying to continue")

            elif exchanges:
                # Use exchange parameter (less common, but supported)
                for exchange in exchanges:
                    logger.info(f"Fetching from exchange: {exchange}")
                    profiles = self.fmp.get_stock_screener(
                        market_cap_more_than=min_mcap,
                        volume_more_than=min_vol // 1000,  # API expects volume in thousands
                        exchange=exchange,  # Exchange code (TSX, LSE, NSE, etc.)
                        limit=10000  # Maximum results
                    )

                    if profiles:
                        all_profiles.extend(profiles)
                        logger.info(f"✓ Fetched {len(profiles)} profiles from {exchange}")
                    else:
                        logger.warning(f"{exchange} returned empty - trying to continue")
            else:
                # No filter specified - fetch all regions (slower but comprehensive)
                logger.info("No country/exchange filter - fetching ALL regions")
                profiles = self.fmp.get_stock_screener(
                    market_cap_more_than=min_mcap,
                    volume_more_than=min_vol // 1000,  # API expects volume in thousands
                    # No country/exchange parameter = all regions
                    limit=10000  # Maximum results
                )

                if profiles:
                    all_profiles.extend(profiles)
                    logger.info(f"✓ Fetched {len(profiles)} profiles from all regions")

            if not all_profiles:
                logger.warning("stock-screener returned empty, trying profile-bulk as fallback...")

                # Fallback to profile-bulk if screener fails
                for part in range(5):
                    logger.info(f"Fetching profile-bulk part {part}...")

                    try:
                        profiles = self.fmp._request(
                            'profile-bulk',
                            params={'part': part},
                            cache=self.fmp.cache_universe
                        )

                        if not profiles:
                            logger.warning(f"Part {part} returned empty")
                            break

                        all_profiles.extend(profiles)
                        logger.info(f"✓ Fetched {len(profiles)} profiles from part {part}")
                    except Exception as bulk_error:
                        logger.error(f"profile-bulk part {part} failed: {bulk_error}")
                        break

        except Exception as e:
            logger.error(f"Failed to fetch universe: {type(e).__name__}: {e}")
            logger.error("Trying alternative: available-traded/list endpoint...")

            # Last resort: get all traded symbols
            try:
                all_traded = self.fmp._request('available-traded/list', cache=self.fmp.cache_universe)
                if all_traded:
                    # Map countries to their primary exchanges
                    country_to_exchanges = {
                        'US': ['NYSE', 'NASDAQ', 'AMEX'],
                        'CA': ['TSX', 'TSXV', 'NEO'],
                        'UK': ['LSE', 'LONDON', 'LON'],
                        'IN': ['NSE', 'BSE'],
                        'AU': ['ASX'],
                        'BR': ['SAO', 'BVMF'],
                        'MX': ['BMV', 'MEX'],
                        'CH': ['SIX', 'SW'],  # Switzerland
                        'JP': ['TSE', 'JPX'],
                        'HK': ['HKSE', 'HKG'],
                        'FR': ['EPA', 'PAR'],
                        'DE': ['ETR', 'GER', 'FRA', 'XETRA'],
                        'IT': ['MIL', 'BIT'],
                        'ES': ['BME', 'MCE'],
                        'NL': ['AMS'],
                        'SE': ['STO'],
                        'NO': ['OSE'],
                        'DK': ['CPH'],
                        'FI': ['HEL'],
                        'BE': ['BRU'],
                        'AT': ['VIE'],
                        'PL': ['WSE']
                    }

                    # Determine which exchanges to filter by
                    target_exchanges = []
                    if exchanges:
                        # User specified exchanges explicitly
                        target_exchanges = exchanges
                    elif countries:
                        # Map countries to exchanges
                        for country in countries:
                            target_exchanges.extend(country_to_exchanges.get(country, []))

                    # Default to US exchanges if nothing specified
                    if not target_exchanges:
                        target_exchanges = ['NYSE', 'NASDAQ']

                    logger.info(f"Filtering for exchanges: {target_exchanges}")

                    # Get profiles in batches
                    symbols = [item['symbol'] for item in all_traded if item.get('exchangeShortName') in target_exchanges][:500]
                    logger.info(f"Found {len(symbols)} symbols from {target_exchanges}, fetching profiles...")

                    # Batch profile requests
                    for i in range(0, len(symbols), 100):
                        batch = symbols[i:i+100]
                        batch_profiles = self.fmp.get_profile_bulk(batch)
                        if batch_profiles:
                            all_profiles.extend(batch_profiles)
                            logger.info(f"✓ Fetched {len(batch_profiles)} profiles (batch {i//100 + 1})")
            except Exception as e2:
                logger.error(f"All fallback methods failed: {e2}")

        # ULTRA FALLBACK: Use hardcoded symbols for testing if nothing else worked
        if not all_profiles and countries:
            logger.warning("All API methods failed. Trying hardcoded sample symbols as last resort...")

            # Sample major stocks from various markets (for testing only)
            sample_symbols = {
                'UK': ['SHEL.L', 'BP.L', 'HSBA.L', 'AZN.L', 'ULVR.L', 'GSK.L', 'RIO.L', 'DGE.L', 'BARC.L', 'VOD.L'],
                'CA': ['SHOP.TO', 'CNR.TO', 'TD.TO', 'RY.TO', 'BMO.TO', 'ENB.TO', 'CP.TO', 'SU.TO', 'CNQ.TO', 'TRP.TO'],
                'IN': ['RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'HDFCBANK.NS', 'ICICIBANK.NS', 'BHARTIARTL.NS', 'HINDUNILVR.NS'],
                'AU': ['BHP.AX', 'CSL.AX', 'CBA.AX', 'WBC.AX', 'NAB.AX', 'ANZ.AX', 'WES.AX', 'RIO.AX'],
                'BR': ['PETR4.SA', 'VALE3.SA', 'ITUB4.SA', 'BBDC4.SA', 'ABEV3.SA', 'B3SA3.SA'],
            }

            for country in countries:
                if country in sample_symbols:
                    symbols_to_try = sample_symbols[country]
                    logger.info(f"Attempting to fetch {len(symbols_to_try)} sample {country} stocks...")

                    try:
                        batch_profiles = self.fmp.get_profile_bulk(symbols_to_try)
                        if batch_profiles:
                            all_profiles.extend(batch_profiles)
                            logger.warning(f"⚠️ Using {len(batch_profiles)} sample stocks for {country}. This is LIMITED DATA for testing only.")
                            logger.warning(f"⚠️ To get full market data, upgrade your FMP plan to include international markets.")
                    except Exception as sample_error:
                        logger.error(f"Even sample symbols failed: {sample_error}")

        if not all_profiles:
            error_msg = (
                "❌ No profiles fetched after trying multiple endpoints.\n\n"
                f"**Attempted endpoints:**\n"
                f"  1. stock-screener (country={countries})\n"
                f"  2. profile-bulk (5 parts)\n"
                f"  3. available-traded/list + profile-bulk\n\n"
                f"**Possible causes:**\n"
                f"  • Your FMP API plan may not include international data (UK, etc.)\n"
                f"  • These specific endpoints may be restricted on your plan\n"
                f"  • The country '{countries}' may not have sufficient data in FMP\n\n"
                f"**Solutions:**\n"
                f"  1. Try running with 'United States' instead of '{countries}'\n"
                f"  2. Check your FMP plan at: https://financialmodelingprep.com/developer/docs/pricing\n"
                f"  3. Upgrade to a plan that includes international data\n"
                f"  4. Contact FMP support: support@financialmodelingprep.com\n\n"
                f"💡 **Free and Basic plans typically only include US stocks.**"
            )
            raise ValueError(error_msg)

        # Convert to DataFrame
        df = pd.DataFrame(all_profiles)

        # Store flag if using sample data (for UI warning)
        self._using_sample_data = len(all_profiles) <= 20 and countries and countries != ['US']

        logger.info(f"Total profiles fetched: {len(df)}")
        if self._using_sample_data:
            logger.warning("⚠️ USING SAMPLE DATA - Not a full market screener. Upgrade FMP plan for complete data.")

        # Normalize column names (stock-screener uses different names than profile-bulk)
        column_mapping = {
            'marketCap': 'mktCap',          # stock-screener → profile-bulk
            'volume': 'volAvg',             # stock-screener → profile-bulk
            'companyName': 'name',          # sometimes different
        }

        for old_name, new_name in column_mapping.items():
            if old_name in df.columns and new_name not in df.columns:
                df[new_name] = df[old_name]
                logger.debug(f"Mapped {old_name} → {new_name}")

        # Log available columns for debugging
        logger.info(f"DataFrame columns: {df.columns.tolist()[:10]}...")

        # NOTE: Country/exchange filtering is now done at API level, not post-processing
        # This avoids the bug where country filter was blocking international stocks
        # The API calls above already filtered by country/exchange parameter

        # Filter by market cap (handle both field names)
        if 'mktCap' in df.columns:
            df = df[df['mktCap'] >= min_mcap]
            logger.info(f"After market cap filter: {len(df)}")
        elif 'marketCap' in df.columns:
            df = df[df['marketCap'] >= min_mcap]
            logger.info(f"After market cap filter: {len(df)}")
        else:
            logger.warning("No market cap field found - skipping market cap filter")

        # Calculate avgDollarVol_3m
        # Use volAvg (from profile-bulk) or volume (from stock-screener)
        volume_col = 'volAvg' if 'volAvg' in df.columns else 'volume'
        price_col = 'price'

        if volume_col in df.columns and price_col in df.columns:
            df['avgDollarVol_3m'] = df[volume_col] * df[price_col]
            df = df[df['avgDollarVol_3m'] >= min_vol]
            logger.info(f"After volume filter: {len(df)}")
        else:
            logger.warning(f"Volume or price columns not found - skipping volume filter")
            df['avgDollarVol_3m'] = 0  # Default value

        # Validate we have enough stocks after filtering
        if len(df) == 0:
            raise ValueError(
                f"❌ No stocks found matching your criteria:\n"
                f"  • Min Market Cap: ${min_mcap/1e6:,.0f}M\n"
                f"  • Min Daily Volume: ${min_vol/1e6:,.1f}M\n\n"
                f"💡 Try lowering the minimum thresholds."
            )

        if len(df) < 10:
            logger.warning(f"⚠️ Only {len(df)} stocks match your criteria. Consider lowering thresholds.")

        # Enrich sector with fallback logic (BEFORE classification)
        logger.info("Enriching sectors with fallback logic...")
        df['sector'] = df.apply(self._enrich_sector, axis=1)
        unknown_count = (df['sector'] == 'Unknown').sum()
        if unknown_count > 0:
            logger.warning(f"{unknown_count} stocks still have Unknown sector after enrichment")
        else:
            logger.info("✓ All stocks have valid sectors")

        # Classify companies
        df['is_financial'] = df.apply(self._classify_financial, axis=1)
        df['is_REIT'] = df.apply(self._classify_reit, axis=1)
        df['is_utility'] = df.apply(self._classify_utility, axis=1)
        df['is_ETF'] = df.apply(self._classify_etf, axis=1)

        # Filter out ETFs (Exchange Traded Funds should not be in stock screener)
        etf_count = df['is_ETF'].sum()
        if etf_count > 0:
            logger.info(f"Filtering out {etf_count} ETFs from universe")
            df = df[~df['is_ETF']]
            logger.info(f"After ETF filter: {len(df)} stocks remaining")

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

    def _enrich_sector(self, row) -> str:
        """
        Enrich sector with fallback logic for Unknown/empty sectors.

        Fallback strategy:
        1. ETF/Index exception (QQQ, SPY, IWM, etc.)
        2. Use API sector if available and valid
        3. Infer from industry keywords
        4. Return 'Unknown' as last resort

        Examples:
        - QQQ: ETF_Index (not Financial Services)
        - Amazon: Industry "Internet Retail" → Sector "Consumer Cyclical"
        - Google: Industry "Internet Content" → Sector "Communication Services"
        """
        ticker = (row.get('symbol') or row.get('ticker') or '').upper()

        # CRITICAL: ETF/Index Exception (QQQ, SPY, IWM should NOT be compared with stocks)
        ETF_TICKERS = ['QQQ', 'SPY', 'IWM', 'DIA', 'VTI', 'VOO', 'VEA', 'VWO',
                       'EFA', 'EEM', 'AGG', 'BND', 'TLT', 'GLD', 'SLV',
                       'XLK', 'XLF', 'XLE', 'XLV', 'XLI', 'XLC', 'XLY', 'XLP', 'XLRE']
        if ticker in ETF_TICKERS:
            logger.info(f"ETF detected: {ticker} → Sector: ETF_Index")
            return 'ETF_Index'

        sector = (row.get('sector') or '').strip()
        industry = (row.get('industry') or '').lower()

        # If sector is valid (not empty, not 'Unknown'), use it
        if sector and sector.lower() not in ['unknown', 'n/a', '']:
            return sector

        # FALLBACK: Infer sector from industry keywords
        sector_mapping = {
            'Technology': [
                'software', 'internet', 'semiconductor', 'computer',
                'electronics', 'it services', 'cloud', 'saas',
                'cybersecurity', 'artificial intelligence', 'data'
            ],
            'Consumer Cyclical': [
                'retail', 'e-commerce', 'automotive', 'apparel',
                'leisure', 'hotels', 'restaurants', 'travel',
                'homebuilding', 'luxury goods'
            ],
            'Consumer Defensive': [
                'food', 'beverage', 'tobacco', 'household products',
                'personal products', 'discount stores'
            ],
            'Healthcare': [
                'pharmaceutical', 'biotechnology', 'medical',
                'health care', 'diagnostics', 'hospital'
            ],
            'Financials': [
                'bank', 'insurance', 'asset management', 'brokerage',
                'credit services', 'capital markets', 'mortgage'
            ],
            'Communication Services': [
                'telecommunication', 'media', 'entertainment',
                'publishing', 'broadcasting', 'internet content'
            ],
            'Industrials': [
                'aerospace', 'defense', 'construction', 'machinery',
                'transportation', 'logistics', 'engineering'
            ],
            'Energy': [
                'oil', 'gas', 'petroleum', 'energy', 'coal',
                'renewable energy', 'utilities' #  Some energy utilities
            ],
            'Basic Materials': [
                'chemicals', 'metals', 'mining', 'steel',
                'paper', 'packaging', 'commodities'
            ],
            'Real Estate': [
                'reit', 'real estate', 'property'
            ],
            'Utilities': [
                'electric', 'water', 'utility', 'power generation'
            ]
        }

        # Search for industry keywords in mapping
        for sector_name, keywords in sector_mapping.items():
            for keyword in keywords:
                if keyword in industry:
                    logger.debug(f"Sector inferred for {row.get('ticker')}: {sector_name} (from industry: {industry})")
                    return sector_name

        # Last resort: return Unknown
        logger.warning(f"Could not infer sector for {row.get('ticker')} (industry: {industry})")
        return 'Unknown'

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

    def _classify_etf(self, row) -> bool:
        """
        Classify if instrument is an ETF (Exchange Traded Fund).

        ETFs should be filtered out from stock screeners as they are:
        - Not individual companies with fundamentals
        - Baskets of other securities
        - Have different risk/return profiles

        Detection criteria:
        - Name contains: ETF, Fund, Index, Trust (with exceptions)
        - Industry contains: Exchange Traded Fund, Investment Trust
        - Type field = 'etf' (if available)
        """
        name = (row.get('name') or row.get('companyName') or '').lower()
        industry = (row.get('industry') or '').lower()
        type_field = (row.get('type') or '').lower()

        # Direct type indicator
        if type_field == 'etf':
            return True

        # Industry indicators
        etf_industries = [
            'exchange traded fund',
            'exchange-traded fund',
            'investment trust',
            'closed-end fund',
            'open-end fund'
        ]

        for ind in etf_industries:
            if ind in industry:
                return True

        # Name indicators (with common patterns)
        # ETF keywords
        etf_keywords = [
            ' etf',           # Space before to avoid "marketplace", "et cetera"
            'etf ',           # Space after
            ' fund',          # Generic funds
            'index fund',
            'yield etf',
            'income etf',
            'dividend etf',
            'sector etf',
            'covered call',   # Common in Canadian ETFs (e.g., Hamilton, Purpose)
            'yield maximizer', # Canadian covered call ETFs
            'premium yield',
            'high interest savings',  # Money market ETFs
            'money market',
            'cash management',
            'aggregate bond',
            'bond index',
            'equity index',
            'composite index',
            'total market',
            'global x',       # ETF provider
            'ishares',        # ETF provider
            'vanguard',       # ETF provider (though some are funds, most are ETFs)
            'betapro',        # Leveraged ETF provider
            'harvest',        # Canadian ETF provider
            'hamilton',       # Canadian ETF provider
            'purpose',        # Canadian ETF provider
            'evolve',         # Canadian ETF provider
        ]

        for keyword in etf_keywords:
            if keyword in name:
                # Exception: Some companies have "fund" or "trust" in name but are REITs or operating companies
                # Allow REITs through (they're already classified separately)
                if 'reit' in industry or 'real estate investment trust' in industry:
                    return False
                # Exception: Royalty trusts/funds (e.g., A&W Revenue Royalties Income Fund)
                if 'royalt' in name or 'royalt' in industry:
                    return False
                # Exception: Mortgage Investment Corporations
                if 'mortgage' in name and 'investment' in name and 'corporation' in name:
                    return False
                return True

        return False

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

        # Handle potential duplicate columns
        if 'marketCap' in df.columns:
            # Ensure we're working with a Series, not DataFrame
            market_cap_series = df['marketCap']
            if isinstance(market_cap_series, pd.DataFrame):
                # If multiple columns, take the first one
                market_cap_series = market_cap_series.iloc[:, 0]
            df['prelim_rank'] = market_cap_series.rank(ascending=False)
        elif 'mktCap' in df.columns:
            market_cap_series = df['mktCap']
            if isinstance(market_cap_series, pd.DataFrame):
                market_cap_series = market_cap_series.iloc[:, 0]
            df['prelim_rank'] = market_cap_series.rank(ascending=False)
        else:
            # If no market cap column, use simple index-based ranking
            logger.warning("No marketCap column found, using sequential ranking")
            df['prelim_rank'] = range(1, len(df) + 1)

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
            # Momentum & Trend Filters
            'revenue_growth_3y', 'roic_trend', 'margin_trend',
            # Moat Score
            'moat_score', 'pricing_power_score', 'operating_leverage_score', 'roic_persistence_score',
            # Quality Degradation Scores (Piotroski for VALUE, Mohanram for GROWTH)
            'piotroski_fscore', 'piotroski_fscore_delta',
            'mohanram_gscore', 'mohanram_gscore_delta',
            'quality_degradation_type', 'quality_degradation_score', 'quality_degradation_delta',
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
        """
        Determine company type for metric calculation.

        Returns: 'reit', 'financial', 'utility', or 'non_financial'
        """
        if row.get('is_REIT', False):
            return 'reit'
        elif row.get('is_financial', False):
            return 'financial'
        elif row.get('is_utility', False):
            return 'utility'
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
