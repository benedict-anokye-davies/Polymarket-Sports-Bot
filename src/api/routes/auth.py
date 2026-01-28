"""
Authentication routes for user registration and login.
Includes refresh token support (REQ-SEC-001).
Rate limited to prevent brute-force attacks.
"""

from datetime import timedelta
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, HTTPException, status, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm

from src.api.deps import DbSession, get_current_user
from src.config import get_settings
from src.core.security import create_access_token, create_refresh_token_jwt, verify_refresh_token
from src.core.exceptions import AuthenticationError
from src.core.rate_limiter import check_auth_rate_limit

settings = get_settings()
from src.db.crud.user import UserCRUD
from src.db.crud.global_settings import GlobalSettingsCRUD
from src.db.crud.sport_config import SportConfigCRUD
from src.db.crud.refresh_token import RefreshTokenCRUD
from src.schemas.auth import (
    UserCreate,
    UserLogin,
    UserResponse,
    TokenResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    LogoutRequest,
)
from src.core.exceptions import ValidationError

if TYPE_CHECKING:
    from src.models.user import User


router = APIRouter(prefix="/auth", tags=["Authentication"])


def _get_client_info(request: Request) -> tuple[str | None, str | None]:
    """Extract client device info and IP address from request."""
    device_info = request.headers.get("User-Agent", "")[:255] if request.headers.get("User-Agent") else None
    ip_address = request.client.host if request.client else None
    return device_info, ip_address


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: DbSession,
    request: Request,
    _: None = Depends(check_auth_rate_limit),
) -> TokenResponse:
    """
    Registers a new user account.
    Creates default global settings and sport configurations.
    Issues both access token and refresh token.

    Args:
        user_data: Registration details (username, email, password)
        db: Database session
        request: HTTP request for client info

    Returns:
        JWT access token, refresh token, and user data
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        user = await UserCRUD.create(
            db,
            username=user_data.username,
            email=user_data.email,
            password=user_data.password
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Registration failed during user creation: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {type(e).__name__}"
        )

    try:
        await GlobalSettingsCRUD.create(db, user.id)
        await SportConfigCRUD.create_defaults_for_user(db, user.id)
    except Exception as e:
        logger.error(f"Registration failed during settings creation: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Account created but settings failed: {type(e).__name__}"
        )

    # Create access token
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes)
    )

    # Create refresh token and store in database
    try:
        device_info, ip_address = _get_client_info(request)
        _, refresh_token = await RefreshTokenCRUD.create(
            db,
            user_id=user.id,
            device_info=device_info,
            ip_address=ip_address,
        )
    except Exception as e:
        logger.error(f"Registration failed during token creation: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Account created but token failed: {type(e).__name__}"
        )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
        refresh_expires_in=settings.refresh_token_expire_days * 24 * 60 * 60,
        user=UserResponse.model_validate(user)
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    db: DbSession,
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    _: None = Depends(check_auth_rate_limit),
) -> TokenResponse:
    """
    Authenticates user and returns access token and refresh token.
    Accepts OAuth2 form data (username field contains email).

    Args:
        db: Database session
        request: HTTP request for client info
        form_data: OAuth2 form with username (email) and password

    Returns:
        JWT access token, refresh token, and user data
    """
    user = await UserCRUD.authenticate(db, form_data.username, form_data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated"
        )

    # Create access token
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes)
    )

    # Create refresh token and store in database
    device_info, ip_address = _get_client_info(request)
    _, refresh_token = await RefreshTokenCRUD.create(
        db,
        user_id=user.id,
        device_info=device_info,
        ip_address=ip_address,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
        refresh_expires_in=settings.refresh_token_expire_days * 24 * 60 * 60,
        user=UserResponse.model_validate(user)
    )


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: DbSession,
    request: Request,
    _: None = Depends(check_auth_rate_limit),
) -> RefreshTokenResponse:
    """
    Refresh an access token using a refresh token.
    Implements token rotation: the old refresh token is revoked and a new one is issued.

    Args:
        refresh_data: Request containing the refresh token
        db: Database session
        request: HTTP request for client info

    Returns:
        New access token and rotated refresh token
    """
    # Rotate the refresh token (validates old, creates new)
    device_info, ip_address = _get_client_info(request)
    result = await RefreshTokenCRUD.rotate(
        db,
        old_plain_token=refresh_data.refresh_token,
        device_info=device_info,
        ip_address=ip_address,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

    new_token_model, new_refresh_token = result

    # Create new access token
    access_token = create_access_token(
        data={"sub": str(new_token_model.user_id)},
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes)
    )

    return RefreshTokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
        refresh_expires_in=settings.refresh_token_expire_days * 24 * 60 * 60,
    )


@router.post("/logout")
async def logout(
    logout_data: LogoutRequest,
    db: DbSession,
    current_user: "User" = Depends(get_current_user),
) -> dict:
    """
    Logout the user by revoking refresh tokens.
    Can optionally logout from all devices.

    Args:
        logout_data: Optional refresh token and logout_all flag
        db: Database session
        current_user: The authenticated user

    Returns:
        Success message
    """
    if logout_data.logout_all_devices:
        # Revoke all refresh tokens for this user
        count = await RefreshTokenCRUD.revoke_all_for_user(
            db,
            user_id=current_user.id,
            reason="logout_all"
        )
        return {"message": f"Logged out from all devices ({count} sessions)"}
    elif logout_data.refresh_token:
        # Revoke only the specific refresh token
        success = await RefreshTokenCRUD.revoke_by_token(
            db,
            plain_token=logout_data.refresh_token,
            reason="logout"
        )
        if not success:
            # Token may already be revoked or expired, but that's fine for logout
            pass
        return {"message": "Logged out successfully"}
    else:
        return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: "User" = Depends(get_current_user)
) -> UserResponse:
    """
    Returns the current authenticated user's information.
    """
    return UserResponse.model_validate(current_user)


@router.get("/sessions")
async def get_active_sessions(
    db: DbSession,
    current_user: "User" = Depends(get_current_user),
) -> list[dict]:
    """
    Get all active sessions (refresh tokens) for the current user.

    Returns:
        List of active sessions with device info
    """
    tokens = await RefreshTokenCRUD.get_active_for_user(db, current_user.id)

    return [
        {
            "id": str(token.id),
            "device_info": token.device_info,
            "ip_address": token.ip_address,
            "created_at": token.created_at.isoformat(),
            "last_used_at": token.last_used_at.isoformat() if token.last_used_at else None,
            "expires_at": token.expires_at.isoformat(),
        }
        for token in tokens
    ]


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    db: DbSession,
    current_user: "User" = Depends(get_current_user),
) -> dict:
    """
    Revoke a specific session (refresh token).

    Args:
        session_id: The session/token UUID to revoke
        db: Database session
        current_user: The authenticated user

    Returns:
        Success message
    """
    import uuid

    try:
        token_uuid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session ID format"
        )

    # Verify the token belongs to the current user
    tokens = await RefreshTokenCRUD.get_active_for_user(db, current_user.id)
    if not any(t.id == token_uuid for t in tokens):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    success = await RefreshTokenCRUD.revoke(
        db,
        token_id=token_uuid,
        reason="user_revoked"
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    return {"message": "Session revoked successfully"}
