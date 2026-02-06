#!/usr/bin/env python3
"""Force-close ALL remaining orphaned positions as finished games."""
import asyncio
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select
from src.db.database import async_session_factory
from src.models.position import Position

async def force_close_all():
    async with async_session_factory() as db:
        result = await db.execute(
            select(Position).where(Position.status == "open")
        )
        positions = list(result.scalars().all())
        
        print(f"Found {len(positions)} open positions to close")
        
        for p in positions:
            p.status = "closed"
            p.exit_reason = "game_finished_manual"
            p.exited_at = datetime.now(timezone.utc)
            p.exit_price = Decimal("0")  # Assume loss - user can check Kalshi for actual results
            p.exit_size = p.entry_size
            p.realized_pnl = -p.entry_price * p.entry_size
            print(f"Closed: {p.token_id}")
        
        await db.commit()
        print(f"\nTotal positions closed: {len(positions)}")

if __name__ == "__main__":
    asyncio.run(force_close_all())
