from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_JWT_SECRET = "dev-only-secret-change-me-before-production-0123456789"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="DRL_", extra="ignore"
    )

    app_name: str = "DRL2 API"
    environment: str = "development"
    cors_origins: list[str] = ["http://localhost:3000"]
    database_url: str = "postgresql+psycopg:///drl2"
    jwt_secret: str = _DEV_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    @model_validator(mode="after")
    def _require_real_secret_outside_development(self) -> Self:
        if self.environment != "development" and self.jwt_secret == _DEV_JWT_SECRET:
            raise ValueError("DRL_JWT_SECRET must be set outside development")
        return self


settings = Settings()
