
import asyncio
import os
import sys
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add app to path
sys.path.insert(0, '/app')

# Get DB URL
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@db:5432/polymarket_bot")

async def main():
    print(f"🔌 Connecting to DB...")
    
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    try:
        async with async_session() as session:
            print("✅ Session created. Enabling Bot...")
            
            # Enable bot
            await session.execute(text("UPDATE global_settings SET bot_enabled = true"))
            await session.commit()
            print("🚀 Bot Enabled in Database! The daemon should wake up in ~3s.")
                
    except Exception as e:
        print(f"❌ DB Error: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
