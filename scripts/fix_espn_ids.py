
import asyncio
import os
import sys

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select, update
from src.db.database import async_session_factory
from src.models.tracked_market import TrackedMarket

mapping = {
    "MEMORL": "401705187",
    "DETNYK": "401705184",
    "BOSCHO": "401705186",
    "PHIATL": "401705185",
    "MINDEN": "401705189",
    "GSWLAL": "401705191",
    "MINOKC": "401705192",
    "CLEORL": "401705183"
}

async def update_markets():
    async with async_session_factory() as db:
        stmt = select(TrackedMarket).where(TrackedMarket.espn_event_id == None)
        result = await db.execute(stmt)
        markets = result.scalars().all()
        
        updated_count = 0
        for m in markets:
            ticker = m.condition_id
            # KXNBAGAME-26FEB06MEMORL-ORL
            parts = ticker.split("-")
            if len(parts) >= 3:
                teams_part = parts[2]
                team_chars = ""
                # Skip the date part (26FEB06)
                if len(teams_part) > 7:
                    team_chars = teams_part[7:] 
                
                if team_chars in mapping:
                    eid = mapping[team_chars]
                    m.espn_event_id = eid
                    # Also set sport to nba just in case
                    m.sport = "nba"
                    updated_count += 1
                    print(f"Updated {ticker} with ESPN ID {eid}")
        
        await db.commit()
        print(f"Total updated: {updated_count}")

if __name__ == "__main__":
    asyncio.run(update_markets())
