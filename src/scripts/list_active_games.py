
import asyncio
import os
import sys
from datetime import datetime, timezone

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.services.market_discovery import market_discovery

async def main():
    print("Discovering Kalshi markets via service...")
    # Increase lookahead to ensure we capture everything
    markets = await market_discovery.discover_kalshi_markets(
        sports=["nba", "nfl", "nhl", "mlb"], 
        include_live=True,
        hours_ahead=72
    )
    
    print(f"\nFound {len(markets)} markets.")
    
    now = datetime.now(timezone.utc)
    print(f"Current UTC: {now}")
    
    # Sort by start time to see the "oldest" active games
    markets.sort(key=lambda m: m.game_start_time.timestamp() if m.game_start_time else 0)
    
    print("\n--- Active Markets (Oldest Start Times First) ---")
    for m in markets[:30]: # Print first 30
        start_str = "None"
        hours_ago = "N/A"
        
        if m.game_start_time:
            start_str = str(m.game_start_time)
            diff_sec = (now - m.game_start_time).total_seconds()
            hours_ago = f"{diff_sec/3600:.2f} hours ago"
            
        print(f"\nTicker: {m.ticker} | Sport: {m.sport}")
        print(f"  Question: {m.question}")
        print(f"  Start: {start_str} ({hours_ago})")
        print(f"  End:   {m.end_date}")
        
    # Check for "completed" games logic
    # An NBA game is roughly 2.5 hours. If we see games started > 3 hours ago, likely stale.
    stale_candidates = [m for m in markets if m.game_start_time and (now - m.game_start_time).total_seconds() > 3600 * 3]
    print(f"\n--- Stale Candidates (>3 hours old) ---")
    print(f"Count: {len(stale_candidates)}")
    for m in stale_candidates:
        print(f"  {m.ticker}: Started {m.game_start_time}")

if __name__ == "__main__":
    asyncio.run(main())
