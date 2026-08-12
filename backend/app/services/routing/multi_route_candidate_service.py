"""Bounded multi-route generation without final product-role assignment."""

from collections.abc import Sequence
from dataclasses import replace
import logging
from time import perf_counter
from typing import Protocol

from ...schemas.routes import WalkingRouteOption
from .mapbox_directions_client import MapboxDirectionsError
from .route_candidate_config import (
    MAXIMUM_MAPBOX_REQUESTS,
    MAXIMUM_RETAINED_CANDIDATES,
    MAXIMUM_ROUTE_DURATION_MULTIPLIER,
    MAXIMUM_WAYPOINT_ATTEMPTS,
    MINIMUM_JOURNEY_FOR_WAYPOINT_M,
    TARGET_MEANINGFUL_CANDIDATE_COUNT,
)
from .route_candidate_models import (
    CandidateGenerationReason,
    CandidateGenerationTimings,
    MultiRouteCandidateResult,
    RouteCandidate,
    RouteCandidateSource,
    SelectedFlowWaypoint,
)
from .route_distinctness_service import RouteDistinctnessService
from .route_pedestrian_flow_service import (
    RoutePedestrianFlowInput,
    RoutePedestrianFlowPipelineResult,
    RoutePedestrianFlowService,
)
from .route_sampling_service import haversine_distance_meters
from .routing_service import WalkingRouteUnavailableError, WalkingRoutingService


_LOGGER = logging.getLogger(__name__)


class _WalkingRouteProvider(Protocol):
    def find_routes(
        self,
        *,
        origin_longitude: float,
        origin_latitude: float,
        destination_longitude: float,
        destination_latitude: float,
    ) -> list[WalkingRouteOption]: ...

    def find_routes_for_coordinates(
        self,
        coordinates: Sequence[tuple[float, float]],
        *,
        alternatives: bool = True,
    ) -> list[WalkingRouteOption]: ...


class _WaypointSelector(Protocol):
    def select_waypoints(
        self,
        *,
        origin: tuple[float, float],
        destination: tuple[float, float],
        direct_route_geometry: object,
        limit: int = MAXIMUM_WAYPOINT_ATTEMPTS,
    ) -> tuple[SelectedFlowWaypoint, ...]: ...


class _FlowPipeline(Protocol):
    def evaluate_routes(
        self,
        routes: Sequence[RoutePedestrianFlowInput],
    ) -> RoutePedestrianFlowPipelineResult: ...


def _representative_key(candidate: RouteCandidate) -> tuple[float, float, int]:
    return (
        candidate.duration_seconds,
        candidate.distance_meters,
        candidate.source_index,
    )


def is_within_detour_limit(
    candidate_duration_seconds: float,
    fastest_duration_seconds: float,
) -> bool:
    """Apply the inclusive 1.5x practical-duration boundary."""

    return candidate_duration_seconds <= (
        fastest_duration_seconds * MAXIMUM_ROUTE_DURATION_MULTIPLIER
    )


class MultiRouteCandidateService:
    """Build up to three meaningful real Mapbox walking candidates."""

    def __init__(
        self,
        routing_service: _WalkingRouteProvider | None = None,
        distinctness_service: RouteDistinctnessService | None = None,
        waypoint_service: _WaypointSelector | None = None,
        flow_service: _FlowPipeline | None = None,
    ) -> None:
        self.routing_service = routing_service or WalkingRoutingService()
        self.distinctness_service = (
            distinctness_service or RouteDistinctnessService()
        )
        if waypoint_service is None:
            from .flow_waypoint_selection_service import (
                FlowWaypointSelectionService,
            )

            waypoint_service = FlowWaypointSelectionService()
        self.waypoint_service = waypoint_service
        self.flow_service = flow_service or RoutePedestrianFlowService()

    @staticmethod
    def _candidate_from_route(
        route: WalkingRouteOption,
        *,
        source_index: int,
        candidate_source: RouteCandidateSource,
        route_id: str | None = None,
        waypoint: SelectedFlowWaypoint | None = None,
    ) -> RouteCandidate:
        return RouteCandidate(
            route_id=route.id if route_id is None else route_id,
            source_index=source_index,
            candidate_source=candidate_source,
            geometry=route.geometry,
            distance_meters=route.distanceMeters,
            duration_seconds=route.durationSeconds,
            steps=tuple(route.steps),
            waypoint_metadata=waypoint,
        )

    def _deduplicate_and_filter(
        self,
        candidates: Sequence[RouteCandidate],
        *,
        fastest_duration_seconds: float,
    ) -> tuple[list[RouteCandidate], bool, bool]:
        detour_rejected = any(
            not is_within_detour_limit(
                candidate.duration_seconds,
                fastest_duration_seconds,
            )
            for candidate in candidates
        )
        practical = sorted(
            (
                candidate
                for candidate in candidates
                if is_within_detour_limit(
                    candidate.duration_seconds,
                    fastest_duration_seconds,
                )
            ),
            key=_representative_key,
        )
        retained: list[RouteCandidate] = []
        similarity_rejected = False
        for candidate in practical:
            if any(
                self.distinctness_service.compare(
                    candidate.geometry,
                    existing.geometry,
                ).too_similar
                for existing in retained
            ):
                similarity_rejected = True
                continue
            retained.append(candidate)
        return retained, similarity_rejected, detour_rejected

    def _bounded_diverse_pool(
        self,
        candidates: Sequence[RouteCandidate],
    ) -> list[RouteCandidate]:
        remaining = sorted(candidates, key=_representative_key)
        if len(remaining) <= MAXIMUM_RETAINED_CANDIDATES:
            return remaining
        selected = [remaining.pop(0)]
        while remaining and len(selected) < MAXIMUM_RETAINED_CANDIDATES:
            scored: list[tuple[float, tuple[float, float, int], RouteCandidate]] = []
            for candidate in remaining:
                maximum_overlap = max(
                    max(
                        comparison.coverage_a_to_b,
                        comparison.coverage_b_to_a,
                    )
                    for comparison in (
                        self.distinctness_service.compare(
                            candidate.geometry,
                            retained.geometry,
                        )
                        for retained in selected
                    )
                )
                scored.append(
                    (maximum_overlap, _representative_key(candidate), candidate)
                )
            chosen = min(scored, key=lambda item: (item[0], item[1]))[2]
            selected.append(chosen)
            remaining.remove(chosen)
        return selected

    def _attach_flow_summaries(
        self,
        candidates: Sequence[RouteCandidate],
    ) -> tuple[tuple[RouteCandidate, ...], RoutePedestrianFlowPipelineResult]:
        evaluation = self.flow_service.evaluate_routes(
            tuple(
                RoutePedestrianFlowInput(
                    route_index=index,
                    geometry=candidate.geometry,
                    route_id=candidate.route_id,
                )
                for index, candidate in enumerate(candidates)
            )
        )
        summaries = {
            route.route_index: route.summary for route in evaluation.routes
        }
        if set(summaries) != set(range(len(candidates))):
            raise RuntimeError(
                "candidate flow evaluation did not return every route index"
            )
        return (
            tuple(
                replace(
                    candidate,
                    pedestrian_flow_summary=summaries[index],
                )
                for index, candidate in enumerate(candidates)
            ),
            evaluation,
        )

    def generate_candidates(
        self,
        *,
        origin_longitude: float,
        origin_latitude: float,
        destination_longitude: float,
        destination_latitude: float,
    ) -> MultiRouteCandidateResult:
        """Generate, validate, and flow-evaluate one bounded candidate pool."""

        total_started = perf_counter()
        origin = (origin_longitude, origin_latitude)
        destination = (destination_longitude, destination_latitude)
        mapbox_request_count = 1

        mapbox_started = perf_counter()
        initial_routes = self.routing_service.find_routes(
            origin_longitude=origin_longitude,
            origin_latitude=origin_latitude,
            destination_longitude=destination_longitude,
            destination_latitude=destination_latitude,
        )
        mapbox_initial_ms = (perf_counter() - mapbox_started) * 1000.0
        if not initial_routes:
            raise WalkingRouteUnavailableError(
                "No valid initial walking route was returned."
            )
        candidate_count_before_filter = len(initial_routes)
        initial_candidate_count = candidate_count_before_filter
        initial_candidates = tuple(
            self._candidate_from_route(
                route,
                source_index=route.routeIndex,
                candidate_source=(
                    RouteCandidateSource.DIRECT
                    if route.routeIndex == 0
                    else RouteCandidateSource.MAPBOX_ALTERNATIVE
                ),
            )
            for route in initial_routes
        )
        fastest_duration = min(
            candidate.duration_seconds for candidate in initial_candidates
        )

        distinctness_started = perf_counter()
        retained, similarity_rejected, detour_rejected = (
            self._deduplicate_and_filter(
                initial_candidates,
                fastest_duration_seconds=fastest_duration,
            )
        )
        candidate_distinctness_ms = (
            perf_counter() - distinctness_started
        ) * 1000.0

        waypoint_selection_ms = 0.0
        waypoint_mapbox_ms = 0.0
        reason = CandidateGenerationReason.MULTIPLE_MAPBOX_ROUTES
        if len(retained) < TARGET_MEANINGFUL_CANDIDATE_COUNT:
            journey_distance = haversine_distance_meters(origin, destination)
            if journey_distance < MINIMUM_JOURNEY_FOR_WAYPOINT_M:
                reason = CandidateGenerationReason.JOURNEY_TOO_SHORT
            else:
                waypoint_selection_started = perf_counter()
                waypoints = self.waypoint_service.select_waypoints(
                    origin=origin,
                    destination=destination,
                    direct_route_geometry=retained[0].geometry,
                    limit=MAXIMUM_WAYPOINT_ATTEMPTS,
                )
                waypoint_selection_ms = (
                    perf_counter() - waypoint_selection_started
                ) * 1000.0
                if not waypoints:
                    if detour_rejected:
                        reason = CandidateGenerationReason.DETOUR_LIMIT_EXCEEDED
                    elif similarity_rejected:
                        reason = CandidateGenerationReason.ALTERNATIVES_TOO_SIMILAR
                    else:
                        reason = CandidateGenerationReason.NO_VALID_WAYPOINT
                waypoint_similarity_rejected = False
                waypoint_detour_rejected = False
                for attempt_index, waypoint in enumerate(waypoints):
                    if (
                        len(retained) >= TARGET_MEANINGFUL_CANDIDATE_COUNT
                        or mapbox_request_count >= MAXIMUM_MAPBOX_REQUESTS
                    ):
                        break
                    mapbox_request_count += 1
                    waypoint_mapbox_started = perf_counter()
                    try:
                        waypoint_routes = (
                            self.routing_service.find_routes_for_coordinates(
                                (
                                    origin,
                                    (waypoint.longitude, waypoint.latitude),
                                    destination,
                                ),
                                alternatives=False,
                            )
                        )
                    except (MapboxDirectionsError, WalkingRouteUnavailableError):
                        waypoint_routes = []
                    waypoint_mapbox_ms += (
                        perf_counter() - waypoint_mapbox_started
                    ) * 1000.0

                    for raw_route in waypoint_routes:
                        candidate = self._candidate_from_route(
                            raw_route,
                            source_index=(
                                initial_candidate_count
                                + attempt_index * 10
                                + raw_route.routeIndex
                            ),
                            candidate_source=RouteCandidateSource.FLOW_WAYPOINT,
                            route_id=(
                                f"flow-waypoint-{waypoint.location_id}-"
                                f"{attempt_index}-{raw_route.routeIndex}"
                            ),
                            waypoint=waypoint,
                        )
                        candidate_count_before_filter += 1
                        if not is_within_detour_limit(
                            candidate.duration_seconds,
                            fastest_duration,
                        ):
                            waypoint_detour_rejected = True
                            continue
                        comparison_started = perf_counter()
                        too_similar = any(
                            self.distinctness_service.compare(
                                candidate.geometry,
                                existing.geometry,
                            ).too_similar
                            for existing in retained
                        )
                        candidate_distinctness_ms += (
                            perf_counter() - comparison_started
                        ) * 1000.0
                        if too_similar:
                            waypoint_similarity_rejected = True
                            continue
                        retained.append(candidate)
                        reason = CandidateGenerationReason.WAYPOINT_ALTERNATIVE_ADDED
                        break

                if len(retained) < TARGET_MEANINGFUL_CANDIDATE_COUNT:
                    if waypoint_detour_rejected:
                        reason = CandidateGenerationReason.DETOUR_LIMIT_EXCEEDED
                    elif waypoint_similarity_rejected or similarity_rejected:
                        reason = CandidateGenerationReason.ALTERNATIVES_TOO_SIMILAR
                    elif waypoints:
                        reason = (
                            CandidateGenerationReason.ONLY_ONE_MEANINGFUL_CORRIDOR
                        )
        elif detour_rejected and len(retained) == 1:
            reason = CandidateGenerationReason.DETOUR_LIMIT_EXCEEDED

        bounding_started = perf_counter()
        retained = self._bounded_diverse_pool(retained)
        candidate_distinctness_ms += (
            perf_counter() - bounding_started
        ) * 1000.0
        evaluated_candidates, flow_evaluation = self._attach_flow_summaries(
            retained
        )
        flow_timings = flow_evaluation.timings
        total_ms = (perf_counter() - total_started) * 1000.0
        timings = CandidateGenerationTimings(
            mapbox_initial_ms=mapbox_initial_ms,
            candidate_distinctness_ms=candidate_distinctness_ms,
            waypoint_selection_ms=waypoint_selection_ms,
            waypoint_mapbox_ms=waypoint_mapbox_ms,
            sampling_ms=flow_timings.sampling_ms,
            flow_batch_db_ms=flow_timings.flow_batch_db_ms,
            flow_aggregation_ms=flow_timings.flow_aggregation_ms,
            total_ms=total_ms,
            mapbox_request_count=mapbox_request_count,
            candidate_count_before_filter=candidate_count_before_filter,
            candidate_count_after_filter=len(evaluated_candidates),
            flow_sql_execution_count=flow_timings.sql_execution_count,
        )
        _LOGGER.info(
            "multi_route_candidates mapbox_initial_ms=%.3f "
            "candidate_distinctness_ms=%.3f waypoint_selection_ms=%.3f "
            "waypoint_mapbox_ms=%.3f sampling_ms=%.3f "
            "flow_batch_db_ms=%.3f flow_aggregation_ms=%.3f total_ms=%.3f "
            "mapbox_request_count=%d candidate_count_before_filter=%d "
            "candidate_count_after_filter=%d flow_sql_execution_count=%d",
            timings.mapbox_initial_ms,
            timings.candidate_distinctness_ms,
            timings.waypoint_selection_ms,
            timings.waypoint_mapbox_ms,
            timings.sampling_ms,
            timings.flow_batch_db_ms,
            timings.flow_aggregation_ms,
            timings.total_ms,
            timings.mapbox_request_count,
            timings.candidate_count_before_filter,
            timings.candidate_count_after_filter,
            timings.flow_sql_execution_count,
        )
        return MultiRouteCandidateResult(
            candidates=evaluated_candidates,
            reason=reason,
            timings=timings,
        )
