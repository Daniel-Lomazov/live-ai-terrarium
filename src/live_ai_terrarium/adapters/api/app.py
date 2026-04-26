from __future__ import annotations

from fastapi import FastAPI

from .routes import CommandBackend, QueryBackend, build_api_router


def create_app(*, command_backend: CommandBackend, query_backend: QueryBackend) -> FastAPI:
    app = FastAPI(
        title="Live AI Terrarium Local API",
        version="1.0.1",
    )
    app.include_router(
        build_api_router(command_backend=command_backend, query_backend=query_backend),
        prefix="/api",
    )
    return app


__all__ = ["create_app"]