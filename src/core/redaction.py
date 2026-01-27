"""
Sensitive Data Redaction Utility (REQ-SEC-007)

Provides utilities to redact sensitive information from logs, error messages,
and other outputs to prevent accidental credential exposure.
"""

import re
from typing import Any
from dataclasses import dataclass, field


@dataclass
class RedactionConfig:
    """Configuration for sensitive data redaction."""

    # Default mask string
    mask: str = "***REDACTED***"

    # Patterns to detect sensitive data (case-insensitive)
    sensitive_keys: list[str] = field(default_factory=lambda: [
        "password",
        "passwd",
        "secret",
        "api_key",
        "apikey",
        "api_secret",
        "apisecret",
        "private_key",
        "privatekey",
        "access_token",
        "accesstoken",
        "refresh_token",
        "refreshtoken",
        "bearer",
        "authorization",
        "auth_token",
        "authtoken",
        "credential",
        "credentials",
        "api_passphrase",
        "passphrase",
        "jwt",
        "session_id",
        "sessionid",
        "cookie",
        "x-api-key",
        "x-auth-token",
    ])

    # Regex patterns for common sensitive data formats
    patterns: list[tuple[str, str]] = field(default_factory=lambda: [
        # Ethereum private keys (64 hex chars, optionally with 0x prefix)
        (r"(0x)?[a-fA-F0-9]{64}", "***ETH_KEY***"),
        # Ethereum addresses
        (r"0x[a-fA-F0-9]{40}", "0x****...****"),
        # JWT tokens
        (r"eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*", "***JWT***"),
        # Bearer tokens
        (r"Bearer\s+[a-zA-Z0-9_\-\.]+", "Bearer ***TOKEN***"),
        # Base64-encoded data that looks like a key (32+ chars)
        (r"[A-Za-z0-9+/]{32,}={0,2}", "***BASE64***"),
        # AWS keys
        (r"AKIA[0-9A-Z]{16}", "***AWS_KEY***"),
        # Generic API keys (alphanumeric, 20+ chars)
        (r"[a-zA-Z0-9_\-]{32,}", "***API_KEY***"),
    ])

    # Show partial data (first/last N chars) instead of full mask
    show_partial: bool = True
    partial_prefix_length: int = 4
    partial_suffix_length: int = 4
    partial_min_length: int = 12  # Minimum length to show partial


def redact_sensitive(
    data: Any,
    config: RedactionConfig | None = None,
    depth: int = 0,
    max_depth: int = 10,
) -> Any:
    """
    Recursively redacts sensitive information from data structures.

    Args:
        data: The data to redact (dict, list, str, or primitive)
        config: Redaction configuration
        depth: Current recursion depth
        max_depth: Maximum recursion depth to prevent infinite loops

    Returns:
        The data with sensitive values redacted
    """
    if config is None:
        config = RedactionConfig()

    if depth > max_depth:
        return config.mask

    if isinstance(data, dict):
        return _redact_dict(data, config, depth, max_depth)
    elif isinstance(data, list):
        return [redact_sensitive(item, config, depth + 1, max_depth) for item in data]
    elif isinstance(data, str):
        return _redact_string(data, config)
    else:
        return data


def _redact_dict(
    data: dict,
    config: RedactionConfig,
    depth: int,
    max_depth: int,
) -> dict:
    """Redacts sensitive keys in a dictionary."""
    result = {}
    sensitive_keys_lower = [k.lower() for k in config.sensitive_keys]

    for key, value in data.items():
        key_lower = key.lower() if isinstance(key, str) else str(key).lower()

        # Check if the key itself is sensitive
        is_sensitive = any(
            sensitive in key_lower or key_lower in sensitive
            for sensitive in sensitive_keys_lower
        )

        if is_sensitive and isinstance(value, str):
            result[key] = _mask_value(value, config)
        else:
            result[key] = redact_sensitive(value, config, depth + 1, max_depth)

    return result


def _redact_string(value: str, config: RedactionConfig) -> str:
    """Applies pattern-based redaction to a string value."""
    result = value

    # Apply regex patterns
    for pattern, replacement in config.patterns:
        result = re.sub(pattern, replacement, result)

    return result


def _mask_value(value: str, config: RedactionConfig) -> str:
    """Masks a sensitive value, optionally showing partial data."""
    if not value:
        return config.mask

    if config.show_partial and len(value) >= config.partial_min_length:
        prefix = value[:config.partial_prefix_length]
        suffix = value[-config.partial_suffix_length:]
        middle_len = len(value) - config.partial_prefix_length - config.partial_suffix_length
        return f"{prefix}{'*' * min(middle_len, 8)}{suffix}"

    return config.mask


def redact_for_logging(data: Any) -> Any:
    """
    Convenience function for redacting data before logging.
    Uses default configuration optimized for log output.
    """
    config = RedactionConfig(show_partial=True)
    return redact_sensitive(data, config)


def redact_error_message(message: str) -> str:
    """
    Redacts sensitive patterns from error messages.
    More aggressive pattern matching for error strings.
    """
    config = RedactionConfig(show_partial=False)
    return _redact_string(message, config)


def create_safe_repr(obj: Any, max_length: int = 100) -> str:
    """
    Creates a safe string representation of an object for logging.
    Redacts sensitive data and truncates long strings.
    """
    try:
        redacted = redact_sensitive(obj)
        repr_str = repr(redacted)
        if len(repr_str) > max_length:
            return repr_str[:max_length - 3] + "..."
        return repr_str
    except Exception:
        return "<redaction error>"


class RedactingFormatter:
    """
    A logging formatter mixin that redacts sensitive data.
    Can be used with standard Python logging formatters.
    """

    def __init__(self, config: RedactionConfig | None = None):
        self.redaction_config = config or RedactionConfig()

    def redact_record(self, record: Any) -> Any:
        """Redacts sensitive data from a logging record."""
        if hasattr(record, "msg"):
            if isinstance(record.msg, str):
                record.msg = _redact_string(record.msg, self.redaction_config)
            elif isinstance(record.msg, dict):
                record.msg = redact_sensitive(record.msg, self.redaction_config)

        if hasattr(record, "args") and record.args:
            if isinstance(record.args, dict):
                record.args = redact_sensitive(record.args, self.redaction_config)
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    redact_sensitive(arg, self.redaction_config)
                    for arg in record.args
                )

        return record
