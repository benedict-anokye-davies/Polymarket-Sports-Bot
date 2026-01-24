"""
CRUD operations for TrackedMarket model.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.tracked_market import TrackedMarket
from src.core.exceptions import NotFoundError


class TrackedMarketCRUD:
    """
    Database operations for TrackedMarket model.
    """
    
    @staticmethod
    async def create(
        db: AsyncSession,
        user_id: uuid.UUID,
        condition_id: str,
        token_id_yes: str,
        token_id_no: str,
        sport: str,
        **kwargs
    ) -> TrackedMarket:
        """
        Creates a new tracked market entry.
        """
        market = TrackedMarket(
            user_id=user_id,
            condition_id=condition_id,
            token_id_yes=token_id_yes,
            token_id_no=token_id_no,
            sport=sport,
            **kwargs
        )
        db.add(market)
        await db.commit()
        await db.refresh(market)
        return market
    
    @staticmethod
    async def get_by_id(db: AsyncSession, market_id: uuid.UUID) -> TrackedMarket | None:
        """
        Retrieves a tracked market by ID.
        """
        result = await db.execute(
            select(TrackedMarket).where(TrackedMarket.id == market_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_by_condition_id(
        db: AsyncSession,
        user_id: uuid.UUID,
        condition_id: str
    ) -> TrackedMarket | None:
        """
        Retrieves a tracked market by condition ID for a specific user.
        """
        result = await db.execute(
            select(TrackedMarket).where(
                TrackedMarket.user_id == user_id,
                TrackedMarket.condition_id == condition_id
            )
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_active_for_user(
        db: AsyncSession,
        user_id: uuid.UUID,
        sport: str | None = None
    ) -> list[TrackedMarket]:
        """
        Retrieves all active (not finished) tracked markets for a user.
        Optionally filtered by sport.
        """
        query = select(TrackedMarket).where(
            TrackedMarket.user_id == user_id,
            TrackedMarket.is_finished == False
        )
        
        if sport:
            query = query.where(TrackedMarket.sport == sport)
        
        result = await db.execute(query)
        return list(result.scalars().all())
    
    @staticmethod
    async def get_live_markets(
        db: AsyncSession,
        user_id: uuid.UUID
    ) -> list[TrackedMarket]:
        """
        Retrieves all currently live markets for a user.
        """
        result = await db.execute(
            select(TrackedMarket).where(
                TrackedMarket.user_id == user_id,
                TrackedMarket.is_live == True,
                TrackedMarket.is_finished == False
            )
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def update_prices(
        db: AsyncSession,
        market_id: uuid.UUID,
        price_yes: Decimal,
        price_no: Decimal
    ) -> TrackedMarket:
        """
        Updates current prices for a tracked market.
        """
        market = await TrackedMarketCRUD.get_by_id(db, market_id)
        if not market:
            raise NotFoundError("Tracked market not found")
        
        market.current_price_yes = price_yes
        market.current_price_no = price_no
        market.last_updated_at = datetime.now(timezone.utc)
        
        await db.commit()
        await db.refresh(market)
        return market
    
    @staticmethod
    async def update_game_state(
        db: AsyncSession,
        market_id: uuid.UUID,
        is_live: bool,
        is_finished: bool,
        current_period: int | None = None,
        time_remaining_seconds: int | None = None,
        home_score: int | None = None,
        away_score: int | None = None
    ) -> TrackedMarket:
        """
        Updates game state information from ESPN.
        """
        market = await TrackedMarketCRUD.get_by_id(db, market_id)
        if not market:
            raise NotFoundError("Tracked market not found")
        
        market.is_live = is_live
        market.is_finished = is_finished
        market.current_period = current_period
        market.time_remaining_seconds = time_remaining_seconds
        market.home_score = home_score
        market.away_score = away_score
        market.last_updated_at = datetime.now(timezone.utc)
        
        await db.commit()
        await db.refresh(market)
        return market
    
    @staticmethod
    async def set_baseline_price(
        db: AsyncSession,
        market_id: uuid.UUID,
        price_yes: Decimal,
        price_no: Decimal
    ) -> TrackedMarket:
        """
        Sets the baseline (pre-game) price for comparison.
        """
        market = await TrackedMarketCRUD.get_by_id(db, market_id)
        if not market:
            raise NotFoundError("Tracked market not found")
        
        market.baseline_price_yes = price_yes
        market.baseline_price_no = price_no
        market.baseline_captured_at = datetime.now(timezone.utc)
        
        await db.commit()
        await db.refresh(market)
        return market
    
    @staticmethod
    async def delete(db: AsyncSession, market_id: uuid.UUID) -> bool:
        """
        Deletes a tracked market entry.
        """
        market = await TrackedMarketCRUD.get_by_id(db, market_id)
        if not market:
            return False
        
        await db.delete(market)
        await db.commit()
        return True
    
    @staticmethod
    async def get_with_positions(
        db: AsyncSession,
        market_id: uuid.UUID
    ) -> TrackedMarket | None:
        """
        Retrieves a tracked market with all associated positions loaded.
        """
        result = await db.execute(
            select(TrackedMarket)
            .where(TrackedMarket.id == market_id)
            .options(selectinload(TrackedMarket.positions))
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def deactivate(
        db: AsyncSession,
        condition_id: str
    ) -> bool:
        """
        Deactivates a market by condition ID (sets is_finished=True).
        
        Args:
            db: Database session
            condition_id: Market condition ID
        
        Returns:
            True if market was found and deactivated
        """
        result = await db.execute(
            select(TrackedMarket).where(
                TrackedMarket.condition_id == condition_id
            )
        )
        market = result.scalar_one_or_none()
        
        if not market:
            return False
        
        market.is_finished = True
        market.is_live = False
        await db.commit()
        return True


# Singleton instance for simplified imports
tracked_market = TrackedMarketCRUD()
