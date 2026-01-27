"""
Graceful shutdown handler for clean application termination.
Ensures all positions are saved and connections closed properly.
"""

import asyncio
import signal
import logging
from datetime import datetime, timezone
from typing import Callable, Awaitable
from contextlib import asynccontextmanager


logger = logging.getLogger(__name__)


class ShutdownHandler:
    """
    Manages graceful shutdown of the application.
    
    Responsibilities:
    - Register cleanup callbacks
    - Handle SIGTERM/SIGINT signals
    - Coordinate ordered shutdown of components
    - Ensure position state is persisted
    - Close connections cleanly
    """
    
    SHUTDOWN_TIMEOUT_SECONDS = 30
    
    def __init__(self):
        self._cleanup_callbacks: list[tuple[int, str, Callable[[], Awaitable[None]]]] = []
        self._is_shutting_down = False
        self._shutdown_event = asyncio.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
    
    def register_cleanup(
        self,
        callback: Callable[[], Awaitable[None]],
        name: str,
        priority: int = 50,
    ) -> None:
        """
        Register a cleanup callback to run during shutdown.
        
        Args:
            callback: Async function to call during shutdown
            name: Descriptive name for logging
            priority: Execution order (lower = earlier, default 50)
        
        Priority Guidelines:
            0-10: Critical state saving (positions, orders)
            11-30: Service disconnection (websockets, APIs)
            31-50: Resource cleanup (caches, pools)
            51-70: Logging finalization
            71-100: Final cleanup
        """
        self._cleanup_callbacks.append((priority, name, callback))
        self._cleanup_callbacks.sort(key=lambda x: x[0])
        logger.debug(f"Registered shutdown callback: {name} (priority={priority})")
    
    def unregister_cleanup(self, name: str) -> bool:
        """Remove a cleanup callback by name."""
        original_len = len(self._cleanup_callbacks)
        self._cleanup_callbacks = [
            (p, n, c) for p, n, c in self._cleanup_callbacks if n != name
        ]
        return len(self._cleanup_callbacks) < original_len
    
    def setup_signal_handlers(self, loop: asyncio.AbstractEventLoop) -> None:
        """
        Install signal handlers for graceful shutdown.
        
        Args:
            loop: The event loop to use for signal handling
        """
        self._loop = loop
        
        try:
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, self._signal_handler, sig)
            logger.info("Signal handlers installed for SIGTERM and SIGINT")
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            signal.signal(signal.SIGTERM, self._sync_signal_handler)
            signal.signal(signal.SIGINT, self._sync_signal_handler)
            logger.info("Windows signal handlers installed")
    
    def _signal_handler(self, sig: signal.Signals) -> None:
        """Handle shutdown signal (Unix)."""
        if self._is_shutting_down:
            logger.warning(f"Received {sig.name} during shutdown, forcing exit")
            raise SystemExit(1)
        
        logger.info(f"Received {sig.name}, initiating graceful shutdown")
        self._is_shutting_down = True
        
        if self._loop:
            self._loop.create_task(self._execute_shutdown())
    
    def _sync_signal_handler(self, signum: int, frame) -> None:
        """Handle shutdown signal (Windows)."""
        sig_name = signal.Signals(signum).name
        
        if self._is_shutting_down:
            logger.warning(f"Received {sig_name} during shutdown, forcing exit")
            raise SystemExit(1)
        
        logger.info(f"Received {sig_name}, initiating graceful shutdown")
        self._is_shutting_down = True
        self._shutdown_event.set()
    
    async def _execute_shutdown(self) -> None:
        """Execute all cleanup callbacks in order."""
        start_time = datetime.now(timezone.utc)
        logger.info(f"Starting graceful shutdown at {start_time.isoformat()}")
        
        successful = 0
        failed = 0
        
        for priority, name, callback in self._cleanup_callbacks:
            try:
                logger.info(f"Running cleanup: {name}")
                await asyncio.wait_for(
                    callback(),
                    timeout=self.SHUTDOWN_TIMEOUT_SECONDS / len(self._cleanup_callbacks)
                )
                successful += 1
                logger.debug(f"Cleanup completed: {name}")
            except asyncio.TimeoutError:
                failed += 1
                logger.error(f"Cleanup timed out: {name}")
            except Exception as e:
                failed += 1
                logger.error(f"Cleanup failed: {name} - {e}")
        
        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        logger.info(
            f"Shutdown complete in {elapsed:.2f}s "
            f"(successful={successful}, failed={failed})"
        )
        
        self._shutdown_event.set()
    
    async def wait_for_shutdown(self) -> None:
        """Wait for the shutdown event to be triggered."""
        await self._shutdown_event.wait()
    
    @property
    def is_shutting_down(self) -> bool:
        """Check if shutdown is in progress."""
        return self._is_shutting_down
    
    def request_shutdown(self) -> None:
        """Programmatically request a shutdown."""
        if not self._is_shutting_down:
            self._is_shutting_down = True
            if self._loop:
                self._loop.create_task(self._execute_shutdown())


@asynccontextmanager
async def graceful_shutdown_context(handler: ShutdownHandler):
    """
    Context manager for graceful shutdown handling.
    
    Usage:
        handler = ShutdownHandler()
        async with graceful_shutdown_context(handler):
            # Application runs here
            await handler.wait_for_shutdown()
    """
    loop = asyncio.get_running_loop()
    handler.setup_signal_handlers(loop)
    
    try:
        yield handler
    finally:
        if not handler.is_shutting_down:
            await handler._execute_shutdown()


class BotShutdownManager:
    """
    High-level shutdown manager for the trading bot.
    Provides pre-configured cleanup callbacks for common components.
    """
    
    def __init__(self, shutdown_handler: ShutdownHandler):
        self._handler = shutdown_handler
    
    def register_position_saver(
        self,
        save_func: Callable[[], Awaitable[None]],
    ) -> None:
        """Register position state saving (highest priority)."""
        self._handler.register_cleanup(save_func, "save_positions", priority=5)
    
    def register_order_canceller(
        self,
        cancel_func: Callable[[], Awaitable[None]],
    ) -> None:
        """Register open order cancellation."""
        self._handler.register_cleanup(cancel_func, "cancel_orders", priority=10)
    
    def register_websocket_closer(
        self,
        close_func: Callable[[], Awaitable[None]],
    ) -> None:
        """Register WebSocket disconnection."""
        self._handler.register_cleanup(close_func, "close_websockets", priority=20)
    
    def register_api_client_closer(
        self,
        close_func: Callable[[], Awaitable[None]],
    ) -> None:
        """Register API client cleanup."""
        self._handler.register_cleanup(close_func, "close_api_clients", priority=25)
    
    def register_cache_flusher(
        self,
        flush_func: Callable[[], Awaitable[None]],
    ) -> None:
        """Register cache flushing."""
        self._handler.register_cleanup(flush_func, "flush_caches", priority=40)
    
    def register_db_pool_closer(
        self,
        close_func: Callable[[], Awaitable[None]],
    ) -> None:
        """Register database connection pool closure."""
        self._handler.register_cleanup(close_func, "close_db_pool", priority=60)
    
    def register_log_flusher(
        self,
        flush_func: Callable[[], Awaitable[None]],
    ) -> None:
        """Register log flushing."""
        self._handler.register_cleanup(flush_func, "flush_logs", priority=80)


# Global shutdown handler
shutdown_handler = ShutdownHandler()
