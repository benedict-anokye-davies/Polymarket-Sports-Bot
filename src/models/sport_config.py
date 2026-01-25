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

    # Latest exit time - must sell once X seconds remaining in game
    exit_time_remaining_seconds: Mapped[int | None] = mapped_column(
        Integer,
        default=120,  # 2 minutes before game ends
        nullable=True
    )

    # Minimum market volume threshold (in USDC) to enter
    min_volume_threshold: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        default=Decimal("1000.00"),
        nullable=True
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
    
    # Per-sport risk limits
    max_daily_loss_usdc: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        default=Decimal("50.00"),
        nullable=True
    )
    max_exposure_usdc: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        default=Decimal("200.00"),
        nullable=True
    )
    
    # Priority for capital allocation (1 = highest)
    priority: Mapped[int] = mapped_column(
        Integer,
        default=1
    )
    
    # Trading schedule (JSON string: "18:00-23:59")
    trading_hours_start: Mapped[str | None] = mapped_column(
        String(10),
        default=None,
        nullable=True
    )
    trading_hours_end: Mapped[str | None] = mapped_column(
        String(10),
        default=None,
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
        back_populates="sport_configs"
    )
    
    # Property aliases to match code expectations
    @property
    def is_enabled(self) -> bool:
        """Alias for enabled field to match code expectations."""
        return self.enabled
    
    @property
    def sport_type(self) -> str:
        """Alias for sport field to match code expectations."""
        return self.sport
    
    @property
    def entry_threshold_pct(self) -> Decimal:
        """Alias for entry_threshold_drop to match code expectations."""
        return self.entry_threshold_drop
    
    @property
    def absolute_entry_price(self) -> Decimal:
        """Alias for entry_threshold_absolute to match code expectations."""
        return self.entry_threshold_absolute
    
    @property
    def default_position_size_usdc(self) -> Decimal:
        """Alias for position_size_usdc to match code expectations."""
        return self.position_size_usdc
    
    @property
    def allowed_entry_segments(self) -> list[str]:
        """
        Generate list of allowed entry segments based on max_entry_segment.
        For NBA/NFL: q1, q2, q3 if max is q3
        For NHL: p1, p2 if max is p2
        """
        segment_orders = {
            "q1": ["q1"],
            "q2": ["q1", "q2"],
            "q3": ["q1", "q2", "q3"],
            "q4": ["q1", "q2", "q3", "q4"],
            "p1": ["p1"],
            "p2": ["p1", "p2"],
            "p3": ["p1", "p2", "p3"],
            "h1": ["h1"],
            "h2": ["h1", "h2"],
        }
        return segment_orders.get(self.max_entry_segment, ["q1", "q2", "q3"])
    
    def __repr__(self) -> str:
        return f"<SportConfig(user_id={self.user_id}, sport={self.sport}, enabled={self.enabled})>"
