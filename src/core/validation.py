"""
Request validation middleware for input sanitization and size limits.
Provides comprehensive request filtering and validation.
"""

import re
import json
import logging
from dataclasses import dataclass, field
from typing import Callable, Awaitable, Pattern
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from fastapi import HTTPException


logger = logging.getLogger(__name__)


@dataclass
class ValidationConfig:
    """Configuration for request validation."""
    max_body_size_bytes: int = 10 * 1024 * 1024  # 10MB default
    max_url_length: int = 2048
    max_header_size: int = 8192
    max_query_params: int = 50
    max_json_depth: int = 20
    
    # Content type restrictions
    allowed_content_types: list[str] = field(default_factory=lambda: [
        "application/json",
        "application/x-www-form-urlencoded",
        "multipart/form-data",
        "text/plain",
    ])
    
    # Path traversal patterns to block
    blocked_path_patterns: list[str] = field(default_factory=lambda: [
        r"\.\./",
        r"\.\.\\",
        r"%2e%2e",
        r"%252e%252e",
    ])
    
    # SQL injection patterns
    sql_injection_patterns: list[str] = field(default_factory=lambda: [
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE|TRUNCATE)\b)",
        r"(--)|(;)--",
        r"(\/\*.*\*\/)",
    ])
    
    # XSS patterns
    xss_patterns: list[str] = field(default_factory=lambda: [
        r"<script[^>]*>",
        r"javascript:",
        r"on\w+\s*=",
        r"<iframe[^>]*>",
    ])


class RequestValidationError(Exception):
    """Raised when request validation fails."""
    def __init__(self, message: str, error_code: str):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


def check_json_depth(obj, max_depth: int, current_depth: int = 0) -> bool:
    """
    Check if JSON object exceeds maximum nesting depth.
    
    Args:
        obj: JSON object to check
        max_depth: Maximum allowed depth
        current_depth: Current recursion depth
    
    Returns:
        True if within limits, False if exceeded
    """
    if current_depth > max_depth:
        return False
    
    if isinstance(obj, dict):
        for value in obj.values():
            if not check_json_depth(value, max_depth, current_depth + 1):
                return False
    elif isinstance(obj, list):
        for item in obj:
            if not check_json_depth(item, max_depth, current_depth + 1):
                return False
    
    return True


class InputSanitizer:
    """
    Sanitizes input strings for common attack patterns.
    """
    
    def __init__(self, config: ValidationConfig):
        self._config = config
        self._path_patterns = [
            re.compile(p, re.IGNORECASE) for p in config.blocked_path_patterns
        ]
        self._sql_patterns = [
            re.compile(p, re.IGNORECASE) for p in config.sql_injection_patterns
        ]
        self._xss_patterns = [
            re.compile(p, re.IGNORECASE) for p in config.xss_patterns
        ]
    
    def check_path_traversal(self, value: str) -> bool:
        """Check for path traversal attempts."""
        for pattern in self._path_patterns:
            if pattern.search(value):
                return True
        return False
    
    def check_sql_injection(self, value: str) -> bool:
        """Check for SQL injection patterns."""
        for pattern in self._sql_patterns:
            if pattern.search(value):
                return True
        return False
    
    def check_xss(self, value: str) -> bool:
        """Check for XSS patterns."""
        for pattern in self._xss_patterns:
            if pattern.search(value):
                return True
        return False
    
    def validate_string(self, value: str, context: str = "") -> list[str]:
        """
        Validate a string for common attack patterns.
        
        Returns:
            List of detected issues (empty if clean)
        """
        issues = []
        
        if self.check_path_traversal(value):
            issues.append(f"Path traversal detected in {context}")
        
        if self.check_sql_injection(value):
            issues.append(f"SQL injection pattern detected in {context}")
        
        if self.check_xss(value):
            issues.append(f"XSS pattern detected in {context}")
        
        return issues
    
    def sanitize_recursive(self, obj, context: str = "body") -> list[str]:
        """
        Recursively validate all strings in an object.
        
        Returns:
            List of all detected issues
        """
        all_issues = []
        
        if isinstance(obj, str):
            all_issues.extend(self.validate_string(obj, context))
        elif isinstance(obj, dict):
            for key, value in obj.items():
                all_issues.extend(self.validate_string(key, f"{context}.key"))
                all_issues.extend(self.sanitize_recursive(value, f"{context}.{key}"))
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                all_issues.extend(self.sanitize_recursive(item, f"{context}[{i}]"))
        
        return all_issues


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware for validating incoming requests.
    
    Checks:
    - Request body size
    - URL length
    - Content type
    - JSON depth
    - Common attack patterns
    """
    
    def __init__(self, app, config: ValidationConfig | None = None):
        super().__init__(app)
        self._config = config or ValidationConfig()
        self._sanitizer = InputSanitizer(self._config)
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Process and validate the request."""
        try:
            await self._validate_request(request)
            return await call_next(request)
        except RequestValidationError as e:
            logger.warning(f"Request validation failed: {e.message}")
            return JSONResponse(
                status_code=400,
                content={
                    "error": e.error_code,
                    "message": e.message,
                },
            )
        except Exception as e:
            logger.error(f"Validation middleware error: {e}")
            return await call_next(request)
    
    async def _validate_request(self, request: Request) -> None:
        """Run all validation checks."""
        # URL length check
        url_length = len(str(request.url))
        if url_length > self._config.max_url_length:
            raise RequestValidationError(
                f"URL exceeds maximum length ({url_length} > {self._config.max_url_length})",
                "URL_TOO_LONG",
            )
        
        # Query parameter count check
        if len(request.query_params) > self._config.max_query_params:
            raise RequestValidationError(
                f"Too many query parameters",
                "TOO_MANY_PARAMS",
            )
        
        # Content-Length check
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                if size > self._config.max_body_size_bytes:
                    raise RequestValidationError(
                        f"Request body too large ({size} bytes)",
                        "BODY_TOO_LARGE",
                    )
            except ValueError:
                raise RequestValidationError(
                    "Invalid Content-Length header",
                    "INVALID_CONTENT_LENGTH",
                )
        
        # Content-Type check for POST/PUT/PATCH
        if request.method in ("POST", "PUT", "PATCH"):
            content_type = request.headers.get("content-type", "")
            base_type = content_type.split(";")[0].strip()
            
            if base_type and base_type not in self._config.allowed_content_types:
                raise RequestValidationError(
                    f"Unsupported content type: {base_type}",
                    "UNSUPPORTED_CONTENT_TYPE",
                )
        
        # Path validation
        path_issues = self._sanitizer.validate_string(request.url.path, "path")
        if path_issues:
            raise RequestValidationError(
                "; ".join(path_issues),
                "INVALID_PATH",
            )
        
        # Query parameter validation
        for key, value in request.query_params.items():
            issues = self._sanitizer.validate_string(key, "query_key")
            issues.extend(self._sanitizer.validate_string(value, f"query[{key}]"))
            if issues:
                raise RequestValidationError(
                    "; ".join(issues),
                    "INVALID_QUERY_PARAM",
                )
        
        # JSON body validation
        if request.method in ("POST", "PUT", "PATCH"):
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                await self._validate_json_body(request)
    
    async def _validate_json_body(self, request: Request) -> None:
        """Validate JSON request body."""
        try:
            body = await request.body()
            
            if len(body) > self._config.max_body_size_bytes:
                raise RequestValidationError(
                    "Request body too large",
                    "BODY_TOO_LARGE",
                )
            
            if not body:
                return
            
            data = json.loads(body)
            
            # Check JSON depth
            if not check_json_depth(data, self._config.max_json_depth):
                raise RequestValidationError(
                    f"JSON nesting exceeds maximum depth ({self._config.max_json_depth})",
                    "JSON_TOO_DEEP",
                )
            
            # Check for attack patterns
            issues = self._sanitizer.sanitize_recursive(data)
            if issues:
                raise RequestValidationError(
                    "; ".join(issues[:3]),  # Limit error message length
                    "INVALID_INPUT",
                )
                
        except json.JSONDecodeError as e:
            raise RequestValidationError(
                f"Invalid JSON: {e.msg}",
                "INVALID_JSON",
            )
        except RequestValidationError:
            raise
        except Exception as e:
            logger.error(f"JSON validation error: {e}")


def create_validation_config(
    max_body_mb: int = 10,
    strict_mode: bool = False,
) -> ValidationConfig:
    """
    Create a validation configuration.
    
    Args:
        max_body_mb: Maximum body size in megabytes
        strict_mode: Enable stricter validation rules
    
    Returns:
        Configured ValidationConfig
    """
    config = ValidationConfig(
        max_body_size_bytes=max_body_mb * 1024 * 1024,
    )
    
    if strict_mode:
        config.max_json_depth = 10
        config.max_query_params = 20
        config.max_url_length = 1024
    
    return config
