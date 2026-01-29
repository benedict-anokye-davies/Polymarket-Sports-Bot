"""
Rate limiting middleware for API protection.
Implements sliding window rate limiting with per-IP and per-user limits.

Uses pure ASGI implementation to avoid request body consumption issues
that occur with Starlette's BaseHTTPMiddleware.
"""

import asyncio
import time
import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Awaitable
import logging

from fastapi import Request, HTTPException
from starlette.types import ASGIApp, Receive, Send, Scope, Message
from starlette.status import HTTP_429_TOO_MANY_REQUESTS


logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """
    Configuration for rate limiting.
    
    Attributes:
        requests_per_minute: Maximum requests allowed per minute
        requests_per_hour: Maximum requests allowed per hour
        burst_limit: Maximum burst requests in short window
        burst_window_seconds: Window size for burst detection
        exempt_paths: URL paths exempt from rate limiting
    """
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_limit: int = 20
    burst_window_seconds: float = 1.0
    exempt_paths: list[str] = field(default_factory=lambda: [
        "/health",
        "/docs",
        "/openapi.json",
        "/redoc",
    ])


@dataclass
class RateLimitState:
    """Tracks request counts for a single client."""
    minute_requests: list[float] = field(default_factory=list)
    hour_requests: list[float] = field(default_factory=list)
    burst_requests: list[float] = field(default_factory=list)
    
    def cleanup(self, now: float) -> None:
        """Remove expired timestamps from tracking lists."""
        minute_ago = now - 60
        hour_ago = now - 3600
        burst_ago = now - 1.0
        
        self.minute_requests = [t for t in self.minute_requests if t > minute_ago]
        self.hour_requests = [t for t in self.hour_requests if t > hour_ago]
        self.burst_requests = [t for t in self.burst_requests if t > burst_ago]
    
    def record_request(self, now: float) -> None:
        """Record a new request timestamp."""
        self.minute_requests.append(now)
        self.hour_requests.append(now)
        self.burst_requests.append(now)


class RateLimiter:
    """
    Sliding window rate limiter with multiple time windows.
    
    Tracks requests per client (IP or user ID) across:
    - Per-minute limit for sustained rate
    - Per-hour limit for overall volume
    - Burst limit for short-term spikes
    
    Thread-safe using asyncio locks.
    """
    
    def __init__(self, config: RateLimitConfig | None = None):
        self.config = config or RateLimitConfig()
        self._states: dict[str, RateLimitState] = defaultdict(RateLimitState)
        self._lock = asyncio.Lock()
        self._cleanup_interval = 60.0
        self._last_cleanup = time.time()
    
    async def check_rate_limit(self, client_id: str) -> tuple[bool, dict]:
        """
        Check if a client has exceeded rate limits.
        
        Args:
            client_id: Unique identifier for the client (IP or user ID)
        
        Returns:
            Tuple of (is_allowed, limit_info_dict)
        """
        now = time.time()
        
        async with self._lock:
            # Periodic cleanup of old data
            if now - self._last_cleanup > self._cleanup_interval:
                await self._cleanup_old_states(now)
                self._last_cleanup = now
            
            state = self._states[client_id]
            state.cleanup(now)
            
            # Check limits
            minute_count = len(state.minute_requests)
            hour_count = len(state.hour_requests)
            burst_count = len(state.burst_requests)
            
            limit_info: dict[str, int | float | str] = {
                "minute_count": minute_count,
                "minute_limit": self.config.requests_per_minute,
                "hour_count": hour_count,
                "hour_limit": self.config.requests_per_hour,
                "burst_count": burst_count,
                "burst_limit": self.config.burst_limit,
            }
            
            # Check burst limit first (short window)
            if burst_count >= self.config.burst_limit:
                limit_info["exceeded"] = "burst"
                limit_info["retry_after"] = self.config.burst_window_seconds
                return False, limit_info
            
            # Check minute limit
            if minute_count >= self.config.requests_per_minute:
                oldest = min(state.minute_requests) if state.minute_requests else now
                limit_info["exceeded"] = "minute"
                limit_info["retry_after"] = max(1, 60 - (now - oldest))
                return False, limit_info
            
            # Check hour limit
            if hour_count >= self.config.requests_per_hour:
                oldest = min(state.hour_requests) if state.hour_requests else now
                limit_info["exceeded"] = "hour"
                limit_info["retry_after"] = max(1, 3600 - (now - oldest))
                return False, limit_info
            
            # Record this request
            state.record_request(now)
            limit_info["remaining_minute"] = self.config.requests_per_minute - minute_count - 1
            limit_info["remaining_hour"] = self.config.requests_per_hour - hour_count - 1
            
            return True, limit_info
    
    async def _cleanup_old_states(self, now: float) -> None:
        """Remove state for clients with no recent requests."""
        hour_ago = now - 3600
        empty_clients = [
            client_id for client_id, state in self._states.items()
            if not state.hour_requests or max(state.hour_requests) < hour_ago
        ]
        for client_id in empty_clients:
            del self._states[client_id]
        
        if empty_clients:
            logger.debug(f"Rate limiter cleanup: removed {len(empty_clients)} inactive clients")
    
    def get_client_stats(self, client_id: str) -> dict:
        """Get current rate limit stats for a client."""
        state = self._states.get(client_id)
        if not state:
            return {
                "minute_count": 0,
                "hour_count": 0,
                "burst_count": 0,
            }
        
        now = time.time()
        state.cleanup(now)
        return {
            "minute_count": len(state.minute_requests),
            "hour_count": len(state.hour_requests),
            "burst_count": len(state.burst_requests),
        }


class RateLimitMiddleware:
    """
    Pure ASGI middleware that enforces rate limits on incoming requests.
    
    Does NOT inherit from BaseHTTPMiddleware to avoid request body
    consumption issues that break FastAPI's Pydantic parsing.
    
    Features:
    - Per-IP rate limiting for unauthenticated requests
    - Configurable exempt paths
    - Rate limit headers in responses
    """
    
    def __init__(
        self,
        app: ASGIApp,
        config: RateLimitConfig | None = None,
    ):
        self.app = app
        self.config = config or RateLimitConfig()
        self.limiter = RateLimiter(self.config)
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """ASGI interface - process request through rate limiter."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Skip exempt paths
        path = scope.get("path", "")
        if path in self.config.exempt_paths:
            await self.app(scope, receive, send)
            return
        
        # Get client identifier from scope
        client_id = self._get_client_id(scope)
        
        # Check rate limit
        is_allowed, limit_info = await self.limiter.check_rate_limit(client_id)
        
        if not is_allowed:
            retry_after = int(limit_info.get("retry_after", 60))
            exceeded = limit_info.get("exceeded", "unknown")
            
            logger.warning(
                f"Rate limit exceeded for {client_id}: {exceeded} limit, "
                f"retry after {retry_after}s"
            )
            
            # Send 429 response directly
            await self._send_rate_limit_response(send, retry_after, exceeded, limit_info)
            return
        
        # Wrap send to add rate limit headers
        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend([
                    (b"x-ratelimit-limit-minute", str(self.config.requests_per_minute).encode()),
                    (b"x-ratelimit-remaining-minute", str(limit_info.get("remaining_minute", 0)).encode()),
                    (b"x-ratelimit-limit-hour", str(self.config.requests_per_hour).encode()),
                    (b"x-ratelimit-remaining-hour", str(limit_info.get("remaining_hour", 0)).encode()),
                ])
                message = {**message, "headers": headers}
            await send(message)
        
        await self.app(scope, receive, send_with_headers)
    
    async def _send_rate_limit_response(
        self,
        send: Send,
        retry_after: int,
        exceeded: str,
        limit_info: dict
    ) -> None:
        """Send a 429 Too Many Requests response."""
        body = json.dumps({
            "detail": {
                "error": "rate_limit_exceeded",
                "limit_type": exceeded,
                "retry_after": retry_after,
                "message": f"Too many requests. Please retry after {retry_after} seconds."
            }
        }).encode()
        
        headers = [
            (b"content-type", b"application/json"),
            (b"retry-after", str(retry_after).encode()),
            (b"x-ratelimit-limit", str(limit_info.get(f"{exceeded}_limit", 0)).encode()),
            (b"x-ratelimit-remaining", b"0"),
            (b"x-ratelimit-reset", str(int(time.time() + retry_after)).encode()),
        ]
        
        await send({
            "type": "http.response.start",
            "status": HTTP_429_TOO_MANY_REQUESTS,
            "headers": headers,
        })
        await send({
            "type": "http.response.body",
            "body": body,
        })
    
    def _get_client_id(self, scope: Scope) -> str:
        """
        Extract client identifier from ASGI scope.
        Uses IP address from headers or connection info.
        """
        headers = dict(scope.get("headers", []))
        
        # Check X-Forwarded-For header (for proxied requests)
        forwarded = headers.get(b"x-forwarded-for", b"").decode()
        if forwarded:
            ip = forwarded.split(",")[0].strip()
            return f"ip:{ip}"
        
        # Fall back to direct client IP
        client = scope.get("client")
        if client:
            return f"ip:{client[0]}"
        
        return "ip:unknown"


# Default rate limiter instance
default_rate_limiter = RateLimiter()


# Auth-specific rate limiter with stricter limits for sensitive endpoints
_auth_rate_limiter = RateLimiter(RateLimitConfig(
    requests_per_minute=10,
    requests_per_hour=50,
    burst_limit=5,
    burst_window_seconds=1.0,
    exempt_paths=[],
))


async def check_auth_rate_limit(request: Request) -> None:
    """
    Dependency for auth endpoints to apply stricter rate limits.
    
    Applies:
    - 10 requests/minute for login/register/refresh
    - 50 requests/hour
    - Burst limit of 5 requests/second
    
    Raises HTTPException with 429 if limit exceeded.
    """
    # Get client IP
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else "unknown"
    
    client_id = f"auth:{ip}"
    
    is_allowed, limit_info = await _auth_rate_limiter.check_rate_limit(client_id)
    
    if not is_allowed:
        retry_after = int(limit_info.get("retry_after", 60))
        exceeded = limit_info.get("exceeded", "unknown")
        
        logger.warning(
            f"Auth rate limit exceeded for {client_id}: {exceeded} limit, "
            f"retry after {retry_after}s"
        )
        
        raise HTTPException(
            status_code=HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "auth_rate_limit_exceeded",
                "limit_type": exceeded,
                "retry_after": retry_after,
                "message": f"Too many authentication attempts. Please retry after {retry_after} seconds."
            },
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(limit_info.get(f"{exceeded}_limit", 0)),
                "X-RateLimit-Remaining": "0",
            }
        )


def create_rate_limit_middleware(
    requests_per_minute: int = 60,
    requests_per_hour: int = 1000,
    burst_limit: int = 20,
    exempt_paths: list[str] | None = None,
) -> Callable[[ASGIApp], RateLimitMiddleware]:
    """
    Factory function to create rate limit middleware with custom config.
    
    Args:
        requests_per_minute: Max requests per minute per client
        requests_per_hour: Max requests per hour per client
        burst_limit: Max burst requests in 1 second
        exempt_paths: URL paths to exempt from limiting
    
    Returns:
        Callable that creates a configured RateLimitMiddleware instance
    """
    config = RateLimitConfig(
        requests_per_minute=requests_per_minute,
        requests_per_hour=requests_per_hour,
        burst_limit=burst_limit,
        exempt_paths=exempt_paths or RateLimitConfig().exempt_paths,
    )
    return lambda app: RateLimitMiddleware(app, config=config)
