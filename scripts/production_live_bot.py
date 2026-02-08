
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
from src.services.espn_service import ESPNService

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
    "drop_threshold": 0.10,       # 10% drop required (lowered for testing)
    
    # Execution
    "position_size_dollars": 1.0,  # Max USD to risk per trade
    "dry_run": False,             # Set True to simulate only
    
    # Risk Management (Soft Limits)
    "stop_loss_pct": 0.20,        # 20% Stop Loss
    "take_profit_pct": 0.20,      # 20% Take Profit
    
    # System
    "bot_enabled": True           # Controlled by DB
}

# ESPN uses slightly different abbreviations than Kalshi for some teams
# This maps ESPN abbrev -> Kalshi abbrev
ESPN_TO_KALSHI_ABBREV = {
    "SA": "SAS",    # San Antonio Spurs
    "GS": "GSW",    # Golden State Warriors (ESPN sometimes uses GS)
    "NO": "NOP",    # New Orleans Pelicans
    "NY": "NYK",    # New York Knicks
    "WSH": "WAS",   # Washington Wizards
    "PHO": "PHX",   # Phoenix Suns
    "BKN": "BKN",   # Brooklyn Nets (same)
    # Most teams use same abbreviation
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
        
        # ESPN Service for live game detection
        self.espn = ESPNService()
        self.live_team_abbreviations = set()  # Cache of currently live teams from ESPN
        self.open_positions = set()  # Cache of current Kalshi positions (tickers)
        self.active_order_tickers = set()  # Cache of current Kalshi open orders (tickers)
        
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
                            # User requested strict $1 limit - overriding DB value for safety
                            # CONFIG["position_size_dollars"] = float(params["position_size"])
                            CONFIG["position_size_dollars"] = 1.0
                        
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
                     INSERT INTO activity_logs (id, user_id, category, level, message, details, created_at)
                     VALUES (:id, :user_id, :category, :level, :message, :details, :created_at)
                 """)

                 
                 await session.execute(stmt, {
                     "id": uuid.uuid4(),
                     "user_id": self.user_id,
                     "category": category,
                     "level": "INFO",  # Default level
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

            # Log current balance for verification
            balance_data = await self.client.get_balance()
            available = balance_data.get("available_balance", 0)
            total = balance_data.get("balance", 0)
            logger.info(f"💰 ACCOUNT BALANCE: ${available:.2f} available / ${total:.2f} total")

            # Log open orders to see if funds are tied up
            orders_data = await self.client.get_open_orders()
            orders = orders_data.get("orders", [])
            if orders:
                logger.info(f"📋 OPEN ORDERS: {len(orders)} pending. Tickers: {[o.get('ticker') for o in orders]}")
            else:
                logger.info("📋 OPEN ORDERS: None. (Funds should be available if > $0)")

            logger.info(f"🔧 CONFIRMED CONFIG: Position Size ${CONFIG['position_size_dollars']} | Drop Threshold {CONFIG['drop_threshold']:.1%}")
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
            # API Error suggests 'period_interval' is the param name and wants INT (minutes?)
            # Error was: parsing "1h": invalid syntax
            params = {"limit": 100, "start_ts": start_ts, "end_ts": now_ts, "period_interval": 60}
            
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
            
            # Kalshi Series Candlesticks have nested structure: 
            # 'price': {'open': ..., 'close': ...}
            # 'yes_ask': {'open': ..., 'close': ...}
            
            price_val = None
            
            # Try 'price' (Last Trade) first
            price_obj = pregame_point.get("price")
            if isinstance(price_obj, dict):
                price_val = price_obj.get("close")
            
            # Fallback to 'yes_ask' (Offer) if price is missing
            if price_val is None:
                ask_obj = pregame_point.get("yes_ask")
                if isinstance(ask_obj, dict):
                    price_val = ask_obj.get("close")
            
            # Fallback to flat 'close'
            if price_val is None:
                price_val = pregame_point.get("close") or pregame_point.get("c")

            if price_val is None:
                 logger.warning(f"Unknown candlestick format keys: {pregame_point.keys()}")
                 return None
                 
            return float(price_val) / 100.0
            
        except Exception as e:
            logger.error(f"   ❌ History Fetch Error: {e}")
            return None


    async def check_strategy(self, market):
        """The Core Limit Logic."""
        ticker = market.get("ticker", "")
        
        # 0. Market Status Check - Reject finished/settled markets
        market_status = market.get("status", "")
        if market_status in ("finalized", "closed", "settled"):
            return False, f"Game Finished (status: {market_status})"
        
        # 0b. ESPN Live Game Check - Only trade on games ESPN confirms are IN-PROGRESS
        # Extract team abbreviation from ticker (e.g., KXNBAGAME-26FEB07DALSAS-DAL -> DAL)
        ticker_parts = ticker.split("-")
        if len(ticker_parts) >= 3:
            team_abbrev = ticker_parts[-1]  # e.g., "DAL" or "SAS"
            
            # Check if this team is in a live game according to ESPN
            if team_abbrev not in self.live_team_abbreviations:
                return False, f"ESPN: Team {team_abbrev} not in live game"
        
        # 1. Timezone Check
        game_date = parse_ticker_date(ticker)
        if not game_date:
            return False, "Invalid Date Parse"
            
        today = get_cst_now().date()
        
        if game_date > today:
            return False, f"Future game date: {market.get('open_date')} (Today CST: {today})"
        if (today - game_date).days > 1:
            return False, "Old game"
        
        # 1b. Check if game is already decided (has a result)
        result = market.get("result")
        if result is not None and result != "":
            return False, f"Game already decided (result: {result})"

        # 2. Volume Check
        # Dashboard shows "Notional Volume" = Contracts * $1 Face Value.
        # The API 'volume' field returns contracts traded. Each contract has a $1 max payout.
        # To approximate Dashboard: volume * 100 (treating API as cents, Dashboard as dollars).
        volume = market.get("volume", 0)
        dashboard_volume = float(volume) * 100  # Approximate Dashboard Value
        
        if dashboard_volume < CONFIG["min_volume_dollars"]:
            return False, f"Low Volume (${dashboard_volume:,.0f} < ${CONFIG['min_volume_dollars']:,.0f})"

        # 3. Strategy: Check for Drop
        pregame_prob = await self.get_pregame_probability(ticker)
        if pregame_prob is None:
            return False, "No pregame data found. STRICT MODE violation."
            
        current_prob = float(market.get("yes_ask", 0)) / 100.0
        
        # 3b. Price Sanity Check - If prob is 95%+ or 5%- the outcome is decided (game over)
        if current_prob >= 0.95:
            return False, f"Game already decided (current price {current_prob:.0%})"
        if current_prob <= 0.05:
            return False, f"Game already decided (current price {current_prob:.0%})"
        
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

        # Calculate size based on target dollar amount
        # position_size_dollars is total USD to spend
        # price_cents is price per contract
        # min 1 contract
        contracts_to_buy = max(1, int((CONFIG["position_size_dollars"] * 100) / price_cents))
        
        logger.info(f"   🚀 EXECUTING BUY: {ticker} @ {price_cents}c | Size: ${CONFIG['position_size_dollars']} ({contracts_to_buy} contracts)")
        try:
            order = await self.client.place_order(
                ticker=ticker,
                side="buy",
                yes_no="yes",
                price=price_cents,
                size=contracts_to_buy, 
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
            positions = resp.get("market_positions") or resp.get("positions") or []
            if isinstance(resp, list): positions = resp # Handle list direct return
            
            # Update cache of open positions
            self.open_positions = set()
            self.active_order_tickers = set()
            
            for pos in positions:
                ticker = pos.get("ticker")
                count = abs(int(pos.get("position", 0)))
                if count == 0: continue
                
                self.open_positions.add(ticker)
                
                # Fetch Current Market Price (Bid to Sell)
                m_resp = await self.client.get_market(ticker)
                market = m_resp.get("market", m_resp)
                current_bid_cents = market.get("yes_bid", 0)
                
                # Calculate Cost Basis - Kalshi returns total_cost_shares, divide by count for avg
                total_cost_shares = pos.get("total_cost_shares", 0)
                if total_cost_shares and count:
                    avg_price_cents = total_cost_shares / count
                else:
                    avg_price_cents = pos.get("avg_price", 0) or pos.get("average_price", 0) or 0
                
                if avg_price_cents > 0:
                    pnl_pct = (current_bid_cents - avg_price_cents) / avg_price_cents
                else:
                    pnl_pct = 0
                    
                logger.info(f"   📊 {ticker} | Entry: {avg_price_cents}c | Bid: {current_bid_cents}c | PnL: {pnl_pct:+.1%}")
                
                if pnl_pct <= -CONFIG["stop_loss_pct"]:
                    logger.info(f"   🛑 STOP LOSS TRIGGERED: {ticker} ({pnl_pct:.1%})")
                    await self.close_position(ticker, count, "stop_loss")
                elif pnl_pct >= CONFIG["take_profit_pct"]:
                    logger.info(f"   💰 TAKE PROFIT TRIGGERED: {ticker} (+{pnl_pct:.1%})")
                    await self.close_position(ticker, count, "take_profit")

            # 2. Fetch Open Orders for entry suppression
            try:
                order_data = await self.client.get_open_orders()
                orders = order_data.get("orders", [])
                for o in orders:
                    status = o.get("status")
                    if status in ["resting", "open", "pending"]:
                        self.active_order_tickers.add(o.get("ticker"))
            except Exception as e:
                logger.error(f"Error fetching open orders: {e}")
                        
        except Exception as e:
            logger.error(f"Error in monitor_positions: {e}")
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
                
                # 0b. Fetch live games from ESPN to determine which games are actually in-progress
                try:
                    espn_live_games = await self.espn.get_live_games("nba")
                    self.live_team_abbreviations = set()
                    for game in espn_live_games:
                        state = self.espn.parse_game_state(game, "nba")
                        if state["home_team"]:
                            espn_abbrev = state["home_team"]["abbreviation"]
                            # Translate ESPN abbreviation to Kalshi format
                            kalshi_abbrev = ESPN_TO_KALSHI_ABBREV.get(espn_abbrev, espn_abbrev)
                            self.live_team_abbreviations.add(kalshi_abbrev)
                        if state["away_team"]:
                            espn_abbrev = state["away_team"]["abbreviation"]
                            kalshi_abbrev = ESPN_TO_KALSHI_ABBREV.get(espn_abbrev, espn_abbrev)
                            self.live_team_abbreviations.add(kalshi_abbrev)
                    logger.info(f"📺 ESPN: {len(espn_live_games)} live games, Teams: {self.live_team_abbreviations}")
                except Exception as e:
                    logger.error(f"⚠️ ESPN fetch failed: {e}. Using empty live list.")
                    self.live_team_abbreviations = set()
                
                # 1. Discovery (Quick Scan) - Note: Kalshi doesn't support status=active, use open
                found_markets = await self.client.get_markets(series_ticker="KXNBAGAME", status="open", limit=100)
                markets = found_markets.get("markets", [])
                
                logger.info(f"🔎 Scanning {len(markets)} Markets...")
                
                for m in markets:
                    ticker = m.get("ticker", "")
                    # 2. Strategy Check
                    is_good, reason = await self.check_strategy(m)
                    
                    if is_good:
                        if ticker in self.open_positions:
                            # Already hold it, skip
                            continue
                            
                        if ticker in self.active_order_tickers:
                            # Already have a pending order, skip
                            continue
                            
                        logger.info(f"✨ MATCH: {ticker} - {reason}")
                        await self.execute_trade(m, "nba")
                    else:
                         # Verbose logging to reassure user
                         logger.info(f"   Using {ticker}: {reason}")
                             
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

