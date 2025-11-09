"""
UltraQuality Screener - Streamlit Web Interface

This is the MAIN FILE for the Streamlit web app.
- Streamlit Cloud is configured to run this file
- The UI loads instantly with lazy imports
- The screener only runs when user clicks the button

For CLI usage, use: python cli_run_screener.py
"""
import streamlit as st
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# NOTE: We import ScreenerPipeline lazily inside the button click
# to avoid blocking the UI load with heavy imports

def recalculate_scores(df, weight_quality, weight_value, threshold_buy, threshold_monitor,
                       threshold_quality_exceptional, exclude_reds):
    """
    Recalculate composite scores and decisions with new parameters.
    This allows interactive adjustment without re-running the entire pipeline.
    """
    df = df.copy()

    # Recalculate composite score with new weights
    df['composite_0_100'] = (
        weight_quality * df['quality_score_0_100'] +
        weight_value * df['value_score_0_100']
    )

    # Recalculate decision logic
    def decide(row):
        composite = row.get('composite_0_100', 0)
        quality = row.get('quality_score_0_100', 0)
        value = row.get('value_score_0_100', 0)
        status = row.get('guardrail_status', 'AMBAR')

        # ROJO = Auto AVOID (accounting red flags)
        if exclude_reds and status == 'ROJO':
            return 'AVOID', 'RED guardrails (accounting concerns)'

        # Exceptional composite score = BUY even with AMBAR
        # BUT: Block if revenue declining OR quality deteriorating (Piotroski for VALUE, Mohanram for GROWTH)
        revenue_growth = row.get('revenue_growth_3y')
        degradation_delta = row.get('quality_degradation_delta')
        degradation_type = row.get('quality_degradation_type')

        if composite >= 85:  # Raised from 80 to 85 (more selective)
            # Check 1: Revenue decline (universal check)
            if revenue_growth is not None and revenue_growth < 0:
                return 'MONITOR', f'High score ({composite:.0f}) but revenue declining ({revenue_growth:.1f}% 3Y)'

            # Check 2: Quality degradation (Piotroski F-Score for VALUE, Mohanram G-Score for GROWTH)
            if degradation_delta is not None and degradation_delta < 0:
                score_name = 'F-Score' if degradation_type == 'VALUE' else 'G-Score'
                return 'MONITOR', f'High score ({composite:.0f}) but {degradation_type} quality degrading ({score_name} Δ{degradation_delta})'

            return 'BUY', f'Exceptional score ({composite:.0f} ≥ 85)'

        # Exceptional Quality companies = BUY even with moderate composite
        # Relaxed for AMBAR: if very high quality, accept lower composite
        # BUT: Block if revenue declining OR quality deteriorating (Piotroski/Mohanram)
        if quality >= threshold_quality_exceptional:
            # Check 1: Revenue decline
            if revenue_growth is not None and revenue_growth < 0:
                return 'MONITOR', f'High quality (Q:{quality:.0f}) but revenue declining ({revenue_growth:.1f}% 3Y)'

            # Check 2: Quality degradation (F-Score for VALUE, G-Score for GROWTH)
            if degradation_delta is not None and degradation_delta < 0:
                score_name = 'F-Score' if degradation_type == 'VALUE' else 'G-Score'
                return 'MONITOR', f'High quality (Q:{quality:.0f}) but {degradation_type} quality degrading ({score_name} Δ{degradation_delta})'

            if composite >= 60:
                return 'BUY', f'Exceptional quality (Q:{quality:.0f} ≥ {threshold_quality_exceptional}, C:{composite:.0f} ≥ 60)'
            elif composite >= 55 and status != 'ROJO':
                return 'BUY', f'High quality override (Q:{quality:.0f} ≥ {threshold_quality_exceptional}, C:{composite:.0f} ≥ 55)'

        # High Quality with AMBAR can still be BUY if composite is decent
        # This prevents great companies (GOOGL, META) from being blocked by AMBAR
        if quality >= 70 and composite >= threshold_buy and status == 'AMBAR':
            return 'BUY', f'High quality + AMBAR (Q:{quality:.0f} ≥ 70, C:{composite:.0f} ≥ {threshold_buy})'

        # Good score + Clean guardrails = BUY
        if composite >= threshold_buy and status == 'VERDE':
            return 'BUY', f'Score {composite:.0f} ≥ {threshold_buy} + Clean'

        # Middle tier = MONITOR
        if composite >= threshold_monitor:
            return 'MONITOR', f'Score {composite:.0f} in range [{threshold_monitor}, {threshold_buy})'

        # Low score = AVOID
        return 'AVOID', f'Score {composite:.0f} < {threshold_monitor}'

    # Apply decision logic and capture reason
    df[['decision', 'decision_reason']] = df.apply(lambda row: pd.Series(decide(row)), axis=1)

    return df

def get_results_with_current_params():
    """
    Get results from session_state and recalculate with current sidebar parameters.
    Returns None if no results available.
    """
    if 'results' not in st.session_state:
        return None

    df = st.session_state['results']

    # Get current sidebar parameters (these are defined later but accessible)
    w_quality = st.session_state.get('weight_quality_slider', 0.65)
    w_value = 1.0 - w_quality
    t_buy = st.session_state.get('threshold_buy_slider', 65)
    t_monitor = st.session_state.get('threshold_monitor_slider', 45)
    t_quality_exc = st.session_state.get('threshold_quality_exceptional_slider', 80)
    excl_reds = st.session_state.get('exclude_reds_checkbox', True)

    # Recalculate with current parameters
    return recalculate_scores(df, w_quality, w_value, t_buy, t_monitor, t_quality_exc, excl_reds)

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
        max_value=100000,
        value=2000,
        step=100,
        help="Minimum market capitalization in millions (default: $2B to avoid small caps)"
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
        min_value=50,
        max_value=700,
        value=500,
        step=50,
        help="Number of stocks to deep-dive after preliminary ranking. 500 stocks = ~4 min with 1300 calls/min API limit"
    )

# Scoring weights
with st.sidebar.expander("⚖️ Scoring Weights", expanded=True):
    weight_quality = st.slider("Quality Weight", 0.0, 1.0, 0.70, 0.05,
                                key='weight_quality_slider',
                                help="QARP default: 0.70 (prioritize exceptional companies with moats)")
    weight_value = 1.0 - weight_quality
    st.write(f"**Value Weight:** {weight_value:.2f}")
    st.caption("✨ Moving sliders will instantly recalculate results")

    # Guidance
    if weight_quality >= 0.75:
        st.success("✅ **Optimal:** 75%+ Quality captures exceptional companies (Buffett-style)")
    elif weight_quality >= 0.70:
        st.success("✅ **Recommended:** 70% Quality = QARP balance (wonderful companies at fair prices)")
    elif weight_quality >= 0.60:
        st.info("💡 **Tip:** 60-70% Quality works but may miss some high-moat companies (GOOGL, META)")
    else:
        st.warning("⚠️ **Warning:** <60% Quality prioritizes value over excellence. Commodities may rank higher than tech giants.")

# Decision thresholds
with st.sidebar.expander("🎯 Decision Thresholds", expanded=True):
    threshold_buy = st.slider("BUY Threshold", 50, 90, 65, 5,
                               key='threshold_buy_slider',
                               help="Minimum composite score for BUY (QARP default: 65)")
    threshold_monitor = st.slider("MONITOR Threshold", 30, 70, 45, 5,
                                   key='threshold_monitor_slider',
                                   help="Minimum composite score for MONITOR (QARP default: 45)")
    threshold_quality_exceptional = st.slider("Quality Exceptional", 70, 95, 85, 5,
                                               key='threshold_quality_exceptional_slider',
                                               help="If Quality ≥ this, force BUY even with lower composite (only truly exceptional companies). Default: 85")

    exclude_reds = st.checkbox("Exclude RED Guardrails", value=True,
                               key='exclude_reds_checkbox',
                               help="Auto-AVOID stocks with accounting red flags")

    st.caption("""
    **Guardrail Colors:**
    - 🟢 VERDE: Clean accounting
    - 🟡 AMBAR: Minor concerns (high-quality companies often have AMBAR)
    - 🔴 ROJO: Red flags (manipulation risk)

    **New:** Quality ≥70 + AMBAR can still be BUY
    """)

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
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["🏠 Home", "📊 Results", "📈 Analytics", "🔎 Calibration", "🔍 Qualitative", "ℹ️ About"])

with tab1:
    st.header("Run Screener")

    # Show existing results summary if available
    if 'results' in st.session_state:
        # Get recalculated results with current slider values
        df_existing = get_results_with_current_params()
        buys_existing = (df_existing['decision'] == 'BUY').sum()
        monitors_existing = (df_existing['decision'] == 'MONITOR').sum()
        timestamp_existing = st.session_state.get('timestamp', datetime.now())
        config_version = st.session_state.get('config_version', 'unknown')

        # Check if results are from old config
        CURRENT_VERSION = "QARP-v3-Moat"  # Updated when major scoring changes (v3 = Moat Score added)
        is_stale = config_version != CURRENT_VERSION

        if is_stale:
            st.warning(f"⚠️ **Results are from older version** ({config_version}). Re-run screener to use latest methodology with **Moat Score** (competitive advantages).")
        else:
            st.success(f"📊 **Latest Results Available** (from {timestamp_existing.strftime('%Y-%m-%d %H:%M:%S')})")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Analyzed", len(df_existing))
        with col2:
            st.metric("🟢 BUY Signals", buys_existing)
        with col3:
            st.metric("🟡 MONITOR", monitors_existing)
        with col4:
            avg = df_existing['composite_0_100'].mean()
            st.metric("Avg Score", f"{avg:.1f}")

        col_btn1, col_btn2 = st.columns([3, 1])
        with col_btn1:
            st.info("👉 Check **Results**, **Analytics**, and **Qualitative** tabs to explore the data")
        with col_btn2:
            if st.button("🗑️ Clear Results", use_container_width=True):
                for key in ['results', 'timestamp', 'config_version']:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()

        st.markdown("---")

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
            status_text.text("Loading modules...")
            progress_bar.progress(3)

            # Lazy import to avoid blocking UI load
            from screener.orchestrator import ScreenerPipeline

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

            # Validate results before saving
            if len(df) == 0:
                st.warning("⚠️ Screening completed but no stocks met the criteria.")
                st.info("💡 Try lowering the minimum Market Cap or Volume thresholds.")
                progress_bar.empty()
                status_text.empty()
            else:
                # Save to session state
                st.session_state['results'] = df
                st.session_state['timestamp'] = datetime.now()
                st.session_state['config_version'] = "QARP-v3-Moat"  # Track methodology version (v3 = Moat Score added)
                st.session_state['output_csv'] = output_csv

                # Show quick summary
                buys = (df['decision'] == 'BUY').sum()
                monitors = (df['decision'] == 'MONITOR').sum()

                st.success(f"✅ Found {buys} BUY signals and {monitors} MONITOR from {len(df)} stocks!")

                # Clear progress indicators
                progress_bar.empty()
                status_text.empty()

                # Force Streamlit to rerun so other tabs show the data
                st.rerun()

        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
            st.exception(e)
            progress_bar.empty()
            status_text.empty()

with tab2:
    st.header("Screening Results")

    if 'results' in st.session_state:
        # Get recalculated results with current slider values
        df = get_results_with_current_params()
        timestamp = st.session_state['timestamp']

        st.caption(f"Last run: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        st.caption(f"⚖️ Current weights: Quality {weight_quality:.0%}, Value {weight_value:.0%}")

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

        # Debug panel - show if ROIC-adjusted yields are present
        config_version = st.session_state.get('config_version', 'unknown')
        if config_version in ['QARP-v2', 'QARP-v3-Moat'] and 'earnings_yield_adj' in df.columns:
            with st.expander("🔧 Debug: ROIC-Adjusted Yields Verification"):
                st.caption("Verify that ROIC adjustments are working correctly")

                # Show examples of adjustments
                debug_cols = ['ticker', 'roic_%', 'moat_score', 'earnings_yield', 'earnings_yield_adj',
                             'value_score_0_100', 'quality_score_0_100', 'decision']
                available_debug_cols = [col for col in debug_cols if col in df.columns]

                if available_debug_cols:
                    st.write("**Sample: Top 10 by Quality Score**")
                    debug_df = df[available_debug_cols].sort_values('quality_score_0_100', ascending=False).head(10)
                    st.dataframe(debug_df, use_container_width=True)

                    st.caption("Expected: High ROIC companies should have earnings_yield_adj > earnings_yield")

        # Display table
        display_cols = [
            'ticker', 'name', 'sector',
            'roic_%',  # NEW: Show ROIC for transparency
            'moat_score',  # NEW: Competitive advantages score
            'composite_0_100',
            'value_score_0_100', 'quality_score_0_100',
            'guardrail_status', 'decision', 'decision_reason'  # NEW: shows WHY
        ]

        available_cols = [col for col in display_cols if col in filtered.columns]

        st.dataframe(
            filtered[available_cols].sort_values('composite_0_100', ascending=False),
            use_container_width=True,
            height=600
        )

        # Show special cases
        with st.expander("🔍 Investigate Specific Companies"):
            search_ticker = st.text_input("Enter ticker(s) - comma separated (e.g., MA,V,GOOGL)", key="search_ticker")
            if search_ticker:
                tickers = [t.strip().upper() for t in search_ticker.split(',')]
                search_df = df[df['ticker'].str.upper().isin(tickers)]

                if not search_df.empty:
                    detail_cols = ['ticker', 'roic_%', 'moat_score', 'earnings_yield', 'earnings_yield_adj',
                                  'value_score_0_100', 'quality_score_0_100', 'composite_0_100',
                                  'guardrail_status', 'decision', 'decision_reason',
                                  'pricing_power_score', 'operating_leverage_score', 'roic_persistence_score']
                    available_detail_cols = [col for col in detail_cols if col in search_df.columns]

                    st.dataframe(search_df[available_detail_cols], use_container_width=True)
                else:
                    st.warning(f"No results found for: {', '.join(tickers)}")

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
        # Get recalculated results with current slider values
        df = get_results_with_current_params()

        # Validate sufficient data
        if len(df) < 5:
            st.warning("⚠️ Not enough data for analytics (minimum 5 stocks required)")
            st.info("💡 Try lowering the Min Market Cap or Volume thresholds.")
        else:
            try:
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

            except Exception as e:
                st.error(f"❌ Error generating analytics: {str(e)}")
                st.info("💡 Try running the screener again with different parameters.")

    else:
        st.info("👈 Run the screener first to see analytics")

with tab4:
    st.header("🔎 Guardrail Calibration Analysis")

    if 'results' in st.session_state:
        df = get_results_with_current_params()

        st.markdown("""
        **Analyze guardrail effectiveness and detect potential false positives.**

        This tool helps you calibrate the screener by showing:
        - Distribution of each guardrail metric
        - Companies affected by each guardrail
        - High-quality companies potentially blocked incorrectly
        - Recommendations for threshold adjustments
        """)

        # Import analyzer
        try:
            from analyze_guardrails import GuardrailAnalyzer

            analyzer = GuardrailAnalyzer(df)

            # Analysis type selector
            analysis_type = st.selectbox(
                "Select Analysis Type",
                options=[
                    'Full Report',
                    '🔍 High-Quality ROJO Deep Dive',
                    'Beneish M-Score',
                    'Altman Z-Score',
                    'Revenue Growth',
                    'M&A / Goodwill',
                    'Share Dilution',
                    'Accruals / NOA'
                ]
            )

            if st.button("🔍 Generate Analysis", type="primary"):
                with st.spinner("Analyzing guardrails..."):
                    if analysis_type == 'Full Report':
                        report = analyzer.generate_full_report()
                    elif analysis_type == '🔍 High-Quality ROJO Deep Dive':
                        report = analyzer.analyze_high_quality_rojo_deep_dive()
                    elif analysis_type == 'Beneish M-Score':
                        report = analyzer._analyze_beneish()
                    elif analysis_type == 'Altman Z-Score':
                        report = analyzer._analyze_altman_z()
                    elif analysis_type == 'Revenue Growth':
                        report = analyzer._analyze_revenue_decline()
                    elif analysis_type == 'M&A / Goodwill':
                        report = analyzer._analyze_mna_flag()
                    elif analysis_type == 'Share Dilution':
                        report = analyzer._analyze_dilution()
                    elif analysis_type == 'Accruals / NOA':
                        report = analyzer._analyze_accruals()

                    # Display in code block for better formatting
                    st.code(report, language="text")

                    # Download button
                    st.download_button(
                        label="📥 Download Report",
                        data=report,
                        file_name=f"guardrail_analysis_{analysis_type.lower().replace(' ', '_').replace('/', '_')}.txt",
                        mime="text/plain"
                    )

            # Quick stats
            st.subheader("📊 Quick Stats")
            col1, col2, col3 = st.columns(3)

            with col1:
                verde_count = (df['guardrail_status'] == 'VERDE').sum()
                verde_pct = (verde_count / len(df)) * 100
                st.metric("VERDE (Clean)", f"{verde_count}", f"{verde_pct:.1f}%")

            with col2:
                ambar_count = (df['guardrail_status'] == 'AMBAR').sum()
                ambar_pct = (ambar_count / len(df)) * 100
                st.metric("AMBAR (Warning)", f"{ambar_count}", f"{ambar_pct:.1f}%")

            with col3:
                rojo_count = (df['guardrail_status'] == 'ROJO').sum()
                rojo_pct = (rojo_count / len(df)) * 100
                st.metric("ROJO (Blocked)", f"{rojo_count}", f"{rojo_pct:.1f}%")

            # Top guardrail reasons
            if 'guardrail_reasons' in df.columns:
                st.subheader("🔝 Top 10 Guardrail Reasons")
                reasons = df['guardrail_reasons'].value_counts().head(10)
                reasons_df = pd.DataFrame({
                    'Reason': reasons.index,
                    'Count': reasons.values,
                    'Percentage': (reasons.values / len(df) * 100).round(1)
                })
                st.dataframe(reasons_df, use_container_width=True)

        except ImportError as e:
            st.error(f"❌ Error loading analysis tool: {str(e)}")
            st.info("Make sure analyze_guardrails.py is in the project directory")
        except Exception as e:
            st.error(f"❌ Error during analysis: {str(e)}")

    else:
        st.info("👈 Run the screener first to analyze guardrails")

with tab5:
    st.header("🔍 Qualitative Analysis")

    if 'results' in st.session_state:
        # Get recalculated results with current slider values
        df = get_results_with_current_params()

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
                        import yaml
                        import os
                        from screener.qualitative import QualitativeAnalyzer
                        from screener.ingest import FMPClient

                        # Load config
                        with open('settings.yaml', 'r') as f:
                            config = yaml.safe_load(f)

                        # Get API key (same logic as orchestrator)
                        api_key = None
                        if 'FMP_API_KEY' in st.secrets:
                            api_key = st.secrets['FMP_API_KEY']
                        elif 'FMP' in st.secrets:
                            api_key = st.secrets['FMP']

                        if not api_key:
                            api_key = os.getenv('FMP_API_KEY')

                        if not api_key:
                            api_key = config['fmp'].get('api_key')

                        if not api_key or api_key.startswith('${'):
                            st.error("FMP_API_KEY not found. Please configure it in Streamlit secrets.")
                            st.stop()

                        # Initialize FMP client and analyzer
                        fmp_client = FMPClient(api_key, config['fmp'])
                        analyzer = QualitativeAnalyzer(fmp_client, config)

                        # Get company data from results for context
                        df = st.session_state['results']
                        stock_data = df[df['ticker'] == selected_ticker].iloc[0]
                        company_type = stock_data.get('company_type', 'unknown')

                        # Run analysis
                        analysis = analyzer.analyze_symbol(
                            selected_ticker,
                            company_type=company_type,
                            peers_df=df
                        )

                        if analysis and 'error' not in analysis:
                            st.session_state[f'qual_{selected_ticker}'] = analysis
                            st.success("✅ Analysis complete!")
                            st.rerun()  # Rerun to show the new results
                        else:
                            st.error(f"❌ Analysis failed: {analysis.get('error', 'Unknown error')}")

                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")

            # Display cached analysis if available
            if f'qual_{selected_ticker}' in st.session_state:
                analysis = st.session_state[f'qual_{selected_ticker}']

                # Check if analysis is from old version (has DEBUG messages)
                intrinsic = analysis.get('intrinsic_value', {})
                notes = intrinsic.get('notes', [])
                has_old_debug = any('DEBUG:' in str(note) for note in notes)

                if has_old_debug:
                    st.warning(f"⚠️ Cached analysis for {selected_ticker} is from an older version with outdated diagnostics.")
                    # Clear the cache
                    del st.session_state[f'qual_{selected_ticker}']
                    st.info("🔄 Cache cleared. Please click the '🔍 Run Deep Analysis' button above again to get fresh results with improved diagnostics.")
                    st.markdown("""
                    **New features you'll get:**
                    - ✅ Auto-detection of company type (non_financial, financial, reit, utility)
                    - ✅ Detailed error messages showing exact failure points and data values
                    - ✅ Color-coded diagnostic messages (green=success, red=error, yellow=warning)
                    - ✅ Specific troubleshooting info (e.g., "OCF=X, capex=Y, base_cf=Z")
                    """)
                    # Don't show anything else - wait for user to click button again
                elif f'qual_{selected_ticker}' in st.session_state:
                    # Only show analysis if it's valid (no DEBUG messages)
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

                    # Insider Activity & Ownership
                    st.subheader("👔 Insider Activity & Ownership")
                    insider = analysis.get('insider_trading', {})

                    if insider:
                        # Ownership metrics
                        col1, col2, col3, col4 = st.columns(4)

                        with col1:
                            insider_own = insider.get('insider_ownership_pct')
                            if insider_own is not None:
                                st.metric("Insider Ownership", f"{insider_own:.2f}%")
                            else:
                                st.metric("Insider Ownership", "N/A")

                        with col2:
                            inst_own = insider.get('institutional_ownership_pct')
                            if inst_own is not None:
                                st.metric("Institutional Own.", f"{inst_own:.1f}%")
                            else:
                                st.metric("Institutional Own.", "N/A")

                        with col3:
                            dilution = insider.get('net_share_issuance_12m_%')
                            if dilution is not None:
                                delta_color = "inverse" if dilution > 0 else "normal"
                                st.metric("Share Change (12M)", f"{dilution:+.1f}%",
                                         delta="Dilution" if dilution > 0 else "Buyback" if dilution < 0 else "Flat",
                                         delta_color=delta_color)
                            else:
                                st.metric("Share Change (12M)", "N/A")

                        with col4:
                            assessment = insider.get('assessment', 'neutral')
                            emoji_map = {'positive': '🟢', 'neutral': '🟡', 'negative': '🔴'}
                            emoji = emoji_map.get(assessment, '🟡')
                            st.metric("Assessment", f"{emoji} {assessment.title()}")

                        # Additional context
                        if insider_own is not None:
                            if insider_own >= 15:
                                st.success("✓ Strong insider ownership (≥15%) indicates good alignment with shareholders")
                            elif insider_own >= 5:
                                st.info("✓ Moderate insider ownership (5-15%)")
                            elif insider_own < 1:
                                st.warning("⚠️ Low insider ownership (<1%) - weak alignment signal")

                    else:
                        st.info("Ownership data not available")

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

                    # Intrinsic Value Estimation
                    st.subheader("💰 Intrinsic Value Estimation")
                    intrinsic = analysis.get('intrinsic_value', {})

                    # Show section if we have intrinsic_value dict (even if current_price is missing)
                    if intrinsic and 'current_price' in intrinsic:
                        col1, col2, col3, col4 = st.columns(4)

                        current_price = intrinsic.get('current_price', 0)

                        with col1:
                            if current_price and current_price > 0:
                                st.metric("Current Price", f"${current_price:.2f}")
                            else:
                                st.metric("Current Price", "N/A")
                                st.caption("⚠️ Price data unavailable")

                        with col2:
                            dcf_val = intrinsic.get('dcf_value')
                            if dcf_val and dcf_val > 0:
                                st.metric("DCF Value", f"${dcf_val:.2f}")
                            else:
                                st.metric("DCF Value", "N/A")

                        with col3:
                            fwd_val = intrinsic.get('forward_multiple_value')
                            if fwd_val and fwd_val > 0:
                                st.metric("Forward Multiple", f"${fwd_val:.2f}")
                            else:
                                st.metric("Forward Multiple", "N/A")

                        with col4:
                            fair_val = intrinsic.get('weighted_value')
                            if fair_val and fair_val > 0:
                                st.metric("Fair Value", f"${fair_val:.2f}")
                            else:
                                st.metric("Fair Value", "N/A")

                        # Show debug notes if present (for troubleshooting)
                        notes = intrinsic.get('notes', [])
                        if notes:
                            with st.expander("📋 Calculation Details & Debug Info"):
                                for note in notes:
                                    if note.startswith('✓'):
                                        st.success(note)
                                    elif note.startswith('✗') or 'ERROR' in note or 'failed' in note.lower():
                                        st.error(note)
                                    elif note.startswith('⚠️') or 'WARNING' in note:
                                        st.warning(note)
                                    else:
                                        st.info(note)

                        # Upside/Downside
                        if intrinsic.get('upside_downside_%') is not None:
                            upside = intrinsic.get('upside_downside_%', 0)
                            assessment = intrinsic.get('valuation_assessment', 'Unknown')
                            confidence = intrinsic.get('confidence', 'Low')

                            # Color based on assessment
                            if assessment == 'Undervalued':
                                color = 'green'
                                emoji = '🟢'
                            elif assessment == 'Overvalued':
                                color = 'red'
                                emoji = '🔴'
                            else:
                                color = 'orange'
                                emoji = '🟡'

                            # Display industry profile
                            industry_profile = intrinsic.get('industry_profile', 'unknown').replace('_', ' ').title()
                            primary_metric = intrinsic.get('primary_metric', 'EV/EBIT')

                            st.markdown(f"### {emoji} {assessment}: {upside:+.1f}% {'upside' if upside > 0 else 'downside'}")
                            st.caption(f"**Industry Profile:** {industry_profile} | **Primary Metric:** {primary_metric}")
                            st.caption(f"**Confidence:** {confidence}")

                            # Explanation
                            with st.expander("📖 Research-Based Valuation Methodology"):
                                st.markdown(f"""
                                ### Industry-Specific Approach

                                **Industry Profile:** {industry_profile}
                                **Primary Metric:** {primary_metric}

                                This valuation uses academic research (Damodaran, NYU Stern; Harbula 2009) to select
                                optimal metrics by industry characteristics:

                                **Valuation Framework:**

                                1. **Capital-Intensive** (Oil/Gas, Utilities, Manufacturing):
                                   - Primary: **EV/EBIT** (D&A reflects actual capex needs)
                                   - Research: More stable than EBITDA for capex-heavy businesses
                                   - Typical multiples: 8-12x EV/EBIT

                                2. **Asset-Light / High-Growth** (Software, Biotech):
                                   - Primary: **EV/Revenue** or **EV/EBITDA**
                                   - Research: Damodaran 2025 - Software ~98x, Biotech ~62x
                                   - Higher multiples reflect growth potential

                                3. **Asset-Based** (Banks, REITs):
                                   - Primary: **P/B** or **P/FFO**
                                   - Research: Book value best for tangible assets
                                   - Conservative multiples: 1.0-1.5x for banks

                                4. **Mature/Stable** (Consumer Staples, Healthcare):
                                   - Primary: **FCF Yield**
                                   - Research: Predictable cash flows enable accurate DCF
                                   - Higher DCF weighting (50%)

                                5. **Cyclical** (Retail, Consumer Discretionary):
                                   - Primary: **EV/EBITDA**
                                   - Research: Use normalized earnings to avoid peak/trough
                                   - Lower DCF weight (harder to project cycles)

                                ---

                                ### DCF Method
                                - **Growth Capex Adjustment**: Only maintenance capex subtracted
                                - High growth (>10% revenue): 50% capex = maintenance
                                - Moderate (5-10%): 70% maintenance
                                - Mature (<5%): 90% maintenance
                                - **WACC**: Industry-adjusted based on risk profile
                                - **Terminal Growth**: 3% perpetual

                                ### Weighting
                                - **Varies by industry** (not fixed 40/40/20)
                                - High-growth: 30% DCF, 70% Multiples
                                - Stable: 50% DCF, 50% Multiples
                                - Default: 40% DCF, 60% Multiples

                                **No P/E ratios used** - Focus on cash flow and operating metrics per best practices.
                                """)

                        # === PRICE PROJECTIONS ===
                        projections = intrinsic.get('price_projections', {})
                        if projections and 'scenarios' in projections:
                            st.markdown("---")
                            st.markdown("### 📈 Price Projections by Scenario")

                            scenarios = projections.get('scenarios', {})

                            if scenarios:
                                # Display as table
                                scenario_names = list(scenarios.keys())

                                # Create columns for each scenario
                                cols = st.columns(len(scenario_names))

                                for i, (scenario_name, data) in enumerate(scenarios.items()):
                                    with cols[i]:
                                        # Emoji based on scenario
                                        if 'Bear' in scenario_name:
                                            emoji = '🐻'
                                            color = '#ff6b6b'
                                        elif 'Bull' in scenario_name:
                                            emoji = '🐂'
                                            color = '#51cf66'
                                        else:
                                            emoji = '📊'
                                            color = '#ffd43b'

                                        st.markdown(f"**{emoji} {scenario_name}**")
                                        st.caption(data.get('description', ''))
                                        st.caption(f"Growth: {data.get('growth_assumption', 'N/A')}")

                                        st.markdown("**Price Targets:**")
                                        st.metric("1 Year", f"${data.get('1Y_target', 0):.2f}",
                                                 delta=data.get('1Y_return', 'N/A'))
                                        st.metric("3 Year", f"${data.get('3Y_target', 0):.2f}",
                                                 delta=data.get('3Y_cagr', 'N/A') + " CAGR")
                                        st.metric("5 Year", f"${data.get('5Y_target', 0):.2f}",
                                                 delta=data.get('5Y_cagr', 'N/A') + " CAGR")

                                st.caption("**Note:** Projections combine revenue growth (70%) with mean reversion to fair value (30%). Not investment advice.")

                    else:
                        st.info("Valuation analysis not available. Run the analysis to see intrinsic value estimates.")
                        # Show debug notes if available
                        if intrinsic.get('notes'):
                            with st.expander("🔍 Debug Information"):
                                for note in intrinsic.get('notes', []):
                                    st.caption(f"• {note}")

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

with tab6:
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
