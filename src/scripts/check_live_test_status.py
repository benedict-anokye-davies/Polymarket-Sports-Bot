import os
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_local.db"
import asyncio
from sqlalchemy import select, desc
from src.db.database import async_session_factory
from src.models import ActivityLog, SportConfig, User, TrackedMarket

async def check_status():
    async with async_session_factory() as db:
        print("\n=== LIVE TEST STATUS CHECK ===\n")
        
        # 1. User & Config
        user = (await db.execute(select(User).where(User.username == "live_tester"))).scalar_one_or_none()
        if not user:
            print("ERROR: User 'live_tester' not found")
            return

        print(f"User: {user.username} (ID: {user.id})")
        
        # 2. Sport Configs
        configs = (await db.execute(select(SportConfig).where(SportConfig.user_id == user.id))).scalars().all()
        print("\n--- Sport Configurations ---")
        for c in configs:
            print(f"Sport: {c.sport:<10} Enabled: {str(c.enabled):<5} "
                  f"EntryDrop: {c.entry_threshold_drop} "
                  f"AbsPrice: {c.entry_threshold_absolute} "
                  f"Size: ${c.position_size_usdc}")

        # 3. Tracked Markets
        markets = (await db.execute(select(TrackedMarket).where(
            TrackedMarket.user_id == user.id,
            TrackedMarket.is_user_selected == True
        ))).scalars().all()
        print(f"\n--- Tracked Markets: {len(markets)} ---")
        
        # 4. Recent Logs (Trade/Evaluation related)
        print("\n--- Recent Logs (Last 25) ---")
        logs = (await db.execute(
            select(ActivityLog)
            .where(ActivityLog.user_id == user.id)
            .order_by(desc(ActivityLog.created_at))
            .limit(25)
        )).scalars().all()
        
        for l in reversed(logs):
            print(f"[{l.created_at.strftime('%H:%M:%S')}] [{l.level:<5}] {l.category}: {l.message}")
            if l.details and l.level in ['WARNING', 'ERROR']:
                print(f"   Details: {l.details}")

if __name__ == "__main__":
    asyncio.run(check_status())
