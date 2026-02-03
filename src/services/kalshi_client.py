"""
Kalshi API Client - Updated for 2026 API spec.

Implements RSA-PSS authentication, order management, and portfolio endpoints
using the current Kalshi trade-api/v2 at api.elections.kalshi.com.
"""

import asyncio
import base64
import logging
import time
import uuid as uuid_mod
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


class KalshiClient:
    """
    Kalshi trading API client with RSA-PSS authentication.

    Uses the production API at api.elections.kalshi.com/trade-api/v2.
    All order endpoints use the /portfolio/orders path per the 2026 API spec.
    """

    BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"

    def __init__(self, api_key: str, private_key_pem: str):
        """
        Initialize Kalshi client with API credentials.

        Args:
            api_key: Kalshi API key ID
            private_key_pem: RSA private key in PEM format
        """
        self.api_key = api_key
        self.private_key = load_pem_private_key(
            private_key_pem.encode(),
            password=None,
            backend=default_backend()
        )
        self.client = httpx.AsyncClient(timeout=30.0)

    @staticmethod
    def validate_rsa_key(pem_string: str) -> Tuple[bool, Optional[str]]:
        """
        Validate that a string is a valid RSA private key in PEM format.

        Args:
            pem_string: The PEM-encoded RSA private key string.

        Returns:
            Tuple of (is_valid, error_message). error_message is None if valid.
        """
        try:
            if not pem_string or not pem_string.strip():
                return False, "RSA private key is empty"
            stripped = pem_string.strip()
            if "BEGIN RSA PRIVATE KEY" not in stripped and "BEGIN PRIVATE KEY" not in stripped:
                return False, "Key must contain PEM header (BEGIN RSA PRIVATE KEY or BEGIN PRIVATE KEY)"
            if "END RSA PRIVATE KEY" not in stripped and "END PRIVATE KEY" not in stripped:
                return False, "Key must contain PEM footer (END RSA PRIVATE KEY or END PRIVATE KEY)"
            load_pem_private_key(
                stripped.encode(),
                password=None,
                backend=default_backend()
            )
            return True, None
        except ValueError as e:
            return False, f"Invalid PEM format: {str(e)}"
        except Exception as e:
            return False, f"Failed to load RSA key: {str(e)}"

    def _sign_request(self, method: str, path: str) -> Dict[str, str]:
        """
        Build authenticated headers for a Kalshi API request.

        Signs the message "{timestamp}{METHOD}{/trade-api/v2/path}" using RSA-PSS
        with SHA-256 per the Kalshi authentication spec.

        The path used for signing must be the full API path (including /trade-api/v2)
        but WITHOUT query parameters.

        Args:
            method: HTTP method (GET, POST, DELETE, PUT)
            path: API path relative to BASE_URL (e.g. "/portfolio/balance")

        Returns:
            Dict of authentication headers
        """
        timestamp = str(int(time.time() * 1000))

        # Strip query params for signing - only sign the path portion
        sign_path = path.split("?")[0]
        # The full path for signing includes the /trade-api/v2 prefix
        full_sign_path = f"/trade-api/v2{sign_path}"

        message = f"{timestamp}{method.upper()}{full_sign_path}"

        signature = self.private_key.sign(
            message.encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH
            ),
            hashes.SHA256()
        )

        return {
            "KALSHI-ACCESS-KEY": self.api_key,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode(),
            "Content-Type": "application/json",
        }

    async def _authenticated_request(self, method: str, path: str, **kwargs) -> Dict:
        """
        Make authenticated request to Kalshi API with retry logic.

        Implements exponential backoff for rate limiting (429) and server errors (5xx).
        """
        max_retries = 3
        last_error = None

        for attempt in range(max_retries):
            try:
                headers = self._sign_request(method, path)
                url = f"{self.BASE_URL}{path}"

                response = await self.client.request(
                    method,
                    url,
                    headers=headers,
                    **kwargs
                )

                # Handle rate limiting (429) with exponential backoff
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 5))
                    wait_time = max(retry_after, 2 ** attempt)
                    logger.warning(f"Rate limited (429), waiting {wait_time}s before retry {attempt + 1}/{max_retries}")
                    await asyncio.sleep(wait_time)
                    continue

                # Handle server errors (5xx) with exponential backoff
                if response.status_code in (500, 502, 503, 504):
                    wait_time = 2 ** attempt
                    logger.warning(f"Server error ({response.status_code}), waiting {wait_time}s before retry {attempt + 1}/{max_retries}")
                    await asyncio.sleep(wait_time)
                    continue

                response.raise_for_status()

                if response.status_code == 204:
                    return {}
                return response.json()

            except httpx.HTTPStatusError as e:
                last_error = e
                resp_text = ""
                try:
                    resp_text = e.response.text
                except Exception:
                    pass
                logger.error(f"Kalshi API error {e.response.status_code}: {resp_text}")
                # Don't retry on client errors (4xx except 429)
                if 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                    raise
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"HTTP error ({e.response.status_code}), retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                raise
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Request error: {str(e)}, retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue

        raise Exception(f"API request failed after {max_retries} attempts: {str(last_error)}")

    # =========================================================================
    # Market Data Endpoints
    # =========================================================================

    async def get_markets(self, status: str = "open", limit: int = 200, cursor: Optional[str] = None, **kwargs) -> Dict:
        """Get markets with given status."""
        params = f"?status={status}&limit={limit}"
        if cursor:
            params += f"&cursor={cursor}"
        
        # Add any additional filters (e.g. series_ticker, tickers, event_ticker)
        for k, v in kwargs.items():
            params += f"&{k}={v}"
            
        return await self._authenticated_request("GET", f"/markets{params}")
        return await self._authenticated_request("GET", f"/markets{params}")

    async def get_market(self, ticker: str) -> Dict:
        """Get details for a specific market by ticker."""
        return await self._authenticated_request("GET", f"/markets/{ticker}")

    async def get_market_history(
        self,
        ticker: str,
        limit: int = 100,
        cursor: Optional[str] = None
    ) -> Dict:
        """Get historical candlestick data for a market."""
        params = f"?limit={limit}"
        if cursor:
            params += f"&cursor={cursor}"
        return await self._authenticated_request("GET", f"/markets/{ticker}/history{params}")

    # =========================================================================
    # Portfolio Endpoints
    # =========================================================================

    async def get_balance(self) -> Dict:
        """
        Get current account balance.
        Normalizes Kalshi's cent-based values to USD dollars (float).
        """
        data = await self._authenticated_request("GET", "/portfolio/balance")
        
        # Convert cents to dollars
        if "balance" in data:
            data["balance"] = float(data["balance"]) / 100.0
        if "available_balance" in data:
            data["available_balance"] = float(data["available_balance"]) / 100.0
            
        return data

    async def get_positions(self, status: str = "open") -> Dict:
        """
        Get current positions.
        Normalizes cost basis and PnL values from cents to dollars.
        """
        data = await self._authenticated_request("GET", f"/portfolio/positions?status={status}")
        
        # Normalize positions if present
        positions = data.get("positions", [])
        for pos in positions:
            # Convert known cent fields to dollars
            for field in ["fees", "cost_basis", "realized_pnl", "market_exposure"]:
                if field in pos and pos[field] is not None:
                    pos[field] = float(pos[field]) / 100.0
        
        return data

    async def get_settlements(self, limit: int = 100, cursor: Optional[str] = None) -> Dict:
        """Get settled positions."""
        params = f"?limit={limit}"
        if cursor:
            params += f"&cursor={cursor}"
        return await self._authenticated_request("GET", f"/portfolio/settlements{params}")

    async def get_fills(
        self,
        ticker: Optional[str] = None,
        limit: int = 100,
        cursor: Optional[str] = None
    ) -> Dict:
        """Get order fill history."""
        params = f"?limit={limit}"
        if ticker:
            params += f"&ticker={ticker}"
        if cursor:
            params += f"&cursor={cursor}"
        return await self._authenticated_request("GET", f"/portfolio/fills{params}")

    # =========================================================================
    # Order Endpoints (all under /portfolio/orders per 2026 API)
    # =========================================================================

    async def place_order(
        self,
        ticker: str,
        side: str,
        yes_no: str,
        price: float,
        size: int,
        client_order_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict:
        """Place a new order on Kalshi.

        Args:
            ticker: Market ticker symbol (e.g. "KXNBA-26FEB02-LAL-BOS")
            side: "buy" or "sell"
            yes_no: Contract side - "yes" or "no"
            price: Price in 0-1 range (will be converted to cents) or in cents 1-99
            size: Number of contracts to trade
            client_order_id: Optional idempotency key (UUID recommended)
        """
        # Convert price to cents if in 0-1 decimal range
        if price <= 1.0:
            price_cents = max(1, min(99, int(price * 100)))
        else:
            price_cents = max(1, min(99, int(price)))

        payload: Dict[str, Any] = {
            "ticker": ticker,
            "action": side.lower(),
            "side": yes_no.lower(),
            "count": int(size),
            "type": "limit",
            "yes_price": price_cents,
        }

        if client_order_id:
            payload["client_order_id"] = client_order_id
        else:
            payload["client_order_id"] = str(uuid_mod.uuid4())

        logger.info(f"Placing order: {payload['action']} {payload['count']}x {ticker} {payload['side']} @ {price_cents}c")

        response = await self._authenticated_request(
            "POST",
            "/portfolio/orders",
            json=payload
        )

        order_data = response.get("order", response)
        order_id = order_data.get("order_id", "")
        logger.info(f"Order placed: {order_id}")
        return response

    async def cancel_order(self, order_id: str) -> Dict:
        """Cancel an existing order."""
        return await self._authenticated_request(
            "DELETE",
            f"/portfolio/orders/{order_id}"
        )

    async def get_order_status(self, order_id: str) -> Dict:
        """Get status of a specific order."""
        return await self._authenticated_request(
            "GET",
            f"/portfolio/orders/{order_id}"
        )

    async def get_open_orders(self, ticker: Optional[str] = None) -> Dict:
        """Get open orders, optionally filtered by ticker."""
        params = ""
        if ticker:
            params = f"?ticker={ticker}"
        return await self._authenticated_request(
            "GET",
            f"/portfolio/orders{params}"
        )

    async def batch_orders(
        self,
        orders: List[Dict[str, Any]]
    ) -> Dict:
        """Place multiple orders in a single request."""
        return await self._authenticated_request(
            "POST",
            "/portfolio/orders/batched",
            json={"orders": orders}
        )

    # =========================================================================
    # Order fill monitoring
    # =========================================================================

    async def wait_for_fill(self, order_id: str, timeout: int = 60) -> str:
        """
        Poll order status until filled or timeout.

        Args:
            order_id: The order ID to monitor
            timeout: Maximum seconds to wait

        Returns:
            Final status string: "filled", "canceled", "timeout", or other status
        """
        start = time.time()
        poll_interval = 1.0

        while time.time() - start < timeout:
            try:
                resp = await self.get_order_status(order_id)
                order = resp.get("order", resp)
                status = order.get("status", "")

                if status in ("executed", "filled"):
                    return "filled"
                if status in ("canceled", "cancelled"):
                    return "canceled"
                if status in ("expired",):
                    return "expired"
            except Exception as e:
                logger.warning(f"Error polling order {order_id}: {e}")

            await asyncio.sleep(poll_interval)
            # Increase interval over time
            poll_interval = min(poll_interval * 1.5, 5.0)

        logger.warning(f"Order {order_id} fill timeout after {timeout}s")
        return "timeout"

    # =========================================================================
    # Slippage check
    # =========================================================================

    async def check_slippage(
        self,
        ticker: str,
        expected_price: float,
        side: str = "buy",
        max_slippage: float = 0.02
    ) -> Tuple[bool, float]:
        """
        Check if current market price is within acceptable slippage of expected price.

        Args:
            ticker: Market ticker to check
            expected_price: Price we expect to trade at (0-1 range)
            side: "buy" or "sell"
            max_slippage: Maximum acceptable slippage (default 2%)

        Returns:
            Tuple of (slippage_acceptable, actual_slippage)
        """
        try:
            market_data = await self.get_market(ticker)
            market = market_data.get("market", market_data)

            # Use dollar-denominated fields per 2026 API
            if side.lower() == "buy":
                current_price = market.get("yes_ask_dollars", market.get("yes_ask", 0))
            else:
                current_price = market.get("yes_bid_dollars", market.get("yes_bid", 0))

            if not current_price:
                return True, 0.0

            # Convert cents to dollars if needed
            if isinstance(current_price, (int, float)) and current_price > 1:
                current_price = current_price / 100.0

            if expected_price <= 0:
                return True, 0.0

            slippage = abs(current_price - expected_price) / expected_price
            return slippage <= max_slippage, slippage

        except Exception as e:
            logger.warning(f"Slippage check failed for {ticker}: {e}")
            return True, 0.0

    # =========================================================================
    # Connection test
    # =========================================================================

    async def test_connection(self) -> bool:
        """Test API connectivity by fetching balance."""
        try:
            await self.get_balance()
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            return False

    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()
