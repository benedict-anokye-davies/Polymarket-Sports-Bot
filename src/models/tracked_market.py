"""
Tracked market model for storing Polymarket markets being monitored.
Links ESPN game data to Polymarket market identifiers.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Boolean, Integer, DateTime, Numeric, Text, ForeignKey, UniqueConstraint, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from src.db.database import Base


class TrackedMarket(Base):
    """
    Represents a Polymarket market being tracked for trading.
    Contains both Polymarket identifiers and ESPN game data.
    """
    
    __tablename__ = "tracked_markets"
    __table_args__ = (
        UniqueConstraint("user_id", "condition_id", name="uq_user_condition"),
        Index("ix_tracked_markets_condition_id", "condition_id"),
        Index("ix_tracked_markets_game_start_time", "game_start_time"),
        Index("ix_tracked_markets_sport", "sport"),
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
        nullable=False
    )
    token_id_yes: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    token_id_no: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    question: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )
    
    espn_event_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )
    sport: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )
    
    home_team: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )
    away_team: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )
    home_abbrev: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True
    )
    away_abbrev: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True
    )
    
    # Game selection fields - allows users to choose specific games
    is_user_selected: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether user has selected this game for trading"
    )
    auto_discovered: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether this market was auto-discovered by the bot"
    )
    
    game_start_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    baseline_price_yes: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True
    )
    baseline_price_no: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True
    )
    baseline_captured_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    current_price_yes: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True
    )
    current_price_no: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True
    )
    is_live: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )
    is_finished: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )
    current_period: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )
    time_remaining_seconds: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )
    home_score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )
    away_score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )
    
    match_confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 2),
        nullable=True
    )
    
    last_updated_at: Mapped[datetime] = mapped_column(
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
        back_populates="tracked_markets"
    )
    positions: Mapped[list["Position"]] = relationship(
        "Position",
        back_populates="tracked_market",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<TrackedMarket(condition_id={self.condition_id}, sport={self.sport})>"
