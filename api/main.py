"""
UltraQuality API - FastAPI Backend

This API exposes the stock analysis functionality for the Flutter frontend.
Run with: uvicorn api.main:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.screener.technical import TechnicalAnalyzerV2, MarketRegimeSystem

app = FastAPI(
    title="UltraQuality API",
    description="Professional Stock Screener & Analysis API",
    version="1.0.0",
)

# CORS middleware for Flutter app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your Flutter app's origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize analyzers
analyzer = TechnicalAnalyzerV2()
regime_system = MarketRegimeSystem()


# ==================== MODELS ====================

class TickerRequest(BaseModel):
    tickers: List[str]


class PositionSizeRequest(BaseModel):
    ticker: str
    portfolio_value: float = 100000
    risk_per_trade: float = 0.005


class ConvictionBreakdown(BaseModel):
    setup: float
    market: float
    timing: float
    data: float
    environment: float
    final_: float

    class Config:
        fields = {'final_': 'final'}


class AnalysisResponse(BaseModel):
    ticker: str
    company_name: str
    sector: str
    technical_score: float
    fundamental_score: float
    combined_score: float
    conviction: ConvictionBreakdown
    regime: str
    alignment: int
    breadth: float
    breadth_state: str
    trend: str
    extension: str
    extension_percent: float
    volume: str
    rs_vs_spy: float
    rs_vs_sector: float
    rs_score: int
    sharpe_ratio: float
    volatility: float
    recommendation: str
    action: str
    warnings: List[str]
    vetoes: List[str]
    analyzed_at: str
    current_price: float
    stop_loss: float
    atr: float


class RegimeResponse(BaseModel):
    global_regime: str
    alignment: int
    breadth: float
    breadth_state: str
    regional_regime: str
    sector_regimes: Dict[str, str]
    environment_multiplier: float
    kill_switch_active: bool
    vetoes: List[str]
    warnings: List[str]
    timestamp: str
    index_returns: Dict[str, float]


class ScreenerResponse(BaseModel):
    results: List[AnalysisResponse]
    total: int
    regime: RegimeResponse


# ==================== HELPERS ====================

def format_analysis(analysis: Dict[str, Any], ticker: str) -> AnalysisResponse:
    """Format analysis result for API response."""

    # Extract conviction breakdown
    conviction_data = analysis.get('conviction_breakdown', {})
    environment_data = analysis.get('environment', {})

    conviction = ConvictionBreakdown(
        setup=conviction_data.get('setup_strength', 0),
        market=conviction_data.get('market_factor', 1),
        timing=conviction_data.get('timing_factor', 1),
        data=conviction_data.get('data_factor', 1),
        environment=environment_data.get('multiplier', 1),
        final_=analysis.get('conviction', 0),
    )

    # Get technical analysis data
    tech = analysis.get('technical_analysis', {})
    indicators = tech.get('indicators', {})

    return AnalysisResponse(
        ticker=ticker,
        company_name=analysis.get('company_name', ticker),
        sector=analysis.get('sector', 'Unknown'),
        technical_score=analysis.get('technical_score', 0),
        fundamental_score=analysis.get('fundamental_score', 0),
        combined_score=analysis.get('combined_score', 0),
        conviction=conviction,
        regime=analysis.get('market_regime', 'UNKNOWN'),
        alignment=analysis.get('alignment', 0),
        breadth=analysis.get('breadth', 0),
        breadth_state=analysis.get('breadth_state', 'NEUTRAL'),
        trend=tech.get('trend', 'UNKNOWN'),
        extension=tech.get('extension_state', 'NORMAL'),
        extension_percent=tech.get('ma200_distance', 0),
        volume=tech.get('volume_analysis', 'NEUTRAL'),
        rs_vs_spy=analysis.get('rs_vs_spy', 0),
        rs_vs_sector=analysis.get('rs_vs_sector', 0),
        rs_score=analysis.get('rs_score', 0),
        sharpe_ratio=indicators.get('sharpe_ratio', 0),
        volatility=indicators.get('volatility_12m', 0),
        recommendation=analysis.get('recommendation', ''),
        action=analysis.get('action', 'HOLD'),
        warnings=environment_data.get('warnings', []),
        vetoes=environment_data.get('vetoes', []),
        analyzed_at=datetime.now().isoformat(),
        current_price=analysis.get('current_price', 0),
        stop_loss=analysis.get('stop_loss', 0),
        atr=tech.get('atr_percent', 0),
    )


def format_regime(regime_data: Dict[str, Any]) -> RegimeResponse:
    """Format regime data for API response."""
    return RegimeResponse(
        global_regime=regime_data.get('global_regime', 'UNKNOWN'),
        alignment=regime_data.get('alignment', 0),
        breadth=regime_data.get('breadth', 0),
        breadth_state=regime_data.get('breadth_state', 'NEUTRAL'),
        regional_regime=regime_data.get('regional_regime', 'UNKNOWN'),
        sector_regimes=regime_data.get('sector_regimes', {}),
        environment_multiplier=regime_data.get('environment_multiplier', 1),
        kill_switch_active=regime_data.get('kill_switch', False),
        vetoes=regime_data.get('vetoes', []),
        warnings=regime_data.get('warnings', []),
        timestamp=datetime.now().isoformat(),
        index_returns=regime_data.get('index_returns', {}),
    )


# ==================== ENDPOINTS ====================

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "UltraQuality API",
        "version": "1.0.0",
    }


@app.get("/api/v1/analyze/{ticker}", response_model=AnalysisResponse)
async def analyze_ticker(ticker: str):
    """
    Analyze a single ticker.

    Returns comprehensive technical and fundamental analysis.
    """
    try:
        ticker = ticker.upper().strip()
        analysis = analyzer.analyze(ticker)

        if not analysis:
            raise HTTPException(status_code=404, detail=f"No data found for {ticker}")

        return format_analysis(analysis, ticker)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/analyze/batch", response_model=List[AnalysisResponse])
async def analyze_batch(request: TickerRequest):
    """
    Analyze multiple tickers in batch.

    More efficient than calling single ticker endpoint multiple times.
    """
    results = []

    for ticker in request.tickers:
        try:
            ticker = ticker.upper().strip()
            analysis = analyzer.analyze(ticker)
            if analysis:
                results.append(format_analysis(analysis, ticker))
        except Exception:
            continue  # Skip failed tickers

    return results


@app.get("/api/v1/regime", response_model=RegimeResponse)
async def get_market_regime():
    """
    Get current market regime.

    Includes global regime, alignment, breadth, and environment factors.
    """
    try:
        regime_data = regime_system.get_full_state()
        return format_regime(regime_data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/screener", response_model=ScreenerResponse)
async def run_screener(
    sector: Optional[str] = Query(None, description="Filter by sector"),
    min_score: Optional[float] = Query(None, description="Minimum combined score"),
    min_conviction: Optional[float] = Query(None, description="Minimum conviction"),
    regime: Optional[str] = Query(None, description="Filter by regime compatibility"),
    limit: int = Query(50, description="Maximum results to return"),
):
    """
    Run the stock screener with optional filters.

    Returns a list of stocks matching the criteria, sorted by combined score.
    """
    try:
        # Get current regime
        regime_data = regime_system.get_full_state()

        # Run screener (this would integrate with your existing screener logic)
        # For now, return empty results - you'd integrate your actual screener here
        results = []

        # Apply filters
        if min_score:
            results = [r for r in results if r.combined_score >= min_score]
        if min_conviction:
            results = [r for r in results if r.conviction.final_ >= min_conviction]
        if sector:
            results = [r for r in results if r.sector.lower() == sector.lower()]

        # Sort by combined score
        results.sort(key=lambda x: x.combined_score, reverse=True)

        return ScreenerResponse(
            results=results[:limit],
            total=len(results),
            regime=format_regime(regime_data),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/fundamentals/{ticker}")
async def get_fundamentals(ticker: str):
    """
    Get fundamental data for a ticker.

    Includes financial metrics, ratios, and quality scores.
    """
    try:
        ticker = ticker.upper().strip()
        # This would integrate with your fundamental analysis
        # For now, return placeholder
        return {
            "ticker": ticker,
            "pe_ratio": None,
            "pb_ratio": None,
            "debt_to_equity": None,
            "roe": None,
            "revenue_growth": None,
            "earnings_growth": None,
            "dividend_yield": None,
            "payout_ratio": None,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/position-size")
async def calculate_position_size(request: PositionSizeRequest):
    """
    Calculate optimal position size for a ticker.

    Based on conviction, ATR-based stops, and risk management rules.
    """
    try:
        ticker = request.ticker.upper().strip()
        analysis = analyzer.analyze(ticker)

        if not analysis:
            raise HTTPException(status_code=404, detail=f"No data found for {ticker}")

        # Extract relevant data
        conviction = analysis.get('conviction', 0)
        current_price = analysis.get('current_price', 0)
        atr_percent = analysis.get('technical_analysis', {}).get('atr_percent', 2.5)

        # Calculate position size
        allocation_percent = conviction * 10  # Max 10% at conviction 1.0
        position_value = request.portfolio_value * (allocation_percent / 100)

        # Stop loss calculation (2.5x ATR)
        stop_distance = atr_percent * 2.5
        stop_price = current_price * (1 - stop_distance / 100)

        # Shares
        shares = int(position_value / current_price) if current_price > 0 else 0
        actual_investment = shares * current_price

        # Max loss
        max_loss = actual_investment * (stop_distance / 100)

        return {
            "ticker": ticker,
            "current_price": current_price,
            "conviction": conviction,
            "allocation_percent": allocation_percent,
            "position_value": position_value,
            "shares": shares,
            "actual_investment": actual_investment,
            "stop_price": stop_price,
            "stop_distance_percent": stop_distance,
            "max_loss": max_loss,
            "max_loss_percent": (max_loss / request.portfolio_value) * 100,
            "limiting_factor": "conviction_cap" if position_value < (request.portfolio_value * 0.15) else "stop_based",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== WEBSOCKET (optional for real-time updates) ====================

from fastapi import WebSocket, WebSocketDisconnect

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)


manager = ConnectionManager()


@app.websocket("/ws/regime")
async def websocket_regime(websocket: WebSocket):
    """
    WebSocket endpoint for real-time regime updates.
    """
    await manager.connect(websocket)
    try:
        while True:
            # Wait for client messages (like subscription requests)
            data = await websocket.receive_text()

            # Send current regime
            regime_data = regime_system.get_full_state()
            await websocket.send_json(format_regime(regime_data).dict())

    except WebSocketDisconnect:
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
