#!/usr/bin/env python3
"""
Force-close orphaned positions from Feb 5th games that are already finished.
These positions have no ESPN IDs and can't be resolved automatically.
"""
import asyncio
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select, update
from src.db.database import async_session_factory
from src.models.position import Position
from src.models.tracked_market import TrackedMarket

async def force_close_orphaned():
    async with async_session_factory() as db:
        # Get all open positions
        result = await db.execute(
            select(Position).where(Position.status == "open")
        )
        positions = list(result.scalars().all())
        
        print(f"Found {len(positions)} open positions to close")
        
        closed_count = 0
        for p in positions:
            # Check if from Feb 5th (ticker contains FEB05)
            if p.token_id and "FEB05" in p.token_id.upper():
                # Close as game finished
                p.status = "closed"
                p.exit_reason = "game_finished_manual"
                p.exited_at = datetime.now(timezone.utc)
                # Set exit price to 0 (loss) or 1 (win) based on market resolution
                # For now, assume worst case (full loss) - user can check Kalshi for actual result
                p.exit_price = Decimal("0")
                p.exit_size = p.entry_size
                p.realized_pnl = -p.entry_price * p.entry_size  # Loss = entry cost
                closed_count += 1
                print(f"Closed position {p.id}: {p.token_id}")
        
        # Also mark tracked markets as finished
        result2 = await db.execute(
            select(TrackedMarket).where(TrackedMarket.is_finished == False)
        )
        markets = list(result2.scalars().all())
        
        market_count = 0
        for m in markets:
            if m.condition_id and ("FEB05" in m.condition_id.upper() or "FEB06" in m.condition_id.upper() or "FEB07" in m.condition_id.upper()):
                m.is_finished = True
                m.is_active = False
                market_count += 1
                print(f"Marked market as finished: {m.condition_id}")
        
        await db.commit()
        print(f"\nTotal positions closed: {closed_count}")
        print(f"Total markets marked finished: {market_count}")

if __name__ == "__main__":
    asyncio.run(force_close_orphaned())
