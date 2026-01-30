# CLAUDE.md - Antigravity AI Instructions

> **Read this file every time before starting work on this project.**
> This file extends `.github/copilot-instructions.md` with Kalshi integration, deployment info, and common issues.

## Quick Reference

| Component | Location | Purpose |
|-----------|----------|---------|
| Backend API | `src/api/routes/` | FastAPI endpoints (bot, trading, settings, auth) |
| Services | `src/services/` | Core logic (bot_runner, trading_engine, espn_service, kalshi_client) |
| Frontend | `frontend/src/` | React + TypeScript app (Vite, Zustand, TailwindCSS) |
| Database | `src/db/crud/` | SQLAlchemy async CRUD operations |
| Schemas | `src/schemas/` | Pydantic request/response models |

## Deployment Architecture

```
┌─────────────────┐     ┌─────────────────┐
│   Vercel        │     │   Railway       │
│   (Frontend)    │────▶│   (Backend)     │
│   React + Vite  │     │   FastAPI       │
└─────────────────┘     └────────┬────────┘
                                 │
                        ┌────────▼────────┐
                        │   PostgreSQL    │
                        │   (Railway)     │
                        └─────────────────┘
```

**URLs:**
- Frontend: `polymarket-sports-bot-*.vercel.app`
- Backend API: `polymarket-sports-bot-*.railway.app`
- Health Check: `GET /health`

## Kalshi Integration (Added Nov 2025)

### Kalshi vs Polymarket

| Feature | Kalshi | Polymarket |
|---------|--------|------------|
| Auth | RSA-signed API key | EIP-712 wallet signature |
| Balance | Cents (divide by 100) | USDC |
| Order size | Contracts | Shares |
| Demo mode | `demo-api.kalshi.co` | N/A |

### Kalshi Client (`src/services/kalshi_client.py`)

```python
# RSA Authentication
from src.services.kalshi_client import KalshiClient

client = KalshiClient(
    api_key_id="your-api-key",
    private_key_pem="-----BEGIN RSA PRIVATE KEY-----\n...",
    environment="production"  # or "demo"
)

# Get balance (returns cents, divide by 100)
balance = await client.get_balance()
usdc_balance = balance["available_balance"] / 100

# Always close when done
await client.close()
```

### Dual Platform Support

The bot supports both platforms via a common interface:

```python
# In bot.py / bot_runner.py
if platform == "kalshi":
    trading_client = KalshiClient(...)
else:
    trading_client = PolymarketClient(...)

# BotRunner accepts trading_client (not polymarket_client!)
bot_runner = await get_bot_runner(
    user_id=user_id,
    trading_client=trading_client,  # Correct parameter name
    ...
)
```

## Common Issues & Fixes

### 1. "get_bot_runner() got an unexpected keyword argument"

**Cause:** Parameter name mismatch between caller and function
**Fix:** Ensure `get_bot_runner()` signature uses `trading_client`:

```python
# In src/services/bot_runner.py
async def get_bot_runner(
    user_id: UUID,
    trading_client: Union[PolymarketClient, KalshiClient],  # NOT polymarket_client
    trading_engine: TradingEngine,
    espn_service: ESPNService
) -> BotRunner:
```

### 2. Status Bar shows "Offline" / SSE not connecting

**Cause:** `useSSE` hook not called in DashboardLayout
**Fix:** Wire the hook in `frontend/src/components/layout/DashboardLayout.tsx`:

```typescript
import { useSSE } from '@/hooks/useSSE';

export function DashboardLayout({ children }) {
  // Add this line:
  useSSE({ enabled: true });
  
  // ... rest of component
}
```

### 3. BotStatus type errors (`is_running`, `active_positions` don't exist)

**Cause:** Frontend using wrong property names
**Fix:** Use correct properties from `BotStatus` interface:

```typescript
// Wrong:
setBotStatus(botStatus.is_running, botStatus.active_positions);

// Correct:
setBotStatus(botStatus.bot_enabled, botStatus.tracked_markets);
```

### 4. Balance shows N/A on Accounts page

**Cause:** Kalshi credentials not decrypting or API call failing
**Check:**
1. Railway logs for `KalshiClient` errors
2. Credentials stored in `polymarket_accounts` table with correct `platform="kalshi"`
3. `get_balance()` returns dict with `available_balance` in cents

### 5. "Failed to load league data" error

**Cause:** `/bot/categories` endpoint failing
**Check:** `ESPNService.get_all_categories()` in Railway logs

### 6. "Unable to connect to server" errors

**Cause:** Backend API not responding (crash, timeout, CORS)
**Debug:**
1. Check Railway deployment logs
2. Verify `/health` endpoint responds
3. Check for Python exceptions in logs

## Key Files to Know

| File | Purpose |
|------|---------|
| `src/services/bot_runner.py` | Main bot orchestration (2300+ lines) |
| `src/services/trading_engine.py` | Entry/exit logic |
| `src/services/espn_service.py` | Game state polling + league data |
| `src/services/kalshi_client.py` | Kalshi RSA auth + order management |
| `src/api/routes/bot.py` | Bot control endpoints |
| `frontend/src/api/client.ts` | API client with all endpoints |
| `frontend/src/stores/useAppStore.ts` | Global state (bot status, wallet) |
| `frontend/src/hooks/useSSE.ts` | Real-time SSE connection |

## Trading Parameters Flow

Frontend → API → Database → BotRunner:

```
BotConfig.tsx (UI sliders)
    ↓ toApiParams()
saveBotConfig() API call
    ↓
SportConfig table (database)
    ↓ BotRunner.initialize()
self.entry_threshold, self.take_profit, self.stop_loss
```

## Environment Variables

```bash
# Backend (.env)
DATABASE_URL=postgresql+asyncpg://...
SECRET_KEY=your-jwt-secret
ENCRYPTION_KEY=your-fernet-key

# Frontend (Vercel)
VITE_API_URL=https://your-backend.railway.app/api/v1
```

## Development Commands

```bash
# Backend
uvicorn src.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev

# Migrations
alembic upgrade head
alembic revision --autogenerate -m "description"

# Push and Deploy
git add -A && git commit -m "message" && git push origin master
```

## Railway Deployment Troubleshooting

1. **Check deployment status:** Railway Dashboard → Deployments
2. **View logs:** Click deployment → Logs
3. **Trigger redeploy:** Settings → Deploy → Trigger Deploy (with "Clear cache" if needed)
4. **Verify commit:** Ensure latest commit hash matches what's deployed

## Code Style (from copilot-instructions.md)

- **Type hints** on all function signatures
- **Google-style docstrings** on public methods
- **No emojis** in code, comments, logs, or UI
- **No placeholder TODOs** or commented-out code
- **async/await** patterns throughout

## For Full Documentation

See `.github/copilot-instructions.md` for:
- Polymarket authentication (L1/L2)
- WebSocket integration
- ESPN game state parsing
- Market matching algorithm
- Onboarding flow
- Error handling patterns
- Docker deployment
