"""
Comprehensive audit trail system for compliance and debugging.
Tracks all significant system events with full context.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Protocol
from decimal import Decimal


logger = logging.getLogger(__name__)


class AuditEventType(str, Enum):
    """Types of audit events."""
    # Authentication events
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_FAILED = "auth.failed"
    AUTH_TOKEN_REFRESH = "auth.token_refresh"
    
    # User events
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"
    USER_SETTINGS_CHANGED = "user.settings_changed"
    
    # Wallet events
    WALLET_CONNECTED = "wallet.connected"
    WALLET_DISCONNECTED = "wallet.disconnected"
    WALLET_CREDENTIALS_UPDATED = "wallet.credentials_updated"
    
    # Trading events
    ORDER_PLACED = "trading.order_placed"
    ORDER_FILLED = "trading.order_filled"
    ORDER_CANCELLED = "trading.order_cancelled"
    ORDER_FAILED = "trading.order_failed"
    POSITION_OPENED = "trading.position_opened"
    POSITION_CLOSED = "trading.position_closed"
    POSITION_MODIFIED = "trading.position_modified"
    
    # Bot events
    BOT_STARTED = "bot.started"
    BOT_STOPPED = "bot.stopped"
    BOT_PAUSED = "bot.paused"
    BOT_RESUMED = "bot.resumed"
    BOT_ERROR = "bot.error"
    BOT_CONFIG_CHANGED = "bot.config_changed"
    
    # Market events
    MARKET_SUBSCRIBED = "market.subscribed"
    MARKET_UNSUBSCRIBED = "market.unsubscribed"
    MARKET_PRICE_ALERT = "market.price_alert"
    MARKET_MATCHED = "market.matched"
    
    # System events
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    SYSTEM_ERROR = "system.error"
    SYSTEM_HEALTH_DEGRADED = "system.health_degraded"
    
    # Security events
    SECURITY_RATE_LIMITED = "security.rate_limited"
    SECURITY_VALIDATION_FAILED = "security.validation_failed"
    SECURITY_SUSPICIOUS_ACTIVITY = "security.suspicious_activity"


class AuditSeverity(str, Enum):
    """Severity levels for audit events."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Represents a single audit event."""
    event_type: AuditEventType
    severity: AuditSeverity
    user_id: str | None
    action: str
    resource_type: str
    resource_id: str | None
    details: dict = field(default_factory=dict)
    ip_address: str | None = None
    user_agent: str | None = None
    correlation_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_id: str = ""
    
    def __post_init__(self):
        if not self.event_id:
            self.event_id = f"{self.event_type.value}_{self.timestamp.timestamp()}"
    
    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "user_id": self.user_id,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "details": self._serialize_details(),
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp.isoformat(),
        }
    
    def _serialize_details(self) -> dict:
        """Serialize details, handling special types."""
        result = {}
        for key, value in self.details.items():
            if isinstance(value, Decimal):
                result[key] = str(value)
            elif isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, Enum):
                result[key] = value.value
            else:
                result[key] = value
        return result


class AuditStorage(Protocol):
    """Protocol for audit event storage backends."""
    
    async def store(self, event: AuditEvent) -> bool:
        """Store an audit event. Returns success status."""
        ...
    
    async def query(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        event_types: list[AuditEventType] | None = None,
        user_id: str | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """Query audit events with filters."""
        ...


class InMemoryAuditStorage:
    """
    In-memory audit storage for development/testing.
    Events are lost on restart.
    """
    
    MAX_EVENTS = 10000
    
    def __init__(self):
        self._events: list[AuditEvent] = []
        self._lock = asyncio.Lock()
    
    async def store(self, event: AuditEvent) -> bool:
        async with self._lock:
            self._events.append(event)
            
            # Prune old events
            if len(self._events) > self.MAX_EVENTS:
                self._events = self._events[-self.MAX_EVENTS:]
            
            return True
    
    async def query(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        event_types: list[AuditEventType] | None = None,
        user_id: str | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        async with self._lock:
            filtered = self._events
            
            if start_time:
                filtered = [e for e in filtered if e.timestamp >= start_time]
            
            if end_time:
                filtered = [e for e in filtered if e.timestamp <= end_time]
            
            if event_types:
                filtered = [e for e in filtered if e.event_type in event_types]
            
            if user_id:
                filtered = [e for e in filtered if e.user_id == user_id]
            
            return sorted(
                filtered,
                key=lambda e: e.timestamp,
                reverse=True
            )[:limit]


class FileAuditStorage:
    """
    File-based audit storage with JSON Lines format.
    Suitable for simple production deployments.
    """
    
    def __init__(self, file_path: str):
        self._file_path = file_path
        self._lock = asyncio.Lock()
    
    async def store(self, event: AuditEvent) -> bool:
        async with self._lock:
            try:
                with open(self._file_path, "a") as f:
                    f.write(json.dumps(event.to_dict()) + "\n")
                return True
            except Exception as e:
                logger.error(f"Failed to write audit event: {e}")
                return False
    
    async def query(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        event_types: list[AuditEventType] | None = None,
        user_id: str | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        events = []
        
        try:
            with open(self._file_path, "r") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        event = self._dict_to_event(data)
                        
                        # Apply filters
                        if start_time and event.timestamp < start_time:
                            continue
                        if end_time and event.timestamp > end_time:
                            continue
                        if event_types and event.event_type not in event_types:
                            continue
                        if user_id and event.user_id != user_id:
                            continue
                        
                        events.append(event)
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.error(f"Failed to read audit events: {e}")
        
        return sorted(events, key=lambda e: e.timestamp, reverse=True)[:limit]
    
    def _dict_to_event(self, data: dict) -> AuditEvent:
        return AuditEvent(
            event_id=data.get("event_id", ""),
            event_type=AuditEventType(data["event_type"]),
            severity=AuditSeverity(data["severity"]),
            user_id=data.get("user_id"),
            action=data["action"],
            resource_type=data["resource_type"],
            resource_id=data.get("resource_id"),
            details=data.get("details", {}),
            ip_address=data.get("ip_address"),
            user_agent=data.get("user_agent"),
            correlation_id=data.get("correlation_id"),
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )


class AuditLogger:
    """
    Central audit logging service.
    
    Provides high-level methods for logging common events
    with proper categorization and context.
    """
    
    def __init__(self, storage: AuditStorage):
        self._storage = storage
        self._enabled = True
    
    async def log(self, event: AuditEvent) -> bool:
        """Log an audit event."""
        if not self._enabled:
            return False
        
        success = await self._storage.store(event)
        
        # Also log to standard logger for debugging
        log_level = {
            AuditSeverity.INFO: logging.INFO,
            AuditSeverity.WARNING: logging.WARNING,
            AuditSeverity.ERROR: logging.ERROR,
            AuditSeverity.CRITICAL: logging.CRITICAL,
        }.get(event.severity, logging.INFO)
        
        logger.log(
            log_level,
            f"AUDIT: {event.event_type.value} - {event.action}",
            extra={"audit_event": event.to_dict()},
        )
        
        return success
    
    async def query(self, **kwargs) -> list[AuditEvent]:
        """Query audit events."""
        return await self._storage.query(**kwargs)
    
    # Authentication events
    async def log_login(
        self,
        user_id: str,
        ip_address: str | None = None,
        success: bool = True,
    ) -> bool:
        return await self.log(AuditEvent(
            event_type=AuditEventType.AUTH_LOGIN if success else AuditEventType.AUTH_FAILED,
            severity=AuditSeverity.INFO if success else AuditSeverity.WARNING,
            user_id=user_id,
            action="login" if success else "login_failed",
            resource_type="session",
            resource_id=None,
            ip_address=ip_address,
        ))
    
    async def log_logout(self, user_id: str) -> bool:
        return await self.log(AuditEvent(
            event_type=AuditEventType.AUTH_LOGOUT,
            severity=AuditSeverity.INFO,
            user_id=user_id,
            action="logout",
            resource_type="session",
            resource_id=None,
        ))
    
    # Trading events
    async def log_order_placed(
        self,
        user_id: str,
        order_id: str,
        market_id: str,
        side: str,
        size: Decimal,
        price: Decimal,
        correlation_id: str | None = None,
    ) -> bool:
        return await self.log(AuditEvent(
            event_type=AuditEventType.ORDER_PLACED,
            severity=AuditSeverity.INFO,
            user_id=user_id,
            action="order_placed",
            resource_type="order",
            resource_id=order_id,
            details={
                "market_id": market_id,
                "side": side,
                "size": size,
                "price": price,
            },
            correlation_id=correlation_id,
        ))
    
    async def log_order_filled(
        self,
        user_id: str,
        order_id: str,
        fill_price: Decimal,
        fill_size: Decimal,
    ) -> bool:
        return await self.log(AuditEvent(
            event_type=AuditEventType.ORDER_FILLED,
            severity=AuditSeverity.INFO,
            user_id=user_id,
            action="order_filled",
            resource_type="order",
            resource_id=order_id,
            details={
                "fill_price": fill_price,
                "fill_size": fill_size,
            },
        ))
    
    async def log_order_cancelled(
        self,
        user_id: str,
        order_id: str,
        reason: str,
    ) -> bool:
        return await self.log(AuditEvent(
            event_type=AuditEventType.ORDER_CANCELLED,
            severity=AuditSeverity.INFO,
            user_id=user_id,
            action="order_cancelled",
            resource_type="order",
            resource_id=order_id,
            details={"reason": reason},
        ))
    
    async def log_position_opened(
        self,
        user_id: str,
        position_id: str,
        market_id: str,
        side: str,
        size: Decimal,
        entry_price: Decimal,
    ) -> bool:
        return await self.log(AuditEvent(
            event_type=AuditEventType.POSITION_OPENED,
            severity=AuditSeverity.INFO,
            user_id=user_id,
            action="position_opened",
            resource_type="position",
            resource_id=position_id,
            details={
                "market_id": market_id,
                "side": side,
                "size": size,
                "entry_price": entry_price,
            },
        ))
    
    async def log_position_closed(
        self,
        user_id: str,
        position_id: str,
        exit_price: Decimal,
        pnl: Decimal,
        reason: str,
    ) -> bool:
        return await self.log(AuditEvent(
            event_type=AuditEventType.POSITION_CLOSED,
            severity=AuditSeverity.INFO,
            user_id=user_id,
            action="position_closed",
            resource_type="position",
            resource_id=position_id,
            details={
                "exit_price": exit_price,
                "pnl": pnl,
                "reason": reason,
            },
        ))
    
    # Bot events
    async def log_bot_started(self, user_id: str, config: dict) -> bool:
        return await self.log(AuditEvent(
            event_type=AuditEventType.BOT_STARTED,
            severity=AuditSeverity.INFO,
            user_id=user_id,
            action="bot_started",
            resource_type="bot",
            resource_id=user_id,
            details={"config": config},
        ))
    
    async def log_bot_stopped(self, user_id: str, reason: str) -> bool:
        return await self.log(AuditEvent(
            event_type=AuditEventType.BOT_STOPPED,
            severity=AuditSeverity.INFO,
            user_id=user_id,
            action="bot_stopped",
            resource_type="bot",
            resource_id=user_id,
            details={"reason": reason},
        ))
    
    async def log_bot_error(
        self,
        user_id: str,
        error_type: str,
        error_message: str,
    ) -> bool:
        return await self.log(AuditEvent(
            event_type=AuditEventType.BOT_ERROR,
            severity=AuditSeverity.ERROR,
            user_id=user_id,
            action="bot_error",
            resource_type="bot",
            resource_id=user_id,
            details={
                "error_type": error_type,
                "error_message": error_message,
            },
        ))
    
    # Security events
    async def log_rate_limited(
        self,
        ip_address: str,
        endpoint: str,
        user_id: str | None = None,
    ) -> bool:
        return await self.log(AuditEvent(
            event_type=AuditEventType.SECURITY_RATE_LIMITED,
            severity=AuditSeverity.WARNING,
            user_id=user_id,
            action="rate_limited",
            resource_type="request",
            resource_id=None,
            ip_address=ip_address,
            details={"endpoint": endpoint},
        ))
    
    async def log_validation_failed(
        self,
        ip_address: str,
        endpoint: str,
        error: str,
        user_id: str | None = None,
    ) -> bool:
        return await self.log(AuditEvent(
            event_type=AuditEventType.SECURITY_VALIDATION_FAILED,
            severity=AuditSeverity.WARNING,
            user_id=user_id,
            action="validation_failed",
            resource_type="request",
            resource_id=None,
            ip_address=ip_address,
            details={
                "endpoint": endpoint,
                "error": error,
            },
        ))
    
    # System events
    async def log_system_startup(self, version: str, environment: str) -> bool:
        return await self.log(AuditEvent(
            event_type=AuditEventType.SYSTEM_STARTUP,
            severity=AuditSeverity.INFO,
            user_id=None,
            action="system_startup",
            resource_type="system",
            resource_id=None,
            details={
                "version": version,
                "environment": environment,
            },
        ))
    
    async def log_system_shutdown(self, reason: str) -> bool:
        return await self.log(AuditEvent(
            event_type=AuditEventType.SYSTEM_SHUTDOWN,
            severity=AuditSeverity.INFO,
            user_id=None,
            action="system_shutdown",
            resource_type="system",
            resource_id=None,
            details={"reason": reason},
        ))


# Global audit logger instance
audit_logger = AuditLogger(InMemoryAuditStorage())


def setup_audit_logger(
    storage_type: str = "memory",
    file_path: str | None = None,
) -> AuditLogger:
    """
    Configure the global audit logger.
    
    Args:
        storage_type: "memory" or "file"
        file_path: Path for file storage (required if storage_type="file")
    
    Returns:
        Configured AuditLogger
    """
    global audit_logger
    
    if storage_type == "file":
        if not file_path:
            raise ValueError("file_path required for file storage")
        storage = FileAuditStorage(file_path)
    else:
        storage = InMemoryAuditStorage()
    
    audit_logger = AuditLogger(storage)
    return audit_logger
