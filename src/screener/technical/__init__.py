"""
Technical Analysis Module

Basado en evidencia académica 2020-2024:
- Momentum 12M (Jegadeesh & Titman, Moskowitz)
- Sector Relative Strength (Bretscher, Arnott)
- Trend MA200 (Brock et al.)
- Volume confirmation (básico)
- Walk-Forward Optimization (Han, Zhou & Zhu 2016)
- Trailing Stops (Dai 2021)

Hierarchical Market Regime System (2024):
- Cross-market alignment (Cooper et al. 2004, Blin et al. 2022)
- 8-layer architecture for signal validation
- Kill switch, breadth, and environment multipliers
"""

from .analyzer import TechnicalAnalyzer, EnhancedTechnicalAnalyzer
from .analyzer_v2 import TechnicalAnalyzerV2
from .backtester import WalkForwardBacktester
from .market_regime import (
    MarketRegimeSystem,
    GlobalRegime,
    BreadthState,
    RegionalRegime,
    SectorRegime
)
from .earnings_risk import (
    EarningsRiskAnalyzer,
    EarningsRiskLevel,
    EarningsRiskAssessment,
    get_earnings_risk_summary
)
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
    'TechnicalAnalyzerV2',
    'WalkForwardBacktester',
    'MarketRegimeSystem',
    'GlobalRegime',
    'BreadthState',
    'RegionalRegime',
    'SectorRegime',
    'EarningsRiskAnalyzer',
    'EarningsRiskLevel',
    'EarningsRiskAssessment',
    'get_earnings_risk_summary',
    'create_entry_exit_chart',
    'create_equity_curve_chart',
    'create_parameter_stability_chart',
    'create_trade_distribution_chart',
    'create_current_decision_panel'
]

