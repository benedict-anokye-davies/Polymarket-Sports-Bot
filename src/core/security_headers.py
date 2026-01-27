"""
Security Headers Middleware (REQ-SEC-008)

Adds essential security headers to all HTTP responses following OWASP guidelines.
These headers help protect against common web vulnerabilities like XSS, clickjacking,
content sniffing, and other attacks.
"""

from dataclasses import dataclass, field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


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


def create_security_headers_config(
    debug: bool = False,
    csp_report_uri: str | None = None,
) -> SecurityHeadersConfig:
    """
    Creates a security headers configuration appropriate for the environment.

    Args:
        debug: If True, relaxes certain headers for development
        csp_report_uri: Optional URI for CSP violation reports
    """
    config = SecurityHeadersConfig()

    if debug:
        # Relax HSTS in development
        config.hsts_enabled = False
        # More permissive CSP for development
        config.csp_directives["connect-src"] = "'self' ws: wss: http://localhost:* http://127.0.0.1:*"

    if csp_report_uri:
        config.csp_directives["report-uri"] = csp_report_uri

    return config


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds security headers to HTTP responses.

    Usage:
        app.add_middleware(
            SecurityHeadersMiddleware,
            config=SecurityHeadersConfig(),
        )
    """

    def __init__(self, app, config: SecurityHeadersConfig | None = None):
        super().__init__(app)
        self.config = config or SecurityHeadersConfig()

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Check if path is excluded
        path = request.url.path
        if any(path.startswith(excluded) for excluded in self.config.excluded_paths):
            return response

        # X-Content-Type-Options
        if self.config.x_content_type_options:
            response.headers["X-Content-Type-Options"] = self.config.x_content_type_options

        # X-Frame-Options
        if self.config.x_frame_options:
            response.headers["X-Frame-Options"] = self.config.x_frame_options

        # X-XSS-Protection
        if self.config.x_xss_protection:
            response.headers["X-XSS-Protection"] = self.config.x_xss_protection

        # Strict-Transport-Security (HSTS)
        if self.config.hsts_enabled:
            hsts_value = f"max-age={self.config.hsts_max_age}"
            if self.config.hsts_include_subdomains:
                hsts_value += "; includeSubDomains"
            if self.config.hsts_preload:
                hsts_value += "; preload"
            response.headers["Strict-Transport-Security"] = hsts_value

        # Referrer-Policy
        if self.config.referrer_policy:
            response.headers["Referrer-Policy"] = self.config.referrer_policy

        # Content-Security-Policy
        if self.config.csp_enabled and self.config.csp_directives:
            csp_parts = []
            for directive, value in self.config.csp_directives.items():
                csp_parts.append(f"{directive} {value}")
            response.headers["Content-Security-Policy"] = "; ".join(csp_parts)

        # Permissions-Policy
        if self.config.permissions_policy_enabled and self.config.permissions_policy:
            policy_parts = []
            for feature, value in self.config.permissions_policy.items():
                policy_parts.append(f"{feature}={value}")
            response.headers["Permissions-Policy"] = ", ".join(policy_parts)

        # Cache-Control for API responses
        if self.config.cache_control_private and path.startswith("/api"):
            # Don't cache API responses by default
            if "Cache-Control" not in response.headers:
                response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"

        return response
