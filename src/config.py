"""
Application configuration management using Pydantic settings.
Loads configuration from environment variables with validation.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    All sensitive values should be set via environment variables,
    not hardcoded in this file.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore frontend env vars like VITE_API_URL
    )
    
    # Application
    app_name: str = "polymarket-bot"
    debug: bool = False
    secret_key: str
    
    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """
        Validates that secret_key is cryptographically secure.
        Requires minimum 32 characters (256 bits) for production use.
        """
        if len(v) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 characters. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        # Warn about common weak keys (but don't block in case of testing)
        weak_keys = ["changeme", "secret", "password", "12345678"]
        if any(weak in v.lower() for weak in weak_keys):
            import logging
            logging.getLogger(__name__).warning(
                "SECRET_KEY appears to contain a weak pattern. "
                "Use a cryptographically random value in production."
            )
        return v
    
    # Database
    database_url: str
    
    # JWT Configuration
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # CORS Configuration
    # Comma-separated list of allowed origins, or "*" for all (not recommended for production)
    # Includes localhost for development and common deployment platforms
    cors_allowed_origins: str = "http://localhost:3000,http://localhost:5173,http://localhost:5175,http://127.0.0.1:3000,http://127.0.0.1:5173,http://127.0.0.1:5175,https://polymarket-sports-bot.netlify.app,https://polymarket-sports-bot.vercel.app,https://polymarket-sports-bot-9ndj.vercel.app,https://polymarket-sports-bot-7j2h.vercel.app,https://polymarket-sports-bot-ctjt.vercel.app,https://polymarket-sports-bot-zz8c.vercel.app,https://polymarket-sports-bot.pages.dev,https://polymarket-sports-bot-production.up.railway.app"
    cors_allow_credentials: bool = True
    cors_allow_methods: str = "GET,POST,PUT,DELETE,PATCH,OPTIONS"
    cors_allow_headers: str = "Authorization,Content-Type,X-Request-ID"

    @property
    def cors_origins_list(self) -> list[str]:
        """
        Parses comma-separated CORS origins into a list.
        Returns ["*"] if cors_allowed_origins is set to "*".
        """
        if self.cors_allowed_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @property
    def cors_methods_list(self) -> list[str]:
        """Parses comma-separated CORS methods into a list."""
        if self.cors_allow_methods.strip() == "*":
            return ["*"]
        return [method.strip() for method in self.cors_allow_methods.split(",") if method.strip()]

    @property
    def cors_headers_list(self) -> list[str]:
        """Parses comma-separated CORS headers into a list."""
        if self.cors_allow_headers.strip() == "*":
            return ["*"]
        return [header.strip() for header in self.cors_allow_headers.split(",") if header.strip()]

    # Encryption key for sensitive data (must be 32+ characters)
    encryption_key: str | None = None
    
    @field_validator("encryption_key")
    @classmethod
    def validate_encryption_key(cls, v: str | None) -> str | None:
        """
        Validates that encryption_key is suitable for cryptographic use.
        Requires minimum 32 characters (256 bits) for AES-256.
        """
        if v is None:
            return v
        if len(v) < 32:
            raise ValueError(
                "ENCRYPTION_KEY must be at least 32 characters for AES-256. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        # Warn about common weak keys
        weak_keys = ["changeme", "secret", "password", "12345678", "encryptionkey"]
        if any(weak in v.lower() for weak in weak_keys):
            import logging
            logging.getLogger(__name__).warning(
                "ENCRYPTION_KEY appears to contain a weak pattern. "
                "Use a cryptographically random value in production."
            )
        return v
    
    # Discord webhook for alerts
    discord_webhook_url: str | None = None
    
    # Incident Management - PagerDuty
    pagerduty_routing_key: str | None = None
    
    # Incident Management - OpsGenie
    opsgenie_api_key: str | None = None
    
    # Incident Management - Slack
    slack_alert_webhook: str | None = None
    
    # Redis (optional, for distributed rate limiting)
    redis_url: str | None = None
    
    # Rate Limiting Configuration
    rate_limit_requests_per_minute: int = 60
    rate_limit_requests_per_hour: int = 1000
    rate_limit_burst: int = 20
    
    # CloudWatch (optional, for log shipping)
    cloudwatch_region: str | None = None
    cloudwatch_log_group: str | None = None
    cloudwatch_log_stream: str | None = None
    cloudwatch_access_key: str | None = None
    cloudwatch_secret_key: str | None = None
    
    # Elasticsearch (optional, for log shipping)
    elasticsearch_hosts: str | None = None  # Comma-separated list
    elasticsearch_index: str = "polymarket-bot-logs"
    elasticsearch_username: str | None = None
    elasticsearch_password: str | None = None
    
    @property
    def async_database_url(self) -> str:
        """
        Ensures the database URL uses the async driver.
        Converts postgresql:// to postgresql+asyncpg:// if needed.
        For Supabase pooler connections, disables prepared statements.
        """
        url = self.database_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        
        # Supabase pooler requires prepared_statement_cache_size=0
        if "pooler.supabase.com" in url or "supabase.co" in url:
            if "?" in url:
                url += "&prepared_statement_cache_size=0"
            else:
                url += "?prepared_statement_cache_size=0"
        
        return url
    
    @property
    def elasticsearch_host_list(self) -> list[str] | None:
        """
        Parses comma-separated Elasticsearch hosts into a list.
        """
        if self.elasticsearch_hosts:
            return [h.strip() for h in self.elasticsearch_hosts.split(",")]
        return None


@lru_cache
def get_settings() -> Settings:
    """
    Returns cached settings instance.
    Uses lru_cache to avoid reading .env file on every call.
    """
    return Settings()


# Global settings instance
settings = get_settings()
