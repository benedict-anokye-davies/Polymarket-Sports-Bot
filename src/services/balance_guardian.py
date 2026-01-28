"""
Balance Guardian service - monitors account balance and triggers kill switch.
Implements automatic trading halt when balance drops below configured threshold.
"""

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from src.services.polymarket_client import PolymarketClient
    from src.services.kalshi_client import KalshiClient

logger = logging.getLogger(__name__)

# Max retries for balance fetch operations
MAX_BALANCE_FETCH_RETRIES = 3
BALANCE_FETCH_RETRY_DELAY = 2.0


class BalanceGuardian:
    """
    Monitors account balance and enforces risk limits.
    
    Responsibilities:
    - Periodic balance checks against configured threshold
    - Kill switch activation when balance too low
    - Losing streak tracking and position size reduction
    - Alert notifications via configured channels
    """
    
    def __init__(
        self,
        db: AsyncSession,
        user_id: UUID,
        polymarket_client: "PolymarketClient | None" = None,
        kalshi_client: "KalshiClient | None" = None,
    ):
        self.db = db
        self.user_id = user_id
        self.polymarket_client = polymarket_client
        self.kalshi_client = kalshi_client
        self._is_monitoring = False
    
    async def check_balance(self) -> dict:
        """
        Check current balance against configured threshold.
        
        Returns:
            dict with balance status, current_balance, threshold, is_safe
        """
        from src.models import GlobalSettings
        
        settings = await self._get_settings()
        if not settings:
            return {"error": "Settings not found", "is_safe": True}
        
        threshold = Decimal(str(settings.min_balance_threshold_usdc or 50))
        
        current_balance = Decimal("0")
        balance_breakdown = {}
        
        if self.polymarket_client:
            try:
                pm_balance = await self._get_polymarket_balance()
                balance_breakdown["polymarket"] = float(pm_balance)
                current_balance += pm_balance
            except Exception as e:
                logger.warning(f"Failed to fetch Polymarket balance: {e}")
        
        if self.kalshi_client:
            try:
                kalshi_balance = await self._get_kalshi_balance()
                balance_breakdown["kalshi"] = float(kalshi_balance)
                current_balance += kalshi_balance
            except Exception as e:
                logger.warning(f"Failed to fetch Kalshi balance: {e}")
        
        is_safe = current_balance >= threshold
        margin = current_balance - threshold
        
        result = {
            "current_balance": float(current_balance),
            "threshold": float(threshold),
            "is_safe": is_safe,
            "margin": float(margin),
            "breakdown": balance_breakdown,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
        
        if not is_safe:
            logger.warning(
                f"Balance below threshold for user {self.user_id}: "
                f"${current_balance} < ${threshold}"
            )
            await self._trigger_kill_switch(
                reason=f"Balance ${current_balance} below threshold ${threshold}"
            )
        
        return result
    
    async def _get_polymarket_balance(self) -> Decimal:
        """
        Fetch current Polymarket USDC balance with retry logic.
        
        Uses exponential backoff on failures to handle transient network issues
        without triggering kill switch unnecessarily.
        """
        if not self.polymarket_client:
            return Decimal("0")
        
        last_error: Exception | None = None
        for attempt in range(MAX_BALANCE_FETCH_RETRIES):
            try:
                balance_data = await self.polymarket_client.get_balance()
                if isinstance(balance_data, dict):
                    return Decimal(str(balance_data.get("balance", 0)))
                return Decimal(str(balance_data or 0))
            except Exception as e:
                last_error = e
                if attempt < MAX_BALANCE_FETCH_RETRIES - 1:
                    delay = BALANCE_FETCH_RETRY_DELAY * (2 ** attempt)
                    logger.warning(
                        f"Polymarket balance fetch attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
        
        logger.error(
            f"Polymarket balance fetch failed after {MAX_BALANCE_FETCH_RETRIES} attempts: {last_error}"
        )
        if last_error:
            raise last_error
        raise RuntimeError("Balance fetch failed with no recorded error")
    
    async def _get_kalshi_balance(self) -> Decimal:
        """
        Fetch current Kalshi USD balance with retry logic.
        
        Uses exponential backoff on failures to handle transient network issues.
        Note: Kalshi returns balance in cents, divided by 100 for dollars.
        """
        if not self.kalshi_client:
            return Decimal("0")
        
        last_error: Exception | None = None
        for attempt in range(MAX_BALANCE_FETCH_RETRIES):
            try:
                balance_data = await self.kalshi_client.get_balance()
                if isinstance(balance_data, dict):
                    return Decimal(str(balance_data.get("balance", 0))) / Decimal("100")
                return Decimal(str(balance_data or 0))
            except Exception as e:
                last_error = e
                if attempt < MAX_BALANCE_FETCH_RETRIES - 1:
                    delay = BALANCE_FETCH_RETRY_DELAY * (2 ** attempt)
                    logger.warning(
                        f"Kalshi balance fetch attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
        
        logger.error(
            f"Kalshi balance fetch failed after {MAX_BALANCE_FETCH_RETRIES} attempts: {last_error}"
        )
        if last_error:
            raise last_error
        raise RuntimeError("Balance fetch failed with no recorded error")
    
    async def _trigger_kill_switch(self, reason: str) -> None:
        """
        Activate kill switch - halt all trading activity.
        
        Args:
            reason: Description of why kill switch was triggered
        """
        from src.models import GlobalSettings
        
        logger.critical(f"KILL SWITCH TRIGGERED: {reason}")
        
        stmt = (
            update(GlobalSettings)
            .where(GlobalSettings.user_id == self.user_id)
            .values(
                bot_enabled=False,
                kill_switch_triggered_at=datetime.now(timezone.utc),
                kill_switch_reason=reason,
            )
        )
        await self.db.execute(stmt)
        await self.db.commit()
        
        await self._send_alert(
            level="critical",
            title="Kill Switch Activated",
            message=reason,
        )
    
    async def reset_kill_switch(self) -> dict:
        """
        Reset kill switch after manual review.
        
        Returns:
            dict with reset status
        """
        from src.models import GlobalSettings
        
        balance_check = await self.check_balance()
        if not balance_check.get("is_safe", False):
            return {
                "success": False,
                "error": "Cannot reset - balance still below threshold",
                "current_balance": balance_check.get("current_balance"),
            }
        
        stmt = (
            update(GlobalSettings)
            .where(GlobalSettings.user_id == self.user_id)
            .values(
                kill_switch_triggered_at=None,
                kill_switch_reason=None,
            )
        )
        await self.db.execute(stmt)
        await self.db.commit()
        
        logger.info(f"Kill switch reset for user {self.user_id}")
        
        return {"success": True, "message": "Kill switch reset successfully"}
    
    async def record_trade_outcome(self, is_win: bool) -> dict:
        """
        Record trade outcome for losing streak tracking.
        
        Args:
            is_win: True if trade was profitable
        
        Returns:
            dict with streak info and any size adjustment
        """
        from src.models import GlobalSettings
        
        settings = await self._get_settings()
        if not settings:
            return {"error": "Settings not found"}
        
        current_streak = settings.current_losing_streak or 0
        max_streak = settings.max_losing_streak or 0
        
        if is_win:
            new_streak = 0
        else:
            new_streak = current_streak + 1
            max_streak = max(max_streak, new_streak)
        
        stmt = (
            update(GlobalSettings)
            .where(GlobalSettings.user_id == self.user_id)
            .values(
                current_losing_streak=new_streak,
                max_losing_streak=max_streak,
            )
        )
        await self.db.execute(stmt)
        await self.db.commit()
        
        size_adjustment = await self.calculate_streak_adjustment()
        
        return {
            "is_win": is_win,
            "current_losing_streak": new_streak,
            "max_losing_streak": max_streak,
            "size_adjustment": size_adjustment,
        }
    
    async def calculate_streak_adjustment(self) -> float:
        """
        Calculate position size reduction based on losing streak.
        
        Returns:
            Multiplier between 0.0 and 1.0 for position sizing
        """
        settings = await self._get_settings()
        if not settings:
            return 1.0
        
        if not settings.streak_reduction_enabled:
            return 1.0
        
        streak = settings.current_losing_streak or 0
        reduction_pct = settings.streak_reduction_pct_per_loss or Decimal("0.1")
        
        total_reduction = float(reduction_pct) * streak
        multiplier = max(0.1, 1.0 - total_reduction)
        
        return multiplier
    
    async def _get_settings(self):
        """Fetch GlobalSettings for current user."""
        from src.models import GlobalSettings
        
        stmt = select(GlobalSettings).where(GlobalSettings.user_id == self.user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def _send_alert(self, level: str, title: str, message: str) -> None:
        """
        Send alert notification via configured channels.
        
        Args:
            level: Alert severity (info, warning, critical)
            title: Alert title
            message: Alert message body
        """
        settings = await self._get_settings()
        if not settings:
            return
        
        if settings.discord_webhook_url:
            from src.services.discord_notifier import DiscordNotifier
            
            try:
                notifier = DiscordNotifier(settings.discord_webhook_url)
                await notifier.send_alert(
                    title=f"[{level.upper()}] {title}",
                    message=message,
                )
            except Exception as e:
                logger.error(f"Discord notification failed: {e}")
    
    async def get_status(self) -> dict:
        """
        Get current balance guardian status.
        
        Returns:
            dict with balance, threshold, kill switch status, streak info
        """
        settings = await self._get_settings()
        balance_check = await self.check_balance()
        
        return {
            "balance": balance_check,
            "kill_switch": {
                "triggered": settings.kill_switch_triggered_at is not None if settings else False,
                "triggered_at": settings.kill_switch_triggered_at.isoformat() if settings and settings.kill_switch_triggered_at else None,
                "reason": settings.kill_switch_reason if settings else None,
            },
            "streak": {
                "current_losing_streak": settings.current_losing_streak if settings else 0,
                "max_losing_streak": settings.max_losing_streak if settings else 0,
                "reduction_enabled": settings.streak_reduction_enabled if settings else False,
                "size_multiplier": await self.calculate_streak_adjustment(),
            },
        }
