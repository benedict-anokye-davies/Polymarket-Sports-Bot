"""
Security utilities for authentication and password hashing.
Implements JWT token creation/verification and bcrypt password hashing.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from src.config import get_settings
from src.core.exceptions import AuthenticationError


__all__ = [
    "create_access_token",
    "verify_token",
    "hash_password",
    "verify_password",
]

settings = get_settings()

ALGORITHM = "HS256"


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """
    Creates a JWT access token with the given payload.
    
    Args:
        data: Dictionary of claims to encode in the token
        expires_delta: Optional custom expiration time
    
    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.access_token_expire_minutes)
    
    to_encode.update({"exp": expire, "iat": now})
    
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)
    
    return encoded_jwt


def verify_token(token: str) -> dict[str, Any]:
    """
    Verifies and decodes a JWT token.
    
    Args:
        token: The JWT token string to verify
    
    Returns:
        Decoded token payload as dictionary
    
    Raises:
        AuthenticationError: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        raise AuthenticationError(f"Invalid or expired token: {str(e)}")


def hash_password(password: str) -> str:
    """
    Hashes a password using bcrypt.

    Args:
        password: Plain text password to hash

    Returns:
        Bcrypt hash of the password
    """
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a password against its hash.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Bcrypt hash to compare against

    Returns:
        True if password matches, False otherwise
    """
    password_bytes = plain_password.encode('utf-8')
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)
