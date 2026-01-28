"""
Polymarket CLOB API client implementation.
Handles L1/L2 authentication and all trading operations.
Includes retry logic with circuit breakers for resilience.
Supports paper trading mode for safe testing.
Implements idempotency key generation to prevent duplicate orders.
"""

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
import time

import httpx
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType

from src.core.exceptions import PolymarketAPIError, InsufficientBalanceError
from src.core.retry import retry_async, polymarket_circuit


logger = logging.getLogger(__name__)


def generate_idempotency_key(
    token_id: str,
    side: str,
    price: float,
    size: float,
    timestamp_window: int = 5
) -> str:
    """
    Generates an idempotency key for order placement.
    
    Uses a time-windowed approach where identical orders within the
    same time window will have the same idempotency key, preventing
    accidental duplicate orders from retries or double-clicks.
    
    Args:
        token_id: Token being traded
        side: BUY or SELL
        price: Order price
        size: Order size
        timestamp_window: Time window in seconds (default 5s)
    
    Returns:
        SHA-256 hash of order parameters with timestamp window
    """
    timestamp_bucket = int(time.time() // timestamp_window) * timestamp_window
    order_data = f"{token_id}:{side}:{price}:{size}:{timestamp_bucket}"
    return hashlib.sha256(order_data.encode()).hexdigest()[:32]


class PolymarketClient:
    """
    Async wrapper around Polymarket CLOB API.
    Supports both L1 (wallet signature) and L2 (HMAC) authentication.
    """
    
    CLOB_HOST = "https://clob.polymarket.com"
    GAMMA_HOST = "https://gamma-api.polymarket.com"
    CHAIN_ID = 137
    
    def __init__(
        self,
        private_key: str,
        funder_address: str,
        api_key: str | None = None,
        api_secret: str | None = None,
        passphrase: str | None = None,
        dry_run: bool = False,
        max_slippage: float = 0.02
    ):
        """
        Initializes the Polymarket client.
        
        Args:
            private_key: Wallet private key for L1 auth
            funder_address: Address holding USDC funds
            api_key: Optional API key for L2 auth
            api_secret: Optional API secret for L2 auth
            passphrase: Optional passphrase for L2 auth
            dry_run: If True, simulate orders without executing
            max_slippage: Maximum acceptable slippage (0.02 = 2%)
        """
        self.private_key = private_key
        self.funder_address = funder_address
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.dry_run = dry_run
        self.max_slippage = max_slippage
        
        self._clob_client: ClobClient | None = None
        self._http_client: httpx.AsyncClient | None = None
        
        # Track simulated orders for paper trading
        self._simulated_orders: dict[str, dict] = {}
        self._simulated_order_counter: int = 0
        
        # Track recently submitted idempotency keys to prevent duplicates
        # Key: idempotency_key, Value: (timestamp, order_result)
        self._recent_orders: dict[str, tuple[float, dict]] = {}
        self._idempotency_ttl: int = 60  # seconds to keep idempotency keys
    
    async def _get_clob_client(self) -> ClobClient:
        """
        Lazily initializes the CLOB client with appropriate auth.
        """
        if self._clob_client is None:
            if self.api_key and self.api_secret and self.passphrase:
                creds = {
                    "apiKey": self.api_key,
                    "secret": self.api_secret,
                    "passphrase": self.passphrase
                }
                self._clob_client = ClobClient(
                    host=self.CLOB_HOST,
                    chain_id=self.CHAIN_ID,
                    key=self.private_key,
                    creds=creds,
                    signature_type=1,
                    funder=self.funder_address
                )
            else:
                self._clob_client = ClobClient(
                    host=self.CLOB_HOST,
                    chain_id=self.CHAIN_ID,
                    key=self.private_key
                )
        return self._clob_client
    
    async def _get_http_client(self) -> httpx.AsyncClient:
        """
        Returns reusable async HTTP client.
        """
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client
    
    async def derive_api_credentials(self) -> dict[str, str]:
        """
        Derives API credentials using L1 authentication.
        These credentials can then be used for L2 authentication.
        
        Returns:
            Dictionary with apiKey, secret, and passphrase
        """
        client = await self._get_clob_client()
        
        loop = asyncio.get_event_loop()
        creds = await loop.run_in_executor(None, client.derive_api_key)
        
        self.api_key = creds.api_key
        self.api_secret = creds.api_secret
        self.passphrase = creds.api_passphrase
        
        self._clob_client = None
        
        return {
            "api_key": creds.api_key,
            "api_secret": creds.api_secret,
            "passphrase": creds.api_passphrase
        }
    
    async def get_balance(self) -> Decimal:
        """
        Fetches USDC balance for the funder address.
        Uses retry logic with circuit breaker for resilience.
        
        Returns:
            Balance in USDC as Decimal
        """
        try:
            http = await self._get_http_client()
            
            response = await retry_async(
                http.get,
                f"{self.CLOB_HOST}/balance",
                params={"address": self.funder_address},
                max_retries=3,
                circuit_breaker=polymarket_circuit
            )
            response.raise_for_status()
            
            data = response.json()
            logger.debug(f"Balance fetched: {data.get('balance', 0)} USDC")
            return Decimal(str(data.get("balance", 0)))
            
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch balance: {e}")
            raise PolymarketAPIError(f"Failed to fetch balance: {str(e)}")
    
    async def get_midpoint_price(self, token_id: str) -> float:
        """
        Fetches current midpoint price for a token.
        Uses retry logic with circuit breaker for resilience.
        
        Args:
            token_id: The token ID to get price for
        
        Returns:
            Midpoint price as float
        """
        try:
            http = await self._get_http_client()
            
            response = await retry_async(
                http.get,
                f"{self.CLOB_HOST}/midpoint",
                params={"token_id": token_id},
                max_retries=3,
                circuit_breaker=polymarket_circuit
            )
            response.raise_for_status()
            
            data = response.json()
            return float(data.get("mid", 0))
            
        except httpx.HTTPError as e:
            logger.warning(f"Failed to fetch midpoint for {token_id}: {e}")
            raise PolymarketAPIError(f"Failed to fetch midpoint: {str(e)}")
    
    async def get_orderbook(self, token_id: str) -> dict[str, Any]:
        """
        Fetches full orderbook for a token.
        Uses retry logic with circuit breaker for resilience.
        
        Returns:
            Dictionary with bids and asks arrays
        """
        try:
            http = await self._get_http_client()
            
            response = await retry_async(
                http.get,
                f"{self.CLOB_HOST}/book",
                params={"token_id": token_id},
                max_retries=3,
                circuit_breaker=polymarket_circuit
            )
            response.raise_for_status()
            
            return response.json()
            
        except httpx.HTTPError as e:
            logger.warning(f"Failed to fetch orderbook for {token_id}: {e}")
            raise PolymarketAPIError(f"Failed to fetch orderbook: {str(e)}")
    
    async def place_order(
        self,
        token_id: str,
        side: str,
        price: float,
        size: float,
        order_type: str = "GTC"
    ) -> dict[str, Any]:
        """
        Places an order on Polymarket (or simulates in dry_run mode).
        
        Uses idempotency key generation to prevent duplicate orders from
        retries or accidental double-submissions within a short time window.
        
        Args:
            token_id: Token ID to trade
            side: "BUY" or "SELL"
            price: Limit price (0.0 to 1.0)
            size: Number of contracts
            order_type: Order type (GTC, GTD, FOK)
        
        Returns:
            Order response from API
        """
        # Paper trading mode - simulate the order
        if self.dry_run:
            return await self._simulate_order(token_id, side, price, size, order_type)
        
        # Generate idempotency key for this order
        idempotency_key = generate_idempotency_key(token_id, side, price, size)
        
        # Clean up expired idempotency keys
        current_time = time.time()
        expired_keys = [
            k for k, (ts, _) in self._recent_orders.items()
            if current_time - ts > self._idempotency_ttl
        ]
        for key in expired_keys:
            del self._recent_orders[key]
        
        # Check if we've recently submitted this exact order
        if idempotency_key in self._recent_orders:
            ts, cached_result = self._recent_orders[idempotency_key]
            logger.warning(
                f"Duplicate order detected (idempotency_key={idempotency_key[:8]}...). "
                f"Returning cached result from {current_time - ts:.1f}s ago."
            )
            return cached_result
        
        if not all([self.api_key, self.api_secret, self.passphrase]):
            creds = await self.derive_api_credentials()
        
        try:
            client = await self._get_clob_client()
            
            order_args = OrderArgs(
                token_id=token_id,
                price=price,
                size=size,
                side=side.upper(),
            )
            
            loop = asyncio.get_event_loop()
            
            if order_type == "GTC":
                result = await loop.run_in_executor(
                    None,
                    lambda: client.create_and_post_order(order_args)
                )
            else:
                result = await loop.run_in_executor(
                    None,
                    lambda: client.create_and_post_order(order_args)
                )
            
            logger.info(
                f"Order placed: {side} {size} @ {price} for token {token_id[:16]}..."
            )
            order_result = {"id": result.get("orderID"), "status": "created", "raw": result}
            
            # Cache the result with idempotency key
            self._recent_orders[idempotency_key] = (time.time(), order_result)
            
            return order_result
            
        except Exception as e:
            error_str = str(e).lower()
            logger.error(f"Order placement failed: {e}")
            if "insufficient" in error_str or "balance" in error_str:
                raise InsufficientBalanceError(f"Insufficient balance: {str(e)}")
            raise PolymarketAPIError(f"Failed to place order: {str(e)}")
    
    async def _simulate_order(
        self,
        token_id: str,
        side: str,
        price: float,
        size: float,
        order_type: str
    ) -> dict[str, Any]:
        """
        Simulates an order for paper trading mode.
        
        Args:
            token_id: Token ID to trade
            side: "BUY" or "SELL"
            price: Limit price
            size: Number of contracts
            order_type: Order type
        
        Returns:
            Simulated order response
        """
        self._simulated_order_counter += 1
        order_id = f"DRY_RUN_{self._simulated_order_counter:06d}"
        
        order = {
            "id": order_id,
            "token_id": token_id,
            "side": side.upper(),
            "price": price,
            "size": size,
            "order_type": order_type,
            "status": "FILLED",  # Assume immediate fill for simulation
            "filled_size": size,
            "filled_price": price,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "is_simulated": True
        }
        
        self._simulated_orders[order_id] = order
        
        logger.info(
            f"[DRY RUN] Simulated order: {side} {size} @ {price} "
            f"for token {token_id[:16]}... (order_id={order_id})"
        )
        
        return {"id": order_id, "status": "FILLED", "is_simulated": True, "raw": order}
    
    async def get_order_status(self, order_id: str) -> dict[str, Any]:
        """
        Gets the current status of an order.
        
        Args:
            order_id: Order ID to check
        
        Returns:
            Order status dictionary
        """
        # Check simulated orders first
        if order_id.startswith("DRY_RUN_"):
            return self._simulated_orders.get(order_id, {"status": "NOT_FOUND"})
        
        try:
            client = await self._get_clob_client()
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: client.get_order(order_id)
            )
            
            return result
            
        except Exception as e:
            logger.warning(f"Failed to get order status for {order_id}: {e}")
            return {"status": "ERROR", "error": str(e)}

    async def get_order(self, order_id: str) -> dict[str, Any]:
        """
        Gets full order details by ID.
        
        Args:
            order_id: Order ID to retrieve
        
        Returns:
            Order details dictionary
        """
        return await self.get_order_status(order_id)
    
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
        if order_id.startswith("DRY_RUN_"):
            return self._simulated_orders.get(order_id, {"status": "FILLED"})
        
        import time
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = await self.get_order_status(order_id)
            
            if status.get("status") in ("FILLED", "CANCELLED", "EXPIRED", "REJECTED"):
                logger.info(f"Order {order_id} final status: {status.get('status')}")
                return status
            
            await asyncio.sleep(poll_interval)
        
        logger.warning(f"Order {order_id} timed out after {timeout}s")
        return {"status": "TIMEOUT", "order_id": order_id}
    
    async def check_slippage(
        self,
        token_id: str,
        expected_price: float,
        side: str
    ) -> tuple[bool, float]:
        """
        Check if current market price is within acceptable slippage.
        
        Args:
            token_id: Token to check
            expected_price: Price we expected to trade at
            side: "BUY" or "SELL"
        
        Returns:
            Tuple of (is_acceptable, actual_price)
        """
        try:
            prices = await self.get_midpoint_price(token_id)
            actual_price = prices if isinstance(prices, float) else prices.get("mid", expected_price)
            
            if side.upper() == "BUY":
                slippage = (actual_price - expected_price) / expected_price
            else:
                slippage = (expected_price - actual_price) / expected_price
            
            is_acceptable = slippage <= self.max_slippage
            
            if not is_acceptable:
                logger.warning(
                    f"Slippage too high: {slippage:.2%} > {self.max_slippage:.2%} "
                    f"(expected={expected_price}, actual={actual_price})"
                )
            
            return is_acceptable, actual_price
            
        except Exception as e:
            logger.error(f"Error checking slippage: {e}")
            return True, expected_price  # Allow trade on error
    
    async def cancel_order(self, order_id: str) -> dict[str, Any]:
        """
        Cancels an existing order.
        
        Args:
            order_id: The order ID to cancel
        
        Returns:
            Cancellation response
        """
        try:
            client = await self._get_clob_client()
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: client.cancel(order_id)
            )
            
            return {"success": True, "raw": result}
            
        except Exception as e:
            raise PolymarketAPIError(f"Failed to cancel order: {str(e)}")
    
    async def get_open_orders(self) -> list[dict[str, Any]]:
        """
        Fetches all open orders for the user.
        
        Returns:
            List of open orders
        """
        try:
            client = await self._get_clob_client()
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                client.get_orders
            )
            
            return result if isinstance(result, list) else []
            
        except Exception as e:
            raise PolymarketAPIError(f"Failed to fetch orders: {str(e)}")
    
    async def get_positions(self) -> list[dict[str, Any]]:
        """
        Fetches all positions for the user.
        Uses retry logic with circuit breaker for resilience.
        
        Returns:
            List of positions with token_id and size
        """
        try:
            http = await self._get_http_client()
            
            response = await retry_async(
                http.get,
                f"{self.GAMMA_HOST}/positions",
                params={"user": self.funder_address},
                max_retries=3,
                circuit_breaker=polymarket_circuit
            )
            response.raise_for_status()
            
            return response.json()
            
        except httpx.HTTPError as e:
            logger.warning(f"Failed to fetch positions: {e}")
            raise PolymarketAPIError(f"Failed to fetch positions: {str(e)}")
    
    async def get_sports_markets(self, sport: str | None = None) -> list[dict[str, Any]]:
        """
        Fetches active sports markets from Gamma API.
        Uses retry logic with circuit breaker for resilience.
        
        Args:
            sport: Optional sport filter (e.g., "nba", "nfl")
        
        Returns:
            List of market data dictionaries
        """
        try:
            http = await self._get_http_client()
            
            params = {"active": "true", "closed": "false"}
            if sport:
                params["tag"] = sport.upper()
            
            response = await retry_async(
                http.get,
                f"{self.GAMMA_HOST}/markets",
                params=params,
                max_retries=3,
                circuit_breaker=polymarket_circuit
            )
            response.raise_for_status()
            
            logger.debug(f"Fetched sports markets, sport={sport}")
            return response.json()
            
        except httpx.HTTPError as e:
            logger.warning(f"Failed to fetch markets: {e}")
            raise PolymarketAPIError(f"Failed to fetch markets: {str(e)}")
    
    async def close(self) -> None:
        """
        Closes HTTP client connections.
        """
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
