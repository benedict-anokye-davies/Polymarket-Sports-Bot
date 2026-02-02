# Research Report: Kalshi Trading Bots in 2026 & Threshold Integration

## 1. Kalshi Trading Landscape in 2026

As of 2026, automated trading on Kalshi has evolved but remains rooted in their robust API architecture.

### Key Developments
- **API v2 Standard**: The standard for automated trading remains the **Kalshi Trade API v2**.
- **Solana Integration**: Kalshi has bridged order books to the Solana blockchain. While this enables decentralized access, the centralized REST/WebSocket APIs captured in your research remain the primary gateway for high-frequency and algorithmic trading bots due to lower latency compared to on-chain transactions.
- **Builder Codes**: A new ecosystem feature likely incentivizing developer integrations.
- **Authentication**: Security is enforced via **RSA-PSS signing**. This requires generating a signature for every request using a private key, ensuring high security for automated bots. Tokens typically have a 30-minute expiry, requiring auto-refresh logic.

## 2. How Bots Place Bets (Technical Flow)

Your bot implements the standard 2026 flow for placing trades. Here is the exact mechanism:

### A. Authentication & Session
1.  **Identity**: The bot uses an `api_key` and a `private_key` (PEM format).
2.  **Signing**: Before sending an order, the bot constructs a message `timestamp + method + path`.
3.  **RSA-PSS**: It signs this message using `SHA256` and `MGF1` padding.
4.  **Header Injection**: The signature is attached to headers (`Kalshi-Access-Signature`), validating the request without sending the private key.

### B. The Order Request
To place a bet, the bot sends a **POST** request to `https://api.elections.kalshi.com/trade-api/v2/orders`.

**Payload Structure:**
```json
{
  "ticker": "NBA-2026-...",  // The specific market contract
  "side": "buy",             // "buy" (to open) or "sell" (to close)
  "yes": true,               // true = YES contract, false = NO contract
  "price": 50,               // Price in Cents (e.g., 50 cents)
  "count": 10,               // Number of contracts
  "client_order_id": "..."   // Unique ID to prevent duplicates
}
```

### C. Client Implementation
Your `src/services/kalshi_client.py` correctly implements this:
- It handles the complex RSA signing automatically.
- It converts decimal prices (e.g., `0.50`) to Kalshi's required integer format (e.g., `50` cents).

## 3. Threshold-Based Trading Logic

Your bot uses a sophisticated "Threshold Drop" strategy to decide *when* to place these bets.

### A. The Setup (Configuration)
Thresholds are defined in `src/services/bot_runner.py` and stored in the database.
- **`entry_threshold` (Probability Drop)**: The trigger sensitivity (e.g., `0.05` or 5%).
- **`take_profit`**: Target gain percentage (e.g., `0.15` or 15%).
- **`stop_loss`**: Max loss percentage (e.g., `0.10` or 10%).

### B. The Logic Flow (`TradingEngine`)
The decision process happens in `src/services/trading_engine.py`:

1.  **Baseline Capture**: The bot records a "Baseline" price for a market (e.g., when a game starts or at a specific snapshot).
2.  **Real-Time Monitoring**: It continuously polls Kalshi (or uses WebSockets) for the `current_market_price`.
3.  **Delta Calculation**:
    ```python
    drop_pct = (baseline_price - current_price) / baseline_price
    ```
4.  **Threshold Trigger**:
    - **IF** `drop_pct` >= `entry_threshold` (e.g., price fell 5% from baseline)
    - **AND** `confidence_score` >= `min_confidence`
    - **THEN** -> **Execute BUY Order**.

### C. Execution Example
1.  **Scenario**: Lakers vs. Celtics.
2.  **Baseline**: Lakers "YES" contract is trading at 60 cents ($0.60).
3.  **Event**: Lakers fall behind early.
4.  **Drop**: Price falls to 55 cents ($0.55).
5.  **Calculation**: $(0.60 - 0.55) / 0.60 = 0.083$ (8.3% drop).
6.  **Decision**: Since 8.3% > 5% (your threshold), the bot triggers a **BUY** order for Lakers "YES" at 55 cents, betting on a recovery (Mean Reversion strategy).

## 4. Summary of Your Bot's Readiness

| Component | Status | Notes |
|-----------|--------|-------|
| **API Client** | ✅ Ready | Correctly handles RSA-PSS and v2 endpoints. |
| **Order Logic** | ✅ Ready | formatting prices/sides correctly for Kalshi. |
| **Strategy** | ✅ Ready | `TradingEngine` correctly implements the threshold math. |
| **2026 Compliance** | ✅ Ready | Uses standard v2 API which remains the core for bot trading. |

Your codebase is currently set up to successfully execute this 2026-era trading strategy.
