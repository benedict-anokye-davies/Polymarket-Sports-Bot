"""
Simple in-memory caching for API responses.
Provides TTL-based caching for ESPN data, market data, and other
frequently accessed but slowly changing data.
"""

import asyncio
import logging
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable

logger = logging.getLogger(__name__)


class CacheEntry:
    """Single cache entry with value and expiration."""
    
    def __init__(self, value: Any, ttl_seconds: int):
        self.value = value
        self.expires_at = datetime.now(timezone.utc).timestamp() + ttl_seconds
    
    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc).timestamp() > self.expires_at


class InMemoryCache:
    """
    Thread-safe in-memory cache with TTL support.
    
    Suitable for caching ESPN game data, market prices, and other
    data that doesn't need to be shared across instances.
    
    For distributed caching, use Redis (see redis_rate_limiter.py).
    """
    
    def __init__(self, default_ttl: int = 60):
        """
        Initialize cache with default TTL.
        
        Args:
            default_ttl: Default time-to-live in seconds for cache entries
        """
        self._cache: dict[str, CacheEntry] = {}
        self._default_ttl = default_ttl
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Any | None:
        """
        Get value from cache if exists and not expired.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        entry = self._cache.get(key)
        if entry is None:
            return None
        
        if entry.is_expired:
            async with self._lock:
                self._cache.pop(key, None)
            return None
        
        return entry.value
    
    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """
        Set value in cache with optional custom TTL.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if not specified)
        """
        ttl = ttl if ttl is not None else self._default_ttl
        async with self._lock:
            self._cache[key] = CacheEntry(value, ttl)
    
    async def delete(self, key: str) -> bool:
        """
        Delete a key from cache.
        
        Args:
            key: Cache key to delete
            
        Returns:
            True if key existed and was deleted
        """
        async with self._lock:
            return self._cache.pop(key, None) is not None
    
    async def clear(self) -> None:
        """Clear all entries from cache."""
        async with self._lock:
            self._cache.clear()
    
    async def cleanup_expired(self) -> int:
        """
        Remove all expired entries from cache.
        
        Returns:
            Number of entries removed
        """
        async with self._lock:
            expired_keys = [k for k, v in self._cache.items() if v.is_expired]
            for key in expired_keys:
                del self._cache[key]
            return len(expired_keys)
    
    @property
    def size(self) -> int:
        """Current number of entries in cache."""
        return len(self._cache)


# Global cache instances for different data types
espn_cache = InMemoryCache(default_ttl=30)  # ESPN data refreshes every 30s
market_cache = InMemoryCache(default_ttl=10)  # Market prices refresh every 10s
settings_cache = InMemoryCache(default_ttl=300)  # Settings cache for 5 minutes


def cached(
    cache: InMemoryCache,
    key_prefix: str = "",
    ttl: int | None = None,
) -> Callable:
    """
    Decorator for caching async function results.
    
    Args:
        cache: Cache instance to use
        key_prefix: Prefix for cache keys
        ttl: Optional custom TTL in seconds
    
    Usage:
        @cached(espn_cache, "scoreboard", ttl=30)
        async def get_scoreboard(sport: str) -> dict:
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Build cache key from function name and arguments
            key_parts = [key_prefix, func.__name__]
            key_parts.extend(str(a) for a in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = ":".join(filter(None, key_parts))
            
            # Check cache
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_value
            
            # Call function and cache result
            logger.debug(f"Cache miss: {cache_key}")
            result = await func(*args, **kwargs)
            await cache.set(cache_key, result, ttl)
            return result
        
        return wrapper
    return decorator


async def get_cache_stats() -> dict[str, Any]:
    """
    Get statistics about all cache instances.
    
    Returns:
        Dictionary with cache sizes and stats
    """
    return {
        "espn_cache": {
            "size": espn_cache.size,
            "default_ttl": espn_cache._default_ttl,
        },
        "market_cache": {
            "size": market_cache.size,
            "default_ttl": market_cache._default_ttl,
        },
        "settings_cache": {
            "size": settings_cache.size,
            "default_ttl": settings_cache._default_ttl,
        },
    }
