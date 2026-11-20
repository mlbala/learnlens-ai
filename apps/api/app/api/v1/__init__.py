from app.api.v1.auth import router as auth_router
from app.api.v1.chat import router as chat_router
from app.api.v1.health import router as health_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.me import router as me_router
from app.api.v1.playlists import router as playlists_router
from app.api.v1.settings_providers import router as settings_providers_router
from app.api.v1.usage import router as usage_router
from app.api.v1.videos import router as videos_router

__all__ = [
    "auth_router",
    "chat_router",
    "health_router",
    "jobs_router",
    "me_router",
    "playlists_router",
    "settings_providers_router",
    "usage_router",
    "videos_router",
]
