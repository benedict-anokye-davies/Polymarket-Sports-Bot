"""
Position model for tracking open and closed trading positions.
Records entry and exit details with P&L calculations.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, DateTime, Numeric, Text, ForeignKey, Integer, func, Index, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from src.db.database import Base


class Position(Base):
    """
    Represents a trading position in a Polymarket market.
    Tracks entry price, size, exit details, and realized P&L.
    """
    
    __tablename__ = "positions"
    __table_args__ = (
        Index("ix_positions_status", "status"),
        Index("ix_positions_user_id", "user_id"),
        Index("ix_positions_tracked_market", "tracked_market_id"),
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
    tracked_market_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tracked_markets.id", ondelete="SET NULL"),
        nullable=True
    )
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("polymarket_accounts.id", ondelete="SET NULL"),
        nullable=True
    )
    
    condition_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    token_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    side: Mapped[str] = mapped_column(
        String(10),
        nullable=False
    )
    sport: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Sport identifier for analytics grouping"
    )
    team: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )
    
    entry_price: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=False
    )
    entry_size: Mapped[Decimal] = mapped_column(
        Numeric(18, 6),
        nullable=False
    )
    entry_cost_usdc: Mapped[Decimal] = mapped_column(
        Numeric(18, 6),
        nullable=False
    )
    entry_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )
    entry_order_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )
    
    # Order confirmation tracking
    requested_entry_price: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True
    )
    actual_entry_price: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True
    )
    fill_status: Mapped[str] = mapped_column(
        String(20),
        default="filled"
    )
    slippage_usdc: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6),
        nullable=True
    )
    confirmation_attempts: Mapped[int] = mapped_column(
        Integer,
        default=0
    )
    
    # Position sync status for recovery
    sync_status: Mapped[str] = mapped_column(
        String(20),
        default="synced"
    )
    recovered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    recovery_source: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )
    
    # Confidence scoring
    entry_confidence_score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )
    entry_confidence_breakdown: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True
    )
    
    exit_price: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True
    )
    exit_size: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6),
        nullable=True
    )
    exit_proceeds_usdc: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6),
        nullable=True
    )
    exit_reason: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )
    exit_order_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )
    
    realized_pnl_usdc: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6),
        nullable=True
    )
    
    status: Mapped[str] = mapped_column(
        String(20),
        default="open"
    )
    
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
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
    
    user: Mapped["User"] = relationship(
        "User",
        back_populates="positions"
    )
    tracked_market: Mapped["TrackedMarket"] = relationship(
        "TrackedMarket",
        back_populates="positions"
    )
    trades: Mapped[list["Trade"]] = relationship(
        "Trade",
        back_populates="position",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Position(id={self.id}, side={self.side}, status={self.status})>"
