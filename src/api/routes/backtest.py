"""
Backtest API endpoints - run and manage strategy backtests.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db, get_current_user
from src.models import User
from src.models.backtest import BacktestResult
from src.services.backtester import Backtester, BacktestConfig

router = APIRouter(prefix="/backtest", tags=["backtest"])


class BacktestConfigRequest(BaseModel):
    """Request schema for running a backtest."""
    start_date: datetime
    end_date: datetime
    initial_capital: float = Field(1000.0, ge=100)
    entry_threshold_drop_pct: float = Field(0.05, ge=0.01, le=0.5)
    exit_take_profit_pct: float = Field(0.10, ge=0.01, le=1.0)
    exit_stop_loss_pct: float = Field(0.08, ge=0.01, le=1.0)
    max_position_size_pct: float = Field(0.20, ge=0.01, le=1.0)
    max_concurrent_positions: int = Field(5, ge=1, le=50)
    min_confidence_score: float = Field(0.6, ge=0, le=1.0)
    use_kelly_sizing: bool = False
    kelly_fraction: float = Field(0.25, ge=0.1, le=1.0)
    sport_filter: Optional[str] = None
    name: Optional[str] = None


class BacktestTradeResponse(BaseModel):
    """Single trade from backtest."""
    token_id: str
    entry_time: Optional[datetime]
    entry_price: float
    exit_time: Optional[datetime]
    exit_price: Optional[float]
    contracts: int
    pnl: float
    exit_reason: str


class BacktestSummaryResponse(BaseModel):
    """Backtest summary statistics."""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    max_drawdown: float
    sharpe_ratio: Optional[float]
    profit_factor: float
    avg_trade_pnl: float
    avg_win: float
    avg_loss: float
    final_capital: float
    roi_pct: float


class BacktestResultResponse(BaseModel):
    """Complete backtest result response."""
    id: str
    name: Optional[str]
    status: str
    config: dict
    summary: Optional[BacktestSummaryResponse]
    trades_count: int
    created_at: datetime
    completed_at: Optional[datetime]


class RunBacktestResponse(BaseModel):
    """Response when starting a backtest."""
    id: str
    status: str
    message: str


@router.post("/run", response_model=RunBacktestResponse)
async def run_backtest(
    request: BacktestConfigRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Start a new backtest with the given configuration.
    
    Runs in background and saves results to database.
    """
    config = BacktestConfig(
        start_date=request.start_date,
        end_date=request.end_date,
        initial_capital=request.initial_capital,
        entry_threshold_drop_pct=request.entry_threshold_drop_pct,
        exit_take_profit_pct=request.exit_take_profit_pct,
        exit_stop_loss_pct=request.exit_stop_loss_pct,
        max_position_size_pct=request.max_position_size_pct,
        max_concurrent_positions=request.max_concurrent_positions,
        min_confidence_score=request.min_confidence_score,
        use_kelly_sizing=request.use_kelly_sizing,
        kelly_fraction=request.kelly_fraction,
        sport_filter=request.sport_filter,
    )
    
    pending_result = BacktestResult(
        user_id=current_user.id,
        name=request.name or f"Backtest {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
        config={
            "start_date": request.start_date.isoformat(),
            "end_date": request.end_date.isoformat(),
            "initial_capital": request.initial_capital,
            "entry_threshold_drop_pct": request.entry_threshold_drop_pct,
            "exit_take_profit_pct": request.exit_take_profit_pct,
            "exit_stop_loss_pct": request.exit_stop_loss_pct,
            "max_position_size_pct": request.max_position_size_pct,
            "max_concurrent_positions": request.max_concurrent_positions,
            "min_confidence_score": request.min_confidence_score,
            "use_kelly_sizing": request.use_kelly_sizing,
            "kelly_fraction": request.kelly_fraction,
            "sport_filter": request.sport_filter,
        },
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    
    db.add(pending_result)
    await db.commit()
    await db.refresh(pending_result)
    
    async def run_in_background(result_id: UUID, user_id: UUID, cfg: BacktestConfig, name: str):
        from src.db.database import async_session_factory
        
        async with async_session_factory() as session:
            try:
                backtester = Backtester(session, user_id)
                summary, trades, equity_curve = await backtester.run_backtest(cfg)
                
                result = await session.get(BacktestResult, result_id)
                if result:
                    import dataclasses
                    result.result_summary = dataclasses.asdict(summary)
                    result.trades = [
                        {
                            "token_id": t.token_id,
                            "entry_time": t.entry_time.isoformat() if t.entry_time else None,
                            "entry_price": t.entry_price,
                            "exit_time": t.exit_time.isoformat() if t.exit_time else None,
                            "exit_price": t.exit_price,
                            "contracts": t.contracts,
                            "pnl": t.pnl,
                            "exit_reason": t.exit_reason,
                        }
                        for t in trades
                    ]
                    result.equity_curve = equity_curve
                    result.status = "completed"
                    result.completed_at = datetime.now(timezone.utc)
                    await session.commit()
                    
            except Exception as e:
                result = await session.get(BacktestResult, result_id)
                if result:
                    result.status = "failed"
                    result.error_message = str(e)[:500]
                    await session.commit()
    
    background_tasks.add_task(
        run_in_background,
        pending_result.id,
        current_user.id,
        config,
        request.name,
    )
    
    return RunBacktestResponse(
        id=str(pending_result.id),
        status="running",
        message="Backtest started. Check results endpoint for completion.",
    )


@router.get("/results", response_model=list[BacktestResultResponse])
async def list_backtests(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all backtest results for the current user.
    """
    stmt = (
        select(BacktestResult)
        .where(BacktestResult.user_id == current_user.id)
        .order_by(BacktestResult.created_at.desc())
        .limit(limit)
    )
    
    result = await db.execute(stmt)
    results = result.scalars().all()
    
    return [
        BacktestResultResponse(
            id=str(r.id),
            name=r.name,
            status=r.status,
            config=r.config,
            summary=BacktestSummaryResponse(**r.result_summary) if r.result_summary else None,
            trades_count=len(r.trades) if r.trades else 0,
            created_at=r.created_at,
            completed_at=r.completed_at,
        )
        for r in results
    ]


@router.get("/results/{result_id}", response_model=BacktestResultResponse)
async def get_backtest_result(
    result_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific backtest result by ID.
    """
    stmt = (
        select(BacktestResult)
        .where(BacktestResult.id == result_id)
        .where(BacktestResult.user_id == current_user.id)
    )
    
    result = await db.execute(stmt)
    backtest = result.scalar_one_or_none()
    
    if not backtest:
        raise HTTPException(status_code=404, detail="Backtest not found")
    
    return BacktestResultResponse(
        id=str(backtest.id),
        name=backtest.name,
        status=backtest.status,
        config=backtest.config,
        summary=BacktestSummaryResponse(**backtest.result_summary) if backtest.result_summary else None,
        trades_count=len(backtest.trades) if backtest.trades else 0,
        created_at=backtest.created_at,
        completed_at=backtest.completed_at,
    )


@router.get("/results/{result_id}/trades", response_model=list[BacktestTradeResponse])
async def get_backtest_trades(
    result_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all trades from a backtest result.
    """
    stmt = (
        select(BacktestResult)
        .where(BacktestResult.id == result_id)
        .where(BacktestResult.user_id == current_user.id)
    )
    
    result = await db.execute(stmt)
    backtest = result.scalar_one_or_none()
    
    if not backtest:
        raise HTTPException(status_code=404, detail="Backtest not found")
    
    if not backtest.trades:
        return []
    
    return [
        BacktestTradeResponse(
            token_id=t["token_id"],
            entry_time=datetime.fromisoformat(t["entry_time"]) if t.get("entry_time") else None,
            entry_price=t["entry_price"],
            exit_time=datetime.fromisoformat(t["exit_time"]) if t.get("exit_time") else None,
            exit_price=t.get("exit_price"),
            contracts=t["contracts"],
            pnl=t["pnl"],
            exit_reason=t.get("exit_reason", ""),
        )
        for t in backtest.trades
    ]


@router.get("/results/{result_id}/equity-curve")
async def get_backtest_equity_curve(
    result_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get equity curve data from a backtest result.
    """
    stmt = (
        select(BacktestResult)
        .where(BacktestResult.id == result_id)
        .where(BacktestResult.user_id == current_user.id)
    )
    
    result = await db.execute(stmt)
    backtest = result.scalar_one_or_none()
    
    if not backtest:
        raise HTTPException(status_code=404, detail="Backtest not found")
    
    return backtest.equity_curve or []


@router.delete("/results/{result_id}")
async def delete_backtest(
    result_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a backtest result.
    """
    stmt = (
        select(BacktestResult)
        .where(BacktestResult.id == result_id)
        .where(BacktestResult.user_id == current_user.id)
    )
    
    result = await db.execute(stmt)
    backtest = result.scalar_one_or_none()
    
    if not backtest:
        raise HTTPException(status_code=404, detail="Backtest not found")
    
    await db.delete(backtest)
    await db.commit()
    
    return {"message": "Backtest deleted successfully"}
