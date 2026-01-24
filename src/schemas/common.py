"""
Common schemas used across multiple endpoints.
"""

from typing import Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class MessageResponse(BaseModel):
    """
    Simple message response for operations without data payload.
    """
    message: str
    success: bool = True


class ErrorResponse(BaseModel):
    """
    Standard error response format.
    """
    error: str
    message: str
    details: dict | None = None


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Generic paginated response wrapper.
    """
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int
