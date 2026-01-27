"""
Order Confirmation service - monitors order execution and verifies fills.
Implements retry logic for partial fills and timeout handling.
"""

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from src.services.polymarket_client import PolymarketClient
    from src.services.kalshi_client import KalshiClient

logger = logging.getLogger(__name__)


class OrderConfirmation:
    """
    Monitors order execution and confirms fills.
    
    Responsibilities:
    - Poll for order status after placement
    - Track fill prices and calculate slippage
    - Handle partial fills with retry logic
    - Update position records with actual execution data
    """
    
    DEFAULT_TIMEOUT_SECONDS = 30
    DEFAULT_POLL_INTERVAL = 2.0
    MAX_CONFIRMATION_ATTEMPTS = 5
    
    def __init__(
        self,
        db: AsyncSession,
        user_id: UUID,
        polymarket_client: "PolymarketClient | None" = None,
        kalshi_client: "KalshiClient | None" = None,
    ):
        self.db = db
        self.user_id = user_id
        self.polymarket_client = polymarket_client
        self.kalshi_client = kalshi_client
    
    async def confirm_order(
        self,
        order_id: str,
        position_id: UUID,
        platform: str = "polymarket",
        timeout_seconds: int | None = None,
    ) -> dict:
        """
        Wait for order confirmation and update position with fill data.
        
        Args:
            order_id: Exchange order ID
            position_id: Internal position UUID
            platform: Trading platform (polymarket/kalshi)
            timeout_seconds: Max time to wait for fill
        
        Returns:
            dict with fill status, actual price, slippage
        """
        timeout = timeout_seconds or self.DEFAULT_TIMEOUT_SECONDS
        start_time = datetime.now(timezone.utc)
        attempts = 0
        
        while True:
            attempts += 1
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            if elapsed >= timeout:
                await self._update_position_status(
                    position_id=position_id,
                    fill_status="timeout",
                    confirmation_attempts=attempts,
                )
                return {
                    "success": False,
                    "fill_status": "timeout",
                    "attempts": attempts,
                    "elapsed_seconds": elapsed,
                }
            
            if attempts > self.MAX_CONFIRMATION_ATTEMPTS:
                await self._update_position_status(
                    position_id=position_id,
                    fill_status="max_attempts",
                    confirmation_attempts=attempts,
                )
                return {
                    "success": False,
                    "fill_status": "max_attempts",
                    "attempts": attempts,
                }
            
            try:
                if platform == "polymarket":
                    order_status = await self._check_polymarket_order(order_id)
                elif platform == "kalshi":
                    order_status = await self._check_kalshi_order(order_id)
                else:
                    return {"success": False, "error": f"Unknown platform: {platform}"}
                
                if order_status["status"] == "filled":
                    await self._update_position_fill(
                        position_id=position_id,
                        actual_price=order_status.get("fill_price"),
                        fill_status="filled",
                        confirmation_attempts=attempts,
                    )
                    
                    slippage = await self._calculate_slippage(
                        position_id, order_status.get("fill_price")
                    )
                    
                    return {
                        "success": True,
                        "fill_status": "filled",
                        "actual_price": order_status.get("fill_price"),
                        "slippage_usdc": slippage,
                        "attempts": attempts,
                        "elapsed_seconds": elapsed,
                    }
                
                elif order_status["status"] == "partial":
                    logger.info(
                        f"Order {order_id} partially filled: "
                        f"{order_status.get('filled_size')}/{order_status.get('total_size')}"
                    )
                    await self._update_position_status(
                        position_id=position_id,
                        fill_status="partial",
                        confirmation_attempts=attempts,
                    )
                
                elif order_status["status"] == "cancelled":
                    await self._update_position_status(
                        position_id=position_id,
                        fill_status="cancelled",
                        confirmation_attempts=attempts,
                    )
                    return {
                        "success": False,
                        "fill_status": "cancelled",
                        "attempts": attempts,
                    }
                
                elif order_status["status"] == "rejected":
                    await self._update_position_status(
                        position_id=position_id,
                        fill_status="rejected",
                        confirmation_attempts=attempts,
                    )
                    return {
                        "success": False,
                        "fill_status": "rejected",
                        "reason": order_status.get("reject_reason"),
                        "attempts": attempts,
                    }
                
            except Exception as e:
                logger.warning(f"Order status check failed (attempt {attempts}): {e}")
            
            await asyncio.sleep(self.DEFAULT_POLL_INTERVAL)
    
    async def _check_polymarket_order(self, order_id: str) -> dict:
        """Check Polymarket order status via CLOB API."""
        if not self.polymarket_client:
            raise ValueError("Polymarket client not configured")
        
        try:
            order = await self.polymarket_client.get_order(order_id)
            
            status_map = {
                "MATCHED": "filled",
                "OPEN": "pending",
                "CANCELLED": "cancelled",
                "EXPIRED": "cancelled",
            }
            
            status = status_map.get(order.get("status", ""), "pending")
            
            if order.get("size_matched", 0) > 0 and order.get("size_matched") < order.get("original_size", 0):
                status = "partial"
            
            return {
                "status": status,
                "fill_price": Decimal(str(order.get("price", 0))),
                "filled_size": order.get("size_matched", 0),
                "total_size": order.get("original_size", 0),
            }
        except Exception as e:
            logger.error(f"Polymarket order check failed: {e}")
            return {"status": "unknown", "error": str(e)}
    
    async def _check_kalshi_order(self, order_id: str) -> dict:
        """Check Kalshi order status via REST API."""
        if not self.kalshi_client:
            raise ValueError("Kalshi client not configured")
        
        try:
            order = await self.kalshi_client.get_order(order_id)
            
            status = order.get("status", "").lower()
            if status == "executed":
                status = "filled"
            elif status in ("pending", "resting"):
                status = "pending"
            elif status == "canceled":
                status = "cancelled"
            
            return {
                "status": status,
                "fill_price": Decimal(str(order.get("average_fill_price", 0))) / Decimal("100"),
                "filled_size": order.get("filled_count", 0),
                "total_size": order.get("count", 0),
                "reject_reason": order.get("reject_reason"),
            }
        except Exception as e:
            logger.error(f"Kalshi order check failed: {e}")
            return {"status": "unknown", "error": str(e)}
    
    async def _update_position_status(
        self,
        position_id: UUID,
        fill_status: str,
        confirmation_attempts: int,
    ) -> None:
        """Update position with fill status."""
        from src.models import Position
        
        stmt = (
            update(Position)
            .where(Position.id == position_id)
            .values(
                fill_status=fill_status,
                confirmation_attempts=confirmation_attempts,
            )
        )
        await self.db.execute(stmt)
        await self.db.commit()
    
    async def _update_position_fill(
        self,
        position_id: UUID,
        actual_price: Decimal | None,
        fill_status: str,
        confirmation_attempts: int,
    ) -> None:
        """Update position with confirmed fill data."""
        from src.models import Position
        
        position = await self._get_position(position_id)
        slippage = None
        
        if position and actual_price and position.requested_entry_price:
            slippage = abs(actual_price - position.requested_entry_price)
        
        stmt = (
            update(Position)
            .where(Position.id == position_id)
            .values(
                actual_entry_price=actual_price,
                fill_status=fill_status,
                slippage_usdc=slippage,
                confirmation_attempts=confirmation_attempts,
            )
        )
        await self.db.execute(stmt)
        await self.db.commit()
    
    async def _calculate_slippage(
        self,
        position_id: UUID,
        actual_price: Decimal | None,
    ) -> Decimal | None:
        """Calculate slippage between requested and actual fill price."""
        position = await self._get_position(position_id)
        if not position or not actual_price:
            return None
        
        if position.requested_entry_price:
            return abs(actual_price - position.requested_entry_price)
        return None
    
    async def _get_position(self, position_id: UUID):
        """Fetch position by ID."""
        from src.models import Position
        
        stmt = select(Position).where(Position.id == position_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_pending_confirmations(self) -> list[dict]:
        """
        Get all positions awaiting order confirmation.
        
        Returns:
            List of positions with pending fill status
        """
        from src.models import Position
        
        stmt = (
            select(Position)
            .where(Position.user_id == self.user_id)
            .where(Position.fill_status.in_(["pending", "partial"]))
        )
        result = await self.db.execute(stmt)
        positions = result.scalars().all()
        
        return [
            {
                "position_id": str(p.id),
                "token_id": p.token_id,
                "fill_status": p.fill_status,
                "confirmation_attempts": p.confirmation_attempts,
                "requested_price": float(p.requested_entry_price) if p.requested_entry_price else None,
            }
            for p in positions
        ]
