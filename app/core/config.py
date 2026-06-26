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
    platform_activation_token_ttl_seconds: int = 60 * 60 * 24 * 7
    default_tenant_id: str = "tenant_default"

    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    database_url: str = "sqlite:///./.data/amazon-experts-backend.sqlite3"
    database_auto_migrate: bool = True
    database_schema_dir: str = Field(
        default_factory=lambda: str(Path(__file__).resolve().parents[2] / "infra" / "sql")
    )

    pageindex_base_url: str | None = None
    pageindex_api_key: str | None = None

    # agent-gateway ACP data plane. The route prefix is the gateway's external path prefix for
    # the ACP route; the client posts to <prefix>/turn and <prefix>/permission and reads history
    # from <prefix>/sessions and <prefix>/sessions/{id}/transcript (all route-scoped and
    # authenticated by acp_auth_token, so no admin plane is needed). When acp_cwd_base is set
    # each session's cwd is <base>/<tenant_id>, and it must resolve under the ACP service's
    # allowedRoots (shared filesystem).
    acp_gateway_base_url: str | None = None
    acp_route_prefix: str = ""
    acp_search_route_prefix: str | None = None
    acp_auth_token: str | None = None
    acp_client_id: str = "amazon-experts-backend"
    acp_default_model: str | None = None
    acp_default_cwd: str = Field(default_factory=lambda: str(Path.cwd()))
    acp_cwd_base: str | None = None

    codex_home: str = Field(default_factory=lambda: str(Path.home() / ".codex"))
    codex_skills_dir: str | None = None

    object_storage_backend: str = "local"
    object_storage_local_dir: str = Field(
        default_factory=lambda: str(Path.cwd() / ".data" / "objects")
    )
    object_storage_public_base_url: str | None = None
    object_storage_max_upload_bytes: int = 100 * 1024 * 1024

    minio_endpoint: str | None = None
    minio_access_key: str | None = None
    minio_secret_key: str | None = None
    minio_bucket: str | None = None
    minio_secure: bool = False
    # Short-lived presigned URL TTL for document upload/download (seconds). See design section 11.
    presigned_url_ttl_seconds: int = 900


@lru_cache
def get_settings() -> Settings:
    return Settings()
