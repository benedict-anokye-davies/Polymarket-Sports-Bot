"""
Trade model for recording individual order executions.
Each position may have multiple trades (entry and exit orders).
"""

import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, DateTime, Numeric, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from src.db.database import Base


class Trade(Base):
    """
    Records an individual order execution on Polymarket.
    Tracks order ID, price, size, and execution status.
    """
    
    __tablename__ = "trades"
    
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
    position_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("positions.id", ondelete="SET NULL"),
        nullable=True
    )
    
    polymarket_order_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )
    action: Mapped[str] = mapped_column(
        String(10),
        nullable=False
    )
    side: Mapped[str] = mapped_column(
        String(10),
        nullable=False
    )
    
    price: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=False
    )
    size: Mapped[Decimal] = mapped_column(
        Numeric(18, 6),
        nullable=False
    )
    total_usdc: Mapped[Decimal] = mapped_column(
        Numeric(18, 6),
        nullable=False
    )
    fee_usdc: Mapped[Decimal] = mapped_column(
        Numeric(18, 6),
        default=Decimal("0")
    )
    
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending"
    )
    
    executed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    
    position: Mapped["Position"] = relationship(
        "Position",
        back_populates="trades"
    )
    
    def __repr__(self) -> str:
        return f"<Trade(id={self.id}, action={self.action}, status={self.status})>"
