"""
Integration tests for KalshiClient.
Tests REAL code with HTTP responses mocked at the httpx level.
These tests verify actual parsing, validation, and data transformation.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone
import json
import httpx

from src.services.kalshi_client import KalshiClient, KalshiOrder, KalshiMarket, KalshiAuthenticator
from src.core.exceptions import TradingError, RateLimitError


TEST_API_KEY = "test-api-key-12345"
TEST_PRIVATE_KEY = "-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----"


# =============================================================================
# Test Fixtures - Create clients with mocked auth but real HTTP parsing
# =============================================================================

@pytest.fixture
def mock_auth():
    """Mock authenticator to bypass RSA validation."""
    auth = MagicMock(spec=KalshiAuthenticator)
    auth.api_key_id = TEST_API_KEY
    auth.sign_request.return_value = {
        "KALSHI-ACCESS-KEY": TEST_API_KEY,
        "KALSHI-ACCESS-SIGNATURE": "test-signature",
        "KALSHI-ACCESS-TIMESTAMP": "1234567890"
    }
    return auth


@pytest.fixture
def mock_http_client():
    """Mock httpx.AsyncClient for HTTP-level mocking."""
    return AsyncMock(spec=httpx.AsyncClient)


@pytest.fixture
def kalshi_client(mock_auth, mock_http_client):
    """Create KalshiClient with mocked auth and HTTP client."""
    with patch('src.services.kalshi_client.KalshiAuthenticator', return_value=mock_auth):
        with patch('src.services.kalshi_client.httpx.AsyncClient', return_value=mock_http_client):
            client = KalshiClient(
                api_key_id=TEST_API_KEY,
                private_key_pem=TEST_PRIVATE_KEY,
                dry_run=False  # Test real API path, not dry run
            )
            client._client = mock_http_client
            return client


# =============================================================================
# REAL Tests - Validation Logic (no mocks on the method being tested)
# =============================================================================

class TestKalshiClientValidation:
    """Tests that exercise REAL validation code."""
    
    def test_empty_api_key_raises_error(self):
        """REAL TEST: Empty API key triggers actual validation in KalshiAuthenticator."""
        with pytest.raises(TradingError) as exc:
            KalshiClient(api_key_id="", private_key_pem=TEST_PRIVATE_KEY)
        assert "API key is required" in str(exc.value)
    
    def test_whitespace_api_key_raises_error(self):
        """REAL TEST: Whitespace-only API key fails validation."""
        with pytest.raises(TradingError) as exc:
            KalshiClient(api_key_id="   ", private_key_pem=TEST_PRIVATE_KEY)
        assert "API key is required" in str(exc.value)
    
    def test_empty_private_key_raises_error(self):
        """REAL TEST: Empty private key fails validation."""
        with pytest.raises(TradingError) as exc:
            KalshiClient(api_key_id=TEST_API_KEY, private_key_pem="")
        assert "private key is required" in str(exc.value).lower()
    
    def test_invalid_pem_format_raises_error(self):
        """REAL TEST: Malformed PEM triggers actual cryptography error handling."""
        with pytest.raises(TradingError) as exc:
            KalshiClient(api_key_id=TEST_API_KEY, private_key_pem="not-a-pem-key")
        assert "Invalid RSA private key format" in str(exc.value)
    
    def test_validate_rsa_key_static_invalid(self):
        """REAL TEST: Static validation method with invalid key."""
        is_valid, error = KalshiClient.validate_rsa_key("garbage-key")
        assert is_valid is False
        assert "Invalid RSA" in error or "private key" in error.lower()
    
    def test_validate_rsa_key_static_empty(self):
        """REAL TEST: Static validation method with empty string."""
        is_valid, error = KalshiClient.validate_rsa_key("")
        assert is_valid is False
        assert len(error) > 0


class TestKalshiOrderValidation:
    """Tests that exercise REAL order validation code."""
    
    @pytest.fixture
    def dry_run_client(self, mock_auth):
        """Client in dry_run mode for order validation tests."""
        with patch('src.services.kalshi_client.KalshiAuthenticator', return_value=mock_auth):
            with patch('src.services.kalshi_client.httpx.AsyncClient'):
                return KalshiClient(
                    api_key_id=TEST_API_KEY,
                    private_key_pem=TEST_PRIVATE_KEY,
                    dry_run=True
                )
    
    @pytest.mark.asyncio
    async def test_price_below_minimum_raises_error(self, dry_run_client):
        """REAL TEST: Price < 0.01 triggers actual validation."""
        with pytest.raises(TradingError) as exc:
            await dry_run_client.place_order(
                ticker="NBA-TEST",
                side="buy",
                yes_no="yes",
                price=0.001,  # Below minimum 0.01
                size=10
            )
        assert "Invalid price" in str(exc.value)
    
    @pytest.mark.asyncio
    async def test_price_above_maximum_raises_error(self, dry_run_client):
        """REAL TEST: Price > 0.99 triggers actual validation."""
        with pytest.raises(TradingError) as exc:
            await dry_run_client.place_order(
                ticker="NBA-TEST",
                side="buy",
                yes_no="yes",
                price=1.50,  # Above maximum 0.99
                size=10
            )
        assert "Invalid price" in str(exc.value)
    
    @pytest.mark.asyncio
    async def test_size_zero_raises_error(self, dry_run_client):
        """REAL TEST: Size of 0 triggers actual validation."""
        with pytest.raises(TradingError) as exc:
            await dry_run_client.place_order(
                ticker="NBA-TEST",
                side="buy",
                yes_no="yes",
                price=0.50,
                size=0  # Invalid
            )
        assert "Invalid size" in str(exc.value)
    
    @pytest.mark.asyncio
    async def test_negative_size_raises_error(self, dry_run_client):
        """REAL TEST: Negative size triggers actual validation."""
        with pytest.raises(TradingError) as exc:
            await dry_run_client.place_order(
                ticker="NBA-TEST",
                side="buy",
                yes_no="yes",
                price=0.50,
                size=-5  # Invalid
            )
        assert "Invalid size" in str(exc.value)
    
    @pytest.mark.asyncio
    async def test_dry_run_returns_simulated_order(self, dry_run_client):
        """REAL TEST: Dry run mode returns properly formatted simulated order."""
        order = await dry_run_client.place_order(
            ticker="NBA-LAL-BOS-2026",
            side="buy",
            yes_no="yes",
            price=0.45,
            size=10
        )
        
        # Verify REAL simulated order structure
        assert isinstance(order, KalshiOrder)
        assert "dry-run" in order.order_id.lower()
        assert order.ticker == "NBA-LAL-BOS-2026"
        assert order.side == "buy"
        assert order.yes_no == "yes"
        assert order.price == 0.45
        assert order.size == 10
        assert order.status == "filled"  # Simulated orders are auto-filled
        assert order.filled_size == 10


# =============================================================================
# REAL Tests - HTTP Response Parsing (mock at httpx level, test real parsing)
# =============================================================================

class TestKalshiMarketParsing:
    """Tests that exercise REAL JSON parsing and data transformation."""
    
    @pytest.mark.asyncio
    async def test_get_sports_markets_parses_response(self, kalshi_client, mock_http_client):
        """REAL TEST: Actual parsing of market list response."""
        # Mock HTTP response with realistic Kalshi data
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = json.dumps({
            "markets": [
                {
                    "ticker": "NBA24-LAL-BOS-W-260126",
                    "event_ticker": "NBA24-LAL-BOS",
                    "title": "Will the Lakers beat the Celtics on Jan 26?",
                    "status": "open",
                    "yes_price": 0.42,
                    "no_price": 0.58,
                    "volume_yes": 15420,
                    "volume_no": 8930,
                    "close_ts": 1737936000,
                    "event_start_ts": 1737925200
                },
                {
                    "ticker": "NBA24-MIA-NYK-W-260126",
                    "event_ticker": "NBA24-MIA-NYK",
                    "title": "Will the Heat beat the Knicks on Jan 26?",
                    "status": "open",
                    "yes_price": 0.55,
                    "no_price": 0.45,
                    "volume_yes": 9800,
                    "volume_no": 7200,
                    "close_ts": 1737943200,
                    "event_start_ts": 1737932400
                }
            ]
        })
        mock_response.json.return_value = json.loads(mock_response.text)
        mock_http_client.get.return_value = mock_response
        
        # Call REAL method - tests actual parsing logic
        markets = await kalshi_client.get_sports_markets(sport="NBA")
        
        # Verify real parsing worked
        assert len(markets) == 2
        
        # First market
        assert markets[0].ticker == "NBA24-LAL-BOS-W-260126"
        assert markets[0].event_ticker == "NBA24-LAL-BOS"
        assert markets[0].title == "Will the Lakers beat the Celtics on Jan 26?"
        assert markets[0].status == "open"
        assert markets[0].yes_price == 0.42
        assert markets[0].no_price == 0.58
        assert markets[0].volume_yes == 15420
        
        # Second market
        assert markets[1].ticker == "NBA24-MIA-NYK-W-260126"
        assert markets[1].yes_price == 0.55
    
    @pytest.mark.asyncio
    async def test_get_market_parses_single_response(self, kalshi_client, mock_http_client):
        """REAL TEST: Actual parsing of single market response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = json.dumps({
            "market": {
                "ticker": "NBA24-LAL-BOS-W-260126",
                "event_ticker": "NBA24-LAL-BOS",
                "title": "Lakers vs Celtics Game Winner",
                "status": "active",
                "yes_price": 0.48,
                "no_price": 0.52,
                "volume_yes": 25000,
                "volume_no": 18000,
                "close_ts": 1737936000,
                "event_start_ts": 1737925200
            }
        })
        mock_response.json.return_value = json.loads(mock_response.text)
        mock_http_client.get.return_value = mock_response
        
        # Call REAL method
        market = await kalshi_client.get_market("NBA24-LAL-BOS-W-260126")
        
        # Verify real parsing
        assert isinstance(market, KalshiMarket)
        assert market.ticker == "NBA24-LAL-BOS-W-260126"
        assert market.status == "active"
        assert market.yes_price == 0.48
        assert market.no_price == 0.52
    
    @pytest.mark.asyncio
    async def test_get_orderbook_parses_response(self, kalshi_client, mock_http_client):
        """REAL TEST: Actual parsing of orderbook response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = json.dumps({
            "orderbook": {
                "yes": [
                    [0.45, 500],
                    [0.44, 1200],
                    [0.43, 800]
                ],
                "no": [
                    [0.55, 600],
                    [0.56, 900],
                    [0.57, 400]
                ]
            }
        })
        mock_response.json.return_value = json.loads(mock_response.text)
        mock_http_client.get.return_value = mock_response
        
        # Call REAL method
        orderbook = await kalshi_client.get_orderbook("NBA24-TEST")
        
        # Verify real parsing
        assert "orderbook" in orderbook or "yes" in orderbook
    
    @pytest.mark.asyncio
    async def test_empty_markets_response(self, kalshi_client, mock_http_client):
        """REAL TEST: Handle empty markets list gracefully."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = json.dumps({"markets": []})
        mock_response.json.return_value = {"markets": []}
        mock_http_client.get.return_value = mock_response
        
        markets = await kalshi_client.get_sports_markets()
        
        assert markets == []
        assert isinstance(markets, list)


# =============================================================================
# REAL Tests - Error Handling (test actual exception transformation)
# =============================================================================

class TestKalshiErrorHandling:
    """Tests that exercise REAL error handling code."""
    
    @pytest.mark.asyncio
    async def test_rate_limit_429_raises_rate_limit_error(self, kalshi_client, mock_http_client):
        """REAL TEST: 429 response triggers actual RateLimitError."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "30"}
        mock_response.text = "Rate limit exceeded"
        mock_http_client.get.return_value = mock_response
        
        with pytest.raises(RateLimitError) as exc:
            await kalshi_client.get_sports_markets()
        
        assert "Rate limited" in str(exc.value)
        assert exc.value.details["retry_after"] == 30
    
    @pytest.mark.asyncio
    async def test_400_error_raises_trading_error(self, kalshi_client, mock_http_client):
        """REAL TEST: 400 response triggers actual TradingError with details."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = '{"error": "Invalid market ticker"}'
        mock_http_client.get.return_value = mock_response
        
        with pytest.raises(TradingError) as exc:
            await kalshi_client.get_market("INVALID-TICKER")
        
        assert "400" in str(exc.value)
        assert "Invalid market ticker" in str(exc.value)
    
    @pytest.mark.asyncio
    async def test_500_error_raises_trading_error(self, kalshi_client, mock_http_client):
        """REAL TEST: 500 response triggers actual TradingError."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"
        mock_http_client.get.return_value = mock_response
        
        with pytest.raises(TradingError) as exc:
            await kalshi_client.get_sports_markets()
        
        assert "500" in str(exc.value)
    
    @pytest.mark.asyncio
    async def test_network_error_raises_trading_error(self, kalshi_client, mock_http_client):
        """REAL TEST: Network failure triggers actual error transformation."""
        mock_http_client.get.side_effect = httpx.RequestError("Connection refused")
        
        with pytest.raises(TradingError) as exc:
            await kalshi_client.get_sports_markets()
        
        assert "Network error" in str(exc.value)


# =============================================================================
# REAL Tests - Order Response Parsing
# =============================================================================

class TestKalshiOrderParsing:
    """Tests that exercise REAL order response parsing."""
    
    @pytest.mark.asyncio
    async def test_get_orders_parses_response(self, kalshi_client, mock_http_client):
        """REAL TEST: Actual parsing of orders list response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = json.dumps({
            "orders": [
                {
                    "order_id": "ord-abc123",
                    "ticker": "NBA24-LAL-BOS-W-260126",
                    "side": "buy",
                    "yes_no": "yes",
                    "price": 0.45,
                    "size": 100,
                    "status": "open",
                    "filled_size": 0,
                    "created_time": "2026-01-26T10:30:00Z"
                },
                {
                    "order_id": "ord-def456",
                    "ticker": "NBA24-MIA-NYK-W-260126",
                    "side": "sell",
                    "yes_no": "no",
                    "price": 0.60,
                    "size": 50,
                    "status": "filled",
                    "filled_size": 50,
                    "created_time": "2026-01-26T09:15:00Z"
                }
            ]
        })
        mock_response.json.return_value = json.loads(mock_response.text)
        mock_http_client.get.return_value = mock_response
        
        # Call REAL method
        orders = await kalshi_client.get_orders()
        
        # Verify real parsing
        assert len(orders) == 2
        
        assert orders[0].order_id == "ord-abc123"
        assert orders[0].ticker == "NBA24-LAL-BOS-W-260126"
        assert orders[0].side == "buy"
        assert orders[0].yes_no == "yes"
        assert orders[0].price == 0.45
        assert orders[0].size == 100
        assert orders[0].status == "open"
        assert orders[0].filled_size == 0
        
        assert orders[1].order_id == "ord-def456"
        assert orders[1].status == "filled"
        assert orders[1].filled_size == 50


# =============================================================================
# Dataclass Tests (always real - no HTTP)
# =============================================================================

class TestKalshiDataclasses:
    """Tests for Kalshi data structures - always real."""
    
    def test_kalshi_order_all_fields(self):
        """REAL TEST: KalshiOrder dataclass with all fields."""
        order = KalshiOrder(
            order_id="ord-test-123",
            ticker="NBA24-TEST",
            side="buy",
            yes_no="yes",
            price=0.45,
            size=100,
            status="filled",
            filled_size=100,
            created_at=datetime(2026, 1, 26, 12, 0, 0, tzinfo=timezone.utc)
        )
        
        assert order.order_id == "ord-test-123"
        assert order.ticker == "NBA24-TEST"
        assert order.side == "buy"
        assert order.yes_no == "yes"
        assert order.price == 0.45
        assert order.size == 100
        assert order.status == "filled"
        assert order.filled_size == 100
        assert order.created_at.year == 2026
    
    def test_kalshi_market_all_fields(self):
        """REAL TEST: KalshiMarket dataclass with all fields."""
        market = KalshiMarket(
            ticker="NBA24-LAL-BOS-W-260126",
            event_ticker="NBA24-LAL-BOS",
            title="Lakers vs Celtics",
            status="open",
            yes_price=0.42,
            no_price=0.58,
            volume_yes=15420,
            volume_no=8930,
            close_ts=1737936000,
            event_start_ts=1737925200
        )
        
        assert market.ticker == "NBA24-LAL-BOS-W-260126"
        assert market.event_ticker == "NBA24-LAL-BOS"
        assert market.yes_price == 0.42
        assert market.no_price == 0.58
        assert market.yes_price + market.no_price == 1.0  # Verify prices sum to 1
