"""FastAPI application factory — health + schema/auth + security + observability."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import (
    auth_router,
    chat_router,
    health_router,
    jobs_router,
    learning_history_router,
    learning_history_settings_router,
    me_router,
    playlists_router,
    settings_providers_router,
    tutor_router,
    usage_router,
    videos_router,
)
from app.core.api_abuse import ApiAbuseMiddleware
from app.core.errors import http_exception_handler
from app.core.observability import configure_circuit_breaker, configure_structured_logging
from app.core.policies.ai_guardrails import configure_ai_guardrails
from app.core.policies.audit_policy import configure_audit_policy
from app.core.policies.usage_policy import configure_usage_policy
from app.core.quota_middleware import QuotaMiddleware
from app.core.rate_limit import configure_api_rate_limiter, configure_auth_rate_limiter
from app.core.request_id import RequestIdMiddleware
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.settings import Settings, get_settings
from app.db.session import create_engine, create_session_factory


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    configure_structured_logging(level=settings.log_level, json_logs=settings.log_json)
    configure_auth_rate_limiter(
        limit=settings.auth_rate_limit_per_minute,
        window_seconds=60.0,
    )
    configure_api_rate_limiter(
        limit=settings.api_rate_limit_per_minute,
        window_seconds=60.0,
    )
    configure_usage_policy(
        daily_chat_messages=settings.usage_daily_chat_messages,
        daily_transcript_jobs=settings.usage_daily_transcript_jobs,
        daily_media_jobs=settings.usage_daily_media_jobs,
    )
    configure_circuit_breaker(
        failure_threshold=settings.circuit_failure_threshold,
        recovery_timeout_seconds=settings.circuit_recovery_timeout_seconds,
    )
    configure_audit_policy()
    configure_ai_guardrails(
        backend=settings.ai_guardrails_backend,
        nemo_config_path=settings.ai_guardrails_nemo_config,
        hf_model_id=settings.ai_guardrails_hf_model,
        hf_threshold=settings.ai_guardrails_hf_threshold,
        block_direct_injection=settings.ai_guardrails_block_direct_injection,
    )
    engine = None
    if settings.database_url:
        engine = create_engine(settings)
        app.state.engine = engine
        app.state.session_factory = create_session_factory(engine)
    else:
        app.state.engine = None
        app.state.session_factory = None
    try:
        yield
    finally:
        if engine is not None:
            await engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the API app. Does not call paid AI providers on startup."""
    settings = settings or get_settings()
    configure_structured_logging(level=settings.log_level, json_logs=settings.log_json)

    if settings.is_production_like() and settings.session_secret in {
        "",
        "dev-only-change-me",
    }:
        msg = "SESSION_SECRET must be set to a strong value in production"
        raise RuntimeError(msg)

    # Explicitly refuse any service-key auth bypass in production-like envs.
    if settings.is_production_like() and settings.allow_test_seed:
        msg = "ALLOW_TEST_SEED cannot be enabled outside test/development"
        raise RuntimeError(msg)

    app = FastAPI(
        title=settings.app_name,
        version="0.2.0",
        docs_url="/docs" if settings.environment == "development" else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings

    origins = settings.cors_origin_list()
    # Middleware order: last added runs first on request.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Request-ID",
            "X-Trace-ID",
            "traceparent",
            "X-CSRF-Token",
            "Idempotency-Key",
        ],
        expose_headers=["X-Request-ID", "X-Trace-ID", "traceparent"],
    )
    app.add_middleware(QuotaMiddleware, settings=settings)
    app.add_middleware(ApiAbuseMiddleware, settings=settings)
    app.add_middleware(SecurityHeadersMiddleware, settings=settings)
    app.add_middleware(RequestIdMiddleware)
    app.add_exception_handler(HTTPException, http_exception_handler)

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(me_router)
    app.include_router(videos_router)
    app.include_router(learning_history_router)
    app.include_router(learning_history_settings_router)
    app.include_router(playlists_router)
    app.include_router(jobs_router)
    app.include_router(chat_router)
    app.include_router(tutor_router)
    app.include_router(settings_providers_router)
    app.include_router(usage_router)
    return app


app = create_app()
