import json

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "TriShield Phishing Detection API"
    database_url: str = "sqlite:///./trishield.db"
    jwt_secret_key: str = "dev-secret-change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    rate_limit_per_minute: int = 60
    webpage_fetch_use_network: bool = True
    # Stored as a raw string (not list[str]) because pydantic-settings tries to
    # JSON-decode any complex-typed env var itself, before field validators run —
    # which makes a plain comma-separated value (easy to type into a platform's
    # env var box) blow up before we get a chance to normalize it.
    cors_allow_origins_raw: str = Field(
        default="http://localhost:5173,http://localhost:3000",
        alias="CORS_ALLOW_ORIGINS",
    )

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        # Managed Postgres providers (e.g. Render) hand out `postgres://`,
        # a scheme SQLAlchemy 1.4+/2.x no longer accepts.
        if value.startswith("postgres://"):
            return "postgresql://" + value[len("postgres://"):]
        return value

    @property
    def cors_allow_origins(self) -> list[str]:
        # Accept either a JSON array (`["https://a.com","https://b.com"]`)
        # or a plain comma-separated string (`https://a.com,https://b.com`).
        stripped = self.cors_allow_origins_raw.strip()
        if stripped.startswith("["):
            return json.loads(stripped)
        return [origin.strip() for origin in stripped.split(",") if origin.strip()]


settings = Settings()
