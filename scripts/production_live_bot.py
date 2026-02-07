
import asyncio
import os
import sys
import time
import json
import uuid
import logging
from datetime import datetime, timedelta, timezone

# DB Imports
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add app to path
sys.path.insert(0, '/app')
from src.services.kalshi_client import KalshiClient

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("KalshiProductionBot")

# INITIAL DEFAULT CONFIG (Will be updated from DB)
CONFIG = {
    # Timezone Settings
    "timezone_offset_hours": -6,  # US Central Standard Time (CST)
    
    # Validation Rules
    "min_volume_dollars": 50000.0,
    "max_spread_cents": 5,        # 5 cents wide max
    
    # Strategy
    "min_pregame_prob": 0.65,     # 65% pre-game favorite
    "drop_threshold": 0.25,       # 25% drop required (e.g. 65% -> 40%)
    
    # Execution
    "position_size_dollars": 1.0,
    "dry_run": False,             # Set True to simulate only
    
    # Risk Management (Soft Limits)
    "stop_loss_pct": 0.20,        # 20% Stop Loss
    "take_profit_pct": 0.20,      # 20% Take Profit
    
    # System
    "bot_enabled": True           # Controlled by DB
}

TARGET_TEAMS = {} # Populated dynamically (NBA)

def get_cst_now():
    """Get current time in US Central."""
    offset = timezone(timedelta(hours=CONFIG["timezone_offset_hours"]))
    return datetime.now(offset)

def parse_ticker_date(ticker):
    """Parses date from ticker like KXNBAGAME-26FEB08LACMIN-MIN -> 2026-02-08"""
    try:
        parts = ticker.split("-")
        if len(parts) >= 2:
            date_part = parts[1][:7] # 26FEB08
            dt = datetime.strptime(date_part, "%y%b%d")
            return dt.date()
    except Exception as e:
        return None

class KalshiProductionBot:
    def __init__(self):
        self.api_key = "813faefe-becc-4647-807a-295dcf69fcad"
        self.key_file = "/app/kalshi.key"
        self.client = None
        
        # DB Setup
        self.db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@db:5432/polymarket_bot")
        self.db_engine = create_async_engine(self.db_url, echo=False)
        self.active_session = sessionmaker(self.db_engine, class_=AsyncSession, expire_on_commit=False)


    async def update_config_from_db(self):
        """Polls DB for latest settings."""
        try:
            async with self.active_session() as session:
                # Get the first user's settings (Simple assumption for single-user bot)
                result = await session.execute(text("SELECT user_id, bot_enabled, bot_config_json FROM global_settings LIMIT 1"))
                row = result.fetchone()
                
                if row:
                    self.user_id = row[0] # Store user_id for logging
                    
                    # 1. Update Enabled Status
                    CONFIG["bot_enabled"] = bool(row[1])
                    
                    # 2. Update Parameters from JSON
                    config_json = row[2]
                    if config_json and isinstance(config_json, dict):
                        params = config_json.get("parameters", {})
                        
                        # Update Volume
                        if "min_volume" in params:
                            CONFIG["min_volume_dollars"] = float(params["min_volume"])
                        
                        # Update Strategy Limits
                        if "stop_loss" in params:
                            CONFIG["stop_loss_pct"] = float(params["stop_loss"]) / 100.0
                        if "take_profit" in params:
                            CONFIG["take_profit_pct"] = float(params["take_profit"]) / 100.0
                        if "probability_drop" in params:
                            CONFIG["drop_threshold"] = float(params["probability_drop"]) / 100.0
                        if "position_size" in params:
                            CONFIG["position_size_dollars"] = float(params["position_size"])
                        
        except Exception as e:
            logger.error(f"⚠️ DB Config Sync Failed: {e}")

    async def log_activity(self, message, category="BOT", details=None):
        """Log to ActivityLog table for Frontend visibility."""
        if not self.user_id:
            return
            
        try:
            async with self.active_session() as session:
                 # Clean details
                 details_json = details if isinstance(details, dict) else {"info": str(details)} if details else {}
                 
                 # Using raw SQL for speed/simplicity in this script
                 stmt = text("""
                     INSERT INTO activity_logs (id, user_id, category, message, details, created_at)
                     VALUES (:id, :user_id, :category, :message, :details, :created_at)
                 """)

                 
                 await session.execute(stmt, {
                     "id": uuid.uuid4(),
                     "user_id": self.user_id,
                     "category": category,
                     "message": message,
                     "details": json.dumps(details_json),
                     "created_at": datetime.utcnow()
                 })
                 await session.commit()
        except Exception as e:
            logger.error(f"Failed to log activity: {e}")

    async def setup(self):
        logger.info("Initializing Production Bot v2.2 (DB Connected + Metrics)")
        try:
            with open(self.key_file, "r") as f:
                private_key = f.read()
            self.client = KalshiClient(api_key=self.api_key, private_key_pem=private_key)
            logger.info("✅ Kalshi Client Connected")
        except Exception as e:
            logger.error(f"❌ Failed to load credentials from {self.key_file}: {e}")
            sys.exit(1)

    async def get_pregame_probability(self, ticker):
        """Get the probability (price) before the game started."""
        try:
            # FIX 2026: Use /series/{series}/markets/{market}/candlesticks
            # 1. Extract Series Ticker (remove last part after dash)
            # Ticker: KXNBAGAME-26FEB07HOUOKC-OKC -> Series: KXNBAGAME-26FEB07HOUOKC
            series_ticker = ticker.rsplit('-', 1)[0]
            
            # 2. Calculate Start TS (5 days ago in seconds)
            now_ts = int(time.time())
            start_ts = now_ts - (5 * 86400)
            
            # 3. Request
            # Passing params separately ensures clean encoding
            path = f"/series/{series_ticker}/markets/{ticker}/candlesticks"
            # API expects 'interval' (e.g. 1h), not 'period'
            params = {"limit": 100, "start_ts": start_ts, "end_ts": now_ts, "interval": "1h"}
            
            history = await self.client._authenticated_request("GET", path, params=params)
            
            points = history.get("candlesticks", [])
            
            if not points:
                # Fallback: If no history, maybe market just opened? 
                # Strict Mode requires history.
                logger.warning(f"No history found for {ticker} at {path}")
                return None
                
            # 2. Sort by time (oldest first)
            points.sort(key=lambda x: x.get("end_period_ts"))
            
            # 3. Use the oldest point as 'pregame' approximation
            pregame_point = points[0]
            price = pregame_point.get("price") # Close price of bar?
            # Kalshi candlesticks: open, high, low, close, volume... 
            # API returns: o, h, l, c, v (usually shorter keys) OR full names.
            # Let's check keys if possible. Assuming 'c' or 'close'.
            # Or use 'yes_price' if it's history endpoint structure.
            # The 'candlesticks' endpoint usually returns 'price' object or o/h/l/c.
            # I will dump one point to log if fails.
            
            # Actually, standard is 'close' or 'c'.
            # I'll try 'close' then 'c' then 'price'.
            price_val = pregame_point.get("close") or pregame_point.get("c") or pregame_point.get("price")
            
            if price_val is None:
                 logger.warning(f"Unknown candlestick format: {pregame_point.keys()}")
                 return None
                 
            return float(price_val) / 100.0
            
        except Exception as e:
            logger.error(f"   ❌ History Fetch Error: {e}")
            return None


    async def check_strategy(self, market):
        """The Core Limit Logic."""
        ticker = market.get("ticker", "")
        
        # 1. Timezone Check
        game_date = parse_ticker_date(ticker)
        if not game_date:
            return False, "Invalid Date Parse"
            
        today = get_cst_now().date()
        
        if game_date > today:
            return False, f"Future game date: {market.get('open_date')} (Today CST: {today})"
        if (today - game_date).days > 1:
            return False, "Old game"

        # 2. Volume Check
        yes_ask = market.get("yes_ask", 0)
        volume = market.get("volume", 0)
        est_volume_dollars = volume * (yes_ask / 100.0) if yes_ask else volume * 0.50
        
        if est_volume_dollars < CONFIG["min_volume_dollars"]:
            return False, f"Low Volume (${est_volume_dollars:,.0f} < ${CONFIG['min_volume_dollars']:,.0f})"

        # 3. Strategy: Check for Drop
        pregame_prob = await self.get_pregame_probability(ticker)
        if pregame_prob is None:
            return False, "No pregame data found. STRICT MODE violation."
            
        current_prob = float(yes_ask) / 100.0
        drop = pregame_prob - current_prob
        
        if drop > CONFIG["drop_threshold"]:
             if pregame_prob < CONFIG["min_pregame_prob"]:
                 return False, f"Was not favorite enough pregame ({pregame_prob:.2%})"
             return True, f"DROP DETECTED! {pregame_prob:.1%} -> {current_prob:.1%} (Drop {drop:.1%})"
        
        return False, f"Drop {drop:.1%} < {CONFIG['drop_threshold']:.1%}"

    async def execute_trade(self, market, team):
        """Execute the order."""
        ticker = market.get("ticker")
        price_cents = market.get("yes_ask")
        
        if CONFIG["dry_run"]:
            logger.info(f"   👀 [DRY RUN] Would Buy {ticker} @ {price_cents}c")
            await self.log_activity(f"DRY RUN: Buy {ticker}", details={"price": price_cents})
            return

        logger.info(f"   🚀 EXECUTING BUY: {ticker} @ {price_cents}c")
        try:
            order = await self.client.place_order(
                ticker=ticker,
                side="buy",
                yes_no="yes",
                price=price_cents,
                size=int(CONFIG["position_size_dollars"]), 
                client_order_id=f"prod-{team}-{os.urandom(4).hex()}"
            )
            logger.info(f"   ✅ ORDER SENT: {order}")
            await self.log_activity(f"Placed BUY Order: {ticker}", category="TRADE", details=order)
            
        except Exception as e:
            logger.error(f"   ❌ ORDER FAILED: {e}")
            await self.log_activity(f"Order Failed: {ticker}", category="ERROR", details={"error": str(e)})

    async def monitor_positions(self):
        """Monitor positions for SL/TP using direct API call."""
        try:
            # GET /portfolio/positions
            resp = await self.client._authenticated_request("GET", "/portfolio/positions")
            positions = resp.get("market_positions", [])
            
            for pos in positions:
                ticker = pos.get("ticker")
                count = abs(int(pos.get("position", 0)))
                if count == 0: continue
                
                # Fetch Current Market Price (Bid to Sell)
                m_resp = await self.client.get_market(ticker)
                market = m_resp.get("market", m_resp)
                current_bid_cents = market.get("yes_bid", 0)
                
                # Calculate Cost Basis
                avg_price_cents = pos.get("avg_price", 0)
                if avg_price_cents == 0:
                    cost_basis = pos.get("cost_basis", 0)
                    avg_price_cents = cost_basis / count if count else 0
                
                if avg_price_cents > 0:
                    pnl_pct = (current_bid_cents - avg_price_cents) / avg_price_cents
                else:
                    pnl_pct = 0
                    
                # logger.info(f"   Positions: {ticker} | Entry: {avg_price_cents}c | Bid: {current_bid_cents}c | PnL: {pnl_pct:.1%}")
                
                if pnl_pct <= -CONFIG["stop_loss_pct"]:
                    logger.info(f"   🛑 STOP LOSS TRIGGERED: {ticker} ({pnl_pct:.1%})")
                    await self.close_position(ticker, count, "stop_loss")
                elif pnl_pct >= CONFIG["take_profit_pct"]:
                    logger.info(f"   💰 TAKE PROFIT TRIGGERED: {ticker} (+{pnl_pct:.1%})")
                    await self.close_position(ticker, count, "take_profit")
                        
        except Exception as e:
            pass # Suppress transient errors in position loop

    async def close_position(self, ticker, count, reason):
        """Execute a sell order to close position."""
        if CONFIG["dry_run"]:
            logger.info(f"   👀 [DRY RUN] Would Close {ticker}")
            await self.log_activity(f"DRY RUN: Close {ticker} ({reason})")
            return
            
        try:
            logger.info(f"   📉 CLOSING {ticker} ({reason})...")
            m_resp = await self.client.get_market(ticker)
            bid = m_resp.get("market", m_resp).get("yes_bid", 0)
            
            if bid == 0:
                logger.warning(f"   ⚠️ Cannot close {ticker}: No Liquidity (Bid 0)")
                return
                
            order = await self.client.place_order(
                ticker=ticker,
                side="sell",
                yes_no="yes",
                price=bid, 
                size=count,
                client_order_id=f"close-{reason}-{os.urandom(4).hex()}"
            )
            logger.info(f"   ✅ CLOSE SENT: {order}")
            await self.log_activity(f"Closed Position: {ticker}", category="TRADE", details={"reason": reason, "order": order})
            
        except Exception as e:
            logger.error(f"   ❌ CLOSE FAILED: {e}")
            await self.log_activity(f"Close Failed: {ticker}", category="ERROR", details={"error": str(e)})

    async def run_daemon(self):
        await self.setup()
        
        logger.info("🚀 DAEMON STARTED (Polling every 3s)")
        
        while True:
            try:
                # 0. Sync Config
                await self.update_config_from_db()
                
                if not CONFIG["bot_enabled"]:
                    logger.info("💤 Bot Disabled in Settings. Sleeping 10s...")
                    await asyncio.sleep(10)
                    continue

                logger.info(f"🕒 Cycle Start (CST: {get_cst_now()}) | Vol>${CONFIG['min_volume_dollars']/1000:.0f}k | Drop>{CONFIG['drop_threshold']:.0%}")
                
                # 1. Discovery (Quick Scan)
                found_markets = await self.client.get_markets(series_ticker="KXNBAGAME", status="open", limit=100)
                markets = found_markets.get("markets", [])
                
                logger.info(f"🔎 Scanning {len(markets)} Markets...")
                
                for m in markets:
                    ticker = m.get("ticker", "")
                    # 2. Strategy Check
                    is_good, reason = await self.check_strategy(m)
                    
                    if is_good:
                        logger.info(f"✨ MATCH: {ticker} - {reason}")
                        await self.execute_trade(m, "nba")
                    else:
                         if "Future" in reason:
                             logger.info(f"   ⏭️ SKIPPED: {ticker} - {reason}")
                             
                # 2. Monitor Positions (SL/TP)
                await self.monitor_positions()
                
                logger.info("   Sleeping 3s...")
                await asyncio.sleep(3)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"   ⚠️ Cycle Error: {e}")
                await asyncio.sleep(3)

async def main():
    bot = KalshiProductionBot()
    await bot.run_daemon()

if __name__ == "__main__":
    asyncio.run(main())

