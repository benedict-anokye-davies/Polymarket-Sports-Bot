# Kalshi Sports Trading Bot
## Professional Technical Specification v2.0

**Document Version:** 2.0  
**Last Updated:** January 2026  
**Classification:** Technical Specification  
**Author:** Ben Anokye-Davies

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Technology Stack Decision](#2-technology-stack-decision)
3. [System Architecture](#3-system-architecture)
4. [Security Architecture](#4-security-architecture)
5. [Database Schema](#5-database-schema)
6. [Authentication System](#6-authentication-system)
7. [Onboarding Flow](#7-onboarding-flow)
8. [Kalshi Integration](#8-kalshi-integration)
9. [Core Trading Engine](#9-core-trading-engine)
10. [API Specification](#10-api-specification)
11. [Dashboard Specification](#11-dashboard-specification)
12. [Deployment Architecture](#12-deployment-architecture)
13. [File Structure](#13-file-structure)
14. [Development Phases](#14-development-phases)
15. [Claude Code Prompts](#15-claude-code-prompts)

---

## 1. Executive Summary

### Project Overview

This document specifies a production-grade automated trading system for Kalshi prediction markets, focusing on sports betting opportunities. The system monitors live sports markets, captures pre-game baselines, executes trades based on configurable thresholds, and manages positions through their complete lifecycle.

### Client Requirements Summary

| Requirement | Description |
|-------------|-------------|
| Live Trading | Bot only enters positions on LIVE games, not pre-game |
| Baseline Tracking | Capture pre-game odds as reference point |
| Threshold Entry | Buy when odds drop X points from baseline |
| Time Filtering | Sport-specific entry/exit windows (quarters, innings, etc.) |
| Risk Management | Stop-loss, take-profit, position limits |
| Web Dashboard | Non-technical user interface, mobile-friendly |
| Alerts | Discord notifications for trades |
| 24/7 Operation | Cloud-hosted, always running |
| Security | Authentication, encrypted credentials |
| Onboarding | Guided setup for first-time users |

### Key Deliverables

1. Secure web application with authentication
2. Interactive onboarding guide
3. Kalshi account connection flow
4. Real-time trading dashboard
5. Automated trading engine
6. Sport-specific configuration system
7. Discord alert integration
8. Comprehensive documentation

---

## 2. Technology Stack Decision

### Recommended Stack: Python with FastAPI

After evaluating the requirements, Python with FastAPI is the optimal choice for the following reasons:

| Factor | Python/FastAPI | Node.js/Express | Decision |
|--------|----------------|-----------------|----------|
| Async Support | Native async/await | Native async | Tie |
| Trading Libraries | Excellent (pandas, numpy) | Limited | Python |
| Kalshi SDK | Official Python SDK available | None | Python |
| Data Processing | Superior (pandas, dataclasses) | Requires libraries | Python |
| Type Safety | Pydantic validation | TypeScript needed | Python |
| API Documentation | Auto-generated OpenAPI | Manual | Python |
| WebSocket | Native support | Native support | Tie |
| Deployment | Simple Docker | Simple Docker | Tie |
| Maintenance | Clear, readable code | Callback complexity | Python |

### Final Technology Stack

```
BACKEND
--------
Runtime:        Python 3.11+
Framework:      FastAPI 0.109+
ORM:            SQLAlchemy 2.0 (async)
Validation:     Pydantic v2
Auth:           python-jose (JWT), passlib (bcrypt)
WebSocket:      FastAPI WebSocket
Task Queue:     APScheduler (in-process) or Celery (if scaling needed)
HTTP Client:    httpx (async)

FRONTEND
--------
Framework:      HTML5 + Vanilla JavaScript (simple, no build step)
                OR React 18+ with TypeScript (if complexity grows)
Styling:        Tailwind CSS 3.4
Charts:         Chart.js or Lightweight Charts
Real-time:      Native WebSocket API

DATABASE
--------
Primary:        PostgreSQL 15+ (production)
Development:    SQLite (local testing)
Migrations:     Alembic
Connection:     asyncpg (async PostgreSQL driver)

INFRASTRUCTURE
--------------
Container:      Docker + Docker Compose
Hosting:        Google Cloud Run (GCP credits available)
SSL:            Automatic via Cloud Run
Secrets:        GCP Secret Manager or environment variables
Monitoring:     Structured logging (JSON format)

EXTERNAL SERVICES
-----------------
Trading:        Kalshi API (REST + WebSocket)
Alerts:         Discord Webhook API
```

---

## 3. System Architecture

### High-Level Architecture

```
                                    INTERNET
                                        |
                                        v
                            +-------------------+
                            |   Load Balancer   |
                            |   (Cloud Run)     |
                            +-------------------+
                                        |
                                        v
+------------------------------------------------------------------+
|                        APPLICATION SERVER                         |
|                          (FastAPI)                                |
|                                                                   |
|  +------------------+  +------------------+  +------------------+ |
|  |   Auth Module    |  |   API Routes     |  |   WebSocket      | |
|  |                  |  |                  |  |   Handler        | |
|  |  - Login         |  |  - /api/v1/*     |  |                  | |
|  |  - Register      |  |  - REST endpoints|  |  - Dashboard     | |
|  |  - JWT tokens    |  |  - CRUD ops      |  |  - Live updates  | |
|  +------------------+  +------------------+  +------------------+ |
|                                                                   |
|  +------------------+  +------------------+  +------------------+ |
|  |  Trading Engine  |  |  Market Monitor  |  |  Alert Service   | |
|  |                  |  |                  |  |                  | |
|  |  - Entry logic   |  |  - WebSocket     |  |  - Discord       | |
|  |  - Exit logic    |  |  - Polling       |  |  - Email (opt)   | |
|  |  - Position mgmt |  |  - Baseline      |  |  - In-app        | |
|  +------------------+  +------------------+  +------------------+ |
|                                                                   |
+------------------------------------------------------------------+
            |                       |                       |
            v                       v                       v
    +-------------+         +-------------+         +-------------+
    | PostgreSQL  |         | Kalshi API  |         | Discord API |
    | Database    |         | (External)  |         | (External)  |
    +-------------+         +-------------+         +-------------+
```

### Component Responsibilities

| Component | Responsibility |
|-----------|---------------|
| Auth Module | User registration, login, JWT management, session handling |
| API Routes | REST endpoints for dashboard, settings, manual trades |
| WebSocket Handler | Real-time dashboard updates, live P&L, position changes |
| Trading Engine | Entry/exit decision logic, order execution, position lifecycle |
| Market Monitor | Kalshi API connection, market data streaming, baseline capture |
| Alert Service | Discord notifications, trade alerts, daily summaries |

---

## 4. Security Architecture

### Authentication Flow

```
1. User Registration
   Client                    Server                     Database
     |                          |                           |
     |-- POST /auth/register -->|                           |
     |   {email, password}      |                           |
     |                          |-- Hash password           |
     |                          |-- (bcrypt, cost=12)       |
     |                          |                           |
     |                          |-- INSERT user ----------->|
     |                          |                           |
     |<-- 201 Created ----------|                           |
     |   {user_id, email}       |                           |

2. User Login
   Client                    Server                     Database
     |                          |                           |
     |-- POST /auth/login ----->|                           |
     |   {email, password}      |                           |
     |                          |-- SELECT user ----------->|
     |                          |<-- user data -------------|
     |                          |                           |
     |                          |-- Verify password         |
     |                          |-- (bcrypt compare)        |
     |                          |                           |
     |                          |-- Generate JWT            |
     |                          |-- (access + refresh)      |
     |                          |                           |
     |<-- 200 OK ---------------|                           |
     |   {access_token,         |                           |
     |    refresh_token}        |                           |

3. Authenticated Request
   Client                    Server                     Database
     |                          |                           |
     |-- GET /api/v1/status --->|                           |
     |   Authorization: Bearer  |                           |
     |   <access_token>         |                           |
     |                          |                           |
     |                          |-- Verify JWT              |
     |                          |-- Check expiration        |
     |                          |-- Extract user_id         |
     |                          |                           |
     |                          |-- Process request ------->|
     |                          |<-- Response --------------|
     |                          |                           |
     |<-- 200 OK ---------------|                           |
```

### Security Measures

| Measure | Implementation |
|---------|---------------|
| Password Hashing | bcrypt with cost factor 12 |
| JWT Tokens | RS256 signing, 15-minute access token, 7-day refresh token |
| HTTPS | Enforced at load balancer level (Cloud Run) |
| CORS | Strict origin policy, credentials required |
| Rate Limiting | 100 requests/minute per IP, 10 login attempts/hour |
| Input Validation | Pydantic models for all inputs |
| SQL Injection | SQLAlchemy ORM with parameterized queries |
| XSS Prevention | Content-Security-Policy headers, HTML escaping |
| Kalshi Credentials | Encrypted at rest (Fernet), never exposed to frontend |

### Credential Storage

```python
# Kalshi API credentials are encrypted before storage
# Key derivation from application secret

from cryptography.fernet import Fernet
import base64
import hashlib

def derive_key(secret: str) -> bytes:
    """Derive encryption key from application secret."""
    return base64.urlsafe_b64encode(
        hashlib.sha256(secret.encode()).digest()
    )

def encrypt_credential(plaintext: str, secret: str) -> str:
    """Encrypt sensitive credential for database storage."""
    fernet = Fernet(derive_key(secret))
    return fernet.encrypt(plaintext.encode()).decode()

def decrypt_credential(ciphertext: str, secret: str) -> str:
    """Decrypt credential when needed for API calls."""
    fernet = Fernet(derive_key(secret))
    return fernet.decrypt(ciphertext.encode()).decode()
```

---

## 5. Database Schema

### Entity Relationship Diagram

```
+------------------+       +------------------+       +------------------+
|      users       |       | kalshi_accounts  |       |  sport_configs   |
+------------------+       +------------------+       +------------------+
| id (PK)          |<---+  | id (PK)          |   +-->| id (PK)          |
| email (UNIQUE)   |    |  | user_id (FK)     |---+   | user_id (FK)     |
| password_hash    |    |  | api_key_id_enc   |       | sport            |
| created_at       |    |  | private_key_enc  |       | enabled          |
| updated_at       |    |  | is_connected     |       | min_pregame_odds |
| is_active        |    |  | last_verified    |       | entry_threshold  |
| onboarding_done  |    |  | created_at       |       | take_profit      |
+------------------+    |  +------------------+       | stop_loss        |
         |              |                             | max_entry_seg    |
         |              +-----------------------------| position_size    |
         |                                            | created_at       |
         |                                            +------------------+
         |
         |              +------------------+       +------------------+
         |              |  tracked_games   |       |    positions     |
         |              +------------------+       +------------------+
         |          +-->| id (PK)          |<--+   | id (PK)          |
         |          |   | user_id (FK)     |   |   | user_id (FK)     |
         |          |   | market_id        |   +---| game_id (FK)     |
         +----------+   | sport            |       | market_id        |
                    |   | event_title      |       | side             |
                    |   | team_a           |       | entry_price      |
                    |   | team_b           |       | entry_quantity   |
                    |   | start_time       |       | exit_price       |
                    |   | pregame_odds_a   |       | exit_reason      |
                    |   | current_odds_a   |       | realized_pnl     |
                    |   | current_segment  |       | status           |
                    |   | is_live          |       | opened_at        |
                    |   | is_finished      |       | closed_at        |
                    |   +------------------+       +------------------+
                    |
                    |   +------------------+       +------------------+
                    |   |     trades       |       |  activity_log    |
                    |   +------------------+       +------------------+
                    +-->| id (PK)          |       | id (PK)          |
                        | user_id (FK)     |       | user_id (FK)     |
                        | position_id (FK) |       | level            |
                        | order_id         |       | category         |
                        | action           |       | message          |
                        | side             |       | details (JSON)   |
                        | price            |       | created_at       |
                        | quantity         |       +------------------+
                        | executed_at      |
                        +------------------+

+------------------+
| global_settings  |
+------------------+
| id (PK)          |
| user_id (FK)     |
| bot_enabled      |
| dry_run_mode     |
| max_daily_loss   |
| max_exposure     |
| discord_webhook  |
| alerts_enabled   |
| updated_at       |
+------------------+
```

### SQL Schema Definition

```sql
-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    onboarding_completed BOOLEAN DEFAULT false,
    onboarding_step INTEGER DEFAULT 0
);

-- Kalshi account credentials (encrypted)
CREATE TABLE kalshi_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    api_key_id_encrypted VARCHAR(500),
    private_key_encrypted TEXT,
    environment VARCHAR(20) DEFAULT 'demo',  -- 'demo' or 'prod'
    is_connected BOOLEAN DEFAULT false,
    last_verified_at TIMESTAMP WITH TIME ZONE,
    account_balance DECIMAL(12, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Sport-specific configurations
CREATE TABLE sport_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    sport VARCHAR(50) NOT NULL,  -- 'nba', 'nfl', 'mlb', 'nhl', 'soccer'
    enabled BOOLEAN DEFAULT true,
    
    -- Entry parameters
    min_pregame_odds DECIMAL(5, 2) DEFAULT 55.00,
    entry_threshold_drop DECIMAL(5, 2) DEFAULT 15.00,
    entry_threshold_absolute DECIMAL(5, 2) DEFAULT 50.00,
    max_entry_segment VARCHAR(50) DEFAULT '3rd_quarter',
    min_time_remaining_seconds INTEGER DEFAULT 300,
    
    -- Exit parameters
    take_profit DECIMAL(5, 2) DEFAULT 20.00,
    stop_loss DECIMAL(5, 2) DEFAULT 10.00,
    exit_before_segment VARCHAR(50) DEFAULT '4th_quarter_2min',
    
    -- Position sizing
    position_size_dollars DECIMAL(10, 2) DEFAULT 50.00,
    max_positions_per_game INTEGER DEFAULT 1,
    max_total_positions INTEGER DEFAULT 5,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(user_id, sport)
);

-- Global settings
CREATE TABLE global_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    bot_enabled BOOLEAN DEFAULT false,
    dry_run_mode BOOLEAN DEFAULT true,
    max_daily_loss DECIMAL(10, 2) DEFAULT 500.00,
    max_portfolio_exposure DECIMAL(10, 2) DEFAULT 2000.00,
    discord_webhook_url VARCHAR(500),
    discord_alerts_enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tracked games
CREATE TABLE tracked_games (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    market_id VARCHAR(100) NOT NULL,
    sport VARCHAR(50) NOT NULL,
    event_title VARCHAR(255) NOT NULL,
    team_a VARCHAR(100),
    team_b VARCHAR(100),
    
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    current_segment VARCHAR(50),
    time_remaining_seconds INTEGER,
    is_live BOOLEAN DEFAULT false,
    is_finished BOOLEAN DEFAULT false,
    
    pregame_odds_a DECIMAL(5, 2),
    pregame_odds_b DECIMAL(5, 2),
    current_odds_a DECIMAL(5, 2),
    current_odds_b DECIMAL(5, 2),
    pregame_captured_at TIMESTAMP WITH TIME ZONE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(user_id, market_id)
);

-- Positions
CREATE TABLE positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    game_id UUID REFERENCES tracked_games(id),
    market_id VARCHAR(100) NOT NULL,
    
    side VARCHAR(10) NOT NULL,  -- 'yes' or 'no'
    team VARCHAR(100),
    entry_price DECIMAL(5, 2) NOT NULL,
    entry_quantity INTEGER NOT NULL,
    entry_cost DECIMAL(10, 2) NOT NULL,
    
    exit_price DECIMAL(5, 2),
    exit_quantity INTEGER,
    exit_proceeds DECIMAL(10, 2),
    exit_reason VARCHAR(50),  -- 'take_profit', 'stop_loss', 'time_exit', 'manual'
    
    realized_pnl DECIMAL(10, 2),
    status VARCHAR(20) DEFAULT 'open',  -- 'open', 'closed', 'pending'
    
    opened_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP WITH TIME ZONE
);

-- Individual trades
CREATE TABLE trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    position_id UUID REFERENCES positions(id),
    kalshi_order_id VARCHAR(100),
    
    action VARCHAR(10) NOT NULL,  -- 'buy' or 'sell'
    side VARCHAR(10) NOT NULL,
    price DECIMAL(5, 2) NOT NULL,
    quantity INTEGER NOT NULL,
    total DECIMAL(10, 2) NOT NULL,
    fees DECIMAL(10, 2) DEFAULT 0,
    
    is_dry_run BOOLEAN DEFAULT false,
    executed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Activity log
CREATE TABLE activity_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    level VARCHAR(20) DEFAULT 'info',  -- 'debug', 'info', 'warning', 'error'
    category VARCHAR(50),  -- 'system', 'trade', 'config', 'alert', 'auth'
    message TEXT NOT NULL,
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_positions_user_status ON positions(user_id, status);
CREATE INDEX idx_tracked_games_user_live ON tracked_games(user_id, is_live);
CREATE INDEX idx_trades_user_date ON trades(user_id, executed_at);
CREATE INDEX idx_activity_log_user_date ON activity_log(user_id, created_at);
```

---

## 6. Authentication System

### JWT Token Structure

```python
# Access Token Payload
{
    "sub": "user_uuid",           # Subject (user ID)
    "email": "user@example.com",
    "type": "access",
    "iat": 1706000000,            # Issued at
    "exp": 1706000900,            # Expires (15 minutes)
    "jti": "unique_token_id"      # JWT ID for revocation
}

# Refresh Token Payload
{
    "sub": "user_uuid",
    "type": "refresh",
    "iat": 1706000000,
    "exp": 1706604800,            # Expires (7 days)
    "jti": "unique_token_id"
}
```

### Authentication Endpoints

| Endpoint | Method | Description | Auth Required |
|----------|--------|-------------|---------------|
| /auth/register | POST | Create new user account | No |
| /auth/login | POST | Authenticate and get tokens | No |
| /auth/refresh | POST | Refresh access token | Refresh token |
| /auth/logout | POST | Invalidate tokens | Yes |
| /auth/me | GET | Get current user info | Yes |
| /auth/change-password | POST | Update password | Yes |

### Request/Response Examples

```python
# POST /auth/register
# Request
{
    "email": "jay@example.com",
    "password": "SecurePassword123!",
    "confirm_password": "SecurePassword123!"
}

# Response (201 Created)
{
    "id": "uuid",
    "email": "jay@example.com",
    "created_at": "2026-01-23T12:00:00Z",
    "onboarding_completed": false
}

# POST /auth/login
# Request
{
    "email": "jay@example.com",
    "password": "SecurePassword123!"
}

# Response (200 OK)
{
    "access_token": "eyJhbGciOiJSUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJSUzI1NiIs...",
    "token_type": "bearer",
    "expires_in": 900,
    "user": {
        "id": "uuid",
        "email": "jay@example.com",
        "onboarding_completed": false
    }
}
```

---

## 7. Onboarding Flow

### Onboarding Steps

The onboarding process guides new users through setup in a structured sequence:

```
Step 0: Registration Complete
         |
         v
Step 1: Welcome Screen
        - Introduction to the bot
        - Overview of features
        - What to expect
         |
         v
Step 2: How It Works
        - Explanation of baseline tracking
        - Threshold-based trading
        - Risk management overview
         |
         v
Step 3: Connect Kalshi Account
        - Instructions to get API keys from Kalshi
        - Input API Key ID
        - Upload/paste private key
        - Test connection
         |
         v
Step 4: Choose Environment
        - Demo mode (paper trading)
        - Live mode (real money)
        - Recommendation: Start with demo
         |
         v
Step 5: Configure First Sport
        - Select primary sport (NBA, NFL, etc.)
        - Set basic parameters
        - Use recommended defaults
         |
         v
Step 6: Risk Settings
        - Set daily loss limit
        - Set maximum exposure
        - Position size defaults
         |
         v
Step 7: Discord Alerts (Optional)
        - Instructions to create webhook
        - Input webhook URL
        - Test notification
         |
         v
Step 8: Review and Launch
        - Summary of all settings
        - Confirm understanding
        - Enable bot (starts in dry run)
         |
         v
Step 9: Dashboard Tour
        - Interactive walkthrough
        - Highlight key features
        - How to access help
         |
         v
Onboarding Complete
```

### Onboarding API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| /api/v1/onboarding/status | GET | Get current onboarding step |
| /api/v1/onboarding/step/{n} | POST | Complete step n |
| /api/v1/onboarding/skip | POST | Skip to dashboard (not recommended) |
| /api/v1/onboarding/reset | POST | Restart onboarding |

### Onboarding Data Model

```python
class OnboardingStatus(BaseModel):
    current_step: int
    total_steps: int
    completed_steps: list[int]
    can_skip: bool
    steps: list[OnboardingStep]

class OnboardingStep(BaseModel):
    step_number: int
    title: str
    description: str
    is_completed: bool
    is_current: bool
    requires_action: bool  # True if user must input something
```

### Step 3: Kalshi Account Connection Flow

```
User Interface                          Server
      |                                    |
      |  1. Display instructions           |
      |     - Link to Kalshi API docs      |
      |     - How to generate keys         |
      |                                    |
      |  2. User enters API Key ID         |
      |------------------------------------>
      |                                    |
      |  3. User uploads private key       |
      |     (PEM file or paste text)       |
      |------------------------------------>
      |                                    |
      |                                    | 4. Validate key format
      |                                    |
      |                                    | 5. Encrypt credentials
      |                                    |
      |                                    | 6. Store in database
      |                                    |
      |                                    | 7. Test API connection
      |                                    |    - Call Kalshi /portfolio/balance
      |                                    |
      |  8. Display result                 |
      |<------------------------------------
      |     - Success: Show balance        |
      |     - Failure: Show error message  |
      |                                    |
      |  9. Mark step complete             |
      |------------------------------------>
```

---

## 8. Kalshi Integration

### API Client Architecture

```python
class KalshiClient:
    """
    Async client for Kalshi API with RSA authentication.
    
    Endpoints used:
    - GET  /portfolio/balance      - Account balance
    - GET  /markets                - List markets
    - GET  /markets/{ticker}       - Single market
    - GET  /markets/{ticker}/orderbook - Order book
    - POST /portfolio/orders       - Place order
    - GET  /portfolio/orders       - List orders
    - DELETE /portfolio/orders/{id} - Cancel order
    - GET  /portfolio/positions    - Current positions
    """
    
    def __init__(
        self,
        api_key_id: str,
        private_key: str,
        environment: str = "demo"  # "demo" or "prod"
    ):
        self.api_key_id = api_key_id
        self.private_key = private_key
        self.base_url = self._get_base_url(environment)
        
    def _get_base_url(self, env: str) -> str:
        if env == "demo":
            return "https://demo-api.kalshi.co/trade-api/v2"
        return "https://api.kalshi.co/trade-api/v2"
    
    async def _sign_request(
        self,
        method: str,
        path: str,
        timestamp: int
    ) -> str:
        """Generate RSA signature for request."""
        # Implementation per Kalshi docs
        pass
    
    async def get_balance(self) -> dict:
        """Get account balance."""
        pass
    
    async def get_sports_markets(self, sport: str = None) -> list:
        """Get all sports markets, optionally filtered by sport."""
        pass
    
    async def get_market(self, ticker: str) -> dict:
        """Get single market details."""
        pass
    
    async def place_order(
        self,
        ticker: str,
        side: str,      # "yes" or "no"
        action: str,    # "buy" or "sell"
        count: int,
        price: int      # In cents (1-99)
    ) -> dict:
        """Place a new order."""
        pass
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order."""
        pass
    
    async def get_positions(self) -> list:
        """Get all current positions."""
        pass
```

### Market Data Structure (Expected from Kalshi)

```python
class KalshiMarket(BaseModel):
    """Market data from Kalshi API."""
    ticker: str                    # e.g., "KXNBA-MIA-CHI-25JAN23"
    title: str                     # e.g., "Miami Heat vs Chicago Bulls"
    subtitle: str                  # Additional context
    status: str                    # "open", "closed", "settled"
    category: str                  # "sports"
    sub_category: str              # "nba", "nfl", etc.
    
    yes_bid: int                   # Best bid for YES (cents)
    yes_ask: int                   # Best ask for YES (cents)
    no_bid: int                    # Best bid for NO (cents)
    no_ask: int                    # Best ask for NO (cents)
    
    last_price: int                # Last traded price
    volume: int                    # 24h volume
    
    open_time: datetime            # When market opened
    close_time: datetime           # When market closes
    expiration_time: datetime      # Settlement time
    
    # Sports-specific fields (may need parsing)
    event_start_time: datetime     # Game start time
    rules_primary: str             # Market rules/description
```

### WebSocket Subscription (if available)

```python
class KalshiWebSocket:
    """WebSocket client for real-time market updates."""
    
    async def connect(self):
        """Establish WebSocket connection."""
        pass
    
    async def subscribe_market(self, ticker: str):
        """Subscribe to updates for a specific market."""
        pass
    
    async def subscribe_portfolio(self):
        """Subscribe to portfolio/position updates."""
        pass
    
    async def on_message(self, handler: Callable):
        """Register message handler."""
        pass
```

---

## 9. Core Trading Engine

### Trading Loop Architecture

```python
class TradingEngine:
    """
    Main trading engine that orchestrates all trading operations.
    
    Runs as a background task, executing the following loop:
    1. Fetch active sports markets
    2. For each market:
       a. If PREGAME: Track baseline
       b. If LIVE: Check entry/exit conditions
       c. If FINISHED: Close any remaining positions
    3. Update dashboard via WebSocket
    4. Sleep and repeat
    """
    
    def __init__(
        self,
        user_id: str,
        kalshi_client: KalshiClient,
        db_session: AsyncSession,
        websocket_manager: WebSocketManager,
        config: TradingConfig
    ):
        self.user_id = user_id
        self.kalshi = kalshi_client
        self.db = db_session
        self.ws = websocket_manager
        self.config = config
        self.is_running = False
        
    async def start(self):
        """Start the trading loop."""
        self.is_running = True
        while self.is_running:
            try:
                await self._trading_cycle()
            except Exception as e:
                await self._handle_error(e)
            await asyncio.sleep(self.config.poll_interval)
    
    async def stop(self):
        """Stop the trading loop gracefully."""
        self.is_running = False
        
    async def _trading_cycle(self):
        """Execute one cycle of the trading loop."""
        # 1. Check if bot is enabled
        settings = await self._get_settings()
        if not settings.bot_enabled:
            return
            
        # 2. Check daily loss limit
        if await self._daily_loss_exceeded():
            await self._disable_bot("Daily loss limit reached")
            return
            
        # 3. Fetch sports markets
        markets = await self.kalshi.get_sports_markets()
        
        # 4. Process each market
        for market in markets:
            await self._process_market(market, settings)
            
        # 5. Check existing positions for exits
        await self._check_exit_conditions()
        
        # 6. Send dashboard update
        await self._broadcast_status()
```

### Entry Logic

```python
async def _check_entry_conditions(
    self,
    market: KalshiMarket,
    game: TrackedGame,
    config: SportConfig
) -> tuple[bool, str]:
    """
    Evaluate whether to enter a position.
    
    Returns:
        (should_enter, reason)
    """
    # 1. Check if already have position
    if await self._has_position(market.ticker):
        return False, "Already have position in this market"
    
    # 2. Check max positions limit
    open_positions = await self._count_open_positions()
    if open_positions >= config.max_total_positions:
        return False, f"At max positions ({config.max_total_positions})"
    
    # 3. Check game segment
    current_segment = self._parse_segment(market)
    if self._is_past_entry_window(current_segment, config.max_entry_segment):
        return False, f"Past entry window: {current_segment}"
    
    # 4. Check time remaining
    time_remaining = self._get_time_remaining(market)
    if time_remaining < config.min_time_remaining_seconds:
        return False, f"Insufficient time: {time_remaining}s"
    
    # 5. Check baseline exists
    if not game.pregame_odds_a:
        return False, "No pregame baseline captured"
    
    # 6. Check threshold conditions
    pregame = game.pregame_odds_a
    current = market.yes_bid  # Current odds for favorite
    drop = pregame - current
    
    # Entry condition: Odds dropped enough from pregame
    if drop >= config.entry_threshold_drop:
        return True, f"Threshold met: dropped {drop} points"
    
    # Alternative: Absolute threshold
    if current <= config.entry_threshold_absolute:
        return True, f"Absolute threshold met: {current}"
    
    return False, "No entry conditions met"
```

### Exit Logic

```python
async def _check_exit_conditions(
    self,
    position: Position,
    market: KalshiMarket,
    config: SportConfig
) -> tuple[bool, str, str]:
    """
    Evaluate whether to exit a position.
    
    Returns:
        (should_exit, reason, exit_type)
    """
    current_price = market.yes_bid
    entry_price = position.entry_price
    pnl_points = current_price - entry_price
    
    # 1. Take profit
    if pnl_points >= config.take_profit:
        return True, f"Take profit: +{pnl_points} points", "take_profit"
    
    # 2. Stop loss
    if pnl_points <= -config.stop_loss:
        return True, f"Stop loss: {pnl_points} points", "stop_loss"
    
    # 3. Time-based exit
    current_segment = self._parse_segment(market)
    if self._should_exit_by_time(current_segment, config.exit_before_segment):
        return True, f"Time exit: {current_segment}", "time_exit"
    
    # 4. Game finished
    if market.status == "closed" or market.status == "settled":
        return True, "Game finished", "game_finished"
    
    return False, "Holding position", None
```

### Order Execution

```python
async def _execute_entry(
    self,
    market: KalshiMarket,
    config: SportConfig,
    reason: str
) -> Position:
    """Execute a buy order and create position record."""
    
    settings = await self._get_settings()
    
    # Calculate position size
    price_cents = market.yes_ask  # Buy at ask
    dollars = config.position_size_dollars
    quantity = int((dollars * 100) / price_cents)
    
    # Check risk limits
    current_exposure = await self._get_total_exposure()
    if current_exposure + dollars > settings.max_portfolio_exposure:
        raise RiskLimitError("Would exceed portfolio exposure limit")
    
    # Execute order (or simulate)
    if settings.dry_run_mode:
        order_id = f"DRY_{uuid4()}"
        await self._log("trade", f"[DRY RUN] Buy {quantity} @ {price_cents}")
    else:
        order = await self.kalshi.place_order(
            ticker=market.ticker,
            side="yes",
            action="buy",
            count=quantity,
            price=price_cents
        )
        order_id = order["order_id"]
    
    # Create position record
    position = await self._create_position(
        market=market,
        side="yes",
        entry_price=price_cents,
        quantity=quantity,
        order_id=order_id,
        is_dry_run=settings.dry_run_mode
    )
    
    # Send alert
    await self._send_alert("entry", position, market, reason)
    
    return position
```

---

## 10. API Specification

### REST API Endpoints

#### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /auth/register | Create new account |
| POST | /auth/login | Authenticate user |
| POST | /auth/refresh | Refresh access token |
| POST | /auth/logout | Invalidate session |
| GET | /auth/me | Get current user |

#### Onboarding

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/onboarding/status | Get onboarding progress |
| POST | /api/v1/onboarding/step/{n}/complete | Mark step complete |
| POST | /api/v1/onboarding/kalshi/connect | Connect Kalshi account |
| POST | /api/v1/onboarding/kalshi/test | Test Kalshi connection |

#### Dashboard

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/status | Bot status summary |
| GET | /api/v1/positions | All open positions |
| GET | /api/v1/positions/history | Closed positions |
| GET | /api/v1/games/tracked | Tracked games |
| GET | /api/v1/games/live | Live games only |

#### Settings

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/settings | Global settings |
| PUT | /api/v1/settings | Update global settings |
| GET | /api/v1/settings/sports | All sport configs |
| GET | /api/v1/settings/sports/{sport} | Single sport config |
| PUT | /api/v1/settings/sports/{sport} | Update sport config |

#### Manual Trading

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/markets | Available markets |
| POST | /api/v1/orders | Place manual order |
| DELETE | /api/v1/positions/{id} | Close position |
| POST | /api/v1/positions/close-all | Close all positions |

#### Bot Control

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/bot/start | Start trading |
| POST | /api/v1/bot/stop | Stop trading |
| POST | /api/v1/bot/pause | Pause (keep positions) |
| POST | /api/v1/bot/resume | Resume trading |

#### Analytics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/stats/daily | Today's statistics |
| GET | /api/v1/stats/weekly | This week's stats |
| GET | /api/v1/stats/monthly | This month's stats |
| GET | /api/v1/logs | Activity logs |

### WebSocket Endpoint

```
WS /ws

Connection requires JWT token in query parameter:
ws://host/ws?token=<access_token>

Server-sent events:
- status_update: Bot status changes
- position_update: Position P&L updates
- new_trade: Trade executed
- game_update: Market data changes
- log: Activity log entry
- alert: Important notification
```

---

## 11. Dashboard Specification

### Page Structure

```
/                       - Login page (if not authenticated)
/register               - Registration page
/onboarding             - Onboarding flow (steps 1-9)
/dashboard              - Main dashboard (requires auth)
/dashboard/settings     - Global settings
/dashboard/sports       - Sport configurations
/dashboard/history      - Trade history
/dashboard/manual       - Manual trading
/dashboard/logs         - Activity logs
```

### Main Dashboard Layout

```
+------------------------------------------------------------------------+
|  KALSHI SPORTS BOT                                    [User] [Logout]  |
+------------------------------------------------------------------------+
|                                                                         |
|  +------------------+  +------------------+  +------------------+       |
|  |   BOT STATUS     |  |   TODAY'S P&L    |  |  OPEN POSITIONS  |       |
|  |   [Running]      |  |   +$127.50       |  |       4          |       |
|  |   Mode: Live     |  |   5W / 2L        |  |   $200 at risk   |       |
|  +------------------+  +------------------+  +------------------+       |
|                                                                         |
|  +------------------------------------------------------------------+  |
|  | OPEN POSITIONS                                       [Close All] |  |
|  +------------------------------------------------------------------+  |
|  | Game             | Entry | Current | P&L     | Time    | Action  |  |
|  +-----------------+-------+---------+---------+---------+---------+  |
|  | Miami v Chicago  | 50c   | 62c     | +$12.00 | Q3 4:21 | [Close] |  |
|  | Lakers v Celtics | 45c   | 48c     | +$3.00  | Q2 8:15 | [Close] |  |
|  +------------------------------------------------------------------+  |
|                                                                         |
|  +------------------------------------------------------------------+  |
|  | TRACKED GAMES (Pregame)                                          |  |
|  +------------------------------------------------------------------+  |
|  | Game             | Pregame | Starts In | Status                  |  |
|  +-----------------+---------+-----------+-------------------------+  |
|  | Warriors v Suns  | 65%     | 45 min    | Tracking                |  |
|  +------------------------------------------------------------------+  |
|                                                                         |
|  +------------------------------------------------------------------+  |
|  | ACTIVITY LOG                                                     |  |
|  +------------------------------------------------------------------+  |
|  | 14:32:05  Bought Miami YES @ 50c (100 contracts)                 |  |
|  | 14:31:22  Entry signal: Miami dropped to 50%                     |  |
|  | 14:30:01  Game live: Miami vs Chicago                            |  |
|  +------------------------------------------------------------------+  |
|                                                                         |
+------------------------------------------------------------------------+
```

### Settings Page

```
+------------------------------------------------------------------------+
|  SETTINGS                                                               |
+------------------------------------------------------------------------+
|                                                                         |
|  BOT CONTROL                                                            |
|  +------------------------------------------------------------------+  |
|  | Bot Enabled      [=====ON=====]                                  |  |
|  | Dry Run Mode     [=====ON=====]  (No real trades)                |  |
|  +------------------------------------------------------------------+  |
|                                                                         |
|  RISK LIMITS                                                            |
|  +------------------------------------------------------------------+  |
|  | Max Daily Loss        [$___500___]                               |  |
|  | Max Portfolio Exposure [$__2000___]                              |  |
|  +------------------------------------------------------------------+  |
|                                                                         |
|  KALSHI ACCOUNT                                                         |
|  +------------------------------------------------------------------+  |
|  | Status: Connected                                                |  |
|  | Environment: Demo                                                |  |
|  | Balance: $1,245.00                         [Test Connection]     |  |
|  +------------------------------------------------------------------+  |
|                                                                         |
|  DISCORD ALERTS                                                         |
|  +------------------------------------------------------------------+  |
|  | Alerts Enabled   [=====ON=====]                                  |  |
|  | Webhook URL      [https://discord.com/api/webhooks/...]          |  |
|  |                                              [Test Webhook]      |  |
|  +------------------------------------------------------------------+  |
|                                                                         |
|                                                    [Save Changes]       |
+------------------------------------------------------------------------+
```

---

## 12. Deployment Architecture

### GCP Cloud Run Deployment

```
                         INTERNET
                             |
                             v
                    +----------------+
                    | Cloud DNS      |
                    | bot.domain.com |
                    +----------------+
                             |
                             v
                    +----------------+
                    | Cloud Load     |
                    | Balancer       |
                    | (HTTPS/SSL)    |
                    +----------------+
                             |
                             v
                    +----------------+
                    | Cloud Run      |
                    | Service        |
                    | (Auto-scaling) |
                    +----------------+
                             |
              +--------------+--------------+
              |                             |
              v                             v
     +----------------+            +----------------+
     | Cloud SQL      |            | Secret Manager |
     | (PostgreSQL)   |            | (Credentials)  |
     +----------------+            +----------------+
```

### Docker Configuration

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

```yaml
# docker-compose.yml (for local development)
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8080:8080"
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/kalshi_bot
      - SECRET_KEY=${SECRET_KEY}
      - KALSHI_ENV=demo
    depends_on:
      - db
    volumes:
      - ./src:/app/src  # Hot reload in development

  db:
    image: postgres:15
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=kalshi_bot
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

### Environment Variables

```bash
# .env.example

# Application
SECRET_KEY=your-secret-key-min-32-chars
DEBUG=false
LOG_LEVEL=INFO

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/kalshi_bot

# JWT
JWT_SECRET_KEY=your-jwt-secret-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# Kalshi (default environment)
KALSHI_DEFAULT_ENV=demo

# Encryption (for storing Kalshi credentials)
ENCRYPTION_KEY=your-fernet-key

# Discord (optional, can be set per user)
DISCORD_DEFAULT_WEBHOOK=

# Server
HOST=0.0.0.0
PORT=8080
```

---

## 13. File Structure

```
kalshi-sports-bot/
|
|-- src/
|   |-- __init__.py
|   |-- main.py                      # FastAPI application entry
|   |-- config.py                    # Configuration management
|   |
|   |-- api/
|   |   |-- __init__.py
|   |   |-- deps.py                  # Dependency injection
|   |   |-- routes/
|   |   |   |-- __init__.py
|   |   |   |-- auth.py              # Authentication endpoints
|   |   |   |-- onboarding.py        # Onboarding endpoints
|   |   |   |-- dashboard.py         # Dashboard data endpoints
|   |   |   |-- settings.py          # Settings endpoints
|   |   |   |-- trading.py           # Manual trading endpoints
|   |   |   |-- bot.py               # Bot control endpoints
|   |   |   |-- stats.py             # Statistics endpoints
|   |   |-- websocket.py             # WebSocket handler
|   |
|   |-- core/
|   |   |-- __init__.py
|   |   |-- security.py              # Password hashing, JWT
|   |   |-- encryption.py            # Credential encryption
|   |   |-- exceptions.py            # Custom exceptions
|   |
|   |-- services/
|   |   |-- __init__.py
|   |   |-- auth_service.py          # Authentication logic
|   |   |-- kalshi_service.py        # Kalshi API wrapper
|   |   |-- trading_engine.py        # Main trading logic
|   |   |-- market_monitor.py        # Market data monitoring
|   |   |-- position_manager.py      # Position management
|   |   |-- alert_service.py         # Discord notifications
|   |   |-- stats_service.py         # Statistics calculations
|   |
|   |-- models/
|   |   |-- __init__.py
|   |   |-- user.py                  # User model
|   |   |-- kalshi_account.py        # Kalshi credentials model
|   |   |-- sport_config.py          # Sport configuration model
|   |   |-- game.py                  # Tracked game model
|   |   |-- position.py              # Position model
|   |   |-- trade.py                 # Trade model
|   |   |-- settings.py              # Global settings model
|   |   |-- activity_log.py          # Activity log model
|   |
|   |-- schemas/
|   |   |-- __init__.py
|   |   |-- auth.py                  # Auth request/response schemas
|   |   |-- onboarding.py            # Onboarding schemas
|   |   |-- dashboard.py             # Dashboard schemas
|   |   |-- settings.py              # Settings schemas
|   |   |-- trading.py               # Trading schemas
|   |
|   |-- db/
|   |   |-- __init__.py
|   |   |-- database.py              # Database connection
|   |   |-- crud/
|   |   |   |-- __init__.py
|   |   |   |-- user.py              # User CRUD operations
|   |   |   |-- kalshi_account.py    # Kalshi account CRUD
|   |   |   |-- sport_config.py      # Sport config CRUD
|   |   |   |-- position.py          # Position CRUD
|   |   |   |-- game.py              # Game CRUD
|   |
|   |-- templates/                   # Jinja2 HTML templates
|   |   |-- base.html
|   |   |-- auth/
|   |   |   |-- login.html
|   |   |   |-- register.html
|   |   |-- onboarding/
|   |   |   |-- layout.html
|   |   |   |-- step1_welcome.html
|   |   |   |-- step2_how_it_works.html
|   |   |   |-- step3_connect_kalshi.html
|   |   |   |-- step4_environment.html
|   |   |   |-- step5_first_sport.html
|   |   |   |-- step6_risk_settings.html
|   |   |   |-- step7_discord.html
|   |   |   |-- step8_review.html
|   |   |   |-- step9_tour.html
|   |   |-- dashboard/
|   |   |   |-- layout.html
|   |   |   |-- index.html
|   |   |   |-- settings.html
|   |   |   |-- sports.html
|   |   |   |-- history.html
|   |   |   |-- manual.html
|   |   |   |-- logs.html
|   |
|   |-- static/
|   |   |-- css/
|   |   |   |-- main.css             # Tailwind compiled
|   |   |-- js/
|   |   |   |-- dashboard.js         # Dashboard logic
|   |   |   |-- websocket.js         # WebSocket client
|   |   |   |-- onboarding.js        # Onboarding logic
|   |   |   |-- settings.js          # Settings forms
|   |   |-- img/
|   |       |-- logo.svg
|
|-- alembic/                         # Database migrations
|   |-- versions/
|   |-- env.py
|   |-- alembic.ini
|
|-- tests/
|   |-- __init__.py
|   |-- conftest.py                  # Test fixtures
|   |-- test_auth.py
|   |-- test_trading_engine.py
|   |-- test_kalshi_client.py
|
|-- docs/
|   |-- USER_GUIDE.md                # End-user documentation
|   |-- SETUP.md                     # Setup instructions
|   |-- API.md                       # API documentation
|   |-- DEPLOYMENT.md                # Deployment guide
|
|-- .env.example
|-- .gitignore
|-- Dockerfile
|-- docker-compose.yml
|-- requirements.txt
|-- pyproject.toml
|-- README.md
```

---

## 14. Development Phases

### Phase 1: Foundation (Days 1-3)

| Task | Description | Deliverable |
|------|-------------|-------------|
| 1.1 | Project setup | Git repo, virtual environment, dependencies |
| 1.2 | Database setup | PostgreSQL/SQLite, SQLAlchemy models, Alembic |
| 1.3 | FastAPI skeleton | Basic app structure, health endpoint |
| 1.4 | Authentication | Registration, login, JWT tokens |
| 1.5 | Security | Password hashing, credential encryption |

**Completion Criteria:** User can register, login, and access protected endpoints.

### Phase 2: Onboarding and Kalshi (Days 4-6)

| Task | Description | Deliverable |
|------|-------------|-------------|
| 2.1 | Onboarding UI | HTML templates for all 9 steps |
| 2.2 | Onboarding API | Endpoints to track/complete steps |
| 2.3 | Kalshi client | API wrapper with RSA auth |
| 2.4 | Connection flow | Store encrypted credentials, test connection |
| 2.5 | Sport configs | Default configurations, CRUD endpoints |

**Completion Criteria:** User can complete onboarding, connect Kalshi account, and configure sports.

### Phase 3: Trading Engine (Days 7-10)

| Task | Description | Deliverable |
|------|-------------|-------------|
| 3.1 | Market monitor | Fetch sports markets, parse data |
| 3.2 | Baseline tracker | Capture pregame odds |
| 3.3 | Entry logic | Threshold evaluation, order placement |
| 3.4 | Exit logic | Take profit, stop loss, time exits |
| 3.5 | Position manager | Track positions, calculate P&L |
| 3.6 | Dry run mode | Simulate trades without real orders |

**Completion Criteria:** Bot can monitor markets, enter positions based on thresholds, and exit based on conditions (in dry run mode).

### Phase 4: Dashboard (Days 11-13)

| Task | Description | Deliverable |
|------|-------------|-------------|
| 4.1 | Dashboard layout | Main page, navigation, responsive |
| 4.2 | Status display | Bot status, P&L, positions |
| 4.3 | Settings pages | Global settings, sport configs |
| 4.4 | WebSocket | Real-time updates to dashboard |
| 4.5 | Manual trading | View markets, place orders |
| 4.6 | History and logs | Trade history, activity log |

**Completion Criteria:** Functional dashboard showing all data with real-time updates.

### Phase 5: Alerts and Polish (Days 14-15)

| Task | Description | Deliverable |
|------|-------------|-------------|
| 5.1 | Discord alerts | Entry/exit/daily summary notifications |
| 5.2 | Error handling | Graceful failures, user-friendly errors |
| 5.3 | Input validation | Comprehensive Pydantic validation |
| 5.4 | Mobile responsive | Dashboard works on phone |
| 5.5 | Loading states | Spinners, disabled buttons |

**Completion Criteria:** Professional UI with alerts and proper error handling.

### Phase 6: Deployment and Documentation (Days 16-18)

| Task | Description | Deliverable |
|------|-------------|-------------|
| 6.1 | Docker setup | Dockerfile, docker-compose |
| 6.2 | GCP deployment | Cloud Run, Cloud SQL |
| 6.3 | SSL/Domain | HTTPS, custom domain (optional) |
| 6.4 | User guide | Complete end-user documentation |
| 6.5 | Final testing | End-to-end testing with client |

**Completion Criteria:** Production deployment, documentation complete, client walkthrough done.

---

## 15. Claude Code Prompts

Use these prompts sequentially with Claude Code to build the project.

### Prompt 1: Project Setup

```
I'm building a Kalshi sports trading bot. Here's the technical specification:
[Paste relevant sections from this document]

Let's start with Phase 1: Foundation

1. Create the project structure as specified in section 13
2. Set up Python virtual environment with these dependencies:
   - fastapi
   - uvicorn[standard]
   - sqlalchemy[asyncio]
   - asyncpg
   - pydantic
   - pydantic-settings
   - python-jose[cryptography]
   - passlib[bcrypt]
   - httpx
   - python-multipart
   - jinja2
   - alembic

3. Create the basic FastAPI application in src/main.py with:
   - CORS middleware
   - Static files serving
   - Template rendering
   - Health check endpoint

4. Set up the configuration in src/config.py using pydantic-settings

Let's build this incrementally. Start with the project structure and requirements.txt.
```

### Prompt 2: Database Models

```
Now let's set up the database layer.

Using the schema from section 5 of the spec, create:

1. src/db/database.py - Async SQLAlchemy setup with session management
2. All models in src/models/ matching the SQL schema:
   - User model
   - KalshiAccount model
   - SportConfig model
   - GlobalSettings model
   - TrackedGame model
   - Position model
   - Trade model
   - ActivityLog model

3. Set up Alembic for migrations

Use SQLAlchemy 2.0 async patterns with proper type hints.
Include relationships between models.
```

### Prompt 3: Authentication

```
Implement the authentication system as specified in sections 4 and 6.

Create:
1. src/core/security.py - Password hashing (bcrypt), JWT creation/verification
2. src/core/encryption.py - Credential encryption for Kalshi keys
3. src/schemas/auth.py - Pydantic schemas for auth requests/responses
4. src/services/auth_service.py - Business logic for auth
5. src/api/routes/auth.py - Auth endpoints:
   - POST /auth/register
   - POST /auth/login
   - POST /auth/refresh
   - POST /auth/logout
   - GET /auth/me

Include proper error handling and validation.
```

### Prompt 4: Onboarding System

```
Build the onboarding flow as specified in section 7.

Create:
1. src/schemas/onboarding.py - Onboarding status and step schemas
2. src/api/routes/onboarding.py - Onboarding endpoints
3. HTML templates in src/templates/onboarding/:
   - All 9 step templates
   - Clean, professional design (no emojis)
   - Mobile responsive with Tailwind CSS

4. src/static/js/onboarding.js - Client-side logic for step navigation

The onboarding must:
- Track progress in database
- Validate each step before allowing next
- Handle Kalshi credential input securely
```

### Prompt 5: Kalshi Integration

```
Implement the Kalshi API client as specified in section 8.

Create:
1. src/services/kalshi_service.py - Full Kalshi API client with:
   - RSA authentication
   - All endpoints needed (balance, markets, orders, positions)
   - Async httpx for HTTP calls
   - Proper error handling

2. Connection testing endpoint in onboarding
3. Credential storage with encryption

Reference the Kalshi API documentation for exact endpoints and authentication flow.
```

### Prompt 6: Trading Engine

```
Build the core trading engine as specified in section 9.

Create:
1. src/services/market_monitor.py - Market data fetching and parsing
2. src/services/trading_engine.py - Main trading loop with:
   - Pregame baseline tracking
   - Entry condition evaluation
   - Exit condition evaluation
   - Order execution (with dry run support)
   
3. src/services/position_manager.py - Position lifecycle management
4. Background task integration with FastAPI

The engine must:
- Run as background task
- Support start/stop/pause
- Handle errors gracefully
- Log all actions
```

### Prompt 7: Dashboard

```
Create the dashboard interface as specified in section 11.

Build:
1. src/templates/dashboard/ - All dashboard HTML templates:
   - Main dashboard with status, positions, activity
   - Settings page
   - Sport configurations page
   - Trade history page
   - Manual trading page

2. src/static/js/dashboard.js - Dashboard JavaScript
3. src/api/websocket.py - WebSocket handler for real-time updates
4. All dashboard API routes in src/api/routes/

Design requirements:
- Professional, clean interface
- No emojis
- Mobile responsive
- Real-time updates via WebSocket
```

### Prompt 8: Alerts and Final Polish

```
Implement alerts and finish the application.

Create:
1. src/services/alert_service.py - Discord webhook integration
   - Entry alerts
   - Exit alerts
   - Daily summary

2. Comprehensive error handling throughout
3. Input validation for all endpoints
4. Loading states in UI
5. Final security review

Test the complete flow:
- Registration -> Onboarding -> Dashboard -> Trading
```

### Prompt 9: Deployment

```
Set up deployment for Google Cloud Platform.

Create:
1. Dockerfile (optimized, multi-stage if needed)
2. docker-compose.yml for local development
3. .env.example with all required variables
4. cloudbuild.yaml for GCP Cloud Build
5. Deployment documentation in docs/DEPLOYMENT.md

Include:
- Health check endpoint
- Proper logging configuration
- Secret management approach
```

---

## Appendix A: Research Questions

Before starting development, research these topics:

1. **Kalshi API Sports Markets**
   - How are sports markets identified? (ticker format)
   - What data is available for game status/time?
   - Rate limits for API calls
   - WebSocket availability for real-time data

2. **Game Time Parsing**
   - How does Kalshi expose quarter/inning/period information?
   - Is time remaining available in API or needs calculation?

3. **GCP Cloud Run**
   - WebSocket support and limitations
   - Minimum instances for always-on
   - Cloud SQL connection from Cloud Run

---

## Appendix B: Testing Checklist

Before client delivery:

- [ ] User can register with email/password
- [ ] User can login and receive JWT tokens
- [ ] Onboarding flow completes all 9 steps
- [ ] Kalshi account connects successfully
- [ ] Sport configurations save and load
- [ ] Bot starts in dry run mode
- [ ] Bot tracks pregame odds correctly
- [ ] Bot enters positions at threshold
- [ ] Bot exits positions at take profit
- [ ] Bot exits positions at stop loss
- [ ] Bot exits positions at time limit
- [ ] Dashboard shows real-time data
- [ ] Settings changes apply immediately
- [ ] Discord alerts deliver correctly
- [ ] Works on mobile devices
- [ ] All error cases handled gracefully

---

*End of Technical Specification*
