
import asyncio
import os
import sys
import uuid
from decimal import Decimal
from datetime import datetime, timezone

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.models.trading_account import TradingAccount
from src.models.tracked_market import TrackedMarket
from src.models.position import Position
from src.services.kalshi_client import KalshiClient
from src.db.database import async_session_factory
from sqlalchemy import select
from src.core.encryption import decrypt_credential

async def main():
    print("--- Synchronizing Kalshi Positions to Local DB ---")
    
    async with async_session_factory() as db:
        # 1. Get User and Account
        stmt = select(TradingAccount).where(TradingAccount.is_primary == True).limit(1)
        result = await db.execute(stmt)
        account = result.scalar_one_or_none()
        
        if not account:
            stmt = select(TradingAccount).limit(1)
            result = await db.execute(stmt)
            account = result.scalar_one_or_none()
            
        if not account:
            print("No trading account found in DB.")
            return

        user_id = account.user_id
        print(f"Syncing for User: {user_id}")

        # 2. Setup Kalshi Client
        creds = {}
        if account.api_key_encrypted:
            creds["api_key"] = decrypt_credential(account.api_key_encrypted)
        if account.private_key_encrypted:
            creds["private_key"] = decrypt_credential(account.private_key_encrypted)
        if account.api_secret_encrypted:
            creds["api_secret"] = decrypt_credential(account.api_secret_encrypted)

        client = KalshiClient(
            api_key=creds.get("api_key"),
            private_key_pem=creds.get("private_key") or creds.get("api_secret")
        )

        # 3. Fetch Positions from Exchange
        print("Fetching positions from Kalshi Exchange...")
        try:
            pos_data = await client.get_positions()
            # The client usually returns a dict with 'market_positions'
            exchange_positions = pos_data.get("market_positions", []) if isinstance(pos_data, dict) else []
            print(f"Found {len(exchange_positions)} positions on exchange.")
        except Exception as e:
            print(f"Error fetching positions: {e}")
            return

        # 4. Target Team Mapping (Helpful for NBA)
        team_map = {
            "LAL": "Los Angeles Lakers",
            "GSW": "Golden State Warriors",
            "DET": "Detroit Pistons",
            "ORL": "Orlando Magic",
            "ATL": "Atlanta Hawks",
            "TOR": "Toronto Raptors",
            "HOU": "Houston Rockets",
            "SAS": "San Antonio Spurs",
            "PHX": "Phoenix Suns",
            "BKN": "Brooklyn Nets",
            "CHI": "Chicago Bulls",
            "DAL": "Dallas Mavericks",
            "OKC": "Oklahoma City Thunder",
            "UTA": "Utah Jazz",
            "NYK": "New York Knicks",
            "CHA": "Charlotte Hornets",
            "WAS": "Washington Wizards"
        }

        synced_count = 0
        for ep in exchange_positions:
            ticker = ep.get("ticker")
            count = ep.get("position", 0)
            
            if count == 0:
                continue
                
            print(f"\nProcessing Ticker: {ticker} (Size: {count})")
            
            # Check if exists in DB
            stmt = select(Position).where(Position.token_id == ticker, Position.status == "open", Position.user_id == user_id)
            result = await db.execute(stmt)
            local_pos = result.scalar_one_or_none()
            
            if local_pos:
                print(f" - Local position already exists: {local_pos.id}")
                continue

            # Need to create Position and TrackedMarket
            # 5. Get Market Metadata
            try:
                m_resp = await client.get_market(ticker)
                m_data = m_resp.get("market", m_resp)
                title = m_data.get("title", "NBA Game")
            except Exception as e:
                print(f" - Error fetching market data for {ticker}: {e}")
                title = "NBA Game"

            # Parse Ticker for Teams
            # KXNBAGAME-26FEB07GSWLAL-LAL
            parts = ticker.split("-")
            home_team = "Unknown"
            away_team = "Unknown"
            target_team_name = "Unknown"
            
            if len(parts) >= 3:
                teams_part = parts[2] # e.g. 26FEB07GSWLAL
                # This is messy to parse perfectly without knowing length of date part
                # But usually ends with 6 chars for teams (GSWLAL)
                team_chars = teams_part[-6:]
                team1_abbr = team_chars[:3]
                team2_abbr = team_chars[3:]
                
                # Kalshi usually lists AWAY then HOME in that compressed part? 
                # Or alphabetically? 
                # Title usually says "Will [Team] win... vs [Other]?"
                # Let's use the mapping
                away_team = team_map.get(team1_abbr, team1_abbr)
                home_team = team_map.get(team2_abbr, team2_abbr)
                
                target_abbr = parts[-1]
                target_team_name = team_map.get(target_abbr, target_abbr)

            # Check/Create TrackedMarket
            stmt = select(TrackedMarket).where(TrackedMarket.condition_id == ticker, TrackedMarket.user_id == user_id)
            result = await db.execute(stmt)
            tm = result.scalar_one_or_none()
            
            if not tm:
                print(f" - Creating TrackedMarket for {ticker}")
                tm = TrackedMarket(
                    user_id=user_id,
                    condition_id=ticker,
                    token_id_yes=ticker,
                    token_id_no=ticker, # Kalshi uses same ticker or we just need one for tracking
                    question=title,
                    sport="nba",
                    home_team=home_team,
                    away_team=away_team,
                    is_user_selected=True,
                    auto_discovered=False,
                    baseline_price_yes=Decimal("0.5"), # Unknown baseline
                    current_price_yes=Decimal(str(ep.get("last_price", 50) / 100.0))
                )
                db.add(tm)
                await db.flush()
            
            # Create Position
            print(f" - Creating Position record...")
            new_pos = Position(
                user_id=user_id,
                tracked_market_id=tm.id,
                condition_id=ticker,
                token_id=ticker,
                side="YES",
                team=target_team_name,
                entry_price=Decimal(str(ep.get("avg_cost", 50) / 100.0)),
                entry_size=Decimal(str(count)),
                entry_cost_usdc=Decimal(str(ep.get("market_exposure", 0))),
                entry_reason="Manual/External Sync",
                status="open",
                opened_at=datetime.now(timezone.utc)
            )
            db.add(new_pos)
            synced_count += 1

        await db.commit()
        print(f"\nSuccessfully synced {synced_count} positions.")

if __name__ == "__main__":
    asyncio.run(main())
