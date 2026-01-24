"""
Polymarket CLOB API client implementation.
Handles L1/L2 authentication and all trading operations.
"""

import asyncio
from decimal import Decimal
from typing import Any

import httpx
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType

from src.core.exceptions import PolymarketAPIError, InsufficientBalanceError


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
        passphrase: str | None = None
    ):
        """
        Initializes the Polymarket client.
        
        Args:
            private_key: Wallet private key for L1 auth
            funder_address: Address holding USDC funds
            api_key: Optional API key for L2 auth
            api_secret: Optional API secret for L2 auth
            passphrase: Optional passphrase for L2 auth
        """
        self.private_key = private_key
        self.funder_address = funder_address
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        
        self._clob_client: ClobClient | None = None
        self._http_client: httpx.AsyncClient | None = None
    
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
        
        Returns:
            Balance in USDC as Decimal
        """
        try:
            http = await self._get_http_client()
            
            response = await http.get(
                f"{self.CLOB_HOST}/balance",
                params={"address": self.funder_address}
            )
            response.raise_for_status()
            
            data = response.json()
            return Decimal(str(data.get("balance", 0)))
            
        except httpx.HTTPError as e:
            raise PolymarketAPIError(f"Failed to fetch balance: {str(e)}")
    
    async def get_midpoint_price(self, token_id: str) -> float:
        """
        Fetches current midpoint price for a token.
        
        Args:
            token_id: The token ID to get price for
        
        Returns:
            Midpoint price as float
        """
        try:
            http = await self._get_http_client()
            
            response = await http.get(
                f"{self.CLOB_HOST}/midpoint",
                params={"token_id": token_id}
            )
            response.raise_for_status()
            
            data = response.json()
            return float(data.get("mid", 0))
            
        except httpx.HTTPError as e:
            raise PolymarketAPIError(f"Failed to fetch midpoint: {str(e)}")
    
    async def get_orderbook(self, token_id: str) -> dict[str, Any]:
        """
        Fetches full orderbook for a token.
        
        Returns:
            Dictionary with bids and asks arrays
        """
        try:
            http = await self._get_http_client()
            
            response = await http.get(
                f"{self.CLOB_HOST}/book",
                params={"token_id": token_id}
            )
            response.raise_for_status()
            
            return response.json()
            
        except httpx.HTTPError as e:
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
        Places an order on Polymarket.
        
        Args:
            token_id: Token ID to trade
            side: "BUY" or "SELL"
            price: Limit price (0.0 to 1.0)
            size: Number of contracts
            order_type: Order type (GTC, GTD, FOK)
        
        Returns:
            Order response from API
        """
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
            
            return {"id": result.get("orderID"), "status": "created", "raw": result}
            
        except Exception as e:
            error_str = str(e).lower()
            if "insufficient" in error_str or "balance" in error_str:
                raise InsufficientBalanceError(f"Insufficient balance: {str(e)}")
            raise PolymarketAPIError(f"Failed to place order: {str(e)}")
    
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
        
        Returns:
            List of positions with token_id and size
        """
        try:
            http = await self._get_http_client()
            
            response = await http.get(
                f"{self.GAMMA_HOST}/positions",
                params={"user": self.funder_address}
            )
            response.raise_for_status()
            
            return response.json()
            
        except httpx.HTTPError as e:
            raise PolymarketAPIError(f"Failed to fetch positions: {str(e)}")
    
    async def get_sports_markets(self, sport: str | None = None) -> list[dict[str, Any]]:
        """
        Fetches active sports markets from Gamma API.
        
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
            
            response = await http.get(
                f"{self.GAMMA_HOST}/markets",
                params=params
            )
            response.raise_for_status()
            
            return response.json()
            
        except httpx.HTTPError as e:
            raise PolymarketAPIError(f"Failed to fetch markets: {str(e)}")
    
    async def close(self) -> None:
        """
        Closes HTTP client connections.
        """
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
