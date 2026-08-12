import pytest

from backend.app.models.pedestrian_flow import (
    PedestrianFlowPipelineTimings,
    RoutePedestrianFlowSummary,
)
from backend.app.schemas.routes import GeoJsonLineString, WalkingRouteOption
from backend.app.services.routing.multi_route_candidate_service import (
    MultiRouteCandidateService,
    is_within_detour_limit,
)
from backend.app.services.routing.route_candidate_models import (
    CandidateGenerationReason,
    RouteCandidateSource,
    SelectedFlowWaypoint,
    WaypointFlowSource,
)
from backend.app.services.routing.route_pedestrian_flow_service import (
    RoutePedestrianFlowEvaluation,
    RoutePedestrianFlowPipelineResult,
)


DIRECT_COORDINATES = [(144.96, -37.82), (144.96, -37.81)]
EAST_COORDINATES = [
    (144.96, -37.82),
    (144.9612, -37.818),
    (144.9612, -37.812),
    (144.96, -37.81),
]
WEST_COORDINATES = [
    (144.96, -37.82),
    (144.9588, -37.818),
    (144.9588, -37.812),
    (144.96, -37.81),
]
FAR_EAST_COORDINATES = [
    (144.96, -37.82),
    (144.9624, -37.818),
    (144.9624, -37.812),
    (144.96, -37.81),
]


def _route(
    index: int,
    coordinates,
    *,
    duration: float = 600,
    distance: float = 1000,
) -> WalkingRouteOption:
    return WalkingRouteOption(
        id=f"mapbox-route-{index}",
        routeIndex=index,
        name=f"Route {index}",
        distanceMeters=distance,
        durationSeconds=duration,
        geometry=GeoJsonLineString(coordinates=coordinates),
    )


class FakeRoutingService:
    def __init__(self, initial, waypoint_responses=()):
        self.initial = list(initial)
        self.waypoint_responses = [list(rows) for rows in waypoint_responses]
        self.initial_calls = []
        self.waypoint_calls = []

    def find_routes(self, **coordinates):
        self.initial_calls.append(coordinates)
        return self.initial

    def find_routes_for_coordinates(self, coordinates, *, alternatives=True):
        self.waypoint_calls.append((tuple(coordinates), alternatives))
        return self.waypoint_responses.pop(0)


class FakeWaypointService:
    def __init__(self, waypoints=()):
        self.waypoints = tuple(waypoints)
        self.calls = []

    def select_waypoints(self, **kwargs):
        self.calls.append(kwargs)
        return self.waypoints[: kwargs["limit"]]


class FakeFlowService:
    def __init__(self, *, sql_count=1):
        self.calls = []
        self.sql_count = sql_count

    def evaluate_routes(self, routes):
        requested = tuple(routes)
        self.calls.append(requested)
        evaluations = []
        for route in requested:
            summary = RoutePedestrianFlowSummary(
                route_index=route.route_index,
                total_sample_count=2,
                live_numeric_sample_count=2,
                historical_numeric_sample_count=2,
                live_coverage_pct=100,
                historical_coverage_pct=100,
                live_median_pedestrian_movements_per_minute=(
                    10.0 + route.route_index
                ),
                live_p75_pedestrian_movements_per_minute=(
                    11.0 + route.route_index
                ),
                live_maximum_pedestrian_movements_per_minute=(
                    12.0 + route.route_index
                ),
                historical_median_pedestrian_movements_per_minute=20.0,
                historical_p75_pedestrian_movements_per_minute=21.0,
                historical_maximum_pedestrian_movements_per_minute=22.0,
            )
            evaluations.append(
                RoutePedestrianFlowEvaluation(
                    route_index=route.route_index,
                    route_id=route.route_id,
                    route_length_meters=1000,
                    sampling_interval_meters=50,
                    samples=(),
                    summary=summary,
                )
            )
        return RoutePedestrianFlowPipelineResult(
            routes=tuple(evaluations),
            timings=PedestrianFlowPipelineTimings(
                sampling_ms=1.0,
                flow_batch_db_ms=2.0,
                flow_aggregation_ms=3.0,
                sql_execution_count=self.sql_count,
            ),
        )


def _waypoint(
    location_id: int,
    *,
    source: WaypointFlowSource = WaypointFlowSource.LIVE,
) -> SelectedFlowWaypoint:
    return SelectedFlowWaypoint(
        location_id=location_id,
        longitude=144.961,
        latitude=-37.815,
        flow_source=source,
        pedestrian_movements_per_minute=5,
        estimated_geometric_detour_meters=100,
        distance_from_direct_route_meters=100,
    )


def _generate(initial, *, waypoints=(), waypoint_responses=(), destination_lat=-37.81):
    routing = FakeRoutingService(initial, waypoint_responses)
    waypoint_service = FakeWaypointService(waypoints)
    flow = FakeFlowService()
    result = MultiRouteCandidateService(
        routing_service=routing,
        waypoint_service=waypoint_service,
        flow_service=flow,
    ).generate_candidates(
        origin_longitude=144.96,
        origin_latitude=-37.82,
        destination_longitude=144.96,
        destination_latitude=destination_lat,
    )
    return result, routing, waypoint_service, flow


def test_one_initial_route_is_retained_when_no_waypoint_exists() -> None:
    result, routing, waypoint_service, flow = _generate(
        [_route(0, DIRECT_COORDINATES)]
    )

    assert len(result.candidates) == 1
    assert result.reason is CandidateGenerationReason.NO_VALID_WAYPOINT
    assert len(routing.initial_calls) == 1
    assert routing.waypoint_calls == []
    assert len(waypoint_service.calls) == 1
    assert len(flow.calls) == 1
    assert result.timings.mapbox_request_count == 1


@pytest.mark.parametrize(
    "routes",
    [
        [
            _route(0, DIRECT_COORDINATES),
            _route(1, EAST_COORDINATES, duration=700),
        ],
        [
            _route(0, DIRECT_COORDINATES),
            _route(1, EAST_COORDINATES, duration=700),
            _route(2, WEST_COORDINATES, duration=750),
        ],
    ],
)
def test_two_or_three_distinct_initial_routes_need_only_one_mapbox_call(routes) -> None:
    result, routing, waypoint_service, flow = _generate(routes)

    assert len(result.candidates) == len(routes)
    assert result.reason is CandidateGenerationReason.MULTIPLE_MAPBOX_ROUTES
    assert routing.waypoint_calls == []
    assert waypoint_service.calls == []
    assert result.timings.mapbox_request_count == 1
    assert len(flow.calls) == 1
    assert len(flow.calls[0]) == len(routes)
    assert result.timings.flow_sql_execution_count == 1


def test_duplicate_routes_use_duration_distance_and_source_ties() -> None:
    routes = [
        _route(0, DIRECT_COORDINATES, duration=600, distance=1000),
        _route(1, DIRECT_COORDINATES, duration=550, distance=1100),
        _route(2, DIRECT_COORDINATES, duration=550, distance=900),
    ]
    result, _, _, _ = _generate(routes)

    assert len(result.candidates) == 1
    assert result.candidates[0].source_index == 2
    assert result.candidates[0].duration_seconds == 550
    assert result.candidates[0].distance_meters == 900
    assert result.reason is CandidateGenerationReason.ALTERNATIVES_TOO_SIMILAR


def test_duplicate_final_tie_keeps_lower_original_source_index() -> None:
    result, _, _, _ = _generate(
        [
            _route(0, DIRECT_COORDINATES, duration=600, distance=1000),
            _route(1, DIRECT_COORDINATES, duration=600, distance=1000),
        ]
    )

    assert len(result.candidates) == 1
    assert result.candidates[0].source_index == 0


def test_nearly_identical_routes_are_deduplicated() -> None:
    variation = [(144.9601, -37.82), (144.9601, -37.81)]
    result, _, _, _ = _generate(
        [
            _route(0, DIRECT_COORDINATES),
            _route(1, variation, duration=650),
        ]
    )

    assert len(result.candidates) == 1


@pytest.mark.parametrize(
    ("duration", "allowed"),
    [(850, True), (900, True), (901, False)],
)
def test_detour_limit_is_inclusive_at_one_point_five_times(duration, allowed) -> None:
    assert is_within_detour_limit(duration, 600) is allowed


def test_first_waypoint_success_adds_distinct_candidate_with_two_calls() -> None:
    result, routing, _, flow = _generate(
        [_route(0, DIRECT_COORDINATES)],
        waypoints=[_waypoint(10), _waypoint(20)],
        waypoint_responses=[[_route(0, EAST_COORDINATES, duration=700)]],
    )

    assert len(result.candidates) == 2
    assert result.reason is CandidateGenerationReason.WAYPOINT_ALTERNATIVE_ADDED
    assert result.timings.mapbox_request_count == 2
    assert len(routing.waypoint_calls) == 1
    assert routing.waypoint_calls[0][1] is False
    assert result.candidates[1].candidate_source is RouteCandidateSource.FLOW_WAYPOINT
    assert result.candidates[1].waypoint_metadata.location_id == 10
    assert len(flow.calls) == 1
    assert [route.route_index for route in flow.calls[0]] == [0, 1]
    assert result.timings.candidate_count_before_filter == 2
    assert result.timings.candidate_count_after_filter == 2
    assert result.timings.sampling_ms == 1.0
    assert result.timings.flow_batch_db_ms == 2.0
    assert result.timings.flow_aggregation_ms == 3.0
    assert result.timings.total_ms >= 0.0


def test_initial_alternative_above_detour_limit_is_rejected() -> None:
    result, routing, _, _ = _generate(
        [
            _route(0, DIRECT_COORDINATES, duration=600),
            _route(1, EAST_COORDINATES, duration=901),
        ]
    )

    assert len(result.candidates) == 1
    assert result.reason is CandidateGenerationReason.DETOUR_LIMIT_EXCEEDED
    assert result.timings.mapbox_request_count == 1
    assert routing.waypoint_calls == []


def test_similar_first_waypoint_is_rejected_then_second_is_attempted() -> None:
    result, routing, _, _ = _generate(
        [_route(0, DIRECT_COORDINATES)],
        waypoints=[_waypoint(10), _waypoint(20)],
        waypoint_responses=[
            [_route(0, DIRECT_COORDINATES, duration=650)],
            [_route(0, EAST_COORDINATES, duration=700)],
        ],
    )

    assert len(result.candidates) == 2
    assert result.candidates[1].waypoint_metadata.location_id == 20
    assert result.timings.mapbox_request_count == 3
    assert len(routing.waypoint_calls) == 2


def test_excessive_first_waypoint_is_rejected_then_second_is_attempted() -> None:
    result, routing, _, _ = _generate(
        [_route(0, DIRECT_COORDINATES)],
        waypoints=[_waypoint(10), _waypoint(20)],
        waypoint_responses=[
            [_route(0, EAST_COORDINATES, duration=901)],
            [_route(0, WEST_COORDINATES, duration=850)],
        ],
    )

    assert len(result.candidates) == 2
    assert result.candidates[1].duration_seconds == 850
    assert result.timings.mapbox_request_count == 3
    assert len(routing.waypoint_calls) == 2


def test_historical_waypoint_provenance_is_preserved() -> None:
    result, _, _, _ = _generate(
        [_route(0, DIRECT_COORDINATES)],
        waypoints=[
            _waypoint(10, source=WaypointFlowSource.HISTORICAL_ESTIMATE)
        ],
        waypoint_responses=[[_route(0, EAST_COORDINATES, duration=700)]],
    )

    assert (
        result.candidates[1].waypoint_metadata.flow_source
        is WaypointFlowSource.HISTORICAL_ESTIMATE
    )


def test_too_short_journey_skips_waypoint_selection() -> None:
    short_coordinates = [(144.96, -37.82), (144.96, -37.819)]
    result, routing, waypoint_service, _ = _generate(
        [_route(0, short_coordinates, distance=111)],
        waypoints=[_waypoint(10)],
        destination_lat=-37.819,
    )

    assert result.reason is CandidateGenerationReason.JOURNEY_TOO_SHORT
    assert len(result.candidates) == 1
    assert waypoint_service.calls == []
    assert routing.waypoint_calls == []


def test_mapbox_call_count_never_exceeds_three_when_both_attempts_fail() -> None:
    result, routing, _, _ = _generate(
        [_route(0, DIRECT_COORDINATES)],
        waypoints=[_waypoint(10), _waypoint(20)],
        waypoint_responses=[
            [_route(0, DIRECT_COORDINATES)],
            [_route(0, DIRECT_COORDINATES)],
        ],
    )

    assert len(result.candidates) == 1
    assert result.reason is CandidateGenerationReason.ALTERNATIVES_TOO_SIMILAR
    assert result.timings.mapbox_request_count == 3
    assert len(routing.waypoint_calls) == 2


@pytest.mark.parametrize(
    "routes",
    [
        [_route(0, DIRECT_COORDINATES)],
        [
            _route(0, DIRECT_COORDINATES),
            _route(1, EAST_COORDINATES, duration=700),
        ],
        [
            _route(0, DIRECT_COORDINATES),
            _route(1, EAST_COORDINATES, duration=700),
            _route(2, WEST_COORDINATES, duration=750),
        ],
    ],
)
def test_all_retained_routes_share_one_phase_one_flow_call(routes) -> None:
    result, _, _, flow = _generate(routes)

    assert len(flow.calls) == 1
    assert len(flow.calls[0]) == len(result.candidates)
    assert [row.route_index for row in flow.calls[0]] == list(
        range(len(result.candidates))
    )
    assert result.timings.flow_sql_execution_count == 1
    assert all(
        candidate.pedestrian_flow_summary is not None
        for candidate in result.candidates
    )


def test_pool_larger_than_three_is_reduced_deterministically_without_roles() -> None:
    routes = [
        _route(0, DIRECT_COORDINATES, duration=600),
        _route(1, EAST_COORDINATES, duration=650),
        _route(2, WEST_COORDINATES, duration=700),
        _route(3, FAR_EAST_COORDINATES, duration=750),
    ]
    result, _, _, _ = _generate(routes)

    assert len(result.candidates) <= 3
    assert not hasattr(result.candidates[0], "rank")
    assert not hasattr(result.candidates[0], "role")
