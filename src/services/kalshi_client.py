"""
Kalshi API Client for Sports Trading
Implements RSA-signed authentication and order management.
"""

import base64
import json
import logging
import time
from typing import Optional, Dict, List, Any, cast
from datetime import datetime, timezone
from dataclasses import dataclass
import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from cryptography.hazmat.backends import default_backend

from src.core.exceptions import TradingError, RateLimitError


logger = logging.getLogger(__name__)


# Kalshi API Base URLs
KALSHI_API_BASE_PRODUCTION = "https://api.elections.kalshi.com/trade-api/v2"
KALSHI_API_BASE_DEMO = "https://demo-api.kalshi.co/trade-api/v2"
KALSHI_WS_URL_PRODUCTION = "wss://api.elections.kalshi.com/trade-api/v2/ws"
KALSHI_WS_URL_DEMO = "wss://demo-api.kalshi.co/trade-api/v2/ws"

# Legacy alias for backwards compatibility
KALSHI_API_BASE = KALSHI_API_BASE_PRODUCTION
KALSHI_WS_URL = KALSHI_WS_URL_PRODUCTION


@dataclass
class KalshiOrder:
    """Represents a Kalshi order response"""
    order_id: str
    ticker: str
    side: str
    yes_no: str
    price: float
    size: int
    status: str
    filled_size: int
    created_at: datetime


@dataclass
class KalshiMarket:
    """Represents a Kalshi market"""
    ticker: str
    event_ticker: str
    title: str
    status: str
    yes_price: float
    no_price: float
    volume_yes: int
    volume_no: int
    close_ts: int
    event_start_ts: int


class KalshiAuthenticator:
    """
    Handles RSA-signed authentication for Kalshi API requests.
    Kalshi uses custom headers with RSA-SHA256 signatures.
    """
    
    def __init__(self, api_key_id: str, private_key_pem: str):
        """
        Initialize authenticator with API key and private key.
        
        Args:
            api_key_id: Kalshi API key ID from dashboard
            private_key_pem: RSA private key in PEM format (string)
        
        Raises:
            TradingError: If API key is empty or private key is invalid PEM format
        """
        if not api_key_id or not api_key_id.strip():
            raise TradingError(
                "Kalshi API key is required. Please provide a valid API key from your Kalshi dashboard."
            )
        
        if not private_key_pem or not private_key_pem.strip():
            raise TradingError(
                "Kalshi private key is required. Please provide your RSA private key in PEM format."
            )
        
        self.api_key_id = api_key_id.strip()
        
        try:
            key_bytes = private_key_pem.encode() if isinstance(private_key_pem, str) else private_key_pem
            loaded_key = serialization.load_pem_private_key(
                key_bytes,
                password=None,
                backend=default_backend()
            )
            # Kalshi requires RSA keys specifically
            if not isinstance(loaded_key, RSAPrivateKey):
                raise TradingError(
                    "Kalshi requires an RSA private key. The provided key is not an RSA key."
                )
            self.private_key: RSAPrivateKey = loaded_key
        except ValueError as e:
            raise TradingError(
                f"Invalid RSA private key format. The key must be in PEM format "
                f"(starting with '-----BEGIN RSA PRIVATE KEY-----' or '-----BEGIN PRIVATE KEY-----'). "
                f"Error: {str(e)}"
            )
        except Exception as e:
            raise TradingError(
                f"Failed to load RSA private key: {str(e)}. "
                f"Please ensure you've copied the complete private key including header and footer lines."
            )
    
    def sign_request(self, method: str, path: str, body: str = "") -> Dict[str, str]:
        """
        Generate Kalshi authentication headers for a request.
        
        Args:
            method: HTTP method (GET, POST, DELETE)
            path: API endpoint path (e.g., /portfolio/orders)
            body: Request body as JSON string (empty for GET)
        
        Returns:
            Dictionary of authentication headers
        """
        # Kalshi requires timestamp in MILLISECONDS
        timestamp = str(int(time.time() * 1000))
        
        # Create canonical string: timestamp + method + path (no body in signature)
        message = timestamp + method.upper() + path
        
        # Sign with RSA-PSS with SHA256 (Kalshi requirement)
        signature = self.private_key.sign(
            message.encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        # Base64 encode signature
        signature_b64 = base64.b64encode(signature).decode()
        
        return {
            'KALSHI-ACCESS-KEY': self.api_key_id,
            'KALSHI-ACCESS-SIGNATURE': signature_b64,
            'KALSHI-ACCESS-TIMESTAMP': timestamp,
            'Content-Type': 'application/json'
        }


class KalshiClient:
    """
    Production Kalshi API client for sports trading.
    Handles market discovery, order placement, and position management.
    """
    
    @staticmethod
    def validate_rsa_key(private_key_pem: str) -> tuple[bool, str]:
        """
        Validate an RSA private key without creating a full client.
        Useful for onboarding flow to validate key format before saving.
        
        Args:
            private_key_pem: RSA private key in PEM format
        
        Returns:
            Tuple of (is_valid, error_message). If valid, error_message is empty.
        """
        if not private_key_pem or not private_key_pem.strip():
            return False, "Private key is required. Please provide your RSA private key in PEM format."
        
        try:
            key_bytes = private_key_pem.encode() if isinstance(private_key_pem, str) else private_key_pem
            serialization.load_pem_private_key(
                key_bytes,
                password=None,
                backend=default_backend()
            )
            return True, ""
        except ValueError as e:
            return False, (
                f"Invalid RSA private key format. The key must be in PEM format "
                f"(starting with '-----BEGIN RSA PRIVATE KEY-----' or '-----BEGIN PRIVATE KEY-----'). "
                f"Error: {str(e)}"
            )
        except Exception as e:
            return False, f"Failed to load RSA private key: {str(e)}"
    
    def __init__(self, api_key_id: str, private_key_pem: str, dry_run: bool = False, environment: str = "production"):
        """
        Initialize Kalshi client with API credentials.

        Args:
            api_key_id: Kalshi API key ID
            private_key_pem: RSA private key in PEM format
            dry_run: If True, simulate orders without placing real trades
            environment: 'production' or 'demo' - determines which Kalshi API to use
        """
        self.auth = KalshiAuthenticator(api_key_id, private_key_pem)
        self.environment = environment.lower()
        
        # Select API URLs based on environment
        if self.environment == "demo":
            self.base_url = KALSHI_API_BASE_DEMO
            self.ws_url = KALSHI_WS_URL_DEMO
            logger.info("Kalshi client initialized in DEMO mode")
        else:
            self.base_url = KALSHI_API_BASE_PRODUCTION
            self.ws_url = KALSHI_WS_URL_PRODUCTION
            logger.info("Kalshi client initialized in PRODUCTION mode")
        
        self._client = httpx.AsyncClient(timeout=30.0)
        self.dry_run = dry_run
    
    async def close(self):
        """Close the HTTP client connection"""
        await self._client.aclose()
    
    async def _request(
        self,
        method: str,
        path: str,
        body: Optional[Dict] = None,
        params: Optional[Dict] = None,
        authenticated: bool = True
    ) -> Dict[str, Any]:
        """
        Make an authenticated request to Kalshi API.
        
        Args:
            method: HTTP method
            path: API endpoint path
            body: Request body (for POST/PUT)
            params: Query parameters (for GET)
            authenticated: Whether to include auth headers
        
        Returns:
            JSON response as dictionary
        
        Raises:
            TradingError: On API errors
            RateLimitError: On rate limit exceeded
        """
        url = f"{self.base_url}{path}"
        body_str = json.dumps(body) if body else ""
        
        headers = {}
        if authenticated:
            headers = self.auth.sign_request(method, path, body_str)
        else:
            headers = {'Content-Type': 'application/json'}
        
        try:
            if method == "GET":
                response = await self._client.get(url, headers=headers, params=params)
            elif method == "POST":
                response = await self._client.post(url, headers=headers, content=body_str)
            elif method == "DELETE":
                response = await self._client.delete(url, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Handle rate limiting
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "60")
                raise RateLimitError(
                    f"Rate limited. Retry after {retry_after}s",
                    details={"retry_after": int(retry_after)}
                )
            
            # Handle errors
            if response.status_code >= 400:
                error_detail = response.text
                raise TradingError(
                    f"Kalshi API error ({response.status_code}): {error_detail}",
                    details={"status_code": response.status_code, "response": error_detail}
                )
            
            return response.json() if response.text else {}
        
        except httpx.RequestError as e:
            raise TradingError(f"Network error: {str(e)}")
    
    # =========================================================================
    # Market Discovery
    # =========================================================================
    
    async def get_sports_markets(
        self,
        sport: Optional[str] = None,
        status: str = "open",
        limit: int = 100
    ) -> List[KalshiMarket]:
        """
        Fetch available sports markets.
        
        Args:
            sport: Filter by sport (NBA, NFL, MLB, NHL, etc.)
            status: Market status filter (open, active, closed)
            limit: Maximum markets to return
        
        Returns:
            List of KalshiMarket objects
        """
        params = {
            "category": "Sports",
            "status": status,
            "limit": limit
        }
        
        if sport:
            params["series_ticker"] = sport.upper()
        
        response = await self._request("GET", "/markets", params=params, authenticated=False)
        
        markets = []
        for m in response.get("markets", []):
            markets.append(KalshiMarket(
                ticker=m.get("ticker", ""),
                event_ticker=m.get("event_ticker", ""),
                title=m.get("title", ""),
                status=m.get("status", ""),
                yes_price=m.get("yes_price", 0.5),
                no_price=m.get("no_price", 0.5),
                volume_yes=m.get("volume_yes", 0),
                volume_no=m.get("volume_no", 0),
                close_ts=m.get("close_ts", 0),
                event_start_ts=m.get("event_start_ts", 0)
            ))
        
        return markets
    
    async def get_market(self, ticker: str) -> KalshiMarket:
        """
        Get details for a specific market.
        
        Args:
            ticker: Market ticker (e.g., NBA24_LAL_BOS_W_241230)
        
        Returns:
            KalshiMarket object
        """
        response = await self._request("GET", f"/markets/{ticker}", authenticated=False)
        m = response.get("market", response)
        
        return KalshiMarket(
            ticker=m.get("ticker", ticker),
            event_ticker=m.get("event_ticker", ""),
            title=m.get("title", ""),
            status=m.get("status", ""),
            yes_price=m.get("yes_price", 0.5),
            no_price=m.get("no_price", 0.5),
            volume_yes=m.get("volume_yes", 0),
            volume_no=m.get("volume_no", 0),
            close_ts=m.get("close_ts", 0),
            event_start_ts=m.get("event_start_ts", 0)
        )
    
    async def get_orderbook(self, ticker: str) -> Dict[str, Any]:
        """
        Fetch orderbook for a market.
        
        Args:
            ticker: Market ticker
        
        Returns:
            Orderbook with bids and asks arrays
        """
        return await self._request("GET", f"/markets/{ticker}/orderbook", authenticated=False)
    
    async def get_trades(self, ticker: str, limit: int = 100) -> List[Dict]:
        """
        Fetch recent trades for a market.
        
        Args:
            ticker: Market ticker
            limit: Maximum trades to return
        
        Returns:
            List of trade objects
        """
        response = await self._request(
            "GET",
            f"/markets/{ticker}/trades",
            params={"limit": limit},
            authenticated=False
        )
        return response.get("trades", [])
    
    # =========================================================================
    # Order Management
    # =========================================================================
    
    async def place_order(
        self,
        ticker: str,
        side: str,
        yes_no: str,
        price: float,
        size: int,
        time_in_force: str = "gtc",
        client_order_id: Optional[str] = None
    ) -> KalshiOrder:
        """
        Place a limit order on a Kalshi sports market.
        
        Args:
            ticker: Market ticker (e.g., NBA24_LAL_BOS_W_241230)
            side: "buy" or "sell"
            yes_no: "yes" or "no"
            price: Limit price (0.01 to 0.99)
            size: Number of contracts
            time_in_force: "gtc" (good-til-cancelled) or "fok" (fill-or-kill)
            client_order_id: Optional idempotency key
        
        Returns:
            KalshiOrder object with order details
        
        Raises:
            TradingError: On order placement failure
        """
        if not 0.01 <= price <= 0.99:
            raise TradingError(f"Invalid price {price}. Must be between 0.01 and 0.99")
        
        if size < 1:
            raise TradingError(f"Invalid size {size}. Must be at least 1 contract")
        
        # Generate client order ID
        order_client_id = client_order_id or f"bot-{int(time.time())}-{ticker[:20]}"
        
        # Paper trading mode - simulate order without placing real trade
        if self.dry_run:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(
                f"[DRY RUN] Simulated Kalshi order: {side.upper()} {size} {yes_no.upper()} "
                f"contracts of {ticker} @ ${price:.2f}"
            )
            
            # Return simulated order response
            return KalshiOrder(
                order_id=f"dry-run-{order_client_id}",
                ticker=ticker,
                side=side.lower(),
                yes_no=yes_no.lower(),
                price=price,
                size=size,
                status="filled",  # Simulate immediate fill for paper trading
                filled_size=size,
                created_at=datetime.now(timezone.utc)
            )
        
        body = {
            "ticker": ticker,
            "side": side.lower(),
            "yes_no": yes_no.lower(),
            "type": "limit",
            "price": round(price, 2),
            "size": size,
            "time_in_force": time_in_force.lower(),
            "client_order_id": order_client_id,
        }
        
        response = await self._request("POST", "/portfolio/orders", body=body)
        
        order = response.get("order", response)
        return KalshiOrder(
            order_id=order.get("order_id", ""),
            ticker=order.get("ticker", ticker),
            side=order.get("side", side),
            yes_no=order.get("yes_no", yes_no),
            price=order.get("price", price),
            size=order.get("size", size),
            status=order.get("status", "pending"),
            filled_size=order.get("filled_size", 0),
            created_at=datetime.now(timezone.utc)
        )
    
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an open order.
        
        Args:
            order_id: Kalshi order ID
        
        Returns:
            True if cancelled successfully
        """
        try:
            await self._request("DELETE", f"/portfolio/orders/{order_id}")
            return True
        except TradingError:
            return False
    
    async def get_orders(self, status: str = "open") -> List[KalshiOrder]:
        """
        Fetch orders with given status.
        
        Args:
            status: Order status filter (open, pending, filled, cancelled)
        
        Returns:
            List of KalshiOrder objects
        """
        response = await self._request(
            "GET",
            "/portfolio/orders",
            params={"status": status}
        )
        
        orders = []
        for o in response.get("orders", []):
            orders.append(KalshiOrder(
                order_id=o.get("order_id", ""),
                ticker=o.get("ticker", ""),
                side=o.get("side", ""),
                yes_no=o.get("yes_no", ""),
                price=o.get("price", 0),
                size=o.get("size", 0),
                status=o.get("status", ""),
                filled_size=o.get("filled_size", 0),
                created_at=datetime.fromisoformat(o.get("created_time", datetime.now().isoformat()))
            ))
        
        return orders

    async def get_order(self, order_id: str) -> Dict[str, Any]:
        """
        Get a specific order by ID.
        
        Args:
            order_id: Order ID to retrieve
        
        Returns:
            Order details dictionary
        """
        try:
            response = await self._request("GET", f"/portfolio/orders/{order_id}")
            return response.get("order", {})
        except TradingError as e:
            logger.warning(f"Failed to get order {order_id}: {e}")
            return {"status": "ERROR", "error": str(e)}
    
    # =========================================================================
    # Portfolio & Balance
    # =========================================================================
    
    async def get_balance(self) -> Dict[str, float]:
        """
        Get account balance.
        
        Returns:
            Dictionary with available_balance and total_balance
        """
        response = await self._request("GET", "/portfolio/balance")
        return {
            "available_balance": response.get("available_balance", 0),
            "total_balance": response.get("total_balance", 0),
            "pending_withdrawals": response.get("pending_withdrawals", 0)
        }
    
    async def get_positions(self) -> List[Dict]:
        """
        Get current positions.
        
        Returns:
            List of position objects with market details
        """
        response = await self._request("GET", "/portfolio/positions")
        return response.get("positions", [])
    
    # =========================================================================
    # Market State Detection
    # =========================================================================
    
    async def get_market_state(self, ticker: str) -> Dict[str, Any]:
        """
        Determine if market is pregame, live, or settled.
        
        Args:
            ticker: Market ticker
        
        Returns:
            Dictionary with market state information
        """
        market = await self.get_market(ticker)
        now = datetime.now(timezone.utc).timestamp()
        
        return {
            "ticker": ticker,
            "status": market.status,
            "is_pregame": now < market.event_start_ts,
            "is_live": market.event_start_ts <= now < market.close_ts and market.status in ["open", "active"],
            "is_settled": market.status in ["closed", "settled"],
            "time_to_start": max(0, market.event_start_ts - now),
            "time_to_close": max(0, market.close_ts - now),
            "yes_price": market.yes_price,
            "no_price": market.no_price,
            "volume": market.volume_yes + market.volume_no
        }
    
    def calculate_implied_probability(self, orderbook: Dict) -> float:
        """
        Calculate implied YES probability from orderbook mid-market.

        Args:
            orderbook: Orderbook dictionary with bids and asks

        Returns:
            Mid-market implied probability (0.0 to 1.0)
        """
        bids = orderbook.get("bids", [])
        asks = orderbook.get("asks", [])

        best_bid = bids[0]["price"] if bids else 0.5
        best_ask = asks[0]["price"] if asks else 0.5

        return (best_bid + best_ask) / 2

    # =========================================================================
    # Bot Runner Compatibility Methods
    # =========================================================================

    async def wait_for_fill(self, order_id: str, timeout: int = 30) -> str:
        """
        Wait for an order to be filled.
        Polls order status until filled, cancelled, or timeout.

        Args:
            order_id: Kalshi order ID
            timeout: Maximum seconds to wait

        Returns:
            Final order status: "filled", "cancelled", "partial", or "timeout"
        """
        # In dry run mode, simulate immediate fill
        if self.dry_run or order_id.startswith("dry-run-"):
            return "filled"
        
        import asyncio
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                response = await self._request("GET", f"/portfolio/orders/{order_id}")
                status = response.get("status", "").lower()

                if status == "filled":
                    return "filled"
                elif status in ["cancelled", "canceled"]:
                    return "cancelled"
                elif status == "partial":
                    return "partial"

                await asyncio.sleep(1)
            except TradingError:
                await asyncio.sleep(1)

        return "timeout"

    async def check_slippage(
        self,
        ticker: str,
        expected_price: float,
        side: str = "buy"
    ) -> tuple[bool, float]:
        """
        Check if current market price is within acceptable slippage.

        Args:
            ticker: Market ticker
            expected_price: Expected execution price
            side: "buy" or "sell"

        Returns:
            Tuple of (is_acceptable, current_price)
        """
        try:
            orderbook = await self.get_orderbook(ticker)

            if side.lower() == "buy":
                # For buy orders, check best ask
                asks = orderbook.get("asks", [])
                if not asks:
                    return False, expected_price
                current_price = asks[0].get("price", expected_price)
                # Allow up to 5% slippage for buys
                slippage = (current_price - expected_price) / expected_price if expected_price > 0 else 0
                return slippage <= 0.05, current_price
            else:
                # For sell orders, check best bid
                bids = orderbook.get("bids", [])
                if not bids:
                    return False, expected_price
                current_price = bids[0].get("price", expected_price)
                # Allow up to 5% slippage for sells
                slippage = (expected_price - current_price) / expected_price if expected_price > 0 else 0
                return slippage <= 0.05, current_price
        except Exception as e:
            logger.debug(f"Slippage check failed: {e}")
            return True, expected_price  # Allow trade if slippage check fails
