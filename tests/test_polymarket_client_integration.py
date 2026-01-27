"""
Integration tests for PolymarketClient.
Tests REAL code with HTTP responses mocked at the httpx/retry level.
These tests verify actual parsing, validation, and data transformation.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from decimal import Decimal
from datetime import datetime, timezone
import json
import httpx

from src.services.polymarket_client import PolymarketClient
from src.core.exceptions import PolymarketAPIError, InsufficientBalanceError


# Test credentials (DO NOT USE IN PRODUCTION)
TEST_PRIVATE_KEY = "0x" + "a" * 64
TEST_FUNDER_ADDRESS = "0x" + "b" * 40


# =============================================================================
# REAL Tests - Client Creation and Configuration
# =============================================================================

class TestPolymarketClientConfiguration:
    """Tests that exercise REAL client configuration."""
    
    def test_client_stores_credentials(self):
        """REAL TEST: Client actually stores provided credentials."""
        client = PolymarketClient(
            private_key=TEST_PRIVATE_KEY,
            funder_address=TEST_FUNDER_ADDRESS,
            dry_run=True
        )
        
        assert client.private_key == TEST_PRIVATE_KEY
        assert client.funder_address == TEST_FUNDER_ADDRESS
        assert client.dry_run is True
    
    def test_client_stores_l2_credentials(self):
        """REAL TEST: L2 credentials are actually stored."""
        client = PolymarketClient(
            private_key=TEST_PRIVATE_KEY,
            funder_address=TEST_FUNDER_ADDRESS,
            api_key="my-api-key",
            api_secret="my-secret",
            passphrase="my-passphrase",
            dry_run=True
        )
        
        assert client.api_key == "my-api-key"
        assert client.api_secret == "my-secret"
        assert client.passphrase == "my-passphrase"
    
    def test_client_default_slippage(self):
        """REAL TEST: Default max_slippage is set correctly."""
        client = PolymarketClient(
            private_key=TEST_PRIVATE_KEY,
            funder_address=TEST_FUNDER_ADDRESS
        )
        
        assert client.max_slippage == 0.02  # 2% default
    
    def test_client_custom_slippage(self):
        """REAL TEST: Custom max_slippage is stored."""
        client = PolymarketClient(
            private_key=TEST_PRIVATE_KEY,
            funder_address=TEST_FUNDER_ADDRESS,
            max_slippage=0.05
        )
        
        assert client.max_slippage == 0.05
    
    def test_client_api_hosts_correct(self):
        """REAL TEST: API hosts are set to production URLs."""
        client = PolymarketClient(
            private_key=TEST_PRIVATE_KEY,
            funder_address=TEST_FUNDER_ADDRESS
        )
        
        assert client.CLOB_HOST == "https://clob.polymarket.com"
        assert client.GAMMA_HOST == "https://gamma-api.polymarket.com"
        assert client.CHAIN_ID == 137  # Polygon mainnet
    
    def test_simulated_orders_initialized(self):
        """REAL TEST: Simulated orders tracking is initialized."""
        client = PolymarketClient(
            private_key=TEST_PRIVATE_KEY,
            funder_address=TEST_FUNDER_ADDRESS,
            dry_run=True
        )
        
        assert client._simulated_orders == {}
        assert client._simulated_order_counter == 0


# =============================================================================
# REAL Tests - Balance Parsing (mock at retry_async level)
# =============================================================================

class TestPolymarketBalanceParsing:
    """Tests that exercise REAL balance parsing code."""
    
    @pytest.fixture
    def client(self):
        return PolymarketClient(
            private_key=TEST_PRIVATE_KEY,
            funder_address=TEST_FUNDER_ADDRESS,
            dry_run=True
        )
    
    @pytest.mark.asyncio
    async def test_balance_parses_decimal_correctly(self, client):
        """REAL TEST: Balance response is parsed to Decimal."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"balance": 1523.456789}
        mock_response.raise_for_status = MagicMock()
        
        with patch('src.services.polymarket_client.retry_async', new_callable=AsyncMock) as mock_retry:
            mock_retry.return_value = mock_response
            
            balance = await client.get_balance()
            
            # Verify REAL parsing to Decimal
            assert isinstance(balance, Decimal)
            assert balance == Decimal("1523.456789")
    
    @pytest.mark.asyncio
    async def test_balance_handles_zero(self, client):
        """REAL TEST: Zero balance is parsed correctly."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"balance": 0}
        mock_response.raise_for_status = MagicMock()
        
        with patch('src.services.polymarket_client.retry_async', new_callable=AsyncMock) as mock_retry:
            mock_retry.return_value = mock_response
            
            balance = await client.get_balance()
            
            assert balance == Decimal("0")
    
    @pytest.mark.asyncio
    async def test_balance_handles_missing_key(self, client):
        """REAL TEST: Missing balance key returns 0."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}  # No "balance" key
        mock_response.raise_for_status = MagicMock()
        
        with patch('src.services.polymarket_client.retry_async', new_callable=AsyncMock) as mock_retry:
            mock_retry.return_value = mock_response
            
            balance = await client.get_balance()
            
            assert balance == Decimal("0")
    
    @pytest.mark.asyncio
    async def test_balance_api_error_raises_exception(self, client):
        """REAL TEST: HTTP error triggers PolymarketAPIError."""
        with patch('src.services.polymarket_client.retry_async', new_callable=AsyncMock) as mock_retry:
            mock_retry.side_effect = httpx.HTTPError("Connection failed")
            
            with pytest.raises(PolymarketAPIError) as exc:
                await client.get_balance()
            
            assert "Failed to fetch balance" in str(exc.value)


# =============================================================================
# REAL Tests - Price Parsing
# =============================================================================

class TestPolymarketPriceParsing:
    """Tests that exercise REAL price parsing code."""
    
    @pytest.fixture
    def client(self):
        return PolymarketClient(
            private_key=TEST_PRIVATE_KEY,
            funder_address=TEST_FUNDER_ADDRESS,
            dry_run=True
        )
    
    @pytest.mark.asyncio
    async def test_midpoint_parses_float(self, client):
        """REAL TEST: Midpoint response is parsed to float."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"mid": 0.4523}
        mock_response.raise_for_status = MagicMock()
        
        with patch('src.services.polymarket_client.retry_async', new_callable=AsyncMock) as mock_retry:
            mock_retry.return_value = mock_response
            
            price = await client.get_midpoint_price("token-abc-123")
            
            assert isinstance(price, float)
            assert price == 0.4523
    
    @pytest.mark.asyncio
    async def test_midpoint_handles_missing_mid(self, client):
        """REAL TEST: Missing 'mid' key returns 0."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()
        
        with patch('src.services.polymarket_client.retry_async', new_callable=AsyncMock) as mock_retry:
            mock_retry.return_value = mock_response
            
            price = await client.get_midpoint_price("token-abc-123")
            
            assert price == 0
    
    @pytest.mark.asyncio
    async def test_midpoint_api_error_raises_exception(self, client):
        """REAL TEST: HTTP error triggers PolymarketAPIError."""
        with patch('src.services.polymarket_client.retry_async', new_callable=AsyncMock) as mock_retry:
            mock_retry.side_effect = httpx.HTTPError("Timeout")
            
            with pytest.raises(PolymarketAPIError) as exc:
                await client.get_midpoint_price("token-abc")
            
            assert "Failed to fetch midpoint" in str(exc.value)


# =============================================================================
# REAL Tests - Orderbook Parsing
# =============================================================================

class TestPolymarketOrderbookParsing:
    """Tests that exercise REAL orderbook parsing code."""
    
    @pytest.fixture
    def client(self):
        return PolymarketClient(
            private_key=TEST_PRIVATE_KEY,
            funder_address=TEST_FUNDER_ADDRESS,
            dry_run=True
        )
    
    @pytest.mark.asyncio
    async def test_orderbook_returns_full_structure(self, client):
        """REAL TEST: Orderbook response structure is preserved."""
        mock_orderbook = {
            "bids": [
                {"price": "0.45", "size": "500"},
                {"price": "0.44", "size": "1200"},
                {"price": "0.43", "size": "800"}
            ],
            "asks": [
                {"price": "0.47", "size": "400"},
                {"price": "0.48", "size": "900"},
                {"price": "0.49", "size": "600"}
            ],
            "spread": 0.02
        }
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_orderbook
        mock_response.raise_for_status = MagicMock()
        
        with patch('src.services.polymarket_client.retry_async', new_callable=AsyncMock) as mock_retry:
            mock_retry.return_value = mock_response
            
            orderbook = await client.get_orderbook("token-abc-123")
            
            # Verify REAL parsing preserves structure
            assert "bids" in orderbook
            assert "asks" in orderbook
            assert len(orderbook["bids"]) == 3
            assert len(orderbook["asks"]) == 3
            assert orderbook["bids"][0]["price"] == "0.45"
    
    @pytest.mark.asyncio
    async def test_orderbook_api_error_raises_exception(self, client):
        """REAL TEST: HTTP error triggers PolymarketAPIError."""
        with patch('src.services.polymarket_client.retry_async', new_callable=AsyncMock) as mock_retry:
            mock_retry.side_effect = httpx.HTTPError("Server error")
            
            with pytest.raises(PolymarketAPIError) as exc:
                await client.get_orderbook("token-abc")
            
            assert "Failed to fetch orderbook" in str(exc.value)


# =============================================================================
# REAL Tests - Order Simulation (Dry Run Mode)
# =============================================================================

class TestPolymarketOrderSimulation:
    """Tests that exercise REAL order simulation code."""
    
    @pytest.fixture
    def client(self):
        return PolymarketClient(
            private_key=TEST_PRIVATE_KEY,
            funder_address=TEST_FUNDER_ADDRESS,
            dry_run=True
        )
    
    @pytest.mark.asyncio
    async def test_dry_run_creates_simulated_order(self, client):
        """REAL TEST: Dry run actually creates simulated order."""
        order = await client.place_order(
            token_id="token-yes-abc123",
            side="BUY",
            price=0.45,
            size=100
        )
        
        # Verify REAL simulation logic
        assert order["id"].startswith("DRY_RUN_")
        assert order["status"] == "FILLED"
        assert order["is_simulated"] is True
    
    @pytest.mark.asyncio
    async def test_dry_run_increments_counter(self, client):
        """REAL TEST: Simulation counter increments correctly."""
        assert client._simulated_order_counter == 0
        
        await client.place_order(
            token_id="token-1",
            side="BUY",
            price=0.45,
            size=10
        )
        assert client._simulated_order_counter == 1
        
        await client.place_order(
            token_id="token-2",
            side="SELL",
            price=0.55,
            size=20
        )
        assert client._simulated_order_counter == 2
    
    @pytest.mark.asyncio
    async def test_dry_run_stores_order_in_dict(self, client):
        """REAL TEST: Simulated orders are stored for later retrieval."""
        order = await client.place_order(
            token_id="token-abc",
            side="BUY",
            price=0.42,
            size=50
        )
        
        order_id = order["id"]
        assert order_id in client._simulated_orders
        
        stored_order = client._simulated_orders[order_id]
        assert stored_order["token_id"] == "token-abc"
        assert stored_order["side"] == "BUY"
        assert stored_order["price"] == 0.42
        assert stored_order["size"] == 50
    
    @pytest.mark.asyncio
    async def test_dry_run_order_contains_all_fields(self, client):
        """REAL TEST: Simulated order has all expected fields."""
        order = await client.place_order(
            token_id="token-yes-xyz",
            side="BUY",
            price=0.38,
            size=200,
            order_type="GTC"
        )
        
        order_id = order["id"]
        stored = client._simulated_orders[order_id]
        
        # Verify all fields are present
        assert "token_id" in stored
        assert "side" in stored
        assert "price" in stored
        assert "size" in stored
        assert "order_type" in stored
        assert "status" in stored
        assert "filled_size" in stored
        assert "filled_price" in stored
        assert "created_at" in stored
        assert "is_simulated" in stored
        
        # Verify values
        assert stored["filled_size"] == 200  # Assumes immediate fill
        assert stored["filled_price"] == 0.38


# =============================================================================
# REAL Tests - Order Status Retrieval
# =============================================================================

class TestPolymarketOrderStatus:
    """Tests that exercise REAL order status retrieval code."""
    
    @pytest.fixture
    def client(self):
        return PolymarketClient(
            private_key=TEST_PRIVATE_KEY,
            funder_address=TEST_FUNDER_ADDRESS,
            dry_run=True
        )
    
    @pytest.mark.asyncio
    async def test_get_status_for_simulated_order(self, client):
        """REAL TEST: Can retrieve status of simulated order."""
        # First create a simulated order
        order = await client.place_order(
            token_id="token-test",
            side="BUY",
            price=0.50,
            size=25
        )
        
        order_id = order["id"]
        
        # Now retrieve its status
        status = await client.get_order_status(order_id)
        
        assert status["token_id"] == "token-test"
        assert status["status"] == "FILLED"
    
    @pytest.mark.asyncio
    async def test_get_status_for_unknown_simulated_order(self, client):
        """REAL TEST: Unknown simulated order returns NOT_FOUND."""
        status = await client.get_order_status("DRY_RUN_999999")
        
        assert status["status"] == "NOT_FOUND"


# =============================================================================
# REAL Tests - Multiple Orders Scenario
# =============================================================================

class TestPolymarketMultipleOrders:
    """Tests that exercise REAL multi-order scenarios."""
    
    @pytest.fixture
    def client(self):
        return PolymarketClient(
            private_key=TEST_PRIVATE_KEY,
            funder_address=TEST_FUNDER_ADDRESS,
            dry_run=True
        )
    
    @pytest.mark.asyncio
    async def test_multiple_orders_unique_ids(self, client):
        """REAL TEST: Multiple orders get unique IDs."""
        order1 = await client.place_order(
            token_id="token-a", side="BUY", price=0.40, size=10
        )
        order2 = await client.place_order(
            token_id="token-b", side="BUY", price=0.45, size=20
        )
        order3 = await client.place_order(
            token_id="token-c", side="SELL", price=0.60, size=30
        )
        
        ids = {order1["id"], order2["id"], order3["id"]}
        assert len(ids) == 3  # All unique
    
    @pytest.mark.asyncio
    async def test_all_orders_stored(self, client):
        """REAL TEST: All orders are stored in tracking dict."""
        await client.place_order(
            token_id="token-1", side="BUY", price=0.40, size=10
        )
        await client.place_order(
            token_id="token-2", side="BUY", price=0.45, size=20
        )
        await client.place_order(
            token_id="token-3", side="SELL", price=0.60, size=30
        )
        
        assert len(client._simulated_orders) == 3
        assert client._simulated_order_counter == 3


# =============================================================================
# REAL Tests - HTTP Client Initialization
# =============================================================================

class TestPolymarketHttpClient:
    """Tests that verify HTTP client lazy initialization."""
    
    @pytest.fixture
    def client(self):
        return PolymarketClient(
            private_key=TEST_PRIVATE_KEY,
            funder_address=TEST_FUNDER_ADDRESS,
            dry_run=True
        )
    
    def test_http_client_initially_none(self, client):
        """REAL TEST: HTTP client is not created until needed."""
        assert client._http_client is None
    
    def test_clob_client_initially_none(self, client):
        """REAL TEST: CLOB client is not created until needed."""
        assert client._clob_client is None
