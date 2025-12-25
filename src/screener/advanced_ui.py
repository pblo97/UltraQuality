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
            st.warning("△ No current price data available")
            return

        current_price = quote[0].get('price', 0)
        if not current_price or current_price == 0:
            st.warning("△ No valid price data")
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

    with st.expander("What is this?", expanded=False):
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
                st.markdown("#### SPY (Market Index)")
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
                st.markdown("#### VIX (Volatility Index)")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("VIX", f"{vix['vix']:.1f}", help="Volatility Index")
                with col2:
                    st.metric("Level", vix['level'], help=vix['market_sentiment'])
                st.info(vix['recommendation'])

            # Breadth
            if 'breadth' in analysis and 'error' not in analysis['breadth']:
                breadth = analysis['breadth']
                st.markdown("#### Market Breadth")
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
                st.markdown("#### Overall Recommendation")

                stance_colors = {
                    'DEFENSIVE': '',
                    'CAUTIOUS': '',
                    'NEUTRAL': '',
                    'BULLISH': ''
                }
                icon = stance_colors.get(rec['stance'], '')

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
    tab1, tab2, tab3 = st.tabs(["Overview", "Add Position", "□ Alerts"])

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
            st.success(f"• Added {new_quantity} shares of {new_symbol} at ${new_price:.2f}")
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
                        st.success(f"Up {pnl_pct:+.1f}%! Consider taking profits")
                    elif pnl_pct <= -10:
                        st.error(f" Down {pnl_pct:.1f}%! Review stop loss")

                    if ma_50 > 0 and abs(current_price - ma_50) / ma_50 < 0.02:
                        st.info(f"Near MA50 (${ma_50:.2f}) - potential scale-in opportunity")

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

        # === BALANCE DE COMPRA/VENTA INSTITUCIONAL ===
        st.markdown("---")
        st.markdown("### Balance de Actividad Institucional")
        st.caption("Resumen de cambios en posiciones institucionales (basado en últimos reportes)")

        # Determine which column has the change data
        change_col = None
        if 'change' in df_holders.columns:
            change_col = 'change'
        elif 'sharesChange' in df_holders.columns:
            change_col = 'sharesChange'

        if change_col:
            # Calculate buying/selling metrics
            df_all = pd.DataFrame(holders_data)  # Use all holders, not just top 15

            if change_col in df_all.columns:
                # Clean data
                df_all[change_col] = pd.to_numeric(df_all[change_col], errors='coerce').fillna(0)

                # Separate buyers and sellers
                buying = df_all[df_all[change_col] > 0]
                selling = df_all[df_all[change_col] < 0]

                total_bought = buying[change_col].sum()
                total_sold = abs(selling[change_col].sum())
                net_flow = total_bought - total_sold
                num_buyers = len(buying)
                num_sellers = len(selling)

                # Display metrics with custom colors
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    # Compradores - verde
                    st.markdown(f"""
                    <div style='background: #f0fdf4; padding: 1rem; border-radius: 8px; border: 1px solid #86efac;'>
                        <div style='color: #6b7280; font-size: 0.875rem; margin-bottom: 0.25rem;'>Compradores</div>
                        <div style='color: #10b981; font-size: 1.875rem; font-weight: 700;'>{num_buyers:,}</div>
                        <div style='color: #10b981; font-size: 0.875rem; margin-top: 0.25rem;'>+{total_bought:,.0f} acciones</div>
                    </div>
                    """, unsafe_allow_html=True)

                with col2:
                    # Vendedores - rojo
                    st.markdown(f"""
                    <div style='background: #fef2f2; padding: 1rem; border-radius: 8px; border: 1px solid #fca5a5;'>
                        <div style='color: #6b7280; font-size: 0.875rem; margin-bottom: 0.25rem;'>Vendedores</div>
                        <div style='color: #ef4444; font-size: 1.875rem; font-weight: 700;'>{num_sellers:,}</div>
                        <div style='color: #ef4444; font-size: 0.875rem; margin-top: 0.25rem;'>-{total_sold:,.0f} acciones</div>
                    </div>
                    """, unsafe_allow_html=True)

                with col3:
                    # Balance Neto - color según signo
                    if net_flow > 0:
                        bg_color = "#f0fdf4"
                        border_color = "#86efac"
                        text_color = "#10b981"
                        label = "Acumulación"
                    elif net_flow < 0:
                        bg_color = "#fef2f2"
                        border_color = "#fca5a5"
                        text_color = "#ef4444"
                        label = "Distribución"
                    else:
                        bg_color = "#f9fafb"
                        border_color = "#d1d5db"
                        text_color = "#6b7280"
                        label = "Neutral"

                    st.markdown(f"""
                    <div style='background: {bg_color}; padding: 1rem; border-radius: 8px; border: 1px solid {border_color};'>
                        <div style='color: #6b7280; font-size: 0.875rem; margin-bottom: 0.25rem;'>Balance Neto</div>
                        <div style='color: {text_color}; font-size: 1.875rem; font-weight: 700;'>{net_flow:+,}</div>
                        <div style='color: {text_color}; font-size: 0.875rem; margin-top: 0.25rem;'>{label}</div>
                    </div>
                    """, unsafe_allow_html=True)

                with col4:
                    if num_buyers + num_sellers > 0:
                        buy_ratio = (num_buyers / (num_buyers + num_sellers)) * 100

                        if buy_ratio > 50:
                            bg_color = "#f0fdf4"
                            border_color = "#86efac"
                            text_color = "#10b981"
                            label = "Positivo"
                        elif buy_ratio < 50:
                            bg_color = "#fef2f2"
                            border_color = "#fca5a5"
                            text_color = "#ef4444"
                            label = "Negativo"
                        else:
                            bg_color = "#f9fafb"
                            border_color = "#d1d5db"
                            text_color = "#6b7280"
                            label = "Neutral"

                        st.markdown(f"""
                        <div style='background: {bg_color}; padding: 1rem; border-radius: 8px; border: 1px solid {border_color};'>
                            <div style='color: #6b7280; font-size: 0.875rem; margin-bottom: 0.25rem;'>Ratio Compra/Venta</div>
                            <div style='color: {text_color}; font-size: 1.875rem; font-weight: 700;'>{buy_ratio:.1f}% / {100-buy_ratio:.1f}%</div>
                            <div style='color: {text_color}; font-size: 0.875rem; margin-top: 0.25rem;'>{label}</div>
                        </div>
                        """, unsafe_allow_html=True)

                # Summary message
                if net_flow > 0:
                    sentiment = "POSITIVO"
                    emoji = ""
                    color = "#10b981"
                elif net_flow < 0:
                    sentiment = "NEGATIVO"
                    emoji = ""
                    color = "#ef4444"
                else:
                    sentiment = "NEUTRAL"
                    emoji = ""
                    color = "#6b7280"

                st.markdown(f"""
                <div style='background: {color}15; padding: 1rem; border-radius: 8px;
                            border-left: 4px solid {color}; margin-top: 1rem;'>
                    <strong style='color: {color};'>{emoji} Sentimiento Institucional: {sentiment}</strong><br>
                    <span style='font-size: 0.9rem; color: #374151;'>
                        {num_buyers} instituciones comprando ({total_bought:,.0f} acciones) vs
                        {num_sellers} instituciones vendiendo ({total_sold:,.0f} acciones).
                        Balance neto: <strong>{net_flow:+,.0f} acciones</strong>
                    </span>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.info("Datos de cambios en posiciones no disponibles para calcular balance")
        else:
            st.info("Datos de cambios en posiciones no disponibles en el reporte")

        st.markdown("---")

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
                    st.warning("△ **Earnings within 5 days** - High volatility expected. Consider waiting to enter new positions.")
                
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


def render_guardrails_breakdown(symbol: str, guardrails_data: dict, fmp_client, industry: str = ''):
    """
    Render comprehensive guardrails breakdown dashboard.

    Shows all accounting quality metrics with detailed explanations.
    """
    import streamlit as st
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    # Main header
    status = guardrails_data.get('guardrail_status', 'AMBAR')
    status_color = {
        'VERDE': '#10b981',
        'AMBAR': '#f59e0b',
        'ROJO': '#ef4444'
    }.get(status, '#6b7280')

    st.markdown(f"""
    <div style='background: linear-gradient(135deg, {status_color} 0%, {status_color}dd 100%);
                padding: 2rem; border-radius: 12px; margin-bottom: 2rem; text-align: center;'>
        <div style='color: white; font-size: 2.5rem; font-weight: 700; margin-bottom: 0.5rem; letter-spacing: 2px;'>
            ACCOUNTING QUALITY: {status}
        </div>
        <div style='color: white; font-size: 1.1rem; opacity: 0.95; margin-top: 1rem;'>
            {guardrails_data.get('guardrail_reasons', 'All checks OK')}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Create tabs for different guardrail categories
    guardrail_tabs = st.tabs([
        "Overview",
        "Earnings Quality",
        "Cash Conversion",
        "Operating Metrics",
        "Debt & Liquidity"
    ])

    # ========== TAB 1: Overview ==========
    with guardrail_tabs[0]:
        col1, col2, col3, col4 = st.columns(4)

        # Beneish M-Score
        with col1:
            m_score = guardrails_data.get('beneishM')
            if m_score is not None:
                # Determine threshold based on industry
                from screener.guardrails import GuardrailCalculator
                calc = GuardrailCalculator(fmp_client, {'guardrails': {}})
                threshold = calc._get_beneish_threshold_for_industry(industry, symbol)

                if m_score > threshold:
                    m_color = "#ef4444"
                    m_status = "HIGH"
                elif m_score > -2.22:
                    m_color = "#f59e0b"
                    m_status = "BORDERLINE"
                else:
                    m_color = "#10b981"
                    m_status = "GOOD"

                st.markdown(f"""
                <div style='background: white; padding: 1.5rem; border-radius: 8px;
                            border-left: 4px solid {m_color}; box-shadow: 0 2px 8px rgba(0,0,0,0.1);'>
                    <div style='font-size: 0.85rem; color: #6b7280; margin-bottom: 0.5rem;'>
                        Beneish M-Score
                    </div>
                    <div style='font-size: 2rem; font-weight: 700; color: {m_color};'>
                        {m_score:.2f}
                    </div>
                    <div style='font-size: 0.9rem; color: #374151; margin-top: 0.5rem;'>
                        {m_status}
                    </div>
                    <div style='font-size: 0.75rem; color: #9ca3af; margin-top: 0.5rem;'>
                        Threshold: {threshold:.2f}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.info("N/A")

        # Altman Z-Score (if applicable - exclude pharma, biotech, software)
        with col2:
            z_score = guardrails_data.get('altmanZ')

            # Industries where Altman Z doesn't apply
            excluded_industries = [
                'biotechnology', 'drug manufacturers', 'pharmaceutical', 'biotech',
                'software', 'internet', 'semiconductors', 'healthcare technology'
            ]
            industry_lower = industry.lower() if industry else ''
            z_score_applicable = not any(excl in industry_lower for excl in excluded_industries)

            if z_score is not None and z_score_applicable:
                if z_score < 1.8:
                    z_color = "#ef4444"
                    z_status = "DISTRESS"
                elif z_score < 2.99:
                    z_color = "#f59e0b"
                    z_status = "GRAY ZONE"
                else:
                    z_color = "#10b981"
                    z_status = "SAFE"

                st.markdown(f"""
                <div style='background: white; padding: 1.5rem; border-radius: 8px;
                            border-left: 4px solid {z_color}; box-shadow: 0 2px 8px rgba(0,0,0,0.1);'>
                    <div style='font-size: 0.85rem; color: #6b7280; margin-bottom: 0.5rem;'>
                        Altman Z-Score
                    </div>
                    <div style='font-size: 2rem; font-weight: 700; color: {z_color};'>
                        {z_score:.2f}
                    </div>
                    <div style='font-size: 0.9rem; color: #374151; margin-top: 0.5rem;'>
                        {z_status}
                    </div>
                    <div style='font-size: 0.75rem; color: #9ca3af; margin-top: 0.5rem;'>
                        Safe: >2.99
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                # Show N/A or disclaimer for excluded industries
                st.markdown("""
                <div style='background: white; padding: 1.5rem; border-radius: 8px;
                            border-left: 4px solid #6b7280; box-shadow: 0 2px 8px rgba(0,0,0,0.1);'>
                    <div style='font-size: 0.85rem; color: #6b7280; margin-bottom: 0.5rem;'>
                        Altman Z-Score
                    </div>
                    <div style='font-size: 0.9rem; color: #9ca3af; margin-top: 0.5rem;'>
                        N/A for this industry
                    </div>
                    <div style='font-size: 0.75rem; color: #9ca3af; margin-top: 0.5rem;'>
                        (Model designed for manufacturing)
                    </div>
                </div>
                """, unsafe_allow_html=True)

        # Cash Conversion
        with col3:
            import math
            cc = guardrails_data.get('cash_conversion', {})
            fcf_ni = cc.get('fcf_to_ni_current')
            # Check for None and NaN
            if fcf_ni is not None and not (isinstance(fcf_ni, (int, float)) and math.isnan(fcf_ni)):
                if fcf_ni < 40:
                    cc_color = "#ef4444"
                    cc_status = "LOW"
                elif fcf_ni < 60:
                    cc_color = "#f59e0b"
                    cc_status = "MODERATE"
                else:
                    cc_color = "#10b981"
                    cc_status = "STRONG"

                st.markdown(f"""
                <div style='background: white; padding: 1.5rem; border-radius: 8px;
                            border-left: 4px solid {cc_color}; box-shadow: 0 2px 8px rgba(0,0,0,0.1);'>
                    <div style='font-size: 0.85rem; color: #6b7280; margin-bottom: 0.5rem;'>
                        FCF/Net Income
                    </div>
                    <div style='font-size: 2rem; font-weight: 700; color: {cc_color};'>
                        {fcf_ni:.0f}%
                    </div>
                    <div style='font-size: 0.9rem; color: #374151; margin-top: 0.5rem;'>
                        {cc_status}
                    </div>
                    <div style='font-size: 0.75rem; color: #9ca3af; margin-top: 0.5rem;'>
                        Target: >60%
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.info("N/A")

        # Dilution
        with col4:
            dilution = guardrails_data.get('netShareIssuance_12m_%')
            if dilution is not None:
                if dilution > 10:
                    dil_color = "#ef4444"
                    dil_status = "HIGH"
                elif dilution > 5:
                    dil_color = "#f59e0b"
                    dil_status = "MODERATE"
                elif dilution < -5:
                    dil_color = "#10b981"
                    dil_status = "BUYBACKS"
                else:
                    dil_color = "#10b981"
                    dil_status = "LOW"

                st.markdown(f"""
                <div style='background: white; padding: 1.5rem; border-radius: 8px;
                            border-left: 4px solid {dil_color}; box-shadow: 0 2px 8px rgba(0,0,0,0.1);'>
                    <div style='font-size: 0.85rem; color: #6b7280; margin-bottom: 0.5rem;'>
                        Share Dilution (12M)
                    </div>
                    <div style='font-size: 2rem; font-weight: 700; color: {dil_color};'>
                        {dilution:+.1f}%
                    </div>
                    <div style='font-size: 0.9rem; color: #374151; margin-top: 0.5rem;'>
                        {dil_status}
                    </div>
                    <div style='font-size: 0.75rem; color: #9ca3af; margin-top: 0.5rem;'>
                        Target: <5%
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.info("N/A")

    # ========== TAB 2: Earnings Quality ==========
    with guardrail_tabs[1]:
        st.markdown("### Beneish M-Score Components")

        m_score = guardrails_data.get('beneishM')
        if m_score is not None:
            # Explanation
            st.markdown("""
            <div style='background: #f3f4f6; padding: 1rem; border-radius: 8px; margin-bottom: 1.5rem;'>
                <strong>What is Beneish M-Score?</strong><br>
                Developed by Professor Messod Beneish (1999), this model detects earnings manipulation
                by analyzing 8 financial ratios. Higher scores indicate higher probability of manipulation.
                <br><br>
                <strong>Interpretation:</strong>
                <ul style='margin-top: 0.5rem;'>
                    <li><strong>M < -2.22:</strong> Low manipulation risk ✅</li>
                    <li><strong>-2.22 < M < -1.78:</strong> Borderline/Gray zone ⚠️</li>
                    <li><strong>M > -1.78:</strong> High manipulation risk 🚨</li>
                </ul>
                <em>Note: Thresholds are industry-adjusted. High-accrual industries (pharma, biotech, construction)
                use more permissive thresholds.</em>
            </div>
            """, unsafe_allow_html=True)

            # Get industry threshold
            from screener.guardrails import GuardrailCalculator
            calc = GuardrailCalculator(fmp_client, {'guardrails': {}})
            threshold = calc._get_beneish_threshold_for_industry(industry, symbol)

            # Gauge chart
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=m_score,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': f"Beneish M-Score<br><span style='font-size:0.8em'>Industry Threshold: {threshold:.2f}</span>",
                       'font': {'size': 20}},
                number={'font': {'size': 48}},
                gauge={
                    'axis': {'range': [-4, 0], 'tickwidth': 1},
                    'bar': {'color': "#ef4444" if m_score > threshold else "#10b981"},
                    'bgcolor': "white",
                    'borderwidth': 2,
                    'bordercolor': "gray",
                    'steps': [
                        {'range': [-4, -2.22], 'color': 'rgba(16, 185, 129, 0.3)'},
                        {'range': [-2.22, threshold], 'color': 'rgba(245, 158, 11, 0.3)'},
                        {'range': [threshold, 0], 'color': 'rgba(239, 68, 68, 0.3)'}
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75,
                        'value': threshold
                    }
                }
            ))

            fig.update_layout(
                height=350,
                margin=dict(l=20, r=20, t=80, b=20),
                paper_bgcolor='rgba(0,0,0,0)',
                font={'color': "#374151", 'family': "Arial"}
            )

            st.plotly_chart(fig, use_container_width=True)

            # What contributes to this score
            st.markdown("#### What Drives This Score?")
            st.markdown("""
            The Beneish M-Score combines 8 financial indices:

            1. **DSRI** (Days Sales in Receivables Index): Receivables growing faster than sales?
            2. **GMI** (Gross Margin Index): Gross margins deteriorating?
            3. **AQI** (Asset Quality Index): Asset quality declining?
            4. **SGI** (Sales Growth Index): Revenue growth (rapid growth = higher risk)
            5. **DEPI** (Depreciation Index): Depreciation rate slowing?
            6. **SGAI** (SG&A Index): SG&A growing slower than sales?
            7. **TATA** (Total Accruals to Total Assets): High accruals?
            8. **LVGI** (Leverage Index): Leverage increasing?

            **For this company:**
            - M-Score = {:.2f}
            - Industry Threshold = {:.2f}
            - Status: {}
            """.format(
                m_score,
                threshold,
                "HIGH RISK" if m_score > threshold else "LOW RISK"
            ))
        else:
            st.warning("Beneish M-Score data not available (requires at least 2 years of quarterly data)")

        st.markdown("---")

        # Accruals
        st.markdown("### Accruals / NOA (Sloan 1996)")
        accruals = guardrails_data.get('accruals_noa_%')
        if accruals is not None:
            st.markdown("""
            <div style='background: #f3f4f6; padding: 1rem; border-radius: 8px; margin-bottom: 1.5rem;'>
                <strong>What are Accruals?</strong><br>
                Accruals represent the difference between reported earnings and actual cash flow.
                High accruals can indicate:
                <ul>
                    <li>Aggressive revenue recognition</li>
                    <li>Inventory buildup</li>
                    <li>Delayed payments to suppliers</li>
                    <li>Lower earnings quality</li>
                </ul>
                <strong>Rule of Thumb:</strong> Accruals >15% of NOA = concerning (>20% for growth companies)
            </div>
            """, unsafe_allow_html=True)

            accruals_color = "#ef4444" if accruals > 20 else "#f59e0b" if accruals > 15 else "#10b981"

            col1, col2 = st.columns([1, 2])

            with col1:
                st.markdown(f"""
                <div style='background: white; padding: 2rem; border-radius: 8px;
                            border-left: 6px solid {accruals_color}; box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                            text-align: center;'>
                    <div style='font-size: 0.9rem; color: #6b7280; margin-bottom: 1rem;'>
                        Accruals / NOA
                    </div>
                    <div style='font-size: 3rem; font-weight: 700; color: {accruals_color};'>
                        {accruals:.1f}%
                    </div>
                    <div style='font-size: 1rem; color: #374151; margin-top: 1rem;'>
                        {'HIGH' if accruals > 20 else 'ELEVATED' if accruals > 15 else '• NORMAL'}
                    </div>
                </div>
                """, unsafe_allow_html=True)

            with col2:
                # Bar chart showing threshold
                fig = go.Figure()

                fig.add_trace(go.Bar(
                    x=['Current Accruals', 'Threshold (Growth)', 'Threshold (Mature)'],
                    y=[accruals, 20, 15],
                    marker_color=[accruals_color, '#f59e0b', '#10b981'],
                    text=[f"{accruals:.1f}%", "20%", "15%"],
                    textposition='outside'
                ))

                fig.update_layout(
                    title="Accruals vs. Thresholds",
                    yaxis_title="% of NOA",
                    showlegend=False,
                    height=300,
                    plot_bgcolor='rgba(248,249,250,0.8)'
                )

                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Accruals data not available")

    # ========== TAB 3: Cash Conversion ==========
    with guardrail_tabs[2]:
        cc = guardrails_data.get('cash_conversion', {})

        if cc and cc.get('fcf_to_ni_current') is not None:
            st.markdown("### Free Cash Flow Conversion")

            st.markdown("""
            <div style='background: #f3f4f6; padding: 1rem; border-radius: 8px; margin-bottom: 1.5rem;'>
                <strong>Why Cash Conversion Matters:</strong><br>
                Companies can manipulate earnings, but cash is harder to fake. Strong companies
                consistently convert >80% of earnings into free cash flow.
                <br><br>
                <strong>Red Flags:</strong>
                <ul>
                    <li>FCF/NI < 40%: Serious earnings quality concern</li>
                    <li>FCF/NI declining: Quality deteriorating</li>
                    <li>High capex intensity: Capital-intensive business</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)

            import math
            fcf_ni_current = cc.get('fcf_to_ni_current')
            fcf_ni_avg = cc.get('fcf_to_ni_avg_8q')
            fcf_rev = cc.get('fcf_to_revenue_current')
            capex_intensity = cc.get('capex_intensity_current')

            # Metrics row
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                # Check for None and NaN
                if fcf_ni_current is not None and not (isinstance(fcf_ni_current, (int, float)) and math.isnan(fcf_ni_current)):
                    fcf_color = "#ef4444" if fcf_ni_current < 40 else "#f59e0b" if fcf_ni_current < 60 else "#10b981"
                    st.markdown(f"""
                    <div style='background: white; padding: 1.5rem; border-radius: 8px;
                                border-left: 4px solid {fcf_color}; box-shadow: 0 2px 8px rgba(0,0,0,0.1);'>
                        <div style='font-size: 0.85rem; color: #6b7280;'>FCF/NI (Current)</div>
                        <div style='font-size: 2.5rem; font-weight: 700; color: {fcf_color};'>
                            {fcf_ni_current:.0f}%
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.info("FCF/NI data not available")

            with col2:
                if fcf_ni_avg is not None and not (isinstance(fcf_ni_avg, (int, float)) and math.isnan(fcf_ni_avg)):
                    avg_color = "#ef4444" if fcf_ni_avg < 40 else "#f59e0b" if fcf_ni_avg < 60 else "#10b981"
                    st.markdown(f"""
                    <div style='background: white; padding: 1.5rem; border-radius: 8px;
                                border-left: 4px solid {avg_color}; box-shadow: 0 2px 8px rgba(0,0,0,0.1);'>
                        <div style='font-size: 0.85rem; color: #6b7280;'>FCF/NI (8Q Avg)</div>
                        <div style='font-size: 2.5rem; font-weight: 700; color: {avg_color};'>
                            {fcf_ni_avg:.0f}%
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

            with col3:
                if fcf_rev is not None and not (isinstance(fcf_rev, (int, float)) and math.isnan(fcf_rev)):
                    st.markdown(f"""
                    <div style='background: white; padding: 1.5rem; border-radius: 8px;
                                border-left: 4px solid #6366f1; box-shadow: 0 2px 8px rgba(0,0,0,0.1);'>
                        <div style='font-size: 0.85rem; color: #6b7280;'>FCF/Revenue</div>
                        <div style='font-size: 2.5rem; font-weight: 700; color: #6366f1;'>
                            {fcf_rev:.0f}%
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

            with col4:
                if capex_intensity is not None and not (isinstance(capex_intensity, (int, float)) and math.isnan(capex_intensity)):
                    capex_color = "#ef4444" if capex_intensity > 20 else "#f59e0b" if capex_intensity > 10 else "#10b981"
                    st.markdown(f"""
                    <div style='background: white; padding: 1.5rem; border-radius: 8px;
                                border-left: 4px solid {capex_color}; box-shadow: 0 2px 8px rgba(0,0,0,0.1);'>
                        <div style='font-size: 0.85rem; color: #6b7280;'>Capex Intensity</div>
                        <div style='font-size: 2.5rem; font-weight: 700; color: {capex_color};'>
                            {capex_intensity:.1f}%
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

            # Flags
            if cc.get('flags'):
                st.markdown("#### △ Cash Conversion Flags")
                for flag in cc['flags']:
                    st.warning(flag)
        else:
            st.info("Cash conversion data not available")

    # ========== TAB 4: Operating Metrics ==========
    with guardrail_tabs[3]:
        col1, col2 = st.columns(2)

        with col1:
            # Working Capital
            wc = guardrails_data.get('working_capital', {})
            if wc and wc.get('ccc_current') is not None:
                st.markdown("### Working Capital Quality")

                ccc = wc.get('ccc_current')
                dso = wc.get('dso_current')
                dio = wc.get('dio_current')

                # Build DSO and DIO lines only if available
                dso_line = f"DSO: {dso:.0f} days ({wc.get('dso_trend', 'Unknown')})" if dso is not None else "DSO: N/A"
                dio_line = f"DIO: {dio:.0f} days ({wc.get('dio_trend', 'Unknown')})" if dio is not None else "DIO: N/A"

                st.markdown(f"""
                <div style='background: white; padding: 1.5rem; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);'>
                    <div style='font-size: 0.9rem; color: #6b7280; margin-bottom: 1rem;'>
                        <strong>Cash Conversion Cycle (CCC)</strong>
                    </div>
                    <div style='font-size: 2.5rem; font-weight: 700; color: #6366f1; margin-bottom: 1rem;'>
                        {ccc:.0f} days
                    </div>
                    <div style='font-size: 0.85rem; color: #374151;'>
                        {dso_line}<br>
                        {dio_line}<br>
                        CCC Trend: {wc.get('ccc_trend', 'Unknown')}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                if wc.get('flags'):
                    st.markdown("#### Flags")
                    for flag in wc['flags']:
                        st.warning(flag)

        with col2:
            # Margin Trajectory
            mt = guardrails_data.get('margin_trajectory', {})
            if mt and mt.get('gross_margin_current') is not None:
                st.markdown("### Margin Trajectory")

                gm_current = mt.get('gross_margin_current')
                om_current = mt.get('operating_margin_current')
                gm_traj = mt.get('gross_margin_trajectory', 'Unknown')
                om_traj = mt.get('operating_margin_trajectory', 'Unknown')

                traj_color = {
                    'Expanding': '#10b981',
                    'Stable': '#f59e0b',
                    'Compressing': '#ef4444',
                    'Unknown': '#6b7280'
                }

                # Build margin sections
                margin_html_parts = []

                # Gross margin (always present due to outer if condition)
                margin_html_parts.append(f"""
                    <div style='margin-bottom: 1rem;'>
                        <div style='font-size: 0.85rem; color: #6b7280;'>Gross Margin</div>
                        <div style='font-size: 2rem; font-weight: 700; color: {traj_color.get(gm_traj, "#6b7280")};'>
                            {gm_current:.1f}%
                        </div>
                        <div style='font-size: 0.85rem; color: #374151;'>
                            {gm_traj}
                        </div>
                    </div>
                """)

                # Operating margin (only if available)
                if om_current is not None:
                    margin_html_parts.append(f"""
                    <hr style='border: 1px solid #e5e7eb; margin: 1rem 0;'>
                    <div>
                        <div style='font-size: 0.85rem; color: #6b7280;'>Operating Margin</div>
                        <div style='font-size: 2rem; font-weight: 700; color: {traj_color.get(om_traj, "#6b7280")};'>
                            {om_current:.1f}%
                        </div>
                        <div style='font-size: 0.85rem; color: #374151;'>
                            {om_traj}
                        </div>
                    </div>
                    """)

                # Combine parts and display
                st.markdown(f"""
                <div style='background: white; padding: 1.5rem; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);'>
                    {''.join(margin_html_parts)}
                </div>
                """, unsafe_allow_html=True)

        # Revenue Growth
        rev_growth = guardrails_data.get('revenue_growth_3y')
        import pandas as pd
        if rev_growth is not None and not pd.isna(rev_growth):
            st.markdown("### Revenue Growth (3Y CAGR)")

            rev_color = "#ef4444" if rev_growth < -5 else "#f59e0b" if rev_growth < 0 else "#10b981"

            st.markdown(f"""
            <div style='background: white; padding: 2rem; border-radius: 8px;
                        border-left: 6px solid {rev_color}; box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                        text-align: center;'>
                <div style='font-size: 0.9rem; color: #6b7280; margin-bottom: 1rem;'>
                    3-Year Revenue CAGR
                </div>
                <div style='font-size: 3.5rem; font-weight: 700; color: {rev_color};'>
                    {rev_growth:+.1f}%
                </div>
                <div style='font-size: 1rem; color: #374151; margin-top: 1rem;'>
                    {'DECLINING' if rev_growth < -5 else 'FLAT/DECLINING' if rev_growth < 0 else 'GROWING'}
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("Revenue growth data not available for this period")

    # ========== TAB 5: Debt & Liquidity ==========
    with guardrail_tabs[4]:
        dm = guardrails_data.get('debt_maturity_wall', {})

        if dm and dm.get('debt_due_12m') is not None:
            st.markdown("### Debt Maturity & Liquidity")

            col1, col2, col3 = st.columns(3)

            with col1:
                st_debt_pct = dm.get('short_term_debt_pct')
                if st_debt_pct is not None:
                    pct_color = "#ef4444" if st_debt_pct > 40 else "#f59e0b" if st_debt_pct > 25 else "#10b981"
                    st.markdown(f"""
                    <div style='background: white; padding: 1.5rem; border-radius: 8px;
                                border-left: 4px solid {pct_color}; box-shadow: 0 2px 8px rgba(0,0,0,0.1);'>
                        <div style='font-size: 0.85rem; color: #6b7280;'>ST Debt % of Total</div>
                        <div style='font-size: 2.5rem; font-weight: 700; color: {pct_color};'>
                            {st_debt_pct:.0f}%
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

            with col2:
                liquidity = dm.get('liquidity_ratio')
                if liquidity is not None:
                    liq_color = "#ef4444" if liquidity < 0.5 else "#f59e0b" if liquidity < 1.0 else "#10b981"
                    st.markdown(f"""
                    <div style='background: white; padding: 1.5rem; border-radius: 8px;
                                border-left: 4px solid {liq_color}; box-shadow: 0 2px 8px rgba(0,0,0,0.1);'>
                        <div style='font-size: 0.85rem; color: #6b7280;'>Liquidity Ratio</div>
                        <div style='font-size: 2.5rem; font-weight: 700; color: {liq_color};'>
                            {liquidity:.2f}x
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

            with col3:
                int_cov = dm.get('interest_coverage')
                if int_cov is not None:
                    int_color = "#ef4444" if int_cov < 2.0 else "#f59e0b" if int_cov < 3.0 else "#10b981"
                    st.markdown(f"""
                    <div style='background: white; padding: 1.5rem; border-radius: 8px;
                                border-left: 4px solid {int_color}; box-shadow: 0 2px 8px rgba(0,0,0,0.1);'>
                        <div style='font-size: 0.85rem; color: #6b7280;'>Interest Coverage</div>
                        <div style='font-size: 2.5rem; font-weight: 700; color: {int_color};'>
                            {int_cov:.1f}x
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

            if dm.get('flags'):
                st.markdown("#### △ Debt & Liquidity Flags")
                for flag in dm['flags']:
                    if 'FAIL' in flag:
                        st.error(flag)
                    else:
                        st.warning(flag)
        else:
            st.info("Debt maturity data not available")


def render_quality_score_breakdown(symbol: str, stock_data: dict, is_financial: bool = False):
    """
    Render comprehensive quality score breakdown.

    Shows all quality metrics and how they contribute to the final quality score.
    """
    import streamlit as st
    import plotly.graph_objects as go
    import pandas as pd

    quality_score = stock_data.get('quality_score_0_100', 0)

    # Header
    score_color = "#10b981" if quality_score >= 70 else "#f59e0b" if quality_score >= 50 else "#ef4444"

    st.markdown(f"""
    <div style='background: linear-gradient(135deg, {score_color} 0%, {score_color}dd 100%);
                padding: 2rem; border-radius: 12px; margin-bottom: 2rem; text-align: center;'>
        <div style='color: white; font-size: 1.2rem; margin-bottom: 0.5rem; opacity: 0.95;'>
            Quality Score
        </div>
        <div style='color: white; font-size: 4rem; font-weight: 700; margin-bottom: 0.5rem;'>
            {quality_score:.0f}
        </div>
        <div style='color: white; font-size: 1.1rem; opacity: 0.95;'>
            {'EXCELLENT' if quality_score >= 80 else 'STRONG' if quality_score >= 70 else 'MODERATE' if quality_score >= 50 else 'WEAK'}
        </div>
    </div>
    """, unsafe_allow_html=True)

    if not is_financial:
        # Non-Financial Quality Metrics
        st.markdown("### Quality Metrics Breakdown")

        st.markdown("""
        <div style='background: #f3f4f6; padding: 1rem; border-radius: 8px; margin-bottom: 1.5rem;'>
            <strong>How Quality Score is Calculated:</strong><br>
            The quality score combines 11 metrics that measure:
            <ul>
                <li><strong>Profitability:</strong> ROIC, Gross Profit/Assets, Cash ROA</li>
                <li><strong>Cash Generation:</strong> FCF Margin, CFO/NI ratio</li>
                <li><strong>Financial Strength:</strong> Interest Coverage, Net Debt/EBITDA</li>
                <li><strong>Competitive Position:</strong> Moat Score (pricing power + operating leverage + ROIC persistence)</li>
                <li><strong>Growth:</strong> Revenue Growth (3Y CAGR)</li>
                <li><strong>Stability:</strong> ROA & FCF Volatility</li>
            </ul>
            Each metric is normalized by industry and converted to a 0-100 percentile score.
        </div>
        """, unsafe_allow_html=True)

        # Create tabs for different quality dimensions
        quality_tabs = st.tabs([
            "All Metrics",
            "Profitability",
            "Cash Generation",
            "Financial Strength",
            "Moat & Growth"
        ])

        # ========== TAB 1: All Metrics ==========
        with quality_tabs[0]:
            # Collect all quality metrics
            metrics_data = []

            # Higher is better
            higher_better = [
                ('roic_%', 'ROIC', '%', 15, 25),
                ('grossProfits_to_assets', 'Gross Profit / Assets', '%', 20, 35),
                ('cash_roa', 'Cash ROA (CFO/Assets)', '%', 8, 15),
                ('fcf_margin_%', 'FCF Margin', '%', 10, 20),
                ('cfo_to_ni', 'CFO / Net Income', '%', 80, 100),
                ('interestCoverage', 'Interest Coverage', 'x', 5, 10),
                ('moat_score', 'Moat Score', '/100', 50, 70),
                ('revenue_growth_3y', 'Revenue Growth (3Y)', '%', 5, 15)
            ]

            # Lower is better
            lower_better = [
                ('netDebt_ebitda', 'Net Debt / EBITDA', 'x', 3, 1.5),
                ('roa_stability', 'ROA Volatility', '%', 5, 2),
                ('fcf_stability', 'FCF Volatility', '%', 30, 15)
            ]

            # Build metrics table
            import pandas as pd
            import math
            for key, name, unit, threshold_low, threshold_high in higher_better:
                value = stock_data.get(key)
                # Triple check: None, pd.isna, and math.isnan for float NaN
                if value is None or pd.isna(value) or (isinstance(value, (int, float)) and math.isnan(value)):
                    continue  # Skip this metric entirely if invalid

                if value >= threshold_high:
                    status = "EXCELLENT"
                    color = "#10b981"
                elif value >= threshold_low:
                    status = "GOOD"
                    color = "#22c55e"
                else:
                    status = "BELOW TARGET"
                    color = "#f59e0b"

                metrics_data.append({
                    'Metric': name,
                    'Value': f"{value:.1f}{unit}",
                    'Target': f">{threshold_high}{unit}",
                    'Status': status,
                    'Color': color
                })

            for key, name, unit, threshold_high, threshold_low in lower_better:
                value = stock_data.get(key)
                # Triple check: None, pd.isna, and math.isnan for float NaN
                if value is None or pd.isna(value) or (isinstance(value, (int, float)) and math.isnan(value)):
                    continue  # Skip this metric entirely if invalid

                if value <= threshold_low:
                    status = "EXCELLENT"
                    color = "#10b981"
                elif value <= threshold_high:
                    status = "GOOD"
                    color = "#22c55e"
                else:
                    status = "ABOVE TARGET"
                    color = "#f59e0b"

                metrics_data.append({
                    'Metric': name,
                    'Value': f"{value:.1f}{unit}",
                    'Target': f"<{threshold_low}{unit}",
                    'Status': status,
                    'Color': color
                })

            # Display as cards
            if metrics_data:
                cols_per_row = 2
                for i in range(0, len(metrics_data), cols_per_row):
                    cols = st.columns(cols_per_row)
                    for j, col in enumerate(cols):
                        if i + j < len(metrics_data):
                            m = metrics_data[i + j]
                            with col:
                                st.markdown(f"""
                                <div style='background: white; padding: 1.5rem; border-radius: 8px;
                                            border-left: 4px solid {m['Color']}; box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                                            margin-bottom: 1rem;'>
                                    <div style='font-size: 0.85rem; color: #6b7280; margin-bottom: 0.5rem;'>
                                        {m['Metric']}
                                    </div>
                                    <div style='font-size: 2rem; font-weight: 700; color: {m['Color']};'>
                                        {m['Value']}
                                    </div>
                                    <div style='font-size: 0.85rem; color: #374151; margin-top: 0.5rem;'>
                                        Target: {m['Target']}
                                    </div>
                                    <div style='font-size: 0.85rem; margin-top: 0.5rem;'>
                                        {m['Status']}
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)

        # ========== TAB 2: Profitability ==========
        with quality_tabs[1]:
            st.markdown("### Core Profitability Metrics")

            col1, col2, col3 = st.columns(3)

            with col1:
                roic = stock_data.get('roic_%')
                if roic is not None:
                    roic_color = "#10b981" if roic >= 25 else "#22c55e" if roic >= 15 else "#f59e0b"
                    st.markdown(f"""
                    <div style='background: white; padding: 2rem; border-radius: 8px;
                                border-left: 6px solid {roic_color}; box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                                text-align: center;'>
                        <div style='font-size: 0.9rem; color: #6b7280; margin-bottom: 1rem;'>
                            Return on Invested Capital
                        </div>
                        <div style='font-size: 3rem; font-weight: 700; color: {roic_color};'>
                            {roic:.1f}%
                        </div>
                        <div style='font-size: 0.9rem; color: #374151; margin-top: 1rem;'>
                            {'Excellent (>25%)' if roic >= 25 else '• Strong (>15%)' if roic >= 15 else '△ Moderate (<15%)'}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    st.markdown("""
                    <div style='background: #f3f4f6; padding: 0.75rem; border-radius: 6px; margin-top: 1rem; font-size: 0.85rem;'>
                        <strong>What is ROIC?</strong><br>
                        ROIC measures how efficiently a company generates profits from invested capital
                        (debt + equity). It's Warren Buffett's favorite profitability metric.<br>
                        <strong>Rule of Thumb:</strong> ROIC >15% = strong moat, >25% = exceptional business
                    </div>
                    """, unsafe_allow_html=True)

            with col2:
                gp_assets = stock_data.get('grossProfits_to_assets')
                if gp_assets is not None:
                    gp_color = "#10b981" if gp_assets >= 35 else "#22c55e" if gp_assets >= 20 else "#f59e0b"
                    st.markdown(f"""
                    <div style='background: white; padding: 2rem; border-radius: 8px;
                                border-left: 6px solid {gp_color}; box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                                text-align: center;'>
                        <div style='font-size: 0.9rem; color: #6b7280; margin-bottom: 1rem;'>
                            Gross Profit / Assets
                        </div>
                        <div style='font-size: 3rem; font-weight: 700; color: {gp_color};'>
                            {gp_assets:.1f}%
                        </div>
                        <div style='font-size: 0.9rem; color: #374151; margin-top: 1rem;'>
                            {'Excellent (>35%)' if gp_assets >= 35 else '• Strong (>20%)' if gp_assets >= 20 else '△ Moderate (<20%)'}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    st.markdown("""
                    <div style='background: #f3f4f6; padding: 0.75rem; border-radius: 6px; margin-top: 1rem; font-size: 0.85rem;'>
                        <strong>Novy-Marx (2013):</strong><br>
                        Gross profitability is a stronger predictor of returns than traditional
                        net income measures. Asset-light businesses score highest.
                    </div>
                    """, unsafe_allow_html=True)

            with col3:
                cash_roa = stock_data.get('cash_roa')
                if cash_roa is not None:
                    cash_color = "#10b981" if cash_roa >= 15 else "#22c55e" if cash_roa >= 8 else "#f59e0b"
                    st.markdown(f"""
                    <div style='background: white; padding: 2rem; border-radius: 8px;
                                border-left: 6px solid {cash_color}; box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                                text-align: center;'>
                        <div style='font-size: 0.9rem; color: #6b7280; margin-bottom: 1rem;'>
                            Cash ROA (CFO/Assets)
                        </div>
                        <div style='font-size: 3rem; font-weight: 700; color: {cash_color};'>
                            {cash_roa:.1f}%
                        </div>
                        <div style='font-size: 0.9rem; color: #374151; margin-top: 1rem;'>
                            {'Excellent (>15%)' if cash_roa >= 15 else '• Strong (>8%)' if cash_roa >= 8 else '△ Moderate (<8%)'}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    st.markdown("""
                    <div style='background: #f3f4f6; padding: 0.75rem; border-radius: 6px; margin-top: 1rem; font-size: 0.85rem;'>
                        <strong>Piotroski F-Score Component:</strong><br>
                        Cash-based profitability is harder to manipulate than accrual-based
                        net income. High Cash ROA = high earnings quality.
                    </div>
                    """, unsafe_allow_html=True)

        # ========== TAB 3: Cash Generation ==========
        with quality_tabs[2]:
            st.markdown("### Cash Generation Quality")

            col1, col2 = st.columns(2)

            with col1:
                fcf_margin = stock_data.get('fcf_margin_%')
                if fcf_margin is not None:
                    fcf_color = "#10b981" if fcf_margin >= 20 else "#22c55e" if fcf_margin >= 10 else "#f59e0b"
                    st.markdown(f"""
                    <div style='background: white; padding: 2rem; border-radius: 8px;
                                border-left: 6px solid {fcf_color}; box-shadow: 0 2px 8px rgba(0,0,0,0.1);'>
                        <div style='font-size: 0.9rem; color: #6b7280; margin-bottom: 1rem;'>
                            <strong>Free Cash Flow Margin</strong>
                        </div>
                        <div style='font-size: 3.5rem; font-weight: 700; color: {fcf_color}; text-align: center;'>
                            {fcf_margin:.1f}%
                        </div>
                        <div style='font-size: 1rem; color: #374151; margin-top: 1rem; text-align: center;'>
                            {'Excellent (>20%)' if fcf_margin >= 20 else '• Strong (>10%)' if fcf_margin >= 10 else '△ Low (<10%)'}
                        </div>
                        <div style='background: #f3f4f6; padding: 1rem; border-radius: 6px; margin-top: 1rem; font-size: 0.85rem;'>
                            <strong>Formula:</strong> (Operating Cash Flow - Capex) / Revenue<br><br>
                            <strong>Why it matters:</strong> High FCF margin means the company generates
                            abundant cash after funding growth. This cash can be returned to shareholders
                            via dividends and buybacks.
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

            with col2:
                cfo_ni = stock_data.get('cfo_to_ni')
                if cfo_ni is not None:
                    cfo_color = "#10b981" if cfo_ni >= 100 else "#22c55e" if cfo_ni >= 80 else "#f59e0b"
                    st.markdown(f"""
                    <div style='background: white; padding: 2rem; border-radius: 8px;
                                border-left: 6px solid {cfo_color}; box-shadow: 0 2px 8px rgba(0,0,0,0.1);'>
                        <div style='font-size: 0.9rem; color: #6b7280; margin-bottom: 1rem;'>
                            <strong>Operating Cash Flow / Net Income</strong>
                        </div>
                        <div style='font-size: 3.5rem; font-weight: 700; color: {cfo_color}; text-align: center;'>
                            {cfo_ni:.0f}%
                        </div>
                        <div style='font-size: 1rem; color: #374151; margin-top: 1rem; text-align: center;'>
                            {'Excellent (>100%)' if cfo_ni >= 100 else '• Strong (>80%)' if cfo_ni >= 80 else '△ Low (<80%)'}
                        </div>
                        <div style='background: #f3f4f6; padding: 1rem; border-radius: 6px; margin-top: 1rem; font-size: 0.85rem;'>
                            <strong>Earnings Quality Test:</strong><br>
                            If CFO/NI consistently >100%, earnings are high quality (low accruals).<br>
                            If CFO/NI <80%, company may be using aggressive accounting to inflate earnings.
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

            # FCF Stability
            fcf_stab = stock_data.get('fcf_stability')
            if fcf_stab is not None:
                st.markdown("### Cash Flow Stability (Lower is Better)")

                stab_color = "#10b981" if fcf_stab <= 15 else "#22c55e" if fcf_stab <= 30 else "#f59e0b"

                st.markdown(f"""
                <div style='background: white; padding: 2rem; border-radius: 8px;
                            border-left: 6px solid {stab_color}; box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                            text-align: center;'>
                    <div style='font-size: 0.9rem; color: #6b7280; margin-bottom: 1rem;'>
                        FCF Volatility (Coefficient of Variation)
                    </div>
                    <div style='font-size: 3rem; font-weight: 700; color: {stab_color};'>
                        {fcf_stab:.1f}%
                    </div>
                    <div style='font-size: 1rem; color: #374151; margin-top: 1rem;'>
                        {'🌟 Very Stable (<15%)' if fcf_stab <= 15 else '• Stable (<30%)' if fcf_stab <= 30 else '△ Volatile (>30%)'}
                    </div>
                    <div style='background: #f3f4f6; padding: 1rem; border-radius: 6px; margin-top: 1rem; font-size: 0.85rem; text-align: left;'>
                        <strong>Interpretation:</strong> Measures the predictability of free cash flow over time.
                        Lower volatility = more predictable business = lower risk.
                    </div>
                </div>
                """, unsafe_allow_html=True)

        # ========== TAB 4: Financial Strength ==========
        with quality_tabs[3]:
            st.markdown("### Financial Health & Leverage")

            col1, col2 = st.columns(2)

            with col1:
                int_cov = stock_data.get('interestCoverage')
                if int_cov is not None:
                    # Cap display at 50x for readability
                    int_cov_display = min(int_cov, 50)
                    int_color = "#10b981" if int_cov >= 10 else "#22c55e" if int_cov >= 5 else "#f59e0b"

                    st.markdown(f"""
                    <div style='background: white; padding: 2rem; border-radius: 8px;
                                border-left: 6px solid {int_color}; box-shadow: 0 2px 8px rgba(0,0,0,0.1);'>
                        <div style='font-size: 0.9rem; color: #6b7280; margin-bottom: 1rem; text-align: center;'>
                            <strong>Interest Coverage (EBIT/Interest)</strong>
                        </div>
                        <div style='font-size: 3.5rem; font-weight: 700; color: {int_color}; text-align: center;'>
                            {int_cov_display:.1f}x
                        </div>
                        <div style='font-size: 1rem; color: #374151; margin-top: 1rem; text-align: center;'>
                            {'Excellent (>10x)' if int_cov >= 10 else '• Strong (>5x)' if int_cov >= 5 else '△ Weak (<5x)'}
                        </div>
                        <div style='background: #f3f4f6; padding: 1rem; border-radius: 6px; margin-top: 1rem; font-size: 0.85rem;'>
                            <strong>What it measures:</strong> How many times EBIT covers interest expense.<br><br>
                            <strong>Bankruptcy Risk:</strong>
                            <ul style='margin-top: 0.5rem;'>
                                <li>>10x: Very safe</li>
                                <li>5-10x: Safe</li>
                                <li>2-5x: Moderate risk</li>
                                <li><2x: High distress risk</li>
                            </ul>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

            with col2:
                net_debt_ebitda = stock_data.get('netDebt_ebitda')
                if net_debt_ebitda is not None:
                    # Handle negative values (net cash position)
                    if net_debt_ebitda < 0:
                        debt_color = "#10b981"
                        debt_status = "NET CASH POSITION"
                    elif net_debt_ebitda <= 1.5:
                        debt_color = "#10b981"
                        debt_status = "🌟 Very Low Leverage"
                    elif net_debt_ebitda <= 3:
                        debt_color = "#22c55e"
                        debt_status = "• Moderate Leverage"
                    else:
                        debt_color = "#f59e0b"
                        debt_status = "△ High Leverage"

                    st.markdown(f"""
                    <div style='background: white; padding: 2rem; border-radius: 8px;
                                border-left: 6px solid {debt_color}; box-shadow: 0 2px 8px rgba(0,0,0,0.1);'>
                        <div style='font-size: 0.9rem; color: #6b7280; margin-bottom: 1rem; text-align: center;'>
                            <strong>Net Debt / EBITDA</strong>
                        </div>
                        <div style='font-size: 3.5rem; font-weight: 700; color: {debt_color}; text-align: center;'>
                            {net_debt_ebitda:.1f}x
                        </div>
                        <div style='font-size: 1rem; color: #374151; margin-top: 1rem; text-align: center;'>
                            {debt_status}
                        </div>
                        <div style='background: #f3f4f6; padding: 1rem; border-radius: 6px; margin-top: 1rem; font-size: 0.85rem;'>
                            <strong>Interpretation:</strong> Years of EBITDA needed to pay off net debt.<br><br>
                            <strong>Leverage Levels:</strong>
                            <ul style='margin-top: 0.5rem;'>
                                <li><0x: Net cash (no debt)</li>
                                <li><1.5x: Conservative</li>
                                <li>1.5-3x: Moderate</li>
                                <li>>3x: Aggressive</li>
                            </ul>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

        # ========== TAB 5: Moat & Growth ==========
        with quality_tabs[4]:
            st.markdown("### Competitive Advantages & Growth")

            # Moat Score
            moat_score = stock_data.get('moat_score')
            if moat_score is not None:
                moat_color = "#10b981" if moat_score >= 70 else "#f59e0b" if moat_score >= 50 else "#ef4444"

                st.markdown(f"""
                <div style='background: linear-gradient(135deg, {moat_color} 0%, {moat_color}dd 100%);
                            padding: 2rem; border-radius: 12px; margin-bottom: 1.5rem; text-align: center;'>
                    <div style='color: white; font-size: 1.2rem; margin-bottom: 0.5rem; opacity: 0.95;'>
                        Moat Score (Competitive Advantages)
                    </div>
                    <div style='color: white; font-size: 3.5rem; font-weight: 700;'>
                        {moat_score:.0f} / 100
                    </div>
                    <div style='color: white; font-size: 1.1rem; margin-top: 0.5rem; opacity: 0.95;'>
                        {'WIDE MOAT' if moat_score >= 70 else 'NARROW MOAT' if moat_score >= 50 else '△ NO MOAT'}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                st.markdown("""
                <div style='background: #f3f4f6; padding: 1rem; border-radius: 8px; margin-bottom: 1.5rem;'>
                    <strong>What is a Moat?</strong><br>
                    A moat is a sustainable competitive advantage that protects a company's profits
                    from competition. The moat score combines three components:
                    <ol>
                        <li><strong>Pricing Power:</strong> Ability to raise prices without losing customers</li>
                        <li><strong>Operating Leverage:</strong> Revenue growth faster than cost growth</li>
                        <li><strong>ROIC Persistence:</strong> Consistently high returns over time</li>
                    </ol>
                </div>
                """, unsafe_allow_html=True)

                # Moat components
                pricing_power = stock_data.get('pricing_power_score')
                op_leverage = stock_data.get('operating_leverage_score')
                roic_persist = stock_data.get('roic_persistence_score')

                col1, col2, col3 = st.columns(3)

                with col1:
                    if pricing_power is not None:
                        pp_color = "#10b981" if pricing_power >= 70 else "#f59e0b" if pricing_power >= 50 else "#ef4444"
                        st.markdown(f"""
                        <div style='background: white; padding: 1.5rem; border-radius: 8px;
                                    border-left: 4px solid {pp_color}; box-shadow: 0 2px 8px rgba(0,0,0,0.1);'>
                            <div style='font-size: 0.85rem; color: #6b7280;'>Pricing Power</div>
                            <div style='font-size: 2.5rem; font-weight: 700; color: {pp_color};'>
                                {pricing_power:.0f}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                with col2:
                    if op_leverage is not None:
                        ol_color = "#10b981" if op_leverage >= 70 else "#f59e0b" if op_leverage >= 50 else "#ef4444"
                        st.markdown(f"""
                        <div style='background: white; padding: 1.5rem; border-radius: 8px;
                                    border-left: 4px solid {ol_color}; box-shadow: 0 2px 8px rgba(0,0,0,0.1);'>
                            <div style='font-size: 0.85rem; color: #6b7280;'>Operating Leverage</div>
                            <div style='font-size: 2.5rem; font-weight: 700; color: {ol_color};'>
                                {op_leverage:.0f}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                with col3:
                    if roic_persist is not None:
                        rp_color = "#10b981" if roic_persist >= 70 else "#f59e0b" if roic_persist >= 50 else "#ef4444"
                        st.markdown(f"""
                        <div style='background: white; padding: 1.5rem; border-radius: 8px;
                                    border-left: 4px solid {rp_color}; box-shadow: 0 2px 8px rgba(0,0,0,0.1);'>
                            <div style='font-size: 0.85rem; color: #6b7280;'>ROIC Persistence</div>
                            <div style='font-size: 2.5rem; font-weight: 700; color: {rp_color};'>
                                {roic_persist:.0f}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

            # Revenue Growth
            rev_growth = stock_data.get('revenue_growth_3y')
            import pandas as pd
            if rev_growth is not None and not pd.isna(rev_growth):
                st.markdown("---")
                st.markdown("### Revenue Growth (3-Year CAGR)")

                rev_color = "#10b981" if rev_growth >= 15 else "#22c55e" if rev_growth >= 5 else "#f59e0b" if rev_growth >= 0 else "#ef4444"

                st.markdown(f"""
                <div style='background: white; padding: 2rem; border-radius: 12px;
                            border-left: 6px solid {rev_color}; box-shadow: 0 2px 8px rgba(0,0,0,0.1);'>
                    <div style='text-align: center;'>
                        <div style='font-size: 0.9rem; color: #6b7280; margin-bottom: 1rem;'>
                            3-Year Revenue CAGR
                        </div>
                        <div style='font-size: 4rem; font-weight: 700; color: {rev_color};'>
                            {rev_growth:+.1f}%
                        </div>
                        <div style='font-size: 1.1rem; color: #374151; margin-top: 1rem;'>
                            {'FAST GROWTH (>15%)' if rev_growth >= 15 else 'GROWING (>5%)' if rev_growth >= 5 else 'SLOW GROWTH' if rev_growth >= 0 else 'DECLINING'}
                        </div>
                    </div>
                    <div style='background: #f3f4f6; padding: 1rem; border-radius: 6px; margin-top: 1.5rem; font-size: 0.85rem;'>
                        <strong>Why Growth Matters:</strong><br>
                        Declining revenue is a red flag for moat erosion. Even "value" stocks should
                        show stable or growing revenue to confirm their competitive position is intact.
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("---")
                st.info("Revenue growth data not available for this period")

    else:
        # Financial Company Metrics
        st.markdown("### Financial Company Quality Metrics")
        st.info("Quality metrics for financial companies coming soon (ROA, ROE, Efficiency Ratio, NIM, CET1)")


def render_value_score_breakdown(symbol: str, stock_data: dict, is_financial: bool = False):
    """
    Render comprehensive value score breakdown.

    Shows all value metrics and how they contribute to the final value score.
    """
    import streamlit as st
    import plotly.graph_objects as go

    value_score = stock_data.get('value_score_0_100', 0)

    # Header
    score_color = "#10b981" if value_score >= 70 else "#f59e0b" if value_score >= 50 else "#ef4444"

    st.markdown(f"""
    <div style='background: linear-gradient(135deg, {score_color} 0%, {score_color}dd 100%);
                padding: 2rem; border-radius: 12px; margin-bottom: 2rem; text-align: center;'>
        <div style='color: white; font-size: 1.2rem; margin-bottom: 0.5rem; opacity: 0.95;'>
            Value Score
        </div>
        <div style='color: white; font-size: 4rem; font-weight: 700; margin-bottom: 0.5rem;'>
            {value_score:.0f}
        </div>
        <div style='color: white; font-size: 1.1rem; opacity: 0.95;'>
            {'DEEP VALUE' if value_score >= 80 else 'ATTRACTIVE' if value_score >= 70 else 'FAIR VALUE' if value_score >= 50 else 'EXPENSIVE'}
        </div>
    </div>
    """, unsafe_allow_html=True)

    if not is_financial:
        # Non-Financial Value Metrics
        st.markdown("### Value Metrics Breakdown")

        st.markdown("""
        <div style='background: #f3f4f6; padding: 1rem; border-radius: 8px; margin-bottom: 1.5rem;'>
            <strong>How Value Score is Calculated:</strong><br>
            The value score uses modern "Yield" metrics instead of traditional P/E ratios.
            All yields are <strong>ROIC-adjusted</strong> to account for quality differences.
            <br><br>
            <strong>The 5 Yield Metrics:</strong>
            <ol>
                <li><strong>Earnings Yield (EBIT/EV):</strong> Greenblatt Magic Formula yield</li>
                <li><strong>FCF Yield (FCF/EV):</strong> Free cash flow yield</li>
                <li><strong>CFO Yield (CFO/EV):</strong> Operating cash flow yield</li>
                <li><strong>Gross Profit Yield (GP/EV):</strong> Novy-Marx profitability yield</li>
                <li><strong>Shareholder Yield:</strong> Dividends + Buybacks - Issuance</li>
            </ol>
            <br>
            <strong>ROIC Adjustment:</strong> High-ROIC companies "deserve" lower yields (higher valuations).
            The adjustment makes fair comparisons between quality levels.<br>
            Example: Adobe at 5% EY with 40% ROIC → Adjusted EY = 13.3%
        </div>
        """, unsafe_allow_html=True)

        # Create tabs
        value_tabs = st.tabs([
            "All Yields",
            "Earnings & FCF",
            "Cash Flow & GP",
            "Shareholder Returns"
        ])

        # ========== TAB 1: All Yields ==========
        with value_tabs[0]:
            yields_data = []

            yields = [
                ('earnings_yield', 'earnings_yield_adj', 'Earnings Yield (EBIT/EV)', 8, 12),
                ('fcf_yield', 'fcf_yield_adj', 'FCF Yield (FCF/EV)', 6, 10),
                ('cfo_yield', 'cfo_yield_adj', 'CFO Yield (CFO/EV)', 8, 12),
                ('gross_profit_yield', 'gross_profit_yield_adj', 'Gross Profit Yield (GP/EV)', 10, 15)
            ]

            for raw_key, adj_key, name, threshold_low, threshold_high in yields:
                raw_val = stock_data.get(raw_key)
                adj_val = stock_data.get(adj_key)

                if raw_val is not None and adj_val is not None:
                    if adj_val >= threshold_high:
                        status = "DEEP VALUE"
                        color = "#10b981"
                    elif adj_val >= threshold_low:
                        status = "ATTRACTIVE"
                        color = "#22c55e"
                    else:
                        status = "△ FAIR/EXPENSIVE"
                        color = "#f59e0b"

                    yields_data.append({
                        'name': name,
                        'raw': raw_val,
                        'adj': adj_val,
                        'status': status,
                        'color': color
                    })

            # Shareholder Yield (not adjusted)
            sh_yield = stock_data.get('shareholder_yield_%')
            if sh_yield is not None:
                if sh_yield >= 5:
                    status = "EXCELLENT"
                    color = "#10b981"
                elif sh_yield >= 2:
                    status = "GOOD"
                    color = "#22c55e"
                else:
                    status = "△ LOW"
                    color = "#f59e0b"

                yields_data.append({
                    'name': 'Shareholder Yield (Div+Buyback-Dilution)',
                    'raw': sh_yield,
                    'adj': sh_yield,  # Not adjusted
                    'status': status,
                    'color': color
                })

            # Display yields in cards
            for y in yields_data:
                st.markdown(f"""
                <div style='background: white; padding: 1.5rem; border-radius: 8px;
                            border-left: 6px solid {y['color']}; box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                            margin-bottom: 1rem;'>
                    <div style='font-size: 1rem; color: #6b7280; margin-bottom: 1rem;'>
                        <strong>{y['name']}</strong>
                    </div>
                    <div style='display: flex; justify-content: space-around; align-items: center;'>
                        <div style='text-align: center;'>
                            <div style='font-size: 0.85rem; color: #9ca3af;'>Raw</div>
                            <div style='font-size: 2rem; font-weight: 600; color: #6b7280;'>
                                {y['raw']:.1f}%
                            </div>
                        </div>
                        <div style='font-size: 2rem; color: #d1d5db;'>→</div>
                        <div style='text-align: center;'>
                            <div style='font-size: 0.85rem; color: #9ca3af;'>ROIC-Adjusted</div>
                            <div style='font-size: 2.5rem; font-weight: 700; color: {y['color']};'>
                                {y['adj']:.1f}%
                            </div>
                        </div>
                        <div style='text-align: center;'>
                            <div style='font-size: 1rem; font-weight: 600; color: {y['color']};'>
                                {y['status']}
                            </div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        # ========== TAB 2: Earnings & FCF ==========
        with value_tabs[1]:
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("### Earnings Yield (Greenblatt)")

                ey_raw = stock_data.get('earnings_yield')
                ey_adj = stock_data.get('earnings_yield_adj')

                if ey_raw is not None and ey_adj is not None:
                    ey_color = "#10b981" if ey_adj >= 12 else "#22c55e" if ey_adj >= 8 else "#f59e0b"

                    st.markdown(f"""
                    <div style='background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);'>
                        <div style='text-align: center; margin-bottom: 1.5rem;'>
                            <div style='font-size: 0.9rem; color: #6b7280;'>ROIC-Adjusted Earnings Yield</div>
                            <div style='font-size: 3.5rem; font-weight: 700; color: {ey_color};'>
                                {ey_adj:.1f}%
                            </div>
                            <div style='font-size: 0.85rem; color: #9ca3af; margin-top: 0.5rem;'>
                                Raw: {ey_raw:.1f}%
                            </div>
                        </div>
                        <div style='background: #f3f4f6; padding: 1rem; border-radius: 8px; font-size: 0.85rem;'>
                            <strong>Formula:</strong> EBIT / Enterprise Value<br><br>
                            <strong>Joel Greenblatt (2005):</strong> Earnings yield is the inverse
                            of P/E ratio, but uses enterprise value (more accurate for leveraged companies).
                            <br><br>
                            <strong>Target:</strong> >12% = deep value, >8% = attractive
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

            with col2:
                st.markdown("### Free Cash Flow Yield")

                fcf_raw = stock_data.get('fcf_yield')
                fcf_adj = stock_data.get('fcf_yield_adj')

                if fcf_raw is not None and fcf_adj is not None:
                    fcf_color = "#10b981" if fcf_adj >= 10 else "#22c55e" if fcf_adj >= 6 else "#f59e0b"

                    st.markdown(f"""
                    <div style='background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);'>
                        <div style='text-align: center; margin-bottom: 1.5rem;'>
                            <div style='font-size: 0.9rem; color: #6b7280;'>ROIC-Adjusted FCF Yield</div>
                            <div style='font-size: 3.5rem; font-weight: 700; color: {fcf_color};'>
                                {fcf_adj:.1f}%
                            </div>
                            <div style='font-size: 0.85rem; color: #9ca3af; margin-top: 0.5rem;'>
                                Raw: {fcf_raw:.1f}%
                            </div>
                        </div>
                        <div style='background: #f3f4f6; padding: 1rem; border-radius: 8px; font-size: 0.85rem;'>
                            <strong>Formula:</strong> Free Cash Flow / Enterprise Value<br><br>
                            <strong>Why FCF Yield?</strong> FCF is the actual cash available to shareholders
                            after capex. It's harder to manipulate than earnings.
                            <br><br>
                            <strong>Target:</strong> >10% = deep value, >6% = attractive
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

        # ========== TAB 3: Cash Flow & Gross Profit ==========
        with value_tabs[2]:
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("### Operating Cash Flow Yield")

                cfo_raw = stock_data.get('cfo_yield')
                cfo_adj = stock_data.get('cfo_yield_adj')

                if cfo_raw is not None and cfo_adj is not None:
                    cfo_color = "#10b981" if cfo_adj >= 12 else "#22c55e" if cfo_adj >= 8 else "#f59e0b"

                    st.markdown(f"""
                    <div style='background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);'>
                        <div style='text-align: center; margin-bottom: 1.5rem;'>
                            <div style='font-size: 0.9rem; color: #6b7280;'>ROIC-Adjusted CFO Yield</div>
                            <div style='font-size: 3.5rem; font-weight: 700; color: {cfo_color};'>
                                {cfo_adj:.1f}%
                            </div>
                            <div style='font-size: 0.85rem; color: #9ca3af; margin-top: 0.5rem;'>
                                Raw: {cfo_raw:.1f}%
                            </div>
                        </div>
                        <div style='background: #f3f4f6; padding: 1rem; border-radius: 8px; font-size: 0.85rem;'>
                            <strong>Formula:</strong> Operating Cash Flow / Enterprise Value<br><br>
                            <strong>Why CFO?</strong> More stable than FCF (doesn't include capex volatility).
                            Good for companies with lumpy capital spending.
                            <br><br>
                            <strong>Target:</strong> >12% = deep value, >8% = attractive
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

            with col2:
                st.markdown("### Gross Profit Yield (Novy-Marx)")

                gp_raw = stock_data.get('gross_profit_yield')
                gp_adj = stock_data.get('gross_profit_yield_adj')

                if gp_raw is not None and gp_adj is not None:
                    gp_color = "#10b981" if gp_adj >= 15 else "#22c55e" if gp_adj >= 10 else "#f59e0b"

                    st.markdown(f"""
                    <div style='background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);'>
                        <div style='text-align: center; margin-bottom: 1.5rem;'>
                            <div style='font-size: 0.9rem; color: #6b7280;'>ROIC-Adjusted GP Yield</div>
                            <div style='font-size: 3.5rem; font-weight: 700; color: {gp_color};'>
                                {gp_adj:.1f}%
                            </div>
                            <div style='font-size: 0.85rem; color: #9ca3af; margin-top: 0.5rem;'>
                                Raw: {gp_raw:.1f}%
                            </div>
                        </div>
                        <div style='background: #f3f4f6; padding: 1rem; border-radius: 8px; font-size: 0.85rem;'>
                            <strong>Formula:</strong> Gross Profit / Enterprise Value<br><br>
                            <strong>Robert Novy-Marx (2013):</strong> Gross profitability is a better
                            predictor of returns than traditional value metrics.
                            <br><br>
                            <strong>Target:</strong> >15% = deep value, >10% = attractive
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

        # ========== TAB 4: Shareholder Returns ==========
        with value_tabs[3]:
            st.markdown("### Shareholder Yield")

            sh_yield = stock_data.get('shareholder_yield_%')

            if sh_yield is not None:
                sh_color = "#10b981" if sh_yield >= 5 else "#22c55e" if sh_yield >= 2 else "#f59e0b"

                st.markdown(f"""
                <div style='background: white; padding: 2.5rem; border-radius: 12px;
                            border-left: 6px solid {sh_color}; box-shadow: 0 2px 8px rgba(0,0,0,0.1);'>
                    <div style='text-align: center; margin-bottom: 2rem;'>
                        <div style='font-size: 1rem; color: #6b7280; margin-bottom: 1rem;'>
                            Total Shareholder Yield
                        </div>
                        <div style='font-size: 4.5rem; font-weight: 700; color: {sh_color};'>
                            {sh_yield:+.1f}%
                        </div>
                        <div style='font-size: 1.1rem; color: #374151; margin-top: 1rem;'>
                            {'EXCELLENT (>5%)' if sh_yield >= 5 else 'GOOD (>2%)' if sh_yield >= 2 else '△ LOW (<2%)' if sh_yield >= 0 else 'DILUTIVE (Negative)'}
                        </div>
                    </div>

                    <div style='background: #f3f4f6; padding: 1.5rem; border-radius: 8px; font-size: 0.9rem;'>
                        <strong>Formula:</strong><br>
                        Shareholder Yield = (Dividends + Buybacks - Stock Issuance) / Market Cap<br><br>

                        <strong>Why This Matters:</strong><br>
                        Traditional dividend yield ignores buybacks and dilution. Shareholder yield
                        captures the <em>total</em> cash returned to shareholders.<br><br>

                        <strong>Components:</strong>
                        <ul style='margin-top: 0.5rem;'>
                            <li><strong>Dividends:</strong> Cash paid directly to shareholders</li>
                            <li><strong>Buybacks:</strong> Reduce share count, increase ownership %</li>
                            <li><strong>Stock Issuance:</strong> Dilutes shareholders (subtracted)</li>
                        </ul>

                        <strong>Interpretation:</strong>
                        <ul style='margin-top: 0.5rem;'>
                            <li>>5%: Excellent capital allocation</li>
                            <li>2-5%: Good shareholder returns</li>
                            <li>0-2%: Modest returns</li>
                            <li><0%: Dilutive (issuing more stock than returning via div+buybacks)</li>
                        </ul>
                    </div>
                </div>
                """, unsafe_allow_html=True)

    else:
        # Financial Company Metrics
        st.markdown("### Financial Company Value Metrics")
        st.info("Value metrics for financial companies coming soon (P/E, P/B, P/TBV, Dividend Yield)")
