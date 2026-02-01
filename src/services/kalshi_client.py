"""
Complete Kalshi API Client Implementation
"""

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

import httpx
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)

class KalshiClient:
    """
    Complete implementation of Kalshi trading API client.
    """
    
    BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
    
    def __init__(self, api_key: str, private_key_pem: str):
        """
        Initialize Kalshi client with API credentials.
        
        Args:
            api_key: Kalshi API key
            private_key_pem: RSA private key in PEM format
        """
        self.api_key = api_key
        self.private_key = load_pem_private_key(
            private_key_pem.encode(),
            password=None,
            backend=default_backend()
        )
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def _authenticated_request(self, method: str, path: str, **kwargs) -> Dict:
        """
        Make authenticated request to Kalshi API with retry logic.
        
        Implements exponential backoff for rate limiting (429) and server errors (5xx).
        """
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                timestamp = str(int(time.time() * 1000))
                message = f"{timestamp}{method.upper()}{path}"
                
                signature = self.private_key.sign(
                    message.encode(),
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.DIGEST_LENGTH
                    ),
                    hashes.SHA256()
                )
                
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Kalshi-Access-Timestamp": timestamp,
                    "Kalshi-Access-Signature": base64.b64encode(signature).decode(),
                    "Content-Type": "application/json"
                }
                
                response = await self.client.request(
                    method,
                    f"{self.BASE_URL}{path}",
                    headers=headers,
                    **kwargs
                )
                
                # Handle rate limiting (429) with exponential backoff
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 5))
                    wait_time = max(retry_after, 2 ** attempt)
                    logger.warning(f"Rate limited (429), waiting {wait_time}s before retry {attempt + 1}/{max_retries}")
                    await asyncio.sleep(wait_time)
                    continue
                
                # Handle server errors (5xx) with exponential backoff
                if response.status_code in (502, 503, 504):
                    wait_time = 2 ** attempt
                    logger.warning(f"Server error ({response.status_code}), waiting {wait_time}s before retry {attempt + 1}/{max_retries}")
                    await asyncio.sleep(wait_time)
                    continue
                    
                response.raise_for_status()
                return response.json()
                
            except httpx.HTTPStatusError as e:
                last_error = e
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

    # Market Data Endpoints
    async def get_markets(self, status: str = "open") -> List[Dict]:
        """Get all markets with given status."""
        return await self._authenticated_request("GET", f"/markets?status={status}")
    
    async def get_market(self, market_id: str) -> Dict:
        """Get details for specific market."""
        return await self._authenticated_request("GET", f"/markets/{market_id}")
    
    async def get_market_history(
        self,
        market_id: str,
        limit: int = 100,
        cursor: Optional[str] = None
    ) -> Dict:
        """Get historical data for a market."""
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        return await self._authenticated_request(
            "GET",
            f"/markets/{market_id}/history",
            params=params
        )

    # Portfolio Endpoints
    async def get_balance(self) -> Dict:
        """Get current account balance."""
        return await self._authenticated_request("GET", "/portfolio/balance")
    
    async def get_positions(self) -> List[Dict]:
        """Get current positions."""
        return await self._authenticated_request("GET", "/portfolio/positions")
    
    async def get_fills(
        self,
        market_id: Optional[str] = None,
        limit: int = 100,
        cursor: Optional[str] = None
    ) -> Dict:
        """Get order fill history."""
        params = {"limit": limit}
        if market_id:
            params["market_id"] = market_id
        if cursor:
            params["cursor"] = cursor
        return await self._authenticated_request(
            "GET",
            "/portfolio/fills",
            params=params
        )

    # Order Endpoints
    async def place_order(
        self,
        ticker: str,
        side: str,
        yes_no: str,
        price: float,
        size: int,
        client_order_id: Optional[str] = None
    ) -> Dict:
        """Place a new order.
        
        Args:
            ticker: Market ticker symbol (e.g., "NBA-2025-01-15-LAL-BOS")
            side: Order side - "buy" or "sell"
            yes_no: Contract side - "yes" or "no"
            price: Price in cents (1-100, where 100 = $1.00)
            size: Number of contracts to trade
            client_order_id: Optional client order ID
        """
        # Convert price to cents if it's in decimal form (0-1 range)
        price_cents = int(price * 100) if price <= 1.0 else int(price)
        
        payload = {
            "ticker": ticker,
            "side": side,
            "yes": yes_no.lower() == "yes",
            "price": price_cents,
            "count": size
        }
        
        if client_order_id:
            payload["client_order_id"] = client_order_id
            
        return await self._authenticated_request(
            "POST",
            "/orders",
            json=payload
        )

    async def cancel_order(self, order_id: str) -> Dict:
        """Cancel an existing order."""
        return await self._authenticated_request(
            "DELETE",
            f"/orders/{order_id}"
        )

    async def get_order_status(self, order_id: str) -> Dict:
        """Get status of specific order."""
        return await self._authenticated_request(
            "GET",
            f"/orders/{order_id}"
        )

    async def get_open_orders(self) -> List[Dict]:
        """Get all open orders."""
        return await self._authenticated_request(
            "GET",
            "/orders"
        )

    async def modify_order(
        self,
        order_id: str,
        new_price: Optional[float] = None,
        new_size: Optional[int] = None
    ) -> Dict:
        """Modify an existing order."""
        payload = {}
        if new_price is not None:
            payload["price"] = new_price
        if new_size is not None:
            payload["count"] = new_size
            
        return await self._authenticated_request(
            "PUT",
            f"/orders/{order_id}",
            json=payload
        )

    async def batch_orders(
        self,
        orders: List[Dict[str, Any]]
    ) -> List[Dict]:
        """Place multiple orders in a single request."""
        if self.dry_run:
            return [{"dry_run": True, "status": "simulated"} for _ in orders]
            
        return await self._authenticated_request(
            "POST",
            "/orders/batch",
            json={"orders": orders}
        )

    # Test function
    async def test_connection(self) -> bool:
        """Test API connectivity."""
        try:
            await self.get_balance()
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            return False

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def main():
        # Initialize with your actual credentials
        client = KalshiClient(
            api_key="your_api_key",
            private_key_pem="""-----BEGIN RSA PRIVATE KEY-----
            your_private_key_here
            -----END RSA PRIVATE KEY-----""",
            dry_run=True  # Set to False for real trading
        )
        
        try:
            # Test connection
            if not await client.test_connection():
                print("Failed to connect to Kalshi API")
                return
                
            print("Successfully connected to Kalshi API")
            
            # Example usage
            balance = await client.get_balance()
            print(f"Account balance: {balance}")
            
            markets = await client.get_markets()
            print(f"Found {len(markets)} open markets")
            
            # Place a test order (would need valid market_id)
            # order = await client.place_order(
            #     market_id="some_market_id",
            #     side="yes",
            #     price=0.50,
            #     size=10
            # )
            # print(f"Order placed: {order}")
            
        finally:
            await client.close()
    
    asyncio.run(main())