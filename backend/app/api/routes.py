"""Backend-owned Mapbox walking-route acquisition endpoint."""

from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException

from ..schemas.routes import WalkingRouteRequest, WalkingRoutesResponse
from ..services.routing.mapbox_directions_client import (
    MapboxDirectionsConfigurationError,
    MapboxDirectionsConnectionError,
    MapboxDirectionsResponseError,
)
from ..services.routing.routing_service import (
    WalkingRouteUnavailableError,
    WalkingRoutingService,
)


router = APIRouter(tags=["routes"])


@lru_cache
def get_walking_routing_service() -> WalkingRoutingService:
    """Construct lazily so missing Mapbox config never affects /health."""

    return WalkingRoutingService()


@router.post("/routes/walking", response_model=WalkingRoutesResponse)
def list_walking_routes(
    request: WalkingRouteRequest,
    service: WalkingRoutingService = Depends(get_walking_routing_service),
) -> WalkingRoutesResponse:
    """Return normalized real Mapbox routes without crowd evaluation."""

    try:
        routes = service.find_routes(
            origin_longitude=request.origin.longitude,
            origin_latitude=request.origin.latitude,
            destination_longitude=request.destination.longitude,
            destination_latitude=request.destination.latitude,
        )
    except MapboxDirectionsConfigurationError:
        raise HTTPException(
            status_code=503,
            detail="Walking routing is not configured.",
        ) from None
    except (MapboxDirectionsConnectionError, MapboxDirectionsResponseError):
        raise HTTPException(
            status_code=502,
            detail="Walking routing service is unavailable.",
        ) from None
    except WalkingRouteUnavailableError:
        raise HTTPException(
            status_code=502,
            detail="Walking routes are currently unavailable.",
        ) from None

    return WalkingRoutesResponse(preference=request.preference, routes=routes)
