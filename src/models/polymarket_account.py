"""
Polymarket account model for storing wallet credentials.
All sensitive data is encrypted at rest using Fernet encryption.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Boolean, Integer, DateTime, Numeric, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from src.db.database import Base


class PolymarketAccount(Base):
    """
    Stores encrypted Polymarket wallet credentials for a user.
    The private key and API credentials are encrypted before storage
    and decrypted only when needed for API calls.
    """
    
    __tablename__ = "polymarket_accounts"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )
    
    private_key_encrypted: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    funder_address: Mapped[str] = mapped_column(
        String(42),
        nullable=False
    )
    
    api_key_encrypted: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )
    api_secret_encrypted: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )
    api_passphrase_encrypted: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )
    
    signature_type: Mapped[int] = mapped_column(
        Integer,
        default=1
    )
    is_connected: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )
    last_balance_usdc: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6),
        nullable=True
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
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
        back_populates="polymarket_account"
    )
    
    def __repr__(self) -> str:
        return f"<PolymarketAccount(user_id={self.user_id}, connected={self.is_connected})>"
