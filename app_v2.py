"""
UltraQuality Stock Screener - Professional Dashboard v2.0

Optimized, modular, and professional interface for institutional-grade stock screening.

Key Improvements:
- Modular architecture (components, pages, utils)
- Professional design (no emojis, clean layout)
- Performance optimized (lazy loading, caching)
- Interactive and educational
- Responsive and accessible

Usage:
    streamlit run app_v2.py
"""

import streamlit as st
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Configure page
st.set_page_config(
    page_title="UltraQuality Stock Screener",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://github.com/yourusername/UltraQuality',
        'Report a bug': 'https://github.com/yourusername/UltraQuality/issues',
        'About': 'Professional stock screener based on academic research'
    }
)

# Custom CSS for professional styling
st.markdown("""
<style>
    /* Hide default Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Professional color scheme */
    :root {
        --primary-color: #0d6efd;
        --success-color: #28a745;
        --warning-color: #ffc107;
        --danger-color: #dc3545;
        --info-color: #0dcaf0;
        --dark-color: #212529;
        --light-color: #f8f9fa;
    }

    /* Clean headers */
    h1, h2, h3 {
        font-weight: 600;
        color: var(--dark-color);
    }

    /* Improved spacing */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    /* Professional buttons */
    .stButton button {
        border-radius: 0.375rem;
        font-weight: 500;
        padding: 0.5rem 1rem;
        transition: all 0.2s;
    }

    .stButton button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }

    /* Clean tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
        border-bottom: 2px solid #e9ecef;
    }

    .stTabs [data-baseweb="tab"] {
        padding: 0.75rem 1rem;
        font-weight: 500;
    }

    /* Metric cards enhancement */
    [data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 700;
    }

    /* Table styling */
    .dataframe {
        font-size: 0.9rem;
    }

    .dataframe thead th {
        background-color: var(--light-color);
        font-weight: 600;
    }

    /* Sidebar styling */
    .css-1d391kg {
        background-color: var(--light-color);
    }

    /* Info boxes */
    .stAlert {
        border-radius: 0.5rem;
        border-left-width: 4px;
    }
</style>
""", unsafe_allow_html=True)


# =====================================
# Sidebar - Navigation & Settings
# =====================================

with st.sidebar:
    st.title("UltraQuality")
    st.caption("Professional Stock Screener")

    st.divider()

    # Navigation
    page = st.radio(
        "Navigation",
        ["Screener", "Analysis", "Education", "Settings"],
        label_visibility="collapsed"
    )

    st.divider()

    # Quick Stats (if screener has run)
    if 'screener_results' in st.session_state and st.session_state.screener_results is not None:
        df = st.session_state.screener_results

        st.subheader("Session Summary")

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Stocks", len(df))
            st.metric(
                "Buy Signals",
                len(df[df['decision'] == 'BUY']) if 'decision' in df.columns else 0
            )
        with col2:
            avg_quality = df['quality_score_0_100'].mean() if 'quality_score_0_100' in df.columns else 0
            st.metric("Avg Quality", f"{avg_quality:.1f}")
            avg_composite = df['composite_0_100'].mean() if 'composite_0_100' in df.columns else 0
            st.metric("Avg Composite", f"{avg_composite:.1f}")

    st.divider()

    # Session info
    st.caption(f"Session: {datetime.now().strftime('%Y-%m-%d %H:%M')}")


# =====================================
# Page Routing
# =====================================

if page == "Screener":
    # Load screener page (lazy import)
    try:
        from src.ui.pages import screener_page
        screener_page.render()
    except ImportError:
        st.error("Screener module not found. Using fallback.")
        _render_screener_fallback()

elif page == "Analysis":
    try:
        from src.ui.pages import analysis_page
        analysis_page.render()
    except ImportError:
        st.error("Analysis module not found. Using fallback.")
        _render_analysis_fallback()

elif page == "Education":
    try:
        from src.ui.pages import education_page
        education_page.render()
    except ImportError:
        st.error("Education module not found. Using fallback.")
        _render_education_fallback()

elif page == "Settings":
    try:
        from src.ui.pages import settings_page
        settings_page.render()
    except ImportError:
        st.error("Settings module not found. Using fallback.")
        _render_settings_fallback()


# =====================================
# Fallback Pages (Minimal Implementation)
# =====================================

def _render_screener_fallback():
    """Minimal screener page if module not found."""
    st.title("Stock Screener")
    st.info("Loading screener interface...")

    st.markdown("""
    ### Features
    - Quality-at-Reasonable-Price (QARP) methodology
    - Academic research-based scoring
    - Multi-dimensional guardrails
    - Technical analysis integration
    - Institutional-grade signals
    """)

    if st.button("Run Screener", type="primary"):
        with st.spinner("Running screener pipeline..."):
            try:
                # Import and run screener
                from screener.orchestrator import ScreenerPipeline
                import yaml

                # Load config
                with open('settings.yaml', 'r') as f:
                    config = yaml.safe_load(f)

                # Run pipeline
                pipeline = ScreenerPipeline(config)
                results_df = pipeline.run()

                # Store in session state
                st.session_state.screener_results = results_df
                st.success(f"Screener completed: {len(results_df)} stocks analyzed")
                st.rerun()

            except Exception as e:
                st.error(f"Screener error: {e}")
                import traceback
                st.code(traceback.format_exc())


def _render_analysis_fallback():
    """Minimal analysis page."""
    st.title("Stock Analysis")

    if 'screener_results' not in st.session_state:
        st.info("Run the screener first to analyze stocks.")
        return

    df = st.session_state.screener_results

    # Stock selector
    ticker = st.selectbox(
        "Select Stock",
        df['ticker'].tolist() if 'ticker' in df.columns else []
    )

    if ticker:
        st.subheader(f"Analysis: {ticker}")

        # Show stock data
        stock_data = df[df['ticker'] == ticker].iloc[0]

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Decision", stock_data.get('decision', 'N/A'))
        with col2:
            st.metric("Composite Score", f"{stock_data.get('composite_0_100', 0):.1f}")
        with col3:
            st.metric("Quality Score", f"{stock_data.get('quality_score_0_100', 0):.1f}")
        with col4:
            st.metric("Value Score", f"{stock_data.get('value_score_0_100', 0):.1f}")

        st.divider()

        # Show all data
        st.subheader("Full Data")
        st.json(stock_data.to_dict())


def _render_education_fallback():
    """Minimal education page."""
    st.title("Investment Education")

    st.markdown("""
    ## Quality-at-Reasonable-Price (QARP) Philosophy

    Our screening methodology combines:

    ### Quality Metrics (70% weight)
    - **ROIC**: Return on Invested Capital (>15% target)
    - **FCF Margin**: Free Cash Flow / Revenue (>10% target)
    - **Moat Score**: Competitive advantage indicators
    - **Earnings Quality**: FCF/NI ratio, accruals analysis

    ### Value Metrics (30% weight)
    - **EV/EBIT**: Enterprise Value / Earnings Before Interest & Tax
    - **FCF Yield**: Free Cash Flow / Enterprise Value
    - **Gross Profit Yield**: Gross Profit / Enterprise Value
    - **Shareholder Yield**: Dividends + Buybacks - Issuance

    ### Guardrails
    - Altman Z-Score (bankruptcy risk)
    - Beneish M-Score (earnings manipulation)
    - Cash conversion quality
    - Debt sustainability

    ### Academic Research
    Our methodology is based on peer-reviewed research:
    - Greenblatt (2005) - Magic Formula
    - Piotroski (2000) - F-Score
    - Novy-Marx (2013) - Gross Profitability Premium
    - Jegadeesh & Titman (1993) - Momentum
    """)


def _render_settings_fallback():
    """Minimal settings page."""
    st.title("Settings")

    st.markdown("""
    ### Configuration

    Edit `settings.yaml` to customize:

    - **Universe filters**: Market cap, volume, exchanges
    - **Scoring weights**: Quality vs Value balance
    - **Decision thresholds**: BUY/MONITOR/AVOID cutoffs
    - **Guardrail thresholds**: Risk tolerance levels

    ### API Configuration

    Set your FMP API key in `.env`:
    ```bash
    FMP_API_KEY=your_api_key_here
    ```
    """)

    # Show current config
    try:
        import yaml
        with open('settings.yaml', 'r') as f:
            config = yaml.safe_load(f)

        st.subheader("Current Configuration")
        st.json(config)
    except Exception as e:
        st.warning(f"Could not load settings.yaml: {e}")


# =====================================
# Footer
# =====================================

st.divider()
st.caption("UltraQuality v2.0 | Professional Stock Screener | Built with Academic Research")
