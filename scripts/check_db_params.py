
import asyncio
import os
import sys
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add app to path
sys.path.insert(0, '/app')

# Get DB URL from env or default
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@db:5432/polymarket_bot")

async def main():
    print(f"🔌 Connecting to DB: {DATABASE_URL}")
    
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    try:
        async with async_session() as session:
            print("✅ Session created. Querying Global Settings...")
            
            # Simple query to get settings
            result = await session.execute(text("SELECT * FROM global_settings LIMIT 1"))
            rows = result.fetchall()
            
            if rows:
                print("📊 Found Settings:")
                for row in rows:
                    print(row)
            else:
                print("⚠️ No settings found in global_settings table.")
                
    except Exception as e:
        print(f"❌ DB Error: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
