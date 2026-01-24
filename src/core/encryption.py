"""
Encryption utilities for secure credential storage.
Uses Fernet symmetric encryption for sensitive data like private keys.
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from src.config import get_settings
from src.core.exceptions import ValidationError

settings = get_settings()


def _derive_key(secret: str) -> bytes:
    """
    Derives a Fernet-compatible key from the application secret.
    Uses SHA-256 hash of the secret, then base64 encodes it.
    
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
    
    Args:
        encrypted_value: Base64-encoded encrypted string
    
    Returns:
        Decrypted plain text credential
    
    Raises:
        ValidationError: If decryption fails due to invalid token or key mismatch
    """
    try:
        key = _derive_key(settings.secret_key)
        fernet = Fernet(key)
        decrypted = fernet.decrypt(encrypted_value.encode())
        return decrypted.decode()
    except InvalidToken:
        raise ValidationError("Failed to decrypt credential: invalid token or key mismatch")
