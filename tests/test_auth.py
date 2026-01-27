"""
Tests for authentication, security, and encryption modules.
Tests REAL functionality: JWT creation/verification, password hashing,
credential encryption, and auth flow validation.
"""

import pytest
from datetime import timedelta, datetime, timezone
from unittest.mock import patch, MagicMock
import uuid

from src.core.security import (
    create_access_token,
    verify_token,
    hash_password,
    verify_password,
    ALGORITHM,
)
from src.core.encryption import (
    encrypt_credential,
    decrypt_credential,
    _derive_key,
)
from src.core.exceptions import AuthenticationError, ValidationError


# =============================================================================
# Password Hashing Tests - Tests REAL bcrypt hashing
# =============================================================================

class TestPasswordHashing:
    """Tests for bcrypt password hashing functionality."""
    
    def test_hash_password_returns_different_from_input(self):
        """Hash should never equal the plain password."""
        password = "mysecretpassword123"
        hashed = hash_password(password)
        
        assert hashed != password
        assert len(hashed) > 0
    
    def test_hash_password_produces_bcrypt_format(self):
        """Hash should be in bcrypt format starting with $2b$."""
        password = "testpassword"
        hashed = hash_password(password)
        
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
        assert len(hashed) == 60  # bcrypt hashes are 60 chars
    
    def test_hash_password_unique_per_call(self):
        """Same password should produce different hashes (unique salt)."""
        password = "samepassword"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        
        assert hash1 != hash2  # Different salts
    
    def test_verify_password_correct(self):
        """Correct password should verify successfully."""
        password = "correctpassword"
        hashed = hash_password(password)
        
        assert verify_password(password, hashed) is True
    
    def test_verify_password_incorrect(self):
        """Wrong password should fail verification."""
        password = "correctpassword"
        hashed = hash_password(password)
        
        assert verify_password("wrongpassword", hashed) is False
    
    def test_verify_password_empty_fails(self):
        """Empty password should not match any hash."""
        password = "realpassword"
        hashed = hash_password(password)
        
        assert verify_password("", hashed) is False
    
    def test_hash_password_handles_unicode(self):
        """Unicode passwords should hash correctly."""
        password = "пароль密码🔐"
        hashed = hash_password(password)
        
        assert verify_password(password, hashed) is True
    
    def test_hash_password_rejects_long_input(self):
        """Passwords over 72 bytes should raise ValueError (bcrypt limit)."""
        password = "a" * 100  # 100 bytes, exceeds 72-byte limit
        
        with pytest.raises(ValueError) as exc_info:
            hash_password(password)
        
        assert "72 bytes" in str(exc_info.value)


# =============================================================================
# JWT Token Tests - Tests REAL JWT creation and verification
# =============================================================================

class TestJWTCreation:
    """Tests for JWT token creation."""
    
    @patch('src.core.security.settings')
    def test_create_token_returns_string(self, mock_settings):
        """Token should be a non-empty string."""
        mock_settings.secret_key = "test-secret-key-for-jwt-testing"
        mock_settings.access_token_expire_minutes = 30
        
        token = create_access_token({"sub": "user123"})
        
        assert isinstance(token, str)
        assert len(token) > 0
    
    @patch('src.core.security.settings')
    def test_create_token_has_three_parts(self, mock_settings):
        """JWT should have header.payload.signature format."""
        mock_settings.secret_key = "test-secret-key-for-jwt-testing"
        mock_settings.access_token_expire_minutes = 30
        
        token = create_access_token({"sub": "user123"})
        parts = token.split(".")
        
        assert len(parts) == 3  # header.payload.signature
    
    @patch('src.core.security.settings')
    def test_create_token_includes_custom_claims(self, mock_settings):
        """Custom claims should be included in token."""
        mock_settings.secret_key = "test-secret-key-for-jwt-testing"
        mock_settings.access_token_expire_minutes = 30
        
        user_id = str(uuid.uuid4())
        token = create_access_token({"sub": user_id, "role": "admin"})
        
        payload = verify_token(token)
        
        assert payload["sub"] == user_id
        assert payload["role"] == "admin"
    
    @patch('src.core.security.settings')
    def test_create_token_includes_exp_claim(self, mock_settings):
        """Token should include expiration claim."""
        mock_settings.secret_key = "test-secret-key-for-jwt-testing"
        mock_settings.access_token_expire_minutes = 30
        
        token = create_access_token({"sub": "user123"})
        payload = verify_token(token)
        
        assert "exp" in payload
        assert "iat" in payload
    
    @patch('src.core.security.settings')
    def test_create_token_custom_expiry(self, mock_settings):
        """Custom expiry delta should be respected."""
        mock_settings.secret_key = "test-secret-key-for-jwt-testing"
        mock_settings.access_token_expire_minutes = 30
        
        custom_delta = timedelta(hours=2)
        token = create_access_token({"sub": "user123"}, expires_delta=custom_delta)
        
        payload = verify_token(token)
        exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        iat_time = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
        
        # Should be approximately 2 hours difference
        delta = exp_time - iat_time
        assert 7190 < delta.total_seconds() < 7210  # ~2 hours


class TestJWTVerification:
    """Tests for JWT token verification."""
    
    @patch('src.core.security.settings')
    def test_verify_valid_token(self, mock_settings):
        """Valid token should verify successfully."""
        mock_settings.secret_key = "test-secret-key-for-jwt-testing"
        mock_settings.access_token_expire_minutes = 30
        
        user_id = str(uuid.uuid4())
        token = create_access_token({"sub": user_id})
        
        payload = verify_token(token)
        
        assert payload["sub"] == user_id
    
    @patch('src.core.security.settings')
    def test_verify_tampered_token_fails(self, mock_settings):
        """Tampered token should raise AuthenticationError."""
        mock_settings.secret_key = "test-secret-key-for-jwt-testing"
        mock_settings.access_token_expire_minutes = 30
        
        token = create_access_token({"sub": "user123"})
        # Tamper with the signature
        tampered = token[:-5] + "XXXXX"
        
        with pytest.raises(AuthenticationError) as exc_info:
            verify_token(tampered)
        
        assert "Invalid or expired token" in str(exc_info.value)
    
    @patch('src.core.security.settings')
    def test_verify_wrong_secret_fails(self, mock_settings):
        """Token signed with different secret should fail."""
        mock_settings.secret_key = "original-secret-key"
        mock_settings.access_token_expire_minutes = 30
        
        token = create_access_token({"sub": "user123"})
        
        # Change secret for verification
        mock_settings.secret_key = "different-secret-key"
        
        with pytest.raises(AuthenticationError):
            verify_token(token)
    
    @patch('src.core.security.settings')
    def test_verify_malformed_token_fails(self, mock_settings):
        """Completely invalid token should fail."""
        mock_settings.secret_key = "test-secret-key-for-jwt-testing"
        
        with pytest.raises(AuthenticationError):
            verify_token("not.a.valid.jwt.token")
    
    @patch('src.core.security.settings')
    def test_verify_empty_token_fails(self, mock_settings):
        """Empty token should fail."""
        mock_settings.secret_key = "test-secret-key-for-jwt-testing"
        
        with pytest.raises(AuthenticationError):
            verify_token("")
    
    @patch('src.core.security.settings')
    def test_verify_expired_token_fails(self, mock_settings):
        """Expired token should raise AuthenticationError."""
        mock_settings.secret_key = "test-secret-key-for-jwt-testing"
        mock_settings.access_token_expire_minutes = 30
        
        # Create token that's already expired
        expired_delta = timedelta(seconds=-10)  # 10 seconds ago
        token = create_access_token({"sub": "user123"}, expires_delta=expired_delta)
        
        with pytest.raises(AuthenticationError) as exc_info:
            verify_token(token)
        
        assert "expired" in str(exc_info.value).lower()


# =============================================================================
# Encryption Tests - Tests REAL Fernet encryption
# =============================================================================

class TestKeyDerivation:
    """Tests for encryption key derivation."""
    
    def test_derive_key_consistent(self):
        """Same secret should produce same derived key."""
        secret = "my-app-secret"
        
        key1 = _derive_key(secret)
        key2 = _derive_key(secret)
        
        assert key1 == key2
    
    def test_derive_key_different_secrets(self):
        """Different secrets should produce different keys."""
        key1 = _derive_key("secret-one")
        key2 = _derive_key("secret-two")
        
        assert key1 != key2
    
    def test_derive_key_is_bytes(self):
        """Derived key should be bytes."""
        key = _derive_key("test-secret")
        
        assert isinstance(key, bytes)
    
    def test_derive_key_correct_length(self):
        """Derived key should be 44 bytes (base64 encoded 32 bytes)."""
        key = _derive_key("test-secret")
        
        assert len(key) == 44  # base64 encoded 32 bytes


class TestCredentialEncryption:
    """Tests for credential encryption/decryption."""
    
    @patch('src.core.encryption.settings')
    def test_encrypt_returns_different_from_input(self, mock_settings):
        """Encrypted value should differ from plaintext."""
        mock_settings.secret_key = "test-encryption-secret-key"
        
        plaintext = "my-private-key-data"
        encrypted = encrypt_credential(plaintext)
        
        assert encrypted != plaintext
    
    @patch('src.core.encryption.settings')
    def test_decrypt_returns_original(self, mock_settings):
        """Decrypted value should match original plaintext."""
        mock_settings.secret_key = "test-encryption-secret-key"
        
        plaintext = "super-secret-api-key-12345"
        encrypted = encrypt_credential(plaintext)
        decrypted = decrypt_credential(encrypted)
        
        assert decrypted == plaintext
    
    @patch('src.core.encryption.settings')
    def test_encrypt_produces_different_ciphertext(self, mock_settings):
        """Same plaintext should produce different ciphertext (random IV)."""
        mock_settings.secret_key = "test-encryption-secret-key"
        
        plaintext = "same-value"
        encrypted1 = encrypt_credential(plaintext)
        encrypted2 = encrypt_credential(plaintext)
        
        # Fernet uses random IV, so ciphertexts differ
        assert encrypted1 != encrypted2
        
        # But both decrypt to same value
        assert decrypt_credential(encrypted1) == plaintext
        assert decrypt_credential(encrypted2) == plaintext
    
    @patch('src.core.encryption.settings')
    def test_decrypt_wrong_key_fails(self, mock_settings):
        """Decrypting with wrong key should raise ValidationError."""
        mock_settings.secret_key = "original-key"
        
        encrypted = encrypt_credential("secret-data")
        
        # Change key for decryption
        mock_settings.secret_key = "different-key"
        
        with pytest.raises(ValidationError) as exc_info:
            decrypt_credential(encrypted)
        
        assert "Failed to decrypt" in str(exc_info.value)
    
    @patch('src.core.encryption.settings')
    def test_decrypt_corrupted_data_fails(self, mock_settings):
        """Corrupted ciphertext should raise ValidationError."""
        mock_settings.secret_key = "test-encryption-secret-key"
        
        with pytest.raises(ValidationError):
            decrypt_credential("not-valid-encrypted-data")
    
    @patch('src.core.encryption.settings')
    def test_encrypt_handles_unicode(self, mock_settings):
        """Unicode plaintext should encrypt/decrypt correctly."""
        mock_settings.secret_key = "test-encryption-secret-key"
        
        plaintext = "私钥数据🔐émoji"
        encrypted = encrypt_credential(plaintext)
        decrypted = decrypt_credential(encrypted)
        
        assert decrypted == plaintext
    
    @patch('src.core.encryption.settings')
    def test_encrypt_handles_long_data(self, mock_settings):
        """Long plaintext should encrypt/decrypt correctly."""
        mock_settings.secret_key = "test-encryption-secret-key"
        
        # Simulate a long private key
        plaintext = "-----BEGIN RSA PRIVATE KEY-----\n" + "A" * 1000 + "\n-----END RSA PRIVATE KEY-----"
        encrypted = encrypt_credential(plaintext)
        decrypted = decrypt_credential(encrypted)
        
        assert decrypted == plaintext


# =============================================================================
# Auth Schema Validation Tests
# =============================================================================

class TestAuthSchemas:
    """Tests for authentication Pydantic schemas."""
    
    def test_user_create_valid(self):
        """Valid user creation data should pass validation."""
        from src.schemas.auth import UserCreate
        
        user_data = UserCreate(
            username="testuser",
            email="test@example.com",
            password="securepassword123"
        )
        
        assert user_data.username == "testuser"
        assert user_data.email == "test@example.com"
        assert user_data.password == "securepassword123"
    
    def test_user_create_invalid_email(self):
        """Invalid email should fail validation."""
        from src.schemas.auth import UserCreate
        from pydantic import ValidationError as PydanticValidationError
        
        with pytest.raises(PydanticValidationError):
            UserCreate(
                username="testuser",
                email="not-an-email",
                password="password123"
            )
    
    def test_user_login_valid(self):
        """Valid login data should pass validation."""
        from src.schemas.auth import UserLogin
        
        login_data = UserLogin(
            email="test@example.com",
            password="mypassword"
        )
        
        assert login_data.email == "test@example.com"
        assert login_data.password == "mypassword"
    
    def test_token_response_structure(self):
        """TokenResponse should have correct structure."""
        from src.schemas.auth import TokenResponse, UserResponse
        
        # Check TokenResponse has expected fields
        assert "access_token" in TokenResponse.model_fields
        assert "expires_in" in TokenResponse.model_fields
        assert "user" in TokenResponse.model_fields


# =============================================================================
# Integration: Auth Flow Tests (mocking database)
# =============================================================================

class TestAuthFlowValidation:
    """Tests for authentication flow validation logic."""
    
    def test_user_id_in_token_is_uuid_string(self):
        """User ID stored in token should be valid UUID string."""
        with patch('src.core.security.settings') as mock_settings:
            mock_settings.secret_key = "test-secret"
            mock_settings.access_token_expire_minutes = 30
            
            user_id = uuid.uuid4()
            token = create_access_token({"sub": str(user_id)})
            payload = verify_token(token)
            
            # Should be parseable as UUID
            parsed_id = uuid.UUID(payload["sub"])
            assert parsed_id == user_id
    
    def test_token_claims_preserved(self):
        """All custom claims should be preserved in token."""
        with patch('src.core.security.settings') as mock_settings:
            mock_settings.secret_key = "test-secret"
            mock_settings.access_token_expire_minutes = 30
            
            claims = {
                "sub": str(uuid.uuid4()),
                "username": "testuser",
                "role": "admin",
                "custom_field": 12345
            }
            
            token = create_access_token(claims)
            payload = verify_token(token)
            
            for key, value in claims.items():
                assert payload[key] == value


class TestSecurityConstants:
    """Tests for security module constants."""
    
    def test_algorithm_is_hs256(self):
        """JWT algorithm should be HS256."""
        assert ALGORITHM == "HS256"


# =============================================================================
# Edge Cases and Security Tests
# =============================================================================

class TestSecurityEdgeCases:
    """Tests for security edge cases."""
    
    def test_hash_empty_password(self):
        """Empty password should still hash (though not recommended)."""
        hashed = hash_password("")
        
        assert len(hashed) == 60
        assert verify_password("", hashed) is True
    
    @patch('src.core.security.settings')
    def test_token_with_special_characters(self, mock_settings):
        """Token data with special characters should work."""
        mock_settings.secret_key = "test-secret"
        mock_settings.access_token_expire_minutes = 30
        
        special_data = {
            "sub": "user@example.com",
            "name": "Test User <script>",
            "emoji": "🔐"
        }
        
        token = create_access_token(special_data)
        payload = verify_token(token)
        
        assert payload["sub"] == special_data["sub"]
        assert payload["name"] == special_data["name"]
        assert payload["emoji"] == special_data["emoji"]
    
    @patch('src.core.encryption.settings')
    def test_encrypt_empty_string(self, mock_settings):
        """Empty string should encrypt/decrypt correctly."""
        mock_settings.secret_key = "test-key"
        
        encrypted = encrypt_credential("")
        decrypted = decrypt_credential(encrypted)
        
        assert decrypted == ""
    
    def test_password_timing_attack_resistance(self):
        """Password verification should take similar time regardless of match."""
        import time
        
        password = "correctpassword"
        hashed = hash_password(password)
        
        # Time correct password
        start = time.perf_counter()
        for _ in range(10):
            verify_password(password, hashed)
        correct_time = time.perf_counter() - start
        
        # Time wrong password
        start = time.perf_counter()
        for _ in range(10):
            verify_password("wrongpassword", hashed)
        wrong_time = time.perf_counter() - start
        
        # Times should be similar (within 50% - bcrypt is constant-time)
        ratio = max(correct_time, wrong_time) / min(correct_time, wrong_time)
        assert ratio < 2.0  # Should be similar timing
