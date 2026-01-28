"""
Encryption utilities for secure credential storage.
Uses Fernet symmetric encryption for sensitive data like private keys.
"""

import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from src.config import get_settings
from src.core.exceptions import ValidationError

settings = get_settings()


# Salt for PBKDF2 key derivation - should be consistent for decryption
# In production, this should be stored alongside encrypted data
_KEY_DERIVATION_SALT = b"polymarket_bot_salt_v1"


def _derive_key(secret: str) -> bytes:
    """
    Derives a Fernet-compatible key from the application secret.
    Uses PBKDF2-HMAC-SHA256 for secure key derivation.
    
    Args:
        secret: The application secret key
    
    Returns:
        32-byte base64-encoded key suitable for Fernet
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_KEY_DERIVATION_SALT,
        iterations=480000,  # OWASP 2023 recommendation
    )
    key = kdf.derive(secret.encode())
    return base64.urlsafe_b64encode(key)


def _derive_key_legacy(secret: str) -> bytes:
    """
    Legacy key derivation using SHA-256.
    Kept for backward compatibility with existing encrypted data.
    
    Args:
        secret: The application secret key
    
    Returns:
        32-byte base64-encoded key suitable for Fernet
    """
    digest = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_credential(value: str) -> str:
    """
    Encrypts a sensitive credential for database storage.
    
    Args:
        value: Plain text credential to encrypt
    
    Returns:
        Base64-encoded encrypted string
    """
    key = _derive_key(settings.secret_key)
    fernet = Fernet(key)
    encrypted = fernet.encrypt(value.encode())
    return encrypted.decode()


def decrypt_credential(encrypted_value: str) -> str:
    """
    Decrypts a credential retrieved from the database.
    Tries PBKDF2-derived key first, falls back to legacy SHA-256 key.
    
    Args:
        encrypted_value: Base64-encoded encrypted string
    
    Returns:
        Decrypted plain text credential
    
    Raises:
        ValidationError: If decryption fails due to invalid token or key mismatch
    """
    # Try PBKDF2-derived key first (new method)
    try:
        key = _derive_key(settings.secret_key)
        fernet = Fernet(key)
        decrypted = fernet.decrypt(encrypted_value.encode())
        return decrypted.decode()
    except InvalidToken:
        pass
    
    # Fall back to legacy SHA-256 key for backward compatibility
    try:
        key = _derive_key_legacy(settings.secret_key)
        fernet = Fernet(key)
        decrypted = fernet.decrypt(encrypted_value.encode())
        return decrypted.decode()
    except InvalidToken:
        raise ValidationError("Failed to decrypt credential: invalid token or key mismatch")
