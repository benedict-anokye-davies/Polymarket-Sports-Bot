"""
Kalshi API client implementation.
Handles authentication and all trading operations for Kalshi markets.
Supports paper trading mode for safe testing.
"""

import asyncio
import logging
import hmac
import hashlib
import base64
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import httpx

from src.core.exceptions import KalshiAPIError, InsufficientBalanceError
from src.core.retry import retry_async


logger = logging.getLogger(__name__)


class KalshiClient:
    """
    Async client for Kalshi REST API.
    Handles HMAC authentication for API access.
    """

    API_HOST = "https://trading-api.kalshi.com/trade-api/v2"
    DEMO_HOST = "https://demo-api.kalshi.co/trade-api/v2"

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        use_demo: bool = False,
        dry_run: bool = False,
        max_slippage: float = 0.02
    ):
        """
        Initializes the Kalshi client.

        Args:
            api_key: Kalshi API key
            api_secret: Kalshi API secret (private key)
            use_demo: If True, use demo API endpoint
            dry_run: If True, simulate orders without executing
            max_slippage: Maximum acceptable slippage (0.02 = 2%)
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = self.DEMO_HOST if use_demo else self.API_HOST
        self.dry_run = dry_run
        self.max_slippage = max_slippage

        self._http_client: httpx.AsyncClient | None = None

        # Track simulated orders for paper trading
        self._simulated_orders: dict[str, dict] = {}
        self._simulated_order_counter: int = 0

    def _generate_signature(self, timestamp: str, method: str, path: str, body: str = "") -> str:
        """
        Generate HMAC signature for Kalshi API authentication.

        Args:
            timestamp: Unix timestamp in milliseconds
            method: HTTP method (GET, POST, DELETE)
            path: API path (e.g., /trade-api/v2/portfolio/balance)
            body: Request body (empty string for GET)

        Returns:
            Base64-encoded HMAC signature
        """
        message = f"{timestamp}{method}{path}{body}"
        signature = hmac.new(
            base64.b64decode(self.api_secret),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        return base64.b64encode(signature).decode('utf-8')

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Returns reusable async HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: dict | None = None,
        params: dict | None = None
    ) -> dict[str, Any]:
        """
        Make authenticated request to Kalshi API.

        Args:
            method: HTTP method
            endpoint: API endpoint (without base URL)
            data: Request body for POST/PUT
            params: Query parameters

        Returns:
            Response JSON as dict
        """
        http = await self._get_http_client()

        timestamp = str(int(datetime.now(timezone.utc).timestamp() * 1000))
        path = f"/trade-api/v2{endpoint}"
        body = "" if data is None else str(data)

        signature = self._generate_signature(timestamp, method.upper(), path, body)

        headers = {
            "KALSHI-ACCESS-KEY": self.api_key,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "Content-Type": "application/json"
        }

        url = f"{self.base_url}{endpoint}"

        try:
            response = await retry_async(
                http.request,
                method,
                url,
                headers=headers,
                json=data,
                params=params,
                max_retries=3
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            error_detail = e.response.text if e.response else str(e)
            logger.error(f"Kalshi API error: {error_detail}")
            raise KalshiAPIError(f"Kalshi API error: {error_detail}")
        except httpx.HTTPError as e:
            logger.error(f"HTTP error: {e}")
            raise KalshiAPIError(f"HTTP error: {str(e)}")

    async def get_balance(self) -> Decimal:
        """
        Fetches account balance.

        Returns:
            Balance in USD as Decimal
        """
        try:
            response = await self._request("GET", "/portfolio/balance")
            balance = response.get("balance", 0) / 100  # Kalshi returns cents
            logger.debug(f"Balance fetched: ${balance:.2f}")
            return Decimal(str(balance))
        except Exception as e:
            logger.error(f"Failed to fetch balance: {e}")
            raise KalshiAPIError(f"Failed to fetch balance: {str(e)}")

    async def get_positions(self) -> list[dict[str, Any]]:
        """
        Fetches all open positions.

        Returns:
            List of position dictionaries
        """
        try:
            response = await self._request("GET", "/portfolio/positions")
            return response.get("market_positions", [])
        except Exception as e:
            logger.error(f"Failed to fetch positions: {e}")
            raise KalshiAPIError(f"Failed to fetch positions: {str(e)}")

    async def get_markets(
        self,
        status: str = "open",
        series_ticker: str | None = None,
        event_ticker: str | None = None,
        limit: int = 100
    ) -> list[dict[str, Any]]:
        """
        Fetches markets from Kalshi.

        Args:
            status: Market status filter (open, closed, settled)
            series_ticker: Filter by series
            event_ticker: Filter by event
            limit: Max markets to return

        Returns:
            List of market data dictionaries
        """
        params = {"status": status, "limit": limit}
        if series_ticker:
            params["series_ticker"] = series_ticker
        if event_ticker:
            params["event_ticker"] = event_ticker

        try:
            response = await self._request("GET", "/markets", params=params)
            return response.get("markets", [])
        except Exception as e:
            logger.error(f"Failed to fetch markets: {e}")
            raise KalshiAPIError(f"Failed to fetch markets: {str(e)}")

    async def get_sports_markets(self, sport: str | None = None) -> list[dict[str, Any]]:
        """
        Fetches active sports betting markets.
        Maps sport names to Kalshi series tickers.

        Args:
            sport: Sport filter (nba, nfl, mlb, nhl, soccer, etc.)

        Returns:
            List of market data dictionaries
        """
        # Map sports to Kalshi series tickers
        sport_series = {
            "nba": "NBA",
            "nfl": "NFL",
            "mlb": "MLB",
            "nhl": "NHL",
            "soccer": "SOCCER",
            "mma": "UFC",
            "tennis": "TENNIS",
            "golf": "GOLF",
            "ncaab": "NCAAB",
            "ncaaf": "NCAAF",
        }

        series_ticker = sport_series.get(sport.lower()) if sport else None

        try:
            markets = await self.get_markets(status="open", series_ticker=series_ticker)
            return markets
        except Exception as e:
            logger.error(f"Failed to fetch sports markets: {e}")
            return []

    async def get_market(self, ticker: str) -> dict[str, Any]:
        """
        Gets details for a specific market.

        Args:
            ticker: Market ticker

        Returns:
            Market data dictionary
        """
        try:
            response = await self._request("GET", f"/markets/{ticker}")
            return response.get("market", {})
        except Exception as e:
            logger.error(f"Failed to fetch market {ticker}: {e}")
            raise KalshiAPIError(f"Failed to fetch market: {str(e)}")

    async def get_orderbook(self, ticker: str) -> dict[str, Any]:
        """
        Fetches orderbook for a market.

        Args:
            ticker: Market ticker

        Returns:
            Orderbook with yes/no sides and bids/asks
        """
        try:
            response = await self._request("GET", f"/markets/{ticker}/orderbook")
            return response.get("orderbook", {})
        except Exception as e:
            logger.error(f"Failed to fetch orderbook for {ticker}: {e}")
            raise KalshiAPIError(f"Failed to fetch orderbook: {str(e)}")

    async def get_midpoint_price(self, ticker: str) -> float:
        """
        Gets current midpoint price for a market (YES side).

        Args:
            ticker: Market ticker

        Returns:
            Midpoint price as float (0-1)
        """
        try:
            orderbook = await self.get_orderbook(ticker)
            yes_bids = orderbook.get("yes", {}).get("bids", [])
            yes_asks = orderbook.get("yes", {}).get("asks", [])

            best_bid = yes_bids[0]["price"] / 100 if yes_bids else 0.5
            best_ask = yes_asks[0]["price"] / 100 if yes_asks else 0.5

            return (best_bid + best_ask) / 2
        except Exception as e:
            logger.warning(f"Failed to get midpoint for {ticker}: {e}")
            return 0.5

    async def place_order(
        self,
        ticker: str,
        side: str,
        price: float,
        size: int,
        order_type: str = "limit"
    ) -> dict[str, Any]:
        """
        Places an order on Kalshi (or simulates in dry_run mode).

        Args:
            ticker: Market ticker
            side: "yes" or "no"
            price: Limit price in dollars (0.01 to 0.99)
            size: Number of contracts
            order_type: "limit" or "market"

        Returns:
            Order response from API
        """
        # Paper trading mode - simulate the order
        if self.dry_run:
            return await self._simulate_order(ticker, side, price, size, order_type)

        try:
            data = {
                "ticker": ticker,
                "side": side.lower(),
                "type": order_type,
                "count": size,
            }

            if order_type == "limit":
                data["yes_price"] = int(price * 100)  # Convert to cents

            response = await self._request("POST", "/portfolio/orders", data=data)

            order = response.get("order", {})
            logger.info(
                f"Order placed: {side} {size} @ ${price:.2f} for {ticker}"
            )

            return {
                "id": order.get("order_id"),
                "status": order.get("status", "created"),
                "raw": order
            }
        except Exception as e:
            error_str = str(e).lower()
            logger.error(f"Order placement failed: {e}")
            if "insufficient" in error_str or "balance" in error_str:
                raise InsufficientBalanceError(f"Insufficient balance: {str(e)}")
            raise KalshiAPIError(f"Failed to place order: {str(e)}")

    async def _simulate_order(
        self,
        ticker: str,
        side: str,
        price: float,
        size: int,
        order_type: str
    ) -> dict[str, Any]:
        """
        Simulates an order for paper trading mode.

        Returns:
            Simulated order response
        """
        self._simulated_order_counter += 1
        order_id = f"KALSHI_DRY_{self._simulated_order_counter:06d}"

        order = {
            "id": order_id,
            "ticker": ticker,
            "side": side.lower(),
            "price": price,
            "count": size,
            "order_type": order_type,
            "status": "filled",
            "filled_count": size,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "is_simulated": True
        }

        self._simulated_orders[order_id] = order

        logger.info(
            f"[DRY RUN] Simulated Kalshi order: {side} {size} @ ${price:.2f} "
            f"for {ticker} (order_id={order_id})"
        )

        return {"id": order_id, "status": "filled", "is_simulated": True, "raw": order}

    async def get_order_status(self, order_id: str) -> dict[str, Any]:
        """
        Gets the current status of an order.

        Args:
            order_id: Order ID to check

        Returns:
            Order status dictionary
        """
        # Check simulated orders first
        if order_id.startswith("KALSHI_DRY_"):
            return self._simulated_orders.get(order_id, {"status": "not_found"})

        try:
            response = await self._request("GET", f"/portfolio/orders/{order_id}")
            return response.get("order", {})
        except Exception as e:
            logger.warning(f"Failed to get order status for {order_id}: {e}")
            return {"status": "error", "error": str(e)}

    async def cancel_order(self, order_id: str) -> dict[str, Any]:
        """
        Cancels an existing order.

        Args:
            order_id: The order ID to cancel

        Returns:
            Cancellation response
        """
        try:
            response = await self._request("DELETE", f"/portfolio/orders/{order_id}")
            return {"success": True, "raw": response}
        except Exception as e:
            raise KalshiAPIError(f"Failed to cancel order: {str(e)}")

    async def check_slippage(
        self,
        ticker: str,
        expected_price: float,
        side: str
    ) -> tuple[bool, float]:
        """
        Check if current market price is within acceptable slippage.

        Args:
            ticker: Market ticker to check
            expected_price: Price we expected to trade at
            side: "yes" or "no"

        Returns:
            Tuple of (is_acceptable, actual_price)
        """
        try:
            actual_price = await self.get_midpoint_price(ticker)

            if side.lower() == "yes":
                slippage = (actual_price - expected_price) / expected_price if expected_price > 0 else 0
            else:
                slippage = (expected_price - actual_price) / expected_price if expected_price > 0 else 0

            is_acceptable = abs(slippage) <= self.max_slippage

            if not is_acceptable:
                logger.warning(
                    f"Slippage too high: {slippage:.2%} > {self.max_slippage:.2%} "
                    f"(expected={expected_price:.4f}, actual={actual_price:.4f})"
                )

            return is_acceptable, actual_price
        except Exception as e:
            logger.error(f"Error checking slippage: {e}")
            return True, expected_price  # Allow trade on error

    async def wait_for_fill(
        self,
        order_id: str,
        timeout: int = 60,
        poll_interval: float = 2.0
    ) -> dict[str, Any]:
        """
        Wait for an order to be filled or timeout.

        Args:
            order_id: Order ID to monitor
            timeout: Maximum seconds to wait
            poll_interval: Seconds between status checks

        Returns:
            Final order status
        """
        # Simulated orders are instantly filled
        if order_id.startswith("KALSHI_DRY_"):
            return self._simulated_orders.get(order_id, {"status": "filled"})

        import time
        start_time = time.time()

        while time.time() - start_time < timeout:
            status = await self.get_order_status(order_id)

            order_status = status.get("status", "").lower()
            if order_status in ("filled", "cancelled", "expired", "rejected"):
                logger.info(f"Order {order_id} final status: {order_status}")
                return status

            await asyncio.sleep(poll_interval)

        logger.warning(f"Order {order_id} timed out after {timeout}s")
        return {"status": "timeout", "order_id": order_id}

    async def close(self) -> None:
        """Closes HTTP client connections."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
