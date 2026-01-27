"""
Alert escalation system with multi-tier severity levels.
Provides configurable alerting with cooldowns and aggregation.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import IntEnum
from typing import Protocol, Callable, Awaitable
import logging


logger = logging.getLogger(__name__)


class AlertSeverity(IntEnum):
    """Alert severity levels from lowest to highest."""
    DEBUG = 0
    INFO = 10
    WARNING = 20
    ERROR = 30
    CRITICAL = 40


@dataclass
class Alert:
    """Represents a single alert."""
    severity: AlertSeverity
    title: str
    message: str
    category: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = field(default_factory=dict)
    alert_id: str = ""
    
    def __post_init__(self):
        if not self.alert_id:
            self.alert_id = f"{self.category}_{self.timestamp.timestamp()}"
    
    def to_dict(self) -> dict:
        return {
            "alert_id": self.alert_id,
            "severity": self.severity.name,
            "title": self.title,
            "message": self.message,
            "category": self.category,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class AlertChannel(Protocol):
    """Protocol for alert delivery channels."""
    
    async def send(self, alert: Alert) -> bool:
        """Send alert through this channel. Returns success status."""
        ...
    
    @property
    def min_severity(self) -> AlertSeverity:
        """Minimum severity this channel handles."""
        ...


class DiscordAlertChannel:
    """Send alerts to Discord webhook."""
    
    SEVERITY_COLORS = {
        AlertSeverity.DEBUG: 0x808080,    # Gray
        AlertSeverity.INFO: 0x3498DB,     # Blue
        AlertSeverity.WARNING: 0xF39C12,  # Orange
        AlertSeverity.ERROR: 0xE74C3C,    # Red
        AlertSeverity.CRITICAL: 0x8E44AD, # Purple
    }
    
    def __init__(
        self,
        webhook_url: str,
        min_severity: AlertSeverity = AlertSeverity.WARNING,
    ):
        self._webhook_url = webhook_url
        self._min_severity = min_severity
    
    @property
    def min_severity(self) -> AlertSeverity:
        return self._min_severity
    
    async def send(self, alert: Alert) -> bool:
        """Send alert to Discord."""
        if alert.severity < self._min_severity:
            return True
        
        try:
            import httpx
            
            embed = {
                "title": f"[{alert.severity.name}] {alert.title}",
                "description": alert.message,
                "color": self.SEVERITY_COLORS.get(alert.severity, 0x95A5A6),
                "timestamp": alert.timestamp.isoformat(),
                "fields": [
                    {"name": "Category", "value": alert.category, "inline": True},
                ],
            }
            
            if alert.metadata:
                for key, value in list(alert.metadata.items())[:5]:
                    embed["fields"].append({
                        "name": key,
                        "value": str(value)[:100],
                        "inline": True,
                    })
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self._webhook_url,
                    json={"embeds": [embed]},
                    timeout=10.0,
                )
                return response.status_code in (200, 204)
                
        except Exception as e:
            logger.error(f"Discord alert failed: {e}")
            return False


class LogAlertChannel:
    """Send alerts to Python logging."""
    
    SEVERITY_LEVELS = {
        AlertSeverity.DEBUG: logging.DEBUG,
        AlertSeverity.INFO: logging.INFO,
        AlertSeverity.WARNING: logging.WARNING,
        AlertSeverity.ERROR: logging.ERROR,
        AlertSeverity.CRITICAL: logging.CRITICAL,
    }
    
    def __init__(
        self,
        logger_name: str = "alerts",
        min_severity: AlertSeverity = AlertSeverity.INFO,
    ):
        self._logger = logging.getLogger(logger_name)
        self._min_severity = min_severity
    
    @property
    def min_severity(self) -> AlertSeverity:
        return self._min_severity
    
    async def send(self, alert: Alert) -> bool:
        """Log alert to configured logger."""
        level = self.SEVERITY_LEVELS.get(alert.severity, logging.INFO)
        self._logger.log(
            level,
            f"[{alert.category}] {alert.title}: {alert.message}",
            extra={"alert_metadata": alert.metadata},
        )
        return True


class CallbackAlertChannel:
    """Send alerts to a callback function."""
    
    def __init__(
        self,
        callback: Callable[[Alert], Awaitable[None]],
        min_severity: AlertSeverity = AlertSeverity.INFO,
    ):
        self._callback = callback
        self._min_severity = min_severity
    
    @property
    def min_severity(self) -> AlertSeverity:
        return self._min_severity
    
    async def send(self, alert: Alert) -> bool:
        """Invoke callback with alert."""
        try:
            await self._callback(alert)
            return True
        except Exception as e:
            logger.error(f"Callback alert failed: {e}")
            return False


@dataclass
class EscalationRule:
    """Defines how alerts escalate based on conditions."""
    threshold_count: int
    time_window_minutes: int
    escalate_to: AlertSeverity
    categories: list[str] = field(default_factory=list)


class AlertManager:
    """
    Centralized alert management with escalation.
    
    Features:
    - Multiple delivery channels
    - Alert cooldowns to prevent spam
    - Automatic escalation based on frequency
    - Alert aggregation for similar issues
    """
    
    DEFAULT_COOLDOWN_SECONDS = 300
    
    def __init__(self):
        self._channels: list[AlertChannel] = []
        self._escalation_rules: list[EscalationRule] = []
        self._recent_alerts: list[Alert] = []
        self._cooldowns: dict[str, datetime] = {}
        self._alert_counts: dict[str, int] = {}
        self._lock = asyncio.Lock()
    
    def add_channel(self, channel: AlertChannel) -> None:
        """Add an alert delivery channel."""
        self._channels.append(channel)
        logger.info(f"Added alert channel: {type(channel).__name__}")
    
    def remove_channel(self, channel: AlertChannel) -> None:
        """Remove an alert delivery channel."""
        if channel in self._channels:
            self._channels.remove(channel)
    
    def add_escalation_rule(self, rule: EscalationRule) -> None:
        """Add an escalation rule."""
        self._escalation_rules.append(rule)
        logger.debug(
            f"Added escalation rule: {rule.threshold_count} alerts in "
            f"{rule.time_window_minutes}m -> {rule.escalate_to.name}"
        )
    
    async def alert(
        self,
        severity: AlertSeverity,
        title: str,
        message: str,
        category: str,
        metadata: dict | None = None,
        cooldown_key: str | None = None,
        cooldown_seconds: int | None = None,
    ) -> bool:
        """
        Send an alert through all applicable channels.
        
        Args:
            severity: Alert severity level
            title: Short alert title
            message: Detailed message
            category: Alert category for grouping
            metadata: Additional context data
            cooldown_key: Key for cooldown deduplication
            cooldown_seconds: Override default cooldown duration
        
        Returns:
            True if alert was sent (not suppressed by cooldown)
        """
        async with self._lock:
            # Check cooldown
            key = cooldown_key or f"{category}_{title}"
            if not self._check_cooldown(key, cooldown_seconds):
                logger.debug(f"Alert suppressed by cooldown: {title}")
                return False
            
            # Check for escalation
            final_severity = self._check_escalation(severity, category)
            
            # Create alert
            alert = Alert(
                severity=final_severity,
                title=title,
                message=message,
                category=category,
                metadata=metadata or {},
            )
            
            # Track alert
            self._recent_alerts.append(alert)
            self._alert_counts[category] = self._alert_counts.get(category, 0) + 1
            self._update_cooldown(key, cooldown_seconds)
            
            # Prune old alerts
            cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
            self._recent_alerts = [a for a in self._recent_alerts if a.timestamp > cutoff]
        
        # Send to channels (outside lock)
        return await self._send_to_channels(alert)
    
    def _check_cooldown(
        self,
        key: str,
        cooldown_seconds: int | None,
    ) -> bool:
        """Check if alert is allowed based on cooldown."""
        if key not in self._cooldowns:
            return True
        
        cooldown = cooldown_seconds or self.DEFAULT_COOLDOWN_SECONDS
        elapsed = (datetime.now(timezone.utc) - self._cooldowns[key]).total_seconds()
        return elapsed >= cooldown
    
    def _update_cooldown(
        self,
        key: str,
        cooldown_seconds: int | None,
    ) -> None:
        """Update cooldown timestamp."""
        self._cooldowns[key] = datetime.now(timezone.utc)
    
    def _check_escalation(
        self,
        severity: AlertSeverity,
        category: str,
    ) -> AlertSeverity:
        """Check if alert should be escalated based on frequency."""
        now = datetime.now(timezone.utc)
        
        for rule in self._escalation_rules:
            if rule.categories and category not in rule.categories:
                continue
            
            # Count recent alerts in window
            window_start = now - timedelta(minutes=rule.time_window_minutes)
            recent_count = sum(
                1 for a in self._recent_alerts
                if a.timestamp > window_start and (
                    not rule.categories or a.category in rule.categories
                )
            )
            
            if recent_count >= rule.threshold_count:
                if rule.escalate_to > severity:
                    logger.warning(
                        f"Escalating alert from {severity.name} to "
                        f"{rule.escalate_to.name} due to frequency"
                    )
                    return rule.escalate_to
        
        return severity
    
    async def _send_to_channels(self, alert: Alert) -> bool:
        """Send alert to all applicable channels."""
        results = await asyncio.gather(
            *[
                channel.send(alert)
                for channel in self._channels
                if alert.severity >= channel.min_severity
            ],
            return_exceptions=True
        )
        
        successes = sum(1 for r in results if r is True)
        failures = len(results) - successes
        
        if failures > 0:
            logger.warning(f"Alert delivery: {successes} succeeded, {failures} failed")
        
        return successes > 0
    
    def get_recent_alerts(
        self,
        limit: int = 100,
        severity: AlertSeverity | None = None,
        category: str | None = None,
    ) -> list[Alert]:
        """Get recent alerts with optional filtering."""
        alerts = self._recent_alerts
        
        if severity is not None:
            alerts = [a for a in alerts if a.severity >= severity]
        
        if category is not None:
            alerts = [a for a in alerts if a.category == category]
        
        return sorted(alerts, key=lambda a: a.timestamp, reverse=True)[:limit]
    
    def get_stats(self) -> dict:
        """Get alert statistics."""
        return {
            "total_alerts": len(self._recent_alerts),
            "by_category": dict(self._alert_counts),
            "by_severity": {
                sev.name: sum(1 for a in self._recent_alerts if a.severity == sev)
                for sev in AlertSeverity
            },
            "channels_configured": len(self._channels),
            "active_cooldowns": len(self._cooldowns),
        }
    
    # Convenience methods
    async def debug(self, title: str, message: str, category: str = "system", **kwargs):
        return await self.alert(AlertSeverity.DEBUG, title, message, category, **kwargs)
    
    async def info(self, title: str, message: str, category: str = "system", **kwargs):
        return await self.alert(AlertSeverity.INFO, title, message, category, **kwargs)
    
    async def warning(self, title: str, message: str, category: str = "system", **kwargs):
        return await self.alert(AlertSeverity.WARNING, title, message, category, **kwargs)
    
    async def error(self, title: str, message: str, category: str = "system", **kwargs):
        return await self.alert(AlertSeverity.ERROR, title, message, category, **kwargs)
    
    async def critical(self, title: str, message: str, category: str = "system", **kwargs):
        return await self.alert(AlertSeverity.CRITICAL, title, message, category, **kwargs)


# Global alert manager
alert_manager = AlertManager()


def setup_default_alerts(discord_webhook: str | None = None) -> AlertManager:
    """
    Configure alert manager with default channels.
    
    Args:
        discord_webhook: Optional Discord webhook URL
    
    Returns:
        Configured AlertManager instance
    """
    # Always add logging channel
    alert_manager.add_channel(LogAlertChannel(min_severity=AlertSeverity.INFO))
    
    # Add Discord if configured
    if discord_webhook:
        alert_manager.add_channel(
            DiscordAlertChannel(discord_webhook, min_severity=AlertSeverity.WARNING)
        )
    
    # Default escalation rules
    alert_manager.add_escalation_rule(
        EscalationRule(
            threshold_count=5,
            time_window_minutes=10,
            escalate_to=AlertSeverity.WARNING,
        )
    )
    alert_manager.add_escalation_rule(
        EscalationRule(
            threshold_count=10,
            time_window_minutes=5,
            escalate_to=AlertSeverity.ERROR,
        )
    )
    alert_manager.add_escalation_rule(
        EscalationRule(
            threshold_count=20,
            time_window_minutes=5,
            escalate_to=AlertSeverity.CRITICAL,
            categories=["trading", "api", "system"],
        )
    )
    
    return alert_manager
