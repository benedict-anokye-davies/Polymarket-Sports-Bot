# Kalshi Live Trading Setup Guide

This guide covers the key requirements to enable live trading with Kalshi.

---

## 🔑 Requirement 1: Kalshi API Credentials

### Step 1: Get Your Kalshi API Key & RSA Private Key

1. **Production Account**: Log into [Kalshi](https://kalshi.com) → Settings → API Keys
2. **Demo Account**: Log into [demo.kalshi.co](https://demo.kalshi.co) → Settings → API Keys

Generate a new API key and **download your RSA private key** (you'll need the full PEM format).

### Step 2: Store Credentials via API

Make a POST request to your backend:

```bash
curl -X POST "https://your-backend-url/api/onboarding/wallet/connect" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "kalshi",
    "api_key": "YOUR_KALSHI_API_KEY_ID",
    "api_secret": "-----BEGIN RSA PRIVATE KEY-----\nMIIE...YOUR_FULL_KEY...\n-----END RSA PRIVATE KEY-----"
  }'
```

> ⚠️ **IMPORTANT**: The `api_secret` field must contain your **complete RSA private key** in PEM format, including the header and footer lines.

### Alternative: Store Credentials via Web UI (Recommended)

The web interface provides a much easier way to enter your RSA private key:

1. Navigate to **Onboarding** or **Settings** → **Accounts**
2. Select **Kalshi** as the trading platform
3. Enter your **API Key** in the API Key field
4. Paste your **complete RSA Private Key** into the large textarea (it preserves newlines!)
5. Click **Test Connection** to verify your credentials work

> ✅ **TIP**: The RSA Private Key field is a multiline textarea, so you can paste your entire PEM key directly without worrying about newlines being stripped.

### Step 3: Test Connection

```bash
curl -X POST "https://your-backend-url/api/onboarding/wallet/test" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

## 🌍 Requirement 2: Environment Selection (Demo vs Production)

The environment is set when credentials are stored. By default, the bot connects to **production**.

### For Demo Mode (Recommended for Testing)

The environment is automatically determined based on your API credentials. If you're using demo.kalshi.co credentials, the bot will work with the demo environment.

To explicitly use demo mode, you need to update the credential storage to include environment:

**In the API route (`bot.py` line 51)**, the environment is passed when creating the client:
```python
trading_client = KalshiClient(
    api_key_id=credentials["api_key"],
    private_key_pem=credentials["api_secret"],
    environment=credentials.get("environment", "production")  # "demo" or "production"
)
```

### Adding Environment Support

To add environment selection, update your credentials storage to include:
```json
{
  "platform": "kalshi",
  "api_key": "your-key",
  "api_secret": "your-pem-key",
  "environment": "demo"
}
```

---

## 📄 Requirement 3: Disable Paper Trading Mode

By default, `dry_run_mode = True` (paper trading). To enable **live trading**:

### Option A: Via API Endpoint

```bash
curl -X POST "https://your-backend-url/api/bot/paper-trading?enabled=false" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Option B: Via Bot Config Endpoint

```bash
curl -X POST "https://your-backend-url/api/bot/config" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "simulation_mode": false,
    "sport": "nba",
    "game": {
      "game_id": "401234567",
      "home_team": "Lakers",
      "away_team": "Celtics",
      "selected_side": "home"
    }
  }'
```

### Option C: Via Frontend

Navigate to **Bot Config** page and toggle off "Simulation Mode".

---

## ✅ Verification Checklist

| Requirement | How to Check | Expected Result |
|------------|--------------|-----------------|
| API Key stored | `GET /api/onboarding/status` | `wallet_connected: true` |
| Connection works | `POST /api/onboarding/wallet/test` | `success: true, balance_usdc: X.XX` |
| Paper trading OFF | `GET /api/bot/paper-trading` | `paper_trading_enabled: false` |
| Bot can start | `POST /api/bot/start` | `message: "Bot started successfully"` |

---

## 🚀 Quick Start Commands

```bash
# 1. Store Kalshi credentials
curl -X POST "$API_URL/api/onboarding/wallet/connect" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"platform":"kalshi","api_key":"YOUR_KEY","api_secret":"YOUR_PEM"}'

# 2. Test connection
curl -X POST "$API_URL/api/onboarding/wallet/test" \
  -H "Authorization: Bearer $TOKEN"

# 3. Disable paper trading
curl -X POST "$API_URL/api/bot/paper-trading?enabled=false" \
  -H "Authorization: Bearer $TOKEN"

# 4. Start the bot
curl -X POST "$API_URL/api/bot/start" \
  -H "Authorization: Bearer $TOKEN"
```

---

## 📋 Current Code References

| File | Purpose |
|------|---------|
| `src/services/kalshi_client.py` | Kalshi API client with `place_order()` |
| `src/api/routes/onboarding.py` | Credential storage (`/wallet/connect`) |
| `src/api/routes/bot.py` | Bot control (`/start`, `/paper-trading`) |
| `src/models/global_settings.py` | `dry_run_mode` database field |

---

**Last Updated:** January 30, 2026
