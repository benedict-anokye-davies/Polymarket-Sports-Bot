"""
User model for authentication and account management.
Stores user credentials and onboarding progress.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from src.db.database import Base


class User(Base):
    """
    Represents a registered user of the trading bot.
    Each user has their own Polymarket account, sport configurations,
    and trading positions.
    """
    
    __tablename__ = "users"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )
    onboarding_completed: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )
    onboarding_step: Mapped[int] = mapped_column(
        Integer,
        default=0
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
    
    polymarket_account: Mapped["PolymarketAccount"] = relationship(
        "PolymarketAccount",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )
    sport_configs: Mapped[list["SportConfig"]] = relationship(
        "SportConfig",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    tracked_markets: Mapped[list["TrackedMarket"]] = relationship(
        "TrackedMarket",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    positions: Mapped[list["Position"]] = relationship(
        "Position",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    global_settings: Mapped["GlobalSettings"] = relationship(
        "GlobalSettings",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )
    activity_logs: Mapped[list["ActivityLog"]] = relationship(
        "ActivityLog",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"
