# Polymarket Bot API Reference

**Base URL:** `http://localhost:8000/api/v1`

**Authentication:** Bearer token in `Authorization` header
```
Authorization: Bearer <access_token>
```

---

## Authentication

### Register
```
POST /auth/register
Content-Type: application/json

{
  "username": "string",
  "email": "string",
  "password": "string"
}

Response 201:
{
  "access_token": "string",
  "token_type": "bearer"
}
```

### Login
```
POST /auth/login
Content-Type: application/x-www-form-urlencoded

username=email@example.com&password=yourpassword

Response 200:
{
  "access_token": "string",
  "token_type": "bearer"
}
```

### Get Current User
```
GET /auth/me
Authorization: Bearer <token>

Response 200:
{
  "id": "uuid",
  "username": "string",
  "email": "string",
  "is_active": true,
  "onboarding_completed": false,
  "created_at": "2026-01-24T00:00:00Z"
}
```

---

## Dashboard

### Get Stats
```
GET /dashboard/stats
Authorization: Bearer <token>

Response 200:
{
  "portfolio_value": 1000.00,
  "daily_pnl": 50.00,
  "daily_pnl_percent": 5.0,
  "active_pnl": 25.00,
  "active_pnl_percent": 2.5,
  "open_positions": 3,
  "tracked_markets": 5,
  "win_rate": 65.5,
  "total_trades": 20
}
```

### Get Performance Data
```
GET /dashboard/performance
Authorization: Bearer <token>

Response 200:
{
  "daily": [...],
  "weekly": [...],
  "monthly": [...]
}
```

### SSE Stream (Real-time updates)
```
GET /dashboard/stream
Authorization: Bearer <token>

Response: Server-Sent Events stream
```

---

## Bot Control

### Start Bot
```
POST /bot/start
Authorization: Bearer <token>

Response 200:
{
  "message": "Bot started successfully"
}
```

### Stop Bot
```
POST /bot/stop
Authorization: Bearer <token>

Response 200:
{
  "message": "Bot stopped successfully"
}
```

### Emergency Stop
```
POST /bot/emergency-stop
Authorization: Bearer <token>

Response 200:
{
  "message": "Emergency stop executed"
}
```

### Get Bot Status
```
GET /bot/status
Authorization: Bearer <token>

Response 200:
{
  "bot_enabled": true,
  "tracked_markets": 5,
  "open_positions": 2,
  "last_scan": "2026-01-24T00:00:00Z"
}
```

### Get Tracked Games
```
GET /bot/tracked-games
Authorization: Bearer <token>

Response 200:
[
  {
    "espn_event_id": "string",
    "sport": "nba",
    "home_team": "Lakers",
    "away_team": "Celtics",
    "status": "live",
    "period": 2,
    "clock": "5:30"
  }
]
```

---

## Trading

### Get All Markets
```
GET /trading/markets
Authorization: Bearer <token>

Response 200:
[
  {
    "id": "uuid",
    "condition_id": "string",
    "token_id": "string",
    "question": "Will Lakers beat Celtics?",
    "baseline_price": 0.55,
    "current_price": 0.52,
    "status": "active"
  }
]
```

### Get Market Details
```
GET /trading/markets/{market_id}
Authorization: Bearer <token>

Response 200:
{
  "id": "uuid",
  "condition_id": "string",
  ...
}
```

### Get All Positions
```
GET /trading/positions
Authorization: Bearer <token>

Response 200:
[
  {
    "id": "uuid",
    "token_id": "string",
    "side": "buy",
    "size": 100,
    "entry_price": 0.50,
    "current_price": 0.55,
    "pnl": 5.00,
    "pnl_percent": 10.0,
    "status": "open"
  }
]
```

### Get Open Positions
```
GET /trading/positions/open
Authorization: Bearer <token>
```

### Get Position Details
```
GET /trading/positions/{position_id}
Authorization: Bearer <token>
```

### Place Order
```
POST /trading/order
Authorization: Bearer <token>
Content-Type: application/json

{
  "token_id": "string",
  "side": "buy",
  "size": 100,
  "price": 0.50
}

Response 200:
{
  "order_id": "string",
  "status": "filled",
  "filled_size": 100,
  "average_price": 0.50
}
```

### Close Position
```
DELETE /trading/positions/{position_id}/close
Authorization: Bearer <token>

Response 200:
{
  "id": "uuid",
  "status": "closed",
  "exit_price": 0.55,
  "realized_pnl": 5.00
}
```

---

## Settings

### Get All Sport Configs
```
GET /settings/sports
Authorization: Bearer <token>

Response 200:
[
  {
    "id": "uuid",
    "sport": "nba",
    "enabled": true,
    "entry_threshold": 0.05,
    "exit_threshold": 0.10,
    "max_positions": 5,
    "position_size": 50.00
  }
]
```

### Get Sport Config
```
GET /settings/sports/{sport}
Authorization: Bearer <token>
```

### Update Sport Config
```
PUT /settings/sports/{sport}
Authorization: Bearer <token>
Content-Type: application/json

{
  "enabled": true,
  "entry_threshold": 0.05,
  "exit_threshold": 0.10,
  "max_positions": 5,
  "position_size": 50.00
}
```

### Create Sport Config
```
POST /settings/sports
Authorization: Bearer <token>
Content-Type: application/json

{
  "sport": "nfl",
  "enabled": true,
  ...
}
```

### Get Global Settings
```
GET /settings/global
Authorization: Bearer <token>

Response 200:
{
  "id": "uuid",
  "bot_enabled": false,
  "daily_loss_limit": 100.00,
  "max_exposure": 500.00,
  "discord_webhook_url": "string|null"
}
```

### Update Global Settings
```
PUT /settings/global
Authorization: Bearer <token>
Content-Type: application/json

{
  "daily_loss_limit": 100.00,
  "max_exposure": 500.00,
  "discord_webhook_url": "https://discord.com/api/webhooks/..."
}
```

### Test Discord Webhook
```
POST /settings/discord/test
Authorization: Bearer <token>

Response 200:
{
  "message": "Test notification sent successfully"
}
```

---

## Activity Logs

### Get All Logs
```
GET /logs/
Authorization: Bearer <token>

Response 200:
[
  {
    "id": "uuid",
    "action": "bot_started",
    "details": "Bot started by user",
    "level": "info",
    "created_at": "2026-01-24T00:00:00Z"
  }
]
```

### Get Error Logs
```
GET /logs/errors
Authorization: Bearer <token>
```

### Get Trade Logs
```
GET /logs/trades
Authorization: Bearer <token>
```

---

## Onboarding

### Get Status
```
GET /onboarding/status
Authorization: Bearer <token>

Response 200:
{
  "current_step": 1,
  "total_steps": 9,
  "completed_steps": [],
  "can_proceed": true,
  "wallet_connected": false
}
```

### Get Step Data
```
GET /onboarding/step/{step_number}
Authorization: Bearer <token>

Response 200:
{
  "step_number": 1,
  "title": "Welcome",
  "description": "...",
  "is_completed": false,
  "requires_input": false,
  "input_fields": null
}
```

### Complete Step
```
POST /onboarding/step/{step_number}/complete
Authorization: Bearer <token>
```

### Connect Wallet
```
POST /onboarding/wallet/connect
Authorization: Bearer <token>
Content-Type: application/json

{
  "private_key": "0x...",
  "funder_address": "0x..."
}
```

### Test Wallet Connection
```
POST /onboarding/wallet/test
Authorization: Bearer <token>

Response 200:
{
  "success": true,
  "address": "0x...",
  "balance": "100.00"
}
```

### Complete Onboarding
```
POST /onboarding/complete
Authorization: Bearer <token>
```

### Skip Onboarding
```
POST /onboarding/skip
Authorization: Bearer <token>
```

---

## Health Check

```
GET /health

Response 200:
{
  "status": "healthy",
  "version": "1.0.0"
}
```

---

## Error Responses

All endpoints return errors in this format:
```json
{
  "detail": "Error message string"
}
```

Or for validation errors:
```json
{
  "detail": [
    {
      "type": "validation_error",
      "loc": ["body", "field_name"],
      "msg": "Error description"
    }
  ]
}
```

## Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 422 | Validation Error |
| 500 | Server Error |
