import os
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_local.db"
import asyncio
from sqlalchemy import select
from src.db.database import async_session_factory
from src.models import SportConfig, User

SUPPORTED_SPORTS = ["nba", "nfl", "mlb", "nhl", "ncaab", "tennis", "soccer", "mma", "golf"]

async def enable_all_sports():
    async with async_session_factory() as db:
        print("--- Enabling All Sports ---")
        
        # Get User
        result = await db.execute(select(User).where(User.username == "live_tester"))
        user = result.scalars().first()
        if not user:
            print("User 'live_tester' NOT FOUND")
            return

        print(f"User ID: {user.id}")
        
        # Get existing configs
        result = await db.execute(select(SportConfig).where(SportConfig.user_id == user.id))
        existing_configs = {c.sport: c for c in result.scalars().all()}
        
        for sport in SUPPORTED_SPORTS:
            if sport in existing_configs:
                config = existing_configs[sport]
                if not config.enabled:
                    config.enabled = True
                    print(f"Updated {sport}: Enabled=True")
                else:
                    print(f"Skipped {sport}: Already Enabled")
            else:
                # Create new config
                new_config = SportConfig(
                    user_id=user.id,
                    sport=sport,
                    enabled=True
                )
                db.add(new_config)
                print(f"Created {sport}: Enabled=True")
        
        await db.commit()
        print("--- Done ---")

if __name__ == "__main__":
    asyncio.run(enable_all_sports())
