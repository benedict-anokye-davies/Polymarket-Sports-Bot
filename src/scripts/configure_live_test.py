
import os
# FORCE DATABASE TO test_local.db
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_local.db"

import asyncio
import logging
from decimal import Decimal
from src.db.database import async_session_factory
from src.db.crud.sport_config import SportConfigCRUD
from src.db.crud.tracked_market import TrackedMarketCRUD
from src.db.crud.user import UserCRUD
from src.models.sport_config import SportConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def configure_live_test():
    async with async_session_factory() as db:
        # Get the main user (assuming single user or first user)
        from sqlalchemy import select
        from src.models.user import User
        
        
        result = await db.execute(select(User))
        users = result.scalars().all()
        
        if not users:
            logger.info("No users found. Creating default 'live_tester' user...")
            # Create default user
            from src.db.crud.user import UserCRUD
            try:
                user = await UserCRUD.create(db, "live_tester", "test@example.com", "password123")
                # Create default sport configs for new user
                await SportConfigCRUD.create_defaults_for_user(db, user.id)
                logger.info("Created user: live_tester / password123")
            except Exception as e:
                logger.error(f"Failed to create user: {e}")
                return
        else:
            user = users[0]
            
        logger.info(f"Configuring for user: {user.username} ({user.id})")

        # Sports to configure
        # Attempting to support NBA and CBB (mapped to 'ncaab' or 'basketball_ncaab' typically, 
        # but let's try 'ncaab' as it's common. If not present, we create it.)
        target_sports = ['nba', 'ncaab'] 

        for sport in target_sports:
            logger.info(f"Configuring {sport}...")
            
            # Check/Create Config
            config = await SportConfigCRUD.get_by_user_and_sport(db, user.id, sport)
            if not config:
                logger.info(f"Creating new config for {sport}")
                config = await SportConfigCRUD.create(db, user.id, sport)
            
            # Update Parameters
            # Bet Size: $1
            # TP: 10% (0.10)
            # SL: 10% (0.10)
            # Entry Threshold: 25% (0.25) -> This means if price <= 0.25
            
            updated_config = await SportConfigCRUD.update(
                db, 
                config.id,
                enabled=True,
                position_size_usdc=Decimal("1.00"),
                take_profit_pct=Decimal("0.10"),
                stop_loss_pct=Decimal("0.10"),
                entry_threshold_absolute=Decimal("0.25"), # "If pregame probability goes below 25%" -> interpreted as price < 0.25
                entry_threshold_drop=Decimal("0.15"), # Keep default drop logic as secondary
                max_positions_per_game=5, # Allow multiple bets if needed
                max_total_positions=20 # Allow enough room for "all games"
            )
            logger.info(f"Updated {sport} config: Size=${updated_config.position_size_usdc}, TP={updated_config.take_profit_pct}, SL={updated_config.stop_loss_pct}, Entry<{updated_config.entry_threshold_absolute}")

            # Select All Active Games
            logger.info(f"Selecting all active games for {sport}...")
            count = await TrackedMarketCRUD.select_all_by_sport(db, user.id, sport)
            logger.info(f"Selected {count} games for {sport}.")

if __name__ == "__main__":
    asyncio.run(configure_live_test())
