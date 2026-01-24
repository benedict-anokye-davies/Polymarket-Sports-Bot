"""
Custom exception classes for the application.
Provides structured error handling with HTTP status code mapping.
"""

from typing import Any


__all__ = [
    "AppException",
    "AuthenticationError",
    "AuthorizationError",
    "NotFoundError",
    "ValidationError",
    "PolymarketAPIError",
    "ESPNAPIError",
    "InsufficientBalanceError",
    "RateLimitError",
    "WebSocketError",
    "TradingError",
]


class AppException(Exception):
    """
    Base exception class for all application-specific errors.
    Includes status code and optional detail dictionary.
    """
    
    status_code: int = 500
    default_message: str = "An unexpected error occurred"
    
    def __init__(self, message: str | None = None, details: dict[str, Any] | None = None):
        self.message = message or self.default_message
        self.details = details or {}
        super().__init__(self.message)


class AuthenticationError(AppException):
    """
    Raised when authentication fails.
    Invalid credentials, expired tokens, missing auth headers.
    """
    status_code = 401
    default_message = "Authentication failed"


class AuthorizationError(AppException):
    """
    Raised when user lacks permission for an action.
    Valid auth but insufficient privileges.
    """
    status_code = 403
    default_message = "Permission denied"


class NotFoundError(AppException):
    """
    Raised when a requested resource is not found.
    Database records, API endpoints, etc.
    """
    status_code = 404
    default_message = "Resource not found"


class ValidationError(AppException):
    """
    Raised when input validation fails.
    Invalid parameters, malformed data.
    """
    status_code = 400
    default_message = "Validation failed"


class PolymarketAPIError(AppException):
    """
    Raised when Polymarket API returns an error or fails.
    5xx responses, timeouts, connection errors.
    """
    status_code = 502
    default_message = "Polymarket API error"


class ESPNAPIError(AppException):
    """
    Raised when ESPN API returns an error or fails.
    Parse errors, timeouts, connection errors.
    """
    status_code = 502
    default_message = "ESPN API error"


class InsufficientBalanceError(AppException):
    """
    Raised when attempting a trade without sufficient funds.
    """
    status_code = 400
    default_message = "Insufficient balance for operation"


class RateLimitError(AppException):
    """
    Raised when API rate limits are exceeded.
    """
    status_code = 429
    default_message = "Rate limit exceeded"


class WebSocketError(AppException):
    """
    Raised when WebSocket connection fails or drops.
    """
    status_code = 503
    default_message = "WebSocket connection error"


class TradingError(AppException):
    """
    Raised when a trading operation fails.
    General trading errors that don't fit other categories.
    """
    status_code = 400
    default_message = "Trading operation failed"
