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
    email_backend: str = "console"
    email_from: str = "DRL2 <no-reply@localhost>"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_starttls: bool = True

    @model_validator(mode="after")
    def _validate_settings(self) -> Self:
        if self.environment != "development":
            if self.jwt_secret == _DEV_JWT_SECRET:
                raise ValueError("DRL_JWT_SECRET must be set outside development")
            if self.email_backend == "console":
                raise ValueError(
                    "DRL_EMAIL_BACKEND must be 'smtp' outside development"
                )
        if self.email_backend not in ("console", "smtp"):
            raise ValueError("DRL_EMAIL_BACKEND must be 'console' or 'smtp'")
        if self.email_backend == "smtp" and not self.smtp_host:
            raise ValueError(
                "DRL_SMTP_HOST is required when DRL_EMAIL_BACKEND is 'smtp'"
            )
        return self


settings = Settings()
