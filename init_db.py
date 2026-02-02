"""Initialize database tables."""
import asyncio
from src.db.database import engine, Base
from src.models import (
    User, PolymarketAccount, SportConfig, TrackedMarket,
    Position, Trade, GlobalSettings, ActivityLog, MarketConfig, RefreshToken
)

async def init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created successfully")

if __name__ == "__main__":
    asyncio.run(init())
