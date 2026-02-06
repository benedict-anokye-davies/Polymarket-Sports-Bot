"""
CRUD operations for Position model.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.dialects.postgresql import insert as pg_insert

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
    async def create_if_not_exists(
        db: AsyncSession,
        user_id: uuid.UUID,
        condition_id: str,
        token_id: str,
        side: str,
        entry_price: Decimal,
        entry_size: Decimal,
        entry_cost_usdc: Decimal,
        **kwargs
    ) -> tuple[Position | None, bool]:
        """
        Creates a position only if no open position exists for this user/market/side.
        
        Uses database-level locking to prevent race conditions where two
        concurrent requests could both create positions for the same market.
        
        Args:
            db: Database session
            user_id: User ID
            condition_id: Market condition ID
            token_id: Token ID being traded
            side: Position side (YES/NO)
            entry_price: Entry price
            entry_size: Position size
            entry_cost_usdc: Entry cost in USDC
            **kwargs: Additional position fields
        
        Returns:
            Tuple of (position, created) where created is True if new position was created
        """
        # Use savepoint for atomicity
        async with db.begin_nested():
            # Check for existing open position with SELECT FOR UPDATE
            existing_query = (
                select(Position)
                .where(
                    Position.user_id == user_id,
                    Position.condition_id == condition_id,
                    Position.status == "open"
                )
                .with_for_update()
            )
            result = await db.execute(existing_query)
            existing = result.scalar_one_or_none()
            
            if existing:
                # Already have an open position for this market
                return existing, False
            
            # Create new position
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
        return position, True
    
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
    async def count_open_for_team(
        db: AsyncSession,
        user_id: uuid.UUID,
        team_name: str
    ) -> int:
        """
        Counts open positions for a specific team name.
        """
        if not team_name:
            return 0
            
        result = await db.execute(
            select(func.count(Position.id)).where(
                Position.user_id == user_id,
                Position.team == team_name,
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
    
    @staticmethod
    async def count_open_for_user(db: AsyncSession, user_id: uuid.UUID) -> int:
        """
        Counts all open positions for a user.
        """
        result = await db.execute(
            select(func.count(Position.id)).where(
                Position.user_id == user_id,
                Position.status == "open"
            )
        )
        return result.scalar() or 0
    
    @staticmethod
    async def count_today_trades(db: AsyncSession, user_id: uuid.UUID) -> int:
        """
        Counts all positions opened or closed today.
        """
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        
        result = await db.execute(
            select(func.count(Position.id)).where(
                Position.user_id == user_id,
                Position.opened_at >= today_start
            )
        )
        return result.scalar() or 0

    @staticmethod
    async def get_trade_stats(db: AsyncSession, user_id: uuid.UUID) -> dict | None:
        """
        Calculate comprehensive trade statistics for Kelly sizing.
        
        Returns win rate and total trades count for historical performance
        calibration in the Kelly criterion calculation.
        
        Args:
            db: Database session
            user_id: User identifier
        
        Returns:
            Dictionary with win_rate and total_trades, or None if no trades
        """
        # Get total closed trades
        total_result = await db.execute(
            select(func.count(Position.id)).where(
                Position.user_id == user_id,
                Position.status == "closed"
            )
        )
        total_trades = total_result.scalar() or 0
        
        if total_trades == 0:
            return None
        
        # Get winning trades
        wins_result = await db.execute(
            select(func.count(Position.id)).where(
                Position.user_id == user_id,
                Position.status == "closed",
                Position.realized_pnl_usdc > 0
            )
        )
        wins = wins_result.scalar() or 0
        
        # Get average win and loss amounts
        avg_win_result = await db.execute(
            select(func.avg(Position.realized_pnl_usdc)).where(
                Position.user_id == user_id,
                Position.status == "closed",
                Position.realized_pnl_usdc > 0
            )
        )
        avg_win = float(avg_win_result.scalar() or 0)
        
        avg_loss_result = await db.execute(
            select(func.avg(func.abs(Position.realized_pnl_usdc))).where(
                Position.user_id == user_id,
                Position.status == "closed",
                Position.realized_pnl_usdc < 0
            )
        )
        avg_loss = float(avg_loss_result.scalar() or 0)
        
        return {
            "win_rate": wins / total_trades if total_trades > 0 else 0.0,
            "total_trades": total_trades,
            "wins": wins,
            "losses": total_trades - wins,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
        }


# Singleton instance for simplified imports
position = PositionCRUD()
