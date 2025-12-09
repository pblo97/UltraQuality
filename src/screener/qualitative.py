"""
Qualitative analysis module (on-demand per symbol).
Provides deep-dive analysis including:
- Business description
- Competitive position & moats
- Skin in the game (insider activity)
- Recent news & press releases
- Latest earnings transcript summary
- M&A activity
- Key risks
"""
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import re

logger = logging.getLogger(__name__)


class QualitativeAnalyzer:
    """
    On-demand qualitative analysis for selected symbols.
    Cached for 24-72h to minimize API calls.
    """

    def __init__(self, fmp_client, config: Dict):
        self.fmp = fmp_client
        self.config = config

    def analyze_symbol(
        self,
        symbol: str,
        company_type: str,
        peers_df: Optional[Any] = None
    ) -> Dict:
        """
        Full qualitative analysis for a symbol.

        Args:
            symbol: Stock ticker
            company_type: 'non_financial', 'financial', or 'reit'
            peers_df: Optional DataFrame with peer metrics (for comparison)

        Returns:
            qualitative_summary dict (see schema in docstring below)
        """
        logger.info(f"Starting qualitative analysis for {symbol}")

        summary = {
            'symbol': symbol,
            'as_of': datetime.now().strftime('%Y-%m-%d'),
            'business_summary': '',
            'peers_list': [],
            'peer_snapshot': [],
            'moats': [],  # Changed to list for UI compatibility
            'moats_raw': {},  # Keep raw data
            'skin_in_the_game': {},
            'insider_trading': {},  # UI expects this
            'news_TLDR': [],
            'recent_news': [],  # UI expects this
            'news_tags': [],
            'pr_highlights': [],
            'transcript_TLDR': {},
            'backlog_data': {},  # New: backlog/order book analysis
            'mna_recent': [],
            'top_risks': [],
            'risks': [],  # UI expects this
            'intrinsic_value': {},  # New: valuation analysis
            'contextual_warnings': []  # New: non-disqualifying warnings (customer concentration, etc.)
        }

        try:
            # 1. Business description
            summary['business_summary'] = self._get_business_summary(symbol)

            # 2. Peers & competitive position
            summary['peers_list'], summary['peer_snapshot'] = self._get_peer_analysis(
                symbol, company_type, peers_df
            )

            # 3. Moats (competitive advantages)
            summary['moats_raw'] = self._assess_moats(
                symbol,
                summary['business_summary'],
                summary['peer_snapshot']
            )
            # Format moats as readable list
            summary['moats'] = self._format_moats(summary['moats_raw'])

            # 4. Skin in the game (insiders & dilution)
            summary['skin_in_the_game'] = self._assess_skin_in_game(symbol)
            summary['insider_trading'] = summary['skin_in_the_game']  # UI compatibility

            # 5. News & PR (last 60-90 days)
            summary['news_TLDR'], summary['news_tags'] = self._summarize_news(symbol, days=90)
            summary['pr_highlights'] = self._summarize_press_releases(symbol, days=90)
            # Format news for UI
            summary['recent_news'] = self._format_news(summary['news_TLDR'], summary['news_tags'])

            # 6. Latest earnings transcript
            summary['transcript_TLDR'] = self._summarize_transcript(symbol)

            # 6b. Backlog analysis (for order-driven industrials)
            # Get industry from profile
            try:
                profile = self.fmp.get_profile(symbol)
                industry = profile[0].get('industry', '') if profile else ''
            except:
                industry = ''
            summary['backlog_data'] = self._extract_backlog_data(symbol, industry)

            # 7. Recent M&A
            summary['mna_recent'] = self._get_recent_mna(symbol)

            # 8. Top risks (synthesized)
            summary['top_risks'] = self._synthesize_risks(
                symbol,
                summary['transcript_TLDR'],
                summary['news_TLDR'],
                summary['news_tags']
            )
            # Format risks for UI
            summary['risks'] = self._format_risks(summary['top_risks'])

            # 9. Intrinsic value estimation
            summary['intrinsic_value'] = self._estimate_intrinsic_value(
                symbol,
                company_type,
                peers_df,
                summary.get('peers_list', [])
            )

            # 10. Contextual Warnings (non-disqualifying)
            # These are informational only, don't affect scoring
            summary['contextual_warnings'] = self._assess_contextual_warnings(
                symbol,
                summary['transcript_TLDR']
            )

        except Exception as e:
            logger.error(f"Error in qualitative analysis for {symbol}: {e}")
            summary['error'] = str(e)

        return summary

    # ===================================
    # 1. Business Description
    # ===================================

    def _get_business_summary(self, symbol: str) -> str:
        """
        Generate 300-600 char business summary.
        Focus: What they sell, to whom, how they make money, key operational drivers.
        """
        try:
            profile = self.fmp.get_profile(symbol)
            if not profile:
                return "No profile data available."

            prof = profile[0]
            description = prof.get('description', '')
            sector = prof.get('sector', '')
            industry = prof.get('industry', '')

            # Truncate and clean description
            # Remove marketing fluff, extract core business
            summary = self._extract_business_core(description, sector, industry)

            # Limit to 600 chars
            if len(summary) > 600:
                summary = summary[:597] + '...'

            return summary

        except Exception as e:
            logger.warning(f"Failed to get business summary for {symbol}: {e}")
            return "Business summary unavailable."

    def _extract_business_core(self, description: str, sector: str, industry: str) -> str:
        """
        Heuristic extraction of core business from long description.
        Remove marketing language, focus on operations.
        """
        # Simple approach: take first 2-3 sentences
        sentences = re.split(r'[.!?]', description)
        core = '. '.join([s.strip() for s in sentences[:3] if s.strip()])

        # Add sector/industry context if description is too short
        if len(core) < 100:
            core = f"{industry} company in {sector} sector. {core}"

        return core

    # ===================================
    # 2. Peers & Competitive Position
    # ===================================

    def _get_peer_analysis(
        self,
        symbol: str,
        company_type: str,
        peers_df: Optional[Any]
    ) -> tuple:
        """
        Get list of peers and comparison snapshot.

        Returns: (peers_list, peer_snapshot)
        """
        try:
            # Get peers from FMP
            peers_data = self.fmp.get_stock_peers(symbol)

            if not peers_data or 'peersList' not in peers_data[0]:
                return [], []

            peers_list = peers_data[0]['peersList'][:5]  # Top 5 peers

            # Get peer profiles for enrichment
            peer_profiles = self.fmp.get_profile_bulk(peers_list)

            # Build snapshot with key metrics
            peer_snapshot = []

            for peer_symbol in peers_list:
                peer_info = next((p for p in peer_profiles if p['symbol'] == peer_symbol), None)

                if not peer_info:
                    continue

                snapshot_row = {
                    'symbol': peer_symbol,
                    'name': peer_info.get('companyName', ''),
                    'marketCap': peer_info.get('mktCap', 0),
                    'sector': peer_info.get('sector', ''),
                    'industry': peer_info.get('industry', '')
                }

                # Add key metrics based on company type
                # (If peers_df is provided with pre-calculated metrics, use that)
                if peers_df is not None and peer_symbol in peers_df.index:
                    row = peers_df.loc[peer_symbol]

                    if company_type == 'non_financial':
                        snapshot_row.update({
                            'ev_ebit_ttm': row.get('ev_ebit_ttm'),
                            'roic_%': row.get('roic_%'),
                            'fcf_margin_%': row.get('fcf_margin_%')
                        })
                    elif company_type == 'financial':
                        snapshot_row.update({
                            'pe_ttm': row.get('pe_ttm'),
                            'roe_%': row.get('roe_%'),
                            'efficiency_ratio': row.get('efficiency_ratio')
                        })
                    elif company_type == 'asset_manager':
                        snapshot_row.update({
                            'pe_ttm': row.get('pe_ttm'),
                            'roe_%': row.get('roe_%'),
                            'aum_growth_%': row.get('aum_growth_%', 'N/A')
                        })
                    elif company_type == 'reit':
                        snapshot_row.update({
                            'p_ffo': row.get('p_ffo'),
                            'ffo_payout_%': row.get('ffo_payout_%'),
                            'occupancy_%': row.get('occupancy_%')
                        })

                peer_snapshot.append(snapshot_row)

            return peers_list, peer_snapshot

        except Exception as e:
            logger.warning(f"Failed to get peer analysis for {symbol}: {e}")
            return [], []

    # ===================================
    # 3. Moats (Competitive Advantages)
    # ===================================

    def _assess_moats(
        self,
        symbol: str,
        business_summary: str,
        peer_snapshot: List[Dict]
    ) -> Dict:
        """
        Assess competitive moats using multi-factor analysis.

        Enhanced detection combining:
        - Business description keywords
        - Industry/sector analysis
        - Financial metrics (margins, ROIC)
        - Competitive position (market cap vs peers)
        - Company profile data

        Moat types:
        - Switching costs
        - Network effects
        - Brand / IP / Intangibles
        - Scale / efficiency advantages
        - Regulatory assets / licenses

        Returns: {moat_type: 'Strong|Probable|Weak|No', notes: str, confidence: str}
        """
        moats = {
            'switching_costs': 'No',
            'network_effects': 'No',
            'brand_IP': 'No',
            'scale_efficiency': 'No',
            'regulatory_assets': 'No',
            'notes': '',
            'confidence': 'Low'
        }

        try:
            # Get additional context
            profile = self.fmp.get_profile(symbol)
            if not profile:
                return self._assess_moats_basic(business_summary)

            prof = profile[0]
            industry = (prof.get('industry', '')).lower()
            sector = (prof.get('sector', '')).lower()
            market_cap = prof.get('mktCap', 0)
            company_name = prof.get('companyName', '')

            summary_lower = business_summary.lower()
            combined_text = f"{summary_lower} {industry} {sector}"

            # Special handling for mega-cap tech companies with known strong moats
            # These are well-documented companies with clear competitive advantages
            mega_tech_moats = {
                'alphabet': {'switching': True, 'network': True, 'brand': True, 'scale': True},
                'google': {'switching': True, 'network': True, 'brand': True, 'scale': True},
                'apple': {'switching': True, 'network': False, 'brand': True, 'scale': True},
                'microsoft': {'switching': True, 'network': False, 'brand': True, 'scale': True},
                'amazon': {'switching': True, 'network': True, 'brand': True, 'scale': True},
                'meta': {'switching': False, 'network': True, 'brand': True, 'scale': True},
                'facebook': {'switching': False, 'network': True, 'brand': True, 'scale': True},
                'nvidia': {'switching': True, 'network': False, 'brand': True, 'scale': True}
            }

            company_name_lower = company_name.lower()
            symbol_lower = symbol.lower()

            # Check if this is a known mega-cap tech
            known_moats = None
            for brand, moat_profile in mega_tech_moats.items():
                if brand in company_name_lower or brand in symbol_lower:
                    known_moats = moat_profile
                    break

            # === 1. SWITCHING COSTS ===
            switching_evidence = []

            if known_moats and known_moats.get('switching'):
                switching_evidence.append('Ecosystem lock-in (proven)')
                moats['switching_costs'] = 'Strong'
            # Strong indicators
            elif any(kw in combined_text for kw in [
                'enterprise software', 'saas', 'cloud platform', 'erp', 'crm',
                'database', 'operating system', 'productivity suite',
                'mission-critical', 'integrated platform', 'ecosystem'
            ]):
                switching_evidence.append('Enterprise/mission-critical software')
                moats['switching_costs'] = 'Strong'

            # Probable indicators
            elif any(kw in combined_text for kw in [
                'subscription', 'recurring revenue', 'long-term contract',
                'platform', 'multi-year', 'customer data', 'workflow'
            ]):
                switching_evidence.append('Subscription/contract model')
                moats['switching_costs'] = 'Probable'

            # === 2. NETWORK EFFECTS ===
            network_evidence = []

            if known_moats and known_moats.get('network'):
                network_evidence.append('Multi-sided platform (proven)')
                moats['network_effects'] = 'Strong'
            # Strong indicators
            elif any(kw in combined_text for kw in [
                'search engine', 'social network', 'social media', 'messaging',
                'marketplace', 'two-sided platform', 'payment network',
                'ride-sharing', 'food delivery', 'app store'
            ]):
                network_evidence.append('Multi-sided platform/network')
                moats['network_effects'] = 'Strong'

            # Probable indicators
            elif any(kw in combined_text for kw in [
                'platform', 'network', 'community', 'user-generated',
                'developer ecosystem', 'third-party'
            ]):
                network_evidence.append('Platform with ecosystem')
                moats['network_effects'] = 'Probable'

            # === 3. BRAND & INTELLECTUAL PROPERTY ===
            brand_evidence = []

            if known_moats and known_moats.get('brand'):
                brand_evidence.append('Globally recognized brand (proven)')
                moats['brand_IP'] = 'Strong'
            else:
                # Check for well-known brands (top tech/consumer companies)
                major_brands = ['alphabet', 'google', 'apple', 'microsoft', 'amazon',
                               'facebook', 'meta', 'netflix', 'tesla', 'nvidia',
                               'nike', 'coca-cola', 'disney', 'visa', 'mastercard',
                               'mcdonalds', 'starbucks', 'oracle', 'salesforce', 'adobe',
                               'paypal', 'intel', 'amd', 'qualcomm', 'broadcom']

                # Check both company name and ticker
                is_major_brand = any(brand in company_name_lower or brand in symbol_lower for brand in major_brands)

                if is_major_brand:
                    brand_evidence.append('Globally recognized brand')
                    moats['brand_IP'] = 'Strong'

            # Strong IP indicators (if not already set as Strong)
            if moats['brand_IP'] != 'Strong' and any(kw in combined_text for kw in [
                'patent', 'proprietary technology', 'intellectual property',
                'algorithm', 'ai model', 'machine learning', 'trade secret',
                'exclusive license', 'semiconductor design', 'drug pipeline'
            ]):
                brand_evidence.append('Strong IP portfolio')
                moats['brand_IP'] = 'Strong'

            # Probable indicators
            elif any(kw in combined_text for kw in [
                'brand', 'trademark', 'licensed', 'franchise', 'premium',
                'luxury', 'reputation', 'trust'
            ]):
                brand_evidence.append('Brand recognition')
                moats['brand_IP'] = 'Probable'

            # === 4. SCALE & COST ADVANTAGES ===
            scale_evidence = []

            if known_moats and known_moats.get('scale'):
                scale_evidence.append('Massive scale and infrastructure (proven)')
                moats['scale_efficiency'] = 'Strong'

            # Check market cap vs peers
            if moats['scale_efficiency'] != 'Strong' and peer_snapshot and market_cap > 0:
                peer_mcaps = [p.get('marketCap', 0) for p in peer_snapshot if p.get('marketCap')]
                if peer_mcaps:
                    avg_peer_mcap = sum(peer_mcaps) / len(peer_mcaps)
                    if market_cap > avg_peer_mcap * 3:
                        scale_evidence.append(f'Market cap {market_cap/1e9:.1f}B vs peers {avg_peer_mcap/1e9:.1f}B avg')
                        moats['scale_efficiency'] = 'Strong' if moats['scale_efficiency'] != 'Strong' else 'Strong'

            # Strong indicators
            if any(kw in combined_text for kw in [
                'largest', 'market leader', 'dominant', '#1', 'leading provider',
                'economies of scale', 'cost advantage', 'low-cost producer',
                'manufacturing scale', 'distribution network', 'global footprint'
            ]):
                scale_evidence.append('Market leadership/scale')
                if moats['scale_efficiency'] == 'No':
                    moats['scale_efficiency'] = 'Strong'

            # Probable indicators
            elif any(kw in combined_text for kw in [
                'scale', 'leading', 'major', 'significant market share',
                'infrastructure', 'data centers', 'warehouse network'
            ]):
                scale_evidence.append('Significant scale')
                if moats['scale_efficiency'] == 'No':
                    moats['scale_efficiency'] = 'Probable'

            # === 5. REGULATORY BARRIERS ===
            regulatory_evidence = []

            # Strong indicators
            if any(kw in combined_text for kw in [
                'regulated utility', 'telecom license', 'spectrum license',
                'fda approved', 'pharmaceutical', 'biotech', 'drug',
                'banking license', 'insurance license', 'gaming license'
            ]):
                regulatory_evidence.append('Regulated industry/licenses required')
                moats['regulatory_assets'] = 'Strong'

            # Probable indicators
            elif any(kw in combined_text for kw in [
                'regulated', 'license', 'compliance', 'certification',
                'approval required', 'barrier to entry'
            ]):
                regulatory_evidence.append('Regulatory requirements')
                moats['regulatory_assets'] = 'Probable'

            # === GENERATE NOTES & CONFIDENCE ===

            moat_count = sum(1 for k, v in moats.items() if k != 'notes' and k != 'confidence' and v in ['Strong', 'Probable'])
            strong_count = sum(1 for k, v in moats.items() if k != 'notes' and k != 'confidence' and v == 'Strong')

            # Confidence based on evidence
            if strong_count >= 2:
                moats['confidence'] = 'High'
            elif moat_count >= 3:
                moats['confidence'] = 'Medium'
            else:
                moats['confidence'] = 'Low'

            # Detailed notes
            evidence_summary = []
            if switching_evidence:
                evidence_summary.append(f"Switching: {', '.join(switching_evidence)}")
            if network_evidence:
                evidence_summary.append(f"Network: {', '.join(network_evidence)}")
            if brand_evidence:
                evidence_summary.append(f"Brand/IP: {', '.join(brand_evidence)}")
            if scale_evidence:
                evidence_summary.append(f"Scale: {', '.join(scale_evidence)}")
            if regulatory_evidence:
                evidence_summary.append(f"Regulatory: {', '.join(regulatory_evidence)}")

            moats['notes'] = f"{moat_count} moats identified ({strong_count} strong). " + " | ".join(evidence_summary) if evidence_summary else f"{moat_count} moats identified."

        except Exception as e:
            logger.warning(f"Enhanced moat analysis failed for {symbol}, falling back to basic: {e}")
            return self._assess_moats_basic(business_summary)

        return moats

    def _assess_moats_basic(self, business_summary: str) -> Dict:
        """Fallback basic moat assessment using only business description."""
        moats = {
            'switching_costs': 'No',
            'network_effects': 'No',
            'brand_IP': 'No',
            'scale_efficiency': 'No',
            'regulatory_assets': 'No',
            'notes': '',
            'confidence': 'Low'
        }

        summary_lower = business_summary.lower()

        if any(kw in summary_lower for kw in ['subscription', 'contract', 'enterprise software', 'SaaS', 'platform']):
            moats['switching_costs'] = 'Probable'
        if any(kw in summary_lower for kw in ['network', 'marketplace', 'social', 'platform', 'two-sided']):
            moats['network_effects'] = 'Probable'
        if any(kw in summary_lower for kw in ['brand', 'patent', 'trademark', 'proprietary', 'licensed', 'franchise']):
            moats['brand_IP'] = 'Probable'
        if any(kw in summary_lower for kw in ['largest', 'leading', 'scale', 'manufacturing', 'distribution']):
            moats['scale_efficiency'] = 'Probable'
        if any(kw in summary_lower for kw in ['regulated', 'license', 'utility', 'telecom', 'pharmaceutical', 'FDA']):
            moats['regulatory_assets'] = 'Probable'

        moat_count = sum(1 for v in moats.values() if v in ['Probable'])
        moats['notes'] = f"{moat_count} potential moats identified from business description (basic analysis)."

        return moats

    # ===================================
    # 4. Skin in the Game
    # ===================================

    def _assess_skin_in_game(self, symbol: str) -> Dict:
        """
        Assess insider alignment and dilution.

        Enhanced to include:
        - Insider ownership % (executives and directors)
        - Insider trading activity (buys vs sells)
        - Share dilution/buybacks

        Returns:
        {
            'insider_ownership_pct': float,
            'institutional_ownership_pct': float,
            'insider_trend_90d': 'net buys|net sells|mixed|none',
            'insider_transactions': {buys: int, sells: int},
            'net_share_issuance_12m_%': float,
            'assessment': 'positive|neutral|negative',
            'buys_6m': int,  # For UI compatibility
            'sells_6m': int
        }
        """
        skin = {
            'insider_ownership_pct': None,
            'institutional_ownership_pct': None,
            'insider_trend_90d': 'none',
            'insider_transactions': {'buys': 0, 'sells': 0},
            'net_share_issuance_12m_%': None,
            'assessment': 'neutral',
            'buys_6m': 0,
            'sells_6m': 0
        }

        # === 1. INSIDER OWNERSHIP % ===
        try:
            # Try multiple approaches to get ownership data

            # Approach 1: Key executives endpoint (may have direct ownership data)
            try:
                key_exec = self.fmp.get_key_executives(symbol)
                if key_exec:
                    # Calculate total shares held by top executives
                    total_exec_shares = 0
                    has_ownership_data = False

                    for exec_data in key_exec[:10]:  # Top 10 executives
                        shares_owned = exec_data.get('sharesOwned', 0) or exec_data.get('totalShares', 0)
                        if shares_owned and shares_owned > 0:
                            total_exec_shares += shares_owned
                            has_ownership_data = True

                    if has_ownership_data:
                        # Get shares outstanding from balance sheet
                        balance = self.fmp.get_balance_sheet(symbol, period='annual', limit=1)
                        if balance:
                            shares_outstanding = balance[0].get('weightedAverageShsOut') or balance[0].get('commonStock', 0)

                            # Convert if needed
                            if shares_outstanding > 1_000_000_000:  # In shares
                                shares_outstanding = shares_outstanding / 1_000_000  # To millions

                            if shares_outstanding > 0:
                                skin['insider_ownership_pct'] = (total_exec_shares / shares_outstanding) * 100
            except Exception as e:
                logger.debug(f"Key executives approach failed: {e}")

            # Approach 2: Key metrics (some companies report it here)
            if skin['insider_ownership_pct'] is None:
                try:
                    key_metrics = self.fmp.get_key_metrics(symbol, period='annual', limit=1)
                    if key_metrics and len(key_metrics) > 0:
                        metrics = key_metrics[0]

                        # Try different field names
                        for field in ['insiderOwnership', 'insider_ownership', 'insidersOwnership']:
                            if field in metrics and metrics[field] is not None:
                                insider_own = metrics[field]
                                if insider_own < 1:  # Decimal format
                                    skin['insider_ownership_pct'] = insider_own * 100
                                else:  # Already percentage
                                    skin['insider_ownership_pct'] = insider_own
                                break
                except Exception as e:
                    logger.debug(f"Key metrics approach failed: {e}")

            # Approach 3: Estimate from profile (founder-led companies)
            if skin['insider_ownership_pct'] is None:
                profile = self.fmp.get_profile(symbol)
                if profile and len(profile) > 0:
                    prof = profile[0]

                    ceo = prof.get('ceo', '').lower()

                    # Known high insider ownership patterns
                    founder_indicators = ['founder', 'co-founder', 'chairman and ceo', 'chairman & ceo']
                    is_founder_led = any(indicator in ceo for indicator in founder_indicators)

                    # Mega-cap tech (large companies) typically have lower insider ownership
                    market_cap = prof.get('mktCap', 0)

                    if is_founder_led:
                        if market_cap > 1_000_000_000_000:  # >$1T
                            skin['insider_ownership_pct'] = 5.0  # Conservative for mega-caps
                        elif market_cap > 100_000_000_000:  # >$100B
                            skin['insider_ownership_pct'] = 8.0
                        else:
                            skin['insider_ownership_pct'] = 15.0
                        skin['notes'] = 'Estimated (founder-led)'
                    else:
                        # Professional management - typically low
                        if market_cap > 100_000_000_000:  # Large cap
                            skin['insider_ownership_pct'] = 0.5
                        else:
                            skin['insider_ownership_pct'] = 2.0
                        skin['notes'] = 'Estimated (professional mgmt)'

            # Institutional ownership (try from key metrics or estimate)
            try:
                if key_metrics and len(key_metrics) > 0:
                    metrics = key_metrics[0]
                    for field in ['institutionalOwnership', 'institutional_ownership']:
                        if field in metrics and metrics[field] is not None:
                            inst_own = metrics[field]
                            if inst_own < 1:
                                skin['institutional_ownership_pct'] = inst_own * 100
                            else:
                                skin['institutional_ownership_pct'] = inst_own
                            break

                # Estimate if not found (large caps typically 70-80% institutional)
                if skin['institutional_ownership_pct'] is None:
                    profile = self.fmp.get_profile(symbol)
                    if profile:
                        market_cap = profile[0].get('mktCap', 0)
                        if market_cap > 100_000_000_000:  # >$100B
                            skin['institutional_ownership_pct'] = 75.0  # Typical for large caps
                        elif market_cap > 10_000_000_000:  # >$10B
                            skin['institutional_ownership_pct'] = 65.0
                        else:
                            skin['institutional_ownership_pct'] = 50.0
            except Exception as e:
                logger.debug(f"Institutional ownership failed: {e}")

        except Exception as e:
            logger.warning(f"Failed to get ownership data for {symbol}: {e}")

        # === 2. INSIDER TRADING ACTIVITY with CLUSTER DETECTION ===
        # IMPORTANT: Filtro de ruido para Mega-Caps (>$100B)
        # En empresas masivas, ventas pequeñas (<50% tenencia) son ruido de 10b5-1 plans
        profile = None
        market_cap = 0
        try:
            profile = self.fmp.get_profile(symbol)
            if profile:
                market_cap = profile[0].get('mktCap', 0)
        except:
            pass

        is_mega_cap = market_cap > 100_000_000_000  # >$100B

        try:
            # Get insider trading transactions (last 6 months)
            insider_trades = self.fmp.get_insider_trading(symbol, limit=100)

            if insider_trades:
                # Count buys and sells in last 6 months
                cutoff = datetime.now() - timedelta(days=180)
                buys = 0
                sells = 0

                # Track for cluster detection
                sell_transactions_by_date = {}  # date -> count
                ceo_sells = 0
                ceo_sell_pct = 0

                # Get key executives names for CEO detection
                try:
                    executives = self.fmp.get_key_executives(symbol)
                    ceo_names = []
                    if executives:
                        for exec_data in executives[:3]:  # Top 3 (likely CEO, CFO, COO)
                            title = exec_data.get('title', '').lower()
                            if 'chief executive' in title or 'ceo' in title:
                                ceo_names.append(exec_data.get('name', '').lower())
                except:
                    ceo_names = []

                for trade in insider_trades:
                    try:
                        trade_date_str = trade.get('transactionDate', trade.get('filingDate', ''))
                        if not trade_date_str:
                            continue

                        trade_date = datetime.fromisoformat(trade_date_str.replace('Z', '+00:00').split('T')[0])

                        if trade_date < cutoff:
                            continue

                        transaction_type = trade.get('transactionType', '').upper()

                        # Count buys vs sells
                        if 'P-PURCHASE' in transaction_type or 'BUY' in transaction_type:
                            buys += 1
                        elif 'S-SALE' in transaction_type or 'SELL' in transaction_type:
                            sells += 1

                            # Track sell date for cluster detection
                            date_key = trade_date_str.split('T')[0]
                            sell_transactions_by_date[date_key] = sell_transactions_by_date.get(date_key, 0) + 1

                            # Check if CEO is selling
                            reporting_person = trade.get('reportingName', '').lower()
                            if any(ceo_name in reporting_person for ceo_name in ceo_names):
                                ceo_sells += 1
                                # Try to get shares owned before/after
                                shares_owned_after = trade.get('securitiesOwned', 0)
                                shares_transacted = trade.get('securitiesTransacted', 0)
                                if shares_owned_after > 0 and shares_transacted > 0:
                                    shares_owned_before = shares_owned_after + shares_transacted
                                    if shares_owned_before > 0:
                                        ceo_sell_pct = max(ceo_sell_pct, (shares_transacted / shares_owned_before) * 100)

                    except Exception as e:
                        logger.debug(f"Error processing trade: {e}")
                        continue

                skin['insider_transactions'] = {'buys': buys, 'sells': sells}
                skin['buys_6m'] = buys
                skin['sells_6m'] = sells

                # Determine trend
                if buys > sells * 2:
                    skin['insider_trend_90d'] = 'net buys'
                elif sells > buys * 2:
                    skin['insider_trend_90d'] = 'net sells'
                elif buys > 0 or sells > 0:
                    skin['insider_trend_90d'] = 'mixed'
                else:
                    skin['insider_trend_90d'] = 'none'

                # === CLUSTER DETECTION ===
                # Red flags: Multiple executives selling on same day/week
                sell_clusters = []
                for date, count in sell_transactions_by_date.items():
                    if count >= 3:  # 3+ executives selling on same day = cluster
                        sell_clusters.append(f"{date} ({count} executives)")

                if sell_clusters:
                    skin['sell_clusters'] = sell_clusters
                    skin['cluster_warning'] = f"⚠️  Insider selling cluster detected: {len(sell_clusters)} dates with 3+ executives selling"

                # CEO selling threshold: Ajustado por tamaño de empresa
                # Mega-caps (>$100B): Solo alertar si venta >50% (ventas menores = 10b5-1 rutinario)
                # Empresas normales: Alertar si venta >20%
                ceo_sell_threshold = 50 if is_mega_cap else 20

                if ceo_sell_pct > ceo_sell_threshold:
                    skin['ceo_large_sale'] = f"⚠️  CEO sold {ceo_sell_pct:.1f}% of holdings in last 6 months (threshold: {ceo_sell_threshold}%)"
                elif is_mega_cap and ceo_sell_pct > 0:
                    # Mega-cap con venta pequeña: Nota informativa, no warning
                    skin['ceo_sale_note'] = f"ℹ️  CEO sold {ceo_sell_pct:.1f}% (likely routine 10b5-1 plan for mega-cap)"

        except Exception as e:
            logger.debug(f"Failed to get insider trading for {symbol}: {e}")

        # === 3. DILUTION / BUYBACKS ===
        try:
            balance = self.fmp.get_balance_sheet(symbol, period='quarter', limit=5)
            if balance and len(balance) >= 5:
                # IMPORTANT: Use weightedAverageShsOut or commonStockSharesOutstanding
                # DO NOT use 'commonStock' (that's par value, not share count)
                shares_t = (balance[0].get('weightedAverageShsOut') or
                           balance[0].get('commonStockSharesOutstanding') or
                           balance[0].get('weightedAverageShsOutDil'))

                # Use 4-quarter lookback for stable 12-month measurement
                shares_t4 = (balance[4].get('weightedAverageShsOut') or
                            balance[4].get('commonStockSharesOutstanding') or
                            balance[4].get('weightedAverageShsOutDil'))

                if shares_t and shares_t4 and shares_t4 > 0:
                    # 12-month change
                    net_issuance_pct = ((shares_t - shares_t4) / shares_t4) * 100

                    # Stock split detection: If close to 50%, 100%, 200%, likely a split
                    # Splits should be adjusted by FMP but sometimes aren't
                    abs_pct = abs(net_issuance_pct)
                    is_likely_split = (
                        (45 <= abs_pct <= 55) or    # 3:2 or 2:3 split
                        (90 <= abs_pct <= 110) or   # 2:1 or 1:2 split
                        (190 <= abs_pct <= 210) or  # 3:1 split
                        (290 <= abs_pct <= 310)     # 4:1 split
                    )

                    if is_likely_split:
                        # Likely a stock split, not actual dilution - set to 0
                        logger.debug(f"Detected potential stock split for {symbol}: {net_issuance_pct:.1f}% change")
                        skin['net_share_issuance_12m_%'] = 0.0
                        skin['notes'] = 'Recent stock split detected'
                    else:
                        skin['net_share_issuance_12m_%'] = net_issuance_pct

        except Exception as e:
            logger.warning(f"Failed to assess dilution for {symbol}: {e}")

        # === 4. OVERALL ASSESSMENT ===
        # Combine all factors

        assessment_score = 0  # Start neutral

        # Insider ownership (higher is better, up to a point)
        if skin['insider_ownership_pct']:
            if skin['insider_ownership_pct'] >= 15:
                assessment_score += 2  # Strong alignment
            elif skin['insider_ownership_pct'] >= 5:
                assessment_score += 1  # Good alignment
            elif skin['insider_ownership_pct'] < 1:
                assessment_score -= 1  # Weak alignment

        # Dilution/buybacks
        if skin['net_share_issuance_12m_%']:
            dilution = skin['net_share_issuance_12m_%']
            if dilution < -2:
                assessment_score += 1  # Buybacks
            elif dilution > 5:
                assessment_score -= 2  # Excessive dilution

        # Final assessment
        if assessment_score >= 2:
            skin['assessment'] = 'positive'
        elif assessment_score <= -2:
            skin['assessment'] = 'negative'
        else:
            skin['assessment'] = 'neutral'

        return skin

    # ===================================
    # 5. News & Press Releases
    # ===================================

    def _summarize_news(self, symbol: str, days: int = 90) -> tuple:
        """
        Summarize stock news from last N days.

        Returns: (news_TLDR: List[str], news_tags: List[str])
        """
        try:
            news = self.fmp.get_stock_news(symbol, limit=12)

            if not news:
                return [], []

            # Filter by date
            cutoff = datetime.now() - timedelta(days=days)
            recent_news = [
                n for n in news
                if datetime.fromisoformat(n.get('publishedDate', '').replace('Z', '+00:00')) > cutoff
            ]

            # Extract key points (simple heuristic: use title + first sentence)
            tldr = []
            tags_set = set()

            for item in recent_news[:6]:  # Top 6
                title = item.get('title', '')
                text = item.get('text', '')

                # Extract first sentence
                summary = title + ': ' + text[:100] if text else title

                tldr.append(summary[:140])

                # Tag classification (keyword-based)
                content_lower = (title + ' ' + text).lower()

                if any(kw in content_lower for kw in ['product', 'launch', 'release']):
                    tags_set.add('products')
                if any(kw in content_lower for kw in ['guidance', 'forecast', 'outlook', 'expect']):
                    tags_set.add('guidance')
                if any(kw in content_lower for kw in ['acquisition', 'merger', 'm&a', 'buyout']):
                    tags_set.add('mna')
                if any(kw in content_lower for kw in ['lawsuit', 'litigation', 'sue', 'settlement']):
                    tags_set.add('litigation')
                if any(kw in content_lower for kw in ['regulation', 'sec', 'fda', 'approval', 'complian']):
                    tags_set.add('regulatory')
                if any(kw in content_lower for kw in ['financing', 'debt', 'equity', 'raise', 'offering']):
                    tags_set.add('financing')
                if any(kw in content_lower for kw in ['esg', 'sustainability', 'environment', 'social']):
                    tags_set.add('ESG')

            return tldr, list(tags_set)

        except Exception as e:
            logger.warning(f"Failed to summarize news for {symbol}: {e}")
            return [], []

    def _summarize_press_releases(self, symbol: str, days: int = 90) -> List[str]:
        """
        Summarize press releases.

        Returns: List of highlight bullets (3-5)
        """
        try:
            pr = self.fmp.get_press_releases(symbol, limit=8)

            if not pr:
                return []

            # Filter by date
            cutoff = datetime.now() - timedelta(days=days)
            recent_pr = [
                p for p in pr
                if datetime.fromisoformat(p.get('date', '').replace('Z', '+00:00')) > cutoff
            ]

            # Extract highlights (title + snippet)
            highlights = []
            for item in recent_pr[:5]:
                title = item.get('title', '')
                text = item.get('text', '')
                snippet = title + ': ' + text[:100] if text else title
                highlights.append(snippet[:140])

            return highlights

        except Exception as e:
            logger.warning(f"Failed to summarize press releases for {symbol}: {e}")
            return []

    # ===================================
    # 6. Earnings Transcript
    # ===================================

    def _summarize_transcript(self, symbol: str) -> Dict:
        """
        Summarize latest earnings call transcript.

        Returns:
        {
            'highlights': List[str],
            'risks': List[str],
            'outlook': List[str],
            'guidance_points': List[Dict]
        }
        """
        tldr = {
            'highlights': [],
            'risks': [],
            'outlook': [],
            'guidance_points': []
        }

        try:
            # Get latest transcript
            transcripts = self.fmp.get_earnings_call_transcript(symbol)

            if not transcripts:
                return tldr

            # FMP returns list; take latest
            transcript = transcripts[0]
            content = transcript.get('content', '')

            if not content:
                return tldr

            # Simple extraction (heuristic-based)
            # In production: use LLM or NLP pipeline

            # Split into sections (if available)
            # Typical structure: Prepared Remarks → Q&A
            sections = content.split('\n\n')

            # Extract highlights (look for growth, margins, customers, unit economics)
            highlights_keywords = ['revenue', 'growth', 'margin', 'customer', 'user', 'cohort', 'ARR', 'bookings']
            for section in sections[:10]:  # First 10 paragraphs
                if any(kw in section.lower() for kw in highlights_keywords):
                    snippet = section[:150].strip()
                    if snippet:
                        tldr['highlights'].append(snippet)

            tldr['highlights'] = tldr['highlights'][:5]  # Top 5

            # Extract risks (look for "risk", "challenge", "headwind")
            risk_keywords = ['risk', 'challenge', 'headwind', 'concern', 'uncertainty', 'pressure']
            for section in sections[:10]:
                if any(kw in section.lower() for kw in risk_keywords):
                    snippet = section[:150].strip()
                    if snippet:
                        tldr['risks'].append(snippet)

            tldr['risks'] = tldr['risks'][:4]  # Top 4

            # Extract outlook / guidance
            outlook_keywords = ['guidance', 'outlook', 'expect', 'anticipate', 'forecast', 'next quarter', 'FY']
            for section in sections:
                if any(kw in section.lower() for kw in outlook_keywords):
                    snippet = section[:150].strip()
                    if snippet:
                        tldr['outlook'].append(snippet)

            tldr['outlook'] = tldr['outlook'][:3]  # Top 3

            # Extract numeric guidance (if present)
            # Look for patterns like "Q4 revenue $X-Y million" or "FY EPS $Z"
            guidance_pattern = r'(Q\d|FY\d{2,4}|full[- ]year)\s+(revenue|EPS|earnings|EBITDA)[^\d]*([\d.,]+[BMK%]?)'
            matches = re.findall(guidance_pattern, content, re.IGNORECASE)

            for match in matches[:3]:
                tldr['guidance_points'].append({
                    'horizon': match[0],
                    'metric': match[1],
                    'value': match[2]
                })

        except Exception as e:
            logger.warning(f"Failed to summarize transcript for {symbol}: {e}")

        return tldr

    def _extract_backlog_data(self, symbol: str, industry: str = '') -> Dict:
        """
        Extract backlog/order book data from latest earnings call transcript.
        Particularly valuable for order-driven industrials: Aerospace & Defense,
        Heavy Equipment, Shipbuilding, Capital Goods, etc.

        Returns:
        {
            'backlog_mentioned': bool,
            'backlog_value': str,  # e.g., "$45.2B"
            'backlog_change': str,  # e.g., "+12% YoY"
            'book_to_bill': str,   # e.g., "1.2x"
            'backlog_duration': str,  # e.g., "18 months"
            'backlog_snippets': List[str],  # Relevant quotes
            'order_trend': str  # 'Positive', 'Stable', 'Declining', or 'Unknown'
        }
        """
        result = {
            'backlog_mentioned': False,
            'backlog_value': None,
            'backlog_change': None,
            'book_to_bill': None,
            'backlog_duration': None,
            'backlog_snippets': [],
            'order_trend': 'Unknown'
        }

        # Only relevant for order-driven companies
        order_driven_keywords = [
            'aerospace', 'defense', 'aircraft', 'aviation',
            'heavy equipment', 'machinery', 'capital goods',
            'shipbuilding', 'industrial equipment', 'construction equipment',
            'engineering', 'turbine', 'locomotive', 'mining equipment'
        ]

        industry_lower = industry.lower()
        is_order_driven = any(keyword in industry_lower for keyword in order_driven_keywords)

        if not is_order_driven:
            # Not an order-driven business - skip backlog analysis
            return result

        try:
            # Get latest transcript
            transcripts = self.fmp.get_earnings_call_transcript(symbol)

            if not transcripts:
                return result

            transcript = transcripts[0]
            content = transcript.get('content', '')

            if not content:
                return result

            content_lower = content.lower()

            # Check if backlog is mentioned
            backlog_keywords = ['backlog', 'order book', 'orders', 'book-to-bill', 'book to bill', 'bookings']
            backlog_mentioned = any(keyword in content_lower for keyword in backlog_keywords)

            if not backlog_mentioned:
                return result

            result['backlog_mentioned'] = True

            # Extract backlog value (dollar amounts)
            # Pattern: "backlog of $X.XB" or "order book of $X.X billion"
            backlog_value_patterns = [
                r'backlog\s+(?:of|is|was|totaled|reached|stood at)\s+[\$€£]?([\d,.]+)\s*(billion|million|B|M|bn|mn)',
                r'order\s+book\s+(?:of|is|was|totaled|reached|stood at)\s+[\$€£]?([\d,.]+)\s*(billion|million|B|M|bn|mn)',
                r'total\s+backlog\s+[\$€£]?([\d,.]+)\s*(billion|million|B|M|bn|mn)',
                r'[\$€£]([\d,.]+)\s*(billion|million|B|M|bn|mn)\s+(?:in|of)\s+backlog'
            ]

            for pattern in backlog_value_patterns:
                match = re.search(pattern, content_lower)
                if match:
                    value = match.group(1)
                    unit = match.group(2)
                    # Normalize unit
                    if unit.lower() in ['billion', 'b', 'bn']:
                        unit_str = 'B'
                    else:
                        unit_str = 'M'
                    result['backlog_value'] = f"${value}{unit_str}"
                    break

            # Extract backlog change (YoY or QoQ)
            change_patterns = [
                r'backlog\s+(?:increased|grew|rose|up|higher)\s+(?:by\s+)?([\d.]+)%',
                r'backlog\s+(?:decreased|declined|fell|down|lower)\s+(?:by\s+)?([\d.]+)%',
                r'([\d.]+)%\s+(?:increase|growth|rise)\s+in\s+backlog',
                r'([\d.]+)%\s+(?:decrease|decline|drop)\s+in\s+backlog',
                r'backlog\s+of\s+[\$€£][\d,.]+[BMbm],?\s+(?:up|down)\s+([\d.]+)%'
            ]

            for pattern in change_patterns:
                match = re.search(pattern, content_lower)
                if match:
                    change_pct = match.group(1)
                    # Check if positive or negative from context
                    context = match.group(0).lower()
                    if any(word in context for word in ['increase', 'grew', 'rose', 'up', 'higher']):
                        result['backlog_change'] = f"+{change_pct}%"
                        result['order_trend'] = 'Positive'
                    elif any(word in context for word in ['decrease', 'declined', 'fell', 'down', 'lower']):
                        result['backlog_change'] = f"-{change_pct}%"
                        result['order_trend'] = 'Declining'
                    else:
                        result['backlog_change'] = f"{change_pct}%"
                    break

            # Extract book-to-bill ratio
            btb_patterns = [
                r'book[- ]to[- ]bill\s+(?:ratio\s+)?(?:of\s+)?(\d+\.?\d*)\b',
                r'book[- ]to[- ]bill\s+(?:was|is)\s+(\d+\.?\d*)\b',
                r'btb\s+(?:ratio\s+)?(?:of\s+)?(\d+\.?\d*)\b'
            ]

            for pattern in btb_patterns:
                match = re.search(pattern, content_lower)
                if match:
                    btb_value = match.group(1)
                    result['book_to_bill'] = f"{btb_value}x"
                    # Book-to-bill > 1.0 is positive (orders exceeding revenue)
                    try:
                        btb_float = float(btb_value)
                        if btb_float > 1.0:
                            result['order_trend'] = 'Positive'
                        elif btb_float < 0.9:
                            result['order_trend'] = 'Declining'
                        else:
                            result['order_trend'] = 'Stable'
                    except:
                        pass
                    break

            # Extract backlog duration
            duration_patterns = [
                r'backlog\s+(?:represents|equals|covers)\s+(?:approximately\s+)?([\d.]+)\s+(months|quarters|years)',
                r'([\d.]+)[- ](month|quarter|year)\s+backlog',
                r'backlog\s+of\s+(?:approximately\s+)?([\d.]+)\s+(months|quarters|years)'
            ]

            for pattern in duration_patterns:
                match = re.search(pattern, content_lower)
                if match:
                    duration_num = match.group(1)
                    duration_unit = match.group(2)
                    result['backlog_duration'] = f"{duration_num} {duration_unit}"
                    break

            # Extract relevant snippets (sentences mentioning backlog)
            sentences = re.split(r'[.!?]\s+', content)
            for sentence in sentences:
                sentence_lower = sentence.lower()
                if any(keyword in sentence_lower for keyword in backlog_keywords):
                    # Clean up and limit length
                    snippet = sentence.strip()[:200]
                    if snippet and len(snippet) > 30:  # Meaningful snippet
                        result['backlog_snippets'].append(snippet)

            # Limit snippets to top 3 most relevant
            result['backlog_snippets'] = result['backlog_snippets'][:3]

            # If no explicit change detected but backlog mentioned, check overall sentiment
            if result['order_trend'] == 'Unknown' and result['backlog_mentioned']:
                # Look for qualitative indicators
                positive_indicators = ['strong backlog', 'robust backlog', 'record backlog', 'growing backlog',
                                     'healthy backlog', 'solid backlog', 'improving backlog']
                negative_indicators = ['weak backlog', 'declining backlog', 'softening backlog', 'lower backlog',
                                     'reduced backlog', 'challenging backlog']

                if any(indicator in content_lower for indicator in positive_indicators):
                    result['order_trend'] = 'Positive'
                elif any(indicator in content_lower for indicator in negative_indicators):
                    result['order_trend'] = 'Declining'
                else:
                    result['order_trend'] = 'Stable'

            logger.info(f"Backlog analysis for {symbol}: {result['order_trend']} trend, "
                       f"Value: {result.get('backlog_value', 'N/A')}, "
                       f"Change: {result.get('backlog_change', 'N/A')}")

        except Exception as e:
            logger.warning(f"Failed to extract backlog data for {symbol}: {e}")

        return result

    def _assess_contextual_warnings(
        self,
        symbol: str,
        transcript_tldr: Dict
    ) -> List[Dict]:
        """
        Assess contextual warnings (non-disqualifying, informational only).
        These do NOT affect scoring VERDE/AMBAR/ROJO.

        Métricas:
        1. Customer Concentration - revenue dependency on few customers
        2. Management Turnover - CEO/CFO changes (instability flag)
        3. Geographic Revenue Exposure - geopolitical risk

        Returns: List of warning dicts:
        {
            'type': str,  # 'customer_concentration', 'management_turnover', 'geographic_risk'
            'severity': str,  # 'Info', 'Caution', 'Warning'
            'message': str,
            'details': str
        }
        """
        warnings = []

        try:
            # Get industry for context
            profile = self.fmp.get_profile(symbol)
            industry = profile[0].get('industry', '') if profile else ''

            # 1. Customer Concentration Analysis
            customer_warning = self._analyze_customer_concentration(symbol)
            if customer_warning:
                warnings.append(customer_warning)

            # 2. Management Turnover Flags
            mgmt_warning = self._analyze_management_turnover(symbol)
            if mgmt_warning:
                warnings.append(mgmt_warning)

            # 3. Geographic Revenue Exposure
            geo_warning = self._analyze_geographic_exposure(symbol)
            if geo_warning:
                warnings.append(geo_warning)

            # 4. R&D Efficiency (Tech/Pharma only)
            rd_warning = self._analyze_rd_efficiency(symbol, industry)
            if rd_warning:
                warnings.append(rd_warning)

        except Exception as e:
            logger.warning(f"Error assessing contextual warnings for {symbol}: {e}")

        return warnings

    def _analyze_customer_concentration(self, symbol: str) -> Optional[Dict]:
        """
        Analyze customer concentration risk from earnings call transcripts.

        High Risk: Single customer >20% of revenue
        Medium Risk: Single customer 10-20%
        Low Risk: Top customer <10%
        """
        try:
            # Get latest transcript
            transcripts = self.fmp.get_earnings_call_transcript(symbol)
            if not transcripts:
                return None

            transcript = transcripts[0]
            content = transcript.get('content', '')
            if not content:
                return None

            content_lower = content.lower()

            # Search patterns for customer concentration
            concentration_patterns = [
                r'(?:largest|top|single|major)\s+customer\s+(?:represents|accounts for|comprises)\s+(?:approximately\s+)?([\d.]+)%',
                r'([\d.]+)%\s+of\s+(?:our\s+)?(?:total\s+)?revenue\s+(?:comes\s+)?from\s+(?:a\s+)?single\s+customer',
                r'customer\s+concentration\s+(?:of\s+)?(?:approximately\s+)?([\d.]+)%',
                r'one\s+customer\s+accounted\s+for\s+(?:approximately\s+)?([\d.]+)%'
            ]

            max_concentration = 0
            for pattern in concentration_patterns:
                matches = re.findall(pattern, content_lower)
                for match in matches:
                    try:
                        pct = float(match)
                        if pct > max_concentration and pct < 100:  # Sanity check
                            max_concentration = pct
                    except:
                        pass

            # Also search for qualitative mentions
            high_risk_keywords = [
                'significant customer concentration',
                'heavily dependent on',
                'reliance on a single customer',
                'loss of our largest customer'
            ]

            has_qualitative_mention = any(kw in content_lower for kw in high_risk_keywords)

            # Generate warning
            if max_concentration > 20 or (has_qualitative_mention and max_concentration > 15):
                return {
                    'type': 'customer_concentration',
                    'severity': 'Warning',
                    'message': f'High customer concentration risk',
                    'details': f'Single customer represents {max_concentration:.0f}% of revenue - loss would be material'
                }
            elif max_concentration > 10:
                return {
                    'type': 'customer_concentration',
                    'severity': 'Caution',
                    'message': f'Moderate customer concentration',
                    'details': f'Top customer {max_concentration:.0f}% of revenue - monitor for changes'
                }
            elif has_qualitative_mention:
                return {
                    'type': 'customer_concentration',
                    'severity': 'Info',
                    'message': 'Customer concentration mentioned',
                    'details': 'Management discussed customer concentration in earnings call'
                }

        except Exception as e:
            logger.warning(f"Error analyzing customer concentration for {symbol}: {e}")

        return None

    def _analyze_management_turnover(self, symbol: str) -> Optional[Dict]:
        """
        Analyze CEO/CFO turnover as instability flag.

        High Risk: 2+ CFO changes in 3 years
        Medium Risk: CEO change in last 2 years
        Info: Recent C-suite departure
        """
        try:
            # Get key executives
            executives = self.fmp.get_key_executives(symbol)
            if not executives:
                return None

            # FMP doesn't provide tenure history, so we'll check news
            # for recent departures/changes
            news = self.fmp.get_stock_news(symbol, limit=50)
            if not news:
                return None

            # Search for executive changes in news
            cfo_changes = 0
            ceo_changes = 0
            recent_departures = []

            for article in news:
                title = article.get('title', '').lower()
                text = article.get('text', '').lower()
                date = article.get('publishedDate', '')

                # Check for CFO/CEO changes
                if any(keyword in title or keyword in text for keyword in [
                    'cfo resign', 'cfo depart', 'cfo step', 'chief financial officer resign',
                    'new cfo', 'appoint cfo', 'interim cfo'
                ]):
                    cfo_changes += 1
                    recent_departures.append(f"CFO change mentioned in news ({date[:10]})")

                if any(keyword in title or keyword in text for keyword in [
                    'ceo resign', 'ceo depart', 'ceo step', 'chief executive resign',
                    'new ceo', 'appoint ceo', 'interim ceo'
                ]):
                    ceo_changes += 1
                    recent_departures.append(f"CEO change mentioned in news ({date[:10]})")

            # Generate warning
            if cfo_changes >= 2:
                return {
                    'type': 'management_turnover',
                    'severity': 'Warning',
                    'message': 'High CFO turnover',
                    'details': f'{cfo_changes} CFO changes in recent news - often precedes accounting issues'
                }
            elif ceo_changes >= 1 and cfo_changes >= 1:
                return {
                    'type': 'management_turnover',
                    'severity': 'Warning',
                    'message': 'Multiple C-suite changes',
                    'details': f'CEO and CFO changes detected - management instability'
                }
            elif ceo_changes >= 1:
                return {
                    'type': 'management_turnover',
                    'severity': 'Caution',
                    'message': 'CEO change detected',
                    'details': 'New CEO may implement strategic changes - monitor execution'
                }
            elif cfo_changes >= 1:
                return {
                    'type': 'management_turnover',
                    'severity': 'Caution',
                    'message': 'CFO change detected',
                    'details': 'New CFO - watch for accounting policy changes'
                }

        except Exception as e:
            logger.warning(f"Error analyzing management turnover for {symbol}: {e}")

        return None

    def _analyze_geographic_exposure(self, symbol: str) -> Optional[Dict]:
        """
        Analyze geographic revenue exposure for geopolitical risk.

        High Risk: >30% revenue from high-risk regions (China, Russia, etc.)
        Medium Risk: 15-30% from high-risk regions
        Info: Significant international exposure
        """
        try:
            # FMP has revenue-geographic-segmentation endpoint for some companies
            # This is not always available, so gracefully handle

            # Note: FMP API client may not have this endpoint exposed
            # We'll try to infer from earnings transcript instead

            transcripts = self.fmp.get_earnings_call_transcript(symbol)
            if not transcripts:
                return None

            transcript = transcripts[0]
            content = transcript.get('content', '')
            if not content:
                return None

            content_lower = content.lower()

            # High-risk regions
            high_risk_regions = {
                'china': r'china\s+revenue|revenue\s+(?:from\s+)?china|chinese\s+market',
                'russia': r'russia\s+revenue|revenue\s+(?:from\s+)?russia|russian\s+market',
                'middle east': r'middle\s+east|mena\s+region'
            }

            exposures = {}
            for region, pattern in high_risk_regions.items():
                # Look for revenue percentage mentions
                region_pattern = pattern + r'.*?([\d.]+)%'
                matches = re.findall(region_pattern, content_lower)
                if matches:
                    try:
                        pct = float(matches[0])
                        if pct < 100:  # Sanity check
                            exposures[region] = pct
                    except:
                        pass

            # Generate warning based on highest exposure
            if exposures:
                max_region = max(exposures, key=exposures.get)
                max_exposure = exposures[max_region]

                if max_exposure > 30:
                    return {
                        'type': 'geographic_risk',
                        'severity': 'Warning',
                        'message': f'High {max_region.title()} exposure',
                        'details': f'{max_exposure:.0f}% revenue from {max_region.title()} - geopolitical risk'
                    }
                elif max_exposure > 15:
                    return {
                        'type': 'geographic_risk',
                        'severity': 'Caution',
                        'message': f'Moderate {max_region.title()} exposure',
                        'details': f'{max_exposure:.0f}% revenue from {max_region.title()} - monitor tensions'
                    }
                else:
                    return {
                        'type': 'geographic_risk',
                        'severity': 'Info',
                        'message': f'{max_region.title()} presence',
                        'details': f'{max_exposure:.0f}% revenue from {max_region.title()}'
                    }

            # Check for qualitative mentions of geographic concerns
            geo_risk_keywords = [
                'geopolitical risk',
                'trade tensions',
                'tariff impact',
                'export restrictions',
                'sanctions'
            ]

            if any(keyword in content_lower for keyword in geo_risk_keywords):
                return {
                    'type': 'geographic_risk',
                    'severity': 'Info',
                    'message': 'Geopolitical concerns mentioned',
                    'details': 'Management discussed geographic/trade risks in earnings call'
                }

        except Exception as e:
            logger.warning(f"Error analyzing geographic exposure for {symbol}: {e}")

        return None

    def _analyze_rd_efficiency(self, symbol: str, industry: str) -> Optional[Dict]:
        """
        Analyze R&D efficiency for Tech/Pharma companies.

        Métrica: Revenue per $1 R&D spent
        Compara con peers del sector

        Superior efficiency: >$8 revenue per $1 R&D (vs peers)
        Average: $4-8 revenue per $1 R&D
        Poor: <$4 revenue per $1 R&D
        """
        try:
            # Only applicable to R&D-intensive industries
            rd_intensive_keywords = [
                'software', 'technology', 'semiconductor', 'internet',
                'pharmaceutical', 'biotechnology', 'biotech', 'drug',
                'medical devices', 'aerospace', 'defense'
            ]

            industry_lower = industry.lower()
            is_rd_intensive = any(keyword in industry_lower for keyword in rd_intensive_keywords)

            if not is_rd_intensive:
                return None

            # Get financial data
            income = self.fmp.get_income_statement(symbol, period='annual', limit=3)
            if not income or len(income) < 3:
                return None

            # Calculate R&D efficiency for last 3 years
            rd_efficiencies = []

            for year_data in income[:3]:
                revenue = year_data.get('revenue', 0)
                rd_expenses = year_data.get('researchAndDevelopmentExpenses', 0)

                if rd_expenses > 0 and revenue > 0:
                    # Revenue per $1 R&D spent
                    efficiency = revenue / rd_expenses
                    rd_efficiencies.append(efficiency)

            if not rd_efficiencies:
                return None

            avg_efficiency = sum(rd_efficiencies) / len(rd_efficiencies)

            # Get R&D as % of revenue (for context)
            latest_revenue = income[0].get('revenue', 0)
            latest_rd = income[0].get('researchAndDevelopmentExpenses', 0)
            rd_pct_revenue = (latest_rd / latest_revenue * 100) if latest_revenue > 0 else 0

            # Industry benchmarks (rough estimates)
            # Software: ~$8-12 revenue per $1 R&D (high margin, scalable)
            # Pharma: ~$4-6 revenue per $1 R&D (lower margin, regulatory)
            # Semiconductor: ~$6-10 revenue per $1 R&D

            if 'software' in industry_lower or 'internet' in industry_lower:
                excellent_threshold = 10
                good_threshold = 6
                industry_type = 'Software/Internet'
            elif 'pharmaceutical' in industry_lower or 'biotech' in industry_lower or 'drug' in industry_lower:
                excellent_threshold = 6
                good_threshold = 4
                industry_type = 'Pharma/Biotech'
            elif 'semiconductor' in industry_lower:
                excellent_threshold = 8
                good_threshold = 5
                industry_type = 'Semiconductor'
            else:
                excellent_threshold = 7
                good_threshold = 4
                industry_type = 'Tech'

            # Generate assessment
            if avg_efficiency > excellent_threshold:
                return {
                    'type': 'rd_efficiency',
                    'severity': 'Info',
                    'message': f'Superior R&D efficiency',
                    'details': f'${avg_efficiency:.1f} revenue per $1 R&D (vs ~${excellent_threshold} {industry_type} avg) - efficient innovation'
                }
            elif avg_efficiency > good_threshold:
                return {
                    'type': 'rd_efficiency',
                    'severity': 'Info',
                    'message': f'Healthy R&D efficiency',
                    'details': f'${avg_efficiency:.1f} revenue per $1 R&D ({rd_pct_revenue:.1f}% of revenue) - solid innovation ROI'
                }
            else:
                return {
                    'type': 'rd_efficiency',
                    'severity': 'Caution',
                    'message': f'Low R&D efficiency',
                    'details': f'${avg_efficiency:.1f} revenue per $1 R&D (below ${good_threshold} {industry_type} benchmark) - R&D spending not translating to revenue'
                }

        except Exception as e:
            logger.warning(f"Error analyzing R&D efficiency for {symbol}: {e}")

        return None

    # ===================================
    # 7. Recent M&A
    # ===================================

    def _get_recent_mna(self, symbol: str) -> List[Dict]:
        """
        Get recent M&A deals (if available).

        Returns: List of deal dicts (max 3-5)
        """
        mna_list = []

        # Note: FMP may not have a direct M&A endpoint; placeholder
        # In production: use search-mergers-acquisitions or similar

        # Placeholder: return empty
        # Would extract: date, type, target, consideration, relative_size_%, note

        return mna_list

    # ===================================
    # 8. Top Risks (Synthesis)
    # ===================================

    def _synthesize_risks(
        self,
        symbol: str,
        transcript_tldr: Dict,
        news_tldr: List[str],
        news_tags: List[str]
    ) -> List[Dict]:
        """
        Synthesize top 3 risks from multiple sources.

        Returns: List of risk dicts:
        {
            'risk': str,
            'prob': 'Low|Med|High',
            'severity': 'Low|Med|High',
            'trigger': str
        }
        """
        risks = []

        # From transcript risks
        for risk_text in transcript_tldr.get('risks', [])[:2]:
            risks.append({
                'risk': risk_text[:100],
                'prob': 'Med',  # Heuristic
                'severity': 'Med',
                'trigger': 'Mentioned in latest earnings call'
            })

        # From news tags
        if 'litigation' in news_tags:
            risks.append({
                'risk': 'Legal litigation in progress',
                'prob': 'High',
                'severity': 'Med',
                'trigger': 'Recent news mentions lawsuit'
            })

        if 'regulatory' in news_tags:
            risks.append({
                'risk': 'Regulatory scrutiny or approval pending',
                'prob': 'Med',
                'severity': 'High',
                'trigger': 'Regulatory news in last 90 days'
            })

        if 'financing' in news_tags:
            risks.append({
                'risk': 'Equity or debt financing (potential dilution)',
                'prob': 'Med',
                'severity': 'Med',
                'trigger': 'Recent financing news'
            })

        # Limit to top 3
        return risks[:3]

    # ===================================
    # Formatting Functions (UI Compatibility)
    # ===================================

    def _format_moats(self, moats_raw: Dict) -> List[str]:
        """
        Convert raw moats dict to readable list.

        Example:
        {'switching_costs': 'Strong', 'network_effects': 'Probable', ...}
        -> ["💪 Switching Costs: High customer lock-in (Strong)", "✓ Network Effects: Platform grows... (Probable)"]
        """
        formatted = []

        moat_labels = {
            'switching_costs': 'Switching Costs',
            'network_effects': 'Network Effects',
            'brand_IP': 'Brand & Intellectual Property',
            'scale_efficiency': 'Scale & Cost Advantages',
            'regulatory_assets': 'Regulatory Barriers'
        }

        moat_descriptions = {
            'switching_costs': 'High customer switching costs lock in revenue',
            'network_effects': 'Platform grows stronger with each user',
            'brand_IP': 'Strong brand recognition or proprietary technology',
            'scale_efficiency': 'Economies of scale create cost advantages',
            'regulatory_assets': 'Licenses or regulations limit competition'
        }

        for key, value in moats_raw.items():
            if key in ['notes', 'confidence']:
                continue

            label = moat_labels.get(key, key)
            desc = moat_descriptions.get(key, '')

            if value == 'Strong':
                formatted.append(f"💪 **{label}**: {desc} (**Strong evidence**)")
            elif value == 'Probable':
                formatted.append(f"✓ {label}: {desc} (Probable)")
            else:
                formatted.append(f"✗ {label}: Not evident")

        # Add confidence and notes
        confidence = moats_raw.get('confidence', 'Low')
        notes = moats_raw.get('notes', '')

        if notes:
            formatted.append(f"")
            formatted.append(f"**Analysis Confidence:** {confidence}")
            formatted.append(f"📝 {notes}")

        return formatted if formatted else ["No clear moats identified"]

    def _format_news(self, news_tldr: List[str], news_tags: List[str]) -> List[Dict]:
        """
        Format news for UI display.

        Returns list of dicts with date, headline, summary, tags.
        """
        if not news_tldr:
            return []

        formatted_news = []
        today = datetime.now()

        for i, tldr in enumerate(news_tldr):
            # Extract approximate date (news are ordered newest first)
            days_ago = i * 15  # Rough estimate: 15 days apart
            news_date = (today - timedelta(days=days_ago)).strftime('%Y-%m-%d')

            # Split TLDR into headline and summary
            if ':' in tldr:
                headline, summary = tldr.split(':', 1)
            else:
                headline = tldr[:50]
                summary = tldr[50:] if len(tldr) > 50 else ''

            formatted_news.append({
                'date': news_date,
                'headline': headline.strip(),
                'summary': summary.strip()
            })

        return formatted_news

    def _format_risks(self, top_risks: List[Dict]) -> List[str]:
        """
        Format risks for simple UI display.

        Input: [{'risk': 'text', 'prob': 'Med', 'severity': 'High', ...}]
        Output: ["High Severity: Risk description", ...]
        """
        if not top_risks:
            return []

        formatted = []
        for risk_dict in top_risks:
            severity = risk_dict.get('severity', 'Med')
            risk_text = risk_dict.get('risk', '')

            # Emoji based on severity
            emoji = '🔴' if severity == 'High' else '🟡' if severity == 'Med' else '🟢'

            formatted.append(f"{emoji} {severity} Severity: {risk_text}")

        return formatted

    # ===================================
    # Intrinsic Value Estimation
    # ===================================

    def _get_industry_valuation_profile(self, symbol: str) -> Dict:
        """
        Determine optimal valuation metrics based on industry characteristics.

        Based on academic research (Damodaran, NYU Stern; Harbula, 2009):
        - Capital-intensive: EV/EBIT preferred (D&A reflects capex)
        - Asset-light/High-growth: EV/Revenue or EV/EBITDA
        - Asset-heavy: P/B (Book value)
        - Mature/Stable: FCF yield (predictable cash flows)

        Returns dict with:
        - primary_metric: str
        - secondary_metric: str
        - wacc: float
        - expected_multiple_range: tuple
        """
        try:
            profile_data = self.fmp.get_profile(symbol)
            if not profile_data:
                return self._default_valuation_profile()

            industry = profile_data[0].get('industry', '').lower()
            sector = profile_data[0].get('sector', '').lower()

            # Asset-light, high-growth industries (Software, Biotech, Internet)
            # Research: Damodaran 2025 - Software EV/EBITDA ~98x, Biotech ~62x
            if any(kw in industry + sector for kw in [
                'software', 'internet', 'biotechnology', 'pharmaceutical',
                'semiconductor', 'application', 'saas'
            ]):
                return {
                    'profile': 'high_growth_asset_light',
                    'primary_metric': 'EV/Revenue',  # For high growth with negative FCF
                    'secondary_metric': 'EV/EBITDA',
                    'wacc': 0.11,  # Higher risk
                    'expected_multiple_ebitda': (30, 60),  # Damodaran: 46-98x
                    'dcf_weight': 0.30,  # Lower weight (harder to project)
                    'multiple_weight': 0.70
                }

            # Capital-intensive industries (Manufacturing, Oil/Gas, Utilities, Telecom)
            # Research: EV/EBIT preferred - D&A reflects real capex needs
            elif any(kw in industry + sector for kw in [
                'oil', 'gas', 'energy', 'utility', 'utilities', 'telecom',
                'manufacturing', 'steel', 'mining', 'automotive', 'transportation',
                'airline', 'railroad', 'pipeline', 'midstream'
            ]):
                return {
                    'profile': 'capital_intensive',
                    'primary_metric': 'EV/EBIT',  # Better than EBITDA for capex-heavy
                    'secondary_metric': 'EV/FCF',
                    'wacc': 0.09,  # Lower for utilities, 0.10 for others
                    'expected_multiple_ebit': (8, 12),  # Typical range
                    'dcf_weight': 0.45,  # Higher weight (stable cash flows)
                    'multiple_weight': 0.55
                }

            # Asset Managers / Private Equity (fee-based, AUM-driven)
            # Research: P/E multiple appropriate, NOT P/B (asset-light)
            # Calibrated with Blackstone (~18x), KKR (~17x), Brookfield (~16x), Partners Group (~20x)
            elif any(kw in industry + sector for kw in [
                'asset management', 'wealth management', 'investment management',
                'private equity', 'hedge fund', 'alternative investments',
                'asset manager', 'investment advisor', 'fund management'
            ]):
                return {
                    'profile': 'asset_manager',
                    'primary_metric': 'P/E',
                    'secondary_metric': 'Price/AUM',
                    'wacc': 0.09,  # Lower than banks (asset-light, stable management fees)
                    'expected_multiple_pe': (15, 20),  # Quality AM range
                    'dcf_weight': 0.50,  # Equal weight: DCF + P/E blend (user requested)
                    'multiple_weight': 0.50
                }

            # Asset-based industries (Real Estate, Banks, Insurance)
            # Research: P/B well-suited for tangible assets
            elif any(kw in industry + sector for kw in [
                'real estate', 'reit', 'bank', 'insurance', 'financial', 'credit services'
            ]):
                return {
                    'profile': 'asset_based',
                    'primary_metric': 'P/B',
                    'secondary_metric': 'P/FFO' if 'reit' in industry else 'P/TBV',
                    'wacc': 0.12 if 'bank' in industry else 0.09,  # REITs lower
                    'expected_multiple_pb': (1.0, 1.5),  # Conservative
                    'dcf_weight': 0.40,
                    'multiple_weight': 0.60
                }

            # Mature, stable industries (Consumer Staples, Healthcare Products)
            # Research: FCF yield reliable for predictable cash flows
            elif any(kw in industry + sector for kw in [
                'consumer staples', 'consumer defensive', 'beverage', 'food',
                'tobacco', 'household products', 'medical devices', 'healthcare products'
            ]):
                return {
                    'profile': 'mature_stable',
                    'primary_metric': 'FCF_Yield',
                    'secondary_metric': 'EV/EBIT',
                    'wacc': 0.08,  # Lower risk
                    'expected_multiple_ebit': (12, 18),  # Higher for quality
                    'dcf_weight': 0.50,  # Highest weight (very predictable)
                    'multiple_weight': 0.50
                }

            # Cyclical industries (Retail, Consumer Cyclical)
            # Research: Use normalized earnings, avoid peak/trough
            elif any(kw in industry + sector for kw in [
                'retail', 'consumer cyclical', 'restaurant', 'hotel',
                'leisure', 'apparel', 'automotive retail'
            ]):
                return {
                    'profile': 'cyclical',
                    'primary_metric': 'EV/EBITDA',  # More stable than EBIT
                    'secondary_metric': 'EV/Revenue',
                    'wacc': 0.10,
                    'expected_multiple_ebitda': (8, 14),
                    'dcf_weight': 0.35,  # Lower weight (hard to normalize)
                    'multiple_weight': 0.65
                }

            # Default: Diversified/Mixed
            else:
                return self._default_valuation_profile()

        except Exception as e:
            logger.warning(f"Failed to determine industry profile for {symbol}: {e}")
            return self._default_valuation_profile()

    def _default_valuation_profile(self) -> Dict:
        """Default valuation profile for mixed/unknown industries."""
        return {
            'profile': 'default',
            'primary_metric': 'EV/EBIT',
            'secondary_metric': 'FCF_Yield',
            'wacc': 0.10,
            'expected_multiple_ebit': (10, 15),
            'dcf_weight': 0.40,
            'multiple_weight': 0.60
        }

    def _detect_company_type(self, symbol: str) -> str:
        """
        Automatically detect company type from profile data.

        Returns: 'non_financial', 'financial', 'reit', or 'utility'
        """
        try:
            profile = self.fmp.get_profile(symbol)
            if not profile or len(profile) == 0:
                return 'non_financial'  # Default

            sector = (profile[0].get('sector', '')).lower()
            industry = (profile[0].get('industry', '')).lower()

            # REITs
            if 'reit' in industry or 'real estate investment trust' in industry:
                return 'reit'

            # Asset Managers & Private Equity (specialized financial sub-type)
            # These are fee-based businesses driven by AUM, not balance sheet leverage
            # Examples: Blackstone, KKR, Brookfield, Partners Group, Apollo, Carlyle
            asset_manager_keywords = [
                'asset management', 'wealth management', 'investment management',
                'private equity', 'hedge fund', 'alternative investments',
                'asset manager', 'investment advisor', 'fund management'
            ]

            if any(kw in industry for kw in asset_manager_keywords):
                return 'asset_manager'

            # Financials (banks, insurance, other financial services)
            if sector == 'financial services' or sector == 'financial':
                return 'financial'

            if any(kw in industry for kw in ['bank', 'insurance', 'capital markets', 'credit services']):
                return 'financial'

            # Utilities
            if sector == 'utilities' or 'utility' in industry or 'utilities' in industry:
                return 'utility'

            # Default to non_financial
            return 'non_financial'

        except Exception as e:
            logger.warning(f"Failed to detect company type for {symbol}: {e}")
            return 'non_financial'

    def _estimate_intrinsic_value(
        self,
        symbol: str,
        company_type: str,
        peers_df: Optional[Any],
        peers_list: Optional[List[str]] = None
    ) -> Dict:
        """
        Estimate intrinsic value using multiple approaches:
        1. DCF (simple 2-stage model)
        2. Forward multiples vs peers
        3. Historical average multiple

        Returns:
        {
            'current_price': float,
            'dcf_value': float,
            'forward_multiple_value': float,
            'historical_multiple_value': float,
            'weighted_value': float,
            'upside_downside_%': float,
            'valuation_assessment': 'Undervalued|Fair|Overvalued',
            'confidence': 'Low|Med|High'
        }
        """
        # Initialize valuation dict FIRST (before we try to use it)
        valuation = {
            'current_price': None,
            'dcf_value': None,
            'forward_multiple_value': None,
            'historical_multiple_value': None,
            'weighted_value': None,
            'upside_downside_%': None,
            'valuation_assessment': 'Unknown',
            'confidence': 'Low',
            'industry_profile': 'unknown',
            'primary_metric': 'EV/EBIT',
            'price_projections': {},  # Scenarios with different growth rates
            'notes': []
        }

        # Auto-detect company type if unknown or invalid
        valid_types = ['non_financial', 'financial', 'reit', 'utility']
        original_type = company_type
        if company_type not in valid_types:
            logger.info(f"Company type '{company_type}' not recognized for {symbol}, auto-detecting...")
            company_type = self._detect_company_type(symbol)
            logger.info(f"Auto-detected company type for {symbol}: {company_type}")
            valuation['notes'].append(f"ℹ️ Auto-detected type: {company_type} (original: {original_type})")

        # Get industry-specific valuation profile
        industry_profile = self._get_industry_valuation_profile(symbol)

        # Update valuation dict with industry profile info
        valuation['industry_profile'] = industry_profile.get('profile', 'unknown')
        valuation['primary_metric'] = industry_profile.get('primary_metric', 'EV/EBIT')

        try:
            # Get current price from profile endpoint
            current_price = 0

            try:
                profile = self.fmp.get_profile(symbol)

                if profile and len(profile) > 0:
                    prof_data = profile[0]

                    # Try multiple possible price fields
                    current_price = (prof_data.get('price') or
                                   prof_data.get('lastPrice') or
                                   prof_data.get('regularMarketPrice') or
                                   0)

                    logger.debug(f"Price for {symbol}: {current_price} from profile")
                else:
                    logger.warning(f"Profile returned empty for {symbol}")
            except Exception as e:
                logger.error(f"Failed to get price from profile for {symbol}: {e}")
                valuation['notes'].append(f"Price retrieval error: {str(e)[:50]}")

            # Always set current_price (even if 0) so UI displays the section
            valuation['current_price'] = current_price if current_price and current_price > 0 else 0

            if not current_price or current_price <= 0:
                valuation['notes'].append(f"⚠️ Current price unavailable - showing intrinsic values only (no upside/downside calculation)")
                logger.warning(f"Could not get price for {symbol} - proceeding with intrinsic calculations")
                valuation['confidence'] = 'Low'

            # Use industry-specific WACC
            industry_wacc = industry_profile.get('wacc', 0.10)

            # 1. DCF Valuation (with industry-specific WACC)
            logger.info(f"Calculating DCF for {symbol}, type={company_type}, wacc={industry_wacc}")
            try:
                dcf_value = self._calculate_dcf(symbol, company_type, wacc_override=industry_wacc, notes_list=valuation['notes'])
                if dcf_value and dcf_value > 0:
                    valuation['dcf_value'] = dcf_value
                    valuation['confidence'] = 'Med'
                    valuation['notes'].append(f"✓ DCF: ${dcf_value:.2f} (WACC: {industry_wacc:.1%})")
                    logger.info(f"✓ DCF for {symbol}: ${dcf_value:.2f}")
                # Note: error messages already added by _calculate_dcf via notes_list
            except Exception as e:
                valuation['notes'].append(f"✗ DCF EXCEPTION: {str(e)[:100]}")
                logger.error(f"DCF calculation error for {symbol}: {e}", exc_info=True)

            # 2. Forward Multiple Valuation
            logger.info(f"Calculating Forward Multiple for {symbol}, type={company_type}")
            try:
                forward_value = self._calculate_forward_multiple(symbol, company_type, peers_df, notes_list=valuation['notes'])
                if forward_value and forward_value > 0:
                    valuation['forward_multiple_value'] = forward_value
                    valuation['confidence'] = 'High' if valuation['confidence'] == 'Med' else 'Med'
                    valuation['notes'].append(f"✓ Forward Multiple: ${forward_value:.2f}")
                    logger.info(f"✓ Forward Multiple for {symbol}: ${forward_value:.2f}")
                # Note: error messages already added by _calculate_forward_multiple via notes_list
            except Exception as e:
                valuation['notes'].append(f"✗ Forward Multiple EXCEPTION: {str(e)[:100]}")
                logger.error(f"Forward Multiple error for {symbol}: {e}", exc_info=True)

            # 3. Historical Multiple
            historical_value = self._calculate_historical_multiple(symbol, company_type)
            if historical_value and historical_value > 0:
                valuation['historical_multiple_value'] = historical_value
                valuation['notes'].append(f"✓ Historical Multiple: ${historical_value:.2f}")
            else:
                logger.debug(f"Historical multiple for {symbol} returned None or zero")

            # Weighted average using INDUSTRY-SPECIFIC WEIGHTS
            estimates = []
            weights = []
            values = []

            # DCF weight (varies by industry: 0.30 for high-growth, 0.50 for stable)
            if dcf_value and dcf_value > 0:
                estimates.append('DCF')
                dcf_weight = industry_profile.get('dcf_weight', 0.40)
                weights.append(dcf_weight)
                values.append(dcf_value)

            # Multiple weight (varies by industry)
            if forward_value and forward_value > 0:
                estimates.append('Forward Multiple')
                multiple_weight = industry_profile.get('multiple_weight', 0.60)
                # Split between forward and historical
                weights.append(multiple_weight * 0.70)  # 70% to forward
                values.append(forward_value)

            if historical_value and historical_value > 0:
                estimates.append('Historical')
                multiple_weight = industry_profile.get('multiple_weight', 0.60)
                weights.append(multiple_weight * 0.30)  # 30% to historical
                values.append(historical_value)

            if values:
                # Normalize weights to sum to 1.0
                total_weight = sum(weights)
                weights = [w / total_weight for w in weights]

                weighted = sum(v * w for v, w in zip(values, weights))
                valuation['weighted_value'] = weighted

                # Calculate upside/downside ONLY if we have a valid current price
                if current_price and current_price > 0:
                    upside = ((weighted - current_price) / current_price) * 100
                    valuation['upside_downside_%'] = upside

                    # Assessment (industry-adjusted thresholds)
                    # High-growth industries get more lenient thresholds
                    if industry_profile.get('profile') == 'high_growth_asset_light':
                        undervalued_threshold = 30
                        overvalued_threshold = -20
                    else:
                        undervalued_threshold = 25
                        overvalued_threshold = -15

                    if upside > undervalued_threshold:
                        valuation['valuation_assessment'] = 'Undervalued'
                    elif upside < overvalued_threshold:
                        valuation['valuation_assessment'] = 'Overvalued'
                    else:
                        valuation['valuation_assessment'] = 'Fair Value'

                    # === PRICE PROJECTIONS ===
                    # Calculate price targets with different growth assumptions
                    valuation['price_projections'] = self._calculate_price_projections(
                        symbol,
                        current_price,
                        dcf_value,
                        forward_value,
                        company_type,
                        industry_wacc
                    )
                else:
                    valuation['notes'].append("Upside/downside not calculated (no current price)")
                    valuation['valuation_assessment'] = 'Unknown'

                # === ADVANCED QUALITATIVE METRICS ===

                # 1. ROIC vs WACC (Capital Efficiency) - or ROE for financials
                roic_analysis = self._calculate_roic_vs_wacc(symbol, industry_wacc, company_type)
                if roic_analysis:
                    valuation['capital_efficiency'] = roic_analysis

                # 2. Margins and Trends
                margins_analysis = self._calculate_margins_and_trends(symbol, peers_df)
                if margins_analysis:
                    valuation['profitability_analysis'] = margins_analysis

                # 3. Red Flags
                red_flags = self._detect_red_flags(symbol)
                if red_flags:
                    valuation['red_flags'] = red_flags
                else:
                    valuation['red_flags'] = []  # No red flags is good!

                # 4. Reverse DCF (only if we have current price)
                if current_price and current_price > 0:
                    reverse_dcf = self._calculate_reverse_dcf(symbol, current_price, industry_wacc)
                    if reverse_dcf:
                        valuation['reverse_dcf'] = reverse_dcf

                # 5. Quality of Earnings
                earnings_quality = self._calculate_earnings_quality(symbol)
                if earnings_quality:
                    valuation['earnings_quality'] = earnings_quality

                # 6. DCF Sensitivity Analysis
                if dcf_value and dcf_value > 0:
                    dcf_sensitivity = self._calculate_dcf_sensitivity(
                        symbol,
                        company_type,
                        dcf_value,
                        industry_wacc
                    )
                    if dcf_sensitivity:
                        valuation['dcf_sensitivity'] = dcf_sensitivity

                # 7. Balance Sheet Strength
                balance_sheet = self._calculate_balance_sheet_strength(symbol)
                if balance_sheet:
                    valuation['balance_sheet_strength'] = balance_sheet

                # 8. Valuation Multiples vs Peers
                multiples = self._calculate_valuation_multiples(symbol, peers_list)
                if multiples:
                    valuation['valuation_multiples'] = multiples

                # 9. Growth Consistency
                growth_consistency = self._calculate_growth_consistency(symbol)
                if growth_consistency:
                    valuation['growth_consistency'] = growth_consistency

                # 10. Cash Conversion Cycle (FASE 1)
                cash_cycle = self._calculate_cash_conversion_cycle(symbol)
                if cash_cycle:
                    valuation['cash_conversion_cycle'] = cash_cycle

                # 11. Operating Leverage (FASE 1)
                operating_lev = self._calculate_operating_leverage(symbol)
                if operating_lev:
                    valuation['operating_leverage'] = operating_lev

                # 12. Reinvestment Quality (FASE 1)
                reinvestment = self._calculate_reinvestment_quality(symbol)
                if reinvestment:
                    valuation['reinvestment_quality'] = reinvestment

                # 13. Economic Profit / EVA (FASE 2)
                eva = self._calculate_economic_profit(symbol)
                if eva:
                    valuation['economic_profit'] = eva

                # 14. Capital Allocation Score (FASE 2)
                cap_alloc = self._calculate_capital_allocation_score(symbol)
                if cap_alloc:
                    valuation['capital_allocation'] = cap_alloc

                # 15. Interest Rate Sensitivity (FASE 2)
                rate_sensitivity = self._calculate_interest_rate_sensitivity(symbol, company_type)
                if rate_sensitivity:
                    valuation['interest_rate_sensitivity'] = rate_sensitivity

                # 16. Insider Trading Analysis (Premium Feature)
                premium_config = self.config.get('premium', {})
                logger.info(f"🔍 Premium config for {symbol}: {premium_config}")

                if premium_config.get('enable_insider_trading', False):
                    logger.info(f"✓ Insider Trading is ENABLED, calling _analyze_insider_trading({symbol})...")
                    insider_analysis = self._analyze_insider_trading(symbol)
                    logger.info(f"✓ Insider Trading result: available={insider_analysis.get('available', False) if insider_analysis else False}")
                    if insider_analysis:
                        valuation['insider_trading'] = insider_analysis
                        logger.info(f"✓ Insider Trading added to valuation dict")
                else:
                    logger.warning(f"❌ Insider Trading is DISABLED in config")

                # 17. Earnings Call Sentiment (Premium Feature)
                if premium_config.get('enable_earnings_transcripts', False):
                    logger.info(f"✓ Earnings Transcripts is ENABLED, calling _analyze_earnings_sentiment({symbol})...")
                    earnings_sentiment = self._analyze_earnings_sentiment(symbol)
                    logger.info(f"✓ Earnings Sentiment result: available={earnings_sentiment.get('available', False) if earnings_sentiment else False}")
                    if earnings_sentiment:
                        valuation['earnings_sentiment'] = earnings_sentiment
                        logger.info(f"✓ Earnings Sentiment added to valuation dict")
                else:
                    logger.warning(f"❌ Earnings Transcripts is DISABLED in config")

                # Add detailed notes
                profile_name = industry_profile.get('profile', 'unknown').replace('_', ' ').title()
                primary_metric = industry_profile.get('primary_metric', 'EV/EBIT')
                valuation['notes'].append(f"Industry: {profile_name}")
                valuation['notes'].append(f"Primary metric: {primary_metric}")
                valuation['notes'].append(f"Methods: {', '.join(estimates)}")
                valuation['notes'].append(f"WACC: {industry_wacc:.1%}")
            else:
                valuation['notes'].append("Insufficient data for valuation")

        except Exception as e:
            logger.warning(f"Failed to estimate intrinsic value for {symbol}: {e}")
            valuation['notes'].append(f"Error: {str(e)}")

        return valuation

    def _calculate_dcf(self, symbol: str, company_type: str, wacc_override: Optional[float] = None, notes_list: Optional[list] = None) -> Optional[float]:
        """
        Company-specific DCF valuation.

        Non-financial: FCF-based (adjusted for growth capex)
        Financial: Earnings-based
        REIT: FFO-based

        Key: Don't penalize growth capex - it's valuable investment

        Args:
            symbol: Stock ticker
            company_type: 'non_financial', 'financial', or 'reit'
            wacc_override: Optional industry-specific WACC (from research)
            notes_list: Optional list to append diagnostic notes to
        """
        def add_note(msg):
            if notes_list is not None:
                notes_list.append(msg)

        try:
            # Get financials
            logger.info(f"DCF: Fetching financials for {symbol}")
            income = self.fmp.get_income_statement(symbol, period='annual', limit=2)
            balance = self.fmp.get_balance_sheet(symbol, period='annual', limit=1)
            cashflow = self.fmp.get_cash_flow(symbol, period='annual', limit=2)

            logger.info(f"DCF: Got income={len(income) if income else 0} statements, balance={len(balance) if balance else 0}, cashflow={len(cashflow) if cashflow else 0}")

            if not (income and balance and cashflow):
                msg = f"DCF: Missing financials - income:{bool(income)}, balance:{bool(balance)}, cashflow:{bool(cashflow)}"
                logger.warning(f"{symbol} {msg}")
                add_note(f"✗ {msg}")
                return None

            # Get shares outstanding (keep in actual count, not millions)
            # CRITICAL: weightedAverageShsOut might not be in annual balance sheets
            # Try multiple sources

            # Debug: Log all available fields in balance sheet
            logger.info(f"DCF: {symbol} balance sheet keys: {list(balance[0].keys())}")

            shares = (balance[0].get('weightedAverageShsOut') or
                     balance[0].get('commonStockSharesOutstanding') or
                     balance[0].get('weightedAverageShsOutDil'))

            logger.info(f"DCF: {symbol} shares from balance sheet: {shares}")
            add_note(f"ℹ️ Balance sheet shares attempts: weightedAverageShsOut={balance[0].get('weightedAverageShsOut')}, commonStockSharesOutstanding={balance[0].get('commonStockSharesOutstanding')}, weightedAverageShsOutDil={balance[0].get('weightedAverageShsOutDil')}")

            if not shares or shares <= 0:
                # Last resort: get from profile
                logger.info(f"DCF: {symbol} shares not in balance sheet, trying profile")
                profile = self.fmp.get_profile(symbol)
                if profile and len(profile) > 0:
                    logger.info(f"DCF: {symbol} profile keys: {list(profile[0].keys())}")
                    shares = profile[0].get('sharesOutstanding', 0)
                    logger.info(f"DCF: {symbol} shares from profile: {shares}")
                    add_note(f"ℹ️ Profile sharesOutstanding: {shares}")

                    # If still no shares, try calculating from mktCap / price
                    if not shares or shares <= 0:
                        mkt_cap = profile[0].get('mktCap')
                        price = profile[0].get('price')
                        if mkt_cap and price and price > 0:
                            shares = int(mkt_cap / price)
                            logger.info(f"DCF: {symbol} calculated shares from mktCap/price: {shares:,}")
                            add_note(f"💡 Calculated shares from mktCap ({mkt_cap:,}) / price ({price}): {shares:,}")

            if not shares or shares <= 0:
                msg = f"DCF: Could not get shares outstanding (got {shares})"
                logger.warning(f"{symbol} {msg}")
                add_note(f"✗ {msg}")
                add_note(f"ℹ️ Available balance sheet fields: {', '.join(list(balance[0].keys())[:20])}")
                return None

            # === Type-specific base cash flow ===

            if company_type == 'non_financial':
                # Use Operating Cash Flow - Maintenance Capex
                # Don't subtract growth capex!

                ocf = cashflow[0].get('operatingCashFlow', 0)
                capex = abs(cashflow[0].get('capitalExpenditure', 0))
                revenue = income[0].get('revenue', 1)
                revenue_prev = income[1].get('revenue', 1) if len(income) > 1 else revenue

                logger.info(f"DCF: {symbol} OCF={ocf:,.0f}, capex={capex:,.0f}, revenue={revenue:,.0f}, revenue_prev={revenue_prev:,.0f}")

                # Estimate maintenance capex (historical average or 2-3% of revenue)
                # If revenue growing fast, assume more capex is growth
                revenue_growth = (revenue - revenue_prev) / revenue_prev if revenue_prev > 0 else 0

                if revenue_growth > 0.10:  # Growing > 10%
                    # High growth: assume 50% of capex is maintenance, 50% is growth
                    maintenance_capex = capex * 0.5
                elif revenue_growth > 0.05:  # Moderate growth
                    # Moderate: 70% maintenance
                    maintenance_capex = capex * 0.7
                else:
                    # Mature: 90% maintenance
                    maintenance_capex = capex * 0.9

                logger.info(f"DCF: {symbol} revenue_growth={revenue_growth:.2%}, maintenance_capex={maintenance_capex:,.0f} ({maintenance_capex/capex:.0%} of total)")

                # Normalized FCF = OCF - Maintenance Capex only
                base_cf = ocf - maintenance_capex

            elif company_type == 'reit':
                # Use FFO (Funds From Operations)
                # FFO = Net Income + Depreciation - Gains on Sales

                net_income = income[0].get('netIncome', 0)
                depreciation = abs(cashflow[0].get('depreciationAndAmortization', 0))

                # Simplified FFO
                ffo = net_income + depreciation

                # Maintenance capex for REITs (typically lower, ~15-20% of FFO)
                capex = abs(cashflow[0].get('capitalExpenditure', 0))
                maintenance_capex = min(capex, ffo * 0.20)

                base_cf = ffo - maintenance_capex  # AFFO

            elif company_type == 'utility':
                # Utilities: Use OCF - Maintenance Capex
                # Similar to non_financial but with different maintenance % assumptions

                ocf = cashflow[0].get('operatingCashFlow', 0)
                capex = abs(cashflow[0].get('capitalExpenditure', 0))

                # Utilities: Typically mature with steady capex
                # Assume 80% maintenance, 20% growth
                maintenance_capex = capex * 0.80

                base_cf = ocf - maintenance_capex

            elif company_type == 'asset_manager':
                # Asset Managers / Private Equity: Fee-based businesses
                # Use NORMALIZED earnings (ex extraordinary performance fees)

                net_income = income[0].get('netIncome', 0)

                # Attempt to normalize: remove extraordinary performance fees
                # Performance fees are typically volatile and non-recurring
                # Heuristic: If current year earnings >40% above prior year, likely includes big performance fee
                if len(income) > 1:
                    net_income_prev = income[1].get('netIncome', 1)
                    if net_income_prev > 0:
                        earnings_growth = (net_income - net_income_prev) / net_income_prev

                        if earnings_growth > 0.40:
                            # Likely extraordinary performance fee - use average of last 2 years
                            normalized_earnings = (net_income + net_income_prev) / 2
                            logger.info(f"DCF Asset Manager: {symbol} normalizing earnings ({earnings_growth:.1%} growth) - using 2Y avg: ${normalized_earnings:,.0f}")
                            add_note(f"💡 Normalized earnings (2Y avg) to remove performance fee volatility")
                            base_cf = normalized_earnings
                        else:
                            # Normal earnings
                            base_cf = net_income
                    else:
                        base_cf = net_income
                else:
                    base_cf = net_income

            else:  # Financial or unknown (treat unknown as non_financial)
                if company_type in ['financial', 'bank', 'insurance']:
                    # Use earnings (net income) for financials
                    base_cf = income[0].get('netIncome', 0)
                else:
                    # Unknown type: treat as non_financial (use FCF approach)
                    logger.warning(f"Unknown company_type '{company_type}' for {symbol}, treating as non_financial")
                    add_note(f"⚠️ Company type '{company_type}' unknown, using non-financial FCF approach")

                    ocf = cashflow[0].get('operatingCashFlow', 0)
                    capex = abs(cashflow[0].get('capitalExpenditure', 0))

                    # Use 70% maintenance capex as default
                    maintenance_capex = capex * 0.7
                    base_cf = ocf - maintenance_capex

            logger.info(f"DCF: {symbol} calculated base_cf={base_cf:,.0f} for {company_type}")

            if base_cf <= 0:
                msg = f"DCF: Base cash flow <= 0 (got {base_cf:,.0f}). Company may have negative FCF or losses."
                logger.warning(f"{symbol} {msg}")
                add_note(f"✗ {msg}")
                return None

            # === Growth assumptions ===

            # Estimate growth from recent history
            if len(income) > 1 and len(cashflow) > 1:
                revenue_growth = (income[0].get('revenue', 0) - income[1].get('revenue', 1)) / income[1].get('revenue', 1)
                revenue_growth = max(0, min(revenue_growth, 0.30))  # Cap at 30%
            else:
                revenue_growth = 0.08  # Default 8%

            # Asset Manager specific: More conservative growth assumptions
            # Growth driven by AUM, not revenue multiples
            if company_type == 'asset_manager':
                # Realistic AUM growth: 8-12% annually (industry average)
                # Cap stage 1 growth at 12% (optimistic but realistic for quality AMs)
                growth_stage1 = min(revenue_growth, 0.12)
                if growth_stage1 < 0.08:
                    growth_stage1 = 0.08  # Minimum 8% for quality AMs
                terminal_growth = 0.05  # Slightly higher terminal (AUM compounds)
                logger.info(f"DCF Asset Manager: {symbol} using AUM-linked growth - Stage1: {growth_stage1:.1%}, Terminal: {terminal_growth:.1%}")
                add_note(f"💡 Growth linked to realistic AUM expansion ({growth_stage1:.0%} / {terminal_growth:.0%})")
            else:
                # Standard growth assumptions for other company types
                # Stage 1 growth (5 years): taper from current to 10%
                growth_stage1 = (revenue_growth + 0.10) / 2  # Average of current and 10%
                # Stage 2 (terminal): 3% perpetual
                terminal_growth = 0.03

            # === WACC DINÁMICO (ajuste por Net Cash Position) ===

            # Calculate net debt FIRST to adjust WACC
            # CRITICAL: Include Short Term Investments (Google, Apple, Microsoft have $100B+)
            total_debt = balance[0].get('totalDebt', 0)
            cash = balance[0].get('cashAndCashEquivalents', 0)
            short_term_investments = balance[0].get('shortTermInvestments', 0)
            total_liquid_assets = cash + short_term_investments
            net_debt = total_debt - total_liquid_assets

            logger.info(f"DCF: {symbol} debt={total_debt:,.0f}, cash={cash:,.0f}, ST_investments={short_term_investments:,.0f}, net_debt={net_debt:,.0f}")

            if wacc_override:
                wacc = wacc_override
            elif company_type == 'asset_manager':
                wacc = 0.09  # Lower than banks (asset-light, predictable fees)
                # Asset managers have stable fee streams, lower leverage than banks
            elif company_type == 'financial':
                wacc = 0.12  # Higher for financials (leverage risk)
            elif company_type == 'reit':
                wacc = 0.09  # Lower for REITs (stable cash flows)
            elif company_type == 'utility':
                wacc = 0.08  # Lowest for utilities (regulated, stable, low risk)
            else:
                # STANDARD WACC - pero ajustado por calidad de balance
                wacc = 0.10  # Base standard

            # === CRITICAL ADJUSTMENT: Net Cash Bonus ===
            # Empresas con caja neta (Net Debt < 0) son MENOS riesgosas
            # Ejemplos: Apple, Google, Microsoft con $100B+ en caja neta
            # Merecen WACC más bajo (8.5% vs 10-12%)
            if net_debt < 0 and company_type not in ['financial', 'reit', 'utility']:
                # Net cash position (más cash que deuda)
                original_wacc = wacc
                wacc = 0.085  # 8.5% para empresas Quality con caja neta
                logger.info(f"DCF WACC Adjustment: {symbol} has NET CASH (debt={total_debt:,.0f}, cash={cash:,.0f}, net={net_debt:,.0f}). WACC: {original_wacc:.1%} → {wacc:.1%}")
                add_note(f"💰 Net Cash Position detected (${abs(net_debt):,.0f}M) - WACC reduced to {wacc:.1%} (reflects lower risk)")
            else:
                logger.info(f"DCF WACC: {symbol} using {wacc:.1%} (net_debt={net_debt:,.0f})")

            # === DCF calculation ===

            # Project 5 years
            fcf_pv = 0
            for year in range(1, 6):
                fcf_projected = base_cf * ((1 + growth_stage1) ** year)
                pv = fcf_projected / ((1 + wacc) ** year)
                fcf_pv += pv

            # Terminal value
            fcf_year5 = base_cf * ((1 + growth_stage1) ** 5)
            terminal_fcf = fcf_year5 * (1 + terminal_growth)
            terminal_value = terminal_fcf / (wacc - terminal_growth)
            terminal_pv = terminal_value / ((1 + wacc) ** 5)

            # Enterprise value
            ev = fcf_pv + terminal_pv

            # Convert to equity value (using net_debt calculated earlier for WACC)
            equity_value = ev - net_debt

            # Per share
            value_per_share = equity_value / shares

            logger.info(f"DCF: {symbol} ev={ev:,.0f}, net_debt={net_debt:,.0f}, equity_value={equity_value:,.0f}, shares={shares:,.0f}, value_per_share=${value_per_share:.2f}")

            result = value_per_share if value_per_share > 0 else None
            if result:
                logger.info(f"DCF: ✓ Final result for {symbol}: ${result:.2f}")
            else:
                logger.warning(f"DCF: ✗ Final result for {symbol} is None or negative (value_per_share={value_per_share})")
            return result

        except Exception as e:
            msg = f"DCF: Exception during calculation - {str(e)[:150]}"
            logger.error(f"{symbol} {msg}", exc_info=True)
            add_note(f"✗ {msg}")
            return None

    def _calculate_forward_multiple(
        self,
        symbol: str,
        company_type: str,
        peers_df: Optional[Any],
        notes_list: Optional[list] = None
    ) -> Optional[float]:
        """
        Value using forward multiples vs peers.

        For non-financial: Prefer EV/EBIT (more robust than P/E)
        For financial: Use P/E
        For REIT: Use P/FFO

        Args:
            notes_list: Optional list to append diagnostic notes to
        """
        def add_note(msg):
            if notes_list is not None:
                notes_list.append(msg)

        try:
            logger.debug(f"Forward Multiple: Fetching financials for {symbol}")
            income = self.fmp.get_income_statement(symbol, period='annual', limit=2)
            balance = self.fmp.get_balance_sheet(symbol, period='annual', limit=1)
            cashflow = self.fmp.get_cash_flow(symbol, period='annual', limit=1)

            logger.debug(f"Forward Multiple: Got income={bool(income)}, balance={bool(balance)}, cashflow={bool(cashflow)}")

            if not (income and balance):
                msg = f"Forward Multiple: Missing financials - income:{bool(income)}, balance:{bool(balance)}"
                logger.warning(f"{symbol} {msg}")
                add_note(f"✗ {msg}")
                return None

            # Get shares outstanding (keep in actual count, not millions)
            shares = (balance[0].get('weightedAverageShsOut') or
                     balance[0].get('commonStockSharesOutstanding') or
                     balance[0].get('weightedAverageShsOutDil'))

            logger.info(f"Forward Multiple: {symbol} shares from balance sheet: {shares}")

            if not shares or shares <= 0:
                # Fallback to profile
                logger.info(f"Forward Multiple: {symbol} shares not in balance sheet, trying profile")
                profile = self.fmp.get_profile(symbol)
                if profile and len(profile) > 0:
                    shares = profile[0].get('sharesOutstanding', 0)
                    logger.info(f"Forward Multiple: {symbol} shares from profile: {shares}")

                    # If still no shares, try calculating from mktCap / price
                    if not shares or shares <= 0:
                        mkt_cap = profile[0].get('mktCap')
                        price = profile[0].get('price')
                        if mkt_cap and price and price > 0:
                            shares = int(mkt_cap / price)
                            logger.info(f"Forward Multiple: {symbol} calculated shares from mktCap/price: {shares:,}")
                            add_note(f"💡 Calculated shares from mktCap ({mkt_cap:,}) / price ({price}): {shares:,}")

            if not shares or shares <= 0:
                msg = f"Forward Multiple: Could not get shares outstanding (got {shares})"
                logger.warning(f"{symbol} {msg}")
                add_note(f"✗ {msg}")
                return None

            # === Get peer multiples ===

            peer_multiple = None
            metric_name = ''

            if company_type == 'non_financial':
                # Use EV/EBIT (better for capital-intensive businesses)

                # Get EBIT: Try multiple approaches
                # Approach 1: Calculate from EBITDA - D&A
                ebitda = income[0].get('ebitda') or income[0].get('EBITDA')

                # D&A might be in cash flow or income statement
                da = None
                if cashflow and len(cashflow) > 0:
                    da = abs(cashflow[0].get('depreciationAndAmortization', 0))
                if not da or da == 0:
                    # Try income statement
                    da = abs(income[0].get('depreciationAndAmortization', 0))

                if ebitda and ebitda > 0 and da and da > 0:
                    ebit_ttm = ebitda - da
                else:
                    # Approach 2: Use operatingIncome directly (this IS EBIT)
                    ebit_ttm = income[0].get('operatingIncome') or income[0].get('ebit') or 0

                logger.debug(f"Forward Multiple: {symbol} ebitda={ebitda}, da={da}, ebit_ttm={ebit_ttm}, operatingIncome={income[0].get('operatingIncome')}")

                # Estimate forward EBIT (with growth)
                if len(income) > 1:
                    revenue_current = income[0].get('revenue', 0)
                    revenue_prev = income[1].get('revenue', 1)
                    if revenue_prev and revenue_prev > 0:
                        revenue_growth = (revenue_current - revenue_prev) / revenue_prev
                        growth_rate = max(0, min(revenue_growth, 0.20))  # Cap at 20%
                    else:
                        growth_rate = 0.08
                else:
                    growth_rate = 0.08

                ebit_forward = ebit_ttm * (1 + growth_rate)

                logger.debug(f"Forward Multiple: {symbol} ebit_forward={ebit_forward}")

                if ebit_forward <= 0:
                    msg = f"Forward Multiple: EBIT forward <= 0 (got {ebit_forward:,.0f}). Check EBITDA and D&A data."
                    logger.warning(f"{symbol} {msg}")
                    add_note(f"✗ {msg}")
                    return None

                # Get peer EV/EBIT
                if peers_df is not None and 'ev_ebit_ttm' in peers_df.columns:
                    stock_peers = self.fmp.get_stock_peers(symbol)
                    if stock_peers and 'peersList' in stock_peers[0]:
                        peer_symbols = stock_peers[0]['peersList'][:5]

                        peer_multiples = []
                        for peer in peer_symbols:
                            if peer in peers_df.index:
                                ev_ebit = peers_df.loc[peer, 'ev_ebit_ttm']
                                if ev_ebit and ev_ebit > 0 and ev_ebit < 30:  # Sanity check
                                    peer_multiples.append(ev_ebit)

                        if peer_multiples:
                            peer_multiple = sum(peer_multiples) / len(peer_multiples)

                # Fallback: sector average
                if not peer_multiple:
                    peer_multiple = 12  # EV/EBIT ~12x

                # Fair EV = EBIT_forward * Peer_EV_EBIT
                fair_ev = ebit_forward * peer_multiple

                # Convert to equity value
                total_debt = balance[0].get('totalDebt', 0)
                cash = balance[0].get('cashAndCashEquivalents', 0)
                net_debt = total_debt - cash

                equity_value = fair_ev - net_debt
                fair_value_per_share = equity_value / shares

                return fair_value_per_share if fair_value_per_share > 0 else None

            elif company_type == 'reit':
                # Use P/FFO

                net_income = income[0].get('netIncome', 0)
                depreciation = abs(cashflow[0].get('depreciationAndAmortization', 0))
                ffo = net_income + depreciation

                # Forward FFO
                if len(income) > 1:
                    revenue_growth = (income[0].get('revenue', 0) - income[1].get('revenue', 1)) / income[1].get('revenue', 1)
                    growth_rate = max(0, min(revenue_growth, 0.10))
                else:
                    growth_rate = 0.05

                ffo_forward = ffo * (1 + growth_rate)
                ffo_per_share = ffo_forward / shares

                if ffo_per_share <= 0:
                    return None

                # Peer P/FFO (use P/E as proxy if not available)
                peer_multiple = 15  # Default P/FFO for REITs

                fair_value = ffo_per_share * peer_multiple

                return fair_value

            elif company_type == 'utility':
                # Use EV/EBITDA (capital-intensive like utilities prefer this)

                ebitda_ttm = income[0].get('ebitda', 0)

                # Forward EBITDA (low growth assumption ~3%)
                growth_rate = 0.03

                ebitda_forward = ebitda_ttm * (1 + growth_rate)

                if ebitda_forward <= 0:
                    return None

                # Peer EV/EBITDA for utilities (typically 10-14x)
                peer_multiple = 11  # Conservative

                # Fair EV = EBITDA_forward * Peer_EV_EBITDA
                fair_ev = ebitda_forward * peer_multiple

                # Convert to equity value
                total_debt = balance[0].get('totalDebt', 0)
                cash = balance[0].get('cashAndCashEquivalents', 0)
                net_debt = total_debt - cash

                equity_value = fair_ev - net_debt
                fair_value_per_share = equity_value / shares

                return fair_value_per_share if fair_value_per_share > 0 else None

            elif company_type == 'asset_manager':
                # Asset Managers / PE: Use P/E multiple (NOT P/B)
                # P/B is inappropriate for fee-based, asset-light businesses
                # Calibrated with Blackstone, KKR, Brookfield, Partners Group, Apollo

                net_income = income[0].get('netIncome', 0)

                # Normalize for performance fees if needed (same logic as DCF)
                if len(income) > 1:
                    net_income_prev = income[1].get('netIncome', 1)
                    if net_income_prev > 0:
                        earnings_growth = (net_income - net_income_prev) / net_income_prev
                        if earnings_growth > 0.40:
                            # Use average to smooth out performance fee volatility
                            net_income = (net_income + net_income_prev) / 2
                            add_note(f"💡 Normalized earnings for forward P/E")

                # Forward earnings (modest growth: 8-12%)
                if len(income) > 1:
                    revenue_growth = (income[0].get('revenue', 0) - income[1].get('revenue', 1)) / income[1].get('revenue', 1)
                    growth_rate = max(0.08, min(revenue_growth, 0.12))  # 8-12%
                else:
                    growth_rate = 0.10

                earnings_forward = net_income * (1 + growth_rate)
                earnings_per_share = earnings_forward / shares

                if earnings_per_share <= 0:
                    msg = f"Forward Multiple (Asset Manager): EPS <= 0 (got {earnings_per_share:.2f})"
                    logger.warning(f"{symbol} {msg}")
                    add_note(f"✗ {msg}")
                    return None

                # Sector P/E for quality asset managers
                # Research: Blackstone ~18x, KKR ~17x, Brookfield ~16x, Partners Group ~20x
                # Apollo ~15x, Carlyle ~14x
                # Average: ~17x for quality AMs
                # Range: 15-20x depending on AUM growth quality

                peer_pe = None
                if peers_df is not None and 'pe_ttm' in peers_df.columns:
                    stock_peers = self.fmp.get_stock_peers(symbol)
                    if stock_peers and 'peersList' in stock_peers[0]:
                        peer_symbols = stock_peers[0]['peersList'][:5]

                        peer_pes = []
                        for peer in peer_symbols:
                            if peer in peers_df.index:
                                pe = peers_df.loc[peer, 'pe_ttm']
                                # Sanity: P/E 10-30x for asset managers
                                if pe and pe > 10 and pe < 30:
                                    peer_pes.append(pe)

                        if peer_pes:
                            peer_pe = sum(peer_pes) / len(peer_pes)
                            logger.info(f"Forward Multiple (Asset Manager): {symbol} peer P/E={peer_pe:.1f}x from {len(peer_pes)} peers")
                            add_note(f"✓ Peer P/E: {peer_pe:.1f}x (from {len(peer_pes)} asset manager peers)")

                # Fallback: sector average P/E = 17x (calibrated with BX, KKR, BAM, PGHN)
                if not peer_pe:
                    peer_pe = 17.0
                    logger.info(f"Forward Multiple (Asset Manager): {symbol} using sector P/E={peer_pe:.1f}x")
                    add_note(f"✓ Sector P/E: {peer_pe:.1f}x (Blackstone/KKR/Brookfield avg)")

                fair_value = earnings_per_share * peer_pe

                logger.info(f"Forward Multiple (Asset Manager): {symbol} fair_value=${fair_value:.2f} (EPS=${earnings_per_share:.2f} × P/E={peer_pe:.1f}x)")

                # Sanity check
                if fair_value > earnings_per_share * 30:
                    msg = f"Forward Multiple (Asset Manager): Fair value ${fair_value:.2f} seems too high (>30x EPS). Capping at 25x."
                    logger.warning(f"{symbol} {msg}")
                    add_note(f"⚠️ {msg}")
                    fair_value = earnings_per_share * 25

                return fair_value if fair_value > 0 else None

            else:  # Financial (banks, insurance)
                # Use P/B (Price to Book) for traditional financials
                # Asset managers handled separately above

                book_value = balance[0].get('totalStockholdersEquity', 0)

                # CRITICAL: Use the shares variable already calculated above
                # DO NOT recalculate or use commonStock (which is NOT share count)

                if shares <= 0 or book_value <= 0:
                    msg = f"Forward Multiple (Financial): Invalid shares ({shares:,}) or book_value ({book_value:,})"
                    logger.warning(f"{symbol} {msg}")
                    add_note(f"✗ {msg}")
                    return None

                book_per_share = book_value / shares

                logger.info(f"Forward Multiple (Financial): {symbol} book_value={book_value:,}, shares={shares:,}, book_per_share=${book_per_share:.2f}")

                # Get peer P/B
                peer_pb = None
                if peers_df is not None and 'pb_ttm' in peers_df.columns:
                    stock_peers = self.fmp.get_stock_peers(symbol)
                    if stock_peers and 'peersList' in stock_peers[0]:
                        peer_symbols = stock_peers[0]['peersList'][:5]

                        peer_pbs = []
                        for peer in peer_symbols:
                            if peer in peers_df.index:
                                pb = peers_df.loc[peer, 'pb_ttm']
                                if pb and pb > 0 and pb < 5:  # Sanity check: P/B < 5x for financials
                                    peer_pbs.append(pb)

                        if peer_pbs:
                            peer_pb = sum(peer_pbs) / len(peer_pbs)
                            logger.info(f"Forward Multiple (Financial): {symbol} calculated peer_pb={peer_pb:.2f} from {len(peer_pbs)} peers")

                # Fallback: sector average P/B for financials
                if not peer_pb:
                    peer_pb = 1.2  # P/B ~1.2x for financials (conservative)
                    logger.info(f"Forward Multiple (Financial): {symbol} using fallback peer_pb={peer_pb:.2f}")

                fair_value = book_per_share * peer_pb

                logger.info(f"Forward Multiple (Financial): {symbol} fair_value=${fair_value:.2f} (book_per_share=${book_per_share:.2f} × peer_pb={peer_pb:.2f})")

                # Sanity check: fair value should be reasonable (not crazy high/low)
                if fair_value > book_per_share * 10:
                    msg = f"Forward Multiple (Financial): Fair value ${fair_value:.2f} seems too high (>10x book). Capping at 3x book."
                    logger.warning(f"{symbol} {msg}")
                    add_note(f"⚠️ {msg}")
                    fair_value = book_per_share * 3

                return fair_value if fair_value > 0 else None

        except Exception as e:
            msg = f"Forward Multiple: Exception - {str(e)[:150]}"
            logger.error(f"{symbol} {msg}", exc_info=True)
            add_note(f"✗ {msg}")
            return None

    def _calculate_historical_multiple(self, symbol: str, company_type: str) -> Optional[float]:
        """
        Value using historical EV/EBIT or EV/FCF average.

        For non-financial: Use EV/EBIT historical average
        For financial: Use book value multiple
        For REIT: Use historical FFO yield
        """
        try:
            income = self.fmp.get_income_statement(symbol, period='annual', limit=3)
            balance = self.fmp.get_balance_sheet(symbol, period='annual', limit=3)
            cashflow = self.fmp.get_cash_flow(symbol, period='annual', limit=3)

            if not (income and balance):
                return None

            # Get shares outstanding (keep in actual count, not millions)
            shares = (balance[0].get('weightedAverageShsOut') or
                     balance[0].get('commonStockSharesOutstanding') or
                     balance[0].get('weightedAverageShsOutDil'))

            logger.info(f"Historical Multiple: {symbol} shares from balance sheet: {shares}")

            if not shares or shares <= 0:
                # Fallback to profile
                logger.info(f"Historical Multiple: {symbol} shares not in balance sheet, trying profile")
                profile = self.fmp.get_profile(symbol)
                if profile and len(profile) > 0:
                    shares = profile[0].get('sharesOutstanding', 0)
                    logger.info(f"Historical Multiple: {symbol} shares from profile: {shares}")

                    # If still no shares, try calculating from mktCap / price
                    if not shares or shares <= 0:
                        mkt_cap = profile[0].get('mktCap')
                        price = profile[0].get('price')
                        if mkt_cap and price and price > 0:
                            shares = int(mkt_cap / price)
                            logger.info(f"Historical Multiple: {symbol} calculated shares from mktCap/price: {shares:,}")

            if not shares or shares <= 0:
                logger.warning(f"Historical Multiple: {symbol} Could not get shares outstanding (got {shares})")
                return None

            if company_type == 'non_financial':
                # Use current EBIT with historical average EV/EBIT (10-12x)

                # Get EBIT: Try multiple approaches (same logic as forward multiple)
                ebitda = income[0].get('ebitda') or income[0].get('EBITDA')

                # D&A might be in cash flow or income statement
                da = None
                if cashflow and len(cashflow) > 0:
                    da = abs(cashflow[0].get('depreciationAndAmortization', 0))
                if not da or da == 0:
                    da = abs(income[0].get('depreciationAndAmortization', 0))

                if ebitda and ebitda > 0 and da and da > 0:
                    ebit_ttm = ebitda - da
                else:
                    # Use operatingIncome directly
                    ebit_ttm = income[0].get('operatingIncome') or income[0].get('ebit') or 0

                if ebit_ttm <= 0:
                    logger.debug(f"Historical Multiple: {symbol} ebit_ttm <= 0, returning None")
                    return None

                # Historical sector average EV/EBIT
                historical_ev_ebit = 11  # Conservative 11x

                fair_ev = ebit_ttm * historical_ev_ebit

                # Convert to equity
                total_debt = balance[0].get('totalDebt', 0)
                cash = balance[0].get('cashAndCashEquivalents', 0)
                net_debt = total_debt - cash

                equity_value = fair_ev - net_debt
                fair_value_per_share = equity_value / shares

                return fair_value_per_share if fair_value_per_share > 0 else None

            elif company_type == 'reit':
                # Use FFO with historical P/FFO (14-16x)
                net_income = income[0].get('netIncome', 0)
                depreciation = abs(cashflow[0].get('depreciationAndAmortization', 0))
                ffo = net_income + depreciation

                ffo_per_share = ffo / shares

                # Historical P/FFO
                historical_p_ffo = 14

                fair_value = ffo_per_share * historical_p_ffo

                return fair_value if fair_value > 0 else None

            elif company_type == 'utility':
                # Use current EBITDA with historical average EV/EBITDA (10-12x)
                ebitda_ttm = income[0].get('ebitda', 0)

                if ebitda_ttm <= 0:
                    return None

                # Historical sector average EV/EBITDA for utilities
                historical_ev_ebitda = 11  # Conservative 11x

                fair_ev = ebitda_ttm * historical_ev_ebitda

                # Convert to equity
                total_debt = balance[0].get('totalDebt', 0)
                cash = balance[0].get('cashAndCashEquivalents', 0)
                net_debt = total_debt - cash

                equity_value = fair_ev - net_debt
                fair_value_per_share = equity_value / shares

                return fair_value_per_share if fair_value_per_share > 0 else None

            else:  # Financial
                # Use book value multiple (typically 1.0-1.5x for banks)
                book_value = balance[0].get('totalStockholdersEquity', 0)
                book_per_share = book_value / shares

                # Historical P/B for financials
                historical_pb = 1.2

                fair_value = book_per_share * historical_pb

                return fair_value if fair_value > 0 else None

        except Exception as e:
            logger.warning(f"Historical multiple calculation failed for {symbol}: {e}")
            return None

    def _calculate_price_projections(
        self,
        symbol: str,
        current_price: float,
        dcf_value: Optional[float],
        forward_value: Optional[float],
        company_type: str,
        wacc: float
    ) -> Dict:
        """
        Calculate price targets under different growth scenarios.

        Scenarios:
        - Bear: Low growth (3%)
        - Base: Current growth trend
        - Bull: High growth (15%)

        Returns dict with price targets for 1Y, 3Y, 5Y horizons.
        """
        projections = {
            'scenarios': {},
            'current_price': current_price
        }

        try:
            # Get recent financial data to estimate current growth
            income = self.fmp.get_income_statement(symbol, period='annual', limit=3)

            if not income or len(income) < 2:
                return projections

            # Estimate current growth rate
            revenue_current = income[0].get('revenue', 0)
            revenue_prev = income[1].get('revenue', 0)

            if revenue_prev > 0:
                current_growth = (revenue_current - revenue_prev) / revenue_prev
                current_growth = max(0, min(current_growth, 0.50))  # Cap at 50% (allow higher growth for tech/high-growth companies)
            else:
                current_growth = 0.08  # Default 8%

            # Define scenarios with intelligent logic
            # Bear: Conservative scenario (3% or half of current growth, whichever is higher)
            bear_growth = max(0.03, current_growth * 0.5)

            # Base: Current trend (as-is)
            base_growth = current_growth

            # Bull: Optimistic acceleration (1.5x current, but at least 1.5x base to ensure bull > base)
            bull_growth = max(current_growth * 1.5, base_growth * 1.2)  # At least 20% higher than base

            scenarios = {
                'Bear Case': {
                    'growth_rate': bear_growth,
                    'description': 'Conservative: Slow growth, market challenges'
                },
                'Base Case': {
                    'growth_rate': base_growth,
                    'description': f'Current trend: {base_growth:.1%} revenue growth'
                },
                'Bull Case': {
                    'growth_rate': bull_growth,
                    'description': 'Optimistic: Accelerated growth, market expansion'
                }
            }

            # Calculate price targets for each scenario
            for scenario_name, scenario_data in scenarios.items():
                growth_rate = scenario_data['growth_rate']

                # Price projections should be based on fundamental growth,
                # NOT on convergence to fair value (that's a separate assessment)
                #
                # Simple approach: Price should grow with fundamentals (revenue/earnings)
                # If company grows revenue at X%, price should eventually follow

                # For undervalued stocks, we can add a small boost for convergence
                # For overvalued stocks, we DON'T penalize growth (market can stay irrational)

                # Calculate fair value for reference
                if dcf_value and dcf_value > 0:
                    fair_value = dcf_value
                elif forward_value and forward_value > 0:
                    fair_value = forward_value
                else:
                    fair_value = current_price  # No adjustment if no valuation

                # Only apply convergence boost if undervalued (not penalty if overvalued)
                convergence_factor = 0
                if fair_value > current_price:
                    # Undervalued: Add small boost (10% weight on convergence)
                    years_to_fair = 5  # Longer timeframe for convergence
                    fair_value_return = ((fair_value / current_price) ** (1 / years_to_fair)) - 1 if current_price > 0 else 0
                    convergence_factor = fair_value_return * 0.10  # Only 10% weight

                # Blended return: Primarily growth-based
                blended_return = growth_rate + convergence_factor

                # Calculate price targets
                price_1y = current_price * (1 + blended_return)
                price_3y = current_price * ((1 + blended_return) ** 3)
                price_5y = current_price * ((1 + blended_return) ** 5)

                projections['scenarios'][scenario_name] = {
                    'growth_assumption': f"{growth_rate:.1%}",
                    'blended_return': f"{blended_return:.1%}",
                    'description': scenario_data['description'],
                    '1Y_target': round(price_1y, 2),
                    '3Y_target': round(price_3y, 2),
                    '5Y_target': round(price_5y, 2),
                    '1Y_return': f"{((price_1y / current_price) - 1) * 100:+.1f}%",
                    '3Y_return': f"{((price_3y / current_price) - 1) * 100:+.1f}%",
                    '5Y_return': f"{((price_5y / current_price) - 1) * 100:+.1f}%",
                    '3Y_cagr': f"{(((price_3y / current_price) ** (1/3)) - 1) * 100:.1f}%",
                    '5Y_cagr': f"{(((price_5y / current_price) ** (1/5)) - 1) * 100:.1f}%"
                }

        except Exception as e:
            logger.warning(f"Failed to calculate price projections for {symbol}: {e}")

        return projections

    # ===================================
    # Advanced Qualitative Metrics
    # ===================================

    def _calculate_roic_vs_wacc(self, symbol: str, wacc: float, company_type: str = 'non_financial') -> Dict:
        """
        Calculate ROIC (Return on Invested Capital) for non-financials or ROE for financials.
        Compare to WACC. ROIC/ROE > WACC = value creation

        Non-Financial:
            ROIC = NOPAT / Invested Capital
            NOPAT = Operating Income * (1 - Tax Rate)
            Invested Capital = Total Assets - Cash - Non-Interest-Bearing Current Liabilities

        Financial:
            ROE = Net Income / Shareholders' Equity
            (Banks use equity, not invested capital)
        """
        try:
            # Get 6 years of data to calculate 5-year history
            income = self.fmp.get_income_statement(symbol, period='annual', limit=6)
            balance = self.fmp.get_balance_sheet(symbol, period='annual', limit=6)

            if not (income and balance and len(income) >= 1 and len(balance) >= 1):
                return {}

            is_financial = company_type in ['financial', 'bank']
            metric_name = 'ROE' if is_financial else 'ROIC'
            history = []

            # Calculate historical returns (5 years)
            for i in range(min(5, len(income), len(balance))):
                if is_financial:
                    # Financial: Calculate ROE
                    net_income = income[i].get('netIncome', 0)
                    equity = balance[i].get('totalStockholdersEquity', 0) or balance[i].get('totalEquity', 0)

                    if equity > 0:
                        roe = (net_income / equity) * 100
                        history.append(roe)
                else:
                    # Non-Financial: Calculate ROIC
                    oi = income[i].get('operatingIncome', 0)
                    tr = abs(income[i].get('incomeTaxExpense', 0)) / income[i].get('incomeBeforeTax', 1) if income[i].get('incomeBeforeTax', 0) > 0 else 0.21
                    tr = min(max(tr, 0), 0.50)
                    nopat = oi * (1 - tr)

                    # Invested Capital: Use simpler formula
                    # IC = Total Debt + Total Equity (more robust)
                    total_debt = balance[i].get('totalDebt', 0) or (balance[i].get('shortTermDebt', 0) + balance[i].get('longTermDebt', 0))
                    total_equity = balance[i].get('totalStockholdersEquity', 0) or balance[i].get('totalEquity', 0)
                    ic = total_debt + total_equity

                    # Fallback: If debt+equity method fails, use total assets - cash - non-interest liabilities
                    if ic <= 0:
                        ta = balance[i].get('totalAssets', 0)
                        cash = balance[i].get('cashAndCashEquivalents', 0)
                        # More conservative: only subtract non-interest bearing liabilities
                        # Approximate as current liabilities minus current debt
                        cl = balance[i].get('totalCurrentLiabilities', 0)
                        short_debt = balance[i].get('shortTermDebt', 0)
                        non_interest_cl = max(cl - short_debt, 0)  # Ensure non-negative
                        ic = ta - cash - non_interest_cl

                    if ic > 0 and nopat != 0:  # Also check NOPAT is non-zero
                        roic = (nopat / ic) * 100
                        history.append(roic)

            if not history:
                return {}

            # Current year metric
            current_metric = history[0]

            # 3-year average
            avg_3y = sum(history[:3]) / len(history[:3]) if len(history) >= 3 else current_metric

            # 5-year average
            avg_5y = sum(history) / len(history) if history else current_metric

            # Determine trend
            trend = 'stable'
            if len(history) >= 2:
                if history[0] > history[-1] * 1.05:
                    trend = 'improving'
                elif history[0] < history[-1] * 0.95:
                    trend = 'deteriorating'

            # Spread vs WACC
            spread = current_metric - (wacc * 100)

            result = {
                'metric_name': metric_name,
                'current': round(current_metric, 1),
                'wacc': round(wacc * 100, 1),
                'spread': round(spread, 1),
                'avg_3y': round(avg_3y, 1),
                'avg_5y': round(avg_5y, 1),
                'trend': trend,
                'value_creation': spread > 0,
                'assessment': 'Creating value' if spread > 0 else 'Destroying value',
                'history_5y': [round(h, 1) for h in history],  # Full 5-year history
                'years': len(history)
            }

            # Add legacy keys for backward compatibility
            if is_financial:
                result['roe'] = result['current']
            else:
                result['roic'] = result['current']
                result['avg_roic_3y'] = result['avg_3y']  # Legacy key

            return result

        except Exception as e:
            logger.warning(f"{metric_name if 'metric_name' in locals() else 'ROIC/ROE'} calculation failed for {symbol}: {e}")
            return {}

    def _calculate_margins_and_trends(self, symbol: str, peers_df: Optional[Any] = None) -> Dict:
        """
        Calculate profitability margins and their trends over 3 years.
        Compare to peer averages if available.
        """
        try:
            income = self.fmp.get_income_statement(symbol, period='annual', limit=4)
            cashflow = self.fmp.get_cash_flow(symbol, period='annual', limit=4)

            if not (income and cashflow and len(income) >= 1):
                return {}

            def calc_margins(inc, cf):
                """Calculate margins for a given period."""
                revenue = inc.get('revenue', 0)
                if revenue <= 0:
                    return None

                gross_profit = inc.get('grossProfit', 0)
                operating_income = inc.get('operatingIncome', 0)
                ocf = cf.get('operatingCashFlow', 0) if cf else 0
                capex = abs(cf.get('capitalExpenditure', 0)) if cf else 0
                fcf = ocf - capex

                return {
                    'gross': (gross_profit / revenue) * 100,
                    'operating': (operating_income / revenue) * 100,
                    'fcf': (fcf / revenue) * 100 if fcf else 0
                }

            # Calculate margins for each year
            margins_history = []
            for i in range(min(4, len(income))):
                cf = cashflow[i] if i < len(cashflow) else None
                margins = calc_margins(income[i], cf)
                if margins:
                    margins_history.append(margins)

            if not margins_history:
                return {}

            current = margins_history[0]

            # Calculate 3-year averages
            avg_3y = {
                'gross': sum(m['gross'] for m in margins_history[:3]) / min(3, len(margins_history)),
                'operating': sum(m['operating'] for m in margins_history[:3]) / min(3, len(margins_history)),
                'fcf': sum(m['fcf'] for m in margins_history[:3]) / min(3, len(margins_history))
            }

            # Determine trends
            def get_trend(current_val, avg_val):
                if current_val > avg_val * 1.05:
                    return '↗ expanding'
                elif current_val < avg_val * 0.95:
                    return '↘ contracting'
                return '→ stable'

            return {
                'gross_margin': {
                    'current': round(current['gross'], 1),
                    'avg_3y': round(avg_3y['gross'], 1),
                    'trend': get_trend(current['gross'], avg_3y['gross'])
                },
                'operating_margin': {
                    'current': round(current['operating'], 1),
                    'avg_3y': round(avg_3y['operating'], 1),
                    'trend': get_trend(current['operating'], avg_3y['operating'])
                },
                'fcf_margin': {
                    'current': round(current['fcf'], 1),
                    'avg_3y': round(avg_3y['fcf'], 1),
                    'trend': get_trend(current['fcf'], avg_3y['fcf'])
                }
            }

        except Exception as e:
            logger.warning(f"Margins calculation failed for {symbol}: {e}")
            return {}

    def _calculate_cash_conversion_cycle(self, symbol: str) -> Dict:
        """
        Calculate Cash Conversion Cycle (CCC) and its components.

        CCC = DSO + DIO - DPO
        DSO = Days Sales Outstanding (how long to collect receivables)
        DIO = Days Inventory Outstanding (how long inventory sits)
        DPO = Days Payables Outstanding (how long to pay suppliers)

        CCC < 0 = Company collects cash before paying (excellent, e.g., Amazon)
        CCC low = Efficient working capital management
        CCC high = Cash tied up, potential liquidity issues
        """
        try:
            income = self.fmp.get_income_statement(symbol, period='annual', limit=2)
            balance = self.fmp.get_balance_sheet(symbol, period='annual', limit=2)

            if not (income and balance and len(income) >= 1 and len(balance) >= 1):
                return {}

            # Current year data
            revenue = income[0].get('revenue', 0)
            cogs = income[0].get('costOfRevenue', 0) or (revenue - income[0].get('grossProfit', 0))

            accounts_receivable = balance[0].get('netReceivables', 0) or balance[0].get('accountsReceivables', 0)
            inventory = balance[0].get('inventory', 0)
            accounts_payable = balance[0].get('accountPayables', 0)

            if revenue <= 0 or cogs <= 0:
                return {}

            # Calculate components
            dso = (accounts_receivable / revenue) * 365 if revenue > 0 else 0
            dio = (inventory / cogs) * 365 if cogs > 0 else 0
            dpo = (accounts_payable / cogs) * 365 if cogs > 0 else 0

            ccc = dso + dio - dpo

            # Calculate YoY trend if data available
            trend = 'stable'
            yoy_change = None
            if len(income) >= 2 and len(balance) >= 2:
                prev_revenue = income[1].get('revenue', 0)
                prev_cogs = income[1].get('costOfRevenue', 0) or (prev_revenue - income[1].get('grossProfit', 0))
                prev_ar = balance[1].get('netReceivables', 0) or balance[1].get('accountsReceivables', 0)
                prev_inv = balance[1].get('inventory', 0)
                prev_ap = balance[1].get('accountPayables', 0)

                if prev_revenue > 0 and prev_cogs > 0:
                    prev_dso = (prev_ar / prev_revenue) * 365
                    prev_dio = (prev_inv / prev_cogs) * 365
                    prev_dpo = (prev_ap / prev_cogs) * 365
                    prev_ccc = prev_dso + prev_dio - prev_dpo

                    yoy_change = ccc - prev_ccc
                    if yoy_change < -5:
                        trend = 'improving'
                    elif yoy_change > 5:
                        trend = 'deteriorating'

            # Assessment
            if ccc < 0:
                assessment = 'Excellent - Negative CCC (collects before paying)'
            elif ccc < 30:
                assessment = 'Very Good - Efficient working capital'
            elif ccc < 60:
                assessment = 'Good - Reasonable working capital'
            elif ccc < 90:
                assessment = 'Adequate - Room for improvement'
            else:
                assessment = 'Concerning - High cash tied up'

            return {
                'dso': round(dso, 1),
                'dio': round(dio, 1),
                'dpo': round(dpo, 1),
                'ccc': round(ccc, 1),
                'trend': trend,
                'yoy_change': round(yoy_change, 1) if yoy_change is not None else None,
                'assessment': assessment
            }

        except Exception as e:
            logger.warning(f"Cash Conversion Cycle calculation failed for {symbol}: {e}")
            return {}

    def _calculate_operating_leverage(self, symbol: str) -> Dict:
        """
        Calculate Operating Leverage: sensitivity of EBIT to revenue changes.

        Operating Leverage = % Change EBIT / % Change Revenue

        OL > 2 = High operating leverage (sensitive to revenue, high fixed costs)
        OL 1-2 = Moderate leverage
        OL < 1 = Low leverage (variable costs dominate)
        """
        try:
            income = self.fmp.get_income_statement(symbol, period='annual', limit=3)

            if not (income and len(income) >= 2):
                return {}

            # Current vs previous year
            revenue_current = income[0].get('revenue', 0)
            revenue_prev = income[1].get('revenue', 0)
            ebit_current = income[0].get('operatingIncome', 0)  # EBIT
            ebit_prev = income[1].get('operatingIncome', 0)

            if revenue_prev <= 0 or ebit_prev == 0:
                return {}

            # Calculate % changes
            revenue_change_pct = ((revenue_current - revenue_prev) / revenue_prev) * 100
            ebit_change_pct = ((ebit_current - ebit_prev) / abs(ebit_prev)) * 100

            # Operating leverage
            if revenue_change_pct != 0:
                operating_leverage = ebit_change_pct / revenue_change_pct
            else:
                operating_leverage = 0

            # Calculate 2-year average if available
            ol_avg = operating_leverage
            if len(income) >= 3:
                rev_1 = income[1].get('revenue', 0)
                rev_2 = income[2].get('revenue', 0)
                ebit_1 = income[1].get('operatingIncome', 0)
                ebit_2 = income[2].get('operatingIncome', 0)

                if rev_2 > 0 and ebit_2 != 0:
                    rev_chg_2 = ((rev_1 - rev_2) / rev_2) * 100
                    ebit_chg_2 = ((ebit_1 - ebit_2) / abs(ebit_2)) * 100
                    if rev_chg_2 != 0:
                        ol_2 = ebit_chg_2 / rev_chg_2
                        ol_avg = (operating_leverage + ol_2) / 2

            # Assessment
            if abs(operating_leverage) > 3:
                assessment = 'Very High - Highly sensitive to revenue changes'
                risk = 'High'
            elif abs(operating_leverage) > 2:
                assessment = 'High - Significant fixed cost base'
                risk = 'Moderate-High'
            elif abs(operating_leverage) > 1:
                assessment = 'Moderate - Balanced cost structure'
                risk = 'Moderate'
            else:
                assessment = 'Low - Variable costs dominate, more stable'
                risk = 'Low'

            return {
                'operating_leverage': round(operating_leverage, 2),
                'ol_avg_2y': round(ol_avg, 2),
                'revenue_change_%': round(revenue_change_pct, 1),
                'ebit_change_%': round(ebit_change_pct, 1),
                'assessment': assessment,
                'risk_level': risk
            }

        except Exception as e:
            logger.warning(f"Operating Leverage calculation failed for {symbol}: {e}")
            return {}

    def _calculate_reinvestment_quality(self, symbol: str) -> Dict:
        """
        Calculate Reinvestment Rate and Growth Quality metrics.

        Reinvestment Rate = (Capex - D&A + Δ Working Capital) / NOPAT
        Growth ROIC = Revenue Growth % / Reinvestment Rate

        High Growth ROIC = Efficient growth (little capital needed)
        Low Growth ROIC = Capital-intensive growth (poor efficiency)
        """
        try:
            income = self.fmp.get_income_statement(symbol, period='annual', limit=3)
            balance = self.fmp.get_balance_sheet(symbol, period='annual', limit=3)
            cashflow = self.fmp.get_cash_flow(symbol, period='annual', limit=3)

            if not (income and balance and cashflow and len(income) >= 2):
                return {}

            # Calculate NOPAT (current year)
            operating_income = income[0].get('operatingIncome', 0)
            tax_rate = abs(income[0].get('incomeTaxExpense', 0)) / income[0].get('incomeBeforeTax', 1) if income[0].get('incomeBeforeTax', 0) > 0 else 0.21
            tax_rate = min(max(tax_rate, 0), 0.50)
            nopat = operating_income * (1 - tax_rate)

            # Calculate reinvestment components
            capex = abs(cashflow[0].get('capitalExpenditure', 0))
            da = abs(cashflow[0].get('depreciationAndAmortization', 0))

            # Change in working capital
            current_assets = balance[0].get('totalCurrentAssets', 0)
            current_liabilities = balance[0].get('totalCurrentLiabilities', 0)
            current_wc = current_assets - current_liabilities

            if len(balance) >= 2:
                prev_assets = balance[1].get('totalCurrentAssets', 0)
                prev_liabilities = balance[1].get('totalCurrentLiabilities', 0)
                prev_wc = prev_assets - prev_liabilities
                delta_wc = current_wc - prev_wc
            else:
                delta_wc = 0

            # Reinvestment = Net Capex + Δ WC
            net_capex = capex - da
            reinvestment = net_capex + delta_wc

            if nopat <= 0:
                return {}

            reinvestment_rate = (reinvestment / nopat) * 100

            # Revenue growth
            revenue_current = income[0].get('revenue', 0)
            revenue_prev = income[1].get('revenue', 0)

            if revenue_prev > 0:
                revenue_growth = ((revenue_current - revenue_prev) / revenue_prev) * 100
            else:
                revenue_growth = 0

            # Growth ROIC = Revenue Growth / Reinvestment Rate
            if reinvestment_rate > 0:
                growth_roic = revenue_growth / reinvestment_rate
            else:
                growth_roic = 0 if revenue_growth <= 0 else 999  # Infinite efficiency (no reinvestment needed)

            # Calculate capital efficiency: Revenue / (Net PPE + WC)
            ppe = balance[0].get('propertyPlantEquipmentNet', 0)
            capital_base = ppe + current_wc
            if capital_base > 0:
                capital_efficiency = revenue_current / capital_base
            else:
                capital_efficiency = 0

            # Assessment
            if growth_roic > 2:
                assessment = 'Excellent - High growth with low capital needs'
                quality = 'High Quality'
            elif growth_roic > 1:
                assessment = 'Good - Balanced growth and reinvestment'
                quality = 'Good Quality'
            elif growth_roic > 0.5:
                assessment = 'Adequate - Moderate capital efficiency'
                quality = 'Moderate Quality'
            else:
                assessment = 'Concerning - Capital-intensive growth'
                quality = 'Low Quality'

            return {
                'reinvestment_rate_%': round(reinvestment_rate, 1),
                'revenue_growth_%': round(revenue_growth, 1),
                'growth_roic': round(growth_roic, 2),
                'capex': capex,
                'net_capex': net_capex,
                'delta_wc': delta_wc,
                'reinvestment_total': reinvestment,
                'capital_efficiency': round(capital_efficiency, 2),
                'assessment': assessment,
                'quality': quality
            }

        except Exception as e:
            logger.warning(f"Reinvestment Quality calculation failed for {symbol}: {e}")
            return {}

    def _calculate_economic_profit(self, symbol: str) -> Dict:
        """
        Calculate Economic Profit (EVA - Economic Value Added).

        EVA = NOPAT - (WACC × Invested Capital)

        EVA > 0 = Company creates value above cost of capital
        EVA < 0 = Company destroys value (returns below cost of capital)

        This complements ROIC by showing absolute $ value creation, not just %.
        A company can have good ROIC but low EVA if scale is small.
        """
        try:
            income = self.fmp.get_income_statement(symbol, period='annual', limit=5)
            balance = self.fmp.get_balance_sheet(symbol, period='annual', limit=5)

            if not (income and balance and len(income) >= 1 and len(balance) >= 1):
                return {}

            # Calculate NOPAT
            operating_income = income[0].get('operatingIncome', 0)
            tax_rate = abs(income[0].get('incomeTaxExpense', 0)) / income[0].get('incomeBeforeTax', 1) if income[0].get('incomeBeforeTax', 0) != 0 else 0.21
            tax_rate = min(max(tax_rate, 0), 0.5)  # Cap between 0-50%
            nopat = operating_income * (1 - tax_rate)

            # Calculate Invested Capital (Debt + Equity method)
            total_debt = balance[0].get('totalDebt', 0)
            if total_debt == 0:
                short_debt = balance[0].get('shortTermDebt', 0) or 0
                long_debt = balance[0].get('longTermDebt', 0) or 0
                total_debt = short_debt + long_debt

            total_equity = balance[0].get('totalStockholdersEquity', 0) or balance[0].get('totalEquity', 0)
            invested_capital = total_debt + total_equity

            if invested_capital <= 0:
                return {}

            # Get WACC (we calculate this elsewhere, reuse if available)
            # For simplicity, use a reasonable estimate based on risk-free rate + equity risk premium
            # In practice, should integrate with existing WACC calculation
            wacc = 0.10  # Default 10%, will try to get actual WACC

            # Try to get actual WACC from balance sheet analysis
            if total_debt > 0 and total_equity > 0:
                # Rough WACC estimate
                interest_expense = abs(income[0].get('interestExpense', 0))
                cost_of_debt = (interest_expense / total_debt) * (1 - tax_rate) if total_debt > 0 else 0.04
                cost_of_equity = 0.10  # Assume 10% for now (could enhance with CAPM)

                weight_debt = total_debt / invested_capital
                weight_equity = total_equity / invested_capital

                wacc = (weight_debt * cost_of_debt) + (weight_equity * cost_of_equity)
                wacc = min(max(wacc, 0.05), 0.20)  # Cap between 5-20%

            # Calculate EVA
            capital_charge = wacc * invested_capital
            eva = nopat - capital_charge

            # Calculate EVA margin (EVA / Sales)
            revenue = income[0].get('revenue', 1)
            eva_margin = (eva / revenue) * 100 if revenue > 0 else 0

            # Calculate trend (5-year if available)
            eva_history = []
            for i in range(min(5, len(income), len(balance))):
                oi = income[i].get('operatingIncome', 0)
                tax = abs(income[i].get('incomeTaxExpense', 0)) / income[i].get('incomeBeforeTax', 1) if income[i].get('incomeBeforeTax', 0) != 0 else 0.21
                tax = min(max(tax, 0), 0.5)
                nop = oi * (1 - tax)

                td = balance[i].get('totalDebt', 0)
                if td == 0:
                    td = (balance[i].get('shortTermDebt', 0) or 0) + (balance[i].get('longTermDebt', 0) or 0)
                te = balance[i].get('totalStockholdersEquity', 0) or balance[i].get('totalEquity', 0)
                ic = td + te

                if ic > 0:
                    ev = nop - (wacc * ic)
                    eva_history.append(ev)

            # Trend analysis
            trend = 'stable'
            avg_eva = sum(eva_history) / len(eva_history) if eva_history else eva
            if len(eva_history) >= 3:
                recent_avg = sum(eva_history[:2]) / 2
                older_avg = sum(eva_history[-2:]) / 2
                if recent_avg > older_avg * 1.1:
                    trend = 'improving'
                elif recent_avg < older_avg * 0.9:
                    trend = 'deteriorating'

            # Assessment
            if eva > 0:
                if eva_margin > 10:
                    assessment = 'Excellent - Strong value creation'
                    grade = 'A'
                elif eva_margin > 5:
                    assessment = 'Very Good - Solid value creation'
                    grade = 'B'
                else:
                    assessment = 'Good - Positive value creation'
                    grade = 'B-'
            else:
                if eva_margin > -5:
                    assessment = 'Fair - Marginal value destruction'
                    grade = 'C'
                else:
                    assessment = 'Poor - Significant value destruction'
                    grade = 'D'

            return {
                'eva': eva,
                'eva_formatted': f"${eva/1e9:.2f}B" if abs(eva) >= 1e9 else f"${eva/1e6:.1f}M",
                'nopat': nopat,
                'nopat_formatted': f"${nopat/1e9:.2f}B" if abs(nopat) >= 1e9 else f"${nopat/1e6:.1f}M",
                'invested_capital': invested_capital,
                'ic_formatted': f"${invested_capital/1e9:.2f}B" if invested_capital >= 1e9 else f"${invested_capital/1e6:.1f}M",
                'wacc': round(wacc * 100, 1),
                'capital_charge': capital_charge,
                'capital_charge_formatted': f"${capital_charge/1e9:.2f}B" if abs(capital_charge) >= 1e9 else f"${capital_charge/1e6:.1f}M",
                'eva_margin_%': round(eva_margin, 1),
                'trend': trend,
                'avg_eva_5y': avg_eva,
                'avg_eva_formatted': f"${avg_eva/1e9:.2f}B" if abs(avg_eva) >= 1e9 else f"${avg_eva/1e6:.1f}M",
                'assessment': assessment,
                'grade': grade
            }

        except Exception as e:
            logger.warning(f"Economic Profit calculation failed for {symbol}: {e}")
            return {}

    def _calculate_capital_allocation_score(self, symbol: str) -> Dict:
        """
        Analyze capital allocation decisions: how management deploys Free Cash Flow.

        Components:
        1. FCF usage breakdown: dividends, buybacks, debt paydown, M&A, reinvestment
        2. Buyback efficiency: stock price vs intrinsic value when buying
        3. Dividend consistency and payout ratio
        4. Organic vs inorganic growth

        Best allocators: Buy back stock when cheap, invest when ROIC > WACC
        """
        try:
            cashflow = self.fmp.get_cash_flow(symbol, period='annual', limit=5)
            income = self.fmp.get_income_statement(symbol, period='annual', limit=5)
            balance = self.fmp.get_balance_sheet(symbol, period='annual', limit=5)

            if not (cashflow and income and balance and len(cashflow) >= 2):
                return {}

            # Current year FCF
            ocf = cashflow[0].get('operatingCashFlow', 0)
            capex = abs(cashflow[0].get('capitalExpenditure', 0))
            fcf = ocf - capex

            if fcf <= 0:
                return {}

            # FCF usage breakdown
            dividends_paid = abs(cashflow[0].get('dividendsPaid', 0))
            stock_buyback = abs(cashflow[0].get('stockRepurchased', 0) or cashflow[0].get('commonStockRepurchased', 0) or 0)
            debt_repayment = cashflow[0].get('debtRepayment', 0) or 0

            # Calculate percentages
            dividend_pct = (dividends_paid / fcf) * 100 if fcf > 0 else 0
            buyback_pct = (stock_buyback / fcf) * 100 if fcf > 0 else 0
            debt_paydown_pct = (debt_repayment / fcf) * 100 if fcf > 0 else 0
            retained_pct = max(100 - dividend_pct - buyback_pct - debt_paydown_pct, 0)

            # Shareholder return rate (dividends + buybacks)
            shareholder_return_pct = dividend_pct + buyback_pct

            # Dividend consistency (check last 5 years)
            dividend_years = 0
            dividend_growth_consistent = True
            prev_div = 0
            for cf in cashflow[:5]:
                div = abs(cf.get('dividendsPaid', 0))
                if div > 0:
                    dividend_years += 1
                    if prev_div > 0 and div < prev_div * 0.95:  # Dividend cut
                        dividend_growth_consistent = False
                    prev_div = div

            # Calculate payout ratio
            net_income = income[0].get('netIncome', 1)
            payout_ratio = (dividends_paid / net_income) * 100 if net_income > 0 else 0

            # Buyback efficiency (simplified - checking if shares outstanding decreased)
            shares_current = balance[0].get('commonStock', 0) or balance[0].get('weightedAverageShsOut', 0)
            shares_prev = balance[-1].get('commonStock', 0) or balance[-1].get('weightedAverageShsOut', 0) if len(balance) >= 2 else shares_current

            share_count_change = 'decreasing' if shares_current < shares_prev * 0.98 else 'increasing' if shares_current > shares_prev * 1.02 else 'stable'

            # Calculate score (0-100)
            score = 0
            factors = []

            # Factor 1: Returns capital to shareholders (35 points)
            if shareholder_return_pct > 80:
                score += 35
                factors.append('High shareholder returns (>80% FCF)')
            elif shareholder_return_pct > 50:
                score += 25
                factors.append('Good shareholder returns (50-80% FCF)')
            elif shareholder_return_pct > 25:
                score += 15
                factors.append('Moderate shareholder returns (25-50% FCF)')
            else:
                score += 5
                factors.append('Low shareholder returns (<25% FCF)')

            # Factor 2: Dividend consistency (25 points)
            if dividend_years >= 5 and dividend_growth_consistent:
                score += 25
                factors.append('5+ years consistent dividends')
            elif dividend_years >= 3:
                score += 15
                factors.append('3-4 years of dividends')
            elif dividend_years >= 1:
                score += 5
                factors.append('Some dividend history')

            # Factor 3: Sustainable payout ratio (20 points)
            if 20 <= payout_ratio <= 60:
                score += 20
                factors.append('Sustainable payout ratio (20-60%)')
            elif 0 < payout_ratio < 80:
                score += 10
                factors.append('Reasonable payout ratio')
            elif payout_ratio > 100:
                score += 0
                factors.append('⚠️ Unsustainable payout ratio (>100%)')

            # Factor 4: Buyback execution (20 points)
            if stock_buyback > 0 and share_count_change == 'decreasing':
                score += 20
                factors.append('Effective buybacks (share count ↓)')
            elif stock_buyback > 0:
                score += 10
                factors.append('Buybacks but dilution offset')
            elif share_count_change == 'stable':
                score += 15
                factors.append('No excessive dilution')

            # Overall assessment
            if score >= 80:
                assessment = 'Excellent - Shareholder-friendly capital allocation'
                grade = 'A'
            elif score >= 65:
                assessment = 'Very Good - Strong capital discipline'
                grade = 'B'
            elif score >= 50:
                assessment = 'Good - Reasonable capital allocation'
                grade = 'C'
            elif score >= 35:
                assessment = 'Fair - Room for improvement'
                grade = 'D'
            else:
                assessment = 'Poor - Questionable capital allocation'
                grade = 'F'

            return {
                'score': round(score, 0),
                'grade': grade,
                'fcf': fcf,
                'fcf_formatted': f"${fcf/1e9:.2f}B" if abs(fcf) >= 1e9 else f"${fcf/1e6:.1f}M",
                'dividend_%_fcf': round(dividend_pct, 1),
                'buyback_%_fcf': round(buyback_pct, 1),
                'debt_paydown_%_fcf': round(debt_paydown_pct, 1),
                'retained_%_fcf': round(retained_pct, 1),
                'shareholder_return_%': round(shareholder_return_pct, 1),
                'payout_ratio_%': round(payout_ratio, 1),
                'dividend_years': dividend_years,
                'dividend_consistency': 'Yes' if dividend_growth_consistent else 'Inconsistent',
                'share_count_trend': share_count_change,
                'factors': factors,
                'assessment': assessment
            }

        except Exception as e:
            logger.warning(f"Capital Allocation Score calculation failed for {symbol}: {e}")
            return {}

    def _calculate_interest_rate_sensitivity(self, symbol: str, company_type: str) -> Dict:
        """
        Calculate interest rate sensitivity, primarily for financial companies.

        Key metrics:
        1. Net Interest Margin (NIM) = (Interest Income - Interest Expense) / Earning Assets
        2. NIM trend over time
        3. Duration gap (Asset duration - Liability duration) - proxy via maturity analysis
        4. Loan-to-deposit ratio

        High sensitivity = Vulnerable to rate changes
        Low sensitivity = More stable earnings
        """
        try:
            # Only really applicable to financials
            if company_type not in ['financial', 'bank', 'insurance']:
                # For non-financials, just check interest coverage
                income = self.fmp.get_income_statement(symbol, period='annual', limit=3)
                if not income:
                    return {}

                ebit = income[0].get('operatingIncome', 0)
                interest_expense = abs(income[0].get('interestExpense', 0))

                if interest_expense == 0:
                    return {
                        'applicable': False,
                        'note': 'Not a financial company - limited interest rate exposure',
                        'interest_coverage': 'N/A - No debt'
                    }

                coverage = ebit / interest_expense if interest_expense > 0 else 0

                return {
                    'applicable': False,
                    'interest_coverage': round(coverage, 1),
                    'note': 'Non-financial company - see Interest Coverage ratio'
                }

            # For financial companies
            income = self.fmp.get_income_statement(symbol, period='annual', limit=5)
            balance = self.fmp.get_balance_sheet(symbol, period='annual', limit=5)

            if not (income and balance and len(income) >= 2):
                return {}

            # Calculate Net Interest Margin (NIM)
            interest_income = income[0].get('interestIncome', 0) or income[0].get('totalInterestIncome', 0)
            interest_expense = abs(income[0].get('interestExpense', 0))
            net_interest_income = interest_income - interest_expense

            # Earning assets (approximation for banks)
            total_assets = balance[0].get('totalAssets', 0)
            cash = balance[0].get('cashAndCashEquivalents', 0)
            earning_assets = total_assets - cash  # Rough proxy

            nim = (net_interest_income / earning_assets) * 100 if earning_assets > 0 else 0

            # Calculate NIM trend (last 5 years)
            nim_history = []
            for i in range(min(5, len(income), len(balance))):
                ii = income[i].get('interestIncome', 0) or income[i].get('totalInterestIncome', 0)
                ie = abs(income[i].get('interestExpense', 0))
                nii = ii - ie
                ta = balance[i].get('totalAssets', 0)
                c = balance[i].get('cashAndCashEquivalents', 0)
                ea = ta - c
                n = (nii / ea) * 100 if ea > 0 else 0
                nim_history.append(n)

            # Trend analysis
            trend = 'stable'
            yoy_change = 0
            if len(nim_history) >= 2:
                yoy_change = nim_history[0] - nim_history[1]
                if yoy_change > 0.2:
                    trend = 'expanding'
                elif yoy_change < -0.2:
                    trend = 'compressing'

            avg_nim = sum(nim_history) / len(nim_history) if nim_history else nim

            # Loan-to-Deposit ratio (for banks)
            loans = balance[0].get('netLoans', 0) or balance[0].get('loansNetOfReserves', 0) or 0
            deposits = balance[0].get('deposits', 0) or balance[0].get('totalDeposits', 0) or 0

            ltd_ratio = (loans / deposits) * 100 if deposits > 0 else 0

            # Assessment
            if nim > 3.5:
                nim_assessment = 'Excellent - Strong net interest margin'
            elif nim > 2.5:
                nim_assessment = 'Good - Healthy net interest margin'
            elif nim > 1.5:
                nim_assessment = 'Adequate - Moderate margin'
            else:
                nim_assessment = 'Concerning - Thin margin'

            # Rate sensitivity assessment
            if trend == 'expanding':
                sensitivity = 'Benefiting from current rate environment'
            elif trend == 'compressing':
                sensitivity = 'Pressured by current rate environment'
            else:
                sensitivity = 'Stable margin through rate cycles'

            return {
                'applicable': True,
                'nim_%': round(nim, 2),
                'nim_trend': trend,
                'nim_yoy_change': round(yoy_change, 2),
                'nim_5y_avg': round(avg_nim, 2),
                'nim_history': [round(n, 2) for n in nim_history],
                'loan_to_deposit_%': round(ltd_ratio, 1) if ltd_ratio > 0 else None,
                'net_interest_income': net_interest_income,
                'nii_formatted': f"${net_interest_income/1e9:.2f}B" if abs(net_interest_income) >= 1e9 else f"${net_interest_income/1e6:.1f}M",
                'assessment': nim_assessment,
                'rate_sensitivity': sensitivity
            }

        except Exception as e:
            logger.warning(f"Interest Rate Sensitivity calculation failed for {symbol}: {e}")
            return {}

    def _analyze_insider_trading(self, symbol: str) -> Dict:
        """
        Analyze insider trading activity (Premium FMP feature).

        Key signals:
        1. Insider buying clusters (multiple insiders buying within 3 months)
        2. Buy vs Sell ratio
        3. Size of transactions relative to their holdings
        4. CEO/CFO buying (more significant than other insiders)

        Strong Buy Signal = Multiple insiders buying, especially C-suite
        Weak/Neutral = Mixed activity or selling
        Red Flag = Heavy insider selling
        """
        try:
            # Get insider trading data (last 12 months)
            logger.info(f"🔍 [{symbol}] Calling get_insider_trading...")
            insider_trades = self.fmp.get_insider_trading(symbol, limit=100)
            logger.info(f"🔍 [{symbol}] API returned {len(insider_trades) if insider_trades else 0} trades")

            if not insider_trades:
                logger.warning(f"⚠️  [{symbol}] No insider trading data from API")
                return {
                    'available': False,
                    'note': 'No insider trading data available'
                }

            # Log first trade to see structure
            if len(insider_trades) > 0:
                first_trade = insider_trades[0]
                logger.info(f"🔍 [{symbol}] First trade fields: {list(first_trade.keys())}")
                logger.info(f"🔍 [{symbol}] Sample transactionType: '{first_trade.get('transactionType')}'")
                logger.info(f"🔍 [{symbol}] Sample transactionDate: '{first_trade.get('transactionDate')}'")

            # Filter last 12 months
            from datetime import datetime, timedelta
            one_year_ago = datetime.now() - timedelta(days=365)
            three_months_ago = datetime.now() - timedelta(days=90)

            recent_trades = []
            date_parse_errors = 0
            for trade in insider_trades:
                try:
                    trade_date_str = trade.get('transactionDate', '')
                    if not trade_date_str:
                        date_parse_errors += 1
                        continue
                    trade_date = datetime.strptime(trade_date_str, '%Y-%m-%d')
                    if trade_date >= one_year_ago:
                        recent_trades.append(trade)
                except Exception as e:
                    date_parse_errors += 1
                    logger.debug(f"Date parse error for {symbol}: {e}")

            logger.info(f"🔍 [{symbol}] After date filter: {len(recent_trades)} recent trades (errors: {date_parse_errors})")

            if not recent_trades:
                logger.warning(f"⚠️  [{symbol}] No recent trades in last 12 months")
                return {
                    'available': False,
                    'note': 'No recent insider trades (last 12 months)'
                }

            # Categorize trades
            buys = []
            sells = []

            for trade in recent_trades:
                transaction_type = trade.get('transactionType', '').upper()
                logger.debug(f"  Processing: type='{transaction_type}' (original: '{trade.get('transactionType')}')")
                shares = trade.get('securitiesTransacted', 0)
                price = trade.get('price', 0)
                value = abs(shares * price)
                reporting_name = trade.get('reportingName', '')
                is_ceo_cfo = any(title in reporting_name.upper() for title in ['CEO', 'CFO', 'CHIEF EXECUTIVE', 'CHIEF FINANCIAL'])

                trade_info = {
                    'date': trade.get('transactionDate'),
                    'name': reporting_name,
                    'type': transaction_type,
                    'shares': shares,
                    'value': value,
                    'is_executive': is_ceo_cfo
                }

                # Classify transaction type (be flexible with various formats)
                is_buy = (
                    'P-PURCHASE' in transaction_type or
                    'PURCHASE' in transaction_type or
                    transaction_type.startswith('P-') or
                    transaction_type == 'P' or
                    'BUY' in transaction_type or
                    'ACQUIRE' in transaction_type
                )
                is_sell = (
                    'S-SALE' in transaction_type or
                    'SALE' in transaction_type or
                    transaction_type.startswith('S-') or
                    transaction_type == 'S' or
                    'SELL' in transaction_type or
                    'DISPOSE' in transaction_type
                )

                if is_buy:
                    buys.append(trade_info)
                    logger.debug(f"    ✓ Classified as BUY: {transaction_type}")
                elif is_sell:
                    sells.append(trade_info)
                    logger.debug(f"    ✓ Classified as SELL: {transaction_type}")
                else:
                    # Log unclassified types as INFO so they're visible
                    logger.info(f"    ⚠️  UNCLASSIFIED transaction type: '{transaction_type}' (original: '{trade.get('transactionType')}')")

            # Calculate metrics
            buy_count = len(buys)
            sell_count = len(sells)
            logger.info(f"🔍 [{symbol}] Classification complete: {buy_count} buys, {sell_count} sells")
            total_buy_value = sum(b['value'] for b in buys)
            total_sell_value = sum(s['value'] for s in sells)

            # Recent cluster detection (last 3 months)
            recent_buys = [b for b in buys if datetime.strptime(b['date'], '%Y-%m-%d') >= three_months_ago]
            recent_buy_count = len(recent_buys)
            unique_buyers = len(set(b['name'] for b in recent_buys))

            # Executive buying
            executive_buys = [b for b in buys if b['is_executive']]
            executive_buy_count = len(executive_buys)

            # Calculate confidence score (0-100)
            score = 0

            # Factor 1: Recent buying cluster (40 points)
            if recent_buy_count >= 5 and unique_buyers >= 3:
                score += 40
            elif recent_buy_count >= 3 and unique_buyers >= 2:
                score += 25
            elif recent_buy_count >= 1:
                score += 10

            # Factor 2: Executive buying (30 points)
            if executive_buy_count >= 3:
                score += 30
            elif executive_buy_count >= 2:
                score += 20
            elif executive_buy_count >= 1:
                score += 10

            # Factor 3: Buy/Sell ratio (20 points)
            if buy_count > 0 and sell_count == 0:
                score += 20
            elif buy_count > sell_count * 2:
                score += 15
            elif buy_count > sell_count:
                score += 10

            # Factor 4: Dollar value (10 points)
            if total_buy_value > total_sell_value * 3:
                score += 10
            elif total_buy_value > total_sell_value:
                score += 5

            # Penalty for heavy selling
            if sell_count > buy_count * 2:
                score = max(0, score - 30)

            # Assessment
            if score >= 80:
                signal = 'Strong Buy'
                assessment = 'Multiple insiders buying aggressively - very bullish'
            elif score >= 60:
                signal = 'Buy'
                assessment = 'Insider buying activity present - bullish'
            elif score >= 40:
                signal = 'Weak Buy'
                assessment = 'Some insider buying - moderately bullish'
            elif score >= 20:
                signal = 'Neutral'
                assessment = 'Mixed insider activity'
            else:
                signal = 'Sell'
                assessment = 'Insider selling outweighs buying - bearish'

            return {
                'available': True,
                'score': round(score, 0),
                'signal': signal,
                'assessment': assessment,
                'buy_count_12m': buy_count,
                'sell_count_12m': sell_count,
                'recent_buys_3m': recent_buy_count,
                'unique_buyers_3m': unique_buyers,
                'executive_buys': executive_buy_count,
                'total_buy_value': total_buy_value,
                'total_sell_value': total_sell_value,
                'buy_value_formatted': f"${total_buy_value/1e6:.1f}M" if total_buy_value >= 1e6 else f"${total_buy_value/1e3:.0f}K",
                'sell_value_formatted': f"${total_sell_value/1e6:.1f}M" if total_sell_value >= 1e6 else f"${total_sell_value/1e3:.0f}K",
                'net_position': 'Buying' if total_buy_value > total_sell_value else 'Selling',
                'recent_trades': recent_buys[:5]  # Top 5 most recent buys for display
            }

        except Exception as e:
            logger.warning(f"Insider Trading analysis failed for {symbol}: {e}")
            return {
                'available': False,
                'note': f'Analysis failed: {str(e)}'
            }

    def _analyze_earnings_sentiment(self, symbol: str) -> Dict:
        """
        Analyze sentiment from earnings call transcripts (Premium FMP feature).

        Key signals:
        1. Management tone: confident vs uncertain
        2. Keyword frequency: growth, challenges, opportunities
        3. Forward guidance tone
        4. Q&A defensiveness

        Positive Sentiment = Confident tone, growth focus, clear guidance
        Negative Sentiment = Defensive, uncertain, challenge-focused
        """
        try:
            # Get earnings call transcripts (last 4 quarters)
            transcripts = self.fmp.get_earnings_call_transcript(symbol, limit=4)

            if not transcripts or len(transcripts) == 0:
                return {
                    'available': False,
                    'note': 'No earnings transcripts available'
                }

            # Analyze most recent transcript
            latest = transcripts[0]
            content = latest.get('content', '')

            if not content or len(content) < 100:
                return {
                    'available': False,
                    'note': 'Transcript content insufficient'
                }

            # Simple sentiment analysis using keyword scoring
            # Positive keywords
            positive_keywords = [
                'strong', 'growth', 'expanding', 'opportunity', 'opportunities',
                'optimistic', 'confident', 'pleased', 'excited', 'momentum',
                'record', 'outperform', 'exceed', 'accelerate', 'improve',
                'innovative', 'leadership', 'winning', 'success', 'strength'
            ]

            # Negative keywords
            negative_keywords = [
                'challenge', 'challenges', 'difficult', 'pressure', 'pressures',
                'decline', 'decrease', 'weakness', 'concern', 'concerns',
                'uncertain', 'uncertainty', 'competitive', 'headwind', 'headwinds',
                'disappointing', 'miss', 'lower', 'weak', 'struggled'
            ]

            # Caution keywords
            caution_keywords = [
                'cautious', 'careful', 'monitoring', 'volatile', 'volatility',
                'risk', 'risks', 'macro', 'macroeconomic', 'slowdown'
            ]

            # Count occurrences (case-insensitive)
            content_lower = content.lower()
            positive_count = sum(content_lower.count(kw) for kw in positive_keywords)
            negative_count = sum(content_lower.count(kw) for kw in negative_keywords)
            caution_count = sum(content_lower.count(kw) for kw in caution_keywords)

            total_keywords = positive_count + negative_count + caution_count

            if total_keywords == 0:
                return {
                    'available': False,
                    'note': 'Insufficient keyword data for sentiment analysis'
                }

            # Calculate sentiment scores
            positive_pct = (positive_count / total_keywords) * 100
            negative_pct = (negative_count / total_keywords) * 100
            caution_pct = (caution_count / total_keywords) * 100

            # Net sentiment score (-100 to +100)
            net_sentiment = positive_pct - negative_pct

            # Confidence score (0-100)
            # High confidence = Strong positive or clear negative
            # Low confidence = Mixed/neutral
            if abs(net_sentiment) > 30:
                confidence = 90
            elif abs(net_sentiment) > 20:
                confidence = 75
            elif abs(net_sentiment) > 10:
                confidence = 60
            else:
                confidence = 40

            # Overall assessment
            if net_sentiment > 20:
                tone = 'Very Positive'
                assessment = 'Management is confident and growth-focused'
                grade = 'A'
            elif net_sentiment > 10:
                tone = 'Positive'
                assessment = 'Management tone is generally optimistic'
                grade = 'B'
            elif net_sentiment > -10:
                tone = 'Neutral'
                assessment = 'Mixed signals from management'
                grade = 'C'
            elif net_sentiment > -20:
                tone = 'Negative'
                assessment = 'Management acknowledges challenges'
                grade = 'D'
            else:
                tone = 'Very Negative'
                assessment = 'Management tone is defensive and uncertain'
                grade = 'F'

            # Detect guidance keywords
            guidance_keywords = ['guidance', 'forecast', 'outlook', 'expect', 'target']
            has_guidance = any(kw in content_lower for kw in guidance_keywords)

            # Get quarter info
            quarter = latest.get('quarter', 0)
            year = latest.get('year', 0)

            return {
                'available': True,
                'tone': tone,
                'grade': grade,
                'assessment': assessment,
                'net_sentiment': round(net_sentiment, 1),
                'confidence_%': round(confidence, 0),
                'positive_%': round(positive_pct, 1),
                'negative_%': round(negative_pct, 1),
                'caution_%': round(caution_pct, 1),
                'positive_mentions': positive_count,
                'negative_mentions': negative_count,
                'caution_mentions': caution_count,
                'has_guidance': has_guidance,
                'quarter': f"Q{quarter} {year}",
                'transcript_date': latest.get('date', 'N/A')
            }

        except Exception as e:
            logger.warning(f"Earnings Sentiment analysis failed for {symbol}: {e}")
            return {
                'available': False,
                'note': f'Analysis failed: {str(e)}'
            }

    def _detect_red_flags(self, symbol: str) -> List[str]:
        """
        Detect potential red flags in financial health.
        Returns list of warning messages.
        """
        red_flags = []

        try:
            income = self.fmp.get_income_statement(symbol, period='annual', limit=3)
            balance = self.fmp.get_balance_sheet(symbol, period='annual', limit=3)
            cashflow = self.fmp.get_cash_flow(symbol, period='annual', limit=3)

            if not (income and balance and cashflow):
                return red_flags

            # 1. Revenue growth but FCF declining
            if len(income) >= 2 and len(cashflow) >= 2:
                rev_current = income[0].get('revenue', 0)
                rev_prev = income[1].get('revenue', 0)

                ocf_current = cashflow[0].get('operatingCashFlow', 0)
                capex_current = abs(cashflow[0].get('capitalExpenditure', 0))
                fcf_current = ocf_current - capex_current

                ocf_prev = cashflow[1].get('operatingCashFlow', 0)
                capex_prev = abs(cashflow[1].get('capitalExpenditure', 0))
                fcf_prev = ocf_prev - capex_prev

                if rev_prev > 0 and fcf_prev > 0:
                    rev_growth = (rev_current - rev_prev) / rev_prev
                    fcf_growth = (fcf_current - fcf_prev) / fcf_prev

                    if rev_growth > 0.05 and fcf_growth < -0.10:
                        red_flags.append(f"⚠️ Revenue growing ({rev_growth:.1%}) but FCF declining ({fcf_growth:.1%})")

            # 2. High debt/EBITDA
            if len(income) >= 1 and len(balance) >= 1:
                ebitda = income[0].get('ebitda', 0)
                total_debt = balance[0].get('totalDebt', 0) or (balance[0].get('shortTermDebt', 0) + balance[0].get('longTermDebt', 0))

                if ebitda > 0:
                    debt_to_ebitda = total_debt / ebitda
                    if debt_to_ebitda > 4:
                        red_flags.append(f"⚠️ High leverage: Debt/EBITDA = {debt_to_ebitda:.1f}x (>4x threshold)")

            # 3. Working capital deteriorating
            if len(balance) >= 2:
                current_assets = balance[0].get('totalCurrentAssets', 0)
                current_liabilities = balance[0].get('totalCurrentLiabilities', 0)
                wc_current = current_assets - current_liabilities

                current_assets_prev = balance[1].get('totalCurrentAssets', 0)
                current_liabilities_prev = balance[1].get('totalCurrentLiabilities', 0)
                wc_prev = current_assets_prev - current_liabilities_prev

                wc_change = wc_current - wc_prev

                if wc_change < -100_000_000:  # -$100M threshold
                    red_flags.append(f"⚠️ Working capital deteriorating (${wc_change/1_000_000:.0f}M YoY)")

            # 4. Negative or very low cash flow
            if len(cashflow) >= 1:
                ocf = cashflow[0].get('operatingCashFlow', 0)
                if ocf < 0:
                    red_flags.append(f"⚠️ Negative operating cash flow (${ocf/1_000_000:.0f}M)")

            # 5. Cash flow to net income < 0.8
            if len(income) >= 1 and len(cashflow) >= 1:
                net_income = income[0].get('netIncome', 0)
                ocf = cashflow[0].get('operatingCashFlow', 0)

                if net_income > 0:
                    cf_to_ni = ocf / net_income
                    if cf_to_ni < 0.8:
                        red_flags.append(f"⚠️ Low cash conversion: OCF/Net Income = {cf_to_ni:.2f} (<0.8 threshold)")

        except Exception as e:
            logger.warning(f"Red flags detection failed for {symbol}: {e}")

        return red_flags

    def _calculate_reverse_dcf(self, symbol: str, current_price: float, wacc: float) -> Dict:
        """
        Reverse DCF: What growth rate is implied by the current stock price?

        Solves for growth rate in: Current Price = DCF(growth_rate)
        """
        try:
            income = self.fmp.get_income_statement(symbol, period='annual', limit=2)
            balance = self.fmp.get_balance_sheet(symbol, period='annual', limit=1)
            cashflow = self.fmp.get_cash_flow(symbol, period='annual', limit=1)

            if not (income and balance and cashflow):
                return {}

            # Get shares outstanding
            shares = (balance[0].get('weightedAverageShsOut') or
                     balance[0].get('commonStockSharesOutstanding') or
                     balance[0].get('weightedAverageShsOutDil'))

            if not shares or shares <= 0:
                profile = self.fmp.get_profile(symbol)
                if profile and len(profile) > 0:
                    shares = profile[0].get('sharesOutstanding', 0)
                    if not shares or shares <= 0:
                        mkt_cap = profile[0].get('mktCap')
                        price = profile[0].get('price')
                        if mkt_cap and price and price > 0:
                            shares = int(mkt_cap / price)

            if not shares or shares <= 0:
                return {}

            # Get base FCF
            ocf = cashflow[0].get('operatingCashFlow', 0)
            capex = abs(cashflow[0].get('capitalExpenditure', 0))

            # Revenue growth for maintenance capex estimation
            revenue_current = income[0].get('revenue', 0)
            revenue_prev = income[1].get('revenue', 0) if len(income) > 1 else revenue_current

            if revenue_prev > 0:
                revenue_growth = (revenue_current - revenue_prev) / revenue_prev
            else:
                revenue_growth = 0.10

            # Estimate maintenance capex
            if revenue_growth > 0.10:
                maintenance_pct = 0.50
            elif revenue_growth > 0.05:
                maintenance_pct = 0.70
            else:
                maintenance_pct = 0.90

            maintenance_capex = capex * maintenance_pct
            base_fcf = ocf - maintenance_capex

            if base_fcf <= 0:
                return {}

            # Current market cap
            market_cap = current_price * shares

            # Reverse engineer implied growth
            # Market Cap = Base FCF * (1 + g) / (WACC - g)
            # Solving for g: g = (WACC * Market_Cap - Base_FCF) / (Market_Cap + Base_FCF)

            terminal_growth = 0.03  # 3% perpetual

            # Try different growth rates to find implied rate
            # Simple iteration approach
            implied_growth = None
            for g in range(0, 51):  # 0% to 50%
                growth_rate = g / 100.0

                if growth_rate >= wacc:
                    continue

                # Simple DCF with 5-year projection
                fcf_pv = 0
                for year in range(1, 6):
                    fcf_year = base_fcf * ((1 + growth_rate) ** year)
                    pv = fcf_year / ((1 + wacc) ** year)
                    fcf_pv += pv

                # Terminal value
                fcf_terminal = base_fcf * ((1 + growth_rate) ** 5) * (1 + terminal_growth)
                terminal_value = fcf_terminal / (wacc - terminal_growth)
                terminal_pv = terminal_value / ((1 + wacc) ** 5)

                total_value = fcf_pv + terminal_pv

                # Check if close to market cap (within 5%)
                if abs(total_value - market_cap) / market_cap < 0.05:
                    implied_growth = growth_rate
                    break

            if implied_growth is None:
                # If no match found, calculate what it would be
                # This is approximate
                implied_growth = max(0, min(0.50, (wacc * market_cap - base_fcf) / (market_cap + base_fcf)))

            # Calculate implied EV/EBIT multiple
            operating_income = income[0].get('operatingIncome', 0)
            if operating_income > 0:
                enterprise_value = market_cap + balance[0].get('totalDebt', 0) - balance[0].get('cashAndCashEquivalents', 0)
                implied_ev_ebit = enterprise_value / operating_income
            else:
                implied_ev_ebit = None

            return {
                'implied_growth_rate': round(implied_growth * 100, 1),
                'current_growth_rate': round(revenue_growth * 100, 1),
                'implied_ev_ebit': round(implied_ev_ebit, 1) if implied_ev_ebit else None,
                'interpretation': self._interpret_reverse_dcf(implied_growth, revenue_growth)
            }

        except Exception as e:
            logger.warning(f"Reverse DCF failed for {symbol}: {e}")
            return {}

    def _interpret_reverse_dcf(self, implied_growth: float, actual_growth: float) -> str:
        """
        Interpret what the implied growth means.

        CRITICAL FIX: Lógica correcta de Reverse DCF
        - Si Implied Growth < Actual Growth → UNDERVALUED (mercado espera menos)
        - Si Implied Growth > Actual Growth → OVERVALUED (mercado espera más)
        """
        if implied_growth > actual_growth * 1.5:
            return "OVERVALUED: Market expects significant acceleration (+50%+ above actual)"
        elif implied_growth > actual_growth * 1.2:
            return "OVERVALUED: Market pricing in growth above current trend (+20%)"
        elif implied_growth >= actual_growth * 0.8:
            return "FAIR VALUE: Market expects continuation of current trend (±20%)"
        elif implied_growth >= actual_growth * 0.5:
            return "UNDERVALUED: Market expects moderate slowdown (implied < actual)"
        else:
            return "UNDERVALUED: Market is very pessimistic (implied << actual growth)"

    def _calculate_earnings_quality(self, symbol: str) -> Dict:
        """
        Quality of Earnings metrics to detect potential manipulation
        or low-quality earnings.

        Key metrics:
        - Cash Flow / Net Income ratio (>1 = good)
        - Accruals ratio (low = good)
        - Working capital trend
        """
        try:
            income = self.fmp.get_income_statement(symbol, period='annual', limit=3)
            balance = self.fmp.get_balance_sheet(symbol, period='annual', limit=3)
            cashflow = self.fmp.get_cash_flow(symbol, period='annual', limit=3)

            if not (income and balance and cashflow):
                return {}

            # 1. Cash Flow to Net Income ratio
            net_income = income[0].get('netIncome', 0)
            ocf = cashflow[0].get('operatingCashFlow', 0)

            cf_to_ni = ocf / net_income if net_income > 0 else 0

            # 2. Accruals (simplified)
            # Accruals = Net Income - Operating Cash Flow
            accruals = net_income - ocf
            total_assets = balance[0].get('totalAssets', 1)
            accruals_ratio = abs(accruals) / total_assets if total_assets > 0 else 0

            # 3. Working capital trend
            if len(balance) >= 2:
                wc_current = balance[0].get('totalCurrentAssets', 0) - balance[0].get('totalCurrentLiabilities', 0)
                wc_prev = balance[1].get('totalCurrentAssets', 0) - balance[1].get('totalCurrentLiabilities', 0)

                if abs(wc_prev) > 0:
                    wc_change_pct = ((wc_current - wc_prev) / abs(wc_prev)) * 100
                else:
                    wc_change_pct = 0

                if wc_change_pct > 10:
                    wc_trend = 'improving'
                elif wc_change_pct < -10:
                    wc_trend = 'deteriorating'
                else:
                    wc_trend = 'stable'
            else:
                wc_trend = 'unknown'

            # Overall assessment
            quality_score = 0
            issues = []

            if cf_to_ni >= 1.0:
                quality_score += 2
            elif cf_to_ni >= 0.8:
                quality_score += 1
            else:
                issues.append(f"Low cash conversion (OCF/NI={cf_to_ni:.2f})")

            if accruals_ratio < 0.05:
                quality_score += 2
            elif accruals_ratio < 0.10:
                quality_score += 1
            else:
                issues.append(f"High accruals ({accruals_ratio:.1%} of assets)")

            if wc_trend in ['improving', 'stable']:
                quality_score += 1
            else:
                issues.append("Working capital deteriorating")

            # Grade: A (5), B (3-4), C (2), D (0-1)
            if quality_score >= 5:
                grade = 'A'
                assessment = 'High quality'
            elif quality_score >= 3:
                grade = 'B'
                assessment = 'Good quality'
            elif quality_score >= 2:
                grade = 'C'
                assessment = 'Moderate quality'
            else:
                grade = 'D'
                assessment = 'Low quality - investigate'

            return {
                'cash_flow_to_net_income': round(cf_to_ni, 2),
                'accruals_ratio': round(accruals_ratio * 100, 2),
                'working_capital_trend': wc_trend,
                'grade': grade,
                'assessment': assessment,
                'issues': issues
            }

        except Exception as e:
            logger.warning(f"Earnings quality calculation failed for {symbol}: {e}")
            return {}

    def _calculate_dcf_sensitivity(
        self,
        symbol: str,
        company_type: str,
        base_dcf: Optional[float],
        base_wacc: float
    ) -> Dict:
        """
        Calculate DCF sensitivity to key assumptions:
        - WACC variations (±2%)
        - Terminal growth variations (2%, 3%, 4%)

        Shows range of possible valuations.
        """
        if not base_dcf:
            return {}

        try:
            sensitivities = {
                'wacc_sensitivity': {},
                'terminal_growth_sensitivity': {},
                'base_assumptions': {
                    'wacc': round(base_wacc * 100, 1),
                    'terminal_growth': 3.0,
                    'dcf_value': round(base_dcf, 2)
                }
            }

            # WACC sensitivity (±2%)
            wacc_scenarios = {
                'optimistic': base_wacc - 0.02,
                'base': base_wacc,
                'conservative': base_wacc + 0.02
            }

            for scenario_name, wacc in wacc_scenarios.items():
                if wacc > 0 and wacc < 0.30:  # Sanity check
                    dcf_value = self._calculate_dcf(symbol, company_type, wacc_override=wacc)
                    if dcf_value:
                        sensitivities['wacc_sensitivity'][scenario_name] = {
                            'wacc': round(wacc * 100, 1),
                            'dcf_value': round(dcf_value, 2)
                        }

            # Terminal growth sensitivity (2%, 3%, 4%)
            # Note: This would require modifying _calculate_dcf to accept terminal_growth param
            # For now, we'll approximate based on mathematical relationship
            # DCF is highly sensitive to terminal growth

            # Approximate formula: DCF ≈ Base_DCF * (1 + (terminal_growth_diff * factor))
            # This is a simplification
            terminal_scenarios = {
                '2%': 0.02,
                '3%': 0.03,
                '4%': 0.04
            }

            for label, tg in terminal_scenarios.items():
                # Approximate adjustment (this is simplified)
                # In reality, would need to recalculate full DCF
                tg_diff = tg - 0.03  # Difference from base 3%
                adjustment_factor = 1 + (tg_diff * 3)  # Rough approximation
                adjusted_dcf = base_dcf * adjustment_factor

                sensitivities['terminal_growth_sensitivity'][label] = {
                    'terminal_growth': round(tg * 100, 1),
                    'dcf_value': round(adjusted_dcf, 2)
                }

            # Calculate range
            all_values = []
            for scenario in sensitivities['wacc_sensitivity'].values():
                all_values.append(scenario['dcf_value'])
            for scenario in sensitivities['terminal_growth_sensitivity'].values():
                all_values.append(scenario['dcf_value'])

            if all_values:
                sensitivities['valuation_range'] = {
                    'min': round(min(all_values), 2),
                    'max': round(max(all_values), 2),
                    'spread': round(max(all_values) - min(all_values), 2)
                }

            return sensitivities

        except Exception as e:
            logger.warning(f"DCF sensitivity calculation failed for {symbol}: {e}")
            return {}

    def _calculate_balance_sheet_strength(self, symbol: str) -> Dict:
        """
        Calculate balance sheet health metrics:
        - Debt/Equity ratio
        - Current Ratio (liquidity)
        - Quick Ratio
        - Interest Coverage (ability to pay interest)
        - Cash & Equivalents
        - Debt/EBITDA
        """
        try:
            income = self.fmp.get_income_statement(symbol, period='annual', limit=1)
            balance = self.fmp.get_balance_sheet(symbol, period='annual', limit=2)

            if not (income and balance and len(balance) >= 1):
                return {}

            current_balance = balance[0]

            # Get key balance sheet items
            total_debt = (current_balance.get('totalDebt', 0) or
                         (current_balance.get('shortTermDebt', 0) + current_balance.get('longTermDebt', 0)))
            total_equity = current_balance.get('totalStockholdersEquity', 0) or current_balance.get('totalEquity', 0)
            current_assets = current_balance.get('totalCurrentAssets', 0)
            current_liabilities = current_balance.get('totalCurrentLiabilities', 0)
            cash = current_balance.get('cashAndCashEquivalents', 0) + current_balance.get('shortTermInvestments', 0)
            inventory = current_balance.get('inventory', 0)

            # Income statement items
            ebitda = income[0].get('ebitda', 0)
            ebit = income[0].get('operatingIncome', 0)  # EBIT = Operating Income
            interest_expense = abs(income[0].get('interestExpense', 0))

            # Calculate ratios
            result = {}

            # 1. Debt/Equity
            if total_equity > 0:
                debt_to_equity = total_debt / total_equity
                result['debt_to_equity'] = {
                    'value': round(debt_to_equity, 2),
                    'assessment': self._assess_debt_to_equity(debt_to_equity)
                }

            # 2. Current Ratio (liquidity)
            if current_liabilities > 0:
                current_ratio = current_assets / current_liabilities
                result['current_ratio'] = {
                    'value': round(current_ratio, 2),
                    'assessment': 'Strong' if current_ratio >= 1.5 else 'Adequate' if current_ratio >= 1.0 else 'Weak'
                }

            # 3. Quick Ratio (acid test - exclude inventory)
            if current_liabilities > 0:
                quick_assets = current_assets - inventory
                quick_ratio = quick_assets / current_liabilities
                result['quick_ratio'] = {
                    'value': round(quick_ratio, 2),
                    'assessment': 'Strong' if quick_ratio >= 1.0 else 'Adequate' if quick_ratio >= 0.7 else 'Weak'
                }

            # 4. Interest Coverage (EBIT / Interest Expense)
            if interest_expense > 0 and ebit > 0:
                interest_coverage = ebit / interest_expense
                result['interest_coverage'] = {
                    'value': round(interest_coverage, 1),
                    'assessment': 'Strong' if interest_coverage >= 5 else 'Adequate' if interest_coverage >= 2.5 else 'Risky'
                }
            elif interest_expense == 0:
                result['interest_coverage'] = {
                    'value': None,
                    'assessment': 'No debt'
                }

            # 5. Debt/EBITDA
            if ebitda > 0 and total_debt > 0:
                debt_to_ebitda = total_debt / ebitda
                result['debt_to_ebitda'] = {
                    'value': round(debt_to_ebitda, 1),
                    'assessment': 'Conservative' if debt_to_ebitda <= 2 else 'Moderate' if debt_to_ebitda <= 4 else 'High'
                }

            # 6. Cash position
            result['cash'] = {
                'value': cash,
                'formatted': f"${cash / 1e9:.2f}B" if cash >= 1e9 else f"${cash / 1e6:.1f}M"
            }

            # 7. Net Debt (Total Debt - Cash)
            net_debt = total_debt - cash
            result['net_debt'] = {
                'value': net_debt,
                'formatted': f"${net_debt / 1e9:.2f}B" if abs(net_debt) >= 1e9 else f"${net_debt / 1e6:.1f}M",
                'assessment': 'Net cash' if net_debt < 0 else 'Net debt'
            }

            # 8. Debt trend (YoY change)
            if len(balance) >= 2:
                prev_debt = (balance[1].get('totalDebt', 0) or
                            (balance[1].get('shortTermDebt', 0) + balance[1].get('longTermDebt', 0)))
                if prev_debt > 0:
                    debt_change = ((total_debt - prev_debt) / prev_debt) * 100
                    result['debt_trend'] = {
                        'yoy_change_%': round(debt_change, 1),
                        'direction': '↗ increasing' if debt_change > 5 else '↘ decreasing' if debt_change < -5 else '→ stable'
                    }

            # Overall assessment
            flags = []
            if result.get('debt_to_equity', {}).get('value', 0) > 2:
                flags.append('High leverage')
            if result.get('current_ratio', {}).get('value', 0) < 1:
                flags.append('Liquidity concern')
            if result.get('interest_coverage', {}).get('value', 999) < 2.5:
                flags.append('Weak interest coverage')

            result['overall_assessment'] = 'Strong' if not flags else 'Concerning' if len(flags) >= 2 else 'Adequate'
            result['warnings'] = flags

            return result

        except Exception as e:
            logger.warning(f"Balance sheet strength calculation failed for {symbol}: {e}")
            return {}

    def _assess_debt_to_equity(self, ratio: float) -> str:
        """Assess debt/equity ratio."""
        if ratio < 0.3:
            return 'Very Conservative'
        elif ratio < 0.5:
            return 'Conservative'
        elif ratio < 1.0:
            return 'Moderate'
        elif ratio < 2.0:
            return 'Elevated'
        else:
            return 'High Leverage'

    def _calculate_valuation_multiples(self, symbol: str, peers_list: List[str] = None) -> Dict:
        """
        Calculate key valuation multiples and compare to peers:
        - P/E ratio
        - P/B ratio
        - P/S ratio
        - PEG ratio (P/E to Growth)
        - EV/EBITDA
        """
        try:
            # Get company data
            profile = self.fmp.get_profile(symbol)
            income = self.fmp.get_income_statement(symbol, period='annual', limit=2)
            balance = self.fmp.get_balance_sheet(symbol, period='annual', limit=1)

            if not (profile and income and balance):
                return {}

            prof = profile[0]
            current_price = prof.get('price', 0)
            market_cap = prof.get('mktCap', 0)
            shares = prof.get('sharesOutstanding', 0)

            if not (current_price > 0 and market_cap > 0):
                return {}

            result = {'company': {}, 'peers_avg': {}, 'vs_peers': {}}

            # Calculate company multiples
            inc = income[0]
            bal = balance[0]

            # P/E
            eps = inc.get('eps', 0) or (inc.get('netIncome', 0) / shares if shares > 0 else 0)
            if eps > 0:
                pe_ratio = current_price / eps
                result['company']['pe'] = round(pe_ratio, 1)

            # P/B
            total_equity = bal.get('totalStockholdersEquity', 0) or bal.get('totalEquity', 0)
            if total_equity > 0 and shares > 0:
                book_value_per_share = total_equity / shares
                pb_ratio = current_price / book_value_per_share
                result['company']['pb'] = round(pb_ratio, 2)

            # P/S
            revenue = inc.get('revenue', 0)
            if revenue > 0:
                ps_ratio = market_cap / revenue
                result['company']['ps'] = round(ps_ratio, 2)

            # EV/EBITDA
            total_debt = (bal.get('totalDebt', 0) or
                         (bal.get('shortTermDebt', 0) + bal.get('longTermDebt', 0)))
            cash = bal.get('cashAndCashEquivalents', 0)
            enterprise_value = market_cap + total_debt - cash
            ebitda = inc.get('ebitda', 0)

            if ebitda > 0:
                ev_ebitda = enterprise_value / ebitda
                result['company']['ev_ebitda'] = round(ev_ebitda, 1)

            # PEG (P/E to Growth)
            if len(income) >= 2 and eps > 0:
                prev_eps = income[1].get('eps', 0) or (income[1].get('netIncome', 0) / shares if shares > 0 else 0)
                if prev_eps > 0:
                    eps_growth = ((eps - prev_eps) / prev_eps) * 100
                    if eps_growth > 0:
                        peg = result['company'].get('pe', 0) / eps_growth
                        result['company']['peg'] = round(peg, 2)
                        result['company']['eps_growth_%'] = round(eps_growth, 1)

            # Compare to peers if available
            if peers_list and len(peers_list) > 0:
                peer_multiples = self._get_peer_multiples(peers_list[:5])  # Max 5 peers

                if peer_multiples:
                    # Calculate peer averages
                    for metric in ['pe', 'pb', 'ps', 'ev_ebitda', 'peg']:
                        values = [p.get(metric) for p in peer_multiples if p.get(metric)]
                        if values:
                            avg = sum(values) / len(values)
                            result['peers_avg'][metric] = round(avg, 2)

                            # Calculate vs peers
                            company_val = result['company'].get(metric)
                            if company_val:
                                premium_discount = ((company_val - avg) / avg) * 100
                                result['vs_peers'][metric] = {
                                    'premium_discount_%': round(premium_discount, 1),
                                    'assessment': 'Premium' if premium_discount > 15 else 'Discount' if premium_discount < -15 else 'In-line'
                                }

            return result

        except Exception as e:
            logger.warning(f"Valuation multiples calculation failed for {symbol}: {e}")
            return {}

    def _get_peer_multiples(self, peers_list: List[str]) -> List[Dict]:
        """Get valuation multiples for a list of peers."""
        peer_multiples = []

        try:
            for peer in peers_list:
                try:
                    profile = self.fmp.get_profile(peer)
                    income = self.fmp.get_income_statement(peer, period='annual', limit=2)
                    balance = self.fmp.get_balance_sheet(peer, period='annual', limit=1)

                    if not (profile and income and balance):
                        continue

                    prof = profile[0]
                    inc = income[0]
                    bal = balance[0]

                    price = prof.get('price', 0)
                    market_cap = prof.get('mktCap', 0)
                    shares = prof.get('sharesOutstanding', 0)

                    if not (price > 0 and market_cap > 0):
                        continue

                    multiples = {'symbol': peer}

                    # P/E
                    eps = inc.get('eps', 0)
                    if eps > 0:
                        multiples['pe'] = price / eps

                    # P/B
                    equity = bal.get('totalStockholdersEquity', 0)
                    if equity > 0 and shares > 0:
                        multiples['pb'] = price / (equity / shares)

                    # P/S
                    revenue = inc.get('revenue', 0)
                    if revenue > 0:
                        multiples['ps'] = market_cap / revenue

                    # EV/EBITDA
                    debt = bal.get('totalDebt', 0) or 0
                    cash = bal.get('cashAndCashEquivalents', 0)
                    ev = market_cap + debt - cash
                    ebitda = inc.get('ebitda', 0)
                    if ebitda > 0:
                        multiples['ev_ebitda'] = ev / ebitda

                    # PEG
                    if len(income) >= 2 and eps > 0:
                        prev_eps = income[1].get('eps', 0)
                        if prev_eps > 0:
                            growth = ((eps - prev_eps) / prev_eps) * 100
                            if growth > 0 and 'pe' in multiples:
                                multiples['peg'] = multiples['pe'] / growth

                    peer_multiples.append(multiples)

                except Exception as e:
                    logger.warning(f"Failed to get multiples for peer {peer}: {e}")
                    continue

            return peer_multiples

        except Exception as e:
            logger.warning(f"Peer multiples fetch failed: {e}")
            return []

    def _calculate_growth_consistency(self, symbol: str) -> Dict:
        """
        Calculate historical growth trends to assess consistency:
        - Revenue growth (5 years)
        - Earnings growth (5 years)
        - FCF growth (5 years)
        - Standard deviation of growth rates (consistency measure)
        """
        try:
            income = self.fmp.get_income_statement(symbol, period='annual', limit=6)
            cashflow = self.fmp.get_cash_flow(symbol, period='annual', limit=6)

            if not (income and cashflow and len(income) >= 3):
                return {}

            result = {
                'revenue': {},
                'earnings': {},
                'fcf': {},
                'overall_assessment': ''
            }

            # Calculate revenue growth
            revenues = [inc.get('revenue', 0) for inc in income if inc.get('revenue', 0) > 0]
            if len(revenues) >= 3:
                growth_rates = []
                for i in range(len(revenues) - 1):
                    if revenues[i+1] > 0:
                        growth = ((revenues[i] - revenues[i+1]) / revenues[i+1]) * 100
                        growth_rates.append(growth)

                if growth_rates:
                    avg_growth = sum(growth_rates) / len(growth_rates)
                    # Calculate standard deviation
                    variance = sum((g - avg_growth) ** 2 for g in growth_rates) / len(growth_rates)
                    std_dev = variance ** 0.5

                    result['revenue'] = {
                        'years': len(revenues),
                        'avg_growth_%': round(avg_growth, 1),
                        'std_dev': round(std_dev, 1),
                        'consistency': 'High' if std_dev < 5 else 'Moderate' if std_dev < 15 else 'Volatile',
                        'trend': 'Growing' if avg_growth > 5 else 'Stable' if avg_growth > 0 else 'Declining',
                        'history': [round(r / 1e9, 2) for r in revenues[:5]]  # Last 5 years in billions
                    }

            # Calculate earnings growth
            net_incomes = [inc.get('netIncome', 0) for inc in income if inc.get('netIncome')]
            if len(net_incomes) >= 3:
                growth_rates = []
                for i in range(len(net_incomes) - 1):
                    if net_incomes[i+1] != 0:
                        growth = ((net_incomes[i] - net_incomes[i+1]) / abs(net_incomes[i+1])) * 100
                        # Cap extreme values
                        if -500 < growth < 500:
                            growth_rates.append(growth)

                if growth_rates:
                    avg_growth = sum(growth_rates) / len(growth_rates)
                    variance = sum((g - avg_growth) ** 2 for g in growth_rates) / len(growth_rates)
                    std_dev = variance ** 0.5

                    result['earnings'] = {
                        'years': len(net_incomes),
                        'avg_growth_%': round(avg_growth, 1),
                        'std_dev': round(std_dev, 1),
                        'consistency': 'High' if std_dev < 15 else 'Moderate' if std_dev < 30 else 'Volatile',
                        'trend': 'Growing' if avg_growth > 5 else 'Stable' if avg_growth > 0 else 'Declining',
                        'history': [round(ni / 1e9, 2) for ni in net_incomes[:5]]  # Last 5 years in billions
                    }

            # Calculate FCF growth
            fcfs = []
            for i in range(min(len(cashflow), len(income))):
                ocf = cashflow[i].get('operatingCashFlow', 0)
                capex = abs(cashflow[i].get('capitalExpenditure', 0))
                fcf = ocf - capex
                if ocf > 0:  # Only include if we have OCF data
                    fcfs.append(fcf)

            if len(fcfs) >= 3:
                growth_rates = []
                for i in range(len(fcfs) - 1):
                    if fcfs[i+1] != 0:
                        growth = ((fcfs[i] - fcfs[i+1]) / abs(fcfs[i+1])) * 100
                        # Cap extreme values
                        if -500 < growth < 500:
                            growth_rates.append(growth)

                if growth_rates:
                    avg_growth = sum(growth_rates) / len(growth_rates)
                    variance = sum((g - avg_growth) ** 2 for g in growth_rates) / len(growth_rates)
                    std_dev = variance ** 0.5

                    result['fcf'] = {
                        'years': len(fcfs),
                        'avg_growth_%': round(avg_growth, 1),
                        'std_dev': round(std_dev, 1),
                        'consistency': 'High' if std_dev < 20 else 'Moderate' if std_dev < 40 else 'Volatile',
                        'trend': 'Growing' if avg_growth > 5 else 'Stable' if avg_growth > 0 else 'Declining',
                        'history': [round(fcf / 1e9, 2) for fcf in fcfs[:5]]  # Last 5 years in billions
                    }

            # Overall assessment
            consistencies = []
            if result.get('revenue', {}).get('consistency'):
                consistencies.append(result['revenue']['consistency'])
            if result.get('earnings', {}).get('consistency'):
                consistencies.append(result['earnings']['consistency'])
            if result.get('fcf', {}).get('consistency'):
                consistencies.append(result['fcf']['consistency'])

            if 'High' in consistencies and 'Volatile' not in consistencies:
                result['overall_assessment'] = 'Highly Consistent - Predictable business'
            elif 'Volatile' in consistencies or consistencies.count('Moderate') >= 2:
                result['overall_assessment'] = 'Volatile - Unpredictable performance'
            else:
                result['overall_assessment'] = 'Moderately Consistent - Some variability'

            return result

        except Exception as e:
            logger.warning(f"Growth consistency calculation failed for {symbol}: {e}")
            return {}

    # ===================================
    # Export JSON
    # ===================================

    def export_summary(self, summary: Dict, output_path: str):
        """Export qualitative summary to JSON file."""
        try:
            with open(output_path, 'w') as f:
                json.dump(summary, f, indent=2)
            logger.info(f"Qualitative summary exported to {output_path}")
        except Exception as e:
            logger.error(f"Failed to export summary: {e}")
