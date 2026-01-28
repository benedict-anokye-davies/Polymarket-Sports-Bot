"""
CRUD operations for GlobalSettings model.
"""

import uuid
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.global_settings import GlobalSettings
from src.core.exceptions import NotFoundError


class GlobalSettingsCRUD:
    """
    Database operations for GlobalSettings model.
    Each user has exactly one global settings record.
    """
    
    @staticmethod
    async def create(db: AsyncSession, user_id: uuid.UUID) -> GlobalSettings:
        """
        Creates default global settings for a user.
        """
        settings = GlobalSettings(user_id=user_id)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
        return settings
    
    @staticmethod
    async def get_by_user_id(db: AsyncSession, user_id: uuid.UUID) -> GlobalSettings | None:
        """
        Retrieves global settings for a user.
        """
        result = await db.execute(
            select(GlobalSettings).where(GlobalSettings.user_id == user_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_or_create(db: AsyncSession, user_id: uuid.UUID) -> GlobalSettings:
        """
        Retrieves existing settings or creates defaults.
        """
        settings = await GlobalSettingsCRUD.get_by_user_id(db, user_id)
        if not settings:
            settings = await GlobalSettingsCRUD.create(db, user_id)
        return settings
    
    @staticmethod
    async def update(db: AsyncSession, user_id: uuid.UUID, **kwargs) -> GlobalSettings:
        """
        Updates global settings for a user.
        
        Args:
            db: Database session
            user_id: User ID
            **kwargs: Fields to update
        
        Returns:
            Updated GlobalSettings instance
        """
        settings = await GlobalSettingsCRUD.get_by_user_id(db, user_id)
        if not settings:
            raise NotFoundError("Global settings not found")
        
        for key, value in kwargs.items():
            if value is not None and hasattr(settings, key):
                setattr(settings, key, value)
        
        await db.commit()
        await db.refresh(settings)
        return settings
    
    @staticmethod
    async def set_bot_enabled(db: AsyncSession, user_id: uuid.UUID, enabled: bool) -> GlobalSettings:
        """
        Enables or disables the trading bot.
        """
        return await GlobalSettingsCRUD.update(db, user_id, bot_enabled=enabled)
    
    @staticmethod
    async def set_discord_webhook(
        db: AsyncSession,
        user_id: uuid.UUID,
        webhook_url: str | None,
        enabled: bool
    ) -> GlobalSettings:
        """
        Updates Discord notification settings.
        """
        return await GlobalSettingsCRUD.update(
            db,
            user_id,
            discord_webhook_url=webhook_url,
            discord_alerts_enabled=enabled
        )
    
    @staticmethod
    async def is_bot_enabled(db: AsyncSession, user_id: uuid.UUID) -> bool:
        """
        Checks if the bot is enabled for a user.
        """
        settings = await GlobalSettingsCRUD.get_by_user_id(db, user_id)
        return settings.bot_enabled if settings else False
    
    @staticmethod
    async def save_bot_config(
        db: AsyncSession,
        user_id: uuid.UUID,
        config: dict
    ) -> GlobalSettings:
        """
        Persists bot configuration to database.
        Stores the full config including selected games and parameters.
        
        Args:
            db: Database session
            user_id: User ID
            config: Configuration dictionary to persist
        
        Returns:
            Updated GlobalSettings instance
        """
        return await GlobalSettingsCRUD.update(db, user_id, bot_config_json=config)
    
    @staticmethod
    async def get_bot_config(db: AsyncSession, user_id: uuid.UUID) -> dict | None:
        """
        Retrieves persisted bot configuration.
        
        Args:
            db: Database session
            user_id: User ID
        
        Returns:
            Configuration dictionary or None if not set
        """
        settings = await GlobalSettingsCRUD.get_by_user_id(db, user_id)
        if settings and settings.bot_config_json:
            return settings.bot_config_json
        return None


# Singleton instance for simplified imports
global_settings = GlobalSettingsCRUD()
