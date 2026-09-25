from typing import Self

from pydantic import model_validator
from app.market.models import Timeframe
from app.scanner.models import ScannerStrategy
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_JWT_SECRET = "dev-only-secret-change-me-before-production-0123456789"
_MARKET_PROVIDERS = ("gate",)


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
    market_provider: str = "gate"
    scanner_enabled: bool = False
    scanner_poll_seconds: int = 60
    scanner_risk_reward: float | None = 2.0
    scanner_tie_break: str = "stop_first"
    scanner_symbols: list[str] = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    scanner_timeframe: str = "1h"
    scanner_strategies: list[str] = [
        "trend_continuation",
        "break_and_retest",
        "liquidity_sweep",
    ]

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
        if self.market_provider not in _MARKET_PROVIDERS:
            raise ValueError(
                "DRL_MARKET_PROVIDER must be one of: " + ", ".join(_MARKET_PROVIDERS)
            )
        valid_timeframes = {tf.value for tf in Timeframe}
        if self.scanner_timeframe not in valid_timeframes:
            raise ValueError(
                "DRL_SCANNER_TIMEFRAME must be one of: "
                + ", ".join(sorted(valid_timeframes))
            )
        valid_strategies = {s.value for s in ScannerStrategy}
        invalid = set(self.scanner_strategies) - valid_strategies
        if invalid:
            raise ValueError(
                "DRL_SCANNER_STRATEGIES contains unknown strategies: "
                + ", ".join(sorted(invalid))
            )
        if self.scanner_tie_break not in ("stop_first", "target_first"):
            raise ValueError(
                "DRL_SCANNER_TIE_BREAK must be 'stop_first' or 'target_first'"
            )
        if self.scanner_risk_reward is not None and self.scanner_risk_reward <= 0:
            raise ValueError("DRL_SCANNER_RISK_REWARD must be positive if set")
        return self


settings = Settings()
