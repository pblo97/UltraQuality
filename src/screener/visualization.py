"""
Visualization module for technical analysis and risk management.

Provides interactive charts showing:
- Price levels (current, MA50, MA200)
- Entry levels (scale-in tranches)
- Stop loss levels (aggressive/moderate/conservative)
- Profit targets
- Overextension zones
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Dict, List, Optional
import pandas as pd


def create_price_levels_chart(
    symbol: str,
    current_price: float,
    ma_50: float,
    ma_200: float,
    risk_management: Dict,
    overextension_risk: int,
    distance_ma200: float,
    historical_prices: Optional[List[Dict]] = None
) -> go.Figure:
    """
    Create interactive price levels chart showing entry, stop, and target levels.

    Args:
        symbol: Stock symbol
        current_price: Current stock price
        ma_50: 50-day moving average
        ma_200: 200-day moving average
        risk_management: Risk management recommendations dict
        overextension_risk: Overextension risk score (0-7)
        distance_ma200: Distance from MA200 in %
        historical_prices: Optional list of historical price data

    Returns:
        Plotly figure object
    """
    fig = go.Figure()

    # Add historical price line if available
    if historical_prices and len(historical_prices) > 0:
        dates = [p['date'] for p in historical_prices[-90:]]  # Last 90 days
        prices = [p['close'] for p in historical_prices[-90:]]

        fig.add_trace(go.Scatter(
            x=dates,
            y=prices,
            mode='lines',
            name=f'{symbol} Price',
            line=dict(color='#1f77b4', width=2),
            hovertemplate='%{y:.2f}<extra></extra>'
        ))

    # Get risk management data
    entry_strategy = risk_management.get('entry_strategy', {})
    stop_loss = risk_management.get('stop_loss', {})
    profit_taking = risk_management.get('profit_taking', {})

    # Determine price range for chart
    all_prices = [current_price, ma_50, ma_200]

    # Add entry levels
    entry_levels = []
    if 'tranche_1' in entry_strategy:
        # Parse tranche prices from strings like "25% NOW at $175.00"
        for i in range(1, 4):
            tranche_key = f'tranche_{i}'
            if tranche_key in entry_strategy:
                tranche_str = entry_strategy[tranche_key]
                # Extract price from string
                if '$' in tranche_str:
                    try:
                        price_str = tranche_str.split('$')[1].split()[0]
                        price = float(price_str.replace(',', ''))
                        entry_levels.append({
                            'price': price,
                            'label': f'Tranche {i}',
                            'color': '#2ca02c' if i == 1 else '#98df8a'
                        })
                        all_prices.append(price)
                    except:
                        pass
    elif 'entry_price' in entry_strategy:
        # Full entry
        try:
            price_str = entry_strategy['entry_price'].replace('$', '').replace(',', '')
            price = float(price_str)
            entry_levels.append({
                'price': price,
                'label': 'Entry',
                'color': '#2ca02c'
            })
            all_prices.append(price)
        except:
            pass

    # Add stop loss levels
    stop_levels = []
    stops = stop_loss.get('stops', {})
    stop_colors = {
        'aggressive': '#d62728',
        'moderate': '#ff7f0e',
        'conservative': '#ffbb78'
    }

    for stop_type in ['aggressive', 'moderate', 'conservative']:
        if stop_type in stops:
            stop_data = stops[stop_type]
            level_str = stop_data.get('level', '')
            if '$' in level_str:
                try:
                    price_str = level_str.replace('$', '').split()[0].replace(',', '')
                    price = float(price_str)
                    stop_levels.append({
                        'price': price,
                        'label': f'{stop_type.capitalize()} Stop',
                        'color': stop_colors[stop_type],
                        'recommended': stop_type == stop_loss.get('recommended', 'moderate')
                    })
                    all_prices.append(price)
                except:
                    pass

    # Determine y-axis range
    if all_prices:
        min_price = min(all_prices) * 0.95
        max_price = max(all_prices) * 1.05
    else:
        min_price = current_price * 0.85
        max_price = current_price * 1.15

    # Add overextension zone (if >30% from MA200)
    if abs(distance_ma200) > 30:
        # Shade area above MA200 + 30%
        zone_bottom = ma_200 * 1.30
        zone_top = max_price

        fig.add_hrect(
            y0=zone_bottom,
            y1=zone_top,
            fillcolor='rgba(255, 0, 0, 0.1)',
            line_width=0,
            annotation_text="Overextension Zone",
            annotation_position="top right"
        )

    # Add MA200 line
    fig.add_hline(
        y=ma_200,
        line_dash="dash",
        line_color="#7f7f7f",
        annotation_text=f"MA200: ${ma_200:.2f}",
        annotation_position="bottom right"
    )

    # Add MA50 line
    fig.add_hline(
        y=ma_50,
        line_dash="dot",
        line_color="#bcbd22",
        annotation_text=f"MA50: ${ma_50:.2f}",
        annotation_position="top right"
    )

    # Add current price line
    fig.add_hline(
        y=current_price,
        line_color="#1f77b4",
        line_width=2,
        annotation_text=f"Current: ${current_price:.2f}",
        annotation_position="top right"
    )

    # Add entry levels
    for i, entry in enumerate(entry_levels):
        # Alternate positions to avoid overlap
        position = "bottom right" if i % 2 == 0 else "top right"
        fig.add_hline(
            y=entry['price'],
            line_color=entry['color'],
            line_width=2.5,
            line_dash="dash",
            annotation_text=f"{entry['label']}: ${entry['price']:.2f}",
            annotation_position=position,
            annotation=dict(
                font=dict(size=11, weight='bold')
            )
        )

    # Add stop loss levels
    for i, stop in enumerate(stop_levels):
        line_width = 3 if stop.get('recommended') else 1.5
        # Alternate positions to avoid overlap
        position = "bottom left" if i % 2 == 0 else "top left"
        recommended_marker = " [RECOMMENDED]" if stop.get('recommended') else ""
        fig.add_hline(
            y=stop['price'],
            line_color=stop['color'],
            line_width=line_width,
            line_dash="dot",
            annotation_text=f"{stop['label']}{recommended_marker}: ${stop['price']:.2f}",
            annotation_position=position,
            annotation=dict(
                font=dict(size=11, weight='bold' if stop.get('recommended') else 'normal')
            )
        )

    # Update layout with professional styling
    fig.update_layout(
        title=None,  # Title removed - shown in tab header instead
        xaxis=dict(
            title="Date" if historical_prices else "",
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(128,128,128,0.2)',
            zeroline=False
        ),
        yaxis=dict(
            title="Price ($)",
            range=[min_price, max_price],
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(128,128,128,0.2)',
            tickformat='$.2f',
            zeroline=False
        ),
        height=600,
        hovermode='x unified',
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor='rgba(255,255,255,0.95)',
            bordercolor='rgba(0,0,0,0.1)',
            borderwidth=1,
            font=dict(size=11)
        ),
        margin=dict(l=70, r=160, t=60, b=70),
        plot_bgcolor='rgba(248,249,250,0.8)',
        paper_bgcolor='white',
        font=dict(family="Arial, sans-serif", size=12, color='#495057'),
        hoverlabel=dict(
            bgcolor="white",
            font_size=12,
            font_family="Arial, sans-serif"
        )
    )

    return fig


def create_overextension_gauge(
    overextension_risk: int,
    overextension_level: str,
    distance_ma200: float
) -> go.Figure:
    """
    Create gauge chart showing overextension risk level.

    Args:
        overextension_risk: Risk score (0-7)
        overextension_level: Risk level (LOW/MEDIUM/HIGH/EXTREME)
        distance_ma200: Distance from MA200 in %

    Returns:
        Plotly figure object
    """
    # Color based on risk level
    colors = {
        'LOW': '#2ca02c',
        'MEDIUM': '#ff7f0e',
        'HIGH': '#d62728',
        'EXTREME': '#8B0000'
    }

    color = colors.get(overextension_level, '#7f7f7f')

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=overextension_risk,
        domain={'x': [0, 1], 'y': [0, 1]},
        number={'font': {'size': 48, 'color': color, 'family': 'Arial, sans-serif'}},
        gauge={
            'axis': {
                'range': [None, 7],
                'tickwidth': 2,
                'tickcolor': "#495057",
                'tickfont': {'size': 14, 'family': 'Arial, sans-serif'}
            },
            'bar': {'color': color, 'thickness': 0.75},
            'bgcolor': "white",
            'borderwidth': 3,
            'bordercolor': "#dee2e6",
            'steps': [
                {'range': [0, 1], 'color': 'rgba(144, 238, 144, 0.3)'},
                {'range': [1, 3], 'color': 'rgba(255, 228, 181, 0.3)'},
                {'range': [3, 5], 'color': 'rgba(255, 182, 193, 0.3)'},
                {'range': [5, 7], 'color': 'rgba(255, 107, 107, 0.3)'}
            ],
            'threshold': {
                'line': {'color': "#dc3545", 'width': 5},
                'thickness': 0.85,
                'value': 5
            }
        }
    ))

    # Add level indicator annotation
    level_text = f"<b>{overextension_level}</b><br><span style='font-size:12px'>Distance from MA200: {distance_ma200:+.1f}%</span>"
    fig.add_annotation(
        text=level_text,
        xref="paper",
        yref="paper",
        x=0.5,
        y=-0.15,
        showarrow=False,
        font=dict(size=16, color=color, family='Arial, sans-serif'),
        align='center'
    )

    fig.update_layout(
        height=350,
        margin=dict(l=20, r=20, t=40, b=100),
        paper_bgcolor='rgba(248,249,250,0.5)',
        font=dict(family="Arial, sans-serif", color='#495057')
    )

    return fig


def create_risk_reward_chart(
    entry_price: float,
    stop_price: float,
    target_price: float,
    current_price: float,
    position_size_pct: float = 100
) -> go.Figure:
    """
    Create risk/reward visualization chart.

    Args:
        entry_price: Entry price
        stop_price: Stop loss price
        target_price: Profit target price
        current_price: Current market price
        position_size_pct: Position size as % (0-100)

    Returns:
        Plotly figure object
    """
    # Calculate R:R ratio
    risk = entry_price - stop_price
    reward = target_price - entry_price
    rr_ratio = reward / risk if risk > 0 else 0

    # Create bar chart
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=['Risk', 'Reward'],
        y=[risk, reward],
        marker_color=['#d62728', '#2ca02c'],
        text=[f'${risk:.2f}', f'${reward:.2f}'],
        textposition='auto',
    ))

    fig.update_layout(
        title=f"Risk/Reward: 1:{rr_ratio:.2f}",
        yaxis_title="$ per share",
        height=300,
        showlegend=False
    )

    fig.add_annotation(
        text=f"Entry: ${entry_price:.2f} | Stop: ${stop_price:.2f} | Target: ${target_price:.2f}",
        xref="paper",
        yref="paper",
        x=0.5,
        y=-0.2,
        showarrow=False,
        font=dict(size=12)
    )

    return fig


def create_sector_comparison_chart(
    sector_data: List[Dict],
    highlight_symbol: str = None
) -> go.Figure:
    """
    Create bar chart comparing overextension risk across sector peers.

    Args:
        sector_data: List of dicts with {symbol, overextension_risk, distance_ma200}
        highlight_symbol: Symbol to highlight

    Returns:
        Plotly figure object
    """
    symbols = [d['symbol'] for d in sector_data]
    risks = [d['overextension_risk'] for d in sector_data]
    distances = [d['distance_ma200'] for d in sector_data]

    # Color bars based on risk level
    colors = []
    for risk in risks:
        if risk >= 5:
            colors.append('#8B0000')  # EXTREME
        elif risk >= 3:
            colors.append('#d62728')  # HIGH
        elif risk >= 1:
            colors.append('#ff7f0e')  # MEDIUM
        else:
            colors.append('#2ca02c')  # LOW

    # Highlight selected symbol
    if highlight_symbol:
        colors = [c if symbols[i] != highlight_symbol else '#1f77b4'
                  for i, c in enumerate(colors)]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=symbols,
        y=risks,
        marker_color=colors,
        text=[f"{r}/7" for r in risks],
        textposition='auto',
        customdata=distances,
        hovertemplate='%{x}<br>Risk: %{y}/7<br>Distance MA200: %{customdata:+.1f}%<extra></extra>'
    ))

    fig.update_layout(
        title="Sector Peer Comparison - Overextension Risk",
        xaxis_title="Symbol",
        yaxis_title="Overextension Risk",
        yaxis_range=[0, 7],
        height=400
    )

    # Add risk zones
    fig.add_hrect(y0=0, y1=1, fillcolor="green", opacity=0.1, line_width=0)
    fig.add_hrect(y0=1, y1=3, fillcolor="yellow", opacity=0.1, line_width=0)
    fig.add_hrect(y0=3, y1=5, fillcolor="orange", opacity=0.1, line_width=0)
    fig.add_hrect(y0=5, y1=7, fillcolor="red", opacity=0.1, line_width=0)

    return fig
