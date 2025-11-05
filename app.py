"""
Streamlit UI for UltraQuality Screener
"""
import streamlit as st
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from screener.orchestrator import ScreenerPipeline

st.set_page_config(
    page_title="UltraQuality Screener",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Title
st.title("📊 UltraQuality: Quality + Value Screener")
st.markdown("*Screening stocks using fundamental quality and value metrics*")

# Sidebar configuration
st.sidebar.header("⚙️ Configuration")

# Universe filters
with st.sidebar.expander("🌍 Universe Filters", expanded=True):
    min_mcap = st.number_input(
        "Min Market Cap ($M)",
        min_value=100,
        max_value=50000,
        value=500,
        step=100,
        help="Minimum market capitalization in millions"
    )

    min_vol = st.number_input(
        "Min Daily Volume ($M)",
        min_value=1,
        max_value=100,
        value=5,
        step=1,
        help="Minimum average daily dollar volume in millions"
    )

    top_k = st.slider(
        "Top-K Stocks to Analyze",
        min_value=20,
        max_value=300,
        value=150,
        step=10,
        help="Number of stocks to deep-dive after preliminary ranking"
    )

# Scoring weights
with st.sidebar.expander("⚖️ Scoring Weights"):
    weight_value = st.slider("Value Weight", 0.0, 1.0, 0.5, 0.1)
    weight_quality = 1.0 - weight_value
    st.write(f"Quality Weight: {weight_quality:.1f}")

    exclude_reds = st.checkbox("Exclude RED Guardrails", value=True)

# API Key status
st.sidebar.markdown("---")
st.sidebar.subheader("🔑 API Status")
try:
    api_key = st.secrets.get('FMP_API_KEY', '')
    if api_key and not api_key.startswith('your_'):
        st.sidebar.success(f"✓ API Key: {api_key[:10]}...")
    else:
        st.sidebar.error("❌ API Key not configured")
        st.sidebar.info("Add FMP_API_KEY to Streamlit secrets")
except:
    st.sidebar.warning("⚠️ Secrets not accessible")

# Main content
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏠 Home", "📊 Results", "📈 Analytics", "🔍 Qualitative", "ℹ️ About"])

with tab1:
    st.header("Run Screener")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Universe", "2000+", "stocks")
    with col2:
        st.metric("Deep Analysis", f"{top_k}", "top stocks")
    with col3:
        st.metric("Time", "3-5", "minutes")

    st.markdown("---")

    # Big run button
    if st.button("🚀 Run Screener", type="primary", use_container_width=True):

        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()

        try:
            status_text.text("Initializing pipeline...")
            progress_bar.progress(5)

            # Initialize pipeline
            pipeline = ScreenerPipeline('settings.yaml')

            # Override config with UI values
            pipeline.config['universe']['min_market_cap'] = min_mcap * 1_000_000
            pipeline.config['universe']['min_avg_dollar_vol_3m'] = min_vol * 1_000_000
            pipeline.config['universe']['top_k'] = top_k
            pipeline.config['scoring']['weight_value'] = weight_value
            pipeline.config['scoring']['weight_quality'] = weight_quality
            pipeline.config['scoring']['exclude_reds'] = exclude_reds

            status_text.text("Stage 1/6: Building universe...")
            progress_bar.progress(15)

            # Run pipeline
            with st.spinner("Running screening pipeline... This may take 3-5 minutes"):
                output_csv = pipeline.run()

            progress_bar.progress(100)
            status_text.text("✅ Complete!")

            # Success message
            st.success(f"✅ Screening complete! Results saved to {output_csv}")

            # Load and display results
            df = pd.read_csv(output_csv)
            st.session_state['results'] = df
            st.session_state['timestamp'] = datetime.now()

            # Show summary
            st.subheader("📈 Summary")
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Total Analyzed", len(df))
            with col2:
                buys = (df['decision'] == 'BUY').sum()
                st.metric("BUY Signals", buys, delta=None)
            with col3:
                monitors = (df['decision'] == 'MONITOR').sum()
                st.metric("MONITOR", monitors)
            with col4:
                avg_score = df['composite_0_100'].mean()
                st.metric("Avg Score", f"{avg_score:.1f}")

            # Switch to results tab
            st.info("👉 Check the **Results** tab to see detailed data")

        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
            st.exception(e)
            progress_bar.empty()
            status_text.empty()

with tab2:
    st.header("Screening Results")

    if 'results' in st.session_state:
        df = st.session_state['results']
        timestamp = st.session_state['timestamp']

        st.caption(f"Last run: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")

        # Filters
        col1, col2, col3 = st.columns(3)
        with col1:
            decision_filter = st.multiselect(
                "Decision",
                options=['BUY', 'MONITOR', 'AVOID'],
                default=['BUY', 'MONITOR']
            )
        with col2:
            guardrail_filter = st.multiselect(
                "Guardrails",
                options=['VERDE', 'AMBAR', 'ROJO'],
                default=['VERDE', 'AMBAR']
            )
        with col3:
            min_score = st.slider("Min Composite Score", 0, 100, 50)

        # Apply filters
        filtered = df[
            (df['decision'].isin(decision_filter)) &
            (df['guardrail_status'].isin(guardrail_filter)) &
            (df['composite_0_100'] >= min_score)
        ]

        st.write(f"**{len(filtered)}** stocks match filters")

        # Display table
        display_cols = [
            'ticker', 'name', 'sector', 'composite_0_100',
            'value_score_0_100', 'quality_score_0_100',
            'guardrail_status', 'decision', 'notes_short'
        ]

        available_cols = [col for col in display_cols if col in filtered.columns]

        st.dataframe(
            filtered[available_cols].sort_values('composite_0_100', ascending=False),
            use_container_width=True,
            height=600
        )

        # Download button
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Full Results (CSV)",
            data=csv,
            file_name=f"screener_results_{timestamp.strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

    else:
        st.info("👈 Run the screener first to see results here")

with tab3:
    st.header("📈 Analytics & Sector Breakdown")

    if 'results' in st.session_state:
        df = st.session_state['results']

        # Sector breakdown
        st.subheader("Sector Distribution")

        col1, col2 = st.columns([2, 1])

        with col1:
            # Sector counts by decision
            sector_decision = df.groupby(['sector', 'decision']).size().unstack(fill_value=0)

            # Create stacked bar chart
            import plotly.graph_objects as go

            fig = go.Figure()
            for decision in ['BUY', 'MONITOR', 'AVOID']:
                if decision in sector_decision.columns:
                    fig.add_trace(go.Bar(
                        name=decision,
                        x=sector_decision.index,
                        y=sector_decision[decision],
                        marker_color='green' if decision == 'BUY' else 'orange' if decision == 'MONITOR' else 'red'
                    ))

            fig.update_layout(
                barmode='stack',
                title="Stocks by Sector and Decision",
                xaxis_title="Sector",
                yaxis_title="Count",
                height=400,
                xaxis_tickangle=-45
            )

            st.plotly_chart(fig, use_container_width=True)

        with col2:
            # Sector summary table
            sector_summary = df.groupby('sector').agg({
                'composite_0_100': 'mean',
                'ticker': 'count'
            }).round(1)
            sector_summary.columns = ['Avg Score', 'Count']
            sector_summary = sector_summary.sort_values('Avg Score', ascending=False)

            st.dataframe(
                sector_summary,
                use_container_width=True,
                height=400
            )

        st.markdown("---")

        # Rejection reasons analysis
        st.subheader("🚫 Rejection Analysis")

        avoided = df[df['decision'] == 'AVOID']

        col1, col2 = st.columns(2)

        with col1:
            st.metric("Total AVOID", len(avoided), f"{len(avoided)/len(df)*100:.1f}%")

            # Guardrail breakdown
            guardrail_breakdown = avoided['guardrail_status'].value_counts()

            fig = go.Figure(data=[go.Pie(
                labels=guardrail_breakdown.index,
                values=guardrail_breakdown.values,
                marker=dict(colors=['red', 'orange', 'green']),
                hole=0.3
            )])
            fig.update_layout(title="Rejection by Guardrail Status", height=300)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            # Top rejection reasons
            st.write("**Top Rejection Reasons:**")

            if 'guardrail_reasons' in avoided.columns:
                all_reasons = []
                for reasons in avoided['guardrail_reasons'].dropna():
                    all_reasons.extend([r.strip() for r in str(reasons).split(';')])

                if all_reasons:
                    from collections import Counter
                    reason_counts = Counter(all_reasons).most_common(10)

                    reason_df = pd.DataFrame(reason_counts, columns=['Reason', 'Count'])
                    st.dataframe(reason_df, use_container_width=True, height=300)
                else:
                    st.info("No specific reasons recorded")
            else:
                st.info("Guardrail reasons not available")

        st.markdown("---")

        # Score distribution
        st.subheader("📊 Score Distribution")

        col1, col2, col3 = st.columns(3)

        with col1:
            fig = go.Figure(data=[go.Histogram(
                x=df['composite_0_100'],
                nbinsx=20,
                marker_color='lightblue'
            )])
            fig.update_layout(
                title="Composite Score Distribution",
                xaxis_title="Score (0-100)",
                yaxis_title="Count",
                height=300
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig = go.Figure(data=[go.Histogram(
                x=df['value_score_0_100'],
                nbinsx=20,
                marker_color='lightgreen'
            )])
            fig.update_layout(
                title="Value Score Distribution",
                xaxis_title="Score (0-100)",
                yaxis_title="Count",
                height=300
            )
            st.plotly_chart(fig, use_container_width=True)

        with col3:
            fig = go.Figure(data=[go.Histogram(
                x=df['quality_score_0_100'],
                nbinsx=20,
                marker_color='lightcoral'
            )])
            fig.update_layout(
                title="Quality Score Distribution",
                xaxis_title="Score (0-100)",
                yaxis_title="Count",
                height=300
            )
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

        # Value vs Quality scatter
        st.subheader("💎 Value vs Quality Matrix")

        fig = go.Figure()

        for decision in ['BUY', 'MONITOR', 'AVOID']:
            mask = df['decision'] == decision
            fig.add_trace(go.Scatter(
                x=df[mask]['value_score_0_100'],
                y=df[mask]['quality_score_0_100'],
                mode='markers',
                name=decision,
                text=df[mask]['ticker'],
                marker=dict(
                    size=8,
                    color='green' if decision == 'BUY' else 'orange' if decision == 'MONITOR' else 'red',
                    opacity=0.6
                )
            ))

        fig.add_hline(y=60, line_dash="dash", line_color="gray", annotation_text="Quality Threshold")
        fig.add_vline(x=60, line_dash="dash", line_color="gray", annotation_text="Value Threshold")

        fig.update_layout(
            title="Value vs Quality Positioning",
            xaxis_title="Value Score (0-100)",
            yaxis_title="Quality Score (0-100)",
            height=500
        )

        st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("👈 Run the screener first to see analytics")

with tab4:
    st.header("🔍 Qualitative Analysis")

    if 'results' in st.session_state:
        df = st.session_state['results']

        st.markdown("""
        Deep-dive qualitative analysis for individual stocks.
        Select a ticker to get detailed fundamental analysis, moats, risks, and insider activity.
        """)

        # Ticker selection
        col1, col2 = st.columns([1, 3])

        with col1:
            # Filter by decision first
            decision_qual = st.selectbox(
                "Filter by Decision",
                options=['All', 'BUY', 'MONITOR', 'AVOID'],
                index=0
            )

            if decision_qual == 'All':
                tickers = df['ticker'].sort_values().tolist()
            else:
                tickers = df[df['decision'] == decision_qual]['ticker'].sort_values().tolist()

            selected_ticker = st.selectbox(
                "Select Ticker",
                options=tickers,
                index=0 if tickers else None
            )

        with col2:
            if selected_ticker:
                # Get stock info
                stock_data = df[df['ticker'] == selected_ticker].iloc[0]

                # Display summary card
                st.markdown(f"### {stock_data['name']} ({selected_ticker})")

                col_a, col_b, col_c, col_d = st.columns(4)
                with col_a:
                    st.metric("Decision", stock_data['decision'])
                with col_b:
                    st.metric("Composite Score", f"{stock_data['composite_0_100']:.1f}")
                with col_c:
                    st.metric("Value Score", f"{stock_data['value_score_0_100']:.1f}")
                with col_d:
                    st.metric("Quality Score", f"{stock_data['quality_score_0_100']:.1f}")

        st.markdown("---")

        if selected_ticker:
            # Run qualitative analysis button
            if st.button(f"🔍 Run Deep Analysis for {selected_ticker}", type="primary"):
                with st.spinner(f"Analyzing {selected_ticker}... This may take 30-60 seconds"):
                    try:
                        from qualitative.analyst import QualitativeAnalyst

                        analyst = QualitativeAnalyst('settings.yaml')
                        analysis = analyst.analyze_symbol(selected_ticker)

                        if analysis and 'error' not in analysis:
                            st.session_state[f'qual_{selected_ticker}'] = analysis
                            st.success("✅ Analysis complete!")
                        else:
                            st.error(f"❌ Analysis failed: {analysis.get('error', 'Unknown error')}")

                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")

            # Display cached analysis if available
            if f'qual_{selected_ticker}' in st.session_state:
                analysis = st.session_state[f'qual_{selected_ticker}']

                # Business Summary
                st.subheader("📝 Business Summary")
                st.write(analysis.get('business_summary', 'Not available'))

                st.markdown("---")

                # Moats
                col1, col2 = st.columns(2)

                with col1:
                    st.subheader("🏰 Competitive Moats")
                    moats = analysis.get('moats', [])
                    if moats:
                        for moat in moats:
                            st.markdown(f"- {moat}")
                    else:
                        st.info("No clear moats identified")

                with col2:
                    st.subheader("⚠️ Key Risks")
                    risks = analysis.get('risks', [])
                    if risks:
                        for risk in risks:
                            st.markdown(f"- {risk}")
                    else:
                        st.info("No major risks identified")

                st.markdown("---")

                # Insider Activity
                st.subheader("👔 Insider Activity")
                insider = analysis.get('insider_trading', {})

                if insider:
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        st.metric("Insider Buys (6M)", insider.get('buys_6m', 0))
                    with col2:
                        st.metric("Insider Sells (6M)", insider.get('sells_6m', 0))
                    with col3:
                        sentiment = "Bullish" if insider.get('buys_6m', 0) > insider.get('sells_6m', 0) else "Bearish" if insider.get('sells_6m', 0) > insider.get('buys_6m', 0) else "Neutral"
                        st.metric("Sentiment", sentiment)
                else:
                    st.info("Insider data not available")

                st.markdown("---")

                # Recent News
                st.subheader("📰 Recent News & Events")
                news = analysis.get('recent_news', [])

                if news:
                    for item in news[:5]:
                        st.markdown(f"**{item.get('date', 'N/A')}**: {item.get('headline', 'No headline')}")
                        st.caption(item.get('summary', '')[:200])
                else:
                    st.info("No recent news available")

                st.markdown("---")

                # Fundamental Metrics Deep Dive
                st.subheader("📊 Fundamental Metrics")

                col1, col2, col3 = st.columns(3)

                with col1:
                    st.write("**Valuation**")
                    if not stock_data.get('is_financial', False):
                        st.metric("EV/EBIT", f"{stock_data.get('ev_ebit_ttm', 0):.2f}")
                        st.metric("P/E", f"{stock_data.get('pe_ttm', 0):.2f}")
                        st.metric("P/B", f"{stock_data.get('pb_ttm', 0):.2f}")
                    else:
                        st.metric("P/E", f"{stock_data.get('pe_ttm', 0):.2f}")
                        st.metric("P/B", f"{stock_data.get('pb_ttm', 0):.2f}")

                with col2:
                    st.write("**Quality**")
                    if not stock_data.get('is_financial', False):
                        st.metric("ROIC", f"{stock_data.get('roic_%', 0):.1f}%")
                        st.metric("FCF Margin", f"{stock_data.get('fcf_margin_%', 0):.1f}%")
                        st.metric("Gross Profits/Assets", f"{stock_data.get('grossProfits_to_assets', 0):.2f}")
                    else:
                        st.metric("ROE", f"{stock_data.get('roe_%', 0):.1f}%")
                        st.metric("ROA", f"{stock_data.get('roa_%', 0):.1f}%")

                with col3:
                    st.write("**Guardrails**")
                    st.metric("Status", stock_data.get('guardrail_status', 'N/A'))
                    if 'altman_z' in stock_data:
                        st.metric("Altman Z-Score", f"{stock_data.get('altman_z', 0):.2f}")
                    if 'beneish_m' in stock_data:
                        st.metric("Beneish M-Score", f"{stock_data.get('beneish_m', 0):.2f}")

            else:
                st.info(f"👆 Click the button above to run qualitative analysis for {selected_ticker}")

    else:
        st.info("👈 Run the screener first to access qualitative analysis")

with tab5:
    st.header("About UltraQuality Screener")

    st.markdown("""
    ### 🎯 What It Does

    UltraQuality combines **Quality** and **Value** investing principles to screen stocks:

    - **Value Metrics**: EV/EBIT, P/E, P/B, Shareholder Yield
    - **Quality Metrics**: ROIC, ROA/ROE, FCF Margin, Efficiency Ratios
    - **Guardrails**: Altman Z-Score, Beneish M-Score, Accruals Analysis

    ### 📊 Asset Types Supported

    - **Non-Financials**: Manufacturing, Tech, Services, Consumer
    - **Financials**: Banks, Insurance, Asset Management
    - **REITs**: Real Estate Investment Trusts

    ### 🔍 Methodology

    1. **Universe Building**: Filter by market cap and volume
    2. **Top-K Selection**: Preliminary ranking
    3. **Feature Calculation**: Value & Quality metrics
    4. **Guardrails**: Accounting quality checks
    5. **Scoring**: Industry-normalized z-scores
    6. **Decision**: BUY / MONITOR / AVOID

    ### ⚖️ Scoring Formula

    ```
    Composite Score = (Value Weight × Value Score) + (Quality Weight × Quality Score)

    Decision:
    - Score ≥ 75 + VERDE → BUY
    - Score 60-75 or AMBAR → MONITOR
    - Score < 60 or ROJO → AVOID
    ```

    ### 📚 References

    - Altman Z-Score (1968) - Bankruptcy prediction
    - Beneish M-Score (1999) - Earnings manipulation detection
    - Sloan (1996) - Accruals anomaly
    - Novy-Marx (2013) - Gross profitability premium

    ### ⚠️ Disclaimer

    This tool is for **educational and research purposes only**.
    It is NOT investment advice. Always conduct your own due diligence
    and consult with a qualified financial advisor before making
    investment decisions.

    ### 🔗 Links

    - [Documentation](https://github.com/pblo97/UltraQuality)
    - [FMP API](https://financialmodelingprep.com)
    """)

# Footer
st.sidebar.markdown("---")
st.sidebar.caption("UltraQuality v1.0")
st.sidebar.caption("Powered by FMP API")
