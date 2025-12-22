"""
Professional Card Components

Clean, consistent card components without emojis.
Designed for institutional-grade presentation.
"""

import streamlit as st
from typing import Optional, Dict, Any


def metric_card(
    label: str,
    value: str,
    delta: Optional[str] = None,
    delta_color: str = "normal",
    help_text: Optional[str] = None,
    inverse: bool = False
):
    """
    Display a metric card with optional delta and help text.

    Args:
        label: Metric label
        value: Metric value (formatted)
        delta: Change indicator (e.g., "+5.2%")
        delta_color: "normal", "inverse", or "off"
        help_text: Tooltip text explaining the metric
        inverse: If True, negative delta is good (e.g., for expense ratios)
    """
    st.metric(
        label=label,
        value=value,
        delta=delta,
        delta_color=delta_color,
        help=help_text
    )


def score_card(
    title: str,
    score: float,
    max_score: float = 100,
    status: Optional[str] = None,
    description: Optional[str] = None
):
    """
    Display a score card with visual indicator.

    Args:
        title: Card title
        score: Numeric score
        max_score: Maximum possible score (default 100)
        status: Status badge (e.g., "EXCELLENT", "GOOD", "POOR")
        description: Explanatory text
    """
    # Determine color based on score
    if score >= 80:
        color = "#28a745"  # Green
        badge_color = "green"
    elif score >= 60:
        color = "#ffc107"  # Yellow
        badge_color = "orange"
    elif score >= 40:
        color = "#fd7e14"  # Orange
        badge_color = "orange"
    else:
        color = "#dc3545"  # Red
        badge_color = "red"

    # Create card container
    with st.container():
        st.markdown(
            f"""
            <div style="
                padding: 1.5rem;
                border-radius: 0.5rem;
                border-left: 4px solid {color};
                background-color: rgba(255, 255, 255, 0.05);
                margin-bottom: 1rem;
            ">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                    <h4 style="margin: 0; font-size: 1rem; font-weight: 600;">{title}</h4>
                    {f'<span style="padding: 0.25rem 0.75rem; border-radius: 0.25rem; background-color: var(--{badge_color}); font-size: 0.75rem; font-weight: 600;">{status}</span>' if status else ''}
                </div>
                <div style="font-size: 2rem; font-weight: 700; color: {color};">
                    {score:.1f}<span style="font-size: 1rem; color: #6c757d;">/{max_score}</span>
                </div>
                {f'<p style="margin-top: 0.5rem; font-size: 0.875rem; color: #6c757d;">{description}</p>' if description else ''}
            </div>
            """,
            unsafe_allow_html=True
        )


def signal_card(
    signal: str,
    confidence: Optional[int] = None,
    reasoning: Optional[str] = None,
    warnings: Optional[list] = None
):
    """
    Display a trading signal card with confidence level.

    Args:
        signal: Signal type ("BUY", "SELL", "HOLD", "STRONG_BUY", "MONITOR", "AVOID")
        confidence: Confidence level 0-10
        reasoning: Explanation for the signal
        warnings: List of warning messages
    """
    # Signal configuration
    signal_config = {
        "STRONG_BUY": {"color": "#0d6efd", "label": "Strong Buy", "icon": "▲▲"},
        "BUY": {"color": "#28a745", "label": "Buy", "icon": "▲"},
        "HOLD": {"color": "#ffc107", "label": "Hold", "icon": "■"},
        "MONITOR": {"color": "#6c757d", "label": "Monitor", "icon": "○"},
        "SELL": {"color": "#fd7e14", "label": "Sell", "icon": "▼"},
        "AVOID": {"color": "#dc3545", "label": "Avoid", "icon": "✕"}
    }

    config = signal_config.get(signal, signal_config["HOLD"])

    # Create signal card
    with st.container():
        st.markdown(
            f"""
            <div style="
                padding: 1.5rem;
                border-radius: 0.5rem;
                border: 2px solid {config['color']};
                background: linear-gradient(135deg, {config['color']}15, transparent);
                margin-bottom: 1rem;
            ">
                <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem;">
                    <span style="font-size: 2rem;">{config['icon']}</span>
                    <div>
                        <h3 style="margin: 0; font-size: 1.5rem; font-weight: 700; color: {config['color']};">
                            {config['label']}
                        </h3>
                        {f'<p style="margin: 0; font-size: 0.875rem; color: #6c757d;">Confidence: {confidence}/10</p>' if confidence is not None else ''}
                    </div>
                </div>
                {f'<p style="margin-bottom: 1rem; line-height: 1.6;">{reasoning}</p>' if reasoning else ''}
                {_render_warnings(warnings) if warnings else ''}
            </div>
            """,
            unsafe_allow_html=True
        )


def _render_warnings(warnings: list) -> str:
    """Helper to render warnings list."""
    if not warnings:
        return ""

    warning_items = "".join([
        f'<li style="margin-bottom: 0.25rem;">{warning}</li>'
        for warning in warnings
    ])

    return f"""
    <div style="
        padding: 0.75rem;
        border-radius: 0.25rem;
        background-color: #fff3cd;
        border-left: 3px solid #ffc107;
    ">
        <strong style="color: #856404;">Considerations:</strong>
        <ul style="margin: 0.5rem 0 0 1rem; padding: 0;">
            {warning_items}
        </ul>
    </div>
    """


def info_card(
    title: str,
    content: str,
    card_type: str = "info"
):
    """
    Display an informational card.

    Args:
        title: Card title
        content: Card content (supports markdown)
        card_type: "info", "success", "warning", or "error"
    """
    type_config = {
        "info": {"color": "#0dcaf0", "bg": "#cff4fc", "text": "#055160"},
        "success": {"color": "#28a745", "bg": "#d1e7dd", "text": "#0f5132"},
        "warning": {"color": "#ffc107", "bg": "#fff3cd", "text": "#856404"},
        "error": {"color": "#dc3545", "bg": "#f8d7da", "text": "#842029"}
    }

    config = type_config.get(card_type, type_config["info"])

    st.markdown(
        f"""
        <div style="
            padding: 1rem;
            border-radius: 0.5rem;
            background-color: {config['bg']};
            border-left: 4px solid {config['color']};
            margin-bottom: 1rem;
        ">
            <h5 style="margin: 0 0 0.5rem 0; color: {config['text']}; font-weight: 600;">
                {title}
            </h5>
            <div style="color: {config['text']}; line-height: 1.6;">
                {content}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def comparison_card(
    items: list[Dict[str, Any]],
    highlight_best: bool = True
):
    """
    Display a comparison card with multiple items.

    Args:
        items: List of dicts with keys: label, value, description, is_best
        highlight_best: Whether to highlight the best option

    Example:
        items = [
            {"label": "Current Price", "value": "$150.00", "description": "As of today"},
            {"label": "Fair Value", "value": "$175.00", "description": "DCF estimate", "is_best": True},
            {"label": "52-Week High", "value": "$200.00", "description": "Historical peak"},
        ]
    """
    # Generate comparison rows
    rows_html = ""
    for item in items:
        is_best = item.get("is_best", False) and highlight_best
        bg_color = "#e7f3ff" if is_best else "transparent"
        border = "2px solid #0d6efd" if is_best else "1px solid #dee2e6"

        rows_html += f"""
        <div style="
            padding: 0.75rem;
            margin-bottom: 0.5rem;
            border-radius: 0.25rem;
            background-color: {bg_color};
            border: {border};
            display: flex;
            justify-content: space-between;
            align-items: center;
        ">
            <div>
                <div style="font-weight: 600; margin-bottom: 0.25rem;">{item['label']}</div>
                <div style="font-size: 0.875rem; color: #6c757d;">{item.get('description', '')}</div>
            </div>
            <div style="font-size: 1.25rem; font-weight: 700; color: #212529;">
                {item['value']}
            </div>
        </div>
        """

    st.markdown(
        f"""
        <div style="padding: 1rem; border-radius: 0.5rem; border: 1px solid #dee2e6; background-color: #ffffff;">
            {rows_html}
        </div>
        """,
        unsafe_allow_html=True
    )
