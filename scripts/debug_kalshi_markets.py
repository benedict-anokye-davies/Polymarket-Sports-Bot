
import asyncio
import logging
import sys
import os
from datetime import datetime, timezone, timedelta
import httpx

# Mock the class structures
class MockMarketDiscovery:
    SPORT_KEYWORDS = {
        "nba": ["nba", "lakers", "celtics", "warriors", "nets", "bulls", "heat", 
                "knicks", "sixers", "suns", "bucks", "mavs", "nuggets", "clippers",
                "basketball", "cavaliers", "raptors", "pacers", "hawks", "hornets",
                "pistons", "magic", "wizards", "thunder", "blazers", "jazz", "kings",
                "spurs", "grizzlies", "pelicans", "timberwolves", "rockets",
                # Cities
                "boston", "brooklyn", "york", "philadelphia", "toronto", "chicago",
                "cleveland", "detroit", "indiana", "milwaukee", "atlanta", "charlotte",
                "miami", "orlando", "washington", "denver", "minnesota", "oklahoma",
                "portland", "utah", "golden state", "los angeles", "phoenix", "sacramento",
                "dallas", "houston", "memphis", "orleans", "san antonio"],
        # ... (rest omitted for brevity, focusing on NBA)
    }

    def _detect_sport(self, text: str) -> str | None:
        text_lower = text.lower()
        for sport, keywords in self.SPORT_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return sport
        return None

async def debug_discovery():
    discovery = MockMarketDiscovery()
    client = httpx.AsyncClient()
    
    print("Fetching markets from Kalshi...")
    kalshi_api_base = "https://api.elections.kalshi.com/trade-api/v2"
    
    all_markets = []
    cursor = None
    page_count = 0
    
    # Fetch first 1000 to save time
    while len(all_markets) < 1000:
        params = {
            "category": "Sports",
            "status": "open",
            "limit": 200
        }
        if cursor:
            params["cursor"] = cursor
        
        try:
            resp = await client.get(f"{kalshi_api_base}/markets", params=params)
            data = resp.json()
            markets = data.get("markets", [])
            if not markets:
                break
            all_markets.extend(markets)
            cursor = data.get("cursor")
            page_count += 1
            print(f"Page {page_count}: Fetched {len(markets)} markets. Total: {len(all_markets)}")
            if not cursor:
                break
        except Exception as e:
            print(f"Error fetching: {e}")
            break

    print(f"\nAnalyzing {len(all_markets)} markets...")
    
    accepted_count = 0
    rejection_reasons = {}
    
    sports_filter = ["nba"] # We are interested in NBA specifically
    min_volume = 100
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(hours=168) # 7 days
    
    for i, market in enumerate(all_markets):
        ticker = market.get("ticker", "")
        title = market.get("title", "")
        status = market.get("status", "")
        
        reason = None
        
        # 1. Status Filter
        if status not in ["open", "active"]:
            reason = f"Status '{status}' not open/active"
        
        # 2. Sport Detection
        if not reason:
            is_special_nba = False
            if "Philadelphia" in title and "Los Angeles" in title:
                is_special_nba = True
            elif "76ers" in title and "Clippers" in title:
                is_special_nba = True
                
            if is_special_nba:
                sport = "nba"
            else:
                sport = discovery._detect_sport(title)
            
            if not sport:
                # Try ticker
                if "NBA" in ticker.upper():
                    sport = "nba"
            
            if not sport:
                reason = "Sport not detected"
            elif sport not in sports_filter:
                reason = f"Sport '{sport}' not in {sports_filter}"
        
        # 3. Timing Filter
        if not reason:
            close_ts = market.get("close_ts", 0)
            if not close_ts:
                # reason = "No close_ts" 
                # PERMISSIVE CHECK: If status is Open, we allow it
                pass
            else:
                end_date = datetime.fromtimestamp(close_ts, tz=timezone.utc)
                if end_date < now:
                    reason = f"Ended (close_ts {end_date})"
                # elif end_date > cutoff: # Temporarily disable cutoff to see if that's the issue
                #    reason = f"Too far in future ({end_date})"
        
        # 4. Volume Filter
        if not reason:
            volume = market.get("volume_yes", 0) + market.get("volume_no", 0)
            if volume < min_volume:
                reason = f"Low Volume ({volume} < {min_volume})"

        if reason:
            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
            if i < 20: # Print details for first few
                 print(f"REJECTED {ticker}: {reason} | Title: {title}")
        if " vs " in title.lower() or " beat " in title.lower():
             print(f"STANDARD MARKET: {ticker} | {title}")
             
        if "detroit" in title.lower() or "denver" in title.lower() or "pistons" in title.lower() or "nuggets" in title.lower():
             print(f"MATCH_CANDIDATE: {ticker} | {title} | Status: {status}")

        if not reason:
            accepted_count += 1
            # print(f"✅ ACCEPTED {ticker}: {title} | Sport: {sport} | Vol: {market.get('volume_yes',0)+market.get('volume_no',0)}")

    print("\nSummary:")
    print(f"Total: {len(all_markets)}")
    print(f"Accepted: {accepted_count}")
    print("Rejection Reasons:")
    for r, c in rejection_reasons.items():
        print(f"  {r}: {c}")

    await client.aclose()

if __name__ == "__main__":
    asyncio.run(debug_discovery())
