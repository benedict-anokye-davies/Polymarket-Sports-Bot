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
    """
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
