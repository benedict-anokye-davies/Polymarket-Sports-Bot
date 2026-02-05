
import asyncio
import os
import sys
import logging
import traceback

# Add src to path
sys.path.append(os.getcwd())

from sqlalchemy import select
from src.db.database import async_session_factory
from src.models import User
from src.services.account_manager import AccountManager
from src.db.crud.account import AccountCRUD
from src.services.kalshi_client import KalshiClient
from src.core.encryption import decrypt_credential

# Configure logging to show everything
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("debug_accounts")

async def debug_accounts():
    async with async_session_factory() as db:
        print("\n--- Debugging Account Manager (Target: e2euser) ---")
        
        # Check Env
        enc_key = os.environ.get("ENCRYPTION_KEY")
        print(f"ENCRYPTION_KEY present: {bool(enc_key)}")
        if enc_key:
            print(f"ENCRYPTION_KEY length: {len(enc_key)}")
            print(f"ENCRYPTION_KEY start: {enc_key[:4]}...")

        # List all users
        print("\nListing all users:")
        users_result = await db.execute(select(User))
        all_users = users_result.scalars().all()
        for u in all_users:
            print(f" - {u.email} ({u.username}) ID: {u.id}")

        # Get e2euser
        result = await db.execute(select(User).where(User.email == "e2e@test.com").limit(1))
        user = result.scalar_one_or_none()
        
        if not user:
            print("No 'e2euser' found! Falling back to any user.")
            result = await db.execute(select(User).limit(1))
            user = result.scalar_one_or_none()
            
        print(f"User found: {user.email} ({user.id})")
        
        manager = AccountManager(db, user.id)
        
        print("\n1. Fetching Active Accounts...")
        accounts = await manager.get_active_accounts()
        print(f"Found {len(accounts)} accounts")
        
        from src.services.kalshi_client import KalshiClient
        
        for acc in accounts:
            print(f"\n[Account {acc.account_name}]")
            print(f"  ID: {acc.id}")
            print(f"  Platform: {acc.platform}")
            print(f"  Primary: {acc.is_primary}")
            print(f"  API Key Encrypted: {bool(acc.api_key_encrypted)}")
            
            print("  -> MANUAL DEBUG: Decrypting credentials...")
            try:
                creds = await AccountCRUD.get_decrypted_credentials(db, acc.id)
                if not creds:
                    print("     !!! No credentials found via AccountCRUD (Expected since AccountCRUD uses user_id)")
                    # continue <-- REMOVED

                    
                api_key = creds.get("api_key")
                api_secret = creds.get("api_secret") or creds.get("private_key")
                
                print(f"     API Key starts with: {api_key[:4] if api_key else 'None'}")
                print(f"     API Secret length: {len(api_secret) if api_secret else 0}")
                
                if not api_key or not api_secret:
                    print("     !!! Missing API Key or Secret")
                    continue
                    
                print("  -> MANUAL DEBUG: Creating KalshiClient...")
                try:
                    client = KalshiClient(api_key=api_key, private_key_pem=api_secret)
                    print("     Client created successfully (in manual test)")
                    
                    print("     -> Fetching balance (Manual)...")
                    balance = await client.get_balance()
                    print(f"     Balance Result: {balance}")
                    await client.close()
                    
                except Exception as e:
                    print(f"     !!! Client Creation/Usage Failed: {e}")
                    traceback.print_exc()
                    
            except Exception as e:
                print(f"     !!! Credential Decryption Failed: {e}")
                traceback.print_exc()

            print("\n  -> Attempting via AccountManager (Reproducing issue)...")
            try:
                client = await manager.get_client_for_account(acc.id)
                if client:
                    print("     Client created successfully via Manager")
                else:
                    print("     !!! Client is None via Manager (See previous logs for why)")
            except Exception as e:
                print(f"     !!! Exception: {e}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(debug_accounts())
