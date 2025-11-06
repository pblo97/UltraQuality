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
                peers_df
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
        Assess competitive moats using heuristics.

        Checklist:
        - Switching costs
        - Network effects
        - Brand / IP / Intangibles
        - Scale / efficiency
        - Regulatory assets / licenses

        Returns: {moat_type: 'Yes|No|Probable', notes: str}
        """
        moats = {
            'switching_costs': 'No',
            'network_effects': 'No',
            'brand_IP': 'No',
            'scale_efficiency': 'No',
            'regulatory_assets': 'No',
            'notes': ''
        }

        # Simple keyword-based heuristics
        # (In production, use LLM or more sophisticated NLP)

        summary_lower = business_summary.lower()

        # Switching costs
        if any(kw in summary_lower for kw in ['subscription', 'contract', 'enterprise software', 'SaaS', 'platform']):
            moats['switching_costs'] = 'Probable'

        # Network effects
        if any(kw in summary_lower for kw in ['network', 'marketplace', 'social', 'platform', 'two-sided']):
            moats['network_effects'] = 'Probable'

        # Brand / IP
        if any(kw in summary_lower for kw in ['brand', 'patent', 'trademark', 'proprietary', 'licensed', 'franchise']):
            moats['brand_IP'] = 'Probable'

        # Scale / efficiency
        if any(kw in summary_lower for kw in ['largest', 'leading', 'scale', 'manufacturing', 'distribution']):
            moats['scale_efficiency'] = 'Probable'

        # Regulatory
        if any(kw in summary_lower for kw in ['regulated', 'license', 'utility', 'telecom', 'pharmaceutical', 'FDA']):
            moats['regulatory_assets'] = 'Probable'

        # Generate notes
        moat_count = sum(1 for v in moats.values() if v in ['Yes', 'Probable'])
        moats['notes'] = f"{moat_count} potential moats identified from business description."

        return moats

    # ===================================
    # 4. Skin in the Game
    # ===================================

    def _assess_skin_in_game(self, symbol: str) -> Dict:
        """
        Assess insider alignment and dilution.

        Returns:
        {
            'insider_trend_90d': 'net buys|net sells|mixed|none',
            'insider_ownership_pct': float,
            'net_share_issuance_12m_%': float,
            'assessment': 'positive|neutral|negative'
        }
        """
        skin = {
            'insider_trend_90d': 'none',
            'insider_ownership_pct': None,
            'net_share_issuance_12m_%': None,
            'assessment': 'neutral'
        }

        # Note: FMP doesn't have a direct insider trading endpoint in all plans
        # Placeholder: would use /insider-trading or /stock_ownership

        # Dilution from balance sheet (reuse logic from guardrails)
        try:
            balance = self.fmp.get_balance_sheet(symbol, period='quarter', limit=5)
            if balance and len(balance) >= 5:
                shares_t = balance[0].get('commonStock') or balance[0].get('weightedAverageShsOut')
                shares_t4 = balance[4].get('commonStock') or balance[4].get('weightedAverageShsOut')

                if shares_t and shares_t4 and shares_t4 > 0:
                    dilution = ((shares_t - shares_t4) / shares_t4) * 100
                    skin['net_share_issuance_12m_%'] = dilution

                    # Assessment
                    if dilution < -2:
                        skin['assessment'] = 'positive'  # Buybacks
                    elif dilution > 5:
                        skin['assessment'] = 'negative'  # Dilution
                    else:
                        skin['assessment'] = 'neutral'

        except Exception as e:
            logger.warning(f"Failed to assess dilution for {symbol}: {e}")

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
        {'switching_costs': 'Probable', 'network_effects': 'No', ...}
        -> ["✓ Switching Costs: High customer lock-in", "✗ Network Effects: Not evident"]
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
            if key == 'notes':
                continue

            label = moat_labels.get(key, key)
            desc = moat_descriptions.get(key, '')

            if value in ['Yes', 'Probable']:
                formatted.append(f"✓ {label}: {desc}")
            else:
                formatted.append(f"✗ {label}: Not evident")

        # Add summary note if available
        notes = moats_raw.get('notes', '')
        if notes:
            formatted.append(f"📝 {notes}")

        return formatted if formatted else ["No clear moats identified from business description"]

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

    def _estimate_intrinsic_value(
        self,
        symbol: str,
        company_type: str,
        peers_df: Optional[Any]
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
        valuation = {
            'current_price': None,
            'dcf_value': None,
            'forward_multiple_value': None,
            'historical_multiple_value': None,
            'weighted_value': None,
            'upside_downside_%': None,
            'valuation_assessment': 'Unknown',
            'confidence': 'Low',
            'notes': []
        }

        try:
            # Get current price
            quote = self.fmp.get_quote(symbol)
            if not quote:
                valuation['notes'].append("Price data unavailable")
                return valuation

            current_price = quote[0].get('price', 0)
            valuation['current_price'] = current_price

            if current_price <= 0:
                valuation['notes'].append("Invalid price data")
                return valuation

            # 1. DCF Valuation (simplified)
            dcf_value = self._calculate_dcf(symbol, company_type)
            if dcf_value:
                valuation['dcf_value'] = dcf_value
                valuation['confidence'] = 'Med'

            # 2. Forward Multiple Valuation
            forward_value = self._calculate_forward_multiple(symbol, company_type, peers_df)
            if forward_value:
                valuation['forward_multiple_value'] = forward_value
                valuation['confidence'] = 'High' if valuation['confidence'] == 'Med' else 'Med'

            # 3. Historical Multiple
            historical_value = self._calculate_historical_multiple(symbol, company_type)
            if historical_value:
                valuation['historical_multiple_value'] = historical_value

            # Weighted average (if we have multiple estimates)
            estimates = [v for v in [dcf_value, forward_value, historical_value] if v]

            if estimates:
                # Weight: DCF 40%, Forward 40%, Historical 20%
                weights = []
                values = []

                if dcf_value:
                    weights.append(0.4)
                    values.append(dcf_value)
                if forward_value:
                    weights.append(0.4)
                    values.append(forward_value)
                if historical_value:
                    weights.append(0.2)
                    values.append(historical_value)

                # Normalize weights
                total_weight = sum(weights)
                weights = [w / total_weight for w in weights]

                weighted = sum(v * w for v, w in zip(values, weights))
                valuation['weighted_value'] = weighted

                # Calculate upside/downside
                upside = ((weighted - current_price) / current_price) * 100
                valuation['upside_downside_%'] = upside

                # Assessment
                if upside > 25:
                    valuation['valuation_assessment'] = 'Undervalued'
                elif upside < -15:
                    valuation['valuation_assessment'] = 'Overvalued'
                else:
                    valuation['valuation_assessment'] = 'Fair Value'

                valuation['notes'].append(f"Based on {len(estimates)} valuation methods")
            else:
                valuation['notes'].append("Insufficient data for valuation")

        except Exception as e:
            logger.warning(f"Failed to estimate intrinsic value for {symbol}: {e}")
            valuation['notes'].append(f"Error: {str(e)}")

        return valuation

    def _calculate_dcf(self, symbol: str, company_type: str) -> Optional[float]:
        """
        Company-specific DCF valuation.

        Non-financial: FCF-based (adjusted for growth capex)
        Financial: Earnings-based (P/E approach)
        REIT: FFO-based

        Key: Don't penalize growth capex - it's valuable investment
        """
        try:
            # Get financials
            income = self.fmp.get_income_statement(symbol, period='annual', limit=2)
            balance = self.fmp.get_balance_sheet(symbol, period='annual', limit=1)
            cashflow = self.fmp.get_cash_flow_statement(symbol, period='annual', limit=2)

            if not (income and balance and cashflow):
                return None

            # Get shares outstanding
            shares = balance[0].get('weightedAverageShsOut') or balance[0].get('commonStock', 0)
            if shares <= 0:
                return None

            # Convert shares to millions if needed
            if shares > 1_000_000_000:
                shares = shares / 1_000_000

            # === Type-specific base cash flow ===

            if company_type == 'non_financial':
                # Use Operating Cash Flow - Maintenance Capex
                # Don't subtract growth capex!

                ocf = cashflow[0].get('operatingCashFlow', 0)
                capex = abs(cashflow[0].get('capitalExpenditure', 0))
                revenue = income[0].get('revenue', 1)
                revenue_prev = income[1].get('revenue', 1) if len(income) > 1 else revenue

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

            else:  # Financial
                # Use earnings (net income)
                base_cf = income[0].get('netIncome', 0)

            if base_cf <= 0:
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

            # === WACC ===

            if company_type == 'financial':
                wacc = 0.12  # Higher for financials
            elif company_type == 'reit':
                wacc = 0.09  # Lower for REITs (stable cash flows)
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

            return value_per_share if value_per_share > 0 else None

        except Exception as e:
            logger.warning(f"DCF calculation failed for {symbol}: {e}")
            return None

    def _calculate_forward_multiple(
        self,
        symbol: str,
        company_type: str,
        peers_df: Optional[Any]
    ) -> Optional[float]:
        """
        Value using forward multiples vs peers.

        For non-financial: Prefer EV/EBIT (more robust than P/E)
        For financial: Use P/E
        For REIT: Use P/FFO
        """
        try:
            income = self.fmp.get_income_statement(symbol, period='annual', limit=2)
            balance = self.fmp.get_balance_sheet(symbol, period='annual', limit=1)
            cashflow = self.fmp.get_cash_flow_statement(symbol, period='annual', limit=1)

            if not (income and balance):
                return None

            shares = balance[0].get('weightedAverageShsOut') or balance[0].get('commonStock', 0)
            if shares <= 0:
                return None

            # Convert shares if needed
            if shares > 1_000_000_000:
                shares = shares / 1_000_000

            # === Get peer multiples ===

            peer_multiple = None
            metric_name = ''

            if company_type == 'non_financial':
                # Use EV/EBIT (better for capital-intensive businesses)

                ebit_ttm = income[0].get('ebitda', 0) - abs(income[0].get('depreciationAndAmortization', 0))

                # Estimate forward EBIT (with growth)
                if len(income) > 1:
                    revenue_growth = (income[0].get('revenue', 0) - income[1].get('revenue', 1)) / income[1].get('revenue', 1)
                    growth_rate = max(0, min(revenue_growth, 0.20))  # Cap at 20%
                else:
                    growth_rate = 0.08

                ebit_forward = ebit_ttm * (1 + growth_rate)

                if ebit_forward <= 0:
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

            else:  # Financial
                # Use P/B (Price to Book) for financials instead of P/E

                book_value = balance[0].get('totalStockholdersEquity', 0)
                shares_ttm = balance[0].get('weightedAverageShsOut') or balance[0].get('commonStock', 0)

                if shares_ttm <= 0 or book_value <= 0:
                    return None

                # Convert shares if needed
                if shares_ttm > 1_000_000_000:
                    shares_ttm = shares_ttm / 1_000_000

                book_per_share = book_value / shares_ttm

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
                                if pb and pb > 0 and pb < 3:  # Sanity check for financials
                                    peer_pbs.append(pb)

                        if peer_pbs:
                            peer_pb = sum(peer_pbs) / len(peer_pbs)

                # Fallback: sector average P/B for financials
                if not peer_pb:
                    peer_pb = 1.2  # P/B ~1.2x for financials

                fair_value = book_per_share * peer_pb

                return fair_value if fair_value > 0 else None

        except Exception as e:
            logger.warning(f"Forward multiple calculation failed for {symbol}: {e}")
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
            cashflow = self.fmp.get_cash_flow_statement(symbol, period='annual', limit=3)

            if not (income and balance):
                return None

            shares = balance[0].get('weightedAverageShsOut') or balance[0].get('commonStock', 0)
            if shares <= 0:
                return None

            # Convert shares if needed
            if shares > 1_000_000_000:
                shares = shares / 1_000_000

            if company_type == 'non_financial':
                # Use current EBIT with historical average EV/EBIT (10-12x)
                ebit_ttm = income[0].get('ebitda', 0) - abs(income[0].get('depreciationAndAmortization', 0))

                if ebit_ttm <= 0:
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
