
import os
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_local.db"

import asyncio
import logging
from decimal import Decimal
from sqlalchemy import select
from src.db.database import async_session_factory
from src.models import User, TrackedMarket, MarketConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def apply_strategy():
    async with async_session_factory() as db:
        # 1. Get User
        result = await db.execute(select(User).where(User.username == "live_tester"))
        user = result.scalars().first()
        if not user:
            result = await db.execute(select(User))
            user = result.scalars().first()
        
        if not user:
            logger.error("No user found.")
            return

        logger.info(f"Applying strategy for User: {user.username} ({user.id})")

        # 2. Get active NBA/NCAAB markets
        query = select(TrackedMarket).where(
            TrackedMarket.sport.in_(["nba", "ncaab"]),
            TrackedMarket.is_user_selected == True
        )
        result = await db.execute(query)
        markets = result.scalars().all()
        
        logger.info(f"Found {len(markets)} active markets to configure.")

        updated_count = 0
        
        for m in markets:
            # Check for existing config
            config_query = select(MarketConfig).where(
                MarketConfig.user_id == user.id,
                MarketConfig.condition_id == m.condition_id
            )
            res = await db.execute(config_query)
            config = res.scalar_one_or_none()
            
            if not config:
                config = MarketConfig(
                    user_id=user.id,
                    condition_id=m.condition_id,
                    sport=m.sport,
                    market_question=m.question,
                    home_team=m.home_team,
                    away_team=m.away_team
                )
                db.add(config)
            
            # Apply Strategy Settings
            # Bet Size: $1
            config.position_size_usdc = Decimal("1.00")
            
            # TP/SL: 10%
            config.take_profit_pct = Decimal("0.10")
            config.stop_loss_pct = Decimal("0.10")
            
            # Entry: Probability < 25% (0.25)
            # We set 'entry_threshold_absolute' to 0.25, meaning buy if price <= 0.25
            config.entry_threshold_absolute = Decimal("0.25")
            
            # Reset defaults for conflicting strategies
            config.entry_threshold_drop = None # Don't rely on drop from baseline
            config.enabled = True
            config.auto_trade = True
            
            updated_count += 1
            
        await db.commit()
        logger.info(f"✅ Successfully configured {updated_count} markets with: Size=$1, TP=10%, SL=10%, Entry<0.25")

if __name__ == "__main__":
    asyncio.run(apply_strategy())
