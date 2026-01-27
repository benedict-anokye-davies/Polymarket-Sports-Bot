"""
Distributed rate limiting using Redis.
Provides consistent rate limiting across multiple application instances.
"""

import asyncio
import time
import logging
import hashlib
from dataclasses import dataclass, field
from typing import Any


logger = logging.getLogger(__name__)


@dataclass
class RedisRateLimitConfig:
    """Configuration for Redis-based rate limiting."""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_limit: int = 20
    burst_window_seconds: float = 1.0
    key_prefix: str = "ratelimit"
    exempt_paths: list[str] = field(default_factory=lambda: [
        "/health",
        "/docs",
        "/openapi.json",
        "/metrics",
    ])


class RedisRateLimiter:
    """
    Distributed rate limiter using Redis.
    
    Uses sliding window algorithm with Redis sorted sets for
    accurate rate limiting across multiple instances.
    
    Features:
    - Per-minute, per-hour, and burst limits
    - Consistent across multiple app instances
    - Atomic operations using Lua scripts
    - Automatic cleanup of expired entries
    """
    
    # Lua script for atomic rate limit check and increment
    RATE_LIMIT_SCRIPT = """
    local key = KEYS[1]
    local now = tonumber(ARGV[1])
    local window = tonumber(ARGV[2])
    local limit = tonumber(ARGV[3])
    
    -- Remove old entries outside the window
    redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)
    
    -- Count current requests in window
    local count = redis.call('ZCARD', key)
    
    if count < limit then
        -- Add new request
        redis.call('ZADD', key, now, now .. '-' .. math.random())
        -- Set expiry on the key
        redis.call('EXPIRE', key, window + 1)
        return {1, limit - count - 1}  -- allowed, remaining
    else
        -- Get oldest entry to calculate retry-after
        local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
        local retry_after = 0
        if oldest[2] then
            retry_after = window - (now - oldest[2])
        end
        return {0, retry_after}  -- denied, retry_after
    end
    """
    
    def __init__(
        self,
        redis_client,
        config: RedisRateLimitConfig | None = None,
    ):
        """
        Initialize Redis rate limiter.
        
        Args:
            redis_client: Async Redis client (aioredis)
            config: Rate limit configuration
        """
        self._redis = redis_client
        self.config = config or RedisRateLimitConfig()
        self._script_sha: str | None = None
    
    async def _ensure_script_loaded(self) -> str:
        """Load Lua script into Redis if not already loaded."""
        if self._script_sha is None:
            self._script_sha = await self._redis.script_load(self.RATE_LIMIT_SCRIPT)
        return self._script_sha
    
    def _make_key(self, client_id: str, window: str) -> str:
        """Generate Redis key for rate limit tracking."""
        # Hash client_id for privacy and consistent key length
        client_hash = hashlib.sha256(client_id.encode()).hexdigest()[:16]
        return f"{self.config.key_prefix}:{window}:{client_hash}"
    
    async def check_rate_limit(self, client_id: str) -> tuple[bool, dict]:
        """
        Check if a client has exceeded rate limits.
        
        Uses Redis sorted sets with sliding window algorithm.
        Checks burst, minute, and hour limits in order.
        
        Args:
            client_id: Unique identifier for the client
        
        Returns:
            Tuple of (is_allowed, limit_info_dict)
        """
        now = time.time()
        script_sha = await self._ensure_script_loaded()
        
        limit_info = {
            "client_id": client_id[:8] + "...",  # Truncate for privacy
            "timestamp": now,
        }
        
        # Check burst limit (1 second window)
        burst_key = self._make_key(client_id, "burst")
        burst_result = await self._redis.evalsha(
            script_sha,
            1,
            burst_key,
            now,
            self.config.burst_window_seconds,
            self.config.burst_limit,
        )
        
        if burst_result[0] == 0:
            limit_info["exceeded"] = "burst"
            limit_info["retry_after"] = max(0.1, burst_result[1])
            limit_info["burst_limit"] = self.config.burst_limit
            return False, limit_info
        
        limit_info["burst_remaining"] = burst_result[1]
        
        # Check minute limit
        minute_key = self._make_key(client_id, "minute")
        minute_result = await self._redis.evalsha(
            script_sha,
            1,
            minute_key,
            now,
            60,
            self.config.requests_per_minute,
        )
        
        if minute_result[0] == 0:
            limit_info["exceeded"] = "minute"
            limit_info["retry_after"] = max(1, minute_result[1])
            limit_info["minute_limit"] = self.config.requests_per_minute
            return False, limit_info
        
        limit_info["minute_remaining"] = minute_result[1]
        
        # Check hour limit
        hour_key = self._make_key(client_id, "hour")
        hour_result = await self._redis.evalsha(
            script_sha,
            1,
            hour_key,
            now,
            3600,
            self.config.requests_per_hour,
        )
        
        if hour_result[0] == 0:
            limit_info["exceeded"] = "hour"
            limit_info["retry_after"] = max(1, hour_result[1])
            limit_info["hour_limit"] = self.config.requests_per_hour
            return False, limit_info
        
        limit_info["hour_remaining"] = hour_result[1]
        
        return True, limit_info
    
    async def get_client_status(self, client_id: str) -> dict:
        """
        Get current rate limit status for a client.
        
        Returns:
            Dict with current counts and limits
        """
        now = time.time()
        
        # Get counts for all windows
        burst_key = self._make_key(client_id, "burst")
        minute_key = self._make_key(client_id, "minute")
        hour_key = self._make_key(client_id, "hour")
        
        # Remove expired entries and count
        async with self._redis.pipeline() as pipe:
            pipe.zremrangebyscore(burst_key, "-inf", now - self.config.burst_window_seconds)
            pipe.zcard(burst_key)
            pipe.zremrangebyscore(minute_key, "-inf", now - 60)
            pipe.zcard(minute_key)
            pipe.zremrangebyscore(hour_key, "-inf", now - 3600)
            pipe.zcard(hour_key)
            results = await pipe.execute()
        
        return {
            "burst": {
                "count": results[1],
                "limit": self.config.burst_limit,
                "remaining": max(0, self.config.burst_limit - results[1]),
            },
            "minute": {
                "count": results[3],
                "limit": self.config.requests_per_minute,
                "remaining": max(0, self.config.requests_per_minute - results[3]),
            },
            "hour": {
                "count": results[5],
                "limit": self.config.requests_per_hour,
                "remaining": max(0, self.config.requests_per_hour - results[5]),
            },
        }
    
    async def reset_client(self, client_id: str) -> None:
        """Reset all rate limits for a client."""
        keys = [
            self._make_key(client_id, "burst"),
            self._make_key(client_id, "minute"),
            self._make_key(client_id, "hour"),
        ]
        await self._redis.delete(*keys)
    
    async def get_global_stats(self) -> dict:
        """
        Get global rate limiting statistics.
        
        Returns:
            Dict with key counts and memory usage
        """
        pattern = f"{self.config.key_prefix}:*"
        
        # Count keys by type
        cursor = 0
        key_counts = {"burst": 0, "minute": 0, "hour": 0}
        
        while True:
            cursor, keys = await self._redis.scan(cursor, match=pattern, count=1000)
            for key in keys:
                key_str = key.decode() if isinstance(key, bytes) else key
                if ":burst:" in key_str:
                    key_counts["burst"] += 1
                elif ":minute:" in key_str:
                    key_counts["minute"] += 1
                elif ":hour:" in key_str:
                    key_counts["hour"] += 1
            
            if cursor == 0:
                break
        
        return {
            "active_clients": key_counts,
            "config": {
                "burst_limit": self.config.burst_limit,
                "requests_per_minute": self.config.requests_per_minute,
                "requests_per_hour": self.config.requests_per_hour,
            },
        }


class RedisRateLimitMiddleware:
    """
    FastAPI middleware for Redis-based rate limiting.
    """
    
    def __init__(
        self,
        app,
        redis_client,
        config: RedisRateLimitConfig | None = None,
    ):
        self.app = app
        self._limiter = RedisRateLimiter(redis_client, config)
        self._config = config or RedisRateLimitConfig()
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Check exempt paths
        path = scope.get("path", "")
        if any(path.startswith(p) for p in self._config.exempt_paths):
            await self.app(scope, receive, send)
            return
        
        # Get client identifier
        client_id = self._get_client_id(scope)
        
        # Check rate limit
        allowed, info = await self._limiter.check_rate_limit(client_id)
        
        if not allowed:
            # Send 429 response
            response = {
                "error": "rate_limit_exceeded",
                "message": f"Rate limit exceeded: {info.get('exceeded', 'unknown')}",
                "retry_after": info.get("retry_after", 60),
            }
            
            await self._send_json_response(
                send,
                status=429,
                body=response,
                headers=[
                    (b"retry-after", str(int(info.get("retry_after", 60))).encode()),
                    (b"x-ratelimit-exceeded", info.get("exceeded", "unknown").encode()),
                ],
            )
            return
        
        # Add rate limit headers to response
        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend([
                    (b"x-ratelimit-limit-minute", str(self._config.requests_per_minute).encode()),
                    (b"x-ratelimit-remaining-minute", str(info.get("minute_remaining", 0)).encode()),
                    (b"x-ratelimit-limit-hour", str(self._config.requests_per_hour).encode()),
                    (b"x-ratelimit-remaining-hour", str(info.get("hour_remaining", 0)).encode()),
                ])
                message["headers"] = headers
            await send(message)
        
        await self.app(scope, receive, send_with_headers)
    
    def _get_client_id(self, scope) -> str:
        """Extract client identifier from request."""
        # Try to get user ID from state (set by auth middleware)
        state = scope.get("state", {})
        if user_id := state.get("user_id"):
            return f"user:{user_id}"
        
        # Fall back to IP address
        client = scope.get("client")
        if client:
            return f"ip:{client[0]}"
        
        # Check X-Forwarded-For header
        headers = dict(scope.get("headers", []))
        forwarded = headers.get(b"x-forwarded-for", b"").decode()
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"
        
        return "ip:unknown"
    
    async def _send_json_response(
        self,
        send,
        status: int,
        body: dict,
        headers: list | None = None,
    ):
        """Send a JSON response."""
        import json
        
        body_bytes = json.dumps(body).encode()
        
        response_headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body_bytes)).encode()),
        ]
        if headers:
            response_headers.extend(headers)
        
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": response_headers,
        })
        await send({
            "type": "http.response.body",
            "body": body_bytes,
        })


async def create_redis_rate_limiter(
    redis_url: str,
    config: RedisRateLimitConfig | None = None,
) -> RedisRateLimiter:
    """
    Factory function to create Redis rate limiter.
    
    Args:
        redis_url: Redis connection URL
        config: Rate limit configuration
    
    Returns:
        Configured RedisRateLimiter instance
    """
    try:
        import redis.asyncio as aioredis
        
        client = aioredis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=False,
        )
        
        # Test connection
        await client.ping()
        
        logger.info("Redis rate limiter connected successfully")
        return RedisRateLimiter(client, config)
        
    except ImportError:
        logger.error("redis package not installed. Install with: pip install redis")
        raise
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        raise
