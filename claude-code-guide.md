# Kalshi Sports Bot - Claude Code Implementation Guide

## Quick Reference

**Client:** Jay Bane  
**Project:** Automated Kalshi sports betting bot  
**Language:** Python 3.11+ with FastAPI  
**Database:** PostgreSQL (prod) / SQLite (dev)  
**Hosting:** Google Cloud Run  

---

## Before You Start

### Critical Architecture Discovery

**Kalshi does NOT provide game state data (quarter, time remaining, score).**

You need TWO data sources:
- **Kalshi API**: Market prices, order placement, positions, balance
- **ESPN API**: Game state, quarter/period, time remaining, scores

This is standard for sports trading bots. ESPN data arrives 5-10 seconds before TV.

### Research Complete

The following has been researched and documented:

1. **Kalshi RSA Auth**: RSA-PSS with SHA256, message = `{timestamp}{method}{path}`
2. **Kalshi Ticker Format**: Hierarchical like `KXNBA-MIA-CHI` or `NFLPLOFFS_SEA_SF`
3. **Game State**: Must use ESPN unofficial API, not Kalshi
4. **ESPN Endpoints**: Public, no auth required, poll every 5-10 seconds

### 2. Set Up Development Environment

```bash
# Create project directory
mkdir kalshi-sports-bot
cd kalshi-sports-bot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# OR: venv\Scripts\activate  # Windows

# Initialize git
git init
```

---

## Claude Code Prompts (Use In Order)

### PROMPT 1: Project Foundation

```
I'm building a production Kalshi sports trading bot for a client. 

Tech stack:
- Python 3.11+ with FastAPI
- SQLAlchemy 2.0 (async) with PostgreSQL
- Pydantic v2 for validation
- JWT authentication with python-jose
- bcrypt for password hashing

Create the initial project structure:

kalshi-sports-bot/
|-- src/
|   |-- __init__.py
|   |-- main.py              # FastAPI app
|   |-- config.py            # Pydantic settings
|   |-- api/
|   |   |-- __init__.py
|   |   |-- deps.py          # Dependencies (get_db, get_current_user)
|   |   |-- routes/
|   |       |-- __init__.py
|   |-- core/
|   |   |-- __init__.py
|   |   |-- security.py      # JWT, password hashing
|   |-- models/
|   |   |-- __init__.py
|   |-- schemas/
|   |   |-- __init__.py
|   |-- services/
|   |   |-- __init__.py
|   |   |-- kalshi_client.py     # Kalshi API (prices, orders, RSA auth)
|   |   |-- espn_service.py      # ESPN API (game state, scores)
|   |   |-- market_matcher.py    # Match ESPN games to Kalshi markets
|   |-- db/
|   |   |-- __init__.py
|   |   |-- database.py
|   |-- templates/
|   |-- static/
|       |-- css/
|       |-- js/
|-- tests/
|-- alembic/
|-- requirements.txt
|-- .env.example
|-- Dockerfile
|-- README.md

Include requirements.txt with:
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
sqlalchemy[asyncio]>=2.0.0
asyncpg>=0.29.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
cryptography>=42.0.0
httpx>=0.26.0
python-multipart>=0.0.6
jinja2>=3.1.0
alembic>=1.13.0
aiosqlite>=0.19.0

Create src/config.py with pydantic-settings for:
- DATABASE_URL
- SECRET_KEY
- JWT settings (algorithm, expiry)
- Debug mode

Create basic src/main.py with:
- FastAPI app with title "Kalshi Sports Bot"
- CORS middleware (allow all origins for now)
- Static files mount
- Templates setup with Jinja2
- Health check endpoint at /health

No emojis anywhere in the code or comments.
```

### PROMPT 2: Database Models

```
Create the database models for the Kalshi sports bot.

In src/db/database.py:
- Async SQLAlchemy engine setup
- AsyncSession factory
- get_db dependency

Create these models in src/models/:

1. user.py - User model:
   - id: UUID primary key
   - email: unique string
   - password_hash: string
   - is_active: boolean
   - onboarding_completed: boolean
   - onboarding_step: integer (0-9)
   - created_at, updated_at: timestamps

2. kalshi_account.py - Kalshi credentials:
   - id: UUID primary key
   - user_id: foreign key to users (unique)
   - api_key_id_encrypted: string
   - private_key_encrypted: text
   - environment: string ('demo' or 'prod')
   - is_connected: boolean
   - last_verified_at: timestamp
   - account_balance: decimal

3. sport_config.py - Sport settings:
   - id: UUID primary key
   - user_id: foreign key
   - sport: string (nba, nfl, mlb, nhl, soccer)
   - enabled: boolean
   - min_pregame_odds: decimal
   - entry_threshold_drop: decimal
   - entry_threshold_absolute: decimal
   - max_entry_segment: string
   - min_time_remaining_seconds: integer
   - take_profit: decimal
   - stop_loss: decimal
   - exit_before_segment: string
   - position_size_dollars: decimal
   - max_positions_per_game: integer
   - max_total_positions: integer
   - Unique constraint on (user_id, sport)

4. global_settings.py:
   - id: UUID primary key
   - user_id: foreign key (unique)
   - bot_enabled: boolean
   - dry_run_mode: boolean (default True)
   - max_daily_loss: decimal
   - max_portfolio_exposure: decimal
   - discord_webhook_url: string
   - discord_alerts_enabled: boolean

5. tracked_game.py:
   - id: UUID primary key
   - user_id: foreign key
   - market_id: string
   - sport: string
   - event_title: string
   - team_a, team_b: strings
   - start_time: timestamp
   - current_segment: string
   - time_remaining_seconds: integer
   - is_live, is_finished: booleans
   - pregame_odds_a, pregame_odds_b: decimals
   - current_odds_a, current_odds_b: decimals
   - pregame_captured_at: timestamp

6. position.py:
   - id: UUID primary key
   - user_id: foreign key
   - game_id: foreign key to tracked_games
   - market_id: string
   - side: string (yes/no)
   - team: string
   - entry_price, entry_quantity, entry_cost: numbers
   - exit_price, exit_quantity, exit_proceeds: numbers (nullable)
   - exit_reason: string (nullable)
   - realized_pnl: decimal (nullable)
   - status: string (open/closed/pending)
   - opened_at, closed_at: timestamps

7. trade.py:
   - id: UUID primary key
   - user_id: foreign key
   - position_id: foreign key
   - kalshi_order_id: string
   - action: string (buy/sell)
   - side: string
   - price, quantity, total, fees: numbers
   - is_dry_run: boolean
   - executed_at: timestamp

8. activity_log.py:
   - id: UUID primary key
   - user_id: foreign key
   - level: string (debug/info/warning/error)
   - category: string
   - message: text
   - details: JSON
   - created_at: timestamp

Use SQLAlchemy 2.0 patterns with proper type hints.
Include an __init__.py in models/ that imports all models.
Set up Alembic for migrations.
```

### PROMPT 3: Authentication System

```
Implement the authentication system.

1. src/core/security.py:
   - verify_password(plain, hashed) using bcrypt
   - get_password_hash(password) using bcrypt cost=12
   - create_access_token(user_id, email) - 15 min expiry
   - create_refresh_token(user_id) - 7 day expiry
   - verify_token(token) - returns payload or raises

2. src/core/encryption.py:
   - derive_key(secret) - SHA256 based key derivation
   - encrypt_credential(plaintext, secret) - Fernet encryption
   - decrypt_credential(ciphertext, secret) - Fernet decryption

3. src/schemas/auth.py:
   - UserCreate: email, password, confirm_password
   - UserLogin: email, password
   - UserResponse: id, email, created_at, onboarding_completed
   - TokenResponse: access_token, refresh_token, token_type, expires_in, user
   - RefreshRequest: refresh_token

4. src/db/crud/user.py:
   - get_user_by_id(db, user_id)
   - get_user_by_email(db, email)
   - create_user(db, user_data)
   - update_user(db, user_id, data)

5. src/services/auth_service.py:
   - register_user(db, user_data)
   - authenticate_user(db, email, password)
   - refresh_tokens(refresh_token)

6. src/api/deps.py:
   - get_db() - async session dependency
   - get_current_user(token) - verify JWT, return user

7. src/api/routes/auth.py:
   - POST /auth/register
   - POST /auth/login
   - POST /auth/refresh
   - POST /auth/logout
   - GET /auth/me

Include proper error handling with HTTPException.
Use Pydantic validators for password strength.
No emojis in any messages or comments.
```

### PROMPT 4: Login and Registration UI

```
Create the authentication UI pages.

1. src/templates/base.html:
   - Clean HTML5 template
   - Tailwind CSS via CDN
   - No emojis anywhere
   - Professional, minimal design
   - Meta viewport for mobile

2. src/templates/auth/login.html:
   - Email and password fields
   - Login button
   - Link to register
   - Error message display area
   - Clean, centered card design

3. src/templates/auth/register.html:
   - Email field
   - Password field with requirements shown
   - Confirm password field
   - Register button
   - Link to login
   - Error message display

4. src/static/css/main.css:
   - Minimal custom styles (Tailwind handles most)
   - Form styling
   - Error state styling

5. src/static/js/auth.js:
   - Form submission handlers
   - Fetch API for login/register
   - Token storage in localStorage
   - Redirect on success
   - Error display

6. Add page routes in src/api/routes/pages.py:
   - GET / - redirect to login or dashboard
   - GET /login - login page
   - GET /register - register page

Design should be:
- Professional and clean
- No decorative elements
- Clear typography
- Works on mobile
- No emojis or playful icons
```

### PROMPT 5: Onboarding Flow

```
Build the complete onboarding system.

1. src/schemas/onboarding.py:
   - OnboardingStep: step_number, title, description, is_completed, requires_action
   - OnboardingStatus: current_step, total_steps (9), completed_steps, steps list
   - KalshiConnectRequest: api_key_id, private_key, environment
   - KalshiTestResponse: success, balance, error_message

2. src/api/routes/onboarding.py:
   - GET /api/v1/onboarding/status
   - POST /api/v1/onboarding/step/{n}/complete
   - POST /api/v1/onboarding/kalshi/connect
   - POST /api/v1/onboarding/kalshi/test
   - POST /api/v1/onboarding/skip (marks complete, not recommended)

3. Create templates in src/templates/onboarding/:

   step1_welcome.html:
   - Welcome message
   - Brief description of the bot
   - What to expect from setup
   - "Get Started" button

   step2_how_it_works.html:
   - Explanation of baseline tracking
   - How thresholds work
   - Risk management overview
   - Diagram or clear text explanation
   - "Continue" button

   step3_connect_kalshi.html:
   - Instructions to get API keys from Kalshi
   - Link to Kalshi API settings
   - Input field for API Key ID
   - Textarea for private key (or file upload)
   - Environment selector (Demo/Live)
   - "Connect Account" button
   - Status indicator

   step4_environment.html:
   - Explain Demo vs Live
   - Strong recommendation to start with Demo
   - Selection buttons
   - "Continue" button

   step5_first_sport.html:
   - Sport selection (NBA, NFL, MLB, NHL, Soccer)
   - Brief description of each
   - Default parameter values shown
   - "Configure" button

   step6_risk_settings.html:
   - Daily loss limit input
   - Max portfolio exposure input
   - Position size default
   - Explanation of each setting
   - "Save" button

   step7_discord.html:
   - Instructions to create Discord webhook
   - Input field for webhook URL
   - "Test Webhook" button
   - Skip option (alerts not required)
   - "Continue" button

   step8_review.html:
   - Summary of all settings
   - Kalshi: connected/environment
   - Sports: which enabled
   - Risk: limits set
   - Alerts: enabled/disabled
   - "Launch Bot" button

   step9_tour.html:
   - Brief dashboard overview
   - Key features highlighted
   - How to get help
   - "Go to Dashboard" button

4. src/static/js/onboarding.js:
   - Step navigation
   - Form submissions
   - Progress tracking
   - Validation before next step

Each template should:
- Extend a common onboarding layout
- Show progress indicator (Step X of 9)
- Have back/next navigation
- Be mobile responsive
- No emojis or decorative icons
```

### PROMPT 6: Kalshi API Client (RSA-PSS Authentication)

```
Implement the Kalshi API client with RSA-PSS authentication.

CRITICAL: Kalshi uses RSA-PSS with SHA256 for request signing.
Message format: {timestamp}{method}{path} (concatenated, no separators)
Path must NOT include query parameters when signing.

Create src/services/kalshi_client.py:

import base64
import httpx
from datetime import datetime
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import padding
from typing import Optional

class KalshiClient:
    """Async client for Kalshi API v2 with RSA-PSS authentication."""
    
    DEMO_URL = "https://demo-api.kalshi.co"
    PROD_URL = "https://api.kalshi.com"
    
    def __init__(
        self,
        api_key_id: str,
        private_key_pem: str,
        environment: str = "demo"
    ):
        self.api_key_id = api_key_id
        self.private_key = self._load_private_key(private_key_pem)
        self.base_url = self.DEMO_URL if environment == "demo" else self.PROD_URL
        self.client = httpx.AsyncClient(timeout=30.0)
    
    def _load_private_key(self, pem_string: str):
        """Load RSA private key from PEM string."""
        return serialization.load_pem_private_key(
            pem_string.encode('utf-8'),
            password=None,
            backend=default_backend()
        )
    
    def _create_signature(self, timestamp: str, method: str, path: str) -> str:
        """
        Create RSA-PSS signature.
        
        CRITICAL: 
        - Strip query params from path before signing
        - Message = timestamp + method + path (concatenated)
        - Use RSA-PSS with SHA256
        """
        path_clean = path.split('?')[0]
        message = f"{timestamp}{method}{path_clean}".encode('utf-8')
        
        signature = self.private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH
            ),
            hashes.SHA256()
        )
        
        return base64.b64encode(signature).decode('utf-8')
    
    async def _request(
        self,
        method: str,
        path: str,
        params: dict = None,
        data: dict = None
    ) -> dict:
        """Make authenticated request."""
        timestamp = str(int(datetime.now().timestamp() * 1000))
        signature = self._create_signature(timestamp, method.upper(), path)
        
        headers = {
            "KALSHI-ACCESS-KEY": self.api_key_id,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "Content-Type": "application/json"
        }
        
        url = f"{self.base_url}{path}"
        
        if method.upper() == "GET":
            response = await self.client.get(url, headers=headers, params=params)
        elif method.upper() == "POST":
            response = await self.client.post(url, headers=headers, json=data)
        elif method.upper() == "DELETE":
            response = await self.client.delete(url, headers=headers)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        response.raise_for_status()
        return response.json()
    
    # Portfolio endpoints
    async def get_balance(self) -> dict:
        return await self._request("GET", "/trade-api/v2/portfolio/balance")
    
    async def get_positions(self) -> list:
        result = await self._request("GET", "/trade-api/v2/portfolio/positions")
        return result.get("market_positions", [])
    
    # Market endpoints
    async def get_markets(self, status: str = None, event_ticker: str = None) -> list:
        params = {}
        if status:
            params["status"] = status
        if event_ticker:
            params["event_ticker"] = event_ticker
        result = await self._request("GET", "/trade-api/v2/markets", params=params)
        return result.get("markets", [])
    
    async def get_sports_markets(self, sport: str = None) -> list:
        """Get sports markets. Filter by KXNBA, KXNFL, etc. prefixes."""
        all_markets = await self.get_markets(status="open")
        
        sport_prefixes = {
            "nba": ["KXNBA", "NBA"],
            "nfl": ["KXNFL", "NFL", "NFLPLOFFS"],
            "mlb": ["KXMLB", "MLB"],
            "nhl": ["KXNHL", "NHL"],
        }
        
        if sport and sport.lower() in sport_prefixes:
            prefixes = sport_prefixes[sport.lower()]
            return [
                m for m in all_markets
                if any(m.get("ticker", "").upper().startswith(p) for p in prefixes)
            ]
        
        all_prefixes = [p for prefixes in sport_prefixes.values() for p in prefixes]
        return [
            m for m in all_markets
            if any(m.get("ticker", "").upper().startswith(p) for p in all_prefixes)
        ]
    
    # Order endpoints
    async def place_order(
        self,
        ticker: str,
        side: str,      # "yes" or "no"
        action: str,    # "buy" or "sell"
        count: int,
        type: str = "limit",
        price: int = None
    ) -> dict:
        data = {
            "ticker": ticker,
            "side": side.lower(),
            "action": action.lower(),
            "count": count,
            "type": type,
        }
        if type == "limit" and price:
            data["yes_price" if side.lower() == "yes" else "no_price"] = price
        
        return await self._request("POST", "/trade-api/v2/portfolio/orders", data=data)
    
    async def cancel_order(self, order_id: str) -> bool:
        try:
            await self._request("DELETE", f"/trade-api/v2/portfolio/orders/{order_id}")
            return True
        except Exception:
            return False
    
    async def test_connection(self) -> tuple[bool, str, float]:
        try:
            balance_data = await self.get_balance()
            balance_dollars = balance_data.get("balance", 0) / 100
            return True, "Connection successful", balance_dollars
        except httpx.HTTPStatusError as e:
            return False, f"HTTP error: {e.response.status_code}", 0.0
        except Exception as e:
            return False, f"Connection failed: {str(e)}", 0.0
    
    async def close(self):
        await self.client.aclose()

Include proper error handling and logging.
No emojis in any code or comments.
```

### PROMPT 6B: ESPN Service (Game State Data)

```
CRITICAL: Kalshi does NOT provide game state data (quarter, time, score).
Must use ESPN's unofficial API for this information.

Create src/services/espn_service.py:

import httpx
from typing import Optional

class ESPNService:
    """Fetch game state from ESPN's unofficial API."""
    
    BASE_URL = "https://site.web.api.espn.com/apis/site/v2/sports"
    
    SPORT_ENDPOINTS = {
        "nba": "basketball/nba",
        "nfl": "football/nfl", 
        "mlb": "baseball/mlb",
        "nhl": "hockey/nhl",
    }
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=10.0)
    
    async def get_scoreboard(self, sport: str) -> list[dict]:
        """Get all games for a sport."""
        if sport not in self.SPORT_ENDPOINTS:
            raise ValueError(f"Unsupported sport: {sport}")
        
        endpoint = self.SPORT_ENDPOINTS[sport]
        url = f"{self.BASE_URL}/{endpoint}/scoreboard"
        
        response = await self.client.get(url)
        response.raise_for_status()
        
        return response.json().get("events", [])
    
    async def get_live_games(self, sport: str) -> list[dict]:
        """Get only games currently in progress."""
        games = await self.get_scoreboard(sport)
        return [
            game for game in games
            if game.get("status", {}).get("type", {}).get("state") == "in"
        ]
    
    def parse_game_state(self, game: dict) -> dict:
        """
        Extract game state from ESPN response.
        
        Returns dict with:
        - event_id, name
        - home_team, away_team, home_abbrev, away_abbrev
        - home_score, away_score
        - period (quarter/inning number)
        - time_remaining_seconds, time_display
        - is_live, is_finished
        """
        status = game.get("status", {})
        status_type = status.get("type", {})
        competition = game.get("competitions", [{}])[0]
        competitors = competition.get("competitors", [])
        
        home = next((c for c in competitors if c.get("homeAway") == "home"), {})
        away = next((c for c in competitors if c.get("homeAway") == "away"), {})
        
        clock_seconds = status.get("clock", 0)
        if isinstance(clock_seconds, float):
            clock_seconds = int(clock_seconds)
        
        return {
            "event_id": game.get("id"),
            "name": game.get("name"),
            "home_team": home.get("team", {}).get("displayName", ""),
            "away_team": away.get("team", {}).get("displayName", ""),
            "home_abbrev": home.get("team", {}).get("abbreviation", ""),
            "away_abbrev": away.get("team", {}).get("abbreviation", ""),
            "home_score": int(home.get("score", 0) or 0),
            "away_score": int(away.get("score", 0) or 0),
            "period": status.get("period", 0),
            "time_remaining_seconds": clock_seconds,
            "time_display": status.get("displayClock", "0:00"),
            "is_live": status_type.get("state") == "in",
            "is_finished": status_type.get("completed", False),
        }
    
    async def close(self):
        await self.client.aclose()

Also create src/services/market_matcher.py:

class MarketMatcher:
    """Match ESPN games to Kalshi markets by team abbreviations."""
    
    def match_games(
        self,
        kalshi_markets: list[dict],
        espn_games: list[dict],
        espn_service: ESPNService
    ) -> list[dict]:
        """
        Match Kalshi markets to ESPN games.
        
        Returns list of merged game data with:
        - Kalshi: ticker, yes_bid, yes_ask, volume
        - ESPN: period, time_remaining, score, is_live
        """
        matched = []
        
        for espn_game in espn_games:
            espn_data = espn_service.parse_game_state(espn_game)
            
            # Find matching Kalshi market by team abbreviations
            kalshi_market = self._find_match(
                espn_data["home_abbrev"],
                espn_data["away_abbrev"],
                kalshi_markets
            )
            
            if kalshi_market:
                matched.append({
                    "kalshi_ticker": kalshi_market["ticker"],
                    "kalshi_yes_bid": kalshi_market.get("yes_bid", 0),
                    "kalshi_yes_ask": kalshi_market.get("yes_ask", 0),
                    "espn_event_id": espn_data["event_id"],
                    **espn_data
                })
        
        return matched
    
    def _find_match(
        self,
        home_abbrev: str,
        away_abbrev: str,
        kalshi_markets: list[dict]
    ) -> Optional[dict]:
        for market in kalshi_markets:
            ticker = market.get("ticker", "").upper()
            title = market.get("title", "").upper()
            
            if home_abbrev.upper() in ticker or home_abbrev.upper() in title:
                if away_abbrev.upper() in ticker or away_abbrev.upper() in title:
                    return market
        
        return None

No emojis. Proper type hints. Handle all errors gracefully.
```
```

### PROMPT 7: Trading Engine Core (Dual-Source Architecture)

```
Build the core trading engine using BOTH Kalshi (prices) and ESPN (game state).

ARCHITECTURE:
- Kalshi API: Market prices, order execution, positions
- ESPN API: Game state (quarter, time remaining, score)
- MarketMatcher: Links ESPN games to Kalshi markets

Create src/services/trading_engine.py:

import asyncio
from datetime import datetime
from typing import Optional

class TradingEngine:
    """
    Main trading loop using dual data sources.
    
    Flow:
    1. Fetch Kalshi sports markets (prices)
    2. Fetch ESPN live games (game state)
    3. Match ESPN games to Kalshi markets
    4. For each matched game:
       - If pregame: capture baseline from Kalshi
       - If live: check entry/exit using ESPN time + Kalshi price
       - If finished: close positions
    """
    
    def __init__(
        self,
        user_id: str,
        kalshi: KalshiClient,
        espn: ESPNService,
        matcher: MarketMatcher,
        db_session,
        alert_service: AlertService
    ):
        self.user_id = user_id
        self.kalshi = kalshi
        self.espn = espn
        self.matcher = matcher
        self.db = db_session
        self.alerts = alert_service
        self.is_running = False
        self.is_paused = False
    
    async def start(self):
        """Start the trading loop."""
        self.is_running = True
        while self.is_running:
            try:
                if not self.is_paused:
                    await self._trading_cycle()
            except Exception as e:
                await self._log_error(f"Trading cycle error: {str(e)}")
            await asyncio.sleep(5)  # Poll every 5 seconds
    
    async def stop(self):
        self.is_running = False
    
    async def pause(self):
        self.is_paused = True
    
    async def resume(self):
        self.is_paused = False
    
    async def _trading_cycle(self):
        """Execute one trading cycle."""
        # 1. Get settings
        settings = await self._get_settings()
        if not settings.bot_enabled:
            return
        
        # 2. Check daily loss limit
        daily_pnl = await self._get_daily_pnl()
        if daily_pnl <= -settings.max_daily_loss:
            await self._log("Daily loss limit reached. Bot paused.")
            await self.pause()
            return
        
        # 3. Get enabled sports
        sport_configs = await self._get_enabled_sports()
        
        for config in sport_configs:
            sport = config.sport
            
            # 4. Fetch from BOTH sources
            kalshi_markets = await self.kalshi.get_sports_markets(sport)
            espn_games = await self.espn.get_scoreboard(sport)
            
            # 5. Match ESPN to Kalshi
            matched_games = self.matcher.match_games(
                kalshi_markets, 
                espn_games,
                self.espn
            )
            
            # 6. Process each matched game
            for game in matched_games:
                await self._process_game(game, config, settings)
        
        # 7. Check exits for all open positions
        await self._check_all_exits()
    
    async def _process_game(self, game: dict, config, settings):
        """Process a single matched game."""
        
        # Game state from ESPN
        is_live = game["is_live"]
        is_finished = game["is_finished"]
        period = game["period"]
        time_remaining = game["time_remaining_seconds"]
        
        # Prices from Kalshi
        kalshi_ticker = game["kalshi_ticker"]
        current_price = game["kalshi_yes_bid"]
        
        if not is_live and not is_finished:
            # PREGAME: Capture baseline
            await self._capture_baseline(game, config)
        
        elif is_live:
            # LIVE: Check entry conditions
            await self._check_entry(game, config, settings)
        
        elif is_finished:
            # FINISHED: Close any positions
            await self._close_positions_for_game(game)
    
    async def _capture_baseline(self, game: dict, config):
        """Store pregame odds as baseline."""
        # Only capture within 15 min of start
        # Store in tracked_games table
        pass
    
    async def _check_entry(self, game: dict, config, settings):
        """Check if should enter position."""
        # Get baseline from database
        baseline = await self._get_baseline(game["kalshi_ticker"])
        if not baseline:
            return
        
        current_price = game["kalshi_yes_bid"]
        drop = baseline - current_price
        
        # Check segment (from ESPN)
        segment = self._get_segment(game["period"], config.sport)
        if self._is_past_entry_window(segment, config.max_entry_segment):
            return
        
        # Check time remaining (from ESPN)
        if game["time_remaining_seconds"] < config.min_time_remaining_seconds:
            return
        
        # Check threshold
        if drop >= config.entry_threshold_drop:
            await self._execute_entry(game, config, settings, f"Drop: {drop} points")
        elif current_price <= config.entry_threshold_absolute:
            await self._execute_entry(game, config, settings, f"Absolute: {current_price}c")
    
    async def _check_all_exits(self):
        """Check exit conditions for all open positions."""
        positions = await self._get_open_positions()
        
        for position in positions:
            # Get current game data (need to refetch)
            game = await self._get_game_data(position.market_id)
            if not game:
                continue
            
            config = await self._get_sport_config(game["sport"])
            current_price = game["kalshi_yes_bid"]
            
            # Calculate P&L
            pnl_points = current_price - position.entry_price
            
            # Take profit
            if pnl_points >= config.take_profit:
                await self._execute_exit(position, game, "take_profit")
                continue
            
            # Stop loss
            if pnl_points <= -config.stop_loss:
                await self._execute_exit(position, game, "stop_loss")
                continue
            
            # Time exit (from ESPN data)
            segment = self._get_segment(game["period"], config.sport)
            if self._should_time_exit(segment, config.exit_before_segment):
                await self._execute_exit(position, game, "time_exit")
                continue
            
            # Game finished
            if game["is_finished"]:
                await self._execute_exit(position, game, "game_finished")
    
    def _get_segment(self, period: int, sport: str) -> str:
        """Convert ESPN period to segment string."""
        if sport in ["nba", "nfl"]:
            segments = {1: "1st_quarter", 2: "2nd_quarter", 
                       3: "3rd_quarter", 4: "4th_quarter"}
            return segments.get(period, "overtime")
        elif sport == "nhl":
            segments = {1: "1st_period", 2: "2nd_period", 3: "3rd_period"}
            return segments.get(period, "overtime")
        elif sport == "mlb":
            return f"inning_{period}"
        return f"period_{period}"
    
    async def _execute_entry(self, game, config, settings, reason):
        """Place buy order."""
        # Calculate quantity
        price = game["kalshi_yes_ask"]
        quantity = int((config.position_size_dollars * 100) / price)
        
        if settings.dry_run_mode:
            order_id = f"DRY_{datetime.now().timestamp()}"
            await self._log(f"[DRY RUN] Buy {quantity} @ {price}c - {reason}")
        else:
            order = await self.kalshi.place_order(
                ticker=game["kalshi_ticker"],
                side="yes",
                action="buy",
                count=quantity,
                price=price
            )
            order_id = order.get("order", {}).get("order_id")
        
        # Create position record
        position = await self._create_position(game, price, quantity, order_id)
        
        # Send alert
        await self.alerts.send_entry_alert(...)
    
    async def _execute_exit(self, position, game, reason):
        """Place sell order."""
        # Similar to entry but for selling
        pass

Include helper methods for database operations.
Comprehensive logging (no emojis).
Type hints throughout.
```

### PROMPT 8: Dashboard API and UI

```
Create the dashboard backend and frontend.

1. src/api/routes/dashboard.py:
   - GET /api/v1/status - Bot status, P&L summary
   - GET /api/v1/positions - Open positions with live P&L
   - GET /api/v1/positions/history - Closed positions
   - GET /api/v1/games/tracked - All tracked games
   - GET /api/v1/games/live - Live games only

2. src/api/routes/settings.py:
   - GET /api/v1/settings - Global settings
   - PUT /api/v1/settings - Update global settings
   - GET /api/v1/settings/sports - All sport configs
   - GET /api/v1/settings/sports/{sport} - Single sport
   - PUT /api/v1/settings/sports/{sport} - Update sport config

3. src/api/routes/bot.py:
   - POST /api/v1/bot/start
   - POST /api/v1/bot/stop
   - POST /api/v1/bot/pause
   - POST /api/v1/bot/resume

4. src/api/routes/trading.py:
   - GET /api/v1/markets - Available markets
   - POST /api/v1/orders - Place manual order
   - DELETE /api/v1/positions/{id} - Close position
   - POST /api/v1/positions/close-all

5. src/api/websocket.py:
   - WebSocket endpoint at /ws
   - Require JWT in query param
   - Broadcast: status_update, position_update, new_trade, game_update, log

6. Create dashboard templates in src/templates/dashboard/:

   layout.html:
   - Navigation sidebar (Dashboard, Settings, Sports, History, Manual, Logs)
   - Header with user info and logout
   - Main content area
   - Mobile responsive

   index.html (main dashboard):
   - Status cards: Bot Status, Today's P&L, Open Positions count
   - Open positions table with close buttons
   - Tracked games table
   - Activity log feed
   - All data updates via WebSocket

   settings.html:
   - Bot enabled toggle
   - Dry run mode toggle
   - Risk limits inputs
   - Kalshi connection status
   - Discord webhook config
   - Save button

   sports.html:
   - Tab navigation for each sport
   - All config fields per sport
   - Enable/disable toggle per sport
   - Save button per sport

   history.html:
   - Filter by sport, date range
   - Table of closed positions
   - P&L column with color coding
   - Export to CSV button

   manual.html:
   - List of available markets
   - Order form: market, side, price, amount
   - Place order button
   - Confirmation dialog

   logs.html:
   - Filter by level, category
   - Scrollable log list
   - Auto-refresh

7. src/static/js/dashboard.js:
   - WebSocket connection management
   - Real-time UI updates
   - Form handlers
   - Confirmation dialogs

Design: Clean, professional, no emojis, mobile responsive.
Use Tailwind CSS utility classes.
```

### PROMPT 9: Discord Alerts

```
Implement the Discord alert system.

src/services/alert_service.py:

class AlertService:
    """Discord webhook integration for trade alerts."""
    
    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url
    
    async def send_entry_alert(
        self,
        game_title: str,
        side: str,
        team: str,
        entry_price: float,
        quantity: int,
        cost: float,
        pregame_odds: float,
        current_odds: float,
        game_status: str
    ):
        """Send Discord alert for position entry."""
        embed = {
            "title": "BUY ORDER EXECUTED",
            "color": 3066993,  # Green
            "fields": [
                {"name": "Game", "value": game_title, "inline": False},
                {"name": "Side", "value": f"{side.upper()} {team}", "inline": True},
                {"name": "Entry Price", "value": f"{entry_price}c", "inline": True},
                {"name": "Contracts", "value": str(quantity), "inline": True},
                {"name": "Cost", "value": f"${cost:.2f}", "inline": True},
                {"name": "Pregame Odds", "value": f"{pregame_odds}%", "inline": True},
                {"name": "Current Odds", "value": f"{current_odds}%", "inline": True},
                {"name": "Game Status", "value": game_status, "inline": True},
            ],
            "timestamp": datetime.utcnow().isoformat()
        }
        await self._send_webhook({"embeds": [embed]})
    
    async def send_exit_alert(
        self,
        game_title: str,
        entry_price: float,
        exit_price: float,
        pnl: float,
        reason: str,
        hold_time: str
    ):
        """Send Discord alert for position exit."""
        is_profit = pnl >= 0
        color = 3066993 if is_profit else 15158332  # Green or Red
        title = "POSITION CLOSED - PROFIT" if is_profit else "POSITION CLOSED - LOSS"
        
        embed = {
            "title": title,
            "color": color,
            "fields": [
                {"name": "Game", "value": game_title, "inline": False},
                {"name": "Entry", "value": f"{entry_price}c", "inline": True},
                {"name": "Exit", "value": f"{exit_price}c", "inline": True},
                {"name": "P&L", "value": f"${pnl:+.2f}", "inline": True},
                {"name": "Reason", "value": reason, "inline": True},
                {"name": "Hold Time", "value": hold_time, "inline": True},
            ],
            "timestamp": datetime.utcnow().isoformat()
        }
        await self._send_webhook({"embeds": [embed]})
    
    async def send_daily_summary(
        self,
        date: str,
        total_trades: int,
        wins: int,
        losses: int,
        net_pnl: float,
        biggest_win: float,
        biggest_loss: float
    ):
        """Send daily summary alert."""
        embed = {
            "title": f"DAILY SUMMARY - {date}",
            "color": 3447003,  # Blue
            "fields": [
                {"name": "Total Trades", "value": str(total_trades), "inline": True},
                {"name": "Win Rate", "value": f"{wins}/{total_trades}", "inline": True},
                {"name": "Net P&L", "value": f"${net_pnl:+.2f}", "inline": True},
                {"name": "Biggest Win", "value": f"${biggest_win:+.2f}", "inline": True},
                {"name": "Biggest Loss", "value": f"${biggest_loss:.2f}", "inline": True},
            ],
            "timestamp": datetime.utcnow().isoformat()
        }
        await self._send_webhook({"embeds": [embed]})
    
    async def send_error_alert(self, error_type: str, message: str):
        """Send error notification."""
        embed = {
            "title": f"ERROR: {error_type}",
            "color": 15158332,  # Red
            "description": message,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self._send_webhook({"embeds": [embed]})
    
    async def test_webhook(self) -> bool:
        """Send test message, return success status."""
        try:
            embed = {
                "title": "Webhook Test",
                "description": "Your Discord alerts are configured correctly.",
                "color": 3066993,
                "timestamp": datetime.utcnow().isoformat()
            }
            await self._send_webhook({"embeds": [embed]})
            return True
        except Exception:
            return False
    
    async def _send_webhook(self, payload: dict):
        """Send payload to Discord webhook."""
        if not self.webhook_url:
            return
        async with httpx.AsyncClient() as client:
            response = await client.post(self.webhook_url, json=payload)
            response.raise_for_status()

No emojis in any alert messages.
```

### PROMPT 10: Deployment and Documentation

```
Finalize deployment configuration and documentation.

1. Update Dockerfile for production:
   - Multi-stage build
   - Non-root user
   - Health check
   - Proper Python optimization flags

2. docker-compose.yml for local development:
   - App service
   - PostgreSQL service
   - Volume for database persistence
   - Environment file reference

3. Create .env.example with all variables:
   - DATABASE_URL
   - SECRET_KEY
   - JWT_SECRET_KEY
   - ENCRYPTION_KEY
   - Debug settings

4. Create docs/USER_GUIDE.md:
   - Getting started
   - Dashboard overview
   - Understanding the bot
   - Configuring sports
   - Risk management
   - Discord alerts
   - Troubleshooting
   - FAQ
   (Professional tone, no emojis)

5. Create docs/SETUP.md:
   - Prerequisites
   - Local development setup
   - Environment configuration
   - Database migrations
   - Running the application

6. Create docs/DEPLOYMENT.md:
   - GCP Cloud Run deployment steps
   - Cloud SQL setup
   - Secret Manager configuration
   - Custom domain (optional)
   - Monitoring setup

7. Update README.md:
   - Project overview
   - Tech stack
   - Quick start
   - Documentation links
   - License

8. Create deployment script for GCP:
   - gcloud commands for Cloud Run
   - Cloud SQL connection
   - Environment variables setup

All documentation should be professional, clear, and without emojis.
```

---

## Final Testing Checklist

Before delivering to client:

```
AUTHENTICATION
[ ] User can register with valid email/password
[ ] User can login and receives tokens
[ ] Protected routes reject invalid tokens
[ ] Token refresh works correctly

ONBOARDING
[ ] All 9 steps display correctly
[ ] Progress saves between sessions
[ ] Kalshi connection works
[ ] Sport config saves correctly
[ ] Discord test webhook works

TRADING ENGINE
[ ] Bot starts in dry run mode
[ ] Pregame baselines captured
[ ] Entry conditions trigger correctly
[ ] Exit conditions trigger correctly
[ ] Positions tracked accurately
[ ] P&L calculations correct

DASHBOARD
[ ] All pages load without errors
[ ] Real-time updates via WebSocket
[ ] Settings changes apply immediately
[ ] Manual trading works
[ ] History displays correctly

ALERTS
[ ] Discord entry alerts sent
[ ] Discord exit alerts sent
[ ] Daily summary works

DEPLOYMENT
[ ] Docker builds successfully
[ ] App runs in container
[ ] Database migrations work
[ ] Works on mobile devices
```

---

## Client Handoff

Deliverables:
1. Working deployment URL
2. Login credentials
3. USER_GUIDE.md documentation
4. Source code (GitHub repo)
5. 30-minute walkthrough call

Support:
- Offer 30-day bug fix support
- Discuss ongoing maintenance pricing
- Get testimonial/review for portfolio
