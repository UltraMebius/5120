"""Backend-owned Mapbox walking-route acquisition endpoint."""

from functools import lru_cache
import logging
from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException

from ..db.exceptions import CalmWayDatabaseError
from ..models.crowd import CrowdPreference
from ..schemas.route_options import (
    ComparisonPedestrianFlowResponse,
    PedestrianFlowEvidenceResponse,
    RouteOptionResponse,
    RouteOptionsRequest,
    RouteOptionsResponse,
)
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
from ..services.routing.multi_route_candidate_service import (
    MultiRouteCandidateService,
)
from ..services.routing.route_candidate_models import (
    CandidateGenerationReason,
    RouteCandidateSource,
)
from ..services.routing.route_option_selection_service import (
    RouteOptionSelectionError,
    RouteOptionSelectionResult,
    RouteOptionSelectionService,
)
from ..services.routing.routing_service import (
    WalkingRouteUnavailableError,
    WalkingRoutingService,
)


router = APIRouter(tags=["routes"])
_LOGGER = logging.getLogger(__name__)


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


@lru_cache
def get_multi_route_candidate_service() -> MultiRouteCandidateService:
    """Construct the additive candidate pipeline lazily."""

    return MultiRouteCandidateService()


@lru_cache
def get_route_option_selection_service() -> RouteOptionSelectionService:
    """Construct the pure Phase 3 product-role selector."""

    return RouteOptionSelectionService()


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


def _public_route_options(
    selection: RouteOptionSelectionResult,
) -> RouteOptionsResponse:
    routes: list[RouteOptionResponse] = []
    for selected in selection.routes:
        candidate = selected.candidate
        summary = candidate.pedestrian_flow_summary
        if summary is None:
            raise RouteOptionSelectionError(
                "route option is missing its pedestrian-flow summary"
            )
        comparison = selected.comparison_pedestrian_flow
        routes.append(
            RouteOptionResponse(
                routeId=candidate.route_id,
                routeIndex=candidate.source_index,
                candidateSource=candidate.candidate_source,
                geometry=candidate.geometry,
                distanceMeters=candidate.distance_meters,
                durationSeconds=candidate.duration_seconds,
                steps=list(candidate.steps),
                roleBadges=list(selected.role_badges),
                relativePedestrianActivity=(
                    selected.relative_pedestrian_activity
                ),
                typicalPedestrianMovementsPerMinute=(
                    comparison.typical_movements_per_minute
                ),
                comparisonPedestrianFlow=ComparisonPedestrianFlowResponse(
                    basis=comparison.basis,
                    typicalMovementsPerMinute=(
                        comparison.typical_movements_per_minute
                    ),
                    p75MovementsPerMinute=(
                        comparison.p75_movements_per_minute
                    ),
                    maximumMovementsPerMinute=(
                        comparison.maximum_movements_per_minute
                    ),
                    coveragePct=comparison.coverage_pct,
                ),
                livePedestrianFlow=PedestrianFlowEvidenceResponse(
                    medianMovementsPerMinute=(
                        summary.live_median_pedestrian_movements_per_minute
                    ),
                    p75MovementsPerMinute=(
                        summary.live_p75_pedestrian_movements_per_minute
                    ),
                    maximumMovementsPerMinute=(
                        summary.live_maximum_pedestrian_movements_per_minute
                    ),
                    coveragePct=summary.live_coverage_pct,
                ),
                historicalPedestrianFlow=PedestrianFlowEvidenceResponse(
                    medianMovementsPerMinute=(
                        summary
                        .historical_median_pedestrian_movements_per_minute
                    ),
                    p75MovementsPerMinute=(
                        summary.historical_p75_pedestrian_movements_per_minute
                    ),
                    maximumMovementsPerMinute=(
                        summary
                        .historical_maximum_pedestrian_movements_per_minute
                    ),
                    coveragePct=summary.historical_coverage_pct,
                ),
                balancedScore=selected.balanced_score,
            )
        )
    generation_reason = selection.generation_reason
    if generation_reason is (
        CandidateGenerationReason.RELAXED_DETOUR_ALTERNATIVE_ADDED
    ):
        generation_reason = (
            CandidateGenerationReason.WAYPOINT_ALTERNATIVE_ADDED
            if any(
                route.candidate.candidate_source
                is RouteCandidateSource.FLOW_WAYPOINT
                for route in selection.routes
            )
            else CandidateGenerationReason.MULTIPLE_MAPBOX_ROUTES
        )
    return RouteOptionsResponse(
        comparisonBasis=selection.comparison_basis,
        generationReason=generation_reason,
        routes=routes,
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


@router.post("/routes/options", response_model=RouteOptionsResponse)
def list_route_options(
    request: RouteOptionsRequest,
    candidate_service: MultiRouteCandidateService = Depends(
        get_multi_route_candidate_service
    ),
    selection_service: RouteOptionSelectionService = Depends(
        get_route_option_selection_service
    ),
) -> RouteOptionsResponse:
    """Generate candidates once, then assign product roles in memory."""

    request_started = perf_counter()
    try:
        candidate_generation_started = perf_counter()
        candidates = candidate_service.generate_candidates(
            origin_longitude=request.origin.longitude,
            origin_latitude=request.origin.latitude,
            destination_longitude=request.destination.longitude,
            destination_latitude=request.destination.latitude,
        )
        candidate_generation_ms = (
            perf_counter() - candidate_generation_started
        ) * 1000.0
        role_assignment_started = perf_counter()
        selection = selection_service.select_options(candidates)
        role_assignment_wall_ms = (
            perf_counter() - role_assignment_started
        ) * 1000.0
        response_construction_started = perf_counter()
        response = _public_route_options(selection)
        response_construction_ms = (
            perf_counter() - response_construction_started
        ) * 1000.0
        total_ms = (perf_counter() - request_started) * 1000.0
        timings = candidates.timings
        _LOGGER.info(
            "routes_options_timing direct_mapbox_ms=%.3f "
            "initial_filtering_ms=%.3f "
            "waypoint_selection_ms=%.3f waypoint_attempts=%d "
            "waypoint_mapbox_ms=%.3f "
            "initial_crowd_evaluation_ms=%.3f "
            "direct_crowd_evaluation_ms=%.3f "
            "waypoint_crowd_evaluation_ms=%.3f "
            "route_sampling_ms=%.3f database_ms=%.3f "
            "route_aggregation_ms=%.3f flow_evaluation_ms=%.3f "
            "final_candidate_filtering_ms=%.3f "
            "role_assignment_ms=%.3f role_assignment_wall_ms=%.3f "
            "response_construction_ms=%.3f candidate_generation_ms=%.3f "
            "total_ms=%.3f mapbox_request_count=%d "
            "flow_sql_execution_count=%d route_count=%d "
            "generation_reason=%s "
            "database_scope=shared_all_candidates "
            "framework_response_serialization_included=false",
            timings.mapbox_initial_ms,
            timings.initial_filtering_ms,
            timings.waypoint_selection_ms,
            timings.waypoint_attempt_count,
            timings.waypoint_mapbox_ms,
            timings.initial_crowd_evaluation_ms,
            timings.direct_crowd_evaluation_ms,
            timings.waypoint_crowd_evaluation_ms,
            timings.sampling_ms,
            timings.flow_batch_db_ms,
            timings.flow_aggregation_ms,
            timings.flow_evaluation_ms,
            timings.final_candidate_filtering_ms,
            selection.route_role_selection_ms,
            role_assignment_wall_ms,
            response_construction_ms,
            candidate_generation_ms,
            total_ms,
            timings.mapbox_request_count,
            timings.flow_sql_execution_count,
            len(selection.routes),
            response.generationReason.value,
        )
        return response
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
    except CalmWayDatabaseError:
        raise HTTPException(
            status_code=503,
            detail="Pedestrian-flow data is currently unavailable.",
        ) from None
    except (RouteOptionSelectionError, ValueError):
        raise HTTPException(
            status_code=500,
            detail="Unable to generate walking route options.",
        ) from None
    except RuntimeError:
        raise HTTPException(
            status_code=500,
            detail="Unable to generate walking route options.",
        ) from None
