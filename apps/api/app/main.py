"""FastAPI application factory — infra vertical slice (health + CORS + request IDs)."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import health_router
from app.core.request_id import RequestIdMiddleware
from app.core.settings import Settings, get_settings


def configure_logging(settings: Settings) -> None:
    """Basic structured-friendly logging; request_id attached via middleware extras."""
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the API app. Does not call paid AI providers on startup."""
    settings = settings or get_settings()
    configure_logging(settings)

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs" if settings.environment == "development" else None,
        redoc_url=None,
    )
    app.state.settings = settings

    origins = settings.cors_origin_list()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-CSRF-Token"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestIdMiddleware)

    app.include_router(health_router)
    return app


app = create_app()
