"""
Global settings model for bot-wide configuration.
Controls bot state, risk limits, and alert preferences.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Boolean, Integer, DateTime, Numeric, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from src.db.database import Base


class GlobalSettings(Base):
    """
    Stores global configuration for the trading bot.
    Each user has one global settings record.
    """
    
    __tablename__ = "global_settings"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )
    
    bot_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )
    
    max_daily_loss_usdc: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        default=Decimal("100.00")
    )
    max_portfolio_exposure_usdc: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        default=Decimal("500.00")
    )
    
    discord_webhook_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )
    discord_alerts_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )
    
    poll_interval_seconds: Mapped[int] = mapped_column(
        Integer,
        default=10
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    
    user: Mapped["User"] = relationship(
        "User",
        back_populates="global_settings"
    )
    
    def __repr__(self) -> str:
        return f"<GlobalSettings(user_id={self.user_id}, bot_enabled={self.bot_enabled})>"
