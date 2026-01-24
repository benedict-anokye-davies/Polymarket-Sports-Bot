"""
Application configuration management using Pydantic settings.
Loads configuration from environment variables with validation.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    )
    
    # Application
    app_name: str = "polymarket-bot"
    debug: bool = False
    secret_key: str
    
    # Database
    database_url: str
    
    # JWT Configuration
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    
    @property
    def async_database_url(self) -> str:
        """
        Ensures the database URL uses the async driver.
        Converts postgresql:// to postgresql+asyncpg:// if needed.
        """
        url = self.database_url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    """
    Returns cached settings instance.
    Uses lru_cache to avoid reading .env file on every call.
    """
    return Settings()
