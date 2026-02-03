
import asyncio
import os
import sys
from datetime import datetime, timezone

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.services.market_discovery import market_discovery

async def main():
    print("Fetching Kalshi markets...")
    markets = await market_discovery.discover_kalshi_markets(sports=None, include_live=True)
    
    print(f"\nFound {len(markets)} markets after discovery filtering.")
    
    print("\n--- Market Analysis ---")
    now = datetime.now(timezone.utc)
    print(f"Current UTC Time: {now}")
    
    count_stale = 0
    for m in markets:
        # We need to peek at the raw market data if possible, but DiscoveredMarket object 
        # has correctly parsed datetime objects. Let's inspect those.
        
        is_stale = False
        if m.end_date and m.end_date < now:
            is_stale = True
            count_stale += 1
            
        if m.game_start_time and m.game_start_time < now:
             # Game started in the past - this is fine for LIVE games, but we want to see how old
             pass
             
        # Print details for potential stale markets or just the first few
        if is_stale or (m.game_start_time and (now - m.game_start_time).total_seconds() > 3600*5):
             print(f"\n[POTENTIAL STALE] {m.ticker}")
             print(f"  Question: {m.question}")
             print(f"  Game Start: {m.game_start_time}")
             print(f"  End Date:   {m.end_date}")
             print(f"  Status:     {m.platform} (Assumed Open)")
             
             if m.end_date:
                 diff = (now - m.end_date).total_seconds() / 3600
                 print(f"  Ended {diff:.2f} hours ago")
    
    print(f"\nTotal strictly stale markets (end_date < now): {count_stale}")
    
    # Let's also do a raw fetch to check keys if needed, 
    # but market_discovery already does the fetch.
    # To truly debug the raw values, we might want to bypass discover_kalshi_markets logic
    # or rely on what we see above. 
    # If count_stale is 0, then the logic in discover_kalshi_markets IS filtering them out, 
    # and the user might be seeing cached data or I need to check the raw response.

if __name__ == "__main__":
    asyncio.run(main())
