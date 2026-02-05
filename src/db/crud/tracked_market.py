"""
CRUD operations for TrackedMarket model.
Includes game selection functionality.
"""

import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy import select, and_, update, delete
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
    
    # =========================================================================
    # Game Selection Methods
    # =========================================================================
    
    @staticmethod
    async def get_selected_for_user(
        db: AsyncSession,
        user_id: uuid.UUID,
        sport: str | None = None,
        include_finished: bool = False
    ) -> list[TrackedMarket]:
        """
        Retrieves all user-selected markets (games user wants to trade on).
        
        Args:
            db: Database session
            user_id: User ID
            sport: Optional sport filter
            include_finished: Whether to include finished games
        
        Returns:
            List of selected TrackedMarket objects
        """
        query = select(TrackedMarket).where(
            TrackedMarket.user_id == user_id,
            TrackedMarket.is_user_selected == True
        )
        
        if not include_finished:
            query = query.where(TrackedMarket.is_finished == False)
        
        if sport:
            query = query.where(TrackedMarket.sport == sport)
        
        query = query.order_by(TrackedMarket.game_start_time.asc())
        result = await db.execute(query)
        return list(result.scalars().all())
    
    @staticmethod
    async def get_unselected_for_user(
        db: AsyncSession,
        user_id: uuid.UUID,
        sport: str | None = None
    ) -> list[TrackedMarket]:
        """
        Retrieves all available but unselected markets (discovered but not selected for trading).
        
        Args:
            db: Database session
            user_id: User ID
            sport: Optional sport filter
        
        Returns:
            List of unselected TrackedMarket objects
        """
        query = select(TrackedMarket).where(
            TrackedMarket.user_id == user_id,
            TrackedMarket.is_user_selected == False,
            TrackedMarket.is_finished == False
        )
        
        if sport:
            query = query.where(TrackedMarket.sport == sport)
        
        query = query.order_by(TrackedMarket.game_start_time.asc())
        result = await db.execute(query)
        return list(result.scalars().all())
    
    @staticmethod
    async def select_game(
        db: AsyncSession,
        user_id: uuid.UUID,
        market_id: uuid.UUID
    ) -> TrackedMarket | None:
        """
        Selects a game for trading (sets is_user_selected=True).
        
        Args:
            db: Database session
            user_id: User ID (for ownership verification)
            market_id: TrackedMarket ID
        
        Returns:
            Updated TrackedMarket or None if not found/not owned
        """
        result = await db.execute(
            select(TrackedMarket).where(
                TrackedMarket.id == market_id,
                TrackedMarket.user_id == user_id
            )
        )
        market = result.scalar_one_or_none()
        
        if not market:
            return None
        
        market.is_user_selected = True
        await db.commit()
        await db.refresh(market)
        return market
    
    @staticmethod
    async def unselect_game(
        db: AsyncSession,
        user_id: uuid.UUID,
        market_id: uuid.UUID
    ) -> TrackedMarket | None:
        """
        Unselects a game from trading (sets is_user_selected=False).
        Does NOT delete the market - keeps it for potential re-selection.
        
        Args:
            db: Database session
            user_id: User ID (for ownership verification)
            market_id: TrackedMarket ID
        
        Returns:
            Updated TrackedMarket or None if not found/not owned
        """
        result = await db.execute(
            select(TrackedMarket).where(
                TrackedMarket.id == market_id,
                TrackedMarket.user_id == user_id
            )
        )
        market = result.scalar_one_or_none()
        
        if not market:
            return None
        
        market.is_user_selected = False
        await db.commit()
        await db.refresh(market)
        return market
    
    @staticmethod
    async def select_by_condition_id(
        db: AsyncSession,
        user_id: uuid.UUID,
        condition_id: str
    ) -> TrackedMarket | None:
        """
        Selects a game by condition_id for trading.
        
        Args:
            db: Database session
            user_id: User ID
            condition_id: Polymarket condition_id
        
        Returns:
            Updated TrackedMarket or None if not found
        """
        result = await db.execute(
            select(TrackedMarket).where(
                TrackedMarket.condition_id == condition_id,
                TrackedMarket.user_id == user_id
            )
        )
        market = result.scalar_one_or_none()
        
        if not market:
            return None
        
        market.is_user_selected = True
        await db.commit()
        await db.refresh(market)
        return market
    
    @staticmethod
    async def unselect_by_condition_id(
        db: AsyncSession,
        user_id: uuid.UUID,
        condition_id: str
    ) -> TrackedMarket | None:
        """
        Unselects a game by condition_id from trading.
        
        Args:
            db: Database session
            user_id: User ID
            condition_id: Polymarket condition_id
        
        Returns:
            Updated TrackedMarket or None if not found
        """
        result = await db.execute(
            select(TrackedMarket).where(
                TrackedMarket.condition_id == condition_id,
                TrackedMarket.user_id == user_id
            )
        )
        market = result.scalar_one_or_none()
        
        if not market:
            return None
        
        market.is_user_selected = False
        await db.commit()
        await db.refresh(market)
        return market
    
    @staticmethod
    async def bulk_select_games(
        db: AsyncSession,
        user_id: uuid.UUID,
        market_ids: list[uuid.UUID]
    ) -> int:
        """
        Selects multiple games at once.
        
        Args:
            db: Database session
            user_id: User ID
            market_ids: List of TrackedMarket IDs to select
        
        Returns:
            Number of markets updated
        """
        result = await db.execute(
            update(TrackedMarket)
            .where(
                TrackedMarket.id.in_(market_ids),
                TrackedMarket.user_id == user_id
            )
            .values(is_user_selected=True)
        )
        await db.commit()
        return result.rowcount
    
    @staticmethod
    async def bulk_unselect_games(
        db: AsyncSession,
        user_id: uuid.UUID,
        market_ids: list[uuid.UUID]
    ) -> int:
        """
        Unselects multiple games at once.
        
        Args:
            db: Database session
            user_id: User ID
            market_ids: List of TrackedMarket IDs to unselect
        
        Returns:
            Number of markets updated
        """
        result = await db.execute(
            update(TrackedMarket)
            .where(
                TrackedMarket.id.in_(market_ids),
                TrackedMarket.user_id == user_id
            )
            .values(is_user_selected=False)
        )
        await db.commit()
        return result.rowcount
    
    @staticmethod
    async def select_all_by_sport(
        db: AsyncSession,
        user_id: uuid.UUID,
        sport: str
    ) -> int:
        """
        Selects all games for a specific sport.
        
        Args:
            db: Database session
            user_id: User ID
            sport: Sport identifier (nba, nfl, etc.)
        
        Returns:
            Number of markets updated
        """
        result = await db.execute(
            update(TrackedMarket)
            .where(
                TrackedMarket.user_id == user_id,
                TrackedMarket.sport == sport,
                TrackedMarket.is_finished == False
            )
            .values(is_user_selected=True)
        )
        await db.commit()
        return result.rowcount
    
    @staticmethod
    async def unselect_all_by_sport(
        db: AsyncSession,
        user_id: uuid.UUID,
        sport: str
    ) -> int:
        """
        Unselects all games for a specific sport.
        
        Args:
            db: Database session
            user_id: User ID
            sport: Sport identifier (nba, nfl, etc.)
        
        Returns:
            Number of markets updated
        """
        result = await db.execute(
            update(TrackedMarket)
            .where(
                TrackedMarket.user_id == user_id,
                TrackedMarket.sport == sport,
                TrackedMarket.is_finished == False
            )
            .values(is_user_selected=False)
        )
        await db.commit()
        return result.rowcount


    @staticmethod
    async def cleanup_stale_unselected(
        db: AsyncSession,
        stale_threshold_hours: int = 24
    ) -> int:
        """
        Deletes unselected markets that haven't been updated for a while.
        This cleans up "Available Games" list.
        
        Args:
            db: Database session
            stale_threshold_hours: Hours of inactivity before deletion
            
        Returns:
            Number of deleted markets
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=stale_threshold_hours)
        
        # Delete unselected, non-live (or stale live) markets
        # We delete if:
        # 1. Not selected by user
        # 2. No open positions (handled by cascade usually, but safe to check)
        # 3. Last updated before cutoff OR game start time (plus buffer) before cutoff
        
        # Simple approach: delete any unselected market updated before cutoff
        result = await db.execute(
            delete(TrackedMarket)
            .where(
                TrackedMarket.is_user_selected == False,
                TrackedMarket.last_updated_at < cutoff
            )
        )
        await db.commit()
        return result.rowcount

# Singleton instance for simplified imports
tracked_market = TrackedMarketCRUD()
