"""
Tests for advanced production infrastructure modules.
Covers Prometheus metrics, Redis rate limiting, log shipping, and incident management.
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
import json


# ============================================================================
# Prometheus Metrics Tests
# ============================================================================

class TestPrometheusMetrics:
    """Tests for Prometheus metrics system."""
    
    def test_counter_increment(self):
        """Test counter metric increments correctly."""
        from src.core.prometheus import Counter
        
        counter = Counter("test_counter_1", "Test counter", labels=["method"])
        
        counter.inc(method="GET")
        counter.inc(method="GET")
        counter.inc(value=5, method="POST")
        
        results = counter.collect()
        
        assert len(results) == 2
        get_result = next(r for r in results if r[0].get("method") == "GET")
        post_result = next(r for r in results if r[0].get("method") == "POST")
        
        assert get_result[1] == 2
        assert post_result[1] == 5
    
    def test_gauge_set_and_modify(self):
        """Test gauge metric set, inc, and dec."""
        from src.core.prometheus import Gauge
        
        gauge = Gauge("test_gauge_1", "Test gauge", labels=["type"])
        
        gauge.set(10, type="connections")
        gauge.inc(value=5, type="connections")
        gauge.dec(value=3, type="connections")
        
        results = gauge.collect()
        
        assert len(results) == 1
        assert results[0][1] == 12  # 10 + 5 - 3
    
    def test_histogram_observations(self):
        """Test histogram metric observations."""
        from src.core.prometheus import Histogram
        
        histogram = Histogram(
            "test_histogram_1",
            "Test histogram",
            labels=["endpoint"],
            buckets=(0.1, 0.5, 1.0, 5.0),
        )
        
        histogram.observe(0.05, endpoint="/api")
        histogram.observe(0.3, endpoint="/api")
        histogram.observe(2.0, endpoint="/api")
        
        results = histogram.collect()
        
        assert len(results) == 1
        data = results[0][1]
        
        assert data["count"] == 3
        assert data["sum"] == pytest.approx(2.35, rel=0.01)
        assert data["buckets"][0.1] == 1
        assert data["buckets"][0.5] == 2
    
    def test_timer_context_manager(self):
        """Test timer context manager for histograms."""
        from src.core.prometheus import Histogram, Timer
        import time
        
        histogram = Histogram("timer_test_1", "Timer test")
        
        with Timer(histogram):
            time.sleep(0.01)
        
        results = histogram.collect()
        assert len(results) == 1
        assert results[0][1]["count"] == 1
        assert results[0][1]["sum"] >= 0.01
    
    def test_metrics_registry(self):
        """Test metrics registry."""
        from src.core.prometheus import MetricsRegistry
        
        registry = MetricsRegistry(prefix="test_app_1")
        
        counter = registry.counter("requests", "Total requests")
        gauge = registry.gauge("connections", "Active connections")
        histogram = registry.histogram("latency", "Request latency")
        
        counter.inc()
        gauge.set(5)
        histogram.observe(0.1)
        
        output = registry.export_prometheus()
        
        assert "test_app_1_requests" in output
        assert "test_app_1_connections" in output
        assert "test_app_1_latency" in output
    
    def test_prometheus_export_format(self):
        """Test Prometheus text format export."""
        from src.core.prometheus import MetricsRegistry
        
        registry = MetricsRegistry(prefix="app_2")
        counter = registry.counter("http_requests", "HTTP requests", labels=["status"])
        counter.inc(status="200")
        counter.inc(status="500")
        
        output = registry.export_prometheus()
        
        assert '# HELP app_2_http_requests HTTP requests' in output
        assert '# TYPE app_2_http_requests counter' in output
        assert 'app_2_http_requests{status="200"} 1' in output
        assert 'app_2_http_requests{status="500"} 1' in output
    
    def test_json_export(self):
        """Test JSON format export."""
        from src.core.prometheus import MetricsRegistry
        
        registry = MetricsRegistry(prefix="test_3")
        counter = registry.counter("events", "Events")
        counter.inc()
        
        output = registry.export_json()
        
        assert "counters" in output
        assert "gauges" in output
        assert "histograms" in output
        assert "timestamp" in output


# ============================================================================
# Log Shipping Tests
# ============================================================================

class TestLogShipping:
    """Tests for log shipping service."""
    
    def test_log_entry_creation(self):
        """Test LogEntry creation and serialization."""
        from src.core.log_shipping import LogEntry, LogLevel
        
        entry = LogEntry(
            timestamp=datetime.now(timezone.utc),
            level=LogLevel.ERROR,
            logger_name="test.module",
            message="Test error message",
            extra={"user_id": "123"},
            correlation_id="corr-456",
        )
        
        data = entry.to_dict()
        
        assert data["level"] == "ERROR"
        assert data["logger"] == "test.module"
        assert data["message"] == "Test error message"
        assert data["extra"]["user_id"] == "123"
        assert data["correlation_id"] == "corr-456"
    
    def test_log_entry_json(self):
        """Test LogEntry JSON serialization."""
        from src.core.log_shipping import LogEntry, LogLevel
        
        entry = LogEntry(
            timestamp=datetime.now(timezone.utc),
            level=LogLevel.INFO,
            logger_name="test",
            message="Test",
        )
        
        json_str = entry.to_json()
        parsed = json.loads(json_str)
        
        assert parsed["level"] == "INFO"
        assert parsed["message"] == "Test"
    
    @pytest.mark.asyncio
    async def test_file_destination(self):
        """Test file log destination."""
        from src.core.log_shipping import FileDestination, LogEntry, LogLevel
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            file_path = f.name
        
        try:
            dest = FileDestination(file_path, max_size_mb=1, compress=False)
            
            entries = [
                LogEntry(
                    timestamp=datetime.now(timezone.utc),
                    level=LogLevel.INFO,
                    logger_name="test",
                    message=f"Log message {i}",
                )
                for i in range(10)
            ]
            
            result = await dest.send(entries)
            assert result is True
            
            with open(file_path, "r") as f:
                lines = f.readlines()
            
            assert len(lines) == 10
            
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)
    
    def test_log_shipper_stats(self):
        """Test log shipper statistics."""
        from src.core.log_shipping import LogShipper
        
        shipper = LogShipper()
        stats = shipper.get_stats()
        
        assert "entries_queued" in stats
        assert "entries_shipped" in stats
        assert "entries_dropped" in stats
        assert "batches_sent" in stats


# ============================================================================
# Incident Management Tests
# ============================================================================

class TestIncidentManagement:
    """Tests for incident management system."""
    
    def test_incident_creation(self):
        """Test Incident dataclass."""
        from src.core.incident_management import Incident, IncidentSeverity
        
        incident = Incident(
            title="Database Connection Failed",
            description="Unable to connect to primary database",
            severity=IncidentSeverity.CRITICAL,
            source="polymarket-bot",
            component="database",
            dedup_key="db-connection-failed",
        )
        
        data = incident.to_dict()
        
        assert data["title"] == "Database Connection Failed"
        assert data["severity"] == "critical"
        assert data["dedup_key"] == "db-connection-failed"
    
    @pytest.mark.asyncio
    async def test_incident_manager_deduplication(self):
        """Test incident deduplication."""
        from src.core.incident_management import (
            IncidentManager,
            Incident,
            IncidentSeverity,
            AlertingProvider,
        )
        
        mock_provider = MagicMock(spec=AlertingProvider)
        mock_provider.create_incident = AsyncMock(return_value="incident-123")
        
        manager = IncidentManager()
        manager.add_provider(mock_provider)
        
        incident = Incident(
            title="Test Incident",
            description="Test",
            severity=IncidentSeverity.HIGH,
            source="test",
            dedup_key="test-dedup-key-1",
        )
        
        ids1 = await manager.trigger(incident)
        assert len(ids1) == 1
        
        ids2 = await manager.trigger(incident)
        assert len(ids2) == 0
        
        assert mock_provider.create_incident.call_count == 1
    
    @pytest.mark.asyncio
    async def test_incident_resolution(self):
        """Test incident resolution."""
        from src.core.incident_management import (
            IncidentManager,
            Incident,
            IncidentSeverity,
            AlertingProvider,
        )
        
        mock_provider = MagicMock(spec=AlertingProvider)
        mock_provider.create_incident = AsyncMock(return_value="incident-123")
        mock_provider.resolve_incident = AsyncMock(return_value=True)
        
        manager = IncidentManager()
        manager.add_provider(mock_provider)
        
        incident = Incident(
            title="Test",
            description="Test",
            severity=IncidentSeverity.MEDIUM,
            source="test",
            dedup_key="resolve-test-key",
        )
        
        await manager.trigger(incident)
        assert len(manager.get_active_incidents()) == 1
        
        resolved = await manager.resolve("resolve-test-key", "Issue fixed")
        assert resolved is True
        assert len(manager.get_active_incidents()) == 0
    
    def test_slack_provider_colors(self):
        """Test Slack provider severity colors."""
        from src.core.incident_management import (
            SlackAlertingProvider,
            IncidentSeverity,
        )
        
        provider = SlackAlertingProvider(
            webhook_url="https://hooks.slack.com/test",
        )
        
        assert provider.SEVERITY_COLORS[IncidentSeverity.HIGH] == "#FF6600"
        assert provider.SEVERITY_COLORS[IncidentSeverity.CRITICAL] == "#FF0000"


# ============================================================================
# Database Audit Storage Tests
# ============================================================================

class TestDatabaseAuditStorage:
    """Tests for database-backed audit storage."""
    
    def test_audit_event_model_conversion(self):
        """Test converting between AuditEvent and database model."""
        from src.core.audit_db import AuditEventModel
        from src.core.audit import AuditEvent, AuditEventType, AuditSeverity
        
        event = AuditEvent(
            event_type=AuditEventType.ORDER_PLACED,
            severity=AuditSeverity.INFO,
            user_id="user_123",
            action="order_placed",
            resource_type="order",
            resource_id="order_456",
            details={"price": "0.65", "size": "100"},
            correlation_id="corr-789",
        )
        
        model = AuditEventModel.from_audit_event(event)
        
        assert model.event_type == "trading.order_placed"
        assert model.user_id == "user_123"
        assert model.details["price"] == "0.65"
        
        restored = model.to_audit_event()
        
        assert restored.event_type == AuditEventType.ORDER_PLACED
        assert restored.user_id == "user_123"


# ============================================================================
# Redis Rate Limiter Tests
# ============================================================================

class TestRedisRateLimiter:
    """Tests for Redis-based rate limiting."""
    
    def test_config_defaults(self):
        """Test rate limit config defaults."""
        from src.core.redis_rate_limiter import RedisRateLimitConfig
        
        config = RedisRateLimitConfig()
        
        assert config.requests_per_minute == 60
        assert config.requests_per_hour == 1000
        assert config.burst_limit == 20
        assert "/health" in config.exempt_paths
    
    def test_config_custom_values(self):
        """Test rate limit config custom values."""
        from src.core.redis_rate_limiter import RedisRateLimitConfig
        
        config = RedisRateLimitConfig(
            requests_per_minute=120,
            requests_per_hour=2000,
            burst_limit=50,
            key_prefix="custom",
            exempt_paths=["/custom"],
        )
        
        assert config.requests_per_minute == 120
        assert config.requests_per_hour == 2000
        assert config.burst_limit == 50
        assert config.key_prefix == "custom"


# ============================================================================
# Integration Tests
# ============================================================================

class TestAdvancedIntegration:
    """Integration tests for advanced infrastructure."""
    
    @pytest.mark.asyncio
    async def test_metrics_with_alerts(self):
        """Test metrics triggering alerts."""
        from src.core.prometheus import MetricsRegistry
        from src.core.alerts import AlertManager, LogAlertChannel
        
        registry = MetricsRegistry()
        error_counter = registry.counter("errors_int", "Error count", labels=["type"])
        
        alert_manager = AlertManager()
        alert_manager.add_channel(LogAlertChannel())
        
        for i in range(10):
            error_counter.inc(type="database")
        
        results = error_counter.collect()
        error_count = results[0][1]
        
        if error_count >= 10:
            await alert_manager.warning(
                "High Error Rate",
                f"Error count reached {error_count}",
                category="system",
            )
        
        assert error_count == 10
    
    @pytest.mark.asyncio
    async def test_audit_with_metrics(self):
        """Test audit logging with metrics tracking."""
        from src.core.audit import AuditLogger, InMemoryAuditStorage
        from src.core.prometheus import MetricsRegistry
        
        storage = InMemoryAuditStorage()
        audit = AuditLogger(storage)
        
        registry = MetricsRegistry()
        audit_counter = registry.counter("audit_events_int", "Audit events", labels=["type"])
        
        await audit.log_login("user_1", success=True)
        audit_counter.inc(type="login")
        
        await audit.log_order_placed(
            user_id="user_1",
            order_id="order_1",
            market_id="market_1",
            side="buy",
            size=Decimal("100"),
            price=Decimal("0.65"),
        )
        audit_counter.inc(type="order")
        
        events = await audit.query()
        assert len(events) == 2
        
        metrics = audit_counter.collect()
        total = sum(m[1] for m in metrics)
        assert total == 2
    
    def test_full_observability_stack(self):
        """Test complete observability stack setup."""
        from src.core.prometheus import metrics
        from src.core.alerts import alert_manager
        from src.core.audit import audit_logger
        
        assert metrics is not None
        assert alert_manager is not None
        assert audit_logger is not None
