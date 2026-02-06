#!/usr/bin/env python3
"""Check database state for positions and tracked markets."""
import asyncio
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.db.database import async_session_factory
from src.db.crud.position import PositionCRUD
from src.db.crud.tracked_market import TrackedMarketCRUD
from sqlalchemy import select
from src.models.position import Position
from src.models.tracked_market import TrackedMarket

async def check():
    async with async_session_factory() as db:
        # Check open positions
        result = await db.execute(
            select(Position).where(Position.status == "open")
        )
        positions = list(result.scalars().all())
        print(f"Open positions: {len(positions)}")
        for p in positions:
            print(f"  ID={p.id}, ticker={p.token_id[:30] if p.token_id else 'N/A'}, status={p.status}")
        
        # Check tracked markets
        result2 = await db.execute(select(TrackedMarket))
        markets = list(result2.scalars().all())
        print(f"\nTracked markets: {len(markets)}")
        for m in markets[:10]:
            print(f"  condition={m.condition_id[:40] if m.condition_id else 'N/A'}, espn_id={m.espn_event_id}, finished={m.is_finished}")

if __name__ == "__main__":
    asyncio.run(check())
