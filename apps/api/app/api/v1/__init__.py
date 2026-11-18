"""API v1 routers."""

from app.api.v1.auth import router as auth_router
from app.api.v1.health import router as health_router
from app.api.v1.me import router as me_router
from app.api.v1.settings_providers import router as settings_providers_router
from app.api.v1.videos import router as videos_router

__all__ = [
    "health_router",
    "auth_router",
    "me_router",
    "videos_router",
    "settings_providers_router",
]
