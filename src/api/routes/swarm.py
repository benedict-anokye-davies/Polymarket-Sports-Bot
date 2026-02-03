from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from src.db.database import get_db
from src.models import TrackedMarket, Position, PositionStatus
from src.services.auth import get_current_user
from src.models.user import User

router = APIRouter(tags=["swarm"])

class SwarmCoordinates(BaseModel):
    x: float
    y: float
    z: float = 0.0

class SwarmMetrics(BaseModel):
    volume: float
    probability: float
    pnl: Optional[float] = None
    last_updated: datetime

class SwarmNode(BaseModel):
    id: str
    ticker: str
    type: str  # "opportunity", "position", "watch"
    status: str  # "active", "pending", "cooling"
    coordinates: Optional[SwarmCoordinates] = None
    metrics: SwarmMetrics
    platform: str

@router.get("/swarm/state", response_model=List[SwarmNode])
async def get_swarm_state(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the current state of the "Strategy Swarm".
    Aggregates active positions, opportunities (tracked markets), and watchlist items.
    """
    nodes = []

    # 1. Fetch Active Positions (Orbiting Satellites)
    positions = db.execute(
        select(Position).where(
            Position.user_id == current_user.id,
            Position.status.in_([PositionStatus.OPEN, PositionStatus.PENDING_ENTRY, PositionStatus.PENDING_EXIT])
        )
    ).scalars().all()

    for pos in positions:
        nodes.append(SwarmNode(
            id=f"pos-{pos.id}",
            ticker=pos.market_ticker,
            type="position",
            status="active" if pos.status == PositionStatus.OPEN else "pending",
            metrics=SwarmMetrics(
                volume=pos.size_currency,
                probability=50.0, # Placeholder, would come from live market data
                pnl=pos.unrealized_pnl,
                last_updated=pos.updated_at
            ),
            platform=pos.market_ticker.split("-")[0] if "-" in pos.market_ticker else "unknown" # simplistic platform inference
        ))

    # 2. Fetch Tracked Markets (Opportunities)
    # Limit to top 20 relevant markets to avoid overcrowding the swarm
    tracked_markets = db.execute(
        select(TrackedMarket).where(
            TrackedMarket.is_active == True
        ).limit(20)
    ).scalars().all()

    for market in tracked_markets:
        # Avoid duplicates if we already have a position
        if any(n.ticker == market.ticker for n in nodes):
            continue
            
        nodes.append(SwarmNode(
            id=f"mkt-{market.id}",
            ticker=market.ticker,
            type="opportunity",
            status="active",
            metrics=SwarmMetrics(
                volume=market.volume or 0.0,
                probability=market.last_price * 100 if market.last_price else 50.0,
                last_updated=market.last_updated or datetime.utcnow()
            ),
            platform=market.source
        ))

    return nodes
