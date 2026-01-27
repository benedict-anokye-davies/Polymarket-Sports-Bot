"""
Refresh Token model for JWT token refresh mechanism (REQ-SEC-001).

Stores refresh tokens in the database to enable:
- Token rotation on refresh
- Token revocation (logout, security events)
- Multiple device sessions
"""

import uuid
import secrets
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from src.db.database import Base


def generate_token() -> str:
    """Generate a secure random token string."""
    return secrets.token_urlsafe(64)


class RefreshToken(Base):
    """
    Represents a refresh token for JWT token refresh mechanism.

    Refresh tokens are long-lived tokens that can be used to obtain
    new access tokens without re-authenticating. They are stored in
    the database to allow for revocation and rotation.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    token_hash: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        nullable=False,
        index=True
    )
    # Device/session identification
    device_info: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(45),  # IPv6 max length
        nullable=True
    )
    # Token state
    is_revoked: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    revoked_reason: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")

    # Indexes for common queries
    __table_args__ = (
        Index("ix_refresh_tokens_user_active", "user_id", "is_revoked"),
        Index("ix_refresh_tokens_expires", "expires_at"),
    )

    @property
    def is_expired(self) -> bool:
        """Check if the token has expired."""
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Check if the token is valid (not revoked and not expired)."""
        return not self.is_revoked and not self.is_expired

    def revoke(self, reason: str = "manual") -> None:
        """Revoke this token."""
        self.is_revoked = True
        self.revoked_at = datetime.now(timezone.utc)
        self.revoked_reason = reason

    def __repr__(self) -> str:
        return f"<RefreshToken(id={self.id}, user_id={self.user_id}, is_valid={self.is_valid})>"
