
import asyncio
import sys
import os
sys.path.append("/app")

import logging
logging.basicConfig(level=logging.INFO)

from src.api.routes.bot import get_live_espn_games

async def test_espn():
    print("Fetching Tennis games...")
    games = await get_live_espn_games("tennis")
    print(f"Found {len(games)} games after filtering.")
    for g in games:
        print(f" - {g['name']} | Status: {g['status']} | Date: {g['startTime']}")

if __name__ == "__main__":
    asyncio.run(test_espn())
