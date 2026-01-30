"""
Test suite for order confirmation system.
Verifies that orders are properly confirmed before recording positions.
"""

import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch

from src.services.order_confirmation import (
    OrderConfirmationManager,
    OrderConfirmationResult,
    FillStatus
)
from src.services.kalshi_client import KalshiClient, KalshiOrder


@pytest.fixture
def mock_kalshi_client():
    """Create a mock Kalshi client for testing."""
    client = Mock(spec=KalshiClient)
    client.dry_run = False
    client.place_order = AsyncMock()
    client.get_order = AsyncMock()
    client.cancel_order = AsyncMock()
    return client


@pytest.fixture
def confirmation_manager(mock_kalshi_client):
    """Create an order confirmation manager with mock client."""
    return OrderConfirmationManager(
        client=mock_kalshi_client,
        max_wait_seconds=5,  # Short timeout for tests
        poll_interval=0.1
    )


class TestOrderConfirmationManager:
    """Test the OrderConfirmationManager class."""
    
    @pytest.mark.asyncio
    async def test_place_and_confirm_successful_fill(self, confirmation_manager, mock_kalshi_client):
        """Test that a successful fill is properly confirmed."""
        # Setup mock order
        mock_order = KalshiOrder(
            order_id="test-order-123",
            ticker="NBA24_LAL_BOS_W_241230",
            side="buy",
            yes_no="yes",
            price=0.65,
            size=100,
            status="pending",
            filled_size=0,
            created_at=datetime.now(timezone.utc)
        )
        mock_kalshi_client.place_order.return_value = mock_order
        
        # Setup mock order status (filled)
        mock_kalshi_client.get_order.return_value = {
            "order_id": "test-order-123",
            "status": "filled",
            "filled_size": 100,
            "avg_price": 0.65,
            "price": 0.65
        }
        
        # Execute
        result = await confirmation_manager.place_and_confirm(
            ticker="NBA24_LAL_BOS_W_241230",
            side="buy",
            yes_no="yes",
            price=0.65,
            size=100
        )
        
        # Verify
        assert result.status == FillStatus.FILLED
        assert result.filled_size == 100
        assert result.avg_fill_price == 0.65
        assert result.order_id == "test-order-123"
        assert result.error_message is None
    
    @pytest.mark.asyncio
    async def test_place_and_confirm_partial_fill_accepted(self, confirmation_manager, mock_kalshi_client):
        """Test that partial fills above threshold are accepted."""
        mock_order = KalshiOrder(
            order_id="test-order-456",
            ticker="NBA24_LAL_BOS_W_241230",
            side="buy",
            yes_no="yes",
            price=0.65,
            size=100,
            status="pending",
            filled_size=0,
            created_at=datetime.now(timezone.utc)
        )
        mock_kalshi_client.place_order.return_value = mock_order
        
        # 85% filled (above 80% threshold)
        mock_kalshi_client.get_order.return_value = {
            "order_id": "test-order-456",
            "status": "filled",
            "filled_size": 85,
            "avg_price": 0.65,
            "price": 0.65
        }
        
        result = await confirmation_manager.place_and_confirm(
            ticker="NBA24_LAL_BOS_W_241230",
            side="buy",
            yes_no="yes",
            price=0.65,
            size=100
        )
        
        assert result.status == FillStatus.PARTIAL
        assert result.filled_size == 85
    
    @pytest.mark.asyncio
    async def test_place_and_confirm_timeout(self, confirmation_manager, mock_kalshi_client):
        """Test that orders timeout if not filled."""
        mock_order = KalshiOrder(
            order_id="test-order-789",
            ticker="NBA24_LAL_BOS_W_241230",
            side="buy",
            yes_no="yes",
            price=0.65,
            size=100,
            status="pending",
            filled_size=0,
            created_at=datetime.now(timezone.utc)
        )
        mock_kalshi_client.place_order.return_value = mock_order
        
        # Order stays pending
        mock_kalshi_client.get_order.return_value = {
            "order_id": "test-order-789",
            "status": "pending",
            "filled_size": 0,
            "avg_price": 0.0,
            "price": 0.65
        }
        
        result = await confirmation_manager.place_and_confirm(
            ticker="NBA24_LAL_BOS_W_241230",
            side="buy",
            yes_no="yes",
            price=0.65,
            size=100
        )
        
        assert result.status == FillStatus.TIMEOUT
        assert "Timeout" in result.error_message
        mock_kalshi_client.cancel_order.assert_called_once_with("test-order-789")
    
    @pytest.mark.asyncio
    async def test_place_and_confirm_cancelled(self, confirmation_manager, mock_kalshi_client):
        """Test handling of cancelled orders."""
        mock_order = KalshiOrder(
            order_id="test-order-000",
            ticker="NBA24_LAL_BOS_W_241230",
            side="buy",
            yes_no="yes",
            price=0.65,
            size=100,
            status="pending",
            filled_size=0,
            created_at=datetime.now(timezone.utc)
        )
        mock_kalshi_client.place_order.return_value = mock_order
        
        mock_kalshi_client.get_order.return_value = {
            "order_id": "test-order-000",
            "status": "cancelled",
            "filled_size": 0,
            "avg_price": 0.0,
            "price": 0.65
        }
        
        result = await confirmation_manager.place_and_confirm(
            ticker="NBA24_LAL_BOS_W_241230",
            side="buy",
            yes_no="yes",
            price=0.65,
            size=100
        )
        
        assert result.status == FillStatus.CANCELLED
    
    @pytest.mark.asyncio
    async def test_place_and_confirm_dry_run(self, confirmation_manager, mock_kalshi_client):
        """Test that dry run mode returns immediately as filled."""
        mock_kalshi_client.dry_run = True
        
        mock_order = KalshiOrder(
            order_id="dry-run-order",
            ticker="NBA24_LAL_BOS_W_241230",
            side="buy",
            yes_no="yes",
            price=0.65,
            size=100,
            status="filled",
            filled_size=100,
            created_at=datetime.now(timezone.utc)
        )
        mock_kalshi_client.place_order.return_value = mock_order
        
        result = await confirmation_manager.place_and_confirm(
            ticker="NBA24_LAL_BOS_W_241230",
            side="buy",
            yes_no="yes",
            price=0.65,
            size=100
        )
        
        assert result.status == FillStatus.FILLED
        assert result.wait_time_seconds == 0.0
        mock_kalshi_client.get_order.assert_not_called()  # Should not poll in dry run
    
    @pytest.mark.asyncio
    async def test_place_and_confirm_slippage_calculation(self, confirmation_manager, mock_kalshi_client):
        """Test that slippage is calculated correctly."""
        mock_order = KalshiOrder(
            order_id="test-order-slippage",
            ticker="NBA24_LAL_BOS_W_241230",
            side="buy",
            yes_no="yes",
            price=0.65,
            size=100,
            status="pending",
            filled_size=0,
            created_at=datetime.now(timezone.utc)
        )
        mock_kalshi_client.place_order.return_value = mock_order
        
        # Fill at worse price (0.67 vs 0.65 requested)
        mock_kalshi_client.get_order.return_value = {
            "order_id": "test-order-slippage",
            "status": "filled",
            "filled_size": 100,
            "avg_price": 0.67,
            "price": 0.65
        }
        
        result = await confirmation_manager.place_and_confirm(
            ticker="NBA24_LAL_BOS_W_241230",
            side="buy",
            yes_no="yes",
            price=0.65,
            size=100
        )
        
        assert result.status == FillStatus.FILLED
        assert result.slippage == pytest.approx(0.02, abs=0.001)  # 0.67 - 0.65 = 0.02
    
    @pytest.mark.asyncio
    async def test_place_and_confirm_api_error(self, confirmation_manager, mock_kalshi_client):
        """Test handling of API errors during order placement."""
        mock_kalshi_client.place_order.side_effect = Exception("API Error: Rate limit exceeded")
        
        result = await confirmation_manager.place_and_confirm(
            ticker="NBA24_LAL_BOS_W_241230",
            side="buy",
            yes_no="yes",
            price=0.65,
            size=100
        )
        
        assert result.status == FillStatus.ERROR
        assert "API Error" in result.error_message


class TestFillStatus:
    """Test the FillStatus enum."""
    
    def test_fill_status_values(self):
        """Test that all expected statuses exist."""
        assert FillStatus.FILLED.value == "filled"
        assert FillStatus.PARTIAL.value == "partial"
        assert FillStatus.CANCELLED.value == "cancelled"
        assert FillStatus.TIMEOUT.value == "timeout"
        assert FillStatus.ERROR.value == "error"
        assert FillStatus.PENDING.value == "pending"
        assert FillStatus.REJECTED.value == "rejected"


class TestOrderConfirmationResult:
    """Test the OrderConfirmationResult dataclass."""
    
    def test_result_creation(self):
        """Test creating a result object."""
        result = OrderConfirmationResult(
            order_id="test-123",
            status=FillStatus.FILLED,
            filled_size=100,
            avg_fill_price=0.65,
            wait_time_seconds=2.5,
            slippage=0.01,
            ticker="NBA24_LAL_BOS_W_241230",
            side="buy",
            platform="kalshi"
        )
        
        assert result.order_id == "test-123"
        assert result.status == FillStatus.FILLED
        assert result.filled_size == 100
        assert result.avg_fill_price == 0.65
        assert result.wait_time_seconds == 2.5
        assert result.slippage == 0.01
        assert result.ticker == "NBA24_LAL_BOS_W_241230"
        assert result.side == "buy"
        assert result.platform == "kalshi"
        assert result.error_message is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
