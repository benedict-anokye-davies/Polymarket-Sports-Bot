"""
FastAPI dependency injection functions.
Provides reusable dependencies for database sessions and authentication.
"""

import uuid
from typing import Annotated, AsyncGenerator, TypeAlias

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.database import async_session_factory
from src.core.security import verify_token
from src.core.exceptions import AuthenticationError
from src.models.user import User
from src.db.crud.user import UserCRUD


security = HTTPBearer(auto_error=True)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yields database session for request scope.
    Automatically closes session after request completes.
    """
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)]
) -> User:
    """
    Validates JWT token and returns the authenticated user.
    
    Args:
        credentials: Bearer token from Authorization header
        db: Database session
    
    Returns:
        Authenticated User instance
    
    Raises:
        HTTPException: If token is invalid or user not found
    """
    try:
        payload = verify_token(credentials.credentials)
        user_id = payload.get("sub")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
        
        user = await UserCRUD.get_by_id(db, uuid.UUID(user_id))
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated"
            )
        
        return user
        
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """
    Ensures user is active. Alias for get_current_user with explicit naming.
    """
    return current_user


async def require_onboarding_complete(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """
    Ensures user has completed onboarding before accessing protected resources.
    
    Raises:
        HTTPException: If onboarding is not complete
    """
    if not current_user.onboarding_completed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please complete onboarding before accessing this resource"
        )
    return current_user


# Type aliases for dependency injection - improves readability and IDE support
DbSession: TypeAlias = Annotated[AsyncSession, Depends(get_db)]
CurrentUser: TypeAlias = Annotated[User, Depends(get_current_user)]
OnboardedUser: TypeAlias = Annotated[User, Depends(require_onboarding_complete)]


__all__ = [
    "get_db",
    "get_current_user",
    "get_current_active_user",
    "require_onboarding_complete",
    "DbSession",
    "CurrentUser",
    "OnboardedUser",
]
