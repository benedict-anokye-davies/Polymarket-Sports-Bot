
import asyncio
import logging
import os
import sys

# FORCE DATABASE TO test_local.db
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_local.db"

from src.db.database import async_session_factory
from src.services.kalshi_client import KalshiClient
from src.db.crud.polymarket_account import PolymarketAccountCRUD
from src.models import User, PolymarketAccount

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def find_nba_game():
    async with async_session_factory() as db:
        # Get Creds (Copy-paste logic from select_all)
        # Use specific username "live_tester"
        from sqlalchemy import select
        result = await db.execute(select(User).where(User.username == "live_tester"))
        user = result.scalars().first()
        
        if not user:
            logger.error("User 'live_tester' not found")
            return

        result = await db.execute(select(PolymarketAccount).where(PolymarketAccount.user_id == user.id))
        account = result.scalar_one_or_none()
        
        from src.core.encryption import decrypt_credential
        api_key = decrypt_credential(account.api_key_encrypted)
        private_key = decrypt_credential(account.private_key_encrypted)
        
        client = KalshiClient(api_key=api_key, private_key_pem=private_key)
        
        logger.info("SEARCHING BROADLY FOR BASKETBALL MARKETS...")
        
        cursor = None
        count = 0
        
        for i in range(5): # Scan 5 pages (1000 markets)
            try:
                logger.info(f"Page {i+1}...")
                response = await client.get_markets(limit=200, cursor=cursor)
                markets = response.get("markets", [])
                
                if not markets:
                    break
                    
                for m in markets:
                    title = m.get("title", "")
                    ticker = m.get("ticker", "")
                    category = m.get("category", "")
                    
                    # Check for Basketball keywords or Team Cities
                    if ("Basketball" in category or "NBA" in ticker or 
                        "Philadelphia" in title or "Los Angeles" in title or "Clippers" in title or "76ers" in title):
                        
                        print(f"[{ticker}] ({category}) {title}")
                        count += 1
                        
                cursor = response.get("cursor")
                if not cursor:
                    break
                    
            except Exception as e:
                logger.error(f"Search failed: {e}")
                break

        logger.info(f"Found {count} potential matches.")

if __name__ == "__main__":
    asyncio.run(find_nba_game())
