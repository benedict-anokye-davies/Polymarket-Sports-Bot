"""
Tests for production infrastructure modules.
Covers rate limiting, logging, validation, health checks, alerts, and audit trail.
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
import json


# ============================================================================
# Price Cache Tests
# ============================================================================

class TestPriceCache:
    """Tests for the price history cache service."""
    
    @pytest.fixture
    def price_cache(self):
        """Create a fresh price cache instance."""
        from src.services.price_cache import PriceHistoryCache
        return PriceHistoryCache(ttl_hours=1, max_snapshots=100)
    
    @pytest.mark.asyncio
    async def test_add_and_get_latest(self, price_cache):
        """Test adding a price snapshot and retrieving it."""
        await price_cache.add(
            market_id="test_market",
            price=Decimal("0.65"),
            bid=Decimal("0.64"),
            ask=Decimal("0.66"),
        )
        
        latest = await price_cache.get_latest("test_market")
        
        assert latest is not None
        assert latest.price == Decimal("0.65")
        assert latest.bid == Decimal("0.64")
        assert latest.ask == Decimal("0.66")
    
    @pytest.mark.asyncio
    async def test_get_latest_nonexistent_market(self, price_cache):
        """Test getting latest price for nonexistent market."""
        latest = await price_cache.get_latest("nonexistent")
        assert latest is None
    
    @pytest.mark.asyncio
    async def test_get_range(self, price_cache):
        """Test retrieving prices within a time range."""
        base_time = datetime.now(timezone.utc)
        
        # Add multiple snapshots
        for i in range(5):
            await price_cache.add(
                market_id="test_market",
                price=Decimal(f"0.{60 + i}"),
                timestamp=base_time + timedelta(minutes=i),
            )
        
        # Get range
        start = base_time + timedelta(minutes=1)
        end = base_time + timedelta(minutes=3)
        snapshots = await price_cache.get_range("test_market", start, end)
        
        assert len(snapshots) == 3
        assert snapshots[0].price == Decimal("0.61")
        assert snapshots[-1].price == Decimal("0.63")
    
    @pytest.mark.asyncio
    async def test_get_stats(self, price_cache):
        """Test calculating OHLCV statistics."""
        base_time = datetime.now(timezone.utc) - timedelta(minutes=30)
        
        prices = [Decimal("0.60"), Decimal("0.65"), Decimal("0.55"), Decimal("0.62")]
        volumes = [Decimal("100"), Decimal("200"), Decimal("150"), Decimal("100")]
        
        for i, (price, volume) in enumerate(zip(prices, volumes)):
            await price_cache.add(
                market_id="test_market",
                price=price,
                volume=volume,
                timestamp=base_time + timedelta(minutes=i * 5),
            )
        
        stats = await price_cache.get_stats("test_market", period_minutes=60)
        
        assert stats is not None
        assert stats.open == Decimal("0.60")
        assert stats.close == Decimal("0.62")
        assert stats.high == Decimal("0.65")
        assert stats.low == Decimal("0.55")
        assert stats.count == 4
    
    @pytest.mark.asyncio
    async def test_max_snapshots_enforcement(self, price_cache):
        """Test that max snapshots limit is enforced."""
        for i in range(150):
            await price_cache.add(
                market_id="test_market",
                price=Decimal(f"0.{50 + (i % 50)}"),
            )
        
        # Should only have 100 snapshots (the max)
        assert len(price_cache._cache["test_market"]) == 100
    
    @pytest.mark.asyncio
    async def test_cache_stats(self, price_cache):
        """Test cache statistics tracking."""
        await price_cache.add("market1", Decimal("0.60"))
        await price_cache.add("market2", Decimal("0.70"))
        await price_cache.get_latest("market1")
        await price_cache.get_latest("nonexistent")
        
        stats = price_cache.get_cache_stats()
        
        assert stats["markets_cached"] == 2
        assert stats["total_snapshots"] == 2
        assert stats["hits"] >= 1
        assert stats["misses"] >= 1
    
    @pytest.mark.asyncio
    async def test_clear_market(self, price_cache):
        """Test clearing cache for a specific market."""
        await price_cache.add("market1", Decimal("0.60"))
        await price_cache.add("market2", Decimal("0.70"))
        
        cleared = await price_cache.clear_market("market1")
        
        assert cleared == 1
        assert "market1" not in price_cache._cache
        assert "market2" in price_cache._cache


# ============================================================================
# Shutdown Handler Tests
# ============================================================================

class TestShutdownHandler:
    """Tests for graceful shutdown handling."""
    
    @pytest.fixture
    def shutdown_handler(self):
        """Create a fresh shutdown handler."""
        from src.core.shutdown import ShutdownHandler
        return ShutdownHandler()
    
    @pytest.mark.asyncio
    async def test_register_cleanup_callback(self, shutdown_handler):
        """Test registering cleanup callbacks."""
        callback_called = False
        
        async def cleanup():
            nonlocal callback_called
            callback_called = True
        
        shutdown_handler.register_cleanup(cleanup, "test_cleanup", priority=50)
        
        assert len(shutdown_handler._cleanup_callbacks) == 1
        assert shutdown_handler._cleanup_callbacks[0][1] == "test_cleanup"
    
    @pytest.mark.asyncio
    async def test_cleanup_priority_ordering(self, shutdown_handler):
        """Test that cleanup callbacks are ordered by priority."""
        async def callback_a(): pass
        async def callback_b(): pass
        async def callback_c(): pass
        
        shutdown_handler.register_cleanup(callback_b, "b", priority=50)
        shutdown_handler.register_cleanup(callback_a, "a", priority=10)
        shutdown_handler.register_cleanup(callback_c, "c", priority=90)
        
        names = [cb[1] for cb in shutdown_handler._cleanup_callbacks]
        assert names == ["a", "b", "c"]
    
    @pytest.mark.asyncio
    async def test_unregister_cleanup(self, shutdown_handler):
        """Test removing a cleanup callback."""
        async def cleanup(): pass
        
        shutdown_handler.register_cleanup(cleanup, "to_remove")
        assert len(shutdown_handler._cleanup_callbacks) == 1
        
        removed = shutdown_handler.unregister_cleanup("to_remove")
        
        assert removed is True
        assert len(shutdown_handler._cleanup_callbacks) == 0
    
    def test_is_shutting_down(self, shutdown_handler):
        """Test shutdown state tracking."""
        assert shutdown_handler.is_shutting_down is False
        
        shutdown_handler._is_shutting_down = True
        assert shutdown_handler.is_shutting_down is True


# ============================================================================
# Alert Manager Tests
# ============================================================================

class TestAlertManager:
    """Tests for the alert escalation system."""
    
    @pytest.fixture
    def alert_manager(self):
        """Create a fresh alert manager."""
        from src.core.alerts import AlertManager, LogAlertChannel, AlertSeverity
        
        manager = AlertManager()
        manager.add_channel(LogAlertChannel(min_severity=AlertSeverity.INFO))
        return manager
    
    @pytest.mark.asyncio
    async def test_send_alert(self, alert_manager):
        """Test sending a basic alert."""
        from src.core.alerts import AlertSeverity
        
        result = await alert_manager.alert(
            severity=AlertSeverity.INFO,
            title="Test Alert",
            message="This is a test",
            category="test",
        )
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_alert_cooldown(self, alert_manager):
        """Test that cooldown prevents rapid duplicate alerts."""
        from src.core.alerts import AlertSeverity
        
        # First alert should succeed
        result1 = await alert_manager.alert(
            severity=AlertSeverity.INFO,
            title="Test",
            message="Message",
            category="test",
            cooldown_key="test_cooldown",
            cooldown_seconds=60,
        )
        
        # Second alert with same key should be suppressed
        result2 = await alert_manager.alert(
            severity=AlertSeverity.INFO,
            title="Test",
            message="Message",
            category="test",
            cooldown_key="test_cooldown",
            cooldown_seconds=60,
        )
        
        assert result1 is True
        assert result2 is False
    
    @pytest.mark.asyncio
    async def test_convenience_methods(self, alert_manager):
        """Test convenience alert methods."""
        await alert_manager.info("Info Title", "Info message", "test")
        await alert_manager.warning("Warning Title", "Warning message", "test")
        await alert_manager.error("Error Title", "Error message", "test")
        
        recent = alert_manager.get_recent_alerts(limit=10)
        assert len(recent) >= 3
    
    def test_get_stats(self, alert_manager):
        """Test alert statistics."""
        stats = alert_manager.get_stats()
        
        assert "total_alerts" in stats
        assert "by_category" in stats
        assert "by_severity" in stats
        assert "channels_configured" in stats


# ============================================================================
# Health Check Tests
# ============================================================================

class TestHealthMonitoring:
    """Tests for health check functionality."""
    
    @pytest.mark.asyncio
    async def test_health_aggregator(self):
        """Test service health aggregation."""
        from src.core.health import (
            ServiceHealthAggregator,
            HealthCheckResult,
            HealthStatus,
        )
        
        aggregator = ServiceHealthAggregator()
        
        async def healthy_check():
            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                response_time_ms=10.0,
                message="OK",
                details={},
                timestamp=datetime.now(timezone.utc),
            )
        
        async def degraded_check():
            return HealthCheckResult(
                status=HealthStatus.DEGRADED,
                response_time_ms=150.0,
                message="Slow",
                details={},
                timestamp=datetime.now(timezone.utc),
            )
        
        aggregator.register_service("service1", healthy_check)
        aggregator.register_service("service2", degraded_check)
        
        results = await aggregator.check_all()
        
        assert len(results) == 2
        assert results["service1"].status == HealthStatus.HEALTHY
        assert results["service2"].status == HealthStatus.DEGRADED
        assert aggregator.get_aggregate_status() == HealthStatus.DEGRADED
    
    def test_pool_metrics(self):
        """Test pool metrics calculations."""
        from src.core.health import PoolMetrics
        
        metrics = PoolMetrics(
            pool_size=10,
            checked_in=7,
            checked_out=3,
            overflow=0,
            invalid=0,
            soft_invalidated=0,
        )
        
        assert metrics.utilization == 30.0
        assert metrics.available == 7


# ============================================================================
# Request Validation Tests
# ============================================================================

class TestRequestValidation:
    """Tests for request validation middleware."""
    
    @pytest.fixture
    def sanitizer(self):
        """Create input sanitizer."""
        from src.core.validation import InputSanitizer, ValidationConfig
        return InputSanitizer(ValidationConfig())
    
    def test_path_traversal_detection(self, sanitizer):
        """Test detection of path traversal attacks."""
        assert sanitizer.check_path_traversal("../../../etc/passwd") is True
        assert sanitizer.check_path_traversal("..\\..\\windows\\system32") is True
        assert sanitizer.check_path_traversal("normal/path/here") is False
    
    def test_sql_injection_detection(self, sanitizer):
        """Test detection of SQL injection patterns."""
        assert sanitizer.check_sql_injection("'; DROP TABLE users;--") is True
        assert sanitizer.check_sql_injection("SELECT * FROM users") is True
        assert sanitizer.check_sql_injection("normal text input") is False
    
    def test_xss_detection(self, sanitizer):
        """Test detection of XSS patterns."""
        assert sanitizer.check_xss("<script>alert('xss')</script>") is True
        assert sanitizer.check_xss("javascript:alert(1)") is True
        assert sanitizer.check_xss('<div onclick="hack()">') is True
        assert sanitizer.check_xss("normal <b>text</b>") is False
    
    def test_recursive_sanitization(self, sanitizer):
        """Test recursive object sanitization."""
        malicious_data = {
            "name": "normal",
            "nested": {
                "payload": "<script>alert(1)</script>",
            },
            "list": ["safe", "'; DROP TABLE;--"],
        }
        
        issues = sanitizer.sanitize_recursive(malicious_data)
        
        assert len(issues) >= 2
    
    def test_json_depth_check(self):
        """Test JSON nesting depth validation."""
        from src.core.validation import check_json_depth
        
        shallow = {"a": {"b": {"c": 1}}}
        deep = {"a": {"b": {"c": {"d": {"e": {"f": 1}}}}}}
        
        assert check_json_depth(shallow, max_depth=5) is True
        assert check_json_depth(deep, max_depth=3) is False


# ============================================================================
# Audit Trail Tests
# ============================================================================

class TestAuditTrail:
    """Tests for the audit logging system."""
    
    @pytest.fixture
    def audit_logger(self):
        """Create audit logger with in-memory storage."""
        from src.core.audit import AuditLogger, InMemoryAuditStorage
        return AuditLogger(InMemoryAuditStorage())
    
    @pytest.mark.asyncio
    async def test_log_event(self, audit_logger):
        """Test logging a basic audit event."""
        from src.core.audit import AuditEvent, AuditEventType, AuditSeverity
        
        event = AuditEvent(
            event_type=AuditEventType.AUTH_LOGIN,
            severity=AuditSeverity.INFO,
            user_id="user_123",
            action="login",
            resource_type="session",
            resource_id=None,
        )
        
        result = await audit_logger.log(event)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_log_order_placed(self, audit_logger):
        """Test logging order placement."""
        result = await audit_logger.log_order_placed(
            user_id="user_123",
            order_id="order_456",
            market_id="market_789",
            side="buy",
            size=Decimal("100"),
            price=Decimal("0.65"),
        )
        
        assert result is True
        
        events = await audit_logger.query(user_id="user_123")
        assert len(events) == 1
        assert events[0].details["side"] == "buy"
    
    @pytest.mark.asyncio
    async def test_query_filters(self, audit_logger):
        """Test querying events with filters."""
        from src.core.audit import AuditEventType
        
        await audit_logger.log_login("user_1", success=True)
        await audit_logger.log_login("user_2", success=False)
        await audit_logger.log_logout("user_1")
        
        # Query by user
        user1_events = await audit_logger.query(user_id="user_1")
        assert len(user1_events) == 2
        
        # Query by event type
        login_events = await audit_logger.query(
            event_types=[AuditEventType.AUTH_LOGIN]
        )
        assert len(login_events) == 1
    
    @pytest.mark.asyncio
    async def test_position_tracking(self, audit_logger):
        """Test position lifecycle logging."""
        await audit_logger.log_position_opened(
            user_id="user_123",
            position_id="pos_001",
            market_id="market_abc",
            side="buy",
            size=Decimal("50"),
            entry_price=Decimal("0.55"),
        )
        
        await audit_logger.log_position_closed(
            user_id="user_123",
            position_id="pos_001",
            exit_price=Decimal("0.70"),
            pnl=Decimal("7.50"),
            reason="take_profit",
        )
        
        events = await audit_logger.query(user_id="user_123")
        assert len(events) == 2


# ============================================================================
# Rate Limiter Tests
# ============================================================================

class TestRateLimiter:
    """Tests for the rate limiting system."""
    
    @pytest.fixture
    def rate_limiter(self):
        """Create rate limiter."""
        from src.core.rate_limiter import RateLimiter, RateLimitConfig
        
        config = RateLimitConfig(
            requests_per_minute=10,
            requests_per_hour=100,
            burst_limit=5,
        )
        return RateLimiter(config)
    
    @pytest.mark.asyncio
    async def test_allow_normal_traffic(self, rate_limiter):
        """Test that normal traffic is allowed."""
        for i in range(3):
            allowed, info = await rate_limiter.check_rate_limit("client_1")
            assert allowed is True
    
    @pytest.mark.asyncio
    async def test_rate_limit_burst(self, rate_limiter):
        """Test burst limit enforcement."""
        # Exhaust burst limit
        for i in range(5):
            await rate_limiter.check_rate_limit("client_burst")
        
        # Next request should be denied
        allowed, info = await rate_limiter.check_rate_limit("client_burst")
        assert allowed is False
        assert info.get("exceeded") == "burst"
    
    @pytest.mark.asyncio
    async def test_different_clients_independent(self, rate_limiter):
        """Test that different clients have independent limits."""
        # Exhaust client1's burst limit
        for i in range(5):
            await rate_limiter.check_rate_limit("client_1")
        
        # client_2 should still be allowed
        allowed, info = await rate_limiter.check_rate_limit("client_2")
        assert allowed is True
    
    @pytest.mark.asyncio
    async def test_limit_info_returned(self, rate_limiter):
        """Test that limit information is returned."""
        allowed, info = await rate_limiter.check_rate_limit("client_check")
        
        assert "minute_count" in info
        assert "minute_limit" in info
        assert "hour_count" in info
        assert info["minute_limit"] == 10
        assert info["hour_limit"] == 100


# ============================================================================
# Logging Service Tests
# ============================================================================

class TestLoggingService:
    """Tests for the structured logging service."""
    
    def test_json_formatter(self):
        """Test JSON log formatting."""
        from src.core.logging_service import JSONFormatter
        import logging
        
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        output = formatter.format(record)
        data = json.loads(output)
        
        assert data["message"] == "Test message"
        assert data["level"] == "INFO"
        assert data["logger"] == "test"
    
    def test_context_logger(self):
        """Test context logger with correlation ID."""
        from src.core.logging_service import ContextLogger, correlation_id_ctx
        import logging
        
        base_logger = logging.getLogger("context_test")
        context_logger = ContextLogger(base_logger)
        
        # Set correlation ID
        token = correlation_id_ctx.set("corr-123")
        
        try:
            # Process adds correlation_id to extra under 'extra' key
            msg, kwargs = context_logger.process("Test", {})
            # The correlation_id may be in kwargs['extra'] or directly in kwargs
            extra = kwargs.get("extra", kwargs)
            assert extra.get("correlation_id") == "corr-123"
        finally:
            correlation_id_ctx.reset(token)


# ============================================================================
# Integration Tests
# ============================================================================

class TestProductionIntegration:
    """Integration tests for production infrastructure."""
    
    @pytest.mark.asyncio
    async def test_full_alert_flow(self):
        """Test complete alert flow from trigger to delivery."""
        from src.core.alerts import (
            AlertManager,
            LogAlertChannel,
            AlertSeverity,
            EscalationRule,
        )
        
        manager = AlertManager()
        manager.add_channel(LogAlertChannel(min_severity=AlertSeverity.INFO))
        
        # Add escalation rule
        manager.add_escalation_rule(EscalationRule(
            threshold_count=3,
            time_window_minutes=5,
            escalate_to=AlertSeverity.ERROR,
        ))
        
        # Send multiple alerts to trigger escalation
        for i in range(5):
            await manager.alert(
                severity=AlertSeverity.WARNING,
                title=f"Warning {i}",
                message="Test warning",
                category="test",
                cooldown_key=f"unique_{i}",  # Different keys to avoid cooldown
            )
        
        recent = manager.get_recent_alerts()
        # Later alerts should be escalated to ERROR
        error_count = sum(1 for a in recent if a.severity == AlertSeverity.ERROR)
        assert error_count > 0
    
    @pytest.mark.asyncio
    async def test_audit_with_correlation(self):
        """Test audit logging with correlation IDs."""
        from src.core.audit import AuditLogger, InMemoryAuditStorage, AuditEvent
        from src.core.audit import AuditEventType, AuditSeverity
        
        storage = InMemoryAuditStorage()
        logger = AuditLogger(storage)
        
        correlation_id = "tx-12345"
        
        # Log related events with same correlation ID
        await logger.log(AuditEvent(
            event_type=AuditEventType.ORDER_PLACED,
            severity=AuditSeverity.INFO,
            user_id="user_1",
            action="order_placed",
            resource_type="order",
            resource_id="order_1",
            correlation_id=correlation_id,
        ))
        
        await logger.log(AuditEvent(
            event_type=AuditEventType.ORDER_FILLED,
            severity=AuditSeverity.INFO,
            user_id="user_1",
            action="order_filled",
            resource_type="order",
            resource_id="order_1",
            correlation_id=correlation_id,
        ))
        
        events = await logger.query()
        correlated = [e for e in events if e.correlation_id == correlation_id]
        assert len(correlated) == 2
