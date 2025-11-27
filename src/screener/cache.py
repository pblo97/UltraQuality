"""
Caching layer for FMP API calls.

Reduces API costs and improves performance by caching responses locally.

Cache TTLs by endpoint type:
- Profile data: 7 days (rarely changes)
- Financial statements: 1 day (updates quarterly but check daily)
- Earnings transcripts: 30 days (historical, immutable)
- News: 1 hour (frequently updated)
- Key metrics: 1 day
"""
import pickle
import hashlib
import os
from datetime import datetime, timedelta
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class CachedFMPClient:
    """
    Wrapper around FMP client with intelligent caching.

    Cache structure:
    .cache/
        {endpoint}/
            {cache_key}.pkl
            {cache_key}.meta  # Stores timestamp

    Usage:
        cached_fmp = CachedFMPClient(fmp_client)
        data = cached_fmp.get_profile('AAPL')  # Cached for 7 days
    """

    def __init__(self, fmp_client, cache_dir='.cache'):
        self.fmp = fmp_client
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

        # Cache TTLs by endpoint
        self.ttls = {
            'profile': timedelta(days=7),
            'balance_sheet': timedelta(days=1),
            'income_statement': timedelta(days=1),
            'cash_flow': timedelta(days=1),
            'key_metrics': timedelta(days=1),
            'ratios': timedelta(days=1),
            'earnings_call_transcript': timedelta(days=30),
            'press_releases': timedelta(days=1),
            'stock_news': timedelta(hours=1),
            'insider_trading': timedelta(hours=6),
            'key_executives': timedelta(days=7),
            'stock_screener': timedelta(hours=1),
            'stock_peers': timedelta(days=7),
        }

        # Stats
        self.stats = {
            'hits': 0,
            'misses': 0,
            'errors': 0
        }

    def _get_cache_key(self, endpoint, symbol, **kwargs):
        """Generate unique cache key from endpoint + params."""
        # Sort kwargs for consistent hashing
        params_str = '|'.join(f"{k}={v}" for k, v in sorted(kwargs.items()))
        key_str = f"{endpoint}:{symbol}:{params_str}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def _get_cache_path(self, endpoint, cache_key):
        """Get file path for cache entry."""
        endpoint_dir = self.cache_dir / endpoint
        endpoint_dir.mkdir(exist_ok=True)
        return endpoint_dir / f"{cache_key}.pkl"

    def _get_meta_path(self, endpoint, cache_key):
        """Get file path for cache metadata."""
        endpoint_dir = self.cache_dir / endpoint
        return endpoint_dir / f"{cache_key}.meta"

    def _is_cache_valid(self, endpoint, cache_key):
        """Check if cache entry exists and is fresh."""
        meta_path = self._get_meta_path(endpoint, cache_key)

        if not meta_path.exists():
            return False

        try:
            with open(meta_path, 'r') as f:
                timestamp_str = f.read().strip()
                cached_time = datetime.fromisoformat(timestamp_str)

            ttl = self.ttls.get(endpoint, timedelta(hours=1))
            age = datetime.now() - cached_time

            return age < ttl
        except Exception as e:
            logger.debug(f"Error checking cache validity: {e}")
            return False

    def _get_from_cache(self, endpoint, cache_key):
        """Retrieve data from cache."""
        cache_path = self._get_cache_path(endpoint, cache_key)

        try:
            with open(cache_path, 'rb') as f:
                data = pickle.load(f)

            self.stats['hits'] += 1
            logger.debug(f"Cache HIT for {endpoint} (key: {cache_key[:8]}...)")
            return data
        except Exception as e:
            logger.debug(f"Error reading from cache: {e}")
            return None

    def _save_to_cache(self, endpoint, cache_key, data):
        """Save data to cache with timestamp."""
        cache_path = self._get_cache_path(endpoint, cache_key)
        meta_path = self._get_meta_path(endpoint, cache_key)

        try:
            # Save data
            with open(cache_path, 'wb') as f:
                pickle.dump(data, f)

            # Save timestamp
            with open(meta_path, 'w') as f:
                f.write(datetime.now().isoformat())

            logger.debug(f"Cached data for {endpoint} (key: {cache_key[:8]}...)")
        except Exception as e:
            logger.warning(f"Error saving to cache: {e}")

    def _fetch_with_cache(self, endpoint, fetch_func, *args, **kwargs):
        """Generic cached fetch wrapper."""
        # Extract symbol (usually first arg)
        symbol = args[0] if args else kwargs.get('symbol', 'unknown')

        # Generate cache key
        cache_key = self._get_cache_key(endpoint, symbol, **kwargs)

        # Check cache
        if self._is_cache_valid(endpoint, cache_key):
            data = self._get_from_cache(endpoint, cache_key)
            if data is not None:
                return data

        # Cache miss - fetch from API
        self.stats['misses'] += 1
        logger.debug(f"Cache MISS for {endpoint} (fetching from API...)")

        try:
            data = fetch_func(*args, **kwargs)
            self._save_to_cache(endpoint, cache_key, data)
            return data
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Error fetching {endpoint}: {e}")
            raise

    # ===================================
    # Cached Methods (wrap FMP client)
    # ===================================

    def get_profile(self, symbol):
        """Get company profile (cached 7 days)."""
        return self._fetch_with_cache(
            'profile',
            self.fmp.get_profile,
            symbol
        )

    def get_balance_sheet(self, symbol, period='quarter', limit=8):
        """Get balance sheet (cached 1 day)."""
        return self._fetch_with_cache(
            'balance_sheet',
            self.fmp.get_balance_sheet,
            symbol,
            period=period,
            limit=limit
        )

    def get_income_statement(self, symbol, period='quarter', limit=12):
        """Get income statement (cached 1 day)."""
        return self._fetch_with_cache(
            'income_statement',
            self.fmp.get_income_statement,
            symbol,
            period=period,
            limit=limit
        )

    def get_cash_flow(self, symbol, period='quarter', limit=8):
        """Get cash flow statement (cached 1 day)."""
        return self._fetch_with_cache(
            'cash_flow',
            self.fmp.get_cash_flow,
            symbol,
            period=period,
            limit=limit
        )

    def get_key_metrics(self, symbol, period='quarter', limit=8):
        """Get key metrics (cached 1 day)."""
        return self._fetch_with_cache(
            'key_metrics',
            self.fmp.get_key_metrics,
            symbol,
            period=period,
            limit=limit
        )

    def get_financial_ratios(self, symbol, period='quarter', limit=8):
        """Get financial ratios (cached 1 day)."""
        return self._fetch_with_cache(
            'ratios',
            self.fmp.get_financial_ratios,
            symbol,
            period=period,
            limit=limit
        )

    def get_earnings_call_transcript(self, symbol, limit=4, year=None, quarter=None):
        """Get earnings call transcript (cached 30 days - immutable)."""
        return self._fetch_with_cache(
            'earnings_call_transcript',
            self.fmp.get_earnings_call_transcript,
            symbol,
            limit=limit,
            year=year,
            quarter=quarter
        )

    def get_press_releases(self, symbol, limit=20):
        """Get press releases (cached 1 day)."""
        return self._fetch_with_cache(
            'press_releases',
            self.fmp.get_press_releases,
            symbol,
            limit=limit
        )

    def get_stock_news(self, symbol, limit=20):
        """Get stock news (cached 1 hour - frequently updated)."""
        return self._fetch_with_cache(
            'stock_news',
            self.fmp.get_stock_news,
            symbol,
            limit=limit
        )

    def get_insider_trading(self, symbol, limit=100):
        """Get insider trading (cached 6 hours)."""
        return self._fetch_with_cache(
            'insider_trading',
            self.fmp.get_insider_trading,
            symbol,
            limit=limit
        )

    def get_key_executives(self, symbol):
        """Get key executives (cached 7 days)."""
        return self._fetch_with_cache(
            'key_executives',
            self.fmp.get_key_executives,
            symbol
        )

    def get_stock_screener(self, **kwargs):
        """Get stock screener results (cached 1 hour)."""
        # For screener, use kwargs as symbol for cache key
        symbol = 'screener'
        return self._fetch_with_cache(
            'stock_screener',
            self.fmp.get_stock_screener,
            symbol,
            **kwargs
        )

    def get_stock_peers(self, symbol):
        """Get stock peers (cached 7 days)."""
        return self._fetch_with_cache(
            'stock_peers',
            self.fmp.get_stock_peers,
            symbol
        )

    # ===================================
    # Cache Management
    # ===================================

    def clear_cache(self, endpoint=None, older_than_days=None):
        """
        Clear cache entries.

        Args:
            endpoint: If specified, only clear this endpoint
            older_than_days: If specified, only clear entries older than N days
        """
        if endpoint:
            endpoints = [endpoint]
        else:
            endpoints = [d.name for d in self.cache_dir.iterdir() if d.is_dir()]

        cleared_count = 0

        for ep in endpoints:
            endpoint_dir = self.cache_dir / ep
            if not endpoint_dir.exists():
                continue

            for file_path in endpoint_dir.glob('*.pkl'):
                meta_path = file_path.with_suffix('.meta')

                should_delete = True

                if older_than_days is not None:
                    try:
                        with open(meta_path, 'r') as f:
                            timestamp_str = f.read().strip()
                            cached_time = datetime.fromisoformat(timestamp_str)

                        age = datetime.now() - cached_time
                        should_delete = age > timedelta(days=older_than_days)
                    except:
                        pass

                if should_delete:
                    file_path.unlink(missing_ok=True)
                    meta_path.unlink(missing_ok=True)
                    cleared_count += 1

        logger.info(f"Cleared {cleared_count} cache entries")
        return cleared_count

    def get_cache_stats(self):
        """Get cache statistics."""
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0

        # Calculate cache size
        total_size = 0
        total_files = 0

        for endpoint_dir in self.cache_dir.iterdir():
            if endpoint_dir.is_dir():
                for file_path in endpoint_dir.glob('*.pkl'):
                    total_size += file_path.stat().st_size
                    total_files += 1

        return {
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'errors': self.stats['errors'],
            'total_requests': total_requests,
            'hit_rate': hit_rate,
            'cache_size_mb': total_size / (1024 * 1024),
            'cache_files': total_files
        }

    def print_stats(self):
        """Print cache statistics."""
        stats = self.get_cache_stats()
        print(f"\n{'='*50}")
        print("CACHE STATISTICS")
        print(f"{'='*50}")
        print(f"Hits: {stats['hits']}")
        print(f"Misses: {stats['misses']}")
        print(f"Errors: {stats['errors']}")
        print(f"Hit Rate: {stats['hit_rate']:.1f}%")
        print(f"Cache Size: {stats['cache_size_mb']:.2f} MB")
        print(f"Cache Files: {stats['cache_files']}")
        print(f"{'='*50}\n")
