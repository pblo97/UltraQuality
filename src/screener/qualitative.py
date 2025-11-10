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
            'mna_recent': [],
            'top_risks': [],
            'risks': [],  # UI expects this
            'intrinsic_value': {}  # New: valuation analysis
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

        # === 2. INSIDER TRADING ACTIVITY ===
        # Note: This endpoint may require premium FMP plan
        # For now, leave as placeholder for future enhancement

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

            # Asset-based industries (Real Estate, Banks, Insurance)
            # Research: P/B well-suited for tangible assets
            elif any(kw in industry + sector for kw in [
                'real estate', 'reit', 'bank', 'insurance', 'financial'
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

            # Financials (banks, insurance, asset managers)
            if sector == 'financial services' or sector == 'financial':
                return 'financial'

            if any(kw in industry for kw in ['bank', 'insurance', 'asset management', 'capital markets']):
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

            # Stage 1 growth (5 years): taper from current to 10%
            growth_stage1 = (revenue_growth + 0.10) / 2  # Average of current and 10%

            # Stage 2 (terminal): 3% perpetual
            terminal_growth = 0.03

            # === WACC (use industry-specific if provided) ===

            if wacc_override:
                wacc = wacc_override
            elif company_type == 'financial':
                wacc = 0.12  # Higher for financials
            elif company_type == 'reit':
                wacc = 0.09  # Lower for REITs (stable cash flows)
            elif company_type == 'utility':
                wacc = 0.08  # Lowest for utilities (regulated, stable, low risk)
            else:
                wacc = 0.10  # Standard

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

            # Convert to equity value
            total_debt = balance[0].get('totalDebt', 0)
            cash = balance[0].get('cashAndCashEquivalents', 0)
            net_debt = total_debt - cash

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

            else:  # Financial
                # Use P/B (Price to Book) for financials instead of P/E

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
        """Interpret what the implied growth means."""
        if implied_growth > actual_growth * 1.5:
            return "Market expects significant acceleration"
        elif implied_growth > actual_growth * 1.2:
            return "Market pricing in growth above current trend"
        elif implied_growth >= actual_growth * 0.8:
            return "Market expects continuation of current trend"
        else:
            return "Market expects slowdown or challenges"

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
