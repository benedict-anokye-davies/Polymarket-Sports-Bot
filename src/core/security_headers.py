"""
Security Headers Middleware (REQ-SEC-008)

Adds essential security headers to all HTTP responses following OWASP guidelines.
These headers help protect against common web vulnerabilities like XSS, clickjacking,
content sniffing, and other attacks.

Uses pure ASGI implementation to avoid request body consumption issues
that occur with Starlette's BaseHTTPMiddleware.
"""

import logging
from dataclasses import dataclass, field
from starlette.types import ASGIApp, Receive, Send, Scope, Message
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass
class SecurityHeadersConfig:
    """Configuration for security headers middleware."""

    # X-Content-Type-Options: Prevents MIME type sniffing
    x_content_type_options: str = "nosniff"

    # X-Frame-Options: Prevents clickjacking
    # Values: DENY, SAMEORIGIN, ALLOW-FROM uri
    x_frame_options: str = "DENY"

    # X-XSS-Protection: Legacy XSS filter (for older browsers)
    # Values: 0, 1, 1; mode=block
    x_xss_protection: str = "1; mode=block"

    # Strict-Transport-Security: Enforce HTTPS
    # Only set in production (when not debug mode)
    hsts_enabled: bool = True
    hsts_max_age: int = 31536000  # 1 year in seconds
    hsts_include_subdomains: bool = True
    hsts_preload: bool = False

    # Referrer-Policy: Controls referrer information
    # Values: no-referrer, no-referrer-when-downgrade, origin, origin-when-cross-origin,
    #         same-origin, strict-origin, strict-origin-when-cross-origin, unsafe-url
    referrer_policy: str = "strict-origin-when-cross-origin"

    # Content-Security-Policy: Controls resource loading
    # Default is permissive; tighten for production
    csp_enabled: bool = True
    csp_directives: dict[str, str] = field(default_factory=lambda: {
        "default-src": "'self'",
        "script-src": "'self' 'unsafe-inline' 'unsafe-eval'",  # Needed for React dev
        "style-src": "'self' 'unsafe-inline'",
        "img-src": "'self' data: https:",
        "font-src": "'self' data:",
        "connect-src": "'self' ws: wss: https:",
        "frame-ancestors": "'none'",
        "base-uri": "'self'",
        "form-action": "'self'",
    })

    # Permissions-Policy: Controls browser features
    permissions_policy_enabled: bool = True
    permissions_policy: dict[str, str] = field(default_factory=lambda: {
        "geolocation": "()",
        "microphone": "()",
        "camera": "()",
        "payment": "()",
        "usb": "()",
    })

    # Cache-Control for sensitive endpoints
    cache_control_private: bool = True

    # Paths to exclude from certain headers (e.g., static files)
    excluded_paths: list[str] = field(default_factory=lambda: ["/static", "/favicon.ico"])
    
    # CSRF/Origin validation settings
    validate_origin: bool = True
    allowed_origins: list[str] = field(default_factory=list)
    csrf_safe_methods: list[str] = field(default_factory=lambda: ["GET", "HEAD", "OPTIONS"])
    csrf_excluded_paths: list[str] = field(default_factory=lambda: ["/health", "/api/v1/auth/"])


def create_security_headers_config(
    debug: bool = False,
    csp_report_uri: str | None = None,
    allowed_origins: list[str] | None = None,
) -> SecurityHeadersConfig:
    """
    Creates a security headers configuration appropriate for the environment.

    Args:
        debug: If True, relaxes certain headers for development
        csp_report_uri: Optional URI for CSP violation reports
        allowed_origins: List of allowed origins for CSRF validation
    """
    config = SecurityHeadersConfig()
    
    # Set allowed origins for CSRF validation
    if allowed_origins:
        config.allowed_origins = allowed_origins
    elif debug:
        # Allow localhost origins in development
        config.allowed_origins = [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ]

    if debug:
        # Relax HSTS in development
        config.hsts_enabled = False
        # More permissive CSP for development
        config.csp_directives["connect-src"] = "'self' ws: wss: http://localhost:* http://127.0.0.1:*"
        # Disable origin validation in debug mode
        config.validate_origin = False

    if csp_report_uri:
        config.csp_directives["report-uri"] = csp_report_uri

    return config


class SecurityHeadersMiddleware:
    """
    Pure ASGI middleware that adds security headers to HTTP responses.
    
    Does NOT inherit from BaseHTTPMiddleware to avoid request body
    consumption issues that break FastAPI's Pydantic parsing.

    Usage:
        app.add_middleware(SecurityHeadersMiddleware, config=SecurityHeadersConfig())
    """

    def __init__(self, app: ASGIApp, config: SecurityHeadersConfig | None = None):
        self.app = app
        self.config = config or SecurityHeadersConfig()
        
        # Pre-build security headers for efficiency
        self._security_headers = self._build_security_headers()
    
    def _build_security_headers(self) -> list[tuple[bytes, bytes]]:
        """Pre-build security headers that don't change per request."""
        headers = []
        
        # X-Content-Type-Options
        if self.config.x_content_type_options:
            headers.append((b"x-content-type-options", self.config.x_content_type_options.encode()))
        
        # X-Frame-Options
        if self.config.x_frame_options:
            headers.append((b"x-frame-options", self.config.x_frame_options.encode()))
        
        # X-XSS-Protection
        if self.config.x_xss_protection:
            headers.append((b"x-xss-protection", self.config.x_xss_protection.encode()))
        
        # Strict-Transport-Security (HSTS)
        if self.config.hsts_enabled:
            hsts_value = f"max-age={self.config.hsts_max_age}"
            if self.config.hsts_include_subdomains:
                hsts_value += "; includeSubDomains"
            if self.config.hsts_preload:
                hsts_value += "; preload"
            headers.append((b"strict-transport-security", hsts_value.encode()))
        
        # Referrer-Policy
        if self.config.referrer_policy:
            headers.append((b"referrer-policy", self.config.referrer_policy.encode()))
        
        # Content-Security-Policy
        if self.config.csp_enabled and self.config.csp_directives:
            csp_parts = [f"{directive} {value}" for directive, value in self.config.csp_directives.items()]
            headers.append((b"content-security-policy", "; ".join(csp_parts).encode()))
        
        # Permissions-Policy
        if self.config.permissions_policy_enabled and self.config.permissions_policy:
            policy_parts = [f"{feature}={value}" for feature, value in self.config.permissions_policy.items()]
            headers.append((b"permissions-policy", ", ".join(policy_parts).encode()))
        
        return headers
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """ASGI interface - add security headers to responses."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        path = scope.get("path", "")
        
        # Check if path is excluded
        if any(path.startswith(excluded) for excluded in self.config.excluded_paths):
            await self.app(scope, receive, send)
            return
        
        # Wrap send to add security headers
        async def send_with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                
                # Add all security headers
                headers.extend(self._security_headers)
                
                # Add Cache-Control for API responses
                if self.config.cache_control_private and path.startswith("/api"):
                    # Check if Cache-Control already set
                    has_cache_control = any(h[0].lower() == b"cache-control" for h in headers)
                    if not has_cache_control:
                        headers.append((b"cache-control", b"no-store, no-cache, must-revalidate, private"))
                
                message = {**message, "headers": headers}
            
            await send(message)
        
        await self.app(scope, receive, send_with_security_headers)
