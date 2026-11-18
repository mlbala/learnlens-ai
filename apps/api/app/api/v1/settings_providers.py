"""Provider settings read endpoint — allowlisted names/capabilities, never secrets."""

from __future__ import annotations

from fastapi import APIRouter

from app.ai.factory import provider_settings_snapshot
from app.api.deps import CurrentAuth, SettingsDep
from app.api.v1.schemas import ProviderSettingsResponse

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


@router.get("/providers", response_model=ProviderSettingsResponse)
async def get_providers(
    _ctx: CurrentAuth,
    settings: SettingsDep,
) -> ProviderSettingsResponse:
    """Return configured provider/model names and health flags without API keys."""
    snapshot = provider_settings_snapshot(settings)
    return ProviderSettingsResponse.model_validate(snapshot)
