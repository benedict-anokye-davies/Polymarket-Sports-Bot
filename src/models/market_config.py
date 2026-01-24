"""
Market configuration model for per-market trading parameter overrides.
Allows users to set specific thresholds for individual markets/events,
overriding the default sport-level configuration.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Boolean, Integer, DateTime, Numeric, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from src.db.database import Base


class MarketConfig(Base):
    """
    Stores trading configuration overrides for a specific market.
    When present, these settings take precedence over SportConfig.
    
    Users can customize entry/exit thresholds per market to:
    - Set tighter/looser thresholds for high-stakes games
    - Adjust position sizing based on confidence
    - Configure different take profit/stop loss levels
    """
    
    __tablename__ = "market_configs"
    __table_args__ = (
        UniqueConstraint("user_id", "condition_id", name="uq_user_market_config"),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    condition_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Polymarket condition_id for the market"
    )
    
    # Descriptive fields for UI display
    market_question: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Human-readable market question"
    )
    sport: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Sport category (nba, nfl, etc.)"
    )
    home_team: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )
    away_team: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )
    
    # Entry condition overrides (nullable = use sport default)
    entry_threshold_drop: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
        comment="Required price drop percentage to enter (0.15 = 15%)"
    )
    entry_threshold_absolute: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
        comment="Enter if price drops below this absolute value"
    )
    min_time_remaining_seconds: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Minimum seconds remaining in period to enter"
    )
    
    # Exit condition overrides
    take_profit_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
        comment="Take profit at this percentage gain (0.20 = 20%)"
    )
    stop_loss_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
        comment="Stop loss at this percentage loss (0.10 = 10%)"
    )
    
    # Position sizing override
    position_size_usdc: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Override position size for this market"
    )
    max_positions: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Max concurrent positions in this market"
    )
    
    # Control flags
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Enable/disable trading on this specific market"
    )
    auto_trade: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Allow bot to auto-trade (false = manual only)"
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now()
    )
    
    # Relationship
    user: Mapped["User"] = relationship(
        "User",
        back_populates="market_configs"
    )
    
    def __repr__(self) -> str:
        return f"<MarketConfig(condition_id={self.condition_id}, enabled={self.enabled})>"
