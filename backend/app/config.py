from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings

# Look for .env in the project root (parent of backend/)
ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    # Environment
    env: str = "development"  # development, staging, or production

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/app"
    db_pool_size: int = 20
    db_pool_max_overflow: int = 10
    db_pool_timeout: int = 30
    db_pool_recycle: int = 3600
    db_echo: bool = False

    # JWT
    jwt_secret_key: str  # No default — must be set
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # Cookies
    cookie_secure: bool = True  # Requires HTTPS (Caddy provides this)
    cookie_samesite: str = "lax"
    cookie_domain: str | None = None  # None = current domain only

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        """Ensure JWT secret is cryptographically strong."""
        if not v:
            raise ValueError(
                "JWT_SECRET_KEY is required. "
                'Generate with: python -c "import secrets; print(secrets.token_urlsafe(64))"'
            )
        if len(v) < 32:
            raise ValueError(
                "JWT_SECRET_KEY must be at least 32 characters. "
                'Generate with: python -c "import secrets; print(secrets.token_urlsafe(64))"'
            )
        # Warn if looks like a weak secret
        weak_patterns = ["secret", "password", "test", "123", "admin", "key"]
        if any(pattern in v.lower() for pattern in weak_patterns):
            raise ValueError(
                "JWT_SECRET_KEY appears to contain common weak patterns. "
                "Use cryptographically random value."
            )
        return v

    @field_validator("cookie_secure")
    @classmethod
    def validate_cookie_secure(cls, v: bool, info) -> bool:
        """Warn about insecure cookie settings in production."""
        import sys

        env = info.data.get("env", "development")

        if not v and env in ["production", "staging"]:
            raise ValueError(
                "COOKIE_SECURE=false is not allowed in production/staging. "
                "Cookies without Secure flag can be intercepted over HTTP."
            )

        if not v and env == "development":
            print(
                "⚠️  WARNING: COOKIE_SECURE=false - Cookies can be intercepted! "
                "Only use for local development without HTTPS.",
                file=sys.stderr,
            )

        return v

    model_config = {
        "env_file": str(ENV_FILE) if ENV_FILE.exists() else None,
        "extra": "ignore",  # Ignore extra env vars not defined in model
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Lazy proxy so that `from app.config import settings` still works,
# but construction is deferred until first attribute access.
class _SettingsProxy:
    def __getattr__(self, name: str):
        return getattr(get_settings(), name)


settings = _SettingsProxy()
