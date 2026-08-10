from fastapi import APIRouter

from ..models.crowd import CrowdPreference
from ..schemas.routes import RouteOption
from ..services.routing import get_preview_routes

router = APIRouter(tags=["routes"])


@router.get("/routes", response_model=list[RouteOption])
def list_routes(
    origin: str | None = None,
    destination: str | None = None,
    preference: CrowdPreference = CrowdPreference.PREFER_QUIETER,
) -> list[RouteOption]:
    """Compatibility endpoint returning explicit Phase 1 preview routes."""
    # Inputs reserve the UI flow. No Mapbox or crowd evaluation occurs in Phase 1.
    _ = (origin, destination)
    return get_preview_routes(preference)
