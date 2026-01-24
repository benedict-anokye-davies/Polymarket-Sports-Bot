"""
Sport configuration model for per-sport trading parameters.
Each user can have different settings for NBA, NFL, MLB, NHL.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Boolean, Integer, DateTime, Numeric, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from src.db.database import Base


class SportConfig(Base):
    """
    Stores trading configuration for a specific sport.
    Controls entry conditions, exit conditions, and position sizing.
    """
    
    __tablename__ = "sport_configs"
    __table_args__ = (
        UniqueConstraint("user_id", "sport", name="uq_user_sport"),
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
    sport: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )
    
    min_pregame_price: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        default=Decimal("0.55")
    )
    entry_threshold_drop: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        default=Decimal("0.15")
    )
    entry_threshold_absolute: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        default=Decimal("0.50")
    )
    max_entry_segment: Mapped[str] = mapped_column(
        String(20),
        default="q3"
    )
    min_time_remaining_seconds: Mapped[int] = mapped_column(
        Integer,
        default=300
    )
    
    take_profit_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        default=Decimal("0.20")
    )
    stop_loss_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        default=Decimal("0.10")
    )
    exit_before_segment: Mapped[str] = mapped_column(
        String(20),
        default="q4_2min"
    )
    
    position_size_usdc: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        default=Decimal("50.00")
    )
    max_positions_per_game: Mapped[int] = mapped_column(
        Integer,
        default=1
    )
    max_total_positions: Mapped[int] = mapped_column(
        Integer,
        default=5
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )
    
    user: Mapped["User"] = relationship(
        "User",
        back_populates="sport_configs"
    )
    
    def __repr__(self) -> str:
        return f"<SportConfig(user_id={self.user_id}, sport={self.sport}, enabled={self.enabled})>"
