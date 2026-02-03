"""
CRUD operations for Trading Accounts (supporting Kalshi).
"""
import uuid
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.trading_account import TradingAccount
from src.core.encryption import encrypt_credential, decrypt_credential
from src.core.exceptions import NotFoundError

logger = logging.getLogger(__name__)

class AccountCRUD:
    """
    Database operations for Trading Accounts.
    """

    @staticmethod
    async def get_by_user_id(db: AsyncSession, user_id: uuid.UUID) -> Optional[TradingAccount]:
        """
        Retrieves the *primary* or first found trading account for a user.
        """
        # Prioritize primary account
        stmt = (
            select(TradingAccount)
            .where(TradingAccount.user_id == user_id)
            .order_by(TradingAccount.is_primary.desc(), TradingAccount.created_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def create(
        db: AsyncSession, 
        user_id: uuid.UUID,
        platform: str = "kalshi",
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        environment: str = "production",
        # Legacy/Polymarket fields (kept for compatibility in signature but unused/ignored if strictly Kalshi)
        private_key: Optional[str] = None,
        funder_address: Optional[str] = None,
    ) -> TradingAccount:
        """
        Creates a new trading account.
        """
        
        # Encrypt credentials
        enc_api_key = encrypt_credential(api_key) if api_key else None
        enc_api_secret = encrypt_credential(api_secret) if api_secret else None
        enc_private = encrypt_credential(private_key) if private_key else None
        
        account = TradingAccount(
            user_id=user_id,
            platform=platform,
            environment=environment,
            api_key_encrypted=enc_api_key,
            api_secret_encrypted=enc_api_secret,
            private_key_encrypted=enc_private,
            funder_address=funder_address,
            is_active=True,
            is_primary=True, # Default to primary if creating via wallet connect flow
            account_name="Kalshi Account" if platform == "kalshi" else "Trading Account"
        )
        
        # Clear other primary accounts if this is primary
        async with db.begin_nested():
             await db.execute(
                update(TradingAccount)
                .where(TradingAccount.user_id == user_id)
                .values(is_primary=False)
             )
             db.add(account)
        
        await db.commit()
        await db.refresh(account)
        return account

    @staticmethod
    async def delete(db: AsyncSession, user_id: uuid.UUID) -> None:
        """
        Deletes all accounts for a user (used during onboarding reset).
        """
        await db.execute(
            delete(TradingAccount).where(TradingAccount.user_id == user_id)
        )
        await db.commit()

    @staticmethod
    async def get_decrypted_credentials(db: AsyncSession, user_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """
        Retrieves decrypted credentials for the primary account.
        """
        account = await AccountCRUD.get_by_user_id(db, user_id)
        if not account:
            return None
            
        creds = {
            "platform": account.platform or "kalshi",
            "environment": getattr(account, 'environment', 'production'),
            "funder_address": account.funder_address
        }
        
        if account.api_key_encrypted:
            creds["api_key"] = decrypt_credential(account.api_key_encrypted)
        
        if account.api_secret_encrypted:
            creds["api_secret"] = decrypt_credential(account.api_secret_encrypted)

        # Legacy fields
        if account.private_key_encrypted:
             creds["private_key"] = decrypt_credential(account.private_key_encrypted)
             
        return creds

    @staticmethod
    async def update_connection_status(
        db: AsyncSession, 
        user_id: uuid.UUID, 
        is_connected: bool, 
        error_msg: Optional[str] = None
    ) -> None:
        """
        Updates the connection status of the primary account.
        """
        account = await AccountCRUD.get_by_user_id(db, user_id)
        if not account:
            return

        account.is_connected = is_connected
        account.connection_error = error_msg
        if is_connected:
            account.last_verified_at = datetime.now(timezone.utc)
            
        await db.commit()
