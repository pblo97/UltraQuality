"""
Professional Data Formatters

Consistent formatting for financial data, scores, and metrics.
No emojis, clean presentation for institutional use.
"""

from typing import Optional, Union
import pandas as pd


def format_currency(value: Optional[float], prefix: str = "$", decimals: int = 2) -> str:
    """
    Format currency values with proper separators.

    Args:
        value: Numeric value
        prefix: Currency symbol
        decimals: Number of decimal places

    Returns:
        Formatted string (e.g., "$1,234.56")
    """
    if value is None or pd.isna(value):
        return "N/A"

    try:
        value = float(value)
        if abs(value) >= 1e12:  # Trillions
            return f"{prefix}{value/1e12:,.{decimals}f}T"
        elif abs(value) >= 1e9:  # Billions
            return f"{prefix}{value/1e9:,.{decimals}f}B"
        elif abs(value) >= 1e6:  # Millions
            return f"{prefix}{value/1e6:,.{decimals}f}M"
        elif abs(value) >= 1e3:  # Thousands
            return f"{prefix}{value/1e3:,.{decimals}f}K"
        else:
            return f"{prefix}{value:,.{decimals}f}"
    except (ValueError, TypeError):
        return "N/A"


def format_percentage(
    value: Optional[float],
    decimals: int = 1,
    include_sign: bool = False
) -> str:
    """
    Format percentage values.

    Args:
        value: Numeric value (already in percentage, e.g., 5.2 for 5.2%)
        decimals: Number of decimal places
        include_sign: Whether to include + for positive values

    Returns:
        Formatted string (e.g., "5.2%", "+5.2%")
    """
    if value is None or pd.isna(value):
        return "N/A"

    try:
        value = float(value)
        sign = "+" if include_sign and value > 0 else ""
        return f"{sign}{value:.{decimals}f}%"
    except (ValueError, TypeError):
        return "N/A"


def format_ratio(value: Optional[float], decimals: int = 2, suffix: str = "x") -> str:
    """
    Format ratio values (e.g., P/E, debt/equity).

    Args:
        value: Numeric value
        decimals: Number of decimal places
        suffix: Suffix to append (default "x")

    Returns:
        Formatted string (e.g., "15.2x")
    """
    if value is None or pd.isna(value):
        return "N/A"

    try:
        value = float(value)
        return f"{value:.{decimals}f}{suffix}"
    except (ValueError, TypeError):
        return "N/A"


def format_score(
    score: Optional[float],
    max_score: float = 100,
    decimals: int = 1,
    include_max: bool = False
) -> str:
    """
    Format score values.

    Args:
        score: Numeric score
        max_score: Maximum possible score
        decimals: Number of decimal places
        include_max: Whether to show "/100" suffix

    Returns:
        Formatted string (e.g., "85.0", "85.0/100")
    """
    if score is None or pd.isna(score):
        return "N/A"

    try:
        score = float(score)
        formatted = f"{score:.{decimals}f}"
        if include_max:
            formatted += f"/{max_score:.0f}"
        return formatted
    except (ValueError, TypeError):
        return "N/A"


def format_decision(decision: str) -> str:
    """
    Format decision labels for display.

    Args:
        decision: Raw decision string

    Returns:
        Formatted decision (title case, no emojis)
    """
    decision_map = {
        "BUY": "Buy",
        "STRONG_BUY": "Strong Buy",
        "SELL": "Sell",
        "HOLD": "Hold",
        "MONITOR": "Monitor",
        "AVOID": "Avoid"
    }
    return decision_map.get(decision, decision.title())


def format_guardrails_status(status: str) -> str:
    """
    Format guardrails status for display.

    Args:
        status: Raw status string (VERDE, AMBAR, ROJO)

    Returns:
        Formatted status (Green/Yellow/Red)
    """
    status_map = {
        "VERDE": "Green",
        "AMBAR": "Yellow",
        "ROJO": "Red"
    }
    return status_map.get(status, status.title())


def format_trend(trend: str) -> str:
    """
    Format trend indicators.

    Args:
        trend: Raw trend string

    Returns:
        Formatted trend with arrow symbol
    """
    trend_map = {
        "UPTREND": "↗ Uptrend",
        "DOWNTREND": "↘ Downtrend",
        "NEUTRAL": "→ Neutral",
        "STABLE": "→ Stable",
        "IMPROVING": "↗ Improving",
        "DETERIORATING": "↘ Deteriorating",
        "EXPANDING": "↗ Expanding",
        "COMPRESSING": "↘ Compressing"
    }
    return trend_map.get(trend, trend.title())


def format_large_number(value: Optional[float], decimals: int = 1) -> str:
    """
    Format large numbers with K/M/B/T suffixes.

    Args:
        value: Numeric value
        decimals: Number of decimal places

    Returns:
        Formatted string (e.g., "1.2B")
    """
    if value is None or pd.isna(value):
        return "N/A"

    try:
        value = float(value)
        if abs(value) >= 1e12:
            return f"{value/1e12:,.{decimals}f}T"
        elif abs(value) >= 1e9:
            return f"{value/1e9:,.{decimals}f}B"
        elif abs(value) >= 1e6:
            return f"{value/1e6:,.{decimals}f}M"
        elif abs(value) >= 1e3:
            return f"{value/1e3:,.{decimals}f}K"
        else:
            return f"{value:,.{decimals}f}"
    except (ValueError, TypeError):
        return "N/A"


def format_confidence(confidence: Optional[Union[int, float, str]]) -> str:
    """
    Format confidence levels.

    Args:
        confidence: Confidence value or string

    Returns:
        Formatted confidence (e.g., "High (8/10)", "Medium")
    """
    if confidence is None or pd.isna(confidence):
        return "N/A"

    # Handle numeric confidence (0-10 scale)
    try:
        conf_num = float(confidence)
        if conf_num >= 8:
            level = "High"
        elif conf_num >= 5:
            level = "Medium"
        else:
            level = "Low"
        return f"{level} ({conf_num:.0f}/10)"
    except (ValueError, TypeError):
        pass

    # Handle string confidence
    confidence_map = {
        "high": "High",
        "medium": "Medium",
        "low": "Low",
        "very_high": "Very High",
        "very_low": "Very Low"
    }
    return confidence_map.get(str(confidence).lower(), str(confidence).title())


def format_technical_signal(
    signal: str,
    score: Optional[float] = None,
    short: bool = False
) -> str:
    """
    Format technical analysis signal.

    Args:
        signal: Signal type (BUY/SELL/HOLD)
        score: Optional technical score
        short: Whether to use short format

    Returns:
        Formatted signal string
    """
    signal_map = {
        "BUY": ("Buy", "↗"),
        "STRONG_BUY": ("Strong Buy", "↗↗"),
        "SELL": ("Sell", "↘"),
        "HOLD": ("Hold", "→")
    }

    label, arrow = signal_map.get(signal, (signal.title(), ""))

    if short:
        return arrow

    if score is not None:
        return f"{label} ({score:.0f}/100)"

    return label


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix for truncated text

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)] + suffix


def format_dataframe_display(df: pd.DataFrame, max_rows: int = 100) -> pd.DataFrame:
    """
    Format dataframe for professional display.

    Args:
        df: Input dataframe
        max_rows: Maximum rows to display

    Returns:
        Formatted dataframe
    """
    # Create a copy to avoid modifying original
    display_df = df.head(max_rows).copy()

    # Format numeric columns
    for col in display_df.columns:
        if col.endswith('_%') or 'percent' in col.lower():
            display_df[col] = display_df[col].apply(
                lambda x: format_percentage(x) if pd.notna(x) else "N/A"
            )
        elif col.endswith('_score') or 'score' in col.lower():
            display_df[col] = display_df[col].apply(
                lambda x: format_score(x) if pd.notna(x) else "N/A"
            )
        elif 'price' in col.lower() or 'value' in col.lower():
            display_df[col] = display_df[col].apply(
                lambda x: format_currency(x) if pd.notna(x) else "N/A"
            )

    # Format decision columns
    if 'decision' in display_df.columns:
        display_df['decision'] = display_df['decision'].apply(format_decision)

    # Format guardrails status
    if 'guardrail_status' in display_df.columns:
        display_df['guardrail_status'] = display_df['guardrail_status'].apply(
            format_guardrails_status
        )

    return display_df


def get_status_badge_html(
    status: str,
    status_type: str = "decision"
) -> str:
    """
    Get HTML for status badge.

    Args:
        status: Status value
        status_type: Type of status ("decision", "guardrails", "trend")

    Returns:
        HTML string for badge
    """
    # Color mapping
    if status_type == "decision":
        color_map = {
            "STRONG_BUY": "#0d6efd",  # Blue
            "BUY": "#28a745",          # Green
            "HOLD": "#ffc107",         # Yellow
            "MONITOR": "#6c757d",      # Gray
            "SELL": "#fd7e14",         # Orange
            "AVOID": "#dc3545"         # Red
        }
    elif status_type == "guardrails":
        color_map = {
            "VERDE": "#28a745",        # Green
            "AMBAR": "#ffc107",        # Yellow
            "ROJO": "#dc3545"          # Red
        }
    else:  # trend or generic
        color_map = {
            "UPTREND": "#28a745",
            "DOWNTREND": "#dc3545",
            "NEUTRAL": "#6c757d"
        }

    color = color_map.get(status, "#6c757d")

    return f"""
    <span style="
        padding: 0.25rem 0.75rem;
        border-radius: 0.25rem;
        background-color: {color};
        color: white;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
    ">
        {format_decision(status) if status_type == "decision" else status}
    </span>
    """
