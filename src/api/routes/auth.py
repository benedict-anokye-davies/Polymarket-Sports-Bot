"""
Authentication routes for user registration and login.
"""

from datetime import timedelta
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, HTTPException, status, Depends, Form
from fastapi.security import OAuth2PasswordRequestForm

from src.api.deps import DbSession, get_current_user
from src.config import get_settings
from src.core.security import create_access_token

settings = get_settings()
from src.db.crud.user import UserCRUD
from src.db.crud.global_settings import GlobalSettingsCRUD
from src.db.crud.sport_config import SportConfigCRUD
from src.schemas.auth import UserCreate, UserLogin, UserResponse, TokenResponse
from src.core.exceptions import ValidationError

if TYPE_CHECKING:
    from src.models.user import User


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: DbSession) -> TokenResponse:
    """
    Registers a new user account.
    Creates default global settings and sport configurations.
    
    Args:
        user_data: Registration details (username, email, password)
        db: Database session
    
    Returns:
        JWT access token and user data
    """
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
    
    await GlobalSettingsCRUD.create(db, user.id)
    await SportConfigCRUD.create_defaults_for_user(db, user.id)
    
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes)
    )
    
    return TokenResponse(
        access_token=access_token,
        expires_in=settings.access_token_expire_minutes * 60,
        user=UserResponse.model_validate(user)
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    db: DbSession,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> TokenResponse:
    """
    Authenticates user and returns access token.
    Accepts OAuth2 form data (username field contains email).
    
    Args:
        db: Database session
        form_data: OAuth2 form with username (email) and password
    
    Returns:
        JWT access token and user data
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
    
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes)
    )
    
    return TokenResponse(
        access_token=access_token,
        expires_in=settings.access_token_expire_minutes * 60,
        user=UserResponse.model_validate(user)
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: "User" = Depends(get_current_user)
) -> UserResponse:
    """
    Returns the current authenticated user's information.
    """
    return UserResponse.model_validate(current_user)
