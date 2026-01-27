"""
CRUD operations for RefreshToken model (REQ-SEC-001).

Handles creation, validation, and revocation of refresh tokens.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.refresh_token import RefreshToken
from src.core.security import hash_refresh_token, generate_refresh_token
from src.config import get_settings

settings = get_settings()


class RefreshTokenCRUD:
    """CRUD operations for refresh tokens."""

    @staticmethod
    async def create(
        db: AsyncSession,
        user_id: uuid.UUID,
        device_info: str | None = None,
        ip_address: str | None = None,
        expires_delta: timedelta | None = None,
    ) -> tuple[RefreshToken, str]:
        """
        Create a new refresh token for a user.

        Args:
            db: Database session
            user_id: User's UUID
            device_info: Optional device/browser info
            ip_address: Optional IP address
            expires_delta: Optional custom expiration

        Returns:
            Tuple of (RefreshToken model, plain token string)
            The plain token is returned only once and should be sent to client.
        """
        # Generate the plain token
        plain_token = generate_refresh_token()

        # Hash for storage
        token_hash = hash_refresh_token(plain_token)

        # Calculate expiration
        now = datetime.now(timezone.utc)
        if expires_delta:
            expires_at = now + expires_delta
        else:
            expires_at = now + timedelta(days=settings.refresh_token_expire_days)

        # Create the model
        refresh_token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            device_info=device_info,
            ip_address=ip_address,
            expires_at=expires_at,
        )

        db.add(refresh_token)
        await db.commit()
        await db.refresh(refresh_token)

        return refresh_token, plain_token

    @staticmethod
    async def get_by_token(
        db: AsyncSession,
        plain_token: str,
    ) -> RefreshToken | None:
        """
        Find a refresh token by its plain value.

        Args:
            db: Database session
            plain_token: The plain token string from the client

        Returns:
            RefreshToken if found, None otherwise
        """
        token_hash = hash_refresh_token(plain_token)

        result = await db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def validate_and_use(
        db: AsyncSession,
        plain_token: str,
    ) -> RefreshToken | None:
        """
        Validate a refresh token and mark it as used.

        Args:
            db: Database session
            plain_token: The plain token string from the client

        Returns:
            RefreshToken if valid, None if invalid/expired/revoked
        """
        token = await RefreshTokenCRUD.get_by_token(db, plain_token)

        if not token:
            return None

        if not token.is_valid:
            return None

        # Update last used timestamp
        token.last_used_at = datetime.now(timezone.utc)
        await db.commit()

        return token

    @staticmethod
    async def revoke(
        db: AsyncSession,
        token_id: uuid.UUID,
        reason: str = "manual",
    ) -> bool:
        """
        Revoke a specific refresh token.

        Args:
            db: Database session
            token_id: Token's UUID
            reason: Reason for revocation

        Returns:
            True if revoked, False if not found
        """
        result = await db.execute(
            select(RefreshToken).where(RefreshToken.id == token_id)
        )
        token = result.scalar_one_or_none()

        if not token:
            return False

        token.revoke(reason)
        await db.commit()

        return True

    @staticmethod
    async def revoke_by_token(
        db: AsyncSession,
        plain_token: str,
        reason: str = "manual",
    ) -> bool:
        """
        Revoke a refresh token by its plain value.

        Args:
            db: Database session
            plain_token: The plain token string
            reason: Reason for revocation

        Returns:
            True if revoked, False if not found
        """
        token = await RefreshTokenCRUD.get_by_token(db, plain_token)

        if not token:
            return False

        token.revoke(reason)
        await db.commit()

        return True

    @staticmethod
    async def revoke_all_for_user(
        db: AsyncSession,
        user_id: uuid.UUID,
        reason: str = "logout_all",
    ) -> int:
        """
        Revoke all refresh tokens for a user.

        Args:
            db: Database session
            user_id: User's UUID
            reason: Reason for revocation

        Returns:
            Number of tokens revoked
        """
        now = datetime.now(timezone.utc)

        result = await db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.is_revoked == False,
            )
            .values(
                is_revoked=True,
                revoked_at=now,
                revoked_reason=reason,
            )
        )
        await db.commit()

        return result.rowcount

    @staticmethod
    async def get_active_for_user(
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> list[RefreshToken]:
        """
        Get all active (non-revoked, non-expired) tokens for a user.

        Args:
            db: Database session
            user_id: User's UUID

        Returns:
            List of active refresh tokens
        """
        now = datetime.now(timezone.utc)

        result = await db.execute(
            select(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.is_revoked == False,
                RefreshToken.expires_at > now,
            )
            .order_by(RefreshToken.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def cleanup_expired(
        db: AsyncSession,
        older_than_days: int = 30,
    ) -> int:
        """
        Delete expired and revoked tokens older than specified days.
        Should be run periodically as a cleanup task.

        Args:
            db: Database session
            older_than_days: Delete tokens expired/revoked more than this many days ago

        Returns:
            Number of tokens deleted
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)

        result = await db.execute(
            delete(RefreshToken).where(
                (RefreshToken.expires_at < cutoff)
                | (
                    (RefreshToken.is_revoked == True)
                    & (RefreshToken.revoked_at < cutoff)
                )
            )
        )
        await db.commit()

        return result.rowcount

    @staticmethod
    async def rotate(
        db: AsyncSession,
        old_plain_token: str,
        device_info: str | None = None,
        ip_address: str | None = None,
    ) -> tuple[RefreshToken, str] | None:
        """
        Rotate a refresh token: revoke the old one and create a new one.
        This is the recommended pattern for refresh token usage.

        Args:
            db: Database session
            old_plain_token: The old token to rotate
            device_info: Optional device info for new token
            ip_address: Optional IP address for new token

        Returns:
            Tuple of (new RefreshToken, new plain token) or None if old token invalid
        """
        # Validate old token
        old_token = await RefreshTokenCRUD.validate_and_use(db, old_plain_token)

        if not old_token:
            return None

        # Revoke old token
        old_token.revoke("rotated")

        # Create new token for the same user
        new_token, new_plain = await RefreshTokenCRUD.create(
            db,
            user_id=old_token.user_id,
            device_info=device_info or old_token.device_info,
            ip_address=ip_address or old_token.ip_address,
        )

        return new_token, new_plain
