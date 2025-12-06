"""
Technical Analysis Module

Basado en evidencia académica 2020-2024:
- Momentum 12M (Jegadeesh & Titman, Moskowitz)
- Sector Relative Strength (Bretscher, Arnott)
- Trend MA200 (Brock et al.)
- Volume confirmation (básico)
- Walk-Forward Optimization (Han, Zhou & Zhu 2016)
- Trailing Stops (Dai 2021)
"""

from .analyzer import TechnicalAnalyzer, EnhancedTechnicalAnalyzer
from .backtester import WalkForwardBacktester
from .visualizations import (
    create_entry_exit_chart,
    create_equity_curve_chart,
    create_parameter_stability_chart,
    create_trade_distribution_chart,
    create_current_decision_panel
)

__all__ = [
    'TechnicalAnalyzer',
    'EnhancedTechnicalAnalyzer',
    'WalkForwardBacktester',
    'create_entry_exit_chart',
    'create_equity_curve_chart',
    'create_parameter_stability_chart',
    'create_trade_distribution_chart',
    'create_current_decision_panel'
]

