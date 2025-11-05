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
            'moats': {},
            'skin_in_the_game': {},
            'news_TLDR': [],
            'news_tags': [],
            'pr_highlights': [],
            'transcript_TLDR': {},
            'mna_recent': [],
            'top_risks': []
        }

        try:
            # 1. Business description
            summary['business_summary'] = self._get_business_summary(symbol)

            # 2. Peers & competitive position
            summary['peers_list'], summary['peer_snapshot'] = self._get_peer_analysis(
                symbol, company_type, peers_df
            )

            # 3. Moats (competitive advantages)
            summary['moats'] = self._assess_moats(
                symbol,
                summary['business_summary'],
                summary['peer_snapshot']
            )

            # 4. Skin in the game (insiders & dilution)
            summary['skin_in_the_game'] = self._assess_skin_in_game(symbol)

            # 5. News & PR (last 60-90 days)
            summary['news_TLDR'], summary['news_tags'] = self._summarize_news(symbol, days=90)
            summary['pr_highlights'] = self._summarize_press_releases(symbol, days=90)

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
