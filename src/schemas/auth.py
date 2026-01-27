"""
Authentication schemas for user registration and login.
"""

import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """
    Schema for user registration request.
    """
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)


class UserLogin(BaseModel):
    """
    Schema for user login request.
    """
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """
    Schema for user data in API responses.
    Excludes sensitive fields like password hash.
    """
    id: uuid.UUID
    username: str
    email: EmailStr
    is_active: bool
    onboarding_completed: bool
    onboarding_step: int
    created_at: datetime
    
    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """
    Schema for JWT token response after successful authentication.
    Includes both access token and refresh token (REQ-SEC-001).
    """
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_in: int | None = None
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    """
    Schema for token refresh request.
    """
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    """
    Schema for token refresh response.
    Returns new access token and optionally a rotated refresh token.
    """
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_in: int | None = None


class LogoutRequest(BaseModel):
    """
    Schema for logout request.
    Optionally revokes the refresh token.
    """
    refresh_token: str | None = None
    logout_all_devices: bool = False
