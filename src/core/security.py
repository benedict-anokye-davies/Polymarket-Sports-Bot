"""
Security utilities for authentication and password hashing.
Implements JWT token creation/verification and bcrypt password hashing.
Includes refresh token support (REQ-SEC-001).
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from src.config import get_settings
from src.core.exceptions import AuthenticationError


__all__ = [
    "create_access_token",
    "create_refresh_token_jwt",
    "verify_token",
    "hash_password",
    "verify_password",
    "hash_refresh_token",
    "generate_refresh_token",
    "verify_refresh_token",
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

    to_encode.update({"exp": expire, "iat": now, "type": "access"})

    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)

    return encoded_jwt


def create_refresh_token_jwt(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """
    Creates a JWT refresh token with the given payload.
    Refresh tokens have a longer expiration than access tokens.

    Args:
        data: Dictionary of claims to encode in the token
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT refresh token string
    """
    to_encode = data.copy()

    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=settings.refresh_token_expire_days)

    to_encode.update({"exp": expire, "iat": now, "type": "refresh"})

    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)

    return encoded_jwt


def verify_token(token: str, token_type: str = "access") -> dict[str, Any]:
    """
    Verifies and decodes a JWT token.

    Args:
        token: The JWT token string to verify
        token_type: Expected token type ("access" or "refresh")

    Returns:
        Decoded token payload as dictionary

    Raises:
        AuthenticationError: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])

        # Verify token type if specified in payload
        if "type" in payload and payload["type"] != token_type:
            raise AuthenticationError(f"Invalid token type: expected {token_type}")

        return payload
    except JWTError as e:
        raise AuthenticationError(f"Invalid or expired token: {str(e)}")


def verify_refresh_token(token: str) -> dict[str, Any]:
    """
    Verifies a refresh token specifically.

    Args:
        token: The refresh token string to verify

    Returns:
        Decoded token payload as dictionary

    Raises:
        AuthenticationError: If token is invalid or expired
    """
    return verify_token(token, token_type="refresh")


def generate_refresh_token() -> str:
    """
    Generates a secure random refresh token string.
    This is used for database-stored refresh tokens.

    Returns:
        A URL-safe random token string (64 bytes, base64 encoded)
    """
    return secrets.token_urlsafe(64)


def hash_refresh_token(token: str) -> str:
    """
    Hashes a refresh token for secure database storage.
    Uses SHA-256 for fast comparison (not bcrypt, as we need quick lookups).

    Args:
        token: The plain refresh token string

    Returns:
        SHA-256 hash of the token (hex encoded)
    """
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


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
