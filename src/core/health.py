"""
Database health monitoring with connection pool metrics.
Provides health check endpoints and pool status tracking.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import text


logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health check status values."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class PoolMetrics:
    """Database connection pool metrics."""
    pool_size: int
    checked_in: int
    checked_out: int
    overflow: int
    invalid: int
    soft_invalidated: int
    
    @property
    def utilization(self) -> float:
        """Pool utilization percentage."""
        total = self.checked_in + self.checked_out
        if total == 0:
            return 0.0
        return (self.checked_out / total) * 100
    
    @property
    def available(self) -> int:
        """Available connections."""
        return self.checked_in
    
    def to_dict(self) -> dict:
        return {
            "pool_size": self.pool_size,
            "checked_in": self.checked_in,
            "checked_out": self.checked_out,
            "overflow": self.overflow,
            "invalid": self.invalid,
            "soft_invalidated": self.soft_invalidated,
            "utilization_percent": round(self.utilization, 2),
            "available": self.available,
        }


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    status: HealthStatus
    response_time_ms: float
    message: str
    details: dict
    timestamp: datetime
    
    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "response_time_ms": round(self.response_time_ms, 2),
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


class DatabaseHealthMonitor:
    """
    Monitors database health and connection pool metrics.
    
    Features:
    - Connection pool status tracking
    - Query latency measurement
    - Health status determination
    - Historical metrics tracking
    """
    
    LATENCY_THRESHOLD_WARNING_MS = 100
    LATENCY_THRESHOLD_UNHEALTHY_MS = 500
    UTILIZATION_THRESHOLD_WARNING = 70
    UTILIZATION_THRESHOLD_UNHEALTHY = 90
    
    def __init__(self, engine: AsyncEngine):
        self._engine = engine
        self._last_check: HealthCheckResult | None = None
        self._check_history: list[HealthCheckResult] = []
        self._max_history = 100
    
    def get_pool_metrics(self) -> PoolMetrics | None:
        """Get current connection pool metrics."""
        pool = self._engine.pool
        if pool is None:
            return None
        
        return PoolMetrics(
            pool_size=pool.size(),
            checked_in=pool.checkedin(),
            checked_out=pool.checkedout(),
            overflow=pool.overflow(),
            invalid=pool.invalidatedcount(),
            soft_invalidated=pool.invalidatedcount() if hasattr(pool, 'invalidatedcount') else 0,
        )
    
    async def check_connectivity(self) -> tuple[bool, float]:
        """
        Test database connectivity with a simple query.
        
        Returns:
            Tuple of (is_connected, latency_ms)
        """
        start = datetime.now(timezone.utc)
        
        try:
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            
            latency = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            return True, latency
            
        except Exception as e:
            latency = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            logger.error(f"Database connectivity check failed: {e}")
            return False, latency
    
    async def run_health_check(self) -> HealthCheckResult:
        """
        Run a comprehensive health check.
        
        Returns:
            HealthCheckResult with status and metrics
        """
        timestamp = datetime.now(timezone.utc)
        pool_metrics = self.get_pool_metrics()
        is_connected, latency = await self.check_connectivity()
        
        # Determine status
        status = HealthStatus.HEALTHY
        messages = []
        
        if not is_connected:
            status = HealthStatus.UNHEALTHY
            messages.append("Database connection failed")
        elif latency > self.LATENCY_THRESHOLD_UNHEALTHY_MS:
            status = HealthStatus.UNHEALTHY
            messages.append(f"High latency: {latency:.2f}ms")
        elif latency > self.LATENCY_THRESHOLD_WARNING_MS:
            status = HealthStatus.DEGRADED
            messages.append(f"Elevated latency: {latency:.2f}ms")
        
        if pool_metrics:
            if pool_metrics.utilization > self.UTILIZATION_THRESHOLD_UNHEALTHY:
                status = HealthStatus.UNHEALTHY
                messages.append(f"Pool exhausted: {pool_metrics.utilization:.1f}%")
            elif pool_metrics.utilization > self.UTILIZATION_THRESHOLD_WARNING:
                if status == HealthStatus.HEALTHY:
                    status = HealthStatus.DEGRADED
                messages.append(f"High pool utilization: {pool_metrics.utilization:.1f}%")
        
        result = HealthCheckResult(
            status=status,
            response_time_ms=latency,
            message="; ".join(messages) if messages else "Database healthy",
            details={
                "connected": is_connected,
                "pool": pool_metrics.to_dict() if pool_metrics else None,
            },
            timestamp=timestamp,
        )
        
        # Track history
        self._last_check = result
        self._check_history.append(result)
        if len(self._check_history) > self._max_history:
            self._check_history.pop(0)
        
        return result
    
    def get_last_check(self) -> HealthCheckResult | None:
        """Get the most recent health check result."""
        return self._last_check
    
    def get_average_latency(self, window_minutes: int = 10) -> float | None:
        """Get average query latency over a time window."""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        recent = [c for c in self._check_history if c.timestamp > cutoff]
        
        if not recent:
            return None
        
        return sum(c.response_time_ms for c in recent) / len(recent)
    
    def get_uptime_percentage(self, window_minutes: int = 60) -> float:
        """Get percentage of healthy checks in time window."""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        recent = [c for c in self._check_history if c.timestamp > cutoff]
        
        if not recent:
            return 100.0
        
        healthy = sum(1 for c in recent if c.status == HealthStatus.HEALTHY)
        return (healthy / len(recent)) * 100


class ServiceHealthAggregator:
    """
    Aggregates health checks from multiple services.
    """
    
    def __init__(self):
        self._services: dict[str, Any] = {}
        self._service_status: dict[str, HealthCheckResult] = {}
    
    def register_service(
        self,
        name: str,
        health_check: callable,
    ) -> None:
        """Register a service health check function."""
        self._services[name] = health_check
    
    async def check_all(self) -> dict[str, HealthCheckResult]:
        """Run health checks for all registered services."""
        results = {}
        
        for name, check_func in self._services.items():
            try:
                result = await check_func()
                results[name] = result
                self._service_status[name] = result
            except Exception as e:
                results[name] = HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    response_time_ms=0,
                    message=f"Health check failed: {e}",
                    details={},
                    timestamp=datetime.now(timezone.utc),
                )
        
        return results
    
    def get_aggregate_status(self) -> HealthStatus:
        """Get overall system health status."""
        if not self._service_status:
            return HealthStatus.HEALTHY
        
        statuses = [r.status for r in self._service_status.values()]
        
        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        if HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY
    
    def get_summary(self) -> dict:
        """Get health summary for all services."""
        return {
            "overall_status": self.get_aggregate_status().value,
            "services": {
                name: result.to_dict()
                for name, result in self._service_status.items()
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# Health check background task
class HealthCheckScheduler:
    """
    Runs periodic health checks in the background.
    """
    
    def __init__(
        self,
        aggregator: ServiceHealthAggregator,
        interval_seconds: int = 30,
    ):
        self._aggregator = aggregator
        self._interval = interval_seconds
        self._task: asyncio.Task | None = None
        self._running = False
    
    async def start(self) -> None:
        """Start the background health check task."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info(f"Health check scheduler started (interval={self._interval}s)")
    
    async def stop(self) -> None:
        """Stop the background task."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Health check scheduler stopped")
    
    async def _run(self) -> None:
        """Main loop for periodic health checks."""
        while self._running:
            try:
                await self._aggregator.check_all()
            except Exception as e:
                logger.error(f"Health check error: {e}")
            
            await asyncio.sleep(self._interval)
