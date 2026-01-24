# Polymarket Sports Trading Bot - Product Requirements Document

**Version**: 1.0  
**Created**: January 23, 2026  
**Client**: The Degen  
**Developer**: Ben Anokye-Davies  
**Budget**: $230 (one-time)  
**Hosting**: DigitalOcean Droplet via GitHub Education Pack ($200 credit)

---

## 1. Executive Summary

### 1.1 Product Overview
Automated trading bot for Polymarket prediction markets focused on live sports betting. The system monitors live sports events via ESPN, captures pre-game baseline prices from Polymarket, and executes trades when prices drop below configured thresholds during live games.

### 1.2 Core Value Proposition
- Automated entry when odds drop during live games (value betting)
- Configurable risk management (stop-loss, take-profit, position limits)
- Web dashboard for non-technical user
- 24/7 operation on cloud infrastructure

### 1.3 Success Criteria
- [ ] Bot can connect to Polymarket and place orders
- [ ] Bot can fetch live game state from ESPN
- [ ] Bot correctly matches ESPN games to Polymarket markets
- [ ] Bot captures baselines and enters positions based on thresholds
- [ ] Bot exits positions on take-profit, stop-loss, or time conditions
- [ ] Web dashboard displays positions, P&L, and bot status
- [ ] User can configure sports, thresholds, and risk settings
- [ ] System runs 24/7 without intervention

---

## 2. Technical Architecture

### 2.1 System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        WEB BROWSER                               │
│                   (Dashboard, Settings)                          │
└─────────────────────────┬───────────────────────────────────────┘
                          │ HTTPS
┌─────────────────────────▼───────────────────────────────────────┐
│                     FASTAPI SERVER                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │   Auth   │  │   API    │  │WebSocket │  │  Trading Engine  │ │
│  │  Routes  │  │  Routes  │  │ Handler  │  │  (Background)    │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘ │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                      SERVICES                             │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────────────┐  │   │
│  │  │ Polymarket │  │   ESPN     │  │  Market Matcher    │  │   │
│  │  │   Client   │  │  Service   │  │                    │  │   │
│  │  └────────────┘  └────────────┘  └────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│                      POSTGRESQL                                  │
│   users, polymarket_accounts, sport_configs, positions, etc.    │
└─────────────────────────────────────────────────────────────────┘
                          │
          ┌───────────────┴───────────────┐
          ▼                               ▼
┌──────────────────┐            ┌──────────────────┐
│  POLYMARKET API  │            │    ESPN API      │
│  (Prices/Orders) │            │  (Game State)    │
└──────────────────┘            └──────────────────┘
```

### 2.2 Technology Stack

| Component | Technology | Version |
|-----------|------------|---------|
| Runtime | Python | 3.11+ |
| Framework | FastAPI | 0.109+ |
| ORM | SQLAlchemy | 2.0+ (async) |
| Database Driver | asyncpg | 0.29+ |
| Validation | Pydantic | 2.5+ |
| JWT | python-jose | 3.3+ |
| Password Hashing | passlib[bcrypt] | 1.7+ |
| Encryption | cryptography | 42+ |
| HTTP Client | httpx | 0.26+ |
| WebSocket | websocket-client | 1.7+ |
| Polymarket SDK | py-clob-client | latest |
| Templates | Jinja2 | 3.1+ |
| Migrations | Alembic | 1.13+ |
| Task Scheduling | APScheduler | 3.10+ |

### 2.3 External Dependencies

| Service | Purpose | Auth |
|---------|---------|------|
| Polymarket CLOB API | Market data, order execution | L1/L2 |
| Polymarket WebSocket | Real-time price updates | None/L2 |
| ESPN API | Live game state | None |
| Discord Webhooks | Trade alerts | Webhook URL |

---

## 3. Database Schema

### 3.1 Entity Relationship

```
users (1) ─────────────── (1) polymarket_accounts
  │
  ├──── (1:N) ──── sport_configs
  │
  ├──── (1:N) ──── tracked_markets
  │                    │
  │                    └──── (1:N) ──── positions
  │                                        │
  │                                        └──── (1:N) ──── trades
  │
  ├──── (1:1) ──── global_settings
  │
  └──── (1:N) ──── activity_logs
```

### 3.2 Table Definitions

#### 3.2.1 users
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    onboarding_completed BOOLEAN DEFAULT false,
    onboarding_step INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### 3.2.2 polymarket_accounts
```sql
CREATE TABLE polymarket_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    private_key_encrypted TEXT NOT NULL,
    funder_address VARCHAR(42) NOT NULL,
    api_key_encrypted TEXT,
    api_secret_encrypted TEXT,
    api_passphrase_encrypted TEXT,
    signature_type INTEGER DEFAULT 1,
    is_connected BOOLEAN DEFAULT false,
    last_balance_usdc DECIMAL(18, 6),
    last_verified_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### 3.2.3 sport_configs
```sql
CREATE TABLE sport_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    sport VARCHAR(20) NOT NULL,  -- nba, nfl, mlb, nhl
    enabled BOOLEAN DEFAULT true,
    
    -- Entry parameters
    min_pregame_price DECIMAL(5, 4) DEFAULT 0.55,
    entry_threshold_drop DECIMAL(5, 4) DEFAULT 0.15,
    entry_threshold_absolute DECIMAL(5, 4) DEFAULT 0.50,
    max_entry_segment VARCHAR(20) DEFAULT 'q3',
    min_time_remaining_seconds INTEGER DEFAULT 300,
    
    -- Exit parameters
    take_profit_pct DECIMAL(5, 4) DEFAULT 0.20,
    stop_loss_pct DECIMAL(5, 4) DEFAULT 0.10,
    exit_before_segment VARCHAR(20) DEFAULT 'q4_2min',
    
    -- Position sizing
    position_size_usdc DECIMAL(10, 2) DEFAULT 50.00,
    max_positions_per_game INTEGER DEFAULT 1,
    max_total_positions INTEGER DEFAULT 5,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(user_id, sport)
);
```

#### 3.2.4 tracked_markets
```sql
CREATE TABLE tracked_markets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    
    -- Polymarket identifiers
    condition_id VARCHAR(100) NOT NULL,
    token_id_yes VARCHAR(100) NOT NULL,
    token_id_no VARCHAR(100) NOT NULL,
    question TEXT,
    
    -- ESPN identifiers
    espn_event_id VARCHAR(50),
    sport VARCHAR(20) NOT NULL,
    
    -- Teams
    home_team VARCHAR(100),
    away_team VARCHAR(100),
    home_abbrev VARCHAR(10),
    away_abbrev VARCHAR(10),
    
    -- Game timing
    game_start_time TIMESTAMP WITH TIME ZONE,
    
    -- Baseline tracking
    baseline_price_yes DECIMAL(5, 4),
    baseline_price_no DECIMAL(5, 4),
    baseline_captured_at TIMESTAMP WITH TIME ZONE,
    
    -- Current state
    current_price_yes DECIMAL(5, 4),
    current_price_no DECIMAL(5, 4),
    is_live BOOLEAN DEFAULT false,
    is_finished BOOLEAN DEFAULT false,
    current_period INTEGER,
    time_remaining_seconds INTEGER,
    home_score INTEGER,
    away_score INTEGER,
    
    -- Matching confidence
    match_confidence DECIMAL(3, 2),
    
    last_updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(user_id, condition_id)
);
```

#### 3.2.5 positions
```sql
CREATE TABLE positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    tracked_market_id UUID REFERENCES tracked_markets(id),
    
    -- Position details
    condition_id VARCHAR(100) NOT NULL,
    token_id VARCHAR(100) NOT NULL,
    side VARCHAR(10) NOT NULL,  -- YES or NO
    team VARCHAR(100),
    
    -- Entry
    entry_price DECIMAL(5, 4) NOT NULL,
    entry_size DECIMAL(18, 6) NOT NULL,
    entry_cost_usdc DECIMAL(18, 6) NOT NULL,
    entry_reason TEXT,
    entry_order_id VARCHAR(100),
    
    -- Exit (nullable until closed)
    exit_price DECIMAL(5, 4),
    exit_size DECIMAL(18, 6),
    exit_proceeds_usdc DECIMAL(18, 6),
    exit_reason VARCHAR(50),  -- take_profit, stop_loss, time_exit, game_finished, manual
    exit_order_id VARCHAR(100),
    
    -- P&L
    realized_pnl_usdc DECIMAL(18, 6),
    
    -- Status
    status VARCHAR(20) DEFAULT 'open',  -- open, closing, closed
    
    opened_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    closed_at TIMESTAMP WITH TIME ZONE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### 3.2.6 trades
```sql
CREATE TABLE trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    position_id UUID REFERENCES positions(id),
    
    -- Order details
    polymarket_order_id VARCHAR(100),
    action VARCHAR(10) NOT NULL,  -- BUY or SELL
    side VARCHAR(10) NOT NULL,    -- YES or NO
    
    -- Execution
    price DECIMAL(5, 4) NOT NULL,
    size DECIMAL(18, 6) NOT NULL,
    total_usdc DECIMAL(18, 6) NOT NULL,
    fee_usdc DECIMAL(18, 6) DEFAULT 0,
    
    -- Status
    status VARCHAR(20) DEFAULT 'pending',  -- pending, filled, cancelled, failed
    
    executed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### 3.2.7 global_settings
```sql
CREATE TABLE global_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    
    -- Bot control
    bot_enabled BOOLEAN DEFAULT false,
    
    -- Risk management
    max_daily_loss_usdc DECIMAL(10, 2) DEFAULT 100.00,
    max_portfolio_exposure_usdc DECIMAL(10, 2) DEFAULT 500.00,
    
    -- Alerts
    discord_webhook_url TEXT,
    discord_alerts_enabled BOOLEAN DEFAULT false,
    
    -- Trading cycle
    poll_interval_seconds INTEGER DEFAULT 10,
    
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### 3.2.8 activity_logs
```sql
CREATE TABLE activity_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    
    level VARCHAR(20) NOT NULL,  -- DEBUG, INFO, WARNING, ERROR, CRITICAL
    category VARCHAR(50) NOT NULL,  -- auth, trading, market, system
    message TEXT NOT NULL,
    details JSONB,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_activity_logs_user_created ON activity_logs(user_id, created_at DESC);
CREATE INDEX idx_activity_logs_level ON activity_logs(level);
```

---

## 4. API Specification

### 4.1 Authentication Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | /auth/register | Create new user account | None |
| POST | /auth/login | Authenticate and get tokens | None |
| POST | /auth/refresh | Refresh access token | Refresh Token |
| POST | /auth/logout | Invalidate tokens | Access Token |
| GET | /auth/me | Get current user info | Access Token |

#### Request/Response Examples

**POST /auth/register**
```json
// Request
{
    "email": "user@example.com",
    "password": "SecurePassword123!",
    "confirm_password": "SecurePassword123!"
}

// Response 201
{
    "id": "uuid",
    "email": "user@example.com",
    "created_at": "2026-01-23T12:00:00Z",
    "onboarding_completed": false
}
```

**POST /auth/login**
```json
// Request
{
    "email": "user@example.com",
    "password": "SecurePassword123!"
}

// Response 200
{
    "access_token": "eyJ...",
    "refresh_token": "eyJ...",
    "token_type": "bearer",
    "expires_in": 900,
    "user": {
        "id": "uuid",
        "email": "user@example.com",
        "onboarding_completed": false,
        "onboarding_step": 0
    }
}
```

### 4.2 Onboarding Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | /api/v1/onboarding/status | Get onboarding progress | Access Token |
| POST | /api/v1/onboarding/step/{n} | Complete step n | Access Token |
| POST | /api/v1/onboarding/wallet/connect | Submit wallet credentials | Access Token |
| POST | /api/v1/onboarding/wallet/test | Test Polymarket connection | Access Token |
| POST | /api/v1/onboarding/skip | Skip to dashboard | Access Token |

### 4.3 Dashboard Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | /api/v1/dashboard/status | Bot status, balance, P&L summary | Access Token |
| GET | /api/v1/dashboard/positions | All open positions | Access Token |
| GET | /api/v1/dashboard/positions/history | Closed positions | Access Token |
| GET | /api/v1/dashboard/markets | Tracked markets with prices | Access Token |
| GET | /api/v1/dashboard/stats | Trading statistics | Access Token |

### 4.4 Settings Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | /api/v1/settings | Get global settings | Access Token |
| PUT | /api/v1/settings | Update global settings | Access Token |
| GET | /api/v1/settings/sports | Get all sport configs | Access Token |
| GET | /api/v1/settings/sports/{sport} | Get specific sport config | Access Token |
| PUT | /api/v1/settings/sports/{sport} | Update sport config | Access Token |
| POST | /api/v1/settings/discord/test | Test Discord webhook | Access Token |

### 4.5 Bot Control Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | /api/v1/bot/start | Start trading engine | Access Token |
| POST | /api/v1/bot/stop | Stop trading engine | Access Token |
| GET | /api/v1/bot/status | Get engine status | Access Token |

### 4.6 Manual Trading Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | /api/v1/markets/available | List available sports markets | Access Token |
| POST | /api/v1/positions/{id}/close | Close specific position | Access Token |
| POST | /api/v1/positions/close-all | Close all positions | Access Token |

### 4.7 Activity Log Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | /api/v1/logs | Get activity logs (paginated) | Access Token |
| GET | /api/v1/logs/export | Export logs as CSV | Access Token |

---

## 5. Service Implementations

### 5.1 PolymarketClient (src/services/polymarket_client.py)

**Responsibilities:**
- L1 authentication (create/derive API credentials)
- L2 authentication (HMAC-signed requests)
- Get account balance
- Get market prices and orderbooks
- Place orders (limit orders)
- Cancel orders
- Get positions
- Get order status

**Key Methods:**
```python
class PolymarketClient:
    async def create_or_derive_api_creds(self) -> ApiCredentials
    async def get_balance(self) -> Decimal
    async def get_markets(self, tag: str = None) -> list[Market]
    async def get_price(self, token_id: str) -> Price
    async def get_orderbook(self, token_id: str) -> Orderbook
    async def create_order(self, token_id: str, side: str, price: Decimal, size: Decimal) -> Order
    async def cancel_order(self, order_id: str) -> bool
    async def get_positions(self) -> list[Position]
    async def test_connection(self) -> tuple[bool, str, Decimal]
```

### 5.2 PolymarketWebSocket (src/services/polymarket_ws.py)

**Responsibilities:**
- Connect to CLOB WebSocket
- Subscribe to market channels (public price updates)
- Subscribe to user channel (order updates)
- Handle reconnection with exponential backoff
- Emit events for price changes

**Key Methods:**
```python
class PolymarketWebSocket:
    async def connect(self) -> None
    async def subscribe_market(self, token_ids: list[str]) -> None
    async def unsubscribe_market(self, token_ids: list[str]) -> None
    async def subscribe_user(self, condition_ids: list[str], auth: dict) -> None
    def on_price_update(self, callback: Callable) -> None
    def on_order_update(self, callback: Callable) -> None
    async def disconnect(self) -> None
```

### 5.3 ESPNService (src/services/espn_service.py)

**Responsibilities:**
- Fetch scoreboard for each sport
- Parse game state (period, time, scores)
- Identify live games
- Get detailed game summary

**Key Methods:**
```python
class ESPNService:
    async def get_scoreboard(self, sport: str) -> list[Game]
    async def get_live_games(self, sport: str) -> list[Game]
    async def get_game_details(self, sport: str, event_id: str) -> GameDetails
    def parse_game_state(self, raw_game: dict) -> GameState
    def normalize_segment(self, period: int, sport: str) -> str
```

### 5.4 MarketMatcher (src/services/market_matcher.py)

**Responsibilities:**
- Match ESPN games to Polymarket markets
- Use multiple matching strategies with confidence scoring
- Cache successful matches

**Key Methods:**
```python
class MarketMatcher:
    async def match_game(self, espn_game: GameState, polymarket_markets: list[Market]) -> MatchResult | None
    def match_by_abbreviation(self, espn_game: GameState, markets: list[Market]) -> MatchResult | None
    def match_by_team_name(self, espn_game: GameState, markets: list[Market]) -> MatchResult | None
    def match_by_time_window(self, espn_game: GameState, markets: list[Market]) -> MatchResult | None
```

### 5.5 TradingEngine (src/services/trading_engine.py)

**Responsibilities:**
- Main trading loop (runs in background)
- Fetch data from both sources
- Match and merge data
- Capture baselines for pregame markets
- Evaluate entry conditions
- Evaluate exit conditions
- Execute orders
- Update positions

**Key Methods:**
```python
class TradingEngine:
    async def start(self) -> None
    async def stop(self) -> None
    async def trading_cycle(self) -> None
    async def capture_baseline(self, market: TrackedMarket) -> None
    async def check_entry(self, market: TrackedMarket, config: SportConfig) -> None
    async def check_exit(self, position: Position, market: TrackedMarket, config: SportConfig) -> None
    async def execute_entry(self, market: TrackedMarket, config: SportConfig, reason: str) -> Position
    async def execute_exit(self, position: Position, reason: str) -> None
    def should_enter(self, market: TrackedMarket, config: SportConfig) -> tuple[bool, str]
    def should_exit(self, position: Position, market: TrackedMarket, config: SportConfig) -> tuple[bool, str]
```

### 5.6 AlertService (src/services/alert_service.py)

**Responsibilities:**
- Send Discord webhook notifications
- Format trade alerts
- Send daily summaries

**Key Methods:**
```python
class AlertService:
    async def send_entry_alert(self, position: Position, market: TrackedMarket) -> None
    async def send_exit_alert(self, position: Position, market: TrackedMarket) -> None
    async def send_error_alert(self, error: str) -> None
    async def send_daily_summary(self, stats: DailyStats) -> None
    async def test_webhook(self, webhook_url: str) -> bool
```

---

## 6. Business Logic

### 6.1 Trading Cycle Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    TRADING CYCLE (every 10s)                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Bot Enabled?   │───No──▶ Skip
                    └────────┬────────┘
                             │ Yes
                              ▼
                    ┌─────────────────┐
                    │ Check Daily     │
                    │ Loss Limit      │───Hit──▶ Pause Bot
                    └────────┬────────┘
                             │ OK
                              ▼
              ┌───────────────────────────────┐
              │  For each enabled sport:       │
              │  1. Fetch Polymarket markets   │
              │  2. Fetch ESPN scoreboard      │
              │  3. Match games to markets     │
              └───────────────┬───────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │  For each matched game:        │
              │                                │
              │  IF pregame AND within 15min:  │
              │    → Capture baseline          │
              │                                │
              │  IF live:                      │
              │    → Check entry conditions    │
              │    → Execute entry if met      │
              │                                │
              │  IF finished:                  │
              │    → Close any open positions  │
              └───────────────┬───────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │  For each open position:       │
              │  1. Get current price          │
              │  2. Check take profit          │
              │  3. Check stop loss            │
              │  4. Check time exit            │
              │  5. Execute exit if needed     │
              └───────────────────────────────┘
```

### 6.2 Entry Conditions

All conditions must be TRUE:

| # | Condition | Implementation |
|---|-----------|----------------|
| 1 | Game is LIVE | `espn_state.is_live == True` |
| 2 | Baseline captured | `market.baseline_price_yes is not None` |
| 3 | Within entry segment | `current_segment <= config.max_entry_segment` |
| 4 | Sufficient time remaining | `time_remaining_seconds >= config.min_time_remaining_seconds` |
| 5 | Price drop threshold met | `baseline - current >= config.entry_threshold_drop` OR `current <= config.entry_threshold_absolute` |
| 6 | Position limit not reached | `open_positions_for_game < config.max_positions_per_game` |
| 7 | Total position limit not reached | `total_open_positions < config.max_total_positions` |
| 8 | Sufficient balance | `balance >= config.position_size_usdc` |

### 6.3 Exit Conditions

Any condition being TRUE triggers exit:

| # | Condition | Reason Code |
|---|-----------|-------------|
| 1 | `(current_price - entry_price) / entry_price >= take_profit_pct` | `take_profit` |
| 2 | `(entry_price - current_price) / entry_price >= stop_loss_pct` | `stop_loss` |
| 3 | `current_segment >= config.exit_before_segment` | `time_exit` |
| 4 | `espn_state.is_finished == True` | `game_finished` |

### 6.4 Segment Mapping

**NBA/NFL (Quarters):**
| Period | Segment Code | Description |
|--------|--------------|-------------|
| 1 | q1 | 1st Quarter |
| 2 | q2 | 2nd Quarter |
| 3 | q3 | 3rd Quarter |
| 4 | q4 | 4th Quarter |
| 5+ | ot | Overtime |

**NHL (Periods):**
| Period | Segment Code | Description |
|--------|--------------|-------------|
| 1 | p1 | 1st Period |
| 2 | p2 | 2nd Period |
| 3 | p3 | 3rd Period |
| 4+ | ot | Overtime |

**MLB (Innings):**
| Inning | Segment Code |
|--------|--------------|
| 1-9 | inning_1 to inning_9 |
| 10+ | extra_{n} |

---

## 7. File Structure

```
polymarket-bot/
├── src/
│   ├── __init__.py
│   ├── main.py                          # FastAPI app entry point
│   ├── config.py                        # Pydantic settings
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py                      # get_db, get_current_user
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── auth.py                  # Authentication endpoints
│   │       ├── onboarding.py            # Onboarding endpoints
│   │       ├── dashboard.py             # Dashboard data endpoints
│   │       ├── settings.py              # Settings endpoints
│   │       ├── bot.py                   # Bot control endpoints
│   │       ├── trading.py               # Manual trading endpoints
│   │       └── logs.py                  # Activity log endpoints
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── security.py                  # JWT, password hashing
│   │   ├── encryption.py                # Fernet encryption
│   │   └── exceptions.py                # Custom exceptions
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── polymarket_client.py         # Polymarket CLOB API client
│   │   ├── polymarket_ws.py             # Polymarket WebSocket
│   │   ├── espn_service.py              # ESPN API service
│   │   ├── market_matcher.py            # ESPN-Polymarket matcher
│   │   ├── trading_engine.py            # Main trading logic
│   │   └── alert_service.py             # Discord alerts
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── polymarket_account.py
│   │   ├── sport_config.py
│   │   ├── tracked_market.py
│   │   ├── position.py
│   │   ├── trade.py
│   │   ├── global_settings.py
│   │   └── activity_log.py
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── onboarding.py
│   │   ├── dashboard.py
│   │   ├── settings.py
│   │   ├── trading.py
│   │   └── common.py
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── database.py                  # Engine, session factory
│   │   └── crud/
│   │       ├── __init__.py
│   │       ├── user.py
│   │       ├── polymarket_account.py
│   │       ├── sport_config.py
│   │       ├── tracked_market.py
│   │       ├── position.py
│   │       └── global_settings.py
│   │
│   ├── templates/
│   │   ├── base.html
│   │   ├── auth/
│   │   │   ├── login.html
│   │   │   └── register.html
│   │   ├── onboarding/
│   │   │   ├── layout.html
│   │   │   └── steps/
│   │   │       ├── step1_welcome.html
│   │   │       ├── step2_how_it_works.html
│   │   │       ├── step3_connect_wallet.html
│   │   │       ├── step4_configure_sport.html
│   │   │       ├── step5_risk_settings.html
│   │   │       ├── step6_position_sizing.html
│   │   │       ├── step7_discord.html
│   │   │       ├── step8_review.html
│   │   │       └── step9_tour.html
│   │   └── dashboard/
│   │       ├── layout.html
│   │       ├── index.html
│   │       ├── positions.html
│   │       ├── markets.html
│   │       ├── settings.html
│   │       ├── sports.html
│   │       └── logs.html
│   │
│   └── static/
│       ├── css/
│       │   └── main.css
│       └── js/
│           ├── auth.js
│           ├── onboarding.js
│           ├── dashboard.js
│           └── settings.js
│
├── alembic/
│   ├── versions/
│   ├── env.py
│   └── script.py.mako
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_polymarket_client.py
│   ├── test_espn_service.py
│   ├── test_market_matcher.py
│   └── test_trading_engine.py
│
├── .env.example
├── .gitignore
├── alembic.ini
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

## 8. Implementation Order

### Phase 1: Foundation (Files 1-15)
1. `requirements.txt` - All dependencies
2. `.env.example` - Environment template
3. `src/config.py` - Settings management
4. `src/main.py` - FastAPI app
5. `src/db/database.py` - Database connection
6. `src/models/*.py` - All SQLAlchemy models
7. `alembic/env.py` - Migration config
8. `src/core/security.py` - JWT, bcrypt
9. `src/core/encryption.py` - Fernet
10. `src/core/exceptions.py` - Custom exceptions
11. `src/schemas/auth.py` - Auth schemas
12. `src/schemas/common.py` - Shared schemas
13. `src/db/crud/user.py` - User CRUD
14. `src/api/deps.py` - Dependencies
15. `src/api/routes/auth.py` - Auth routes

### Phase 2: Onboarding (Files 16-22)
16. `src/schemas/onboarding.py` - Onboarding schemas
17. `src/db/crud/polymarket_account.py` - Account CRUD
18. `src/services/polymarket_client.py` - Polymarket API
19. `src/api/routes/onboarding.py` - Onboarding routes
20. `src/templates/base.html` - Base template
21. `src/templates/auth/*.html` - Auth templates
22. `src/templates/onboarding/*.html` - Onboarding templates

### Phase 3: Core Services (Files 23-30)
23. `src/services/espn_service.py` - ESPN API
24. `src/services/market_matcher.py` - Matcher
25. `src/services/polymarket_ws.py` - WebSocket
26. `src/services/alert_service.py` - Discord alerts
27. `src/db/crud/sport_config.py` - Sport config CRUD
28. `src/db/crud/tracked_market.py` - Market CRUD
29. `src/db/crud/position.py` - Position CRUD
30. `src/db/crud/global_settings.py` - Settings CRUD

### Phase 4: Trading Engine (Files 31-35)
31. `src/services/trading_engine.py` - Main engine
32. `src/schemas/trading.py` - Trading schemas
33. `src/schemas/dashboard.py` - Dashboard schemas
34. `src/schemas/settings.py` - Settings schemas
35. `src/api/routes/bot.py` - Bot control routes

### Phase 5: Dashboard (Files 36-45)
36. `src/api/routes/dashboard.py` - Dashboard routes
37. `src/api/routes/settings.py` - Settings routes
38. `src/api/routes/trading.py` - Trading routes
39. `src/api/routes/logs.py` - Log routes
40. `src/templates/dashboard/*.html` - Dashboard templates
41. `src/static/css/main.css` - Styles
42. `src/static/js/*.js` - JavaScript files

### Phase 6: Deployment (Files 43-47)
43. `Dockerfile` - Container definition
44. `docker-compose.yml` - Compose config
45. `.gitignore` - Git ignore
46. `README.md` - Documentation
47. `pyproject.toml` - Project metadata

---

## 9. Environment Variables

```bash
# .env.example

# Application
APP_NAME=polymarket-bot
DEBUG=false
SECRET_KEY=your-secret-key-min-32-characters-long

# Database
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/polymarket_bot

# JWT
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# Encryption
ENCRYPTION_KEY=your-fernet-compatible-key

# Server
HOST=0.0.0.0
PORT=8000

# Polymarket (these are per-user, stored encrypted in DB)
# POLYMARKET_PRIVATE_KEY=
# POLYMARKET_FUNDER_ADDRESS=
```

---

## 10. Acceptance Criteria

### 10.1 Authentication
- [ ] User can register with email/password
- [ ] User can login and receive JWT tokens
- [ ] User can refresh expired access tokens
- [ ] Protected routes require valid token

### 10.2 Onboarding
- [ ] New users see onboarding flow
- [ ] User can connect Polymarket wallet
- [ ] Connection test shows balance
- [ ] User can configure first sport
- [ ] User can set risk parameters
- [ ] User can optionally add Discord webhook

### 10.3 Trading Engine
- [ ] Engine starts/stops on command
- [ ] Baselines captured within 15 min of game start
- [ ] Entry conditions evaluated correctly
- [ ] Orders placed on Polymarket
- [ ] Exit conditions trigger order placement
- [ ] Positions tracked in database

### 10.4 Dashboard
- [ ] Shows bot status (running/stopped)
- [ ] Shows current balance
- [ ] Shows open positions with P&L
- [ ] Shows closed positions history
- [ ] Shows tracked markets
- [ ] Shows activity log

### 10.5 Settings
- [ ] User can enable/disable sports
- [ ] User can adjust thresholds
- [ ] User can set risk limits
- [ ] User can test Discord webhook
- [ ] Settings persist across sessions

### 10.6 Alerts
- [ ] Discord notification on entry
- [ ] Discord notification on exit
- [ ] Discord notification on errors

---

## 11. Testing Requirements

### 11.1 Unit Tests
- [ ] `test_security.py` - JWT, password hashing
- [ ] `test_encryption.py` - Fernet encrypt/decrypt
- [ ] `test_market_matcher.py` - All matching strategies
- [ ] `test_espn_service.py` - Response parsing

### 11.2 Integration Tests
- [ ] `test_auth_flow.py` - Full auth flow
- [ ] `test_polymarket_client.py` - API calls (with mocking)
- [ ] `test_trading_engine.py` - Entry/exit logic

### 11.3 Manual Testing
- [ ] Complete onboarding flow
- [ ] Place test order on Polymarket
- [ ] Verify Discord alerts
- [ ] Run overnight test

---

## 12. Delivery Checklist

### Pre-Delivery
- [ ] All acceptance criteria met
- [ ] No hardcoded credentials
- [ ] Environment variables documented
- [ ] Database migrations work
- [ ] Docker build succeeds
- [ ] README complete

### Delivery
- [ ] Source code in GitHub repo
- [ ] Deployment instructions provided
- [ ] Client walkthrough completed
- [ ] Credentials transferred securely

### Post-Delivery
- [ ] 1 week of bug fixes included
- [ ] Client can reach developer for questions

---

## Appendix A: Polymarket API Reference

### Base URLs
- CLOB: `https://clob.polymarket.com`
- Gamma: `https://gamma-api.polymarket.com`
- Data: `https://data-api.polymarket.com`
- WebSocket: `wss://ws-subscriptions-clob.polymarket.com/ws/`

### Key Endpoints

**GET /price**
```
GET https://clob.polymarket.com/price?token_id={token_id}
Response: { "price": "0.65" }
```

**GET /book**
```
GET https://clob.polymarket.com/book?token_id={token_id}
Response: {
  "bids": [{"price": "0.64", "size": "100"}],
  "asks": [{"price": "0.66", "size": "150"}]
}
```

**POST /order** (L2 Auth Required)
```
POST https://clob.polymarket.com/order
Headers: POLY_ADDRESS, POLY_SIGNATURE, POLY_TIMESTAMP, POLY_API_KEY, POLY_PASSPHRASE
Body: {
  "order": {
    "tokenID": "...",
    "price": "0.65",
    "size": "10",
    "side": "BUY",
    "feeRateBps": "0",
    "nonce": "0",
    "expiration": "0",
    "taker": "0x0000..."
  },
  "owner": "0x...",
  "orderType": "GTC"
}
```

### WebSocket Subscription
```python
# Market channel (public)
{"assets_ids": ["token_id"], "type": "market"}

# User channel (authenticated)
{"markets": ["condition_id"], "type": "user", "auth": {"apiKey": "...", "secret": "...", "passphrase": "..."}}
```

---

## Appendix B: ESPN API Reference

### Scoreboard Endpoint
```
GET https://site.web.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard
```

**Sport Mappings:**
- NBA: `basketball/nba`
- NFL: `football/nfl`
- MLB: `baseball/mlb`
- NHL: `hockey/nhl`

### Response Structure
```json
{
  "events": [{
    "id": "401547417",
    "name": "Miami Heat at Chicago Bulls",
    "shortName": "MIA @ CHI",
    "date": "2026-01-23T19:00Z",
    "status": {
      "type": {
        "state": "in",
        "completed": false
      },
      "period": 3,
      "displayClock": "4:32",
      "clock": 272
    },
    "competitions": [{
      "competitors": [{
        "homeAway": "home",
        "team": {
          "abbreviation": "CHI",
          "displayName": "Chicago Bulls"
        },
        "score": "78"
      }]
    }]
  }]
}
```

---

*End of PRD*
