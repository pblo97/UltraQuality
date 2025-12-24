"""
FMP API Wrapper with caching, rate limiting, and backoff.
"""
import os
import json
import time
import logging
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import requests
from functools import wraps

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter with jitter."""

    def __init__(self, rate: float):
        """
        Args:
            rate: Requests per second
        """
        self.rate = rate
        self.interval = 1.0 / rate
        self.last_request = 0.0

    def wait(self):
        """Wait if necessary to respect rate limit."""
        now = time.time()
        time_since_last = now - self.last_request
        if time_since_last < self.interval:
            sleep_time = self.interval - time_since_last
            # Add small jitter (±10%)
            jitter = sleep_time * 0.1 * (2 * (hash(str(now)) % 100) / 100 - 1)
            time.sleep(sleep_time + jitter)
        self.last_request = time.time()


class FMPCache:
    """Simple file-based cache for FMP responses."""

    def __init__(self, cache_dir: str, ttl_hours: int = 48):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = timedelta(hours=ttl_hours)
        self.hits = 0
        self.misses = 0

    def _get_key(self, url: str, params: Dict) -> str:
        """Generate cache key from URL and params."""
        # Remove API key from cache key
        cache_params = {k: v for k, v in params.items() if k != 'apikey'}
        key_str = f"{url}:{json.dumps(cache_params, sort_keys=True)}"
        return hashlib.sha256(key_str.encode()).hexdigest()

    def get(self, url: str, params: Dict) -> Optional[Any]:
        """Retrieve cached response if valid."""
        key = self._get_key(url, params)
        cache_file = self.cache_dir / f"{key}.json"

        if cache_file.exists():
            stat = cache_file.stat()
            age = datetime.now() - datetime.fromtimestamp(stat.st_mtime)

            if age < self.ttl:
                with open(cache_file, 'r') as f:
                    self.hits += 1
                    logger.debug(f"Cache HIT: {url}")
                    return json.load(f)

        self.misses += 1
        logger.debug(f"Cache MISS: {url}")
        return None

    def set(self, url: str, params: Dict, data: Any):
        """Store response in cache."""
        key = self._get_key(url, params)
        cache_file = self.cache_dir / f"{key}.json"

        with open(cache_file, 'w') as f:
            json.dump(data, f)

        logger.debug(f"Cached: {url}")

    def get_stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        total = self.hits + self.misses
        hit_rate = self.hits / total if total > 0 else 0.0
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate
        }


class FMPClient:
    """
    Financial Modeling Prep API client with:
    - Rate limiting (configurable req/sec)
    - Caching (file-based with TTL)
    - Exponential backoff with jitter
    - Request metrics tracking
    """

    def __init__(self, api_key: str, config: Dict):
        """
        Initialize FMP client.

        Args:
            api_key: FMP API key
            config: Full config dict (not just config['fmp'])
        """
        self.api_key = api_key

        # Extract FMP-specific config
        fmp_config = config.get('fmp', config)  # Backward compatible: if 'fmp' not in config, assume config IS fmp_config
        self.base_url = fmp_config.get('base_url', 'https://financialmodelingprep.com/api/v3')
        self.rate_limiter = RateLimiter(fmp_config.get('rate_limit_rps', 8))
        self.max_retries = fmp_config.get('max_retries', 3)
        self.timeout = fmp_config.get('timeout_seconds', 30)

        # Caches with different TTLs (read from root config)
        cache_config = config.get('cache', {})
        cache_dir = cache_config.get('cache_dir', './cache')
        ttl_universe = cache_config.get('ttl_universe_hours', 12)
        ttl_symbol = cache_config.get('ttl_symbol_hours', 48)
        ttl_qualitative = cache_config.get('ttl_qualitative_hours', 24)

        self.cache_universe = FMPCache(f"{cache_dir}/universe", ttl_hours=ttl_universe)
        self.cache_symbol = FMPCache(f"{cache_dir}/symbol", ttl_hours=ttl_symbol)
        self.cache_qualitative = FMPCache(f"{cache_dir}/qualitative", ttl_hours=ttl_qualitative)

        # Metrics
        self.requests_by_endpoint = {}
        self.total_requests = 0
        self.total_cached = 0
        self.errors = []

    def _request(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        cache: Optional[FMPCache] = None,
        retry_count: int = 0
    ) -> Any:
        """
        Make HTTP request with rate limiting, caching, and retries.

        Args:
            endpoint: API endpoint (e.g., 'stock-screener')
            params: Query parameters
            cache: Cache instance to use (or None to skip caching)
            retry_count: Current retry attempt

        Returns:
            JSON response data
        """
        url = f"{self.base_url}/{endpoint}"
        params = params or {}
        params['apikey'] = self.api_key

        # Check cache first
        if cache:
            cached = cache.get(url, params)
            if cached is not None:
                self.total_cached += 1
                return cached

        # Rate limit
        self.rate_limiter.wait()

        # Track metrics
        self.total_requests += 1
        self.requests_by_endpoint[endpoint] = self.requests_by_endpoint.get(endpoint, 0) + 1

        try:
            # Log request details (hide full API key)
            safe_params = {k: (v[:10] + '...' if k == 'apikey' and v else v) for k, v in params.items()}
            logger.info(f"→ API Request: GET {url} params={safe_params}")

            response = requests.get(url, params=params, timeout=self.timeout)

            logger.info(f"← API Response: Status {response.status_code}, Size: {len(response.content)} bytes")

            response.raise_for_status()
            data = response.json()

            # Handle FMP error messages
            if isinstance(data, dict) and 'Error Message' in data:
                raise Exception(f"FMP API Error: {data['Error Message']}")

            # Cache successful response
            if cache:
                cache.set(url, params, data)

            return data

        except requests.exceptions.RequestException as e:
            logger.warning(f"Request failed for {url}: {e}")

            # Retry with exponential backoff
            if retry_count < self.max_retries:
                wait_time = (2 ** retry_count) + (hash(url) % 100) / 100  # 2s, 4s, 8s + jitter
                logger.info(f"Retrying in {wait_time:.2f}s (attempt {retry_count + 1}/{self.max_retries})")
                time.sleep(wait_time)
                return self._request(endpoint, params, cache, retry_count + 1)
            else:
                self.errors.append({"endpoint": endpoint, "error": str(e), "time": datetime.now().isoformat()})
                logger.error(f"Max retries exceeded for {url}")
                raise

    # ========================
    # Screener & Universe
    # ========================

    def get_exchanges_list(self) -> List[Dict]:
        """
        Endpoint: /exchanges-list
        Returns list of all available exchanges in FMP.

        Returns list with dicts containing:
        - name: Exchange name
        - stockExchange: Exchange code (e.g., 'NASDAQ', 'NYSE', 'TSX')
        """
        return self._request('exchanges-list', cache=self.cache_universe)

    def get_stock_screener(
        self,
        market_cap_more_than: Optional[int] = None,
        volume_more_than: Optional[int] = None,
        exchange: Optional[str] = None,
        country: Optional[str] = None,
        limit: int = 10000
    ) -> List[Dict]:
        """
        Endpoint: /stock-screener
        Returns list of stocks matching criteria.

        Args:
            exchange: Exchange code (RECOMMENDED - this works reliably)
                     API parameter accepts both upper/lowercase, but use UPPERCASE for consistency
                     with exchangeShortName field in returned data (needed for filtering)
                     Examples: 'TSX', 'LSE', 'NSE', 'HKSE', 'SSE', 'KRX', 'JPX', 'SNT', 'BMV', 'SAO'
                     Also supports: 'NYSE', 'NASDAQ', 'AMEX', 'EURONEXT', 'XETRA'
            country: Country code (NOT RECOMMENDED - FMP API implementation is unreliable)
                    2-letter ISO codes like 'US', 'CA', 'UK', 'DE', 'IN' - may not work
        """
        params = {'limit': limit}
        if market_cap_more_than:
            params['marketCapMoreThan'] = market_cap_more_than
        if volume_more_than:
            params['volumeMoreThan'] = volume_more_than
        if exchange:
            params['exchange'] = exchange
        if country:
            params['country'] = country

        return self._request('stock-screener', params, cache=self.cache_universe)

    def get_profile_bulk(self, symbols: List[str]) -> List[Dict]:
        """
        Endpoint: /profile/{symbol1,symbol2,...}
        Bulk company profiles (sector, industry, market cap, etc.)
        """
        if not symbols:
            return []

        symbol_str = ','.join(symbols[:100])  # FMP limit ~100 symbols
        return self._request(f'profile/{symbol_str}', cache=self.cache_symbol)

    def get_profile(self, symbol: str) -> List[Dict]:
        """Single symbol profile."""
        return self._request(f'profile/{symbol}', cache=self.cache_symbol)

    def get_quote(self, symbol: str) -> List[Dict]:
        """
        Endpoint: /quote/{symbol}
        Real-time quote with price, volume, changes, moving averages.
        """
        return self._request(f'quote/{symbol}', cache=False)  # Real-time data, no cache

    def get_historical_prices(self, symbol: str, from_date: str = None, to_date: str = None) -> Dict:
        """
        Endpoint: /historical-price-full/{symbol}
        Returns: {'symbol': 'AAPL', 'historical': [{'date': '2024-01-01', 'open': 100, 'high': 105, ...}, ...]}

        Args:
            symbol: Stock ticker
            from_date: Optional start date (YYYY-MM-DD)
            to_date: Optional end date (YYYY-MM-DD)
        """
        params = {}
        if from_date:
            params['from'] = from_date
        if to_date:
            params['to'] = to_date
        return self._request(f'historical-price-full/{symbol}', params, cache=self.cache_symbol)

    # ========================
    # Financial Statements
    # ========================

    def get_income_statement(self, symbol: str, period: str = 'quarter', limit: int = 4) -> List[Dict]:
        """
        Endpoint: /income-statement/{symbol}
        Args:
            period: 'quarter' or 'annual'
        """
        params = {'period': period, 'limit': limit}
        return self._request(f'income-statement/{symbol}', params, cache=self.cache_symbol)

    def get_balance_sheet(self, symbol: str, period: str = 'quarter', limit: int = 4) -> List[Dict]:
        """Endpoint: /balance-sheet-statement/{symbol}"""
        params = {'period': period, 'limit': limit}
        return self._request(f'balance-sheet-statement/{symbol}', params, cache=self.cache_symbol)

    def get_cash_flow(self, symbol: str, period: str = 'quarter', limit: int = 4) -> List[Dict]:
        """Endpoint: /cash-flow-statement/{symbol}"""
        params = {'period': period, 'limit': limit}
        return self._request(f'cash-flow-statement/{symbol}', params, cache=self.cache_symbol)

    # ========================
    # Ratios & Metrics (TTM preferred)
    # ========================

    def get_key_metrics_ttm(self, symbol: str) -> List[Dict]:
        """
        Endpoint: /key-metrics-ttm/{symbol}
        TTM metrics including P/E, P/B, ROE, ROIC, etc.
        """
        return self._request(f'key-metrics-ttm/{symbol}', cache=self.cache_symbol)

    def get_ratios_ttm(self, symbol: str) -> List[Dict]:
        """
        Endpoint: /ratios-ttm/{symbol}
        TTM financial ratios.
        """
        return self._request(f'ratios-ttm/{symbol}', cache=self.cache_symbol)

    def get_enterprise_values(self, symbol: str, period: str = 'quarter', limit: int = 4) -> List[Dict]:
        """
        Endpoint: /enterprise-values/{symbol}
        EV, EV/EBITDA, EV/Sales, etc.
        """
        params = {'period': period, 'limit': limit}
        return self._request(f'enterprise-values/{symbol}', params, cache=self.cache_symbol)

    def get_financial_growth(self, symbol: str, period: str = 'quarter', limit: int = 4) -> List[Dict]:
        """
        Endpoint: /financial-growth/{symbol}
        Growth metrics (revenue growth, earnings growth, etc.)
        """
        params = {'period': period, 'limit': limit}
        return self._request(f'financial-growth/{symbol}', params, cache=self.cache_symbol)

    # ========================
    # Premium Features
    # ========================

    def get_insider_trading(self, symbol: str, limit: int = 100) -> List[Dict]:
        """
        Endpoint: /insider-trading (Premium feature - v4 API)
        Returns insider trading transactions for the symbol.

        Note: This endpoint uses v4 API, not v3.

        Response includes:
        - transactionDate
        - reportingName (insider name)
        - transactionType (P-Purchase, S-Sale, etc.)
        - securitiesTransacted (shares)
        - price
        """
        # Insider trading is a v4 endpoint, so we need to use v4 base URL
        v4_base_url = self.base_url.replace('/api/v3', '/api/v4')
        url = f"{v4_base_url}/insider-trading"
        params = {'symbol': symbol, 'page': 0}  # v4 uses 'page' instead of 'limit'
        params['apikey'] = self.api_key

        # Check cache first
        if self.cache_symbol:
            cached = self.cache_symbol.get(url, params)
            if cached is not None:
                self.total_cached += 1
                return cached

        # Rate limit
        self.rate_limiter.wait()

        # Track metrics
        self.total_requests += 1
        self.requests_by_endpoint['insider-trading'] = self.requests_by_endpoint.get('insider-trading', 0) + 1

        try:
            # Log request details
            safe_params = {k: (v[:10] + '...' if k == 'apikey' and v else v) for k, v in params.items()}
            logger.info(f"→ API Request (v4): GET {url} params={safe_params}")

            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            # Handle error responses
            if isinstance(data, dict) and 'Error Message' in data:
                logger.warning(f"API error for insider-trading: {data['Error Message']}")
                return []

            # Cache successful response
            if self.cache_symbol and isinstance(data, list):
                self.cache_symbol.set(url, params, data)

            return data if isinstance(data, list) else []

        except requests.exceptions.Timeout:
            logger.warning(f"Timeout for insider-trading ({symbol})")
            return []
        except requests.exceptions.RequestException as e:
            logger.warning(f"Request error for insider-trading ({symbol}): {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error for insider-trading ({symbol}): {e}")
            return []

    # ========================
    # Qualitative (on-demand)
    # ========================

    def get_stock_news(self, symbol: str, limit: int = 20) -> List[Dict]:
        """Endpoint: /stock_news?tickers={symbol}"""
        params = {'tickers': symbol, 'limit': limit}
        return self._request('stock_news', params, cache=self.cache_qualitative)

    def get_press_releases(self, symbol: str, limit: int = 20) -> List[Dict]:
        """Endpoint: /press-releases/{symbol}"""
        params = {'limit': limit}
        return self._request(f'press-releases/{symbol}', params, cache=self.cache_qualitative)

    def get_earnings_call_transcript(
        self,
        symbol: str,
        limit: Optional[int] = 4,
        year: Optional[int] = None,
        quarter: Optional[int] = None
    ) -> List[Dict]:
        """
        Endpoint: /earning_call_transcript/{symbol} (Premium feature)
        Returns earnings call transcripts.

        Args:
            symbol: Stock ticker
            limit: Number of transcripts to return (default 4)
            year: Specific year (optional)
            quarter: Specific quarter (optional)

        Response includes:
        - quarter
        - year
        - date
        - content (full transcript text)
        """
        params = {}
        if limit is not None:
            params['limit'] = limit
        if year:
            params['year'] = year
        if quarter:
            params['quarter'] = quarter

        return self._request(f'earning_call_transcript/{symbol}', params, cache=self.cache_qualitative)

    def get_stock_peers(self, symbol: str) -> List[Dict]:
        """Endpoint: /stock_peers?symbol={symbol}"""
        params = {'symbol': symbol}
        return self._request('stock_peers', params, cache=self.cache_qualitative)

    def get_key_executives(self, symbol: str) -> List[Dict]:
        """Endpoint: /key-executives/{symbol}"""
        return self._request(f'key-executives/{symbol}', cache=self.cache_qualitative)

    def get_institutional_holders(self, symbol: str) -> List[Dict]:
        """
        Endpoint: /institutional-holder/{symbol}
        Returns list of institutional holders with their positions.
        """
        return self._request(f'institutional-holder/{symbol}', cache=self.cache_qualitative)

    def get_earnings_calendar(self, from_date: str = None, to_date: str = None) -> List[Dict]:
        """
        Endpoint: /earning_calendar
        Returns earnings calendar for specified date range.
        If no dates specified, returns upcoming earnings.
        """
        params = {}
        if from_date:
            params['from'] = from_date
        if to_date:
            params['to'] = to_date

        return self._request('earning_calendar', params=params, cache=self.cache_symbol)

    # ========================
    # Metrics & Stats
    # ========================

    def get_metrics(self) -> Dict[str, Any]:
        """Return request metrics and cache stats."""
        return {
            "total_requests": self.total_requests,
            "total_cached": self.total_cached,
            "requests_by_endpoint": self.requests_by_endpoint,
            "cache_stats": {
                "universe": self.cache_universe.get_stats(),
                "symbol": self.cache_symbol.get_stats(),
                "qualitative": self.cache_qualitative.get_stats()
            },
            "errors": self.errors
        }
