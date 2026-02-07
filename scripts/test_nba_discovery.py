"""
Find LIVE games (Feb 6 games that are still active).
"""
import asyncio
import httpx

async def find_live_games():
    print("=" * 60)
    print("LIVE GAMES RIGHT NOW (Feb 6 games still active)")
    print("=" * 60)
    
    # Teams you mentioned with live games
    teams = {
        "DET": "Detroit Pistons (vs Knicks - Q4)",
        "BOS": "Boston Celtics (vs Heat - Q4)", 
        "MIN": "Minnesota Timberwolves (vs Pelicans - Q4)",
        "LAC": "Los Angeles Clippers (vs Kings)",
        "POR": "Portland Trail Blazers (vs Grizzlies)"
    }
    
    kalshi_api_base = "https://api.elections.kalshi.com/trade-api/v2"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Get ALL game markets
        params = {"series_ticker": "KXNBAGAME", "limit": 200}
        resp = await client.get(f"{kalshi_api_base}/markets", params=params)
        
        if resp.status_code == 200:
            data = resp.json()
            markets = data.get("markets", [])
            
            # Filter for Feb 6 games that are ACTIVE (still in progress)
            feb06_markets = [m for m in markets if "26FEB06" in m.get("ticker", "")]
            active_feb06 = [m for m in feb06_markets if m.get("status") == "active"]
            
            print(f"\nFeb 6 markets: {len(feb06_markets)}")
            print(f"Active (still live): {len(active_feb06)}")
            
            print("\n📺 LIVE GAMES RIGHT NOW:")
            print("-" * 60)
            seen_games = set()
            for m in active_feb06:
                ticker = m.get("ticker", "")
                parts = ticker.split("-")
                if len(parts) >= 2:
                    game_id = parts[1]
                    if game_id not in seen_games:
                        seen_games.add(game_id)
                        title = m.get("title", "")
                        yes_bid = m.get("yes_bid", 0)
                        yes_ask = m.get("yes_ask", 0)
                        print(f"  🔴 {title}")
                        print(f"     Ticker: {ticker.replace('-'+ticker.split('-')[-1], '')}")
            
            print(f"\n\n🎯 YOUR TARGET TEAMS - LIVE STATUS:")
            print("-" * 60)
            for abbr, name in teams.items():
                # Check both Feb 6 and Feb 7
                matches = [m for m in markets if abbr in m.get("ticker", "") and m.get("status") == "active"]
                if matches:
                    m = matches[0]
                    ticker = m.get("ticker")
                    title = m.get("title", "")
                    yes_bid = m.get("yes_bid", 0)
                    yes_ask = m.get("yes_ask", 0)
                    print(f"\n✅ {name}")
                    print(f"   Ticker: {ticker}")
                    print(f"   {title}")
                    print(f"   YES Bid: {yes_bid}¢ | YES Ask: {yes_ask}¢")
                else:
                    # Check if finalized
                    finalized = [m for m in markets if abbr in m.get("ticker", "") and m.get("status") == "finalized"]
                    if finalized:
                        print(f"\n⏹️ {name} - Game ended (finalized)")
                    else:
                        print(f"\n❌ {name} - Not found")
        else:
            print(f"Error: HTTP {resp.status_code}")

if __name__ == "__main__":
    asyncio.run(find_live_games())
