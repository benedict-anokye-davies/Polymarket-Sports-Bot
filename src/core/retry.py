"""
Retry logic and circuit breaker patterns for resilient API calls.
Implements exponential backoff with jitter and circuit breaker state machine.
"""

import asyncio
import random
import logging
from datetime import datetime, timezone, timedelta
from typing import TypeVar, Callable, Any
from functools import wraps
from dataclasses import dataclass, field
from enum import Enum

import httpx


logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreaker:
    """
    Circuit breaker prevents repeated calls to failing services.
    
    State machine:
    - CLOSED: Normal operation, track failures
    - OPEN: Service failing, reject all calls immediately
    - HALF_OPEN: Allow one test call to check recovery
    
    Args:
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds to wait before testing recovery
        expected_exceptions: Exception types that trigger the breaker
    """
    failure_threshold: int = 5
    recovery_timeout: int = 60
    expected_exceptions: tuple = (httpx.HTTPError, asyncio.TimeoutError)
    
    failure_count: int = field(default=0, init=False)
    last_failure_time: datetime | None = field(default=None, init=False)
    state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    
    def record_failure(self) -> None:
        """Record a failure and potentially open the circuit."""
        self.failure_count += 1
        self.last_failure_time = datetime.now(timezone.utc)
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(
                f"Circuit breaker OPENED after {self.failure_count} failures"
            )
    
    def record_success(self) -> None:
        """Record success and close the circuit."""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
    
    def can_execute(self) -> bool:
        """Check if a call can be made."""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            if self.last_failure_time:
                elapsed = datetime.now(timezone.utc) - self.last_failure_time
                if elapsed > timedelta(seconds=self.recovery_timeout):
                    self.state = CircuitState.HALF_OPEN
                    logger.info("Circuit breaker entering HALF_OPEN state")
                    return True
            return False
        
        # HALF_OPEN allows one test call
        return True
    
    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED


def calculate_backoff(attempt: int, base_delay: float = 1.0, max_delay: float = 30.0) -> float:
    """
    Calculate delay with exponential backoff and jitter.
    
    Args:
        attempt: Current attempt number (0-indexed)
        base_delay: Initial delay in seconds
        max_delay: Maximum delay cap in seconds
    
    Returns:
        Delay in seconds with jitter applied
    """
    delay = min(base_delay * (2 ** attempt), max_delay)
    jitter = random.uniform(0, delay * 0.1)  # 0-10% jitter
    return delay + jitter


async def retry_async(
    func: Callable[..., Any],
    *args,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retryable_exceptions: tuple = (httpx.HTTPError, asyncio.TimeoutError),
    retryable_status_codes: set = {429, 500, 502, 503, 504},
    circuit_breaker: CircuitBreaker | None = None,
    **kwargs
) -> Any:
    """
    Retry an async function with exponential backoff.
    
    Args:
        func: Async function to retry
        *args: Positional arguments for func
        max_retries: Maximum number of retry attempts
        base_delay: Initial backoff delay
        max_delay: Maximum backoff delay
        retryable_exceptions: Exception types to retry on
        retryable_status_codes: HTTP status codes to retry on
        circuit_breaker: Optional circuit breaker instance
        **kwargs: Keyword arguments for func
    
    Returns:
        Result of successful function call
    
    Raises:
        Last exception if all retries exhausted
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        # Check circuit breaker
        if circuit_breaker and not circuit_breaker.can_execute():
            raise RuntimeError("Circuit breaker is OPEN, rejecting call")
        
        try:
            result = await func(*args, **kwargs)
            
            # Check for retryable HTTP status codes
            if isinstance(result, httpx.Response):
                if result.status_code in retryable_status_codes:
                    raise httpx.HTTPStatusError(
                        f"Retryable status {result.status_code}",
                        request=result.request,
                        response=result
                    )
            
            # Success - record and return
            if circuit_breaker:
                circuit_breaker.record_success()
            return result
            
        except retryable_exceptions as e:
            last_exception = e
            
            if circuit_breaker:
                circuit_breaker.record_failure()
            
            if attempt == max_retries:
                logger.error(f"Max retries ({max_retries}) exhausted: {e}")
                raise
            
            delay = calculate_backoff(attempt, base_delay, max_delay)
            
            # Handle rate limit headers
            if isinstance(e, httpx.HTTPStatusError):
                if e.response.status_code == 429:
                    retry_after = e.response.headers.get("Retry-After")
                    if retry_after:
                        delay = float(retry_after)
            
            logger.warning(
                f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                f"Retrying in {delay:.2f}s"
            )
            await asyncio.sleep(delay)
    
    raise last_exception


def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retryable_exceptions: tuple = (httpx.HTTPError, asyncio.TimeoutError),
):
    """
    Decorator for adding retry logic to async functions.
    
    Usage:
        @with_retry(max_retries=5, base_delay=2.0)
        async def fetch_data():
            ...
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_async(
                func, *args,
                max_retries=max_retries,
                base_delay=base_delay,
                max_delay=max_delay,
                retryable_exceptions=retryable_exceptions,
                **kwargs
            )
        return wrapper
    return decorator


# Global circuit breakers for external services
polymarket_circuit = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60,
    expected_exceptions=(httpx.HTTPError, asyncio.TimeoutError)
)

espn_circuit = CircuitBreaker(
    failure_threshold=3,
    recovery_timeout=30,
    expected_exceptions=(httpx.HTTPError, asyncio.TimeoutError)
)
