"""
Discord notification service for trade alerts and bot status updates.
Sends formatted webhook messages for trades, errors, and system events.
"""

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import httpx

from src.core.retry import retry_async, CircuitBreaker


logger = logging.getLogger(__name__)


# Circuit breaker for Discord API
discord_circuit = CircuitBreaker(
    failure_threshold=3,
    recovery_timeout=120,  # 2 minutes
    expected_exceptions=(httpx.HTTPError, asyncio.TimeoutError)
)


class DiscordNotifier:
    """
    Discord notification service - DISABLED BY USER REQUEST.
    All methods are no-ops.
    """
    
    def __init__(self, webhook_url: str | None = None):
        self.webhook_url = webhook_url
        logger.info("Discord notifications are DISABLED.")
    
    async def close(self) -> None:
        pass
    
    def set_webhook_url(self, url: str) -> None:
        pass
    
    async def _send_webhook(self, payload: dict[str, Any]) -> bool:
        return True
    
    async def notify_trade_entry(self, *args, **kwargs) -> bool:
        return True
    
    async def notify_trade_exit(self, *args, **kwargs) -> bool:
        return True
    
    async def notify_bot_started(self, *args, **kwargs) -> bool:
        return True
    
    async def notify_bot_stopped(self, *args, **kwargs) -> bool:
        return True
    
    async def notify_error(self, *args, **kwargs) -> bool:
        return True
    
    async def notify_daily_summary(self, *args, **kwargs) -> bool:
        return True
    
    async def notify_risk_limit_hit(self, *args, **kwargs) -> bool:
        return True

    async def send_alert(self, *args, **kwargs) -> bool:
        return True
    
    async def send_notification(self, *args, **kwargs) -> bool:
        return True
    
    async def notify_risk_limit_reached(self, *args, **kwargs) -> bool:
        return True

# Global instance
discord_notifier = DiscordNotifier()
