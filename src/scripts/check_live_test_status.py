
import asyncio
import logging
from sqlalchemy import select, func
from src.db.database import async_session_factory
from src.models.user import User

# from src.models.order import Order <- Removed

from src.models.tracked_market import TrackedMarket

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_status():
    async with async_session_factory() as db:
        # Check ALL Users
        result = await db.execute(select(User))
        users = result.scalars().all()
        
        from src.db.crud.polymarket_account import PolymarketAccountCRUD
        from src.models.position import Position
        from src.models.activity_log import ActivityLog
        
        logger.info(f"Found {len(users)} users:")
        for user in users:
            creds = await PolymarketAccountCRUD.get_decrypted_credentials(db, user.id)
            has_creds = bool(creds and (creds.get("api_key") or creds.get("private_key")))
            
            # Check Tracked Games
            market_count = await db.scalar(
                select(func.count(TrackedMarket.id)).where(TrackedMarket.user_id == user.id)
            )
            
            # Check Positions (Bets Placed)
            position_count = await db.scalar(
                select(func.count(Position.id)).where(Position.user_id == user.id)
            )
            
            # Check Recent Logs
            recent_logs = await db.execute(
                select(ActivityLog.category, ActivityLog.message)
                .where(ActivityLog.user_id == user.id)
                .order_by(ActivityLog.created_at.desc())
                .limit(3)
            )
            logs = [f"{row.category}: {row.message[:50]}..." for row in recent_logs]
            
            logger.info(f"  - {user.username} ({user.id}): Creds={has_creds}, Markets={market_count}, Pos={position_count}")
            if logs:
                for log in logs:
                    logger.info(f"    Last Log: {log}")

if __name__ == "__main__":
    asyncio.run(check_status())
