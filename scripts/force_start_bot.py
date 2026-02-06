
import asyncio
import os
import sys
import uuid

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.models.trading_account import TradingAccount
from src.services.bot_runner import get_bot_runner, get_bot_status, BotState
from src.db.database import async_session_factory
from src.db.crud.account import AccountCRUD
from src.api.routes.bot import _create_bot_dependencies
from sqlalchemy import select

async def main():
    print("--- Forcing Bot Runner Initialization and Start ---")
    
    async with async_session_factory() as db:
        # 1. Get Primary User/Account
        stmt = select(TradingAccount).where(TradingAccount.is_primary == True).limit(1)
        result = await db.execute(stmt)
        account = result.scalar_one_or_none()
        
        if not account:
            stmt = select(TradingAccount).limit(1)
            result = await db.execute(stmt)
            account = result.scalar_one_or_none()
            
        if not account:
            print("No account found.")
            return

        user_id = account.user_id
        print(f"Target User: {user_id}")

        # check if already running
        status = get_bot_status(user_id)
        if status and status.get("state") == "running":
            print("Bot is already running according to in-memory state.")
            # return # Continue anyway to be sure

        # 2. Recreate dependencies
        credentials = await AccountCRUD.get_decrypted_credentials(db, user_id)
        if not credentials:
            print("Failed to get credentials.")
            return

        trading_client, trading_engine, espn_service = await _create_bot_dependencies(
            db, user_id, credentials
        )

        # 3. Get Runner
        bot_runner = await get_bot_runner(
            user_id=user_id,
            trading_client=trading_client,
            trading_engine=trading_engine,
            espn_service=espn_service
        )

        # 4. Initialize and Start
        print("Initializing bot runner (this triggers position recovery)...")
        await bot_runner.initialize(db, user_id)
        
        print("Starting bot background loops...")
        # Note: We can't easily start it in THIS script process and leave it running in the API process
        # UNLESS this script IS the API process or we use a persistent mechanism.
        # But for verification, we can run initialize() here and see the logs.
        # To make it PERSISTENT in the container, we should really fix src/main.py.

        # For now, let's just run initialize() to see the recovery logs.
        # Then I will implement the auto-start in main.py.
        
        print("Initialization complete. check docker logs for 'Recovered' messages.")

if __name__ == "__main__":
    asyncio.run(main())
