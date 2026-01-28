"""
Position Reconciler service - syncs local positions with exchange state.
Recovers position state on bot restart and detects drift.
"""

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


class PositionReconciler:
    """
    Synchronizes local position state with exchange positions.
    
    Responsibilities:
    - Fetch current positions from exchanges on startup
    - Compare with local database state
    - Reconcile differences and mark positions appropriately
    - Handle orphaned positions (exchange-only or DB-only)
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
    
    async def reconcile(self) -> dict:
        """
        Full reconciliation between local DB and exchanges.
        
        Returns:
            dict with reconciliation summary
        """
        results = {
            "polymarket": None,
            "kalshi": None,
            "total_synced": 0,
            "total_recovered": 0,
            "total_closed": 0,
            "errors": [],
        }
        
        if self.polymarket_client:
            try:
                pm_result = await self._reconcile_polymarket()
                results["polymarket"] = pm_result
                results["total_synced"] += pm_result.get("synced", 0)
                results["total_recovered"] += pm_result.get("recovered", 0)
                results["total_closed"] += pm_result.get("closed", 0)
            except Exception as e:
                logger.error(f"Polymarket reconciliation failed: {e}")
                results["errors"].append(f"Polymarket: {str(e)}")
        
        if self.kalshi_client:
            try:
                kalshi_result = await self._reconcile_kalshi()
                results["kalshi"] = kalshi_result
                results["total_synced"] += kalshi_result.get("synced", 0)
                results["total_recovered"] += kalshi_result.get("recovered", 0)
                results["total_closed"] += kalshi_result.get("closed", 0)
            except Exception as e:
                logger.error(f"Kalshi reconciliation failed: {e}")
                results["errors"].append(f"Kalshi: {str(e)}")
        
        results["reconciled_at"] = datetime.now(timezone.utc).isoformat()
        
        return results
    
    async def _reconcile_polymarket(self) -> dict:
        """Reconcile positions with Polymarket exchange."""
        if not self.polymarket_client:
            return {"error": "Client not configured"}
        
        exchange_positions = await self._fetch_polymarket_positions()
        local_positions = await self._get_local_positions(platform="polymarket")
        
        exchange_map = {p["token_id"]: p for p in exchange_positions}
        local_map = {p.token_id: p for p in local_positions}
        
        synced = 0
        recovered = 0
        closed = 0
        
        for token_id, exchange_pos in exchange_map.items():
            if token_id in local_map:
                local_pos = local_map[token_id]
                if local_pos.status == "open":
                    await self._update_position_sync(
                        position_id=local_pos.id,
                        sync_status="synced",
                    )
                    synced += 1
                else:
                    await self._update_position_sync(
                        position_id=local_pos.id,
                        sync_status="recovered",
                        recovery_source="polymarket_api",
                    )
                    recovered += 1
            else:
                await self._create_recovered_position(
                    platform="polymarket",
                    exchange_position=exchange_pos,
                )
                recovered += 1
        
        for token_id, local_pos in local_map.items():
            if token_id not in exchange_map and local_pos.status == "open":
                await self._mark_position_closed(
                    position_id=local_pos.id,
                    close_reason="not_found_on_exchange",
                )
                closed += 1
        
        return {
            "synced": synced,
            "recovered": recovered,
            "closed": closed,
            "exchange_positions": len(exchange_positions),
            "local_positions": len(local_positions),
        }
    
    async def _reconcile_kalshi(self) -> dict:
        """Reconcile positions with Kalshi exchange."""
        if not self.kalshi_client:
            return {"error": "Client not configured"}
        
        exchange_positions = await self._fetch_kalshi_positions()
        local_positions = await self._get_local_positions(platform="kalshi")
        
        exchange_map = {p["ticker"]: p for p in exchange_positions}
        local_map = {p.token_id: p for p in local_positions}
        
        synced = 0
        recovered = 0
        closed = 0
        
        for ticker, exchange_pos in exchange_map.items():
            if ticker in local_map:
                local_pos = local_map[ticker]
                if local_pos.status == "open":
                    await self._update_position_sync(
                        position_id=local_pos.id,
                        sync_status="synced",
                    )
                    synced += 1
            else:
                await self._create_recovered_position(
                    platform="kalshi",
                    exchange_position=exchange_pos,
                )
                recovered += 1
        
        for ticker, local_pos in local_map.items():
            if ticker not in exchange_map and local_pos.status == "open":
                await self._mark_position_closed(
                    position_id=local_pos.id,
                    close_reason="not_found_on_exchange",
                )
                closed += 1
        
        return {
            "synced": synced,
            "recovered": recovered,
            "closed": closed,
        }
    
    async def _fetch_polymarket_positions(self) -> list[dict]:
        """Fetch current positions from Polymarket."""
        if not self.polymarket_client:
            return []
        try:
            positions = await self.polymarket_client.get_positions()
            return [
                {
                    "token_id": p.get("asset_id") or p.get("token_id"),
                    "size": int(p.get("size", 0)),
                    "avg_price": Decimal(str(p.get("avg_price", 0))),
                    "side": p.get("side", "BUY"),
                }
                for p in positions
                if int(p.get("size", 0)) > 0
            ]
        except Exception as e:
            logger.error(f"Failed to fetch Polymarket positions: {e}")
            return []
    
    async def _fetch_kalshi_positions(self) -> list[dict]:
        """Fetch current positions from Kalshi."""
        if not self.kalshi_client:
            return []
        try:
            positions = await self.kalshi_client.get_positions()
            return [
                {
                    "ticker": p.get("market_ticker") or p.get("ticker"),
                    "position": p.get("position", 0),
                    "cost_basis": Decimal(str(p.get("cost_basis", 0))) / Decimal("100"),
                }
                for p in positions
                if p.get("position", 0) != 0
            ]
        except Exception as e:
            logger.error(f"Failed to fetch Kalshi positions: {e}")
            return []
    
    async def _get_local_positions(self, platform: str):
        """Get local DB positions for platform."""
        from src.models import Position
        
        stmt = (
            select(Position)
            .where(Position.user_id == self.user_id)
            .where(Position.status == "open")
        )
        
        if platform == "kalshi":
            stmt = stmt.where(Position.token_id.like("KALSHI-%"))
        else:
            stmt = stmt.where(~Position.token_id.like("KALSHI-%"))
        
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def _update_position_sync(
        self,
        position_id: UUID,
        sync_status: str,
        recovery_source: str | None = None,
    ) -> None:
        """Update position sync status."""
        from src.models import Position
        from typing import Any
        
        values: dict[str, Any] = {
            "sync_status": sync_status,
        }
        
        if recovery_source:
            values["recovery_source"] = recovery_source
            values["recovered_at"] = datetime.now(timezone.utc)
        
        stmt = (
            update(Position)
            .where(Position.id == position_id)
            .values(**values)
        )
        await self.db.execute(stmt)
        await self.db.commit()
    
    async def _create_recovered_position(
        self,
        platform: str,
        exchange_position: dict,
    ) -> None:
        """Create a position record for exchange-only position."""
        from src.models import Position
        
        if platform == "polymarket":
            token_id = exchange_position["token_id"]
            entry_price = exchange_position.get("avg_price", Decimal("0"))
            size = exchange_position.get("size", 0)
        else:
            token_id = f"KALSHI-{exchange_position['ticker']}"
            entry_price = exchange_position.get("cost_basis", Decimal("0"))
            size = abs(exchange_position.get("position", 0))
        
        position = Position(
            user_id=self.user_id,
            condition_id=token_id,
            token_id=token_id,
            entry_price=entry_price,
            actual_entry_price=entry_price,
            contracts=size,
            status="open",
            sync_status="recovered",
            recovery_source=f"{platform}_api",
            recovered_at=datetime.now(timezone.utc),
            fill_status="filled",
        )
        
        self.db.add(position)
        await self.db.commit()
        
        logger.info(f"Recovered position from {platform}: {token_id}")
    
    async def _mark_position_closed(
        self,
        position_id: UUID,
        close_reason: str,
    ) -> None:
        """Mark position as closed when not found on exchange."""
        from src.models import Position
        
        stmt = (
            update(Position)
            .where(Position.id == position_id)
            .values(
                status="closed",
                sync_status="closed_reconciled",
                closed_at=datetime.now(timezone.utc),
            )
        )
        await self.db.execute(stmt)
        await self.db.commit()
        
        logger.info(f"Closed orphaned position {position_id}: {close_reason}")
    
    async def get_sync_status(self) -> dict:
        """
        Get current sync status summary.
        
        Returns:
            dict with position sync breakdown
        """
        from src.models import Position
        from sqlalchemy import func
        
        stmt = (
            select(Position.sync_status, func.count(Position.id))
            .where(Position.user_id == self.user_id)
            .group_by(Position.sync_status)
        )
        result = await self.db.execute(stmt)
        
        # Convert rows to dict properly
        status_counts: dict[str, int] = {}
        for row in result.fetchall():
            status_counts[row[0]] = row[1]
        
        return {
            "synced": status_counts.get("synced", 0),
            "recovered": status_counts.get("recovered", 0),
            "pending": status_counts.get("pending", 0),
            "drift_detected": status_counts.get("drift", 0),
            "last_reconcile": datetime.now(timezone.utc).isoformat(),
        }
