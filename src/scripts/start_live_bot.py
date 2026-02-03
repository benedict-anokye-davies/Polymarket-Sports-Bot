
import os
# FORCE DATABASE TO test_local.db
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_local.db"

import asyncio
import logging
from src.db.database import async_session_factory
from src.services.bot_runner import get_bot_runner
from src.api.routes.bot import _create_bot_dependencies
from src.db.crud.polymarket_account import PolymarketAccountCRUD
from sqlalchemy import select
from src.models.user import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def start_live_bot():
    async with async_session_factory() as db:
        # Get ALL users
        result = await db.execute(select(User))
        users = result.scalars().all()
        
        target_user = None
        target_creds = None
        
        for user in users:
            logger.info(f"Checking user: {user.username} ({user.id})")
            creds = await PolymarketAccountCRUD.get_decrypted_credentials(db, user.id)
            if creds and (creds.get("api_key") or creds.get("private_key")):
                target_user = user
                target_creds = creds
                break
        
        if not target_user:
            logger.error("No users with credentials found in test_local.db!")
            return

        logger.info(f"Found active user: {target_user.username}")

        try:
            # Create Dependencies
            trading_client, trading_engine, espn_service = await _create_bot_dependencies(
                db, target_user.id, target_creds
            )
            
            # Get Runner
            bot_runner = await get_bot_runner(
                user_id=target_user.id,
                trading_client=trading_client,
                trading_engine=trading_engine,
                espn_service=espn_service
            )
            
            # Initialize
            await bot_runner.initialize(db, target_user.id)
            logger.info("Bot initialized. Starting main loop...")
            
            # Start (Blocking Loop)
            await bot_runner.start(db)
            
        except Exception as e:
            logger.error(f"Failed to start bot: {e}")

if __name__ == "__main__":
    asyncio.run(start_live_bot())
