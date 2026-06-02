from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_prefix="EXPERT_NEXT_",
        extra="ignore",
    )

    app_env: str = "development"
    jwt_secret: str = "change-me"
    jwt_issuer: str = "amazon-experts-backend"
    jwt_audience: str = "expert-web"
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_seconds: int = 60 * 60 * 24 * 7
    default_tenant_id: str = "default"

    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    database_url: str = "sqlite:///./.data/amazon-experts-backend.sqlite3"
    database_auto_migrate: bool = True
    database_schema_dir: str = Field(
        default_factory=lambda: str(Path(__file__).resolve().parents[3] / "infra" / "sql")
    )

    pageindex_base_url: str | None = None
    pageindex_api_key: str | None = None

    ngent_base_url: str | None = None
    ngent_auth_token: str | None = None
    ngent_client_id: str = "amazon-experts-backend"
    ngent_default_agent: str = "codex"
    ngent_default_cwd: str = Field(default_factory=lambda: str(Path.cwd()))

    codex_home: str = Field(default_factory=lambda: str(Path.home() / ".codex"))
    codex_skills_dir: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
