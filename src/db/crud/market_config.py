"""
CRUD operations for MarketConfig model.
Handles per-market trading parameter overrides.
"""

import uuid
from decimal import Decimal
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.market_config import MarketConfig
from src.core.exceptions import NotFoundError, ValidationError


class MarketConfigCRUD:
    """
    Database operations for per-market configuration overrides.
    """
    
    @staticmethod
    async def create(
        db: AsyncSession,
        user_id: uuid.UUID,
        condition_id: str,
        **kwargs
    ) -> MarketConfig:
        """
        Creates a new market configuration override.
        
        Args:
            db: Database session
            user_id: Associated user ID
            condition_id: Polymarket condition_id
            **kwargs: Configuration values (entry_threshold_drop, etc.)
        
        Returns:
            Created MarketConfig instance
        
        Raises:
            ValidationError: If config for this market already exists
        """
        existing = await MarketConfigCRUD.get_by_condition_id(db, user_id, condition_id)
        if existing:
            raise ValidationError(
                f"Configuration for market {condition_id} already exists",
                details={"condition_id": condition_id}
            )
        
        config = MarketConfig(
            user_id=user_id,
            condition_id=condition_id,
            **kwargs
        )
        db.add(config)
        await db.commit()
        await db.refresh(config)
        return config
    
    @staticmethod
    async def get_by_id(db: AsyncSession, config_id: uuid.UUID) -> MarketConfig | None:
        """
        Retrieves a market configuration by ID.
        """
        result = await db.execute(
            select(MarketConfig).where(MarketConfig.id == config_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_by_condition_id(
        db: AsyncSession,
        user_id: uuid.UUID,
        condition_id: str
    ) -> MarketConfig | None:
        """
        Retrieves market configuration for a specific user and market.
        
        Args:
            db: Database session
            user_id: User identifier
            condition_id: Polymarket condition_id
        
        Returns:
            MarketConfig if exists, None otherwise
        """
        result = await db.execute(
            select(MarketConfig).where(
                MarketConfig.user_id == user_id,
                MarketConfig.condition_id == condition_id
            )
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_all_for_user(db: AsyncSession, user_id: uuid.UUID) -> list[MarketConfig]:
        """
        Retrieves all market configurations for a user.
        """
        result = await db.execute(
            select(MarketConfig)
            .where(MarketConfig.user_id == user_id)
            .order_by(MarketConfig.created_at.desc())
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_enabled_for_user(db: AsyncSession, user_id: uuid.UUID) -> list[MarketConfig]:
        """
        Retrieves only enabled market configurations for a user.
        """
        result = await db.execute(
            select(MarketConfig).where(
                MarketConfig.user_id == user_id,
                MarketConfig.enabled == True
            )
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_by_sport(
        db: AsyncSession,
        user_id: uuid.UUID,
        sport: str
    ) -> list[MarketConfig]:
        """
        Retrieves market configurations filtered by sport.
        """
        result = await db.execute(
            select(MarketConfig).where(
                MarketConfig.user_id == user_id,
                MarketConfig.sport == sport
            )
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def update(
        db: AsyncSession,
        config_id: uuid.UUID,
        user_id: uuid.UUID,
        **kwargs
    ) -> MarketConfig:
        """
        Updates a market configuration.
        
        Args:
            db: Database session
            config_id: Configuration ID
            user_id: User ID (for ownership verification)
            **kwargs: Fields to update
        
        Returns:
            Updated MarketConfig instance
        
        Raises:
            NotFoundError: If config not found or doesn't belong to user
        """
        config = await MarketConfigCRUD.get_by_id(db, config_id)
        
        if not config or config.user_id != user_id:
            raise NotFoundError(
                "Market configuration not found",
                details={"config_id": str(config_id)}
            )
        
        # Update only provided fields
        for key, value in kwargs.items():
            if hasattr(config, key) and value is not None:
                setattr(config, key, value)
        
        await db.commit()
        await db.refresh(config)
        return config
    
    @staticmethod
    async def upsert(
        db: AsyncSession,
        user_id: uuid.UUID,
        condition_id: str,
        **kwargs
    ) -> MarketConfig:
        """
        Creates or updates a market configuration.
        Useful when setting overrides from the markets page.
        
        Args:
            db: Database session
            user_id: User ID
            condition_id: Market condition_id
            **kwargs: Configuration values
        
        Returns:
            Created or updated MarketConfig
        """
        existing = await MarketConfigCRUD.get_by_condition_id(db, user_id, condition_id)
        
        if existing:
            # Update existing config
            for key, value in kwargs.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            await db.commit()
            await db.refresh(existing)
            return existing
        else:
            # Create new config
            config = MarketConfig(
                user_id=user_id,
                condition_id=condition_id,
                **kwargs
            )
            db.add(config)
            await db.commit()
            await db.refresh(config)
            return config
    
    @staticmethod
    async def delete(
        db: AsyncSession,
        config_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> bool:
        """
        Deletes a market configuration.
        
        Args:
            db: Database session
            config_id: Configuration ID to delete
            user_id: User ID (for ownership verification)
        
        Returns:
            True if deleted, False if not found
        """
        config = await MarketConfigCRUD.get_by_id(db, config_id)
        
        if not config or config.user_id != user_id:
            return False
        
        await db.delete(config)
        await db.commit()
        return True
    
    @staticmethod
    async def delete_by_condition_id(
        db: AsyncSession,
        user_id: uuid.UUID,
        condition_id: str
    ) -> bool:
        """
        Deletes a market configuration by condition_id.
        
        Args:
            db: Database session
            user_id: User ID
            condition_id: Market condition_id
        
        Returns:
            True if deleted, False if not found
        """
        result = await db.execute(
            delete(MarketConfig).where(
                MarketConfig.user_id == user_id,
                MarketConfig.condition_id == condition_id
            )
        )
        await db.commit()
        return result.rowcount > 0
    
    @staticmethod
    async def bulk_delete_for_user(db: AsyncSession, user_id: uuid.UUID) -> int:
        """
        Deletes all market configurations for a user.
        
        Returns:
            Number of configurations deleted
        """
        result = await db.execute(
            delete(MarketConfig).where(MarketConfig.user_id == user_id)
        )
        await db.commit()
        return result.rowcount
