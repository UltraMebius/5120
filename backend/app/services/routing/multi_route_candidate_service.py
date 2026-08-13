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
    MAXIMUM_MEANINGFUL_ROUTES,
    MAXIMUM_ROUTE_DURATION_MULTIPLIER,
    MAXIMUM_WAYPOINT_ATTEMPTS,
    MINIMUM_MEANINGFUL_ROUTES,
    MINIMUM_JOURNEY_FOR_WAYPOINT_M,
    RELAXED_ROUTE_ADDITIONAL_SECONDS,
    RELAXED_ROUTE_DURATION_MULTIPLIER,
    TARGET_MEANINGFUL_ROUTES,
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

    return candidate_duration_seconds <= strict_detour_limit_seconds(
        fastest_duration_seconds
    )


def strict_detour_limit_seconds(fastest_duration_seconds: float) -> float:
    """Return the unchanged primary 1.5x practical-duration boundary."""

    return fastest_duration_seconds * MAXIMUM_ROUTE_DURATION_MULTIPLIER


def relaxed_detour_limit_seconds(fastest_duration_seconds: float) -> float:
    """Return the bounded fallback duration ceiling."""

    return min(
        fastest_duration_seconds * RELAXED_ROUTE_DURATION_MULTIPLIER,
        fastest_duration_seconds + RELAXED_ROUTE_ADDITIONAL_SECONDS,
    )


def is_within_relaxed_detour_limit(
    candidate_duration_seconds: float,
    fastest_duration_seconds: float,
) -> bool:
    """Apply the inclusive relaxed boundary used only for recovery."""

    return candidate_duration_seconds <= relaxed_detour_limit_seconds(
        fastest_duration_seconds
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
        maximum_duration_seconds: float,
    ) -> tuple[list[RouteCandidate], bool, int]:
        detour_rejected_count = sum(
            candidate.duration_seconds > maximum_duration_seconds
            for candidate in candidates
        )
        practical = sorted(
            (
                candidate
                for candidate in candidates
                if candidate.duration_seconds <= maximum_duration_seconds
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
        return retained, similarity_rejected, detour_rejected_count

    def _bounded_diverse_pool(
        self,
        candidates: Sequence[RouteCandidate],
    ) -> list[RouteCandidate]:
        remaining = sorted(candidates, key=_representative_key)
        if len(remaining) <= MAXIMUM_MEANINGFUL_ROUTES:
            return remaining
        selected = [remaining.pop(0)]
        while remaining and len(selected) < MAXIMUM_MEANINGFUL_ROUTES:
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
        strict_detour_limit = strict_detour_limit_seconds(fastest_duration)
        relaxed_detour_limit = relaxed_detour_limit_seconds(fastest_duration)

        distinctness_started = perf_counter()
        retained, similarity_rejected, rejected_strict_detour_count = (
            self._deduplicate_and_filter(
                initial_candidates,
                maximum_duration_seconds=strict_detour_limit,
            )
        )
        strict_candidate_count = len(retained)
        rejected_relaxed_detour_count = sum(
            candidate.duration_seconds > relaxed_detour_limit
            for candidate in initial_candidates
        )
        relaxed_fallback_activated = (
            len(retained) < MINIMUM_MEANINGFUL_ROUTES
        )
        relaxed_alternative_added = False

        if len(retained) < TARGET_MEANINGFUL_ROUTES:
            relaxed_initial_candidates = sorted(
                (
                    candidate
                    for candidate in initial_candidates
                    if strict_detour_limit
                    < candidate.duration_seconds
                    <= relaxed_detour_limit
                ),
                key=_representative_key,
            )
            for candidate in relaxed_initial_candidates:
                if len(retained) >= TARGET_MEANINGFUL_ROUTES:
                    break
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
                relaxed_fallback_activated = True
                relaxed_alternative_added = True

        candidate_distinctness_ms = (
            perf_counter() - distinctness_started
        ) * 1000.0

        waypoint_selection_ms = 0.0
        waypoint_mapbox_ms = 0.0
        third_route_attempted = False
        attempted_waypoint_ids: set[int] = set()
        reason = (
            CandidateGenerationReason.RELAXED_DETOUR_ALTERNATIVE_ADDED
            if relaxed_alternative_added
            else CandidateGenerationReason.MULTIPLE_MAPBOX_ROUTES
        )
        if len(retained) < TARGET_MEANINGFUL_ROUTES:
            journey_distance = haversine_distance_meters(origin, destination)
            if journey_distance < MINIMUM_JOURNEY_FOR_WAYPOINT_M:
                reason = CandidateGenerationReason.JOURNEY_TOO_SHORT
            else:
                waypoint_selection_started = perf_counter()
                available_request_budget = (
                    MAXIMUM_MAPBOX_REQUESTS - mapbox_request_count
                )
                waypoint_attempt_limit = min(
                    MAXIMUM_WAYPOINT_ATTEMPTS,
                    TARGET_MEANINGFUL_ROUTES - len(retained),
                    available_request_budget,
                )
                waypoints = self.waypoint_service.select_waypoints(
                    origin=origin,
                    destination=destination,
                    direct_route_geometry=retained[0].geometry,
                    limit=waypoint_attempt_limit,
                )
                waypoint_selection_ms = (
                    perf_counter() - waypoint_selection_started
                ) * 1000.0
                if not waypoints and len(retained) < MINIMUM_MEANINGFUL_ROUTES:
                    if rejected_relaxed_detour_count > 0:
                        reason = CandidateGenerationReason.DETOUR_LIMIT_EXCEEDED
                    elif similarity_rejected:
                        reason = CandidateGenerationReason.ALTERNATIVES_TOO_SIMILAR
                    else:
                        reason = CandidateGenerationReason.NO_VALID_WAYPOINT
                waypoint_similarity_rejected = False
                waypoint_detour_rejected = False
                for attempt_index, waypoint in enumerate(waypoints):
                    if (
                        len(retained) >= TARGET_MEANINGFUL_ROUTES
                        or mapbox_request_count >= MAXIMUM_MAPBOX_REQUESTS
                    ):
                        break
                    if waypoint.location_id in attempted_waypoint_ids:
                        continue
                    attempted_waypoint_ids.add(waypoint.location_id)
                    if len(retained) >= MINIMUM_MEANINGFUL_ROUTES:
                        third_route_attempted = True
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
                        within_strict_detour = is_within_detour_limit(
                            candidate.duration_seconds,
                            fastest_duration,
                        )
                        if not within_strict_detour:
                            rejected_strict_detour_count += 1
                        if not is_within_relaxed_detour_limit(
                            candidate.duration_seconds,
                            fastest_duration,
                        ):
                            rejected_relaxed_detour_count += 1
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
                        if within_strict_detour:
                            reason = (
                                CandidateGenerationReason
                                .WAYPOINT_ALTERNATIVE_ADDED
                            )
                        else:
                            relaxed_fallback_activated = True
                            relaxed_alternative_added = True
                            reason = (
                                CandidateGenerationReason
                                .RELAXED_DETOUR_ALTERNATIVE_ADDED
                            )
                        break

                if len(retained) < MINIMUM_MEANINGFUL_ROUTES:
                    if waypoint_detour_rejected:
                        reason = CandidateGenerationReason.DETOUR_LIMIT_EXCEEDED
                    elif waypoint_similarity_rejected or similarity_rejected:
                        reason = CandidateGenerationReason.ALTERNATIVES_TOO_SIMILAR
                    elif waypoints:
                        reason = (
                            CandidateGenerationReason.ONLY_ONE_MEANINGFUL_CORRIDOR
                        )

        relaxed_candidate_count = (
            len(retained) if relaxed_fallback_activated else 0
        )
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
            strict_detour_limit_seconds=strict_detour_limit,
            relaxed_detour_limit_seconds=relaxed_detour_limit,
            strict_candidate_count=strict_candidate_count,
            relaxed_candidate_count=relaxed_candidate_count,
            rejected_strict_detour_count=rejected_strict_detour_count,
            rejected_relaxed_detour_count=rejected_relaxed_detour_count,
            relaxed_fallback_activated=relaxed_fallback_activated,
            target_route_count=TARGET_MEANINGFUL_ROUTES,
            final_route_count=len(evaluated_candidates),
            third_route_attempted=third_route_attempted,
            third_route_added=(
                len(evaluated_candidates) >= TARGET_MEANINGFUL_ROUTES
            ),
            remaining_request_budget=(
                MAXIMUM_MAPBOX_REQUESTS - mapbox_request_count
            ),
        )
        _LOGGER.info(
            "multi_route_candidates mapbox_initial_ms=%.3f "
            "candidate_distinctness_ms=%.3f waypoint_selection_ms=%.3f "
            "waypoint_mapbox_ms=%.3f sampling_ms=%.3f "
            "flow_batch_db_ms=%.3f flow_aggregation_ms=%.3f total_ms=%.3f "
            "mapbox_request_count=%d candidate_count_before_filter=%d "
            "candidate_count_after_filter=%d flow_sql_execution_count=%d "
            "strict_detour_limit_seconds=%.3f "
            "relaxed_detour_limit_seconds=%.3f strict_candidate_count=%d "
            "relaxed_candidate_count=%d rejected_strict_detour_count=%d "
            "rejected_relaxed_detour_count=%d "
            "relaxed_fallback_activated=%s target_route_count=%d "
            "final_route_count=%d third_route_attempted=%s "
            "third_route_added=%s remaining_request_budget=%d "
            "generation_reason=%s",
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
            timings.strict_detour_limit_seconds,
            timings.relaxed_detour_limit_seconds,
            timings.strict_candidate_count,
            timings.relaxed_candidate_count,
            timings.rejected_strict_detour_count,
            timings.rejected_relaxed_detour_count,
            timings.relaxed_fallback_activated,
            timings.target_route_count,
            timings.final_route_count,
            timings.third_route_attempted,
            timings.third_route_added,
            timings.remaining_request_budget,
            reason.value,
        )
        return MultiRouteCandidateResult(
            candidates=evaluated_candidates,
            reason=reason,
            timings=timings,
        )
