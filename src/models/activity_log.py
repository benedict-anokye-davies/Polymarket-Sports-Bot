"""
Activity log model for recording system events and trading activity.
Provides audit trail and debugging information.
"""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, ForeignKey, Index, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from src.db.database import Base


class ActivityLog(Base):
    """
    Records system events, trading activity, and errors.
    Used for debugging, auditing, and user activity display.
    """
    
    __tablename__ = "activity_logs"
    __table_args__ = (
        Index("idx_activity_logs_user_created", "user_id", "created_at"),
        Index("idx_activity_logs_level", "level"),
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
    
    level: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    details: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now()
    )
    
    user: Mapped["User"] = relationship(
        "User",
        back_populates="activity_logs"
    )
    
    def __repr__(self) -> str:
        return f"<ActivityLog(level={self.level}, category={self.category})>"
