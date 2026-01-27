"""
Prometheus metrics exporter for monitoring and observability.
Exposes application metrics in Prometheus format.
"""

import time
import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Awaitable
from enum import Enum


logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    """Prometheus metric types."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class MetricLabel:
    """A label for a metric."""
    name: str
    value: str


@dataclass
class Metric:
    """Base metric class."""
    name: str
    help_text: str
    metric_type: MetricType
    labels: list[str] = field(default_factory=list)


class Counter:
    """
    A counter metric that only increases.
    Use for counting events, requests, errors, etc.
    """
    
    def __init__(self, name: str, help_text: str, labels: list[str] | None = None):
        self.name = name
        self.help_text = help_text
        self.labels = labels or []
        self._values: dict[tuple, float] = defaultdict(float)
    
    def inc(self, value: float = 1, **label_values) -> None:
        """Increment the counter."""
        key = self._label_key(label_values)
        self._values[key] += value
    
    def _label_key(self, label_values: dict) -> tuple:
        """Create a hashable key from label values."""
        return tuple(label_values.get(l, "") for l in self.labels)
    
    def collect(self) -> list[tuple[dict, float]]:
        """Collect all metric values."""
        results = []
        for key, value in self._values.items():
            labels = dict(zip(self.labels, key))
            results.append((labels, value))
        return results


class Gauge:
    """
    A gauge metric that can go up or down.
    Use for current values like temperature, queue size, etc.
    """
    
    def __init__(self, name: str, help_text: str, labels: list[str] | None = None):
        self.name = name
        self.help_text = help_text
        self.labels = labels or []
        self._values: dict[tuple, float] = defaultdict(float)
    
    def set(self, value: float, **label_values) -> None:
        """Set the gauge value."""
        key = self._label_key(label_values)
        self._values[key] = value
    
    def inc(self, value: float = 1, **label_values) -> None:
        """Increment the gauge."""
        key = self._label_key(label_values)
        self._values[key] += value
    
    def dec(self, value: float = 1, **label_values) -> None:
        """Decrement the gauge."""
        key = self._label_key(label_values)
        self._values[key] -= value
    
    def _label_key(self, label_values: dict) -> tuple:
        return tuple(label_values.get(l, "") for l in self.labels)
    
    def collect(self) -> list[tuple[dict, float]]:
        results = []
        for key, value in self._values.items():
            labels = dict(zip(self.labels, key))
            results.append((labels, value))
        return results


class Histogram:
    """
    A histogram metric for measuring distributions.
    Use for request latencies, response sizes, etc.
    """
    
    DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
    
    def __init__(
        self,
        name: str,
        help_text: str,
        labels: list[str] | None = None,
        buckets: tuple[float, ...] | None = None,
    ):
        self.name = name
        self.help_text = help_text
        self.labels = labels or []
        self.buckets = buckets or self.DEFAULT_BUCKETS
        self._counts: dict[tuple, dict[float, int]] = defaultdict(
            lambda: {b: 0 for b in self.buckets}
        )
        self._sums: dict[tuple, float] = defaultdict(float)
        self._totals: dict[tuple, int] = defaultdict(int)
    
    def observe(self, value: float, **label_values) -> None:
        """Record an observation."""
        key = self._label_key(label_values)
        self._sums[key] += value
        self._totals[key] += 1
        
        for bucket in self.buckets:
            if value <= bucket:
                self._counts[key][bucket] += 1
    
    def _label_key(self, label_values: dict) -> tuple:
        return tuple(label_values.get(l, "") for l in self.labels)
    
    def collect(self) -> list[tuple[dict, dict]]:
        """Collect histogram data."""
        results = []
        for key in set(self._counts.keys()) | set(self._sums.keys()):
            labels = dict(zip(self.labels, key))
            data = {
                "buckets": dict(self._counts[key]),
                "sum": self._sums[key],
                "count": self._totals[key],
            }
            results.append((labels, data))
        return results


class Timer:
    """Context manager for timing code blocks."""
    
    def __init__(self, histogram: Histogram, **label_values):
        self._histogram = histogram
        self._label_values = label_values
        self._start: float | None = None
    
    def __enter__(self):
        self._start = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._start is not None:
            duration = time.perf_counter() - self._start
            self._histogram.observe(duration, **self._label_values)


class MetricsRegistry:
    """
    Central registry for all application metrics.
    Provides Prometheus-format export.
    """
    
    def __init__(self, prefix: str = "polymarket_bot"):
        self._prefix = prefix
        self._counters: dict[str, Counter] = {}
        self._gauges: dict[str, Gauge] = {}
        self._histograms: dict[str, Histogram] = {}
    
    def counter(
        self,
        name: str,
        help_text: str,
        labels: list[str] | None = None,
    ) -> Counter:
        """Create or get a counter metric."""
        full_name = f"{self._prefix}_{name}"
        if full_name not in self._counters:
            self._counters[full_name] = Counter(full_name, help_text, labels)
        return self._counters[full_name]
    
    def gauge(
        self,
        name: str,
        help_text: str,
        labels: list[str] | None = None,
    ) -> Gauge:
        """Create or get a gauge metric."""
        full_name = f"{self._prefix}_{name}"
        if full_name not in self._gauges:
            self._gauges[full_name] = Gauge(full_name, help_text, labels)
        return self._gauges[full_name]
    
    def histogram(
        self,
        name: str,
        help_text: str,
        labels: list[str] | None = None,
        buckets: tuple[float, ...] | None = None,
    ) -> Histogram:
        """Create or get a histogram metric."""
        full_name = f"{self._prefix}_{name}"
        if full_name not in self._histograms:
            self._histograms[full_name] = Histogram(full_name, help_text, labels, buckets)
        return self._histograms[full_name]
    
    def export_prometheus(self) -> str:
        """Export all metrics in Prometheus text format."""
        lines = []
        
        # Export counters
        for name, counter in self._counters.items():
            lines.append(f"# HELP {name} {counter.help_text}")
            lines.append(f"# TYPE {name} counter")
            for labels, value in counter.collect():
                label_str = self._format_labels(labels)
                lines.append(f"{name}{label_str} {value}")
        
        # Export gauges
        for name, gauge in self._gauges.items():
            lines.append(f"# HELP {name} {gauge.help_text}")
            lines.append(f"# TYPE {name} gauge")
            for labels, value in gauge.collect():
                label_str = self._format_labels(labels)
                lines.append(f"{name}{label_str} {value}")
        
        # Export histograms
        for name, histogram in self._histograms.items():
            lines.append(f"# HELP {name} {histogram.help_text}")
            lines.append(f"# TYPE {name} histogram")
            for labels, data in histogram.collect():
                label_str = self._format_labels(labels)
                
                # Bucket values
                cumulative = 0
                for bucket in sorted(histogram.buckets):
                    cumulative += data["buckets"].get(bucket, 0)
                    bucket_labels = {**labels, "le": str(bucket)}
                    bucket_label_str = self._format_labels(bucket_labels)
                    lines.append(f"{name}_bucket{bucket_label_str} {cumulative}")
                
                # +Inf bucket
                inf_labels = {**labels, "le": "+Inf"}
                inf_label_str = self._format_labels(inf_labels)
                lines.append(f"{name}_bucket{inf_label_str} {data['count']}")
                
                # Sum and count
                lines.append(f"{name}_sum{label_str} {data['sum']}")
                lines.append(f"{name}_count{label_str} {data['count']}")
        
        return "\n".join(lines)
    
    def _format_labels(self, labels: dict) -> str:
        """Format labels for Prometheus output."""
        if not labels:
            return ""
        pairs = [f'{k}="{v}"' for k, v in labels.items()]
        return "{" + ",".join(pairs) + "}"
    
    def export_json(self) -> dict:
        """Export all metrics as JSON."""
        result = {
            "counters": {},
            "gauges": {},
            "histograms": {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        for name, counter in self._counters.items():
            result["counters"][name] = counter.collect()
        
        for name, gauge in self._gauges.items():
            result["gauges"][name] = gauge.collect()
        
        for name, histogram in self._histograms.items():
            result["histograms"][name] = histogram.collect()
        
        return result


# Global metrics registry
metrics = MetricsRegistry()

# Pre-defined application metrics
http_requests_total = metrics.counter(
    "http_requests_total",
    "Total HTTP requests",
    labels=["method", "endpoint", "status"],
)

http_request_duration_seconds = metrics.histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    labels=["method", "endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

active_connections = metrics.gauge(
    "active_connections",
    "Number of active connections",
    labels=["type"],
)

orders_total = metrics.counter(
    "orders_total",
    "Total orders placed",
    labels=["side", "status", "sport"],
)

order_value_usd = metrics.histogram(
    "order_value_usd",
    "Order value in USD",
    labels=["side", "sport"],
    buckets=(1, 5, 10, 25, 50, 100, 250, 500, 1000),
)

positions_open = metrics.gauge(
    "positions_open",
    "Number of open positions",
    labels=["sport"],
)

pnl_total_usd = metrics.gauge(
    "pnl_total_usd",
    "Total profit/loss in USD",
    labels=["sport"],
)

api_calls_total = metrics.counter(
    "api_calls_total",
    "Total external API calls",
    labels=["service", "endpoint", "status"],
)

api_call_duration_seconds = metrics.histogram(
    "api_call_duration_seconds",
    "External API call latency",
    labels=["service", "endpoint"],
)

websocket_messages_total = metrics.counter(
    "websocket_messages_total",
    "Total WebSocket messages",
    labels=["direction", "type"],
)

cache_operations_total = metrics.counter(
    "cache_operations_total",
    "Total cache operations",
    labels=["operation", "result"],
)

db_pool_connections = metrics.gauge(
    "db_pool_connections",
    "Database connection pool status",
    labels=["state"],
)

bot_state = metrics.gauge(
    "bot_state",
    "Current bot state (1=running, 0=stopped)",
    labels=["user_id"],
)

alerts_total = metrics.counter(
    "alerts_total",
    "Total alerts generated",
    labels=["severity", "category"],
)

rate_limit_hits = metrics.counter(
    "rate_limit_hits",
    "Rate limit violations",
    labels=["limit_type"],
)


def get_prometheus_metrics() -> str:
    """Get all metrics in Prometheus format."""
    return metrics.export_prometheus()


def get_json_metrics() -> dict:
    """Get all metrics as JSON."""
    return metrics.export_json()
