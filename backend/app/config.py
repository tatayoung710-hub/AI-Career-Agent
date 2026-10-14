"""Environment configuration shared by the API, worker and Alembic."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "AI Career Agent"
    environment: Literal["development", "test", "production"] = Field(
        default="development", validation_alias="APP_ENV"
    )
    database_url: str = "sqlite:///./data/career.db"
    jwt_secret: str = "development-only-change-this-secret-before-deployment"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = Field(default=720, ge=1, le=10080)
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    storage_dir: Path = Path("./data/files")
    max_upload_bytes: int = Field(default=20 * 1024 * 1024, ge=1024)
    openai_api_key: str = ""
    openai_base_url: str | None = None
    openai_model: str = "gpt-4.1-mini"
    worker_poll_seconds: float = Field(default=2.0, ge=0.1)
    task_lease_seconds: int = Field(default=300, ge=30)
    ai_timeout_seconds: float = Field(default=90.0, ge=1, le=240)
    ai_max_concurrency: int = Field(default=3, ge=1, le=20)
    feishu_access_token: str = ""
    source_feishu_allowed_bases: list[str] = []
    source_fetch_allowed_hosts: list[str] = ["open.feishu.cn"]
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_starttls: bool = True
    email_submit_enabled: bool = False
    smtp_recipient_allowlist: str = ""

    @model_validator(mode="after")
    def validate_production(self) -> "Settings":
        if self.environment == "production":
            if self.database_url.startswith("sqlite"):
                raise ValueError("Production requires PostgreSQL; SQLite is local development only")
            if self.jwt_secret.startswith("development-only") or len(self.jwt_secret) < 32:
                raise ValueError("Production JWT_SECRET must contain at least 32 characters")
            if "*" in self.cors_origins:
                raise ValueError("Production CORS_ORIGINS must list explicit origins")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
