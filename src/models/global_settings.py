"""
Global settings model for bot-wide configuration.
Controls bot state, risk limits, and alert preferences.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Boolean, Integer, DateTime, Numeric, Text, ForeignKey, func, JSON
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
    
    # Trading mode - always real money (no paper trading)
    # This field kept for backwards compatibility but forced to False
    dry_run_mode: Mapped[bool] = mapped_column(
        Boolean,
        default=False  # REAL MONEY TRADING ONLY
    )
    
    # Emergency stop flag - halts all trading immediately
    emergency_stop: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )
    
    # Slippage protection - max acceptable slippage percentage
    max_slippage_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        default=Decimal("0.02")  # 2% default
    )
    
    # Order fill timeout in seconds
    order_fill_timeout_seconds: Mapped[int] = mapped_column(
        Integer,
        default=60
    )
    
    # Balance Guardian settings
    min_balance_threshold_usdc: Mapped[Decimal] = mapped_column(
        Numeric(18, 6),
        default=Decimal("50.0")
    )
    balance_check_interval_seconds: Mapped[int] = mapped_column(
        Integer,
        default=30
    )
    alert_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )
    alert_phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True
    )
    kill_switch_triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    kill_switch_reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )
    
    # Streak tracking for Kelly adjustment
    current_losing_streak: Mapped[int] = mapped_column(
        Integer,
        default=0
    )
    max_losing_streak: Mapped[int] = mapped_column(
        Integer,
        default=0
    )
    streak_reduction_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )
    streak_reduction_pct_per_loss: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("10.0")
    )
    
    # AUTO-TRADE ALL MODE
    # When enabled, bot automatically bets on ANY team that matches parameters
    # No manual game selection needed - scans all markets automatically
    auto_trade_all: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )
    
    # Persistent bot configuration (selected games, parameters)
    # Stored as JSON to survive server restarts
    bot_config_json: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now()
    )
    
    user: Mapped["User"] = relationship(
        "User",
        back_populates="global_settings"
    )
    
    # Property aliases to match code expectations
    @property
    def daily_loss_limit(self) -> Decimal:
        """Alias for max_daily_loss_usdc to match code expectations."""
        return self.max_daily_loss_usdc
    
    @property
    def default_position_size(self) -> Decimal:
        """Default position size - returns 10 USDC as default."""
        return Decimal("10.00")
    
    def __repr__(self) -> str:
        return f"<GlobalSettings(user_id={self.user_id}, bot_enabled={self.bot_enabled})>"
