import os
# MUST SET ENV VAR BEFORE IMPORTING APP MODULES
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_local.db"

import asyncio
from src.db.database import engine, Base
from src.models import *  # Register all models

async def init_db():
    print(f"Initializing database at: {engine.url}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database `test_local.db` initialized successfully.")

if __name__ == "__main__":
    asyncio.run(init_db())
