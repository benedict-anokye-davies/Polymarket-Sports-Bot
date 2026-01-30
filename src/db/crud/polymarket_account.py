"""
CRUD operations for PolymarketAccount model.
"""

import logging
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.polymarket_account import PolymarketAccount
from src.core.encryption import encrypt_credential, decrypt_credential
from src.core.exceptions import NotFoundError

logger = logging.getLogger(__name__)


class PolymarketAccountCRUD:
    """
    Database operations for PolymarketAccount model.
    Handles encryption/decryption of sensitive credentials.
    """
    
    @staticmethod
    async def create(
        db: AsyncSession,
        user_id: uuid.UUID,
        private_key: str | None = None,
        funder_address: str | None = None,
        platform: str = "polymarket",
        api_key: str | None = None,
        api_secret: str | None = None,
        environment: str = "production"
    ) -> PolymarketAccount:
        """
        Creates a new trading account with encrypted credentials.

        Args:
            db: Database session
            user_id: Associated user ID
            private_key: Wallet private key - required for Polymarket (will be encrypted)
            funder_address: Address holding USDC funds - required for Polymarket
            platform: Trading platform ('polymarket' or 'kalshi')
            api_key: API key - required for Kalshi (will be encrypted)
            api_secret: API secret - required for Kalshi (will be encrypted)
            environment: 'production' or 'demo' (Kalshi only)

        Returns:
            Created PolymarketAccount instance
        """
        account = PolymarketAccount(
            user_id=user_id,
            private_key_encrypted=encrypt_credential(private_key) if private_key else None,
            funder_address=funder_address,
            platform=platform,
            environment=environment,
            api_key_encrypted=encrypt_credential(api_key) if api_key else None,
            api_secret_encrypted=encrypt_credential(api_secret) if api_secret else None,
            is_connected=True  # Mark as connected when credentials are saved
        )
        db.add(account)
        await db.commit()
        await db.refresh(account)
        return account
    
    @staticmethod
    async def get_by_user_id(db: AsyncSession, user_id: uuid.UUID) -> PolymarketAccount | None:
        """
        Retrieves primary/first Polymarket account for a user.
        For multi-account, use get_all_for_user instead.
        """
        result = await db.execute(
            select(PolymarketAccount).where(PolymarketAccount.user_id == user_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_all_for_user(db: AsyncSession, user_id: uuid.UUID) -> list[PolymarketAccount]:
        """
        Retrieves ALL trading accounts for a user (multi-account support).
        
        Args:
            db: Database session
            user_id: User ID
        
        Returns:
            List of all PolymarketAccount instances for the user
        """
        result = await db.execute(
            select(PolymarketAccount).where(PolymarketAccount.user_id == user_id)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(db: AsyncSession, account_id: uuid.UUID) -> PolymarketAccount | None:
        """
        Retrieves a specific account by ID.
        
        Args:
            db: Database session
            account_id: Account ID
        
        Returns:
            PolymarketAccount or None if not found
        """
        result = await db.execute(
            select(PolymarketAccount).where(PolymarketAccount.id == account_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_decrypted_credentials(
        db: AsyncSession,
        user_id: uuid.UUID
    ) -> dict[str, str] | None:
        """
        Retrieves and decrypts all credentials for a user.
        
        Args:
            db: Database session
            user_id: User ID
        
        Returns:
            Dictionary with decrypted credentials or None if not found
        """
        account = await PolymarketAccountCRUD.get_by_user_id(db, user_id)
        if not account:
            return None
        
        result = {
            "funder_address": account.funder_address,
            "platform": account.platform,
            "environment": getattr(account, 'environment', 'production'),  # Kalshi demo/production
        }

        # Polymarket credentials - with error handling for corrupted data
        try:
            if account.private_key_encrypted:
                result["private_key"] = decrypt_credential(account.private_key_encrypted)
            if account.api_key_encrypted:
                result["api_key"] = decrypt_credential(account.api_key_encrypted)
            if account.api_secret_encrypted:
                result["api_secret"] = decrypt_credential(account.api_secret_encrypted)
            if account.api_passphrase_encrypted:
                result["passphrase"] = decrypt_credential(account.api_passphrase_encrypted)
        except Exception as e:
            logger.error(f"Failed to decrypt credentials for user {user_id}: {e}")
            raise NotFoundError("Credentials corrupted or cannot be decrypted. Please reconnect your wallet.")

        return result
    
    @staticmethod
    async def update(
        db: AsyncSession,
        account_id: uuid.UUID,
        **kwargs
    ) -> PolymarketAccount:
        """
        Updates an existing trading account with provided fields.

        Args:
            db: Database session
            account_id: The account ID to update
            **kwargs: Fields to update (platform, api_key_encrypted, etc.)

        Returns:
            Updated PolymarketAccount instance
        """
        result = await db.execute(
            select(PolymarketAccount).where(PolymarketAccount.id == account_id)
        )
        account = result.scalar_one_or_none()

        if not account:
            raise NotFoundError("Trading account not found")

        for key, value in kwargs.items():
            if hasattr(account, key):
                setattr(account, key, value)

        await db.commit()
        await db.refresh(account)
        return account

    @staticmethod
    async def update_api_credentials(
        db: AsyncSession,
        user_id: uuid.UUID,
        api_key: str,
        api_secret: str,
        passphrase: str
    ) -> PolymarketAccount:
        """
        Updates stored API credentials for L2 authentication.
        
        Args:
            db: Database session
            user_id: User ID
            api_key: Polymarket API key
            api_secret: API secret
            passphrase: API passphrase
        
        Returns:
            Updated PolymarketAccount instance
        """
        account = await PolymarketAccountCRUD.get_by_user_id(db, user_id)
        if not account:
            raise NotFoundError("Polymarket account not found")
        
        account.api_key_encrypted = encrypt_credential(api_key)
        account.api_secret_encrypted = encrypt_credential(api_secret)
        account.api_passphrase_encrypted = encrypt_credential(passphrase)
        
        await db.commit()
        await db.refresh(account)
        return account
    
    @staticmethod
    async def update_connection_status(
        db: AsyncSession,
        user_id: uuid.UUID,
        is_connected: bool,
        error_message: str | None = None
    ) -> PolymarketAccount:
        """
        Updates the connection status and timestamp.
        """
        account = await PolymarketAccountCRUD.get_by_user_id(db, user_id)
        if not account:
            raise NotFoundError("Polymarket account not found")
        
        account.is_connected = is_connected
        account.connection_error = error_message
        
        await db.commit()
        await db.refresh(account)
        return account
    
    @staticmethod
    async def delete(db: AsyncSession, user_id: uuid.UUID) -> bool:
        """
        Deletes Polymarket account for a user.
        
        Returns:
            True if deleted, False if not found
        """
        account = await PolymarketAccountCRUD.get_by_user_id(db, user_id)
        if not account:
            return False
        
        await db.delete(account)
        await db.commit()
        return True
