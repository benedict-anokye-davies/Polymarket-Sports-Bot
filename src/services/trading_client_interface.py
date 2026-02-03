from typing import Protocol, Any, runtime_checkable

@runtime_checkable
class TradingClient(Protocol):
    """
    Unified interface for Polymarket and Kalshi clients.
    """
    
    async def get_balance(self) -> dict[str, Any]:
        """Get account balance."""
        ...
        
    async def place_order(
        self,
        token_id: str,
        side: str,
        price: float,
        size: float,
        **kwargs: Any
    ) -> Any:
        """Place an order."""
        ...
        
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        ...
        
    async def get_order(self, order_id: str) -> dict[str, Any]:
        """Get order details."""
        ...
        
    async def get_market(self, market_id: str) -> Any:
        """Get market details."""
        ...
        
    async def check_slippage(self, token_id: str, price: float, side: str) -> bool:
        """Check if price slippage is acceptable."""
        ...
