"""
CRUD operations for Trade model.
Records individual trade executions linked to positions.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc

from src.models.trade import Trade


class TradeCRUD:
    """CRUD operations for Trade records."""
    
    @staticmethod
    async def create(
        db: AsyncSession,
        user_id: uuid.UUID,
        position_id: Optional[uuid.UUID],
        action: str,
        side: str,
        price: Decimal,
        size: Decimal,
        total_usdc: Decimal,
        fee_usdc: Decimal = Decimal("0"),
        polymarket_order_id: Optional[str] = None,
        status: str = "filled",
        executed_at: Optional[datetime] = None
    ) -> Trade:
        """Create a new trade record."""
        trade = Trade(
            id=uuid.uuid4(),
            user_id=user_id,
            position_id=position_id,
            action=action,
            side=side,
            price=price,
            size=size,
            total_usdc=total_usdc,
            fee_usdc=fee_usdc,
            polymarket_order_id=polymarket_order_id,
            status=status,
            executed_at=executed_at or datetime.now(timezone.utc)
        )
        db.add(trade)
        await db.flush()
        return trade
    
    @staticmethod
    async def get_by_id(db: AsyncSession, trade_id: uuid.UUID) -> Optional[Trade]:
        """Get trade by ID."""
        result = await db.execute(select(Trade).where(Trade.id == trade_id))
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_by_position(db: AsyncSession, position_id: uuid.UUID):
        """Get all trades for a position."""
        result = await db.execute(
            select(Trade)
            .where(Trade.position_id == position_id)
            .order_by(desc(Trade.executed_at))
        )
        return result.scalars().all()
    
    @staticmethod
    async def get_by_user(db: AsyncSession, user_id: uuid.UUID, limit: int = 100):
        """Get recent trades for user."""
        result = await db.execute(
            select(Trade)
            .where(Trade.user_id == user_id)
            .order_by(desc(Trade.executed_at))
            .limit(limit)
        )
        return result.scalars().all()
