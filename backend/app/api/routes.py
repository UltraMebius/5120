"""Backend-owned Mapbox walking-route acquisition endpoint."""

from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException

from ..models.crowd import CrowdPreference
from ..schemas.routes import (
    InitialCrowdAlert,
    WalkingRouteOption,
    WalkingRouteRequest,
    WalkingRoutesResponse,
)
from ..services.routing.route_crowd_alert_service import (
    RouteCrowdAlertDecision,
    RouteCrowdAlertService,
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


@lru_cache
def get_route_crowd_alert_service() -> RouteCrowdAlertService:
    """Construct the pure initial route-ahead decision service."""

    return RouteCrowdAlertService()


def _public_initial_alert(
    decision: RouteCrowdAlertDecision,
) -> InitialCrowdAlert:
    return InitialCrowdAlert(
        decision=decision.decision,
        reason=decision.reason,
        preference=decision.preference,
        threshold=decision.threshold,
        currentProgressMeters=decision.current_progress_meters,
        lookAheadDistanceMeters=decision.look_ahead_distance_meters,
        totalLookAheadSamples=decision.total_look_ahead_samples,
        numericLookAheadSamples=decision.numeric_look_ahead_samples,
        lookAheadCoveragePct=decision.look_ahead_coverage_pct,
        pctAbovePreference=decision.pct_above_preference_in_window,
        triggerStartDistanceMeters=decision.trigger_start_distance_meters,
        triggerEndDistanceMeters=decision.trigger_end_distance_meters,
        triggerSampleCount=decision.trigger_sample_count,
        maximumExposureInTrigger=decision.maximum_exposure_in_trigger,
    )


def _enriched_route(
    result: RankedRouteCrowdResult,
    *,
    alert_service: RouteCrowdAlertService,
    preference: CrowdPreference,
) -> WalkingRouteOption:
    summary = result.summary
    initial_alert = alert_service.evaluate_ahead(
        result.evaluation,
        preference,
        current_progress_meters=0.0,
    )
    return result.route.model_copy(
        update={
            "initialCrowdAlert": _public_initial_alert(initial_alert),
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
    alert_service: RouteCrowdAlertService = Depends(
        get_route_crowd_alert_service
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
        routes=[
            _enriched_route(
                result,
                alert_service=alert_service,
                preference=request.preference,
            )
            for result in ranking.routes
        ],
        recommendedRouteId=ranking.recommended_route_id,
        rankingStatus=ranking.ranking_status,
    )
