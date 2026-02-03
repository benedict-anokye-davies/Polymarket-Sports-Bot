import os
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_local.db"
import asyncio
from sqlalchemy import update, select
from src.db.database import async_session_factory
from src.models import SportConfig, User

async def force_config_update():
    async with async_session_factory() as db:
        print("\n=== FORCE CONFIG UPDATE ===\n")
        
        user = (await db.execute(select(User).where(User.username == "live_tester"))).scalar_one_or_none()
        if not user:
            print("ERROR: User not found")
            return
            
        stmt = (
            update(SportConfig)
            .where(SportConfig.user_id == user.id)
            .values(
                position_size_usdc=1.0,
                entry_threshold_drop=0.25,
                entry_threshold_absolute=0.50,
                take_profit_pct=0.10,
                stop_loss_pct=0.10,
                enabled=True
            )
        )
        await db.execute(stmt)
        await db.commit()
        print("SUCCESS: Set position_size=$1.00, TP/SL=10% for all sports.")

if __name__ == "__main__":
    asyncio.run(force_config_update())
