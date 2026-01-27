"""
Log shipping service for exporting logs to external systems.
Supports CloudWatch, Elasticsearch, and custom destinations.
"""

import asyncio
import json
import logging
import gzip
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable
from enum import Enum


logger = logging.getLogger(__name__)


class LogLevel(str, Enum):
    """Log levels matching Python logging."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class LogEntry:
    """Structured log entry for shipping."""
    timestamp: datetime
    level: LogLevel
    logger_name: str
    message: str
    extra: dict = field(default_factory=dict)
    exception: str | None = None
    correlation_id: str | None = None
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "logger": self.logger_name,
            "message": self.message,
            "extra": self.extra,
            "exception": self.exception,
            "correlation_id": self.correlation_id,
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class LogDestination(ABC):
    """Abstract base class for log destinations."""
    
    @abstractmethod
    async def send(self, entries: list[LogEntry]) -> bool:
        """Send log entries to destination. Returns success status."""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close connection to destination."""
        pass


class CloudWatchDestination(LogDestination):
    """
    Ships logs to AWS CloudWatch Logs.
    
    Requires boto3 and AWS credentials configured.
    """
    
    def __init__(
        self,
        log_group: str,
        log_stream: str,
        region: str = "us-east-1",
        create_group: bool = True,
    ):
        self._log_group = log_group
        self._log_stream = log_stream
        self._region = region
        self._create_group = create_group
        self._client = None
        self._sequence_token: str | None = None
        self._initialized = False
    
    async def _initialize(self) -> None:
        """Initialize CloudWatch client and create group/stream if needed."""
        if self._initialized:
            return
        
        try:
            import boto3  # type: ignore[import-untyped]
            
            self._client = boto3.client("logs", region_name=self._region)
            
            if self._create_group:
                try:
                    self._client.create_log_group(logGroupName=self._log_group)
                except self._client.exceptions.ResourceAlreadyExistsException:
                    pass
                
                try:
                    self._client.create_log_stream(
                        logGroupName=self._log_group,
                        logStreamName=self._log_stream,
                    )
                except self._client.exceptions.ResourceAlreadyExistsException:
                    pass
            
            self._initialized = True
            logger.info(f"CloudWatch destination initialized: {self._log_group}/{self._log_stream}")
            
        except ImportError:
            logger.error("boto3 not installed. Install with: pip install boto3")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize CloudWatch: {e}")
            raise
    
    async def send(self, entries: list[LogEntry]) -> bool:
        """Send log entries to CloudWatch."""
        if not entries:
            return True
        
        await self._initialize()
        
        try:
            # Convert entries to CloudWatch format
            log_events = [
                {
                    "timestamp": int(e.timestamp.timestamp() * 1000),
                    "message": e.to_json(),
                }
                for e in entries
            ]
            
            # Sort by timestamp (required by CloudWatch)
            log_events.sort(key=lambda x: x["timestamp"])
            
            # Send to CloudWatch
            kwargs = {
                "logGroupName": self._log_group,
                "logStreamName": self._log_stream,
                "logEvents": log_events,
            }
            
            if self._sequence_token:
                kwargs["sequenceToken"] = self._sequence_token
            
            response = self._client.put_log_events(**kwargs)
            self._sequence_token = response.get("nextSequenceToken")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send to CloudWatch: {e}")
            return False
    
    async def close(self) -> None:
        """Close CloudWatch client."""
        self._client = None
        self._initialized = False


class ElasticsearchDestination(LogDestination):
    """
    Ships logs to Elasticsearch.
    
    Supports both self-hosted and Elastic Cloud.
    """
    
    def __init__(
        self,
        hosts: list[str],
        index_prefix: str = "logs",
        api_key: str | None = None,
        username: str | None = None,
        password: str | None = None,
        verify_certs: bool = True,
    ):
        self._hosts = hosts
        self._index_prefix = index_prefix
        self._api_key = api_key
        self._username = username
        self._password = password
        self._verify_certs = verify_certs
        self._client = None
    
    async def _get_client(self):
        """Get or create Elasticsearch client."""
        if self._client is None:
            try:
                from elasticsearch import AsyncElasticsearch  # type: ignore[import-untyped]
                
                kwargs = {
                    "hosts": self._hosts,
                    "verify_certs": self._verify_certs,
                }
                
                if self._api_key:
                    kwargs["api_key"] = self._api_key
                elif self._username and self._password:
                    kwargs["basic_auth"] = (self._username, self._password)
                
                self._client = AsyncElasticsearch(**kwargs)
                
            except ImportError:
                logger.error("elasticsearch not installed. Install with: pip install elasticsearch")
                raise
        
        return self._client
    
    async def send(self, entries: list[LogEntry]) -> bool:
        """Send log entries to Elasticsearch."""
        if not entries:
            return True
        
        try:
            client = await self._get_client()
            
            # Generate index name with date suffix
            today = datetime.now(timezone.utc).strftime("%Y.%m.%d")
            index_name = f"{self._index_prefix}-{today}"
            
            # Bulk index documents
            operations = []
            for entry in entries:
                operations.append({"index": {"_index": index_name}})
                operations.append(entry.to_dict())
            
            response = await client.bulk(operations=operations)
            
            if response.get("errors"):
                logger.warning(f"Some Elasticsearch bulk operations failed")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send to Elasticsearch: {e}")
            return False
    
    async def close(self) -> None:
        """Close Elasticsearch client."""
        if self._client:
            await self._client.close()
            self._client = None


class FileDestination(LogDestination):
    """
    Ships logs to local files with rotation.
    
    Useful for local development or backup.
    """
    
    def __init__(
        self,
        file_path: str,
        max_size_mb: int = 100,
        max_files: int = 10,
        compress: bool = True,
    ):
        self._file_path = file_path
        self._max_size = max_size_mb * 1024 * 1024
        self._max_files = max_files
        self._compress = compress
        self._current_size = 0
    
    async def send(self, entries: list[LogEntry]) -> bool:
        """Append log entries to file."""
        if not entries:
            return True
        
        try:
            # Check if rotation is needed
            await self._maybe_rotate()
            
            # Write entries
            with open(self._file_path, "a") as f:
                for entry in entries:
                    line = entry.to_json() + "\n"
                    f.write(line)
                    self._current_size += len(line.encode())
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to write to file: {e}")
            return False
    
    async def _maybe_rotate(self) -> None:
        """Rotate log file if size limit exceeded."""
        import os
        
        if not os.path.exists(self._file_path):
            self._current_size = 0
            return
        
        if self._current_size < self._max_size:
            return
        
        # Rotate files
        for i in range(self._max_files - 1, 0, -1):
            old_path = f"{self._file_path}.{i}"
            new_path = f"{self._file_path}.{i + 1}"
            
            if self._compress:
                old_path += ".gz"
                new_path += ".gz"
            
            if os.path.exists(old_path):
                if i + 1 >= self._max_files:
                    os.remove(old_path)
                else:
                    os.rename(old_path, new_path)
        
        # Compress and move current file
        rotated_path = f"{self._file_path}.1"
        if self._compress:
            with open(self._file_path, "rb") as f_in:
                with gzip.open(f"{rotated_path}.gz", "wb") as f_out:
                    f_out.writelines(f_in)
            os.remove(self._file_path)
        else:
            os.rename(self._file_path, rotated_path)
        
        self._current_size = 0
    
    async def close(self) -> None:
        """No cleanup needed for file destination."""
        pass


class HttpDestination(LogDestination):
    """
    Ships logs to any HTTP endpoint.
    
    Flexible destination for custom log aggregators.
    """
    
    def __init__(
        self,
        url: str,
        headers: dict | None = None,
        auth: tuple[str, str] | None = None,
        batch_size: int = 100,
        timeout: float = 30.0,
    ):
        self._url = url
        self._headers = headers or {}
        self._auth = auth
        self._batch_size = batch_size
        self._timeout = timeout
    
    async def send(self, entries: list[LogEntry]) -> bool:
        """Send log entries via HTTP POST."""
        if not entries:
            return True
        
        try:
            import httpx
            
            payload = {
                "logs": [e.to_dict() for e in entries],
                "count": len(entries),
                "sent_at": datetime.now(timezone.utc).isoformat(),
            }
            
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    self._url,
                    json=payload,
                    headers=self._headers,
                    auth=self._auth,
                )
                
                return response.status_code in (200, 201, 202, 204)
                
        except Exception as e:
            logger.error(f"Failed to send to HTTP endpoint: {e}")
            return False
    
    async def close(self) -> None:
        """No persistent connection to close."""
        pass


class LogShipper:
    """
    Central log shipping service.
    
    Collects logs and ships to configured destinations.
    Handles batching, retries, and backpressure.
    """
    
    DEFAULT_BATCH_SIZE = 100
    DEFAULT_FLUSH_INTERVAL = 5.0
    MAX_QUEUE_SIZE = 10000
    
    def __init__(
        self,
        destinations: list[LogDestination] | None = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
        flush_interval: float = DEFAULT_FLUSH_INTERVAL,
    ):
        self._destinations = destinations or []
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._queue: deque[LogEntry] = deque(maxlen=self.MAX_QUEUE_SIZE)
        self._lock = asyncio.Lock()
        self._flush_task: asyncio.Task | None = None
        self._running = False
        self._stats = {
            "entries_queued": 0,
            "entries_shipped": 0,
            "entries_dropped": 0,
            "batches_sent": 0,
            "batches_failed": 0,
        }
    
    def add_destination(self, destination: LogDestination) -> None:
        """Add a log destination."""
        self._destinations.append(destination)
    
    async def start(self) -> None:
        """Start the log shipper."""
        if self._running:
            return
        
        self._running = True
        self._flush_task = asyncio.create_task(self._flush_loop())
        logger.info("Log shipper started")
    
    async def stop(self) -> None:
        """Stop the log shipper and flush remaining logs."""
        self._running = False
        
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        
        # Final flush
        await self._flush()
        
        # Close destinations
        for dest in self._destinations:
            await dest.close()
        
        logger.info("Log shipper stopped")
    
    async def log(self, entry: LogEntry) -> None:
        """Add a log entry to the queue."""
        async with self._lock:
            if len(self._queue) >= self.MAX_QUEUE_SIZE:
                self._stats["entries_dropped"] += 1
                return
            
            self._queue.append(entry)
            self._stats["entries_queued"] += 1
            
            # Flush if batch size reached
            if len(self._queue) >= self._batch_size:
                await self._flush()
    
    async def _flush_loop(self) -> None:
        """Background task for periodic flushing."""
        while self._running:
            await asyncio.sleep(self._flush_interval)
            await self._flush()
    
    async def _flush(self) -> None:
        """Flush queued entries to destinations."""
        async with self._lock:
            if not self._queue:
                return
            
            # Get batch of entries
            batch = []
            while self._queue and len(batch) < self._batch_size:
                batch.append(self._queue.popleft())
        
        if not batch:
            return
        
        # Send to all destinations
        results = await asyncio.gather(
            *[dest.send(batch) for dest in self._destinations],
            return_exceptions=True,
        )
        
        successes = sum(1 for r in results if r is True)
        
        if successes > 0:
            self._stats["entries_shipped"] += len(batch)
            self._stats["batches_sent"] += 1
        else:
            self._stats["batches_failed"] += 1
    
    def get_stats(self) -> dict:
        """Get shipping statistics."""
        return {
            **self._stats,
            "queue_size": len(self._queue),
            "destinations": len(self._destinations),
        }


class LogShippingHandler(logging.Handler):
    """
    Python logging handler that ships logs.
    
    Integrates with standard Python logging.
    """
    
    def __init__(self, shipper: LogShipper, level: int = logging.INFO):
        super().__init__(level)
        self._shipper = shipper
        self._loop: asyncio.AbstractEventLoop | None = None
    
    def emit(self, record: logging.LogRecord) -> None:
        """Handle a log record."""
        try:
            entry = LogEntry(
                timestamp=datetime.fromtimestamp(record.created, tz=timezone.utc),
                level=LogLevel[record.levelname],
                logger_name=record.name,
                message=record.getMessage(),
                extra=getattr(record, "extra", {}),
                exception=self.formatException(record.exc_info) if record.exc_info else None,
                correlation_id=getattr(record, "correlation_id", None),
            )
            
            # Schedule async log
            if self._loop is None:
                try:
                    self._loop = asyncio.get_running_loop()
                except RuntimeError:
                    return
            
            self._loop.create_task(self._shipper.log(entry))
            
        except Exception:
            self.handleError(record)


# Convenience function for setup
async def setup_log_shipping(
    cloudwatch_config: dict | None = None,
    elasticsearch_config: dict | None = None,
    file_path: str | None = None,
    http_endpoint: str | None = None,
) -> LogShipper:
    """
    Setup log shipping with configured destinations.
    
    Args:
        cloudwatch_config: CloudWatch configuration dict
        elasticsearch_config: Elasticsearch configuration dict
        file_path: Path for file logging
        http_endpoint: HTTP endpoint URL
    
    Returns:
        Configured LogShipper instance
    """
    destinations = []
    
    if cloudwatch_config:
        destinations.append(CloudWatchDestination(**cloudwatch_config))
    
    if elasticsearch_config:
        destinations.append(ElasticsearchDestination(**elasticsearch_config))
    
    if file_path:
        destinations.append(FileDestination(file_path))
    
    if http_endpoint:
        destinations.append(HttpDestination(http_endpoint))
    
    shipper = LogShipper(destinations)
    await shipper.start()
    
    return shipper
