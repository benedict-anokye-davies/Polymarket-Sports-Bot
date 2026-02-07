# Auto-Trade-All Mode Implementation

## Overview
This feature allows the bot to automatically bet on **ANY team** that matches your configured parameters, without requiring manual game selection.

## Changes Made

### Backend
1. **`src/models/global_settings.py`**
   - Added `auto_trade_all` boolean column (default: False)

2. **`src/services/bot_runner.py`**
   - Added `self.auto_trade_all` instance variable
   - Modified `initialize()` to load `auto_trade_all` from settings
   - Modified discovery loop: skips only if no games selected AND auto_trade_all is disabled
   - Modified market matching: auto-selects markets when `auto_trade_all=True`

3. **`src/schemas/bot_config.py`**
   - Added `auto_trade_all` field to `BotConfigRequest`

4. **`src/api/routes/bot.py`**
   - Added handling for `auto_trade_all` in save_bot_config endpoint
   - Updates GlobalSettings when auto_trade_all changes

5. **`alembic/versions/add_auto_trade_all.py`**
   - Database migration to add the new column

### Frontend
1. **`frontend/src/pages/BotConfig.tsx`**
   - Added `autoTradeAll` state
   - Added toggle UI in Trading Parameters section
   - Modified `handleSave()` to support auto-trade mode
   - Modified `handleToggleBot()` to support auto-trade mode
   - Updated validation: games not required when auto mode enabled

2. **`frontend/src/api/client.ts`**
   - Added `auto_trade_all` to `BotConfigRequest` interface

## How It Works

1. **Enable Auto-Trade Mode**: Click the toggle in Trading Parameters
2. **Configure Parameters**: Set your entry threshold, take profit, stop loss, etc.
3. **Start Bot**: Click START - bot will scan ALL markets
4. **Auto-Betting**: When any team's odds drop to meet your entry threshold, the bot places a bet

## Side Selection in Auto Mode

In auto mode, the `selected_side` is set to `"auto"`. The trading engine:
- Evaluates BOTH YES and NO sides
- Bets on whichever side meets the entry criteria first
- Uses the same parameters (threshold, position size, etc.) for both

## Database Migration

Run the migration on VPS:
```bash
ssh root@76.13.111.52
cd /opt/Polymarket-Sports-Bot
docker exec -it app alembic upgrade head
```

Or apply directly via SQL:
```sql
ALTER TABLE global_settings ADD COLUMN auto_trade_all BOOLEAN DEFAULT FALSE;
```

## Testing

1. Enable Auto-Trade Mode in UI
2. Set a generous entry threshold (e.g., 5% drop)
3. Start bot
4. Check logs for "AUTO-TRADE: Auto-selecting market..."

---
*Implemented: 2026-02-07*
