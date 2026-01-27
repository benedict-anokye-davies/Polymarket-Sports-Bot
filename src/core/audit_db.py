"""
Database-backed audit storage using PostgreSQL.
Provides persistent, queryable audit trail with efficient indexing.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any
from sqlalchemy import Column, String, DateTime, Text, Integer, Index, JSON, Enum as SQLEnum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import declarative_base
from sqlalchemy import and_, or_

from src.core.audit import (
    AuditEvent,
    AuditEventType,
    AuditSeverity,
    AuditStorage,
)


logger = logging.getLogger(__name__)

Base = declarative_base()


class AuditEventModel(Base):
    """SQLAlchemy model for audit events."""
    
    __tablename__ = "audit_events"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(255), unique=True, nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)
    user_id = Column(String(255), nullable=True, index=True)
    action = Column(String(255), nullable=False)
    resource_type = Column(String(100), nullable=False)
    resource_id = Column(String(255), nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    correlation_id = Column(String(255), nullable=True, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    
    __table_args__ = (
        Index('ix_audit_events_user_timestamp', 'user_id', 'timestamp'),
        Index('ix_audit_events_type_timestamp', 'event_type', 'timestamp'),
        Index('ix_audit_events_correlation', 'correlation_id'),
    )
    
    def to_audit_event(self) -> AuditEvent:
        """Convert database model to AuditEvent."""
        return AuditEvent(
            event_id=self.event_id,
            event_type=AuditEventType(self.event_type),
            severity=AuditSeverity(self.severity),
            user_id=self.user_id,
            action=self.action,
            resource_type=self.resource_type,
            resource_id=self.resource_id,
            details=self.details or {},
            ip_address=self.ip_address,
            user_agent=self.user_agent,
            correlation_id=self.correlation_id,
            timestamp=self.timestamp,
        )
    
    @classmethod
    def from_audit_event(cls, event: AuditEvent) -> "AuditEventModel":
        """Create database model from AuditEvent."""
        return cls(
            event_id=event.event_id,
            event_type=event.event_type.value,
            severity=event.severity.value,
            user_id=event.user_id,
            action=event.action,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            details=event._serialize_details(),
            ip_address=event.ip_address,
            user_agent=event.user_agent,
            correlation_id=event.correlation_id,
            timestamp=event.timestamp,
        )


class DatabaseAuditStorage(AuditStorage):
    """
    PostgreSQL-backed audit storage.
    
    Provides persistent storage with efficient querying capabilities.
    Supports pagination, filtering, and aggregation queries.
    """
    
    def __init__(self, session_factory):
        """
        Initialize database audit storage.
        
        Args:
            session_factory: Async session factory for database connections
        """
        self._session_factory = session_factory
        self._batch_queue: list[AuditEvent] = []
        self._batch_size = 100
        self._batch_interval = 5.0
        self._lock = asyncio.Lock()
        self._flush_task: asyncio.Task | None = None
    
    async def store(self, event: AuditEvent) -> bool:
        """Store an audit event to the database."""
        try:
            async with self._session_factory() as session:
                model = AuditEventModel.from_audit_event(event)
                session.add(model)
                await session.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to store audit event: {e}")
            return False
    
    async def store_batch(self, events: list[AuditEvent]) -> int:
        """
        Store multiple audit events in a single transaction.
        
        Returns:
            Number of events successfully stored
        """
        if not events:
            return 0
        
        try:
            async with self._session_factory() as session:
                models = [AuditEventModel.from_audit_event(e) for e in events]
                session.add_all(models)
                await session.commit()
                return len(events)
        except Exception as e:
            logger.error(f"Failed to store audit batch: {e}")
            return 0
    
    async def query(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        event_types: list[AuditEventType] | None = None,
        user_id: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        correlation_id: str | None = None,
        severity: AuditSeverity | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEvent]:
        """
        Query audit events with flexible filtering.
        
        Args:
            start_time: Filter events after this time
            end_time: Filter events before this time
            event_types: Filter by event types
            user_id: Filter by user ID
            resource_type: Filter by resource type
            resource_id: Filter by resource ID
            correlation_id: Filter by correlation ID
            severity: Minimum severity level
            limit: Maximum results to return
            offset: Pagination offset
        
        Returns:
            List of matching AuditEvent objects
        """
        try:
            async with self._session_factory() as session:
                query = select(AuditEventModel)
                
                conditions = []
                
                if start_time:
                    conditions.append(AuditEventModel.timestamp >= start_time)
                
                if end_time:
                    conditions.append(AuditEventModel.timestamp <= end_time)
                
                if event_types:
                    type_values = [t.value for t in event_types]
                    conditions.append(AuditEventModel.event_type.in_(type_values))
                
                if user_id:
                    conditions.append(AuditEventModel.user_id == user_id)
                
                if resource_type:
                    conditions.append(AuditEventModel.resource_type == resource_type)
                
                if resource_id:
                    conditions.append(AuditEventModel.resource_id == resource_id)
                
                if correlation_id:
                    conditions.append(AuditEventModel.correlation_id == correlation_id)
                
                if severity:
                    # Filter by severity level or higher
                    severity_order = ["info", "warning", "error", "critical"]
                    min_index = severity_order.index(severity.value)
                    valid_severities = severity_order[min_index:]
                    conditions.append(AuditEventModel.severity.in_(valid_severities))
                
                if conditions:
                    query = query.where(and_(*conditions))
                
                query = query.order_by(AuditEventModel.timestamp.desc())
                query = query.limit(limit).offset(offset)
                
                result = await session.execute(query)
                models = result.scalars().all()
                
                return [m.to_audit_event() for m in models]
                
        except Exception as e:
            logger.error(f"Failed to query audit events: {e}")
            return []
    
    async def count(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        event_types: list[AuditEventType] | None = None,
        user_id: str | None = None,
    ) -> int:
        """Count matching audit events."""
        try:
            from sqlalchemy import func
            
            async with self._session_factory() as session:
                query = select(func.count(AuditEventModel.id))
                
                conditions = []
                
                if start_time:
                    conditions.append(AuditEventModel.timestamp >= start_time)
                if end_time:
                    conditions.append(AuditEventModel.timestamp <= end_time)
                if event_types:
                    type_values = [t.value for t in event_types]
                    conditions.append(AuditEventModel.event_type.in_(type_values))
                if user_id:
                    conditions.append(AuditEventModel.user_id == user_id)
                
                if conditions:
                    query = query.where(and_(*conditions))
                
                result = await session.execute(query)
                return result.scalar() or 0
                
        except Exception as e:
            logger.error(f"Failed to count audit events: {e}")
            return 0
    
    async def get_event_summary(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> dict[str, int]:
        """
        Get summary of events by type in time range.
        
        Returns:
            Dict mapping event type to count
        """
        try:
            from sqlalchemy import func
            
            async with self._session_factory() as session:
                query = (
                    select(
                        AuditEventModel.event_type,
                        func.count(AuditEventModel.id).label("count")
                    )
                    .where(
                        and_(
                            AuditEventModel.timestamp >= start_time,
                            AuditEventModel.timestamp <= end_time,
                        )
                    )
                    .group_by(AuditEventModel.event_type)
                )
                
                result = await session.execute(query)
                rows = result.all()
                
                return {row[0]: row[1] for row in rows}
                
        except Exception as e:
            logger.error(f"Failed to get event summary: {e}")
            return {}
    
    async def cleanup_old_events(self, retention_days: int = 90) -> int:
        """
        Delete audit events older than retention period.
        
        Args:
            retention_days: Number of days to retain events
        
        Returns:
            Number of events deleted
        """
        try:
            from sqlalchemy import delete
            
            cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
            
            async with self._session_factory() as session:
                stmt = delete(AuditEventModel).where(
                    AuditEventModel.timestamp < cutoff
                )
                result = await session.execute(stmt)
                await session.commit()
                
                deleted = result.rowcount
                logger.info(f"Cleaned up {deleted} audit events older than {retention_days} days")
                return deleted
                
        except Exception as e:
            logger.error(f"Failed to cleanup old events: {e}")
            return 0
    
    async def start_batch_flush(self) -> None:
        """Start background task for batch flushing."""
        if self._flush_task is None:
            self._flush_task = asyncio.create_task(self._batch_flush_loop())
    
    async def stop_batch_flush(self) -> None:
        """Stop background batch flush task."""
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
            self._flush_task = None
        
        # Flush remaining events
        await self._flush_batch()
    
    async def queue_event(self, event: AuditEvent) -> None:
        """Add event to batch queue for deferred storage."""
        async with self._lock:
            self._batch_queue.append(event)
            
            if len(self._batch_queue) >= self._batch_size:
                await self._flush_batch()
    
    async def _batch_flush_loop(self) -> None:
        """Background loop for periodic batch flushing."""
        while True:
            await asyncio.sleep(self._batch_interval)
            await self._flush_batch()
    
    async def _flush_batch(self) -> None:
        """Flush queued events to database."""
        async with self._lock:
            if not self._batch_queue:
                return
            
            events = self._batch_queue[:]
            self._batch_queue.clear()
        
        stored = await self.store_batch(events)
        if stored < len(events):
            logger.warning(f"Only stored {stored}/{len(events)} batch events")
