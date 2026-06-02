from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import install_error_handlers
from app.db import migrate_database


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if settings.database_auto_migrate:
            migrate_database(settings)
        yield

    app = FastAPI(
        title="Amazon Experts Backend",
        version="0.1.0",
        description="FastAPI compatibility shell for PageIndex, ngent and Codex skills.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    install_error_handlers(app)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "amazon-experts-backend"}

    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
