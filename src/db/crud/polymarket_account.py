"""
CRUD operations for PolymarketAccount model.
"""

import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.polymarket_account import PolymarketAccount
from src.core.encryption import encrypt_credential, decrypt_credential
from src.core.exceptions import NotFoundError


class PolymarketAccountCRUD:
    """
    Database operations for PolymarketAccount model.
    Handles encryption/decryption of sensitive credentials.
    """
    
    @staticmethod
    async def create(
        db: AsyncSession,
        user_id: uuid.UUID,
        private_key: str,
        funder_address: str,
        platform: str = "polymarket"
    ) -> PolymarketAccount:
        """
        Creates a new Polymarket account with encrypted credentials.
        
        Args:
            db: Database session
            user_id: Associated user ID
            private_key: Wallet private key (will be encrypted)
            funder_address: Address holding USDC funds
            platform: Trading platform ('polymarket' or 'kalshi')
        
        Returns:
            Created PolymarketAccount instance
        """
        account = PolymarketAccount(
            user_id=user_id,
            private_key_encrypted=encrypt_credential(private_key),
            funder_address=funder_address,
            platform=platform
        )
        db.add(account)
        await db.commit()
        await db.refresh(account)
        return account
    
    @staticmethod
    async def get_by_user_id(db: AsyncSession, user_id: uuid.UUID) -> PolymarketAccount | None:
        """
        Retrieves Polymarket account for a user.
        """
        result = await db.execute(
            select(PolymarketAccount).where(PolymarketAccount.user_id == user_id)
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
        }
        
        # Polymarket credentials
        if account.private_key_encrypted:
            result["private_key"] = decrypt_credential(account.private_key_encrypted)
        if account.api_key_encrypted:
            result["api_key"] = decrypt_credential(account.api_key_encrypted)
        if account.api_secret_encrypted:
            result["api_secret"] = decrypt_credential(account.api_secret_encrypted)
        if account.api_passphrase_encrypted:
            result["passphrase"] = decrypt_credential(account.api_passphrase_encrypted)
        
        return result
    
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
