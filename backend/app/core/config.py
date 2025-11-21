from typing import List, Optional
from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Environment
    ENV: str = "dev"

    # Database - Support both approaches
    # APPROACH 1 (Development): Individual variables
    DATABASE_URL: Optional[str] = None  # Full URL for production (Railway, Render, Supabase)
    POSTGRES_HOST: Optional[str] = None
    POSTGRES_PORT: Optional[int] = None
    POSTGRES_DB: Optional[str] = None
    POSTGRES_USER: Optional[str] = None
    POSTGRES_PASSWORD: Optional[str] = None

    # Redis
    REDIS_URL: str

    # JWT Security
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS - comma separated origins
    CORS_ORIGINS: str = ""

    # Cookie Security
    COOKIE_DOMAIN: str = "localhost"
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"

    # Brevo Email Service
    BREVO_API_KEY: str
    BREVO_SENDER_EMAIL: str
    BREVO_SENDER_NAME: str = "Suremind"

    # Frontend URL
    FRONTEND_URL: str

    # Token Expiration
    EMAIL_VERIFICATION_EXPIRE_HOURS: int = 24
    PASSWORD_RESET_EXPIRE_MINUTES: int = 15

    # Soft Delete
    SOFT_DELETE_DAYS: int = 30
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    def _construct_url(self, scheme: str) -> str:
        """Construct database URL from individual components."""
        if not all([self.POSTGRES_USER, self.POSTGRES_PASSWORD,
                    self.POSTGRES_HOST, self.POSTGRES_PORT, self.POSTGRES_DB]):
            raise ValueError(
                "Either DATABASE_URL or all POSTGRES_* variables must be set"
            )

        return (
            f"{scheme}://{self.POSTGRES_USER}:"
            f"{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:"
            f"{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    def _parse_production_url(self, url: str, scheme: str) -> str:
        """
        Parse production DATABASE_URL and convert to correct scheme.

        Handles URLs from Railway, Render, Supabase with SSL parameters.
        Converts between async (postgresql+asyncpg) and sync (postgresql) schemes.
        """
        parsed = urlparse(url)

        # Determine target scheme
        if scheme == "async":
            new_scheme = "postgresql+asyncpg"
        else:
            new_scheme = "postgresql"

        # Reconstruct URL with new scheme, preserving all parameters
        reconstructed = f"{new_scheme}://{parsed.netloc}{parsed.path}"
        if parsed.query:
            reconstructed += f"?{parsed.query}"

        return reconstructed

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """Get async PostgreSQL connection URL for FastAPI.

        Supports both:
        1. Production: Full DATABASE_URL from env (Railway, Render, Supabase)
        2. Development: Constructed from individual POSTGRES_* vars
        """
        if self.DATABASE_URL:
            # Production: use provided URL, ensure async protocol
            return self._parse_production_url(self.DATABASE_URL, scheme="async")

        # Development: construct from individual variables
        return self._construct_url("postgresql+asyncpg")

    @property
    def SYNC_DATABASE_URL(self) -> str:
        """Get sync PostgreSQL connection URL for Alembic migrations.

        Alembic requires sync protocol, but must use same source as async.
        """
        if self.DATABASE_URL:
            # Production: convert async URL to sync
            return self._parse_production_url(self.DATABASE_URL, scheme="sync")

        # Development: construct from individual variables
        return self._construct_url("postgresql")

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        if not self.CORS_ORIGINS:
            return ["*"] if self.ENV == "dev" else []
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENV == "production"


# Global settings instance
settings = Settings()
