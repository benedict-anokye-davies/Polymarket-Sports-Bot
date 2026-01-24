# Polymarket Sports Trading Bot - AI Agent Instructions

## Project Context

Paid client project for automated sports betting on Polymarket prediction markets. The bot monitors live sports events, captures pre-game baseline prices, and executes trades when prices hit configured thresholds.

## Architecture Overview

**Dual-Source Data Model**: Polymarket provides market/order data but NOT game state. Two data sources required:

| Source | Data Provided | Auth Method |
|--------|---------------|-------------|
| Polymarket CLOB API | Prices, orderbook, orders, positions | L1 (EIP-712) or L2 (HMAC-SHA256) |
| ESPN API | Game state, period, clock, scores | None (public endpoints) |

The core challenge is matching ESPN game events to Polymarket market condition_ids/token_ids.

## Technology Stack

- **Runtime**: Python 3.11+
- **Framework**: FastAPI with async/await patterns
- **ORM**: SQLAlchemy 2.0 async with asyncpg
- **Validation**: Pydantic v2
- **Auth**: JWT (python-jose), bcrypt, Fernet encryption
- **HTTP**: httpx async client
- **WebSocket**: websocket-client for Polymarket streams
- **Database**: PostgreSQL with Alembic migrations
- **Deployment**: Docker, DigitalOcean Droplet (GitHub Education $200 credit)

## Project Structure

```
src/
├── api/
│   ├── deps.py                  # get_db, get_current_user dependencies
│   └── routes/                  # auth, dashboard, settings, trading, bot
├── core/
│   ├── security.py              # JWT creation/verification, bcrypt
│   └── encryption.py            # Fernet encrypt/decrypt for credentials
├── services/
│   ├── polymarket_client.py     # CLOB API wrapper with L1/L2 auth
│   ├── polymarket_ws.py         # WebSocket subscription manager
│   ├── espn_service.py          # Game state polling
│   ├── market_matcher.py        # ESPN-to-Polymarket matching logic
│   └── trading_engine.py        # Entry/exit evaluation, order lifecycle
├── models/                      # SQLAlchemy ORM models
├── schemas/                     # Pydantic request/response schemas
├── db/crud/                     # Database operations by entity
├── templates/                   # Jinja2 HTML templates
└── static/                      # CSS, JS assets
```

## Polymarket Authentication

### L1 Authentication (Wallet Signature)
Used for creating/deriving API credentials. Signs EIP-712 typed data.

```python
# L1 enables: create_api_key(), derive_api_key(), sign orders locally
from py_clob_client.client import ClobClient

client = ClobClient(
    host="https://clob.polymarket.com",
    chain_id=137,
    key=private_key
)
api_creds = client.create_or_derive_api_creds()
```

### L2 Authentication (HMAC)
Used for all trading operations. Requires apiKey, secret, passphrase.

```python
# L2 enables: post orders, cancel orders, get positions
client = ClobClient(
    host="https://clob.polymarket.com",
    chain_id=137,
    key=private_key,
    creds=api_creds,
    signature_type=1,       # 0=EOA, 1=POLY_PROXY, 2=GNOSIS_SAFE
    funder=funder_address   # Address holding USDC funds
)
```

### REST Headers for L2 (if not using py-clob-client)
```
POLY_ADDRESS: Polygon signer address
POLY_SIGNATURE: HMAC-SHA256 of request
POLY_TIMESTAMP: Current UNIX timestamp
POLY_API_KEY: API key value
POLY_PASSPHRASE: API passphrase value
```

## Polymarket WebSocket Integration

### Endpoints
- **CLOB WebSocket**: `wss://ws-subscriptions-clob.polymarket.com/ws/`
- **RTDS**: `wss://ws-live-data.polymarket.com` (comments, crypto prices)

### Channel Types
- `market` - Public orderbook and price updates (no auth)
- `user` - Order status updates (requires auth)

### Subscription Message Format

```python
# Subscribe to market channel (public)
{
    "assets_ids": ["token_id_1", "token_id_2"],
    "type": "market"
}

# Subscribe to user channel (authenticated)
{
    "markets": ["condition_id_1"],
    "type": "user",
    "auth": {
        "apiKey": "...",
        "secret": "...",
        "passphrase": "..."
    }
}

# Dynamic subscribe/unsubscribe
{"assets_ids": ["token_id"], "operation": "subscribe"}
{"assets_ids": ["token_id"], "operation": "unsubscribe"}
```

### WebSocket Events
- `book` - Orderbook updates with bids/asks
- `price_change` - Price movement notifications
- `tick_size_change` - Market tick size updates
- `last_trade_price` - Most recent trade price

### Keep-Alive
Send `"PING"` every 10 seconds to maintain connection.

## ESPN Game State Integration

### Endpoints
```
GET https://site.web.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard
GET https://site.web.api.espn.com/apis/site/v2/sports/{sport}/{league}/summary?event={id}
```

### Sport Mappings
```python
SPORT_ENDPOINTS = {
    "nba": "basketball/nba",
    "nfl": "football/nfl",
    "mlb": "baseball/mlb",
    "nhl": "hockey/nhl",
}
```

### Game State Extraction
```python
# Determine if game is live
is_live = game["status"]["type"]["state"] == "in"

# Get current period/quarter
period = game["status"]["period"]

# Get time remaining
clock_display = game["status"]["displayClock"]
clock_seconds = game["status"]["clock"]

# Get scores from competitors array
home = next(c for c in competitors if c["homeAway"] == "home")
away = next(c for c in competitors if c["homeAway"] == "away")
```

### Segment Normalization
```python
def normalize_segment(period: int, sport: str) -> str:
    """Convert ESPN period number to standard segment identifier."""
    if sport in ("nba", "nfl"):
        mapping = {1: "q1", 2: "q2", 3: "q3", 4: "q4"}
        return mapping.get(period, "ot")
    elif sport == "nhl":
        mapping = {1: "p1", 2: "p2", 3: "p3"}
        return mapping.get(period, "ot")
    elif sport == "mlb":
        return f"inning_{period}"
    return f"period_{period}"
```

## Trading Logic

### Entry Conditions (all must pass)
1. Game status is LIVE (not pregame or finished)
2. Current segment within allowed entry window
3. Time remaining in period exceeds minimum threshold
4. Price dropped from baseline by configured threshold OR price below absolute threshold
5. Position count within configured limits

### Exit Conditions (any triggers exit)
1. Take profit threshold reached
2. Stop loss threshold reached
3. Time-based exit (approaching restricted segment)
4. Game finished

## Market Matching Algorithm

ESPN games must be matched to Polymarket markets. Use a multi-strategy approach with confidence scoring.

### Primary Strategy: Team Abbreviation Matching

```python
def match_by_abbreviation(espn_game: dict, polymarket_markets: list[dict]) -> MatchResult | None:
    """
    Matches ESPN game to Polymarket market using team abbreviations.
    Most reliable method when abbreviations are consistent.
    
    Args:
        espn_game: ESPN event data with competitors array
        polymarket_markets: List of active Polymarket sports markets
    
    Returns:
        MatchResult with token_id and confidence score, or None
    """
    competitors = espn_game["competitions"][0]["competitors"]
    home_abbrev = next(c for c in competitors if c["homeAway"] == "home")["team"]["abbreviation"]
    away_abbrev = next(c for c in competitors if c["homeAway"] == "away")["team"]["abbreviation"]
    
    for market in polymarket_markets:
        title_upper = market["question"].upper()
        if home_abbrev in title_upper and away_abbrev in title_upper:
            return MatchResult(
                token_id=market["token_id"],
                condition_id=market["condition_id"],
                confidence=0.9
            )
    return None
```

### Secondary Strategy: Full Team Name Matching

```python
def match_by_team_name(espn_game: dict, polymarket_markets: list[dict]) -> MatchResult | None:
    """
    Fallback matching using full team display names.
    Handles cases where abbreviations differ between sources.
    """
    competitors = espn_game["competitions"][0]["competitors"]
    home_name = next(c for c in competitors if c["homeAway"] == "home")["team"]["displayName"].lower()
    away_name = next(c for c in competitors if c["homeAway"] == "away")["team"]["displayName"].lower()
    
    for market in polymarket_markets:
        title_lower = market["question"].lower()
        if home_name in title_lower and away_name in title_lower:
            return MatchResult(
                token_id=market["token_id"],
                condition_id=market["condition_id"],
                confidence=0.85
            )
    return None
```

### Tertiary Strategy: Time Window + Partial Match

```python
def match_by_time_window(espn_game: dict, polymarket_markets: list[dict]) -> MatchResult | None:
    """
    Match by game start time within tolerance window.
    Use when team names have variations (e.g., "LA Lakers" vs "Los Angeles Lakers").
    """
    espn_start = datetime.fromisoformat(espn_game["date"].replace("Z", "+00:00"))
    competitors = espn_game["competitions"][0]["competitors"]
    team_keywords = set()
    
    for comp in competitors:
        name_parts = comp["team"]["displayName"].lower().split()
        team_keywords.update(name_parts)
    
    for market in polymarket_markets:
        market_end = datetime.fromisoformat(market["end_date_iso"])
        time_delta = abs((market_end - espn_start).total_seconds())
        
        if time_delta < 14400:  # Within 4 hours
            title_lower = market["question"].lower()
            matches = sum(1 for kw in team_keywords if kw in title_lower)
            if matches >= 2:
                return MatchResult(
                    token_id=market["token_id"],
                    condition_id=market["condition_id"],
                    confidence=0.7
                )
    return None
```

### Combined Matcher

```python
async def match_espn_to_polymarket(espn_game: dict, polymarket_markets: list[dict]) -> MatchResult | None:
    """
    Executes matching strategies in order of reliability.
    Returns first match with confidence above threshold.
    """
    MIN_CONFIDENCE = 0.7
    
    strategies = [
        match_by_abbreviation,
        match_by_team_name,
        match_by_time_window,
    ]
    
    for strategy in strategies:
        result = strategy(espn_game, polymarket_markets)
        if result and result.confidence >= MIN_CONFIDENCE:
            return result
    
    return None
```

## Onboarding Flow

Nine-step wizard guiding users through initial setup. Each step must be completed before proceeding.

| Step | Name | User Action Required | Validation |
|------|------|---------------------|------------|
| 1 | Welcome | Read introduction | Click continue |
| 2 | How It Works | Review trading logic explanation | Click continue |
| 3 | Connect Wallet | Enter private key + funder address | Test API connection |
| 4 | Configure Sport | Select primary sport, set thresholds | Save config |
| 5 | Risk Settings | Set daily loss limit, max exposure | Values > 0 |
| 6 | Position Sizing | Set default position size | Value within balance |
| 7 | Discord Alerts | Enter webhook URL (optional) | Test webhook or skip |
| 8 | Review Settings | Confirm all configurations | Acknowledge |
| 9 | Dashboard Tour | Interactive feature walkthrough | Complete tour |

### Onboarding API Endpoints

```python
GET  /api/v1/onboarding/status          # Returns current step, completion state
POST /api/v1/onboarding/step/{n}        # Mark step n as complete
POST /api/v1/onboarding/wallet/connect  # Submit wallet credentials
POST /api/v1/onboarding/wallet/test     # Verify Polymarket connection
POST /api/v1/onboarding/skip            # Skip to dashboard (not recommended)
```

### Onboarding State Schema

```python
class OnboardingStatus(BaseModel):
    current_step: int
    total_steps: int = 9
    completed_steps: list[int]
    can_proceed: bool
    wallet_connected: bool
    
class OnboardingStepData(BaseModel):
    step_number: int
    title: str
    description: str
    is_completed: bool
    requires_input: bool
    input_fields: list[str] | None
```

## Error Handling and Retry Logic

### HTTP Request Retry Pattern

```python
import asyncio
from httpx import HTTPStatusError, TimeoutException

MAX_RETRIES = 3
BASE_DELAY = 1.0
MAX_DELAY = 30.0

async def request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    **kwargs
) -> httpx.Response:
    """
    Executes HTTP request with exponential backoff retry.
    Retries on 429, 500, 502, 503, 504 status codes and timeouts.
    
    Args:
        client: Configured httpx async client
        method: HTTP method (GET, POST, etc.)
        url: Target URL
        **kwargs: Additional arguments passed to client.request()
    
    Returns:
        Response object on success
    
    Raises:
        HTTPStatusError: After max retries exhausted
    """
    retryable_codes = {429, 500, 502, 503, 504}
    
    for attempt in range(MAX_RETRIES):
        try:
            response = await client.request(method, url, **kwargs)
            
            if response.status_code in retryable_codes:
                raise HTTPStatusError(
                    f"Retryable status {response.status_code}",
                    request=response.request,
                    response=response
                )
            
            response.raise_for_status()
            return response
            
        except (HTTPStatusError, TimeoutException) as e:
            if attempt == MAX_RETRIES - 1:
                raise
            
            delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
            
            if hasattr(e, "response") and e.response.status_code == 429:
                retry_after = e.response.headers.get("Retry-After", delay)
                delay = float(retry_after)
            
            await asyncio.sleep(delay)
```

### WebSocket Reconnection Pattern

```python
class WebSocketManager:
    """
    Manages WebSocket connection with automatic reconnection.
    Implements exponential backoff on connection failures.
    """
    
    def __init__(self, url: str, subscriptions: list[str]):
        self.url = url
        self.subscriptions = subscriptions
        self.reconnect_delay = 1.0
        self.max_reconnect_delay = 60.0
        self.is_connected = False
    
    async def connect(self) -> None:
        while True:
            try:
                async with websockets.connect(self.url) as ws:
                    self.is_connected = True
                    self.reconnect_delay = 1.0
                    
                    await self._subscribe(ws)
                    await self._listen(ws)
                    
            except websockets.ConnectionClosed:
                self.is_connected = False
                await asyncio.sleep(self.reconnect_delay)
                self.reconnect_delay = min(
                    self.reconnect_delay * 2,
                    self.max_reconnect_delay
                )
```

### Circuit Breaker Pattern

```python
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class CircuitBreaker:
    """
    Prevents repeated calls to failing services.
    Opens circuit after threshold failures, closes after timeout.
    """
    failure_threshold: int = 5
    recovery_timeout: int = 60
    failure_count: int = 0
    last_failure_time: datetime | None = None
    state: str = "closed"  # closed, open, half-open
    
    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
    
    def record_success(self) -> None:
        self.failure_count = 0
        self.state = "closed"
    
    def can_execute(self) -> bool:
        if self.state == "closed":
            return True
        
        if self.state == "open":
            if self.last_failure_time:
                elapsed = datetime.utcnow() - self.last_failure_time
                if elapsed > timedelta(seconds=self.recovery_timeout):
                    self.state = "half-open"
                    return True
            return False
        
        return True  # half-open allows one attempt
```

## Logging Standards

Use structured JSON logging for all application logs. This enables log aggregation and querying in production.

### Logger Configuration

```python
import logging
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    """
    Formats log records as JSON for structured logging.
    Compatible with Cloud Run, ELK stack, and other log aggregators.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        
        if hasattr(record, "market_id"):
            log_data["market_id"] = record.market_id
        
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)

def setup_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
```

### Log Level Guidelines

| Level | Use Case | Example |
|-------|----------|---------|
| DEBUG | Internal state, variable values | `Calculated position size: 15 contracts` |
| INFO | Normal operations, state changes | `Order placed: token_id=abc123, size=10` |
| WARNING | Recoverable issues, degraded state | `ESPN API slow response: 2.3s` |
| ERROR | Failed operations requiring attention | `Order placement failed: insufficient balance` |
| CRITICAL | System-wide failures | `Database connection lost` |

### Contextual Logging

```python
logger = logging.getLogger(__name__)

async def place_order(user_id: str, token_id: str, size: int) -> Order:
    extra = {"user_id": user_id, "market_id": token_id}
    
    logger.info(f"Placing order: size={size}", extra=extra)
    
    try:
        order = await polymarket_client.create_order(token_id, size)
        logger.info(f"Order confirmed: order_id={order.id}", extra=extra)
        return order
    except InsufficientBalanceError as e:
        logger.error(f"Order failed: {e}", extra=extra)
        raise
```

## Database Models

| Model | Purpose |
|-------|---------|
| `users` | Authentication, onboarding progress |
| `polymarket_accounts` | Encrypted wallet keys, API credentials |
| `sport_configs` | Per-sport trading parameters |
| `tracked_markets` | Baseline prices, ESPN event mapping |
| `positions` | Open/closed trades, entry/exit data |
| `global_settings` | Bot state, risk limits |

## Code Style Requirements

Write comments as a university CS student would - clear, technical, no fluff.

```python
# Correct style:
def calculate_position_size(balance: float, risk_pct: float) -> int:
    """
    Determines the number of contracts to purchase based on
    available balance and configured risk percentage.
    
    Args:
        balance: Current USDC balance in account
        risk_pct: Maximum percentage of balance to risk (0.0-1.0)
    
    Returns:
        Number of contracts as integer, minimum 1
    """
    raw_size = balance * risk_pct
    return max(1, int(raw_size))
```

### Prohibited
- No emojis anywhere in code, comments, logs, or UI
- No ASCII art or decorative comments
- No placeholder comments like "TODO: implement later"
- No commented-out code blocks
- No informal language in docstrings

### Required
- Type hints on all function signatures
- Docstrings on public methods (Google style)
- Descriptive variable names (no single letters except loop counters)
- Constants in UPPER_SNAKE_CASE
- Private methods prefixed with underscore

## Development Commands

```bash
# Environment setup (Windows)
python -m venv venv
venv\Scripts\activate

# Dependencies
pip install -r requirements.txt

# Database migrations
alembic upgrade head

# Run development server
uvicorn src.main:app --reload --port 8000

# Docker local testing
docker build -t polymarket-bot .
docker-compose up -d
```

## DigitalOcean Deployment

Using GitHub Education Pack ($200 credit). Recommended setup: $6/month Droplet runs 33+ months free.

### Initial Server Setup

```bash
# SSH into your Droplet
ssh root@your-droplet-ip

# Update system and install dependencies
apt update && apt upgrade -y
apt install -y docker.io docker-compose nginx certbot python3-certbot-nginx

# Enable Docker
systemctl enable docker
systemctl start docker

# Create non-root user for running the app
adduser botuser
usermod -aG docker botuser
```

### Application Deployment

```bash
# As botuser
su - botuser

# Clone repository
git clone https://github.com/yourusername/polymarket-bot.git
cd polymarket-bot

# Create environment file
cp .env.example .env
nano .env  # Configure your secrets

# Build and start containers
docker-compose up -d --build

# Check logs
docker-compose logs -f
```

### docker-compose.yml (Production)

```yaml
version: '3.8'

services:
  app:
    build: .
    restart: always
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:${DB_PASSWORD}@db:5432/polymarket_bot
      - SECRET_KEY=${SECRET_KEY}
    depends_on:
      - db
    volumes:
      - ./logs:/app/logs

  db:
    image: postgres:15-alpine
    restart: always
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_DB=polymarket_bot
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

volumes:
  postgres_data:
```

### Nginx Reverse Proxy

```nginx
# /etc/nginx/sites-available/polymarket-bot
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
# Enable site and get SSL certificate
ln -s /etc/nginx/sites-available/polymarket-bot /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
certbot --nginx -d yourdomain.com
```

### Systemd Service (Alternative to Docker)

```ini
# /etc/systemd/system/polymarket-bot.service
[Unit]
Description=Polymarket Trading Bot
After=network.target postgresql.service

[Service]
User=botuser
WorkingDirectory=/home/botuser/polymarket-bot
EnvironmentFile=/home/botuser/polymarket-bot/.env
ExecStart=/home/botuser/polymarket-bot/venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Deployment Checklist

- [ ] Droplet created ($6/month, Ubuntu 22.04)
- [ ] SSH key configured
- [ ] Docker and Docker Compose installed
- [ ] PostgreSQL container running
- [ ] Environment variables configured
- [ ] Nginx reverse proxy configured
- [ ] SSL certificate obtained (Let's Encrypt)
- [ ] Firewall configured (ufw allow 80,443,22)
- [ ] Application running and accessible

## External API Reference

### Polymarket REST Endpoints
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/price` | GET | Current token price |
| `/book` | GET | Full orderbook |
| `/midpoint` | GET | Midpoint price |
| `/order` | POST | Place order (auth required) |
| `/order` | DELETE | Cancel order (auth required) |

### Polymarket Base URLs
- CLOB API: `https://clob.polymarket.com`
- Gamma API: `https://gamma-api.polymarket.com`
- Data API: `https://data-api.polymarket.com`

## Credential Storage

All sensitive credentials encrypted at rest using Fernet symmetric encryption.

```python
from cryptography.fernet import Fernet
import hashlib
import base64

def derive_key(secret: str) -> bytes:
    """Derive Fernet key from application secret."""
    digest = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(digest)

def encrypt_credential(value: str, secret: str) -> str:
    """Encrypt sensitive value before database storage."""
    f = Fernet(derive_key(secret))
    return f.encrypt(value.encode()).decode()
```
