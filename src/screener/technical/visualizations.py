"""
Visualization utilities for Quick Technical Analysis

Clear charts showing:
- WHEN to ENTER
- WHEN to EXIT
- Current trade status
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from typing import Dict, List, Optional


def create_entry_exit_chart(
    prices: pd.DataFrame,
    trades: List[Dict],
    current_params: Dict,
    show_current_signals: bool = True
) -> go.Figure:
    """
    Create interactive chart showing entry/exit signals.

    Args:
        prices: DataFrame with OHLCV data
        trades: List of completed trades
        current_params: Optimized parameters
        show_current_signals: Whether to show current buy/sell zones

    Returns:
        Plotly figure
    """
    # Create subplots: price + volume
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        subplot_titles=('Price & Signals', 'Volume'),
        row_heights=[0.7, 0.3]
    )

    # Candlestick chart
    fig.add_trace(
        go.Candlestick(
            x=prices['date'],
            open=prices['open'],
            high=prices['high'],
            low=prices['low'],
            close=prices['close'],
            name='Price',
            increasing_line_color='#26A69A',
            decreasing_line_color='#EF5350'
        ),
        row=1, col=1
    )

    # MA200
    if 'ma_200' in prices.columns:
        fig.add_trace(
            go.Scatter(
                x=prices['date'],
                y=prices['ma_200'],
                name='MA200',
                line=dict(color='#FFA726', width=2)
            ),
            row=1, col=1
        )

    # MA50
    if 'ma_50' in prices.columns:
        fig.add_trace(
            go.Scatter(
                x=prices['date'],
                y=prices['ma_50'],
                name='MA50',
                line=dict(color='#42A5F5', width=1.5)
            ),
            row=1, col=1
        )

    # Plot entry signals
    for trade in trades:
        entry_date = trade['entry_date']
        entry_price = trade['entry_price']

        # Entry marker
        fig.add_trace(
            go.Scatter(
                x=[entry_date],
                y=[entry_price],
                mode='markers',
                name='Entry',
                marker=dict(
                    symbol='triangle-up',
                    size=15,
                    color='#00E676',
                    line=dict(color='white', width=2)
                ),
                showlegend=False,
                hovertemplate=f'<b>BUY</b><br>Date: {entry_date}<br>Price: ${entry_price:.2f}<extra></extra>'
            ),
            row=1, col=1
        )

        # Exit marker
        exit_date = trade['exit_date']
        exit_price = trade['exit_price']

        fig.add_trace(
            go.Scatter(
                x=[exit_date],
                y=[exit_price],
                mode='markers',
                name='Exit',
                marker=dict(
                    symbol='triangle-down',
                    size=15,
                    color='#FF1744',
                    line=dict(color='white', width=2)
                ),
                showlegend=False,
                hovertemplate=f'<b>SELL</b><br>Date: {exit_date}<br>Price: ${exit_price:.2f}<br>Return: {trade["return_pct"]:.1f}%<br>Reason: {trade["exit_reason"]}<extra></extra>'
            ),
            row=1, col=1
        )

    # Show current signals if requested
    if show_current_signals and len(prices) > 0:
        current_price = prices.iloc[-1]['close']
        current_date = prices.iloc[-1]['date']

        # Calculate trailing stop level
        trailing_stop_pct = current_params.get('trailing_stop_pct', 10) / 100
        recent_high = prices['high'].tail(20).max()
        stop_level = recent_high * (1 - trailing_stop_pct)

        # Add horizontal line for stop level
        fig.add_hline(
            y=stop_level,
            line_dash="dash",
            line_color="red",
            annotation_text=f"Trailing Stop: ${stop_level:.2f}",
            annotation_position="right",
            row=1, col=1
        )

        # Add buy zone if momentum is positive
        if 'momentum_12m' in prices.columns:
            recent_momentum = prices.iloc[-1]['momentum_12m']
            if recent_momentum > current_params.get('momentum_entry_min', 0):
                # Green zone: OK to buy
                fig.add_vrect(
                    x0=prices['date'].iloc[-30],
                    x1=prices['date'].iloc[-1],
                    fillcolor="green",
                    opacity=0.1,
                    layer="below",
                    line_width=0,
                    annotation_text="BUY ZONE",
                    annotation_position="top left",
                    row=1, col=1
                )
            elif recent_momentum < current_params.get('momentum_threshold', -5):
                # Red zone: Should sell
                fig.add_vrect(
                    x0=prices['date'].iloc[-30],
                    x1=prices['date'].iloc[-1],
                    fillcolor="red",
                    opacity=0.1,
                    layer="below",
                    line_width=0,
                    annotation_text="SELL ZONE",
                    annotation_position="top left",
                    row=1, col=1
                )

    # Volume bars
    colors = ['#26A69A' if prices.iloc[i]['close'] >= prices.iloc[i]['open'] else '#EF5350'
              for i in range(len(prices))]

    fig.add_trace(
        go.Bar(
            x=prices['date'],
            y=prices['volume'],
            name='Volume',
            marker_color=colors,
            showlegend=False
        ),
        row=2, col=1
    )

    # Update layout
    fig.update_layout(
        title='Entry/Exit Signals - Walk-Forward Optimized',
        xaxis_rangeslider_visible=False,
        height=700,
        hovermode='x unified',
        template='plotly_dark'
    )

    fig.update_xaxes(title_text="Date", row=2, col=1)
    fig.update_yaxes(title_text="Price ($)", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)

    return fig


def create_equity_curve_chart(
    equity_curve: pd.DataFrame,
    in_sample_metrics: Dict,
    out_sample_metrics: Dict
) -> go.Figure:
    """
    Create equity curve showing in-sample vs out-of-sample performance.

    Args:
        equity_curve: DataFrame with equity over time
        in_sample_metrics: Training metrics
        out_sample_metrics: Testing metrics

    Returns:
        Plotly figure
    """
    fig = go.Figure()

    # Equity curve
    fig.add_trace(
        go.Scatter(
            x=equity_curve['date'],
            y=equity_curve['equity'],
            name='Equity (Out-of-Sample)',
            line=dict(color='#00E676', width=2),
            fill='tozeroy',
            fillcolor='rgba(0, 230, 118, 0.1)'
        )
    )

    # Calculate drawdown
    running_max = equity_curve['equity'].expanding().max()
    drawdown = (equity_curve['equity'] - running_max) / running_max * 100

    # Add drawdown as area
    fig.add_trace(
        go.Scatter(
            x=equity_curve['date'],
            y=drawdown,
            name='Drawdown (%)',
            line=dict(color='#FF1744', width=1),
            fill='tozeroy',
            fillcolor='rgba(255, 23, 68, 0.1)',
            yaxis='y2'
        )
    )

    # Add annotations for key metrics
    annotations = [
        dict(
            x=0.02,
            y=0.98,
            xref='paper',
            yref='paper',
            text=f'<b>Out-of-Sample Performance</b><br>' +
                 f'Sharpe: {out_sample_metrics.get("sharpe_ratio", 0):.2f}<br>' +
                 f'Total Return: {out_sample_metrics.get("total_return", 0):.1f}%<br>' +
                 f'Max DD: {out_sample_metrics.get("max_drawdown", 0):.1f}%<br>' +
                 f'Win Rate: {out_sample_metrics.get("win_rate", 0):.1f}%',
            showarrow=False,
            bgcolor='rgba(0,0,0,0.7)',
            font=dict(color='white', size=11),
            align='left'
        )
    ]

    fig.update_layout(
        title='Equity Curve & Drawdown (Out-of-Sample Only)',
        xaxis_title='Date',
        yaxis_title='Equity ($)',
        yaxis2=dict(
            title='Drawdown (%)',
            overlaying='y',
            side='right'
        ),
        height=400,
        hovermode='x unified',
        template='plotly_dark',
        annotations=annotations
    )

    return fig


def create_parameter_stability_chart(parameter_stability: Dict) -> go.Figure:
    """
    Create heatmap showing parameter stability across windows.

    Args:
        parameter_stability: Dictionary with parameter statistics

    Returns:
        Plotly figure
    """
    params = list(parameter_stability.keys())
    metrics = ['mean', 'std', 'cv']

    # Create matrix
    z_data = []
    for metric in metrics:
        row = [parameter_stability[p][metric] for p in params]
        z_data.append(row)

    fig = go.Figure(data=go.Heatmap(
        z=z_data,
        x=params,
        y=['Mean', 'Std Dev', 'CV'],
        colorscale='RdYlGn_r',
        text=[[f'{val:.2f}' for val in row] for row in z_data],
        texttemplate='%{text}',
        textfont={"size": 10},
        hovertemplate='Parameter: %{x}<br>Metric: %{y}<br>Value: %{z:.2f}<extra></extra>'
    ))

    fig.update_layout(
        title='Parameter Stability Across Walk-Forward Windows',
        xaxis_title='Parameter',
        yaxis_title='Stability Metric',
        height=300,
        template='plotly_dark'
    )

    return fig


def create_trade_distribution_chart(trades: List[Dict]) -> go.Figure:
    """
    Create histogram of trade returns.

    Args:
        trades: List of completed trades

    Returns:
        Plotly figure
    """
    if not trades:
        return go.Figure()

    returns = [t['return_pct'] for t in trades]

    fig = go.Figure()

    fig.add_trace(
        go.Histogram(
            x=returns,
            nbinsx=30,
            name='Trade Returns',
            marker=dict(
                color=returns,
                colorscale='RdYlGn',
                cmid=0,
                line=dict(color='white', width=1)
            )
        )
    )

    # Add vertical line at 0
    fig.add_vline(x=0, line_dash="dash", line_color="white")

    # Calculate statistics
    avg_return = np.mean(returns)
    median_return = np.median(returns)

    fig.add_vline(x=avg_return, line_dash="dot", line_color="yellow",
                  annotation_text=f"Mean: {avg_return:.1f}%")
    fig.add_vline(x=median_return, line_dash="dot", line_color="cyan",
                  annotation_text=f"Median: {median_return:.1f}%")

    fig.update_layout(
        title='Distribution of Trade Returns',
        xaxis_title='Return (%)',
        yaxis_title='Frequency',
        height=350,
        template='plotly_dark',
        showlegend=False
    )

    return fig


def create_current_decision_panel(
    current_data: pd.Series,
    optimal_params: Dict,
    trades: List[Dict]
) -> Dict:
    """
    Create decision panel: Should I BUY/HOLD/SELL now?

    Args:
        current_data: Latest price data row
        optimal_params: Optimized parameters
        trades: Historical trades for context

    Returns:
        Dictionary with decision and reasoning
    """
    decision = {
        'action': 'WAIT',  # BUY, SELL, HOLD, WAIT
        'confidence': 'LOW',  # LOW, MEDIUM, HIGH
        'reasons': [],
        'metrics': {},
        'warnings': []
    }

    # Check entry conditions
    momentum_12m = current_data.get('momentum_12m', 0)
    momentum_min = optimal_params.get('momentum_entry_min', 0)
    ma_200 = current_data.get('ma_200', 0)
    current_price = current_data.get('close', 0)

    # Entry signals
    if momentum_12m > momentum_min:
        decision['reasons'].append(f"✅ Momentum 12M ({momentum_12m:.1f}%) > threshold ({momentum_min:.1f}%)")

        if current_price > ma_200:
            decision['reasons'].append(f"✅ Price (${current_price:.2f}) above MA200 (${ma_200:.2f})")
            decision['action'] = 'BUY'
            decision['confidence'] = 'HIGH' if momentum_12m > momentum_min + 5 else 'MEDIUM'
        else:
            decision['warnings'].append(f"⚠️ Price below MA200 - wait for trend confirmation")
            decision['confidence'] = 'LOW'
    else:
        decision['reasons'].append(f"❌ Momentum 12M ({momentum_12m:.1f}%) below threshold ({momentum_min:.1f}%)")

        # Check if should sell
        momentum_threshold = optimal_params.get('momentum_threshold', -5)
        if momentum_12m < momentum_threshold:
            decision['action'] = 'SELL'
            decision['reasons'].append(f"🔴 Momentum deteriorated below {momentum_threshold}%")
            decision['confidence'] = 'HIGH'

    # Calculate expected metrics based on backtest
    if trades:
        win_rate = len([t for t in trades if t['return_pct'] > 0]) / len(trades) * 100
        avg_win = np.mean([t['return_pct'] for t in trades if t['return_pct'] > 0]) if any(t['return_pct'] > 0 for t in trades) else 0
        avg_loss = np.mean([t['return_pct'] for t in trades if t['return_pct'] < 0]) if any(t['return_pct'] < 0 for t in trades) else 0

        decision['metrics'] = {
            'expected_win_rate': f"{win_rate:.1f}%",
            'avg_win': f"+{avg_win:.1f}%",
            'avg_loss': f"{avg_loss:.1f}%",
            'profit_factor': f"{(abs(avg_win) / abs(avg_loss)):.2f}" if avg_loss != 0 else "N/A"
        }

    return decision
