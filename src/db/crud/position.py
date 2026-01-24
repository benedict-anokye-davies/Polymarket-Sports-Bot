"""
CRUD operations for Position model.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.position import Position
from src.core.exceptions import NotFoundError


class PositionCRUD:
    """
    Database operations for Position model.
    """
    
    @staticmethod
    async def create(
        db: AsyncSession,
        user_id: uuid.UUID,
        condition_id: str,
        token_id: str,
        side: str,
        entry_price: Decimal,
        entry_size: Decimal,
        entry_cost_usdc: Decimal,
        **kwargs
    ) -> Position:
        """
        Creates a new position record.
        """
        position = Position(
            user_id=user_id,
            condition_id=condition_id,
            token_id=token_id,
            side=side,
            entry_price=entry_price,
            entry_size=entry_size,
            entry_cost_usdc=entry_cost_usdc,
            **kwargs
        )
        db.add(position)
        await db.commit()
        await db.refresh(position)
        return position
    
    @staticmethod
    async def get_by_id(db: AsyncSession, position_id: uuid.UUID) -> Position | None:
        """
        Retrieves a position by ID.
        """
        result = await db.execute(select(Position).where(Position.id == position_id))
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_open_for_user(db: AsyncSession, user_id: uuid.UUID) -> list[Position]:
        """
        Retrieves all open positions for a user.
        """
        result = await db.execute(
            select(Position).where(
                Position.user_id == user_id,
                Position.status == "open"
            )
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_open_for_market(
        db: AsyncSession,
        user_id: uuid.UUID,
        condition_id: str
    ) -> list[Position]:
        """
        Retrieves open positions for a specific market.
        """
        result = await db.execute(
            select(Position).where(
                Position.user_id == user_id,
                Position.condition_id == condition_id,
                Position.status == "open"
            )
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_all_for_user(
        db: AsyncSession,
        user_id: uuid.UUID,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0
    ) -> list[Position]:
        """
        Retrieves positions for a user with optional status filter.
        """
        query = select(Position).where(Position.user_id == user_id)
        
        if status:
            query = query.where(Position.status == status)
        
        query = query.order_by(Position.opened_at.desc()).limit(limit).offset(offset)
        
        result = await db.execute(query)
        return list(result.scalars().all())
    
    @staticmethod
    async def close_position(
        db: AsyncSession,
        position_id: uuid.UUID,
        exit_price: Decimal,
        exit_size: Decimal,
        exit_proceeds_usdc: Decimal,
        exit_reason: str,
        exit_order_id: str | None = None
    ) -> Position:
        """
        Closes a position and calculates realized P&L.
        """
        position = await PositionCRUD.get_by_id(db, position_id)
        if not position:
            raise NotFoundError("Position not found")
        
        position.exit_price = exit_price
        position.exit_size = exit_size
        position.exit_proceeds_usdc = exit_proceeds_usdc
        position.exit_reason = exit_reason
        position.exit_order_id = exit_order_id
        position.realized_pnl_usdc = exit_proceeds_usdc - position.entry_cost_usdc
        position.status = "closed"
        position.closed_at = datetime.now(timezone.utc)
        
        await db.commit()
        await db.refresh(position)
        return position
    
    @staticmethod
    async def get_daily_pnl(db: AsyncSession, user_id: uuid.UUID) -> Decimal:
        """
        Calculates total realized P&L for today.
        """
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        
        result = await db.execute(
            select(func.coalesce(func.sum(Position.realized_pnl_usdc), 0)).where(
                Position.user_id == user_id,
                Position.status == "closed",
                Position.closed_at >= today_start
            )
        )
        return result.scalar() or Decimal("0")
    
    @staticmethod
    async def get_total_pnl(db: AsyncSession, user_id: uuid.UUID) -> Decimal:
        """
        Calculates all-time realized P&L.
        """
        result = await db.execute(
            select(func.coalesce(func.sum(Position.realized_pnl_usdc), 0)).where(
                Position.user_id == user_id,
                Position.status == "closed"
            )
        )
        return result.scalar() or Decimal("0")
    
    @staticmethod
    async def get_open_exposure(db: AsyncSession, user_id: uuid.UUID) -> Decimal:
        """
        Calculates total USDC value in open positions.
        """
        result = await db.execute(
            select(func.coalesce(func.sum(Position.entry_cost_usdc), 0)).where(
                Position.user_id == user_id,
                Position.status == "open"
            )
        )
        return result.scalar() or Decimal("0")
    
    @staticmethod
    async def count_open_for_market(
        db: AsyncSession,
        user_id: uuid.UUID,
        condition_id: str
    ) -> int:
        """
        Counts open positions for a specific market.
        """
        result = await db.execute(
            select(func.count(Position.id)).where(
                Position.user_id == user_id,
                Position.condition_id == condition_id,
                Position.status == "open"
            )
        )
        return result.scalar() or 0
    
    @staticmethod
    async def get_win_rate(db: AsyncSession, user_id: uuid.UUID) -> float:
        """
        Calculates win rate as percentage of profitable closed positions.
        """
        total_result = await db.execute(
            select(func.count(Position.id)).where(
                Position.user_id == user_id,
                Position.status == "closed"
            )
        )
        total = total_result.scalar() or 0
        
        if total == 0:
            return 0.0
        
        wins_result = await db.execute(
            select(func.count(Position.id)).where(
                Position.user_id == user_id,
                Position.status == "closed",
                Position.realized_pnl_usdc > 0
            )
        )
        wins = wins_result.scalar() or 0
        
        return (wins / total) * 100
    
    @staticmethod
    async def get_with_trades(db: AsyncSession, position_id: uuid.UUID) -> Position | None:
        """
        Retrieves a position with all associated trades loaded.
        """
        result = await db.execute(
            select(Position)
            .where(Position.id == position_id)
            .options(selectinload(Position.trades))
        )
        return result.scalar_one_or_none()


# Singleton instance for simplified imports
position = PositionCRUD()
