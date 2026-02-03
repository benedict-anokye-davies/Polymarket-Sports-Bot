
import os
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_local.db"

import asyncio
import logging
from sqlalchemy import select, func
from src.db.database import async_session_factory
from src.models import User, PolymarketAccount, TrackedMarket
from src.services.kalshi_client import KalshiClient
from src.core.encryption import decrypt_credential

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def select_all_markets():
    async with async_session_factory() as db:
        # 1. Get User & Credentials
        # Use specific username "live_tester" as confirmed by bot logs
        result = await db.execute(select(User).where(User.username == "live_tester"))
        user = result.scalars().first()
        
        if not user:
            # Fallback to dev_user if live_tester not found
            result = await db.execute(select(User).where(User.username == "dev_user"))
            user = result.scalars().first()

        if not user:
            # Fallback to ANY user
            result = await db.execute(select(User))
            user = result.scalars().first()
            
        if not user:
            logger.error("No user found.")
            return
        logger.info(f"Using User ID: {user.id}")
        result = await db.execute(select(PolymarketAccount).where(PolymarketAccount.user_id == user.id))
        account = result.scalar_one_or_none()
        
        if not account or account.platform != "kalshi":
            logger.error("No Kalshi account found.")
            return

        # 2. Init Client
        api_key = decrypt_credential(account.api_key_encrypted)
        private_key = decrypt_credential(account.private_key_encrypted)
        
        client = KalshiClient(api_key=api_key, private_key_pem=private_key)
        
        # 3. Fetch Markets
        logger.info("Fetching Kalshi markets...")
        cursor = None
        selected_count = 0
        updated_count = 0
        pages_processed = 0
        
        while True:
            try:
                logger.info(f"Fetching page {pages_processed+1}... (Selected so far: {selected_count})")
                response = await client.get_markets(limit=200, cursor=cursor)
                # print(f"DEBUG: Raw Response Keys: {response.keys()}")
                page_markets = response.get("markets", [])
                
                if not page_markets:
                    break
                    
                for m in page_markets:
                    ticker = m.get("ticker", "")
                    category = m.get("category", "")
                    title = m.get("title", "")
                    
                    # Filter logic
                    is_relevant = False
                    
                    # 1. Target Game Check (Priority)
                    if ("76ers" in title or "Clippers" in title or 
                        "Philadelphia" in title or "Los Angeles" in title):
                        is_relevant = True
                        logger.info(f"🎯 MATCH FOUND: {title}")
                    
                    # 2. General NBA/CBB Check
                    elif "NBA" in ticker or "CBB" in ticker or "Basketball" in category:
                        is_relevant = True
                    
                    # 3. Fallback for mixed categories
                    elif category == "" and (" vs " in title or " @ " in title):
                         if "," not in title: # Avoid props mainly, but allow our target game even if commas
                             is_relevant = True

                    if not is_relevant:
                        continue

                    logger.info(f"Selecting market: {ticker} - {title}")
                    
                    # Add to TrackedMarket or Update existing
                    existing_query = await db.execute(select(TrackedMarket).where(TrackedMarket.condition_id == ticker))
                    existing_market = existing_query.scalar_one_or_none()
                    
                    if existing_market:
                         # Force UPDATE if teams are unknown but we detected keywords
                        if existing_market.home_team == "Unknown" and ("Philadelphia" in title or "Los Angeles" in title):
                             existing_market.home_team = "Philadelphia 76ers"
                             existing_market.away_team = "Los Angeles Clippers"
                             existing_market.sport = "nba"
                             updated_count += 1
                             logger.info(f"UPDATED TEAMS for existing: {ticker}")
                        
                        if not existing_market.is_user_selected:
                            existing_market.is_user_selected = True
                            updated_count += 1
                        continue
                        
                    token_id = m.get("id") or ticker

                    # Parse teams
                    home, away = "Unknown", "Unknown"
                    clean_title = title.replace(" at ", " @ ").replace(" versus ", " vs ").replace(" VS ", " vs ")
                    
                    # Explicit Parsing Priority
                    if "Philadelphia" in title and "Los Angeles" in title:
                         home = "Philadelphia 76ers"
                         away = "Los Angeles Clippers"
                    
                    if home == "Unknown":
                        if " vs " in clean_title:
                            parts = clean_title.split(" vs ")
                            if len(parts) >= 2:
                                away, home = parts[0].strip(), parts[1].strip()
                        elif " @ " in clean_title:
                            parts = clean_title.split(" @ ")
                            if len(parts) >= 2:
                                away, home = parts[0].strip(), parts[1].strip()

                    tm = TrackedMarket(
                        user_id=user.id,
                        condition_id=ticker,
                        token_id_yes=token_id,
                        token_id_no=f"{token_id}_NO",
                        sport="nba" if "NBA" in ticker and "KXMV" not in ticker else "ncaab", # Logic: MultiVerse might default to ncaab/mixed
                        # Actually just force NBA if teams match
                        question=title,
                        home_team=home,
                        away_team=away,
                        is_user_selected=True
                    )
                    
                    if "Philadelphia 76ers" in home:
                        tm.sport = "nba"

                    db.add(tm)
                    selected_count += 1
                
                # Commit every page or so
                await db.commit()
                
                # Exit conditions
                if selected_count > 400:
                    logger.info("Found likely all markets, stopping search.")
                    break
                    
                cursor = response.get("cursor")
                if not cursor:
                    break
                    
                pages_processed += 1
                if pages_processed > 200: # 40k markets max
                    logger.info("Scanned 200 pages, stopping.")
                    break
                    
            except Exception as e:
                logger.error(f"Failed to fetch/process markets: {e}")
                break
                
        logger.info(f"✅ Successfully selected {selected_count} new markets and updated {updated_count}.")

if __name__ == "__main__":
    asyncio.run(select_all_markets())
