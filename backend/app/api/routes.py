"""Backend-owned Mapbox walking-route acquisition endpoint."""

from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException

from ..schemas.routes import (
    WalkingRouteOption,
    WalkingRouteRequest,
    WalkingRoutesResponse,
)
from ..services.routing.mapbox_directions_client import (
    MapboxDirectionsConfigurationError,
    MapboxDirectionsConnectionError,
    MapboxDirectionsResponseError,
)
from ..services.routing.route_crowd_ranking_service import (
    RankedRouteCrowdResult,
    RouteCrowdRankingService,
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


@lru_cache
def get_route_crowd_ranking_service() -> RouteCrowdRankingService:
    """Construct lazily so database configuration never affects /health."""

    return RouteCrowdRankingService()


def _enriched_route(result: RankedRouteCrowdResult) -> WalkingRouteOption:
    summary = result.summary
    return result.route.model_copy(
        update={
            "routeCrowdLevel": summary.route_crowd_level,
            "routeCrowdPresentationLevel": (
                summary.route_crowd_presentation_level
            ),
            "preferenceStatus": summary.preference_status,
            "supportedPct": summary.supported_pct,
            "limitedCoveragePct": summary.limited_coverage_pct,
            "dataCoveragePct": summary.data_coverage_pct,
            "noDataPct": summary.no_data_pct,
            "medianCrowdExposureScore": (
                summary.median_crowd_exposure_score
            ),
            "p75CrowdExposureScore": summary.p75_crowd_exposure_score,
            "maximumCrowdExposureScore": (
                summary.maximum_crowd_exposure_score
            ),
            "pctAbovePreference": summary.pct_above_preference,
            "pctVeryHigh": summary.pct_very_high,
            "sampleIntervalM": summary.sample_interval_m,
            "sampleCount": summary.sample_count,
            "numericSampleCount": summary.numeric_sample_count,
            "rank": result.rank,
            "isRecommended": result.is_recommended,
        }
    )


@router.post("/routes/walking", response_model=WalkingRoutesResponse)
def list_walking_routes(
    request: WalkingRouteRequest,
    service: WalkingRoutingService = Depends(get_walking_routing_service),
    ranking_service: RouteCrowdRankingService = Depends(
        get_route_crowd_ranking_service
    ),
) -> WalkingRoutesResponse:
    """Return real Mapbox routes in backend-owned crowd-ranking order."""

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

    ranking = ranking_service.rank_routes(routes, request.preference)
    return WalkingRoutesResponse(
        preference=request.preference,
        routes=[_enriched_route(result) for result in ranking.routes],
        recommendedRouteId=ranking.recommended_route_id,
        rankingStatus=ranking.ranking_status,
    )
