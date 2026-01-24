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
    Sends notifications to Discord via webhooks.
    
    Message types:
    - Trade executed (entry/exit)
    - Bot started/stopped
    - Error alerts
    - Daily summaries
    """
    
    # Discord embed colors
    COLOR_SUCCESS = 0x10B981  # Green
    COLOR_WARNING = 0xF59E0B  # Amber
    COLOR_ERROR = 0xEF4444    # Red
    COLOR_INFO = 0x3B82F6     # Blue
    COLOR_PROFIT = 0x10B981   # Green
    COLOR_LOSS = 0xEF4444     # Red
    
    def __init__(self, webhook_url: str | None = None):
        """
        Initialize Discord notifier.
        
        Args:
            webhook_url: Discord webhook URL for sending messages
        """
        self.webhook_url = webhook_url
        self._client: httpx.AsyncClient | None = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client
    
    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def set_webhook_url(self, url: str) -> None:
        """Update webhook URL."""
        self.webhook_url = url
    
    async def _send_webhook(self, payload: dict[str, Any]) -> bool:
        """
        Send payload to Discord webhook.
        
        Args:
            payload: Discord webhook payload with embeds
        
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.webhook_url:
            logger.debug("Discord webhook URL not configured, skipping notification")
            return False
        
        try:
            client = await self._get_client()
            
            response = await retry_async(
                client.post,
                self.webhook_url,
                json=payload,
                max_retries=2,
                base_delay=1.0,
                circuit_breaker=discord_circuit
            )
            
            if response.status_code in (200, 204):
                return True
            
            logger.warning(f"Discord webhook returned {response.status_code}")
            return False
            
        except Exception as e:
            logger.error(f"Failed to send Discord notification: {e}")
            return False
    
    async def notify_trade_entry(
        self,
        market_name: str,
        side: str,
        price: Decimal,
        size: Decimal,
        reason: str,
        sport: str
    ) -> bool:
        """
        Send notification for trade entry.
        
        Args:
            market_name: Name of the market/game
            side: "YES" or "NO"
            price: Entry price
            size: Position size in USDC
            reason: Entry reason from trading engine
            sport: Sport type (NBA, NFL, etc.)
        """
        embed = {
            "title": "Trade Entry",
            "description": f"Opened position in **{market_name}**",
            "color": self.COLOR_INFO,
            "fields": [
                {"name": "Side", "value": side, "inline": True},
                {"name": "Price", "value": f"${float(price):.4f}", "inline": True},
                {"name": "Size", "value": f"${float(size):.2f}", "inline": True},
                {"name": "Sport", "value": sport.upper(), "inline": True},
                {"name": "Reason", "value": reason, "inline": False},
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "footer": {"text": "Polymarket Sports Bot"}
        }
        
        return await self._send_webhook({"embeds": [embed]})
    
    async def notify_trade_exit(
        self,
        market_name: str,
        side: str,
        entry_price: Decimal,
        exit_price: Decimal,
        pnl: Decimal,
        pnl_pct: float,
        reason: str
    ) -> bool:
        """
        Send notification for trade exit.
        
        Args:
            market_name: Name of the market/game
            side: "YES" or "NO"
            entry_price: Original entry price
            exit_price: Exit price
            pnl: Realized P&L in USDC
            pnl_pct: P&L as percentage
            reason: Exit reason (take_profit, stop_loss, etc.)
        """
        is_profit = pnl >= 0
        color = self.COLOR_PROFIT if is_profit else self.COLOR_LOSS
        pnl_emoji = "+" if is_profit else ""
        
        embed = {
            "title": f"Trade Exit - {'Profit' if is_profit else 'Loss'}",
            "description": f"Closed position in **{market_name}**",
            "color": color,
            "fields": [
                {"name": "Side", "value": side, "inline": True},
                {"name": "Entry", "value": f"${float(entry_price):.4f}", "inline": True},
                {"name": "Exit", "value": f"${float(exit_price):.4f}", "inline": True},
                {"name": "P&L", "value": f"{pnl_emoji}${float(pnl):.2f} ({pnl_emoji}{pnl_pct:.1f}%)", "inline": True},
                {"name": "Reason", "value": reason.replace("_", " ").title(), "inline": True},
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "footer": {"text": "Polymarket Sports Bot"}
        }
        
        return await self._send_webhook({"embeds": [embed]})
    
    async def notify_bot_started(self, user: str, sports: list[str]) -> bool:
        """Send notification when bot starts."""
        embed = {
            "title": "Bot Started",
            "description": f"Trading bot is now active for **{user}**",
            "color": self.COLOR_SUCCESS,
            "fields": [
                {"name": "Active Sports", "value": ", ".join(s.upper() for s in sports), "inline": True},
                {"name": "Status", "value": "Monitoring markets", "inline": True},
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "footer": {"text": "Polymarket Sports Bot"}
        }
        
        return await self._send_webhook({"embeds": [embed]})
    
    async def notify_bot_stopped(self, reason: str = "Manual stop") -> bool:
        """Send notification when bot stops."""
        embed = {
            "title": "Bot Stopped",
            "description": "Trading bot has been stopped",
            "color": self.COLOR_WARNING,
            "fields": [
                {"name": "Reason", "value": reason, "inline": True},
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "footer": {"text": "Polymarket Sports Bot"}
        }
        
        return await self._send_webhook({"embeds": [embed]})
    
    async def notify_error(
        self,
        error_type: str,
        message: str,
        details: str | None = None
    ) -> bool:
        """Send notification for errors."""
        embed = {
            "title": f"Error: {error_type}",
            "description": message,
            "color": self.COLOR_ERROR,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "footer": {"text": "Polymarket Sports Bot"}
        }
        
        if details:
            embed["fields"] = [{"name": "Details", "value": details[:1024], "inline": False}]
        
        return await self._send_webhook({"embeds": [embed]})
    
    async def notify_daily_summary(
        self,
        total_trades: int,
        winning_trades: int,
        total_pnl: Decimal,
        best_trade: dict | None = None,
        worst_trade: dict | None = None
    ) -> bool:
        """Send daily trading summary."""
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        is_profitable = total_pnl >= 0
        pnl_emoji = "+" if is_profitable else ""
        
        fields = [
            {"name": "Total Trades", "value": str(total_trades), "inline": True},
            {"name": "Win Rate", "value": f"{win_rate:.1f}%", "inline": True},
            {"name": "Total P&L", "value": f"{pnl_emoji}${float(total_pnl):.2f}", "inline": True},
        ]
        
        if best_trade:
            fields.append({
                "name": "Best Trade",
                "value": f"{best_trade['market']}: +${best_trade['pnl']:.2f}",
                "inline": False
            })
        
        if worst_trade:
            fields.append({
                "name": "Worst Trade",
                "value": f"{worst_trade['market']}: ${worst_trade['pnl']:.2f}",
                "inline": False
            })
        
        embed = {
            "title": "Daily Trading Summary",
            "color": self.COLOR_PROFIT if is_profitable else self.COLOR_LOSS,
            "fields": fields,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "footer": {"text": "Polymarket Sports Bot"}
        }
        
        return await self._send_webhook({"embeds": [embed]})
    
    async def notify_risk_limit_hit(
        self,
        limit_type: str,
        current_value: Decimal,
        limit_value: Decimal
    ) -> bool:
        """Send notification when risk limit is reached."""
        embed = {
            "title": "Risk Limit Reached",
            "description": f"**{limit_type}** limit has been reached. Trading paused.",
            "color": self.COLOR_WARNING,
            "fields": [
                {"name": "Current", "value": f"${float(current_value):.2f}", "inline": True},
                {"name": "Limit", "value": f"${float(limit_value):.2f}", "inline": True},
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "footer": {"text": "Polymarket Sports Bot"}
        }
        
        return await self._send_webhook({"embeds": [embed]})
