"""
CRUD operations for SportConfig model.
"""

import uuid
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.sport_config import SportConfig
from src.core.exceptions import NotFoundError, ValidationError


class SportConfigCRUD:
    """
    Database operations for SportConfig model.
    """
    
    @staticmethod
    async def create(
        db: AsyncSession,
        user_id: uuid.UUID,
        sport: str,
        **kwargs
    ) -> SportConfig:
        """
        Creates a new sport configuration.
        
        Args:
            db: Database session
            user_id: Associated user ID
            sport: Sport identifier (nba, nfl, mlb, nhl)
            **kwargs: Optional configuration overrides
        
        Returns:
            Created SportConfig instance
        """
        existing = await SportConfigCRUD.get_by_user_and_sport(db, user_id, sport)
        if existing:
            raise ValidationError(f"Configuration for {sport} already exists")
        
        config = SportConfig(user_id=user_id, sport=sport, **kwargs)
        db.add(config)
        await db.commit()
        await db.refresh(config)
        return config
    
    @staticmethod
    async def get_by_id(db: AsyncSession, config_id: uuid.UUID) -> SportConfig | None:
        """
        Retrieves a sport configuration by ID.
        """
        result = await db.execute(select(SportConfig).where(SportConfig.id == config_id))
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_by_user_and_sport(
        db: AsyncSession,
        user_id: uuid.UUID,
        sport: str
    ) -> SportConfig | None:
        """
        Retrieves sport configuration for a specific user and sport.
        """
        result = await db.execute(
            select(SportConfig).where(
                SportConfig.user_id == user_id,
                SportConfig.sport == sport
            )
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_all_for_user(db: AsyncSession, user_id: uuid.UUID) -> list[SportConfig]:
        """
        Retrieves all sport configurations for a user.
        """
        result = await db.execute(
            select(SportConfig).where(SportConfig.user_id == user_id)
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_enabled_for_user(db: AsyncSession, user_id: uuid.UUID) -> list[SportConfig]:
        """
        Retrieves only enabled sport configurations for a user.
        """
        result = await db.execute(
            select(SportConfig).where(
                SportConfig.user_id == user_id,
                SportConfig.enabled == True
            )
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def update(
        db: AsyncSession,
        config_id: uuid.UUID,
        **kwargs
    ) -> SportConfig:
        """
        Updates a sport configuration.
        
        Args:
            db: Database session
            config_id: Configuration ID
            **kwargs: Fields to update
        
        Returns:
            Updated SportConfig instance
        """
        config = await SportConfigCRUD.get_by_id(db, config_id)
        if not config:
            raise NotFoundError("Sport configuration not found")
        
        for key, value in kwargs.items():
            if value is not None and hasattr(config, key):
                setattr(config, key, value)
        
        await db.commit()
        await db.refresh(config)
        return config
    
    @staticmethod
    async def delete(db: AsyncSession, config_id: uuid.UUID) -> bool:
        """
        Deletes a sport configuration.
        
        Returns:
            True if deleted, False if not found
        """
        config = await SportConfigCRUD.get_by_id(db, config_id)
        if not config:
            return False
        
        await db.delete(config)
        await db.commit()
        return True
    
    @staticmethod
    async def create_defaults_for_user(db: AsyncSession, user_id: uuid.UUID) -> list[SportConfig]:
        """
        Creates default configurations for all supported sports.
        
        Returns:
            List of created SportConfig instances
        """
        sports = ["nba", "nfl", "mlb", "nhl"]
        configs = []
        
        for sport in sports:
            existing = await SportConfigCRUD.get_by_user_and_sport(db, user_id, sport)
            if not existing:
                config = SportConfig(user_id=user_id, sport=sport, enabled=False)
                db.add(config)
                configs.append(config)
        
        await db.commit()
        for config in configs:
            await db.refresh(config)
        
        return configs
    
    @staticmethod
    async def get_by_user_id(db: AsyncSession, user_id: uuid.UUID) -> list[SportConfig]:
        """
        Alias for get_all_for_user for compatibility with bot_runner.
        """
        return await SportConfigCRUD.get_all_for_user(db, user_id)


# Singleton instance for simplified imports
sport_config = SportConfigCRUD()
