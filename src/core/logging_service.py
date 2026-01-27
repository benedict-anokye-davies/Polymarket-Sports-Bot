"""
Structured logging service with correlation ID tracking.
Provides JSON-formatted logs for production observability.
Integrates sensitive data redaction (REQ-SEC-007).
"""

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any
from functools import lru_cache

from fastapi import Request

from src.core.redaction import redact_sensitive, RedactionConfig


# Context variable for request correlation ID
correlation_id_ctx: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> str | None:
    """Get the current correlation ID from context."""
    return correlation_id_ctx.get()


def set_correlation_id(correlation_id: str | None = None) -> str:
    """
    Set correlation ID for current context.
    Generates a new ID if none provided.
    """
    cid = correlation_id or str(uuid.uuid4())[:8]
    correlation_id_ctx.set(cid)
    return cid


class JSONFormatter(logging.Formatter):
    """
    Custom log formatter that outputs JSON-structured logs.
    Automatically redacts sensitive data (REQ-SEC-007).

    Includes standard fields:
    - timestamp: ISO format timestamp
    - level: Log level name
    - logger: Logger name
    - message: Log message
    - correlation_id: Request correlation ID
    - module/function/line: Source location
    - extra: Any additional context
    """

    RESERVED_ATTRS = {
        "name", "msg", "args", "created", "filename", "funcName",
        "levelname", "levelno", "lineno", "module", "msecs",
        "pathname", "process", "processName", "relativeCreated",
        "stack_info", "exc_info", "exc_text", "thread", "threadName",
        "taskName",
    }

    def __init__(
        self,
        include_source: bool = True,
        include_process: bool = False,
        include_thread: bool = False,
        redact_sensitive_data: bool = True,
    ):
        super().__init__()
        self.include_source = include_source
        self.include_process = include_process
        self.include_thread = include_thread
        self.redact_sensitive_data = redact_sensitive_data
        self.redaction_config = RedactionConfig() if redact_sensitive_data else None

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON string with sensitive data redaction."""
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add correlation ID if available
        cid = get_correlation_id()
        if cid:
            log_data["correlation_id"] = cid

        # Add source location
        if self.include_source:
            log_data["source"] = {
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
            }

        # Add process/thread info if requested
        if self.include_process:
            log_data["process"] = {
                "id": record.process,
                "name": record.processName,
            }

        if self.include_thread:
            log_data["thread"] = {
                "id": record.thread,
                "name": record.threadName,
            }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add any extra fields from the log call
        extra = {}
        for key, value in record.__dict__.items():
            if key not in self.RESERVED_ATTRS and not key.startswith("_"):
                try:
                    json.dumps(value)  # Ensure serializable
                    extra[key] = value
                except (TypeError, ValueError):
                    extra[key] = str(value)

        if extra:
            log_data["extra"] = extra

        # Apply sensitive data redaction (REQ-SEC-007)
        if self.redact_sensitive_data and self.redaction_config:
            log_data = redact_sensitive(log_data, self.redaction_config)

        return json.dumps(log_data)


class ContextLogger(logging.LoggerAdapter):
    """
    Logger adapter that automatically includes context from contextvars.
    
    Usage:
        logger = get_logger(__name__)
        logger.info("Processing order", order_id=123, amount=50.0)
    """
    
    def process(self, msg: str, kwargs: dict) -> tuple[str, dict]:
        """Add context to log record."""
        extra = kwargs.get("extra", {})
        
        # Add correlation ID
        cid = get_correlation_id()
        if cid:
            extra["correlation_id"] = cid
        
        # Merge any keyword arguments into extra
        for key, value in list(kwargs.items()):
            if key not in ("exc_info", "stack_info", "stacklevel", "extra"):
                extra[key] = value
                del kwargs[key]
        
        kwargs["extra"] = extra
        return msg, kwargs


@lru_cache(maxsize=128)
def get_logger(name: str) -> ContextLogger:
    """
    Get a context-aware logger by name.
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        ContextLogger instance
    """
    logger = logging.getLogger(name)
    return ContextLogger(logger, {})


def setup_structured_logging(
    level: str = "INFO",
    json_output: bool = True,
    include_source: bool = True,
) -> None:
    """
    Configure structured logging for the application.
    
    Args:
        level: Minimum log level
        json_output: Use JSON formatting (True for production)
        include_source: Include source file/line info
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level.upper()))
    
    if json_output:
        handler.setFormatter(JSONFormatter(include_source=include_source))
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ))
    
    root_logger.addHandler(handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


class RequestLoggingMiddleware:
    """
    ASGI middleware for request/response logging with correlation IDs.
    
    Features:
    - Assigns correlation ID to each request
    - Logs request start/end with timing
    - Propagates correlation ID in response headers
    """
    
    def __init__(self, app):
        self.app = app
        self.logger = get_logger("api.requests")
    
    async def __call__(self, scope, receive, send):
        """Process ASGI request."""
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        
        # Generate or extract correlation ID
        headers = dict(scope.get("headers", []))
        correlation_id = headers.get(b"x-correlation-id", b"").decode() or None
        correlation_id = set_correlation_id(correlation_id)
        
        # Extract request info
        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "/")
        query = scope.get("query_string", b"").decode()
        
        # Log request start
        start_time = datetime.now(timezone.utc)
        self.logger.info(
            f"Request started: {method} {path}",
            method=method,
            path=path,
            query=query[:200] if query else None,
        )
        
        # Track response status
        response_status = 0
        
        async def send_wrapper(message):
            nonlocal response_status
            if message["type"] == "http.response.start":
                response_status = message["status"]
                # Add correlation ID to response headers
                headers = list(message.get("headers", []))
                headers.append((b"x-correlation-id", correlation_id.encode()))
                message["headers"] = headers
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as e:
            self.logger.error(
                f"Request failed: {method} {path}",
                method=method,
                path=path,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            raise
        finally:
            # Log request completion
            duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            log_level = logging.WARNING if response_status >= 400 else logging.INFO
            
            self.logger.log(
                log_level,
                f"Request completed: {method} {path} -> {response_status}",
                method=method,
                path=path,
                status=response_status,
                duration_ms=round(duration_ms, 2),
            )


# Structured log event helpers
def log_trade_event(
    event_type: str,
    market_id: str,
    **kwargs: Any
) -> None:
    """
    Log a trading-related event with standard fields.
    
    Args:
        event_type: Type of event (order_placed, position_opened, etc.)
        market_id: Market/condition ID
        **kwargs: Additional event-specific data
    """
    logger = get_logger("trading.events")
    logger.info(
        f"Trade event: {event_type}",
        event_type=event_type,
        market_id=market_id,
        **kwargs
    )


def log_system_event(
    event_type: str,
    component: str,
    **kwargs: Any
) -> None:
    """
    Log a system-level event.
    
    Args:
        event_type: Type of event (startup, shutdown, config_change, etc.)
        component: System component name
        **kwargs: Additional event data
    """
    logger = get_logger("system.events")
    logger.info(
        f"System event: {event_type}",
        event_type=event_type,
        component=component,
        **kwargs
    )


def log_security_event(
    event_type: str,
    user_id: str | None = None,
    **kwargs: Any
) -> None:
    """
    Log a security-related event.
    
    Args:
        event_type: Type of event (login, logout, auth_failure, etc.)
        user_id: Associated user ID if known
        **kwargs: Additional event data
    """
    logger = get_logger("security.events")
    logger.warning(
        f"Security event: {event_type}",
        event_type=event_type,
        user_id=user_id,
        **kwargs
    )
