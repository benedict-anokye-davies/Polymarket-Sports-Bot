"""
Price snapshot model for backtesting data storage.
Captures market prices and game state at regular intervals during live games.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, DateTime, Numeric, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from src.db.database import Base


class PriceSnapshot(Base):
    """
    Stores point-in-time price and game state data for backtesting.
    Captured during live games to enable strategy replay.
    """
    
    __tablename__ = "price_snapshots"
    __table_args__ = (
        Index('idx_snapshots_condition_time', 'condition_id', 'captured_at'),
        Index('idx_snapshots_user_sport', 'user_id', 'sport', 'captured_at'),
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
    token_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    price: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=False
    )
    game_state: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True
    )
    espn_event_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )
    sport: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )
    
    def __repr__(self) -> str:
        return f"<PriceSnapshot(condition_id={self.condition_id}, price={self.price}, captured_at={self.captured_at})>"


class BacktestResult(Base):
    """
    Stores results from a completed backtest run.
    Includes configuration used, summary metrics, and simulated trades.
    """
    
    __tablename__ = "backtest_results"
    __table_args__ = (
        Index('idx_backtest_user_created', 'user_id', 'created_at'),
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
    name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )
    config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False
    )
    result_summary: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True
    )
    trades: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True
    )
    equity_curve: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending"
    )
    error_message: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow
    )
    
    def __repr__(self) -> str:
        return f"<BacktestResult(id={self.id}, status={self.status})>"
