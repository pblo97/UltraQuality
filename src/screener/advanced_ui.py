"""
Advanced UI components for Streamlit.

Integrates:
- Price levels visualization
- Backtesting results
- Options P&L calculator
- Market timing dashboard
- Portfolio tracker
"""

import streamlit as st
import pandas as pd
from typing import Dict, List, Optional
try:
    from .visualization import (
        create_price_levels_chart,
        create_overextension_gauge,
        create_risk_reward_chart,
        create_sector_comparison_chart
    )
    from .backtesting import OverextensionBacktester
    from .options_calculator import OptionsCalculator
    from .market_timing import MarketTimingAnalyzer
    from .portfolio import PortfolioTracker
except ImportError:
    # Fallback for direct execution
    from visualization import (
        create_price_levels_chart,
        create_overextension_gauge,
        create_risk_reward_chart,
        create_sector_comparison_chart
    )
    from backtesting import OverextensionBacktester
    from options_calculator import OptionsCalculator
    from market_timing import MarketTimingAnalyzer
    from portfolio import PortfolioTracker


def render_price_levels_chart(
    symbol: str,
    fmp_client,
    full_analysis: Dict,
    historical_prices: Optional[List[Dict]] = None
):
    """
    Render interactive price levels chart.

    Args:
        symbol: Stock symbol
        fmp_client: FMP client for fetching quote data
        full_analysis: Technical analysis results
        historical_prices: Optional historical price data
    """
    # Fetch current quote
    try:
        quote = fmp_client.get_quote(symbol)  # Pass string, not list
        if not quote or len(quote) == 0:
            st.warning("No current price data available")
            return

        q = quote[0]
        current_price = q.get('price', 0)
        ma_50 = q.get('priceAvg50', 0)
        ma_200 = q.get('priceAvg200', 0)
    except Exception as e:
        st.error(f"Error fetching quote: {e}")
        return

    risk_management = full_analysis.get('risk_management', {})
    overextension_risk = full_analysis.get('overextension_risk', 0)
    distance_ma200 = full_analysis.get('distance_from_ma200', 0)

    # Validate we have minimum required data
    if not current_price or current_price == 0:
        st.warning("No current price data available")
        return

    if not ma_200 or ma_200 == 0:
        st.info("MA200 not available - fetching historical data...")
        # MA200 will be calculated from historical prices if available
        if not historical_prices or len(historical_prices) < 200:
            st.warning("Insufficient historical data (need 200+ days for MA200)")
            return

    fig = create_price_levels_chart(
        symbol=symbol,
        current_price=current_price,
        ma_50=ma_50,
        ma_200=ma_200,
        risk_management=risk_management,
        overextension_risk=overextension_risk,
        distance_ma200=distance_ma200,
        historical_prices=historical_prices
    )

    # Render chart with professional styling
    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            'displayModeBar': True,
            'displaylogo': False,
            'modeBarButtonsToRemove': ['select2d', 'lasso2d'],
            'toImageButtonOptions': {
                'format': 'png',
                'filename': f'{symbol}_price_levels',
                'height': 600,
                'width': 1200,
                'scale': 2
            }
        }
    )


def render_overextension_gauge(full_analysis: Dict):
    """Render overextension risk gauge."""
    overextension_risk = full_analysis.get('overextension_risk', 0)
    overextension_level = full_analysis.get('overextension_level', 'LOW')
    distance_ma200 = full_analysis.get('distance_from_ma200', 0)

    fig = create_overextension_gauge(
        overextension_risk=overextension_risk,
        overextension_level=overextension_level,
        distance_ma200=distance_ma200
    )

    # Render gauge with professional styling
    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            'displayModeBar': False,
            'staticPlot': False
        }
    )

    # Add interpretation card below gauge
    if overextension_risk >= 5:
        risk_color = '#dc3545'
        risk_bg = '#fff5f5'
        risk_message = 'EXTREME RISK - Consider waiting for pullback'
    elif overextension_risk >= 3:
        risk_color = '#ffc107'
        risk_bg = '#fffbf0'
        risk_message = 'ELEVATED RISK - Use caution, scale-in recommended'
    else:
        risk_color = '#28a745'
        risk_bg = '#d4edda'
        risk_message = 'HEALTHY RANGE - Normal entry acceptable'

    st.markdown(f"""
    <div style='background: {risk_bg}; padding: 1rem; border-radius: 8px;
                border-left: 4px solid {risk_color}; margin-top: 1rem;'>
        <div style='color: {risk_color}; font-weight: 600; font-size: 0.95rem;'>
            {risk_message}
        </div>
        <div style='color: #495057; font-size: 0.85rem; margin-top: 0.5rem;'>
            Distance from MA200: {distance_ma200:+.1f}%
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_backtesting_section(symbol: str, fmp_client):
    """Render backtesting analysis section."""
    st.markdown("### Historical Overextension Analysis")

    with st.expander("What is this?", expanded=False):
        st.markdown("""
        Analyzes all past instances when this stock was overextended (>40% above MA200).
        Shows:
        - How often corrections happened
        - Average correction magnitude
        - Time to correction
        - Scale-in strategy performance vs full entry

        **Uses 2 years of historical data**
        """)

    if st.button(f"Run Backtest for {symbol}", key=f"backtest_{symbol}"):
        with st.spinner("Analyzing historical data..."):
            backtester = OverextensionBacktester(fmp_client)

            # Historical overextensions
            hist_results = backtester.analyze_historical_overextensions(symbol)

            if 'error' in hist_results:
                st.error(f"Error: {hist_results['error']}")
                return

            if hist_results.get('instances', 0) == 0:
                st.info(hist_results.get('message', 'No overextension instances found'))
                return

            # Display results
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric(
                    "Instances Found",
                    hist_results['instances'],
                    help="Times stock was >40% above MA200"
                )

            with col2:
                st.metric(
                    "Avg Correction",
                    f"{hist_results['avg_correction_pct']:.1f}%",
                    help="Average pullback from overextended peak"
                )

            with col3:
                st.metric(
                    "Max Correction",
                    f"{hist_results['max_correction_pct']:.1f}%",
                    help="Largest pullback observed"
                )

            with col4:
                days = hist_results.get('avg_days_to_correction')
                if days:
                    st.metric(
                        "Avg Days to Correct",
                        days,
                        help="Average time to correction"
                    )
                else:
                    st.metric("Correction Rate", f"{hist_results['correction_rate']*100:.0f}%")

            # Show details
            if 'details' in hist_results and hist_results['details']:
                st.markdown("#### Recent Overextension Events")
                details_df = pd.DataFrame(hist_results['details'])
                st.dataframe(
                    details_df[['date', 'price', 'distance_pct', 'correction_pct', 'days_to_correction']],
                    use_container_width=True
                )


def render_options_calculator(symbol: str, fmp_client, full_analysis: Dict):
    """Render options P&L calculator."""
    st.markdown("### Options Strategy Calculator")

    # Fetch current quote
    try:
        quote = fmp_client.get_quote(symbol)  # Pass string, not list
        if not quote or len(quote) == 0:
            st.warning("⚠️ No current price data available")
            return

        current_price = quote[0].get('price', 0)
        if not current_price or current_price == 0:
            st.warning("⚠️ No valid price data")
            return
    except Exception as e:
        st.error(f"Error fetching quote: {e}")
        return

    volatility = full_analysis.get('volatility_12m', 30) / 100  # Convert to decimal

    # Ensure volatility is valid (avoid division by zero)
    if volatility == 0:
        volatility = 0.30  # Default to 30% if not available

    calc = OptionsCalculator()

    # Strategy selector
    strategy = st.selectbox(
        "Select Strategy",
        [
            "Covered Call",
            "Protective Put",
            "Collar",
            "Cash-Secured Put",
            "Bull Put Spread"
        ]
    )

    col1, col2 = st.columns(2)

    with col1:
        days_to_expiry = st.slider("Days to Expiration", 7, 180, 45)

    with col2:
        vol_input = st.slider("Implied Volatility %", 10, 100, int(volatility*100))
        volatility = vol_input / 100

    if strategy == "Covered Call":
        strike_pct = st.slider("Strike (% OTM)", 0, 20, 7)
        strike = current_price * (1 + strike_pct/100)

        result = calc.covered_call_analysis(
            stock_price=current_price,
            strike=strike,
            days_to_expiry=days_to_expiry,
            volatility=volatility
        )

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Premium Collected", f"${result['premium']:.2f}")
            st.caption(f"{result['premium_pct']:.1f}% of stock price")
        with col2:
            st.metric("Max Profit", f"${result['max_profit']:.2f}")
            st.caption(f"{result['max_profit_pct']:.1f}% return")
        with col3:
            st.metric("Annualized Return", f"{result['annualized_return']:.0f}%")
            st.caption(f"Probability: {result['probability_profit']:.0f}%")

        st.info(f"**Break-even:** ${result['break_even']:.2f} (downside protection)")

        # Greeks
        greeks = result['greeks']
        st.markdown("**Greeks:**")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Delta", f"{greeks['delta']:.3f}")
        with col2:
            st.metric("Theta", f"{greeks['theta']:.3f}")
        with col3:
            st.metric("Vega", f"{greeks['vega']:.3f}")
        with col4:
            st.metric("Gamma", f"{greeks['gamma']:.4f}")

    elif strategy == "Protective Put":
        strike_pct = st.slider("Strike (% OTM)", 5, 20, 10)
        strike = current_price * (1 - strike_pct/100)

        result = calc.protective_put_analysis(
            stock_price=current_price,
            strike=strike,
            days_to_expiry=days_to_expiry,
            volatility=volatility
        )

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Premium Cost", f"${result['premium_cost']:.2f}")
            st.caption(f"{result['cost_pct']:.1f}% of stock price")
        with col2:
            st.metric("Max Loss", f"${result['max_loss']:.2f}")
            st.caption(f"{result['max_loss_pct']:.1f}%")
        with col3:
            st.metric("Protection Level", f"{result['protection_level']:.0f}%")

        st.info(f"**Annualized Cost:** {result['annualized_cost']:.1f}%")

    elif strategy == "Cash-Secured Put":
        strike_pct = st.slider("Strike (% OTM)", 5, 15, 8)
        strike = current_price * (1 - strike_pct/100)

        result = calc.cash_secured_put_analysis(
            stock_price=current_price,
            strike=strike,
            days_to_expiry=days_to_expiry,
            volatility=volatility
        )

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Premium Credit", f"${result['premium_credit']:.2f}")
            st.caption(f"{result['premium_pct']:.1f}% return on capital")
        with col2:
            st.metric("Effective Entry", f"${result['effective_entry']:.2f}")
            st.caption(f"{result['discount_pct']:.0f}% discount")
        with col3:
            st.metric("Annualized Return", f"{result['annualized_return']:.0f}%")
            st.caption(f"Probability: {result['probability_profit']:.0f}%")


def render_market_timing_dashboard(fmp_client, top_stocks: List[str] = None):
    """Render market timing dashboard."""
    st.markdown("### Market Timing Dashboard")

    with st.expander("📚 What is this?", expanded=False):
        st.markdown("""
        Macro market analysis for timing decisions:
        - % of stocks overextended (correction risk)
        - Sector overextension breakdown
        - VIX (fear/greed indicator)
        - Market breadth
        - Overall recommendation
        """)

    if st.button("Analyze Market Conditions"):
        with st.spinner("Analyzing market..."):
            analyzer = MarketTimingAnalyzer(fmp_client)

            analysis = analyzer.get_comprehensive_market_analysis(top_stocks)

            # SPY
            if 'spy' in analysis:
                spy = analysis['spy']
                st.markdown("#### 📊 SPY (Market Index)")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Price", f"${spy['price']:.2f}")
                with col2:
                    st.metric("MA200", f"${spy['ma_200']:.2f}")
                with col3:
                    dist = spy['distance_ma200']
                    st.metric("Distance from MA200", f"{dist:+.1f}%", delta=dist)

            # VIX
            if 'vix' in analysis and 'error' not in analysis['vix']:
                vix = analysis['vix']
                st.markdown("#### 😱 VIX (Volatility Index)")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("VIX", f"{vix['vix']:.1f}", help="Volatility Index")
                with col2:
                    st.metric("Level", vix['level'], help=vix['market_sentiment'])
                st.info(vix['recommendation'])

            # Breadth
            if 'breadth' in analysis and 'error' not in analysis['breadth']:
                breadth = analysis['breadth']
                st.markdown("#### 📈 Market Breadth")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric(
                        "Sectors Above MA200",
                        f"{breadth['sectors_above_ma200']}/{breadth['sectors_total']}"
                    )
                with col2:
                    st.metric("Breadth %", f"{breadth['breadth_pct']:.0f}%")
                st.info(breadth['message'])

            # Overall recommendation
            if 'overall_recommendation' in analysis:
                rec = analysis['overall_recommendation']
                st.markdown("#### 🎯 Overall Recommendation")

                stance_colors = {
                    'DEFENSIVE': '🔴',
                    'CAUTIOUS': '🟡',
                    'NEUTRAL': '🟢',
                    'BULLISH': '🟢'
                }
                icon = stance_colors.get(rec['stance'], '⚪')

                st.markdown(f"### {icon} {rec['stance']} ({rec['confidence']} confidence)")
                st.markdown(f"**Risk Score:** {rec['risk_score']}/10")
                st.markdown(f"**Action:** {rec['action']}")

                if rec.get('key_factors'):
                    st.markdown("**Key Factors:**")
                    for factor in rec['key_factors']:
                        st.markdown(f"- {factor}")


def render_portfolio_tracker(fmp_client):
    """Render portfolio tracking interface."""
    st.markdown("### Portfolio Tracker")

    tracker = PortfolioTracker()

    # Tabs for different portfolio functions
    tab1, tab2, tab3 = st.tabs(["📊 Overview", "➕ Add Position", "🚨 Alerts"])

    with tab1:
        positions = tracker.get_all_positions()

        if not positions:
            st.info("No positions tracked. Add a position using the 'Add Position' tab.")
        else:
            # Get current prices
            current_prices = {}
            for symbol in positions.keys():
                try:
                    quote = fmp_client.get_quote(symbol)
                    if quote and len(quote) > 0:
                        current_prices[symbol] = quote[0].get('price', 0)
                except:
                    current_prices[symbol] = positions[symbol]['entry_price']

            # Get summary
            summary = tracker.get_portfolio_summary(current_prices)

            # Display summary metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Value", f"${summary['total_value']:,.2f}")
            with col2:
                st.metric("Total Cost", f"${summary['total_cost']:,.2f}")
            with col3:
                pnl = summary['total_pnl']
                st.metric("P&L", f"${pnl:,.2f}", delta=pnl)
            with col4:
                pnl_pct = summary['total_pnl_pct']
                st.metric("P&L %", f"{pnl_pct:+.1f}%", delta=pnl_pct)

            # Display positions
            st.markdown("#### Positions")
            positions_df = pd.DataFrame(summary['positions'])
            st.dataframe(
                positions_df[[
                    'symbol', 'quantity', 'entry_price', 'current_price',
                    'value', 'pnl', 'pnl_pct', 'tranches'
                ]].style.format({
                    'entry_price': '${:.2f}',
                    'current_price': '${:.2f}',
                    'value': '${:,.2f}',
                    'pnl': '${:,.2f}',
                    'pnl_pct': '{:+.1f}%'
                }),
                use_container_width=True
            )

    with tab2:
        st.markdown("#### Add New Position")

        col1, col2 = st.columns(2)
        with col1:
            new_symbol = st.text_input("Symbol", "AAPL").upper()
            new_quantity = st.number_input("Quantity", min_value=1, value=100)
        with col2:
            new_price = st.number_input("Entry Price", min_value=0.01, value=100.0)
            new_notes = st.text_input("Notes (optional)", "")

        if st.button("Add Position"):
            tracker.add_position(
                symbol=new_symbol,
                entry_price=new_price,
                quantity=new_quantity,
                notes=new_notes
            )
            st.success(f"✅ Added {new_quantity} shares of {new_symbol} at ${new_price:.2f}")
            st.rerun()

    with tab3:
        st.markdown("#### Position Alerts")

        if not positions:
            st.info("No positions to monitor")
        else:
            # For each position, generate alerts
            for symbol in positions.keys():
                try:
                    # Get current data
                    quote = fmp_client.get_quote(symbol)
                    if not quote or len(quote) == 0:
                        continue

                    q = quote[0]
                    current_price = q.get('price', 0)
                    ma_50 = q.get('priceAvg50', 0)
                    ma_200 = q.get('priceAvg200', 0)

                    # Need to run technical analysis to get risk management
                    # For now, show basic alerts
                    position = positions[symbol]
                    entry_price = position['entry_price']
                    pnl_pct = ((current_price - entry_price) / entry_price * 100)

                    st.markdown(f"**{symbol}** (${current_price:.2f}, {pnl_pct:+.1f}%)")

                    # Simple alerts
                    if pnl_pct >= 20:
                        st.success(f"💰 Up {pnl_pct:+.1f}%! Consider taking profits")
                    elif pnl_pct <= -10:
                        st.error(f"🔴 Down {pnl_pct:.1f}%! Review stop loss")

                    if ma_50 > 0 and abs(current_price - ma_50) / ma_50 < 0.02:
                        st.info(f"🎯 Near MA50 (${ma_50:.2f}) - potential scale-in opportunity")

                except Exception as e:
                    st.error(f"Error analyzing {symbol}: {e}")


def render_institutional_holders(symbol: str, fmp_client):
    """
    Render institutional holders section with top holders and ownership breakdown.
    
    Args:
        symbol: Stock symbol
        fmp_client: FMP client instance
    """
    import pandas as pd
    from datetime import datetime
    
    try:
        holders_data = fmp_client.get_institutional_holders(symbol)
        
        if not holders_data or len(holders_data) == 0:
            st.info("No institutional holder data available for this symbol")
            return
        
        # Header
        st.markdown("""
        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 1.5rem; border-radius: 12px; margin-bottom: 1.5rem;'>
            <div style='color: white; text-align: center;'>
                <div style='font-size: 2rem; margin-bottom: 0.5rem;'>
                    <i class="bi bi-building"></i>
                </div>
                <div style='font-size: 1.5rem; font-weight: 700;'>
                    Institutional Holders
                </div>
                <div style='font-size: 0.9rem; opacity: 0.95; margin-top: 0.5rem;'>
                    Major institutional positions & ownership changes
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Calculate total institutional ownership
        total_shares = sum([h.get('shares', 0) for h in holders_data[:50]])  # Top 50
        
        # Create DataFrame for display
        df_holders = pd.DataFrame(holders_data[:15])  # Top 15 holders
        
        # Key metrics row
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "Total Holders",
                f"{len(holders_data):,}",
                help="Number of institutional holders"
            )
        
        with col2:
            if 'shares' in df_holders.columns:
                avg_position = df_holders['shares'].mean()
                st.metric(
                    "Avg Position (Top 15)",
                    f"{avg_position:,.0f}",
                    help="Average shares held by top 15 institutions"
                )
        
        with col3:
            # Latest filing date
            if 'date' in df_holders.columns or 'dateReported' in df_holders.columns:
                date_col = 'dateReported' if 'dateReported' in df_holders.columns else 'date'
                latest_date = df_holders[date_col].iloc[0] if len(df_holders) > 0 else "N/A"
                st.metric(
                    "Latest Filing",
                    str(latest_date)[:10] if latest_date != "N/A" else "N/A",
                    help="Most recent filing date"
                )
        
        # Top holders table
        st.markdown("### Top 15 Institutional Holders")
        
        # Prepare display columns
        display_cols = []
        rename_map = {}
        
        if 'holder' in df_holders.columns:
            display_cols.append('holder')
            rename_map['holder'] = 'Institution'
        elif 'name' in df_holders.columns:
            display_cols.append('name')
            rename_map['name'] = 'Institution'
        
        if 'shares' in df_holders.columns:
            display_cols.append('shares')
            rename_map['shares'] = 'Shares'
        
        if 'value' in df_holders.columns:
            display_cols.append('value')
            rename_map['value'] = 'Value ($)'
        
        if 'change' in df_holders.columns:
            display_cols.append('change')
            rename_map['change'] = 'Change'
        elif 'sharesChange' in df_holders.columns:
            display_cols.append('sharesChange')
            rename_map['sharesChange'] = 'Change'
        
        if 'percentOfPortfolio' in df_holders.columns:
            display_cols.append('percentOfPortfolio')
            rename_map['percentOfPortfolio'] = '% of Portfolio'
        
        if display_cols:
            df_display = df_holders[display_cols].copy()
            df_display = df_display.rename(columns=rename_map)
            
            # Format numbers
            if 'Shares' in df_display.columns:
                df_display['Shares'] = df_display['Shares'].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "N/A")
            if 'Value ($)' in df_display.columns:
                df_display['Value ($)'] = df_display['Value ($)'].apply(lambda x: f"${x:,.0f}" if pd.notna(x) else "N/A")
            if 'Change' in df_display.columns:
                df_display['Change'] = df_display['Change'].apply(lambda x: f"{x:+,.0f}" if pd.notna(x) else "0")
            if '% of Portfolio' in df_display.columns:
                df_display['% of Portfolio'] = df_display['% of Portfolio'].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "N/A")
            
            st.dataframe(
                df_display,
                use_container_width=True,
                hide_index=True
            )
        
        # Analysis section
        with st.expander("Ownership Analysis", expanded=False):
            st.markdown("""
            ### What This Means
            
            **High Institutional Ownership (>70%):**
            - Generally positive signal for large caps
            - Indicates professional money managers see value
            - Can provide price stability
            - May have less volatility
            
            **Low Institutional Ownership (<30%):**
            - Common in small caps
            - Can indicate undiscovered opportunities
            - May have higher volatility
            - Less analyst coverage typically
            
            **Recent Increases in Holdings:**
            - Bullish signal - institutions adding positions
            - Check if it's widespread or concentrated
            
            **Recent Decreases:**
            - Bearish signal - institutions reducing exposure
            - Investigate reasons (sector rotation, fundamentals, etc.)
            """)
    
    except Exception as e:
        st.error(f"Error loading institutional holder data: {e}")
        st.caption("This feature requires a valid FMP API key with access to institutional holder data")


def render_earnings_calendar_section(symbol: str, fmp_client):
    """
    Render earnings calendar with upcoming and past earnings dates.
    
    Args:
        symbol: Stock symbol
        fmp_client: FMP client instance
    """
    from datetime import datetime, timedelta
    import pandas as pd
    
    st.markdown("""
    <div style='background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
                padding: 1.5rem; border-radius: 12px; margin-bottom: 1.5rem;'>
        <div style='color: white; text-align: center;'>
            <div style='font-size: 2rem; margin-bottom: 0.5rem;'>
                <i class="bi bi-calendar-event"></i>
            </div>
            <div style='font-size: 1.5rem; font-weight: 700;'>
                Earnings Calendar
            </div>
            <div style='font-size: 0.9rem; opacity: 0.95; margin-top: 0.5rem;'>
                Upcoming and historical earnings announcement dates
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    try:
        # Get upcoming earnings (next 3 months)
        today = datetime.now()
        three_months = today + timedelta(days=90)
        
        from_date = today.strftime('%Y-%m-%d')
        to_date = three_months.strftime('%Y-%m-%d')
        
        calendar = fmp_client.get_earnings_calendar(from_date=from_date, to_date=to_date)
        
        if not calendar:
            st.info("No upcoming earnings data available")
            
            # Try to show from profile
            profile = fmp_client.get_profile(symbol)
            if profile and len(profile) > 0:
                earnings_date_str = profile[0].get('earningsAnnouncement', None)
                if earnings_date_str:
                    st.markdown(f"""
                    <div style='background: #e7f3ff; padding: 1rem; border-radius: 8px;
                                border-left: 4px solid #2196f3;'>
                        <strong>Next Earnings:</strong> {earnings_date_str[:10]}
                    </div>
                    """, unsafe_allow_html=True)
            return
        
        # Filter for this symbol
        symbol_earnings = [e for e in calendar if e.get('symbol', '').upper() == symbol.upper()]
        
        if not symbol_earnings:
            st.info(f"No upcoming earnings found for {symbol} in the next 3 months")
            return
        
        # Create DataFrame
        df_earnings = pd.DataFrame(symbol_earnings)
        
        # Show next earning date prominently
        next_earning = symbol_earnings[0]
        earning_date_str = next_earning.get('date', 'N/A')
        
        if earning_date_str != 'N/A':
            try:
                earning_date = datetime.strptime(earning_date_str, '%Y-%m-%d')
                days_until = (earning_date - today).days
                
                # Color based on proximity
                if days_until <= 5:
                    color = '#dc3545'
                    bg_color = '#fff5f5'
                    urgency = "IMMINENT"
                elif days_until <= 14:
                    color = '#ffc107'
                    bg_color = '#fffbf0'
                    urgency = "UPCOMING"
                else:
                    color = '#28a745'
                    bg_color = '#d4edda'
                    urgency = "SCHEDULED"
                
                st.markdown(f"""
                <div style='background: {bg_color}; padding: 1.5rem; border-radius: 12px;
                            border-left: 5px solid {color}; margin-bottom: 1.5rem;'>
                    <div style='display: flex; justify-content: space-between; align-items: center;'>
                        <div>
                            <div style='font-size: 0.9rem; color: {color}; font-weight: 600;'>{urgency}</div>
                            <div style='font-size: 1.5rem; font-weight: 700; color: #495057; margin-top: 0.25rem;'>
                                {earning_date.strftime('%B %d, %Y')}
                            </div>
                            <div style='font-size: 0.9rem; color: #6c757d; margin-top: 0.25rem;'>
                                {next_earning.get('time', 'Time TBA')}
                            </div>
                        </div>
                        <div style='text-align: right;'>
                            <div style='font-size: 2.5rem; font-weight: 700; color: {color};'>
                                {days_until}
                            </div>
                            <div style='font-size: 0.9rem; color: #6c757d;'>
                                days away
                            </div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Warning if imminent
                if days_until <= 5:
                    st.warning("⚠️ **Earnings within 5 days** - High volatility expected. Consider waiting to enter new positions.")
                
            except ValueError:
                st.info(f"Next Earnings: {earning_date_str}")
        
        # Show all upcoming earnings
        if len(symbol_earnings) > 1:
            with st.expander(f"All Upcoming Earnings ({len(symbol_earnings)} scheduled)"):
                # Prepare display
                display_cols = []
                if 'date' in df_earnings.columns:
                    display_cols.append('date')
                if 'time' in df_earnings.columns:
                    display_cols.append('time')
                if 'fiscalQuarter' in df_earnings.columns:
                    display_cols.append('fiscalQuarter')
                if 'fiscalYear' in df_earnings.columns:
                    display_cols.append('fiscalYear')
                if 'epsEstimate' in df_earnings.columns:
                    display_cols.append('epsEstimate')
                if 'revenueEstimate' in df_earnings.columns:
                    display_cols.append('revenueEstimate')
                
                if display_cols:
                    df_display = df_earnings[display_cols].copy()
                    df_display = df_display.rename(columns={
                        'date': 'Date',
                        'time': 'Time',
                        'fiscalQuarter': 'Fiscal Q',
                        'fiscalYear': 'Year',
                        'epsEstimate': 'EPS Est.',
                        'revenueEstimate': 'Revenue Est.'
                    })
                    
                    st.dataframe(df_display, use_container_width=True, hide_index=True)
    
    except Exception as e:
        st.error(f"Error loading earnings calendar: {e}")
        st.caption("Trying to get earnings date from profile...")
        
        # Fallback to profile data
        try:
            profile = fmp_client.get_profile(symbol)
            if profile and len(profile) > 0:
                earnings_date_str = profile[0].get('earningsAnnouncement', None)
                if earnings_date_str:
                    st.markdown(f"""
                    <div style='background: #e7f3ff; padding: 1rem; border-radius: 8px;
                                border-left: 4px solid #2196f3;'>
                        <strong>Next Earnings:</strong> {earnings_date_str[:10]}
                    </div>
                    """, unsafe_allow_html=True)
        except:
            pass
