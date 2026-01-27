"""
Price history cache service with TTL-based expiration.
Provides fast access to recent price data for analytics and backtesting.
"""

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Iterator
import logging


logger = logging.getLogger(__name__)


@dataclass
class PriceSnapshot:
    """A single price point in time."""
    price: Decimal
    timestamp: datetime
    bid: Decimal = Decimal("0")
    ask: Decimal = Decimal("0")
    volume: Decimal = Decimal("0")
    source: str = "websocket"
    
    @property
    def spread(self) -> Decimal:
        """Calculate bid-ask spread."""
        return self.ask - self.bid
    
    @property
    def mid(self) -> Decimal:
        """Calculate mid price."""
        if self.bid > 0 and self.ask > 0:
            return (self.bid + self.ask) / 2
        return self.price


@dataclass
class PriceStats:
    """Statistical summary of price data."""
    high: Decimal
    low: Decimal
    open: Decimal
    close: Decimal
    vwap: Decimal
    count: int
    volume: Decimal
    period_start: datetime
    period_end: datetime
    
    @property
    def change(self) -> Decimal:
        """Price change from open to close."""
        return self.close - self.open
    
    @property
    def change_pct(self) -> Decimal:
        """Percentage change from open."""
        if self.open == 0:
            return Decimal("0")
        return (self.change / self.open) * 100
    
    @property
    def range(self) -> Decimal:
        """High-low range."""
        return self.high - self.low


class PriceHistoryCache:
    """
    In-memory cache for price history with automatic expiration.
    
    Features:
    - TTL-based expiration of old data
    - OHLCV aggregation for any time period
    - Efficient range queries
    - Thread-safe operations
    """
    
    DEFAULT_TTL_HOURS = 24
    MAX_SNAPSHOTS_PER_MARKET = 10000
    CLEANUP_INTERVAL_SECONDS = 300
    
    def __init__(
        self,
        ttl_hours: int = DEFAULT_TTL_HOURS,
        max_snapshots: int = MAX_SNAPSHOTS_PER_MARKET,
    ):
        self._ttl = timedelta(hours=ttl_hours)
        self._max_snapshots = max_snapshots
        self._cache: dict[str, list[PriceSnapshot]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._last_cleanup = datetime.now(timezone.utc)
        self._stats = {
            "hits": 0,
            "misses": 0,
            "inserts": 0,
            "evictions": 0,
        }
    
    async def add(
        self,
        market_id: str,
        price: Decimal,
        timestamp: datetime | None = None,
        bid: Decimal = Decimal("0"),
        ask: Decimal = Decimal("0"),
        volume: Decimal = Decimal("0"),
        source: str = "websocket",
    ) -> None:
        """
        Add a price snapshot to the cache.
        
        Args:
            market_id: Market/token identifier
            price: Price value
            timestamp: Price timestamp (defaults to now)
            bid: Best bid price
            ask: Best ask price
            volume: Trade volume
            source: Data source identifier
        """
        ts = timestamp or datetime.now(timezone.utc)
        snapshot = PriceSnapshot(
            price=price,
            timestamp=ts,
            bid=bid,
            ask=ask,
            volume=volume,
            source=source,
        )
        
        async with self._lock:
            cache_list = self._cache[market_id]
            cache_list.append(snapshot)
            self._stats["inserts"] += 1
            
            # Maintain sorted order by timestamp
            cache_list.sort(key=lambda x: x.timestamp)
            
            # Enforce max size
            while len(cache_list) > self._max_snapshots:
                cache_list.pop(0)
                self._stats["evictions"] += 1
        
        # Periodic cleanup
        await self._maybe_cleanup()
    
    async def add_batch(
        self,
        market_id: str,
        snapshots: list[PriceSnapshot],
    ) -> None:
        """Add multiple snapshots at once."""
        async with self._lock:
            cache_list = self._cache[market_id]
            cache_list.extend(snapshots)
            cache_list.sort(key=lambda x: x.timestamp)
            self._stats["inserts"] += len(snapshots)
            
            # Enforce max size
            overflow = len(cache_list) - self._max_snapshots
            if overflow > 0:
                del cache_list[:overflow]
                self._stats["evictions"] += overflow
    
    async def get_latest(self, market_id: str) -> PriceSnapshot | None:
        """Get the most recent price snapshot for a market."""
        async with self._lock:
            cache_list = self._cache.get(market_id, [])
            if cache_list:
                self._stats["hits"] += 1
                return cache_list[-1]
            self._stats["misses"] += 1
            return None
    
    async def get_range(
        self,
        market_id: str,
        start_time: datetime,
        end_time: datetime | None = None,
    ) -> list[PriceSnapshot]:
        """
        Get price snapshots within a time range.
        
        Args:
            market_id: Market identifier
            start_time: Range start (inclusive)
            end_time: Range end (inclusive, defaults to now)
        
        Returns:
            List of PriceSnapshot within range
        """
        end = end_time or datetime.now(timezone.utc)
        
        async with self._lock:
            cache_list = self._cache.get(market_id, [])
            if not cache_list:
                self._stats["misses"] += 1
                return []
            
            self._stats["hits"] += 1
            
            # Binary search could optimize this for large lists
            return [
                s for s in cache_list
                if start_time <= s.timestamp <= end
            ]
    
    async def get_stats(
        self,
        market_id: str,
        period_minutes: int = 60,
    ) -> PriceStats | None:
        """
        Calculate OHLCV statistics for a time period.
        
        Args:
            market_id: Market identifier
            period_minutes: Period length in minutes
        
        Returns:
            PriceStats or None if no data
        """
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=period_minutes)
        
        snapshots = await self.get_range(market_id, start_time, end_time)
        
        if not snapshots:
            return None
        
        prices = [s.price for s in snapshots]
        volumes = [s.volume for s in snapshots]
        
        # Calculate VWAP
        total_volume = sum(volumes)
        if total_volume > 0:
            vwap = sum(p * v for p, v in zip(prices, volumes)) / total_volume
        else:
            vwap = sum(prices) / len(prices)
        
        return PriceStats(
            high=max(prices),
            low=min(prices),
            open=snapshots[0].price,
            close=snapshots[-1].price,
            vwap=vwap,
            count=len(snapshots),
            volume=total_volume,
            period_start=snapshots[0].timestamp,
            period_end=snapshots[-1].timestamp,
        )
    
    async def get_price_at_time(
        self,
        market_id: str,
        target_time: datetime,
    ) -> PriceSnapshot | None:
        """
        Get the price snapshot closest to a specific time.
        
        Args:
            market_id: Market identifier
            target_time: Target timestamp
        
        Returns:
            Closest PriceSnapshot or None
        """
        async with self._lock:
            cache_list = self._cache.get(market_id, [])
            if not cache_list:
                return None
            
            # Find closest snapshot
            closest = min(
                cache_list,
                key=lambda s: abs((s.timestamp - target_time).total_seconds())
            )
            return closest
    
    async def get_baseline(
        self,
        market_id: str,
        lookback_minutes: int = 30,
    ) -> Decimal | None:
        """
        Get baseline price from lookback period.
        Returns the opening price from the lookback window.
        
        Args:
            market_id: Market identifier
            lookback_minutes: How far back to look
        
        Returns:
            Baseline price or None
        """
        start_time = datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)
        snapshots = await self.get_range(market_id, start_time)
        
        if snapshots:
            return snapshots[0].price
        return None
    
    async def clear_market(self, market_id: str) -> int:
        """
        Clear all cached data for a market.
        
        Returns:
            Number of snapshots cleared
        """
        async with self._lock:
            count = len(self._cache.get(market_id, []))
            self._cache.pop(market_id, None)
            return count
    
    async def clear_all(self) -> int:
        """
        Clear all cached data.
        
        Returns:
            Total snapshots cleared
        """
        async with self._lock:
            count = sum(len(v) for v in self._cache.values())
            self._cache.clear()
            return count
    
    async def _maybe_cleanup(self) -> None:
        """Run cleanup if enough time has passed."""
        now = datetime.now(timezone.utc)
        if (now - self._last_cleanup).total_seconds() < self.CLEANUP_INTERVAL_SECONDS:
            return
        
        await self._cleanup_expired()
        self._last_cleanup = now
    
    async def _cleanup_expired(self) -> None:
        """Remove expired snapshots from all markets."""
        cutoff = datetime.now(timezone.utc) - self._ttl
        total_removed = 0
        
        async with self._lock:
            for market_id, cache_list in self._cache.items():
                original_len = len(cache_list)
                self._cache[market_id] = [
                    s for s in cache_list if s.timestamp > cutoff
                ]
                removed = original_len - len(self._cache[market_id])
                total_removed += removed
        
        if total_removed > 0:
            logger.debug(f"Cache cleanup: removed {total_removed} expired snapshots")
    
    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        total_snapshots = sum(len(v) for v in self._cache.values())
        return {
            "markets_cached": len(self._cache),
            "total_snapshots": total_snapshots,
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "inserts": self._stats["inserts"],
            "evictions": self._stats["evictions"],
            "hit_rate": (
                self._stats["hits"] / (self._stats["hits"] + self._stats["misses"])
                if (self._stats["hits"] + self._stats["misses"]) > 0
                else 0
            ),
        }
    
    def __len__(self) -> int:
        """Total number of cached snapshots."""
        return sum(len(v) for v in self._cache.values())
    
    def __contains__(self, market_id: str) -> bool:
        """Check if market has cached data."""
        return market_id in self._cache and len(self._cache[market_id]) > 0


# Global cache instance
price_cache = PriceHistoryCache()
