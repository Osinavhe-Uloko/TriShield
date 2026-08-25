from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "TriShield Phishing Detection API"
    database_url: str = "sqlite:///./trishield.db"

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        # Managed Postgres providers (e.g. Render) hand out `postgres://`,
        # a scheme SQLAlchemy 1.4+/2.x no longer accepts.
        if value.startswith("postgres://"):
            return "postgresql://" + value[len("postgres://"):]
        return value
    jwt_secret_key: str = "dev-secret-change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    rate_limit_per_minute: int = 60
    webpage_fetch_use_network: bool = True
    cors_allow_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]


settings = Settings()
