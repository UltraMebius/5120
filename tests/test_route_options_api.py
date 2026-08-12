from fastapi.testclient import TestClient
import pytest

from backend.app.api.routes import (
    get_multi_route_candidate_service,
    get_route_option_selection_service,
)
from backend.app.db.exceptions import DatabaseQueryError
from backend.app.main import app
from backend.app.models.pedestrian_flow import RoutePedestrianFlowSummary
from backend.app.schemas.routes import (
    GeoJsonLineString,
    WalkingRouteStep,
)
from backend.app.services.routing.mapbox_directions_client import (
    MapboxDirectionsConfigurationError,
    MapboxDirectionsConnectionError,
)
from backend.app.services.routing.route_candidate_models import (
    CandidateGenerationReason,
    CandidateGenerationTimings,
    MultiRouteCandidateResult,
    RouteCandidate,
    RouteCandidateSource,
)
from backend.app.services.routing.route_option_selection_service import (
    RouteOptionSelectionService,
)
from backend.app.services.routing.routing_service import (
    WalkingRouteUnavailableError,
)


VALID_REQUEST = {
    "origin": {"longitude": 144.963, "latitude": -37.813},
    "destination": {"longitude": 144.968, "latitude": -37.818},
}

TIMINGS = CandidateGenerationTimings(
    mapbox_initial_ms=1,
    candidate_distinctness_ms=2,
    waypoint_selection_ms=0,
    waypoint_mapbox_ms=0,
    sampling_ms=3,
    flow_batch_db_ms=4,
    flow_aggregation_ms=5,
    total_ms=15,
    mapbox_request_count=1,
    candidate_count_before_filter=3,
    candidate_count_after_filter=3,
    flow_sql_execution_count=1,
)


def _candidate(
    index: int,
    *,
    duration: float,
    live_coverage: float = 100,
    live_p75: float | None = None,
    historical_coverage: float = 100,
    historical_p75: float | None = None,
) -> RouteCandidate:
    live_p75 = float(20 + index) if live_p75 is None else live_p75
    historical_p75 = (
        float(30 + index) if historical_p75 is None else historical_p75
    )
    summary = RoutePedestrianFlowSummary(
        route_index=index,
        total_sample_count=10,
        live_numeric_sample_count=round(live_coverage / 10),
        historical_numeric_sample_count=round(historical_coverage / 10),
        live_coverage_pct=live_coverage,
        historical_coverage_pct=historical_coverage,
        live_median_pedestrian_movements_per_minute=(
            None if live_p75 is None else live_p75 - 2
        ),
        live_p75_pedestrian_movements_per_minute=live_p75,
        live_maximum_pedestrian_movements_per_minute=(
            None if live_p75 is None else live_p75 + 5
        ),
        historical_median_pedestrian_movements_per_minute=(
            None if historical_p75 is None else historical_p75 - 3
        ),
        historical_p75_pedestrian_movements_per_minute=historical_p75,
        historical_maximum_pedestrian_movements_per_minute=(
            None if historical_p75 is None else historical_p75 + 7
        ),
    )
    return RouteCandidate(
        route_id=f"route-{index}",
        source_index=index,
        candidate_source=(
            RouteCandidateSource.DIRECT
            if index == 0
            else RouteCandidateSource.MAPBOX_ALTERNATIVE
        ),
        geometry=GeoJsonLineString(
            coordinates=[
                (144.963, -37.813),
                (144.965 + index / 10_000, -37.815),
                (144.968, -37.818),
            ]
        ),
        distance_meters=1_100 + index * 100,
        duration_seconds=duration,
        steps=(
            WalkingRouteStep(
                instruction=f"Walk route {index}",
                distanceMeters=100 + index,
                durationSeconds=60 + index,
                maneuverLocation=(144.963, -37.813),
            ),
        ),
        pedestrian_flow_summary=summary,
    )


class FakeCandidateService:
    def __init__(self, candidates, *, reason=None):
        self.candidates = tuple(candidates)
        self.reason = reason or CandidateGenerationReason.MULTIPLE_MAPBOX_ROUTES
        self.calls = []

    def generate_candidates(self, **coordinates):
        self.calls.append(coordinates)
        return MultiRouteCandidateResult(
            candidates=self.candidates,
            reason=self.reason,
            timings=TIMINGS,
        )


class FailingCandidateService:
    def __init__(self, error):
        self.error = error

    def generate_candidates(self, **coordinates):
        raise self.error


class SpySelectionService:
    def __init__(self):
        self.delegate = RouteOptionSelectionService()
        self.calls = []

    def select_options(self, result):
        self.calls.append(result)
        return self.delegate.select_options(result)


def _post(candidates, *, reason=None):
    candidate_service = FakeCandidateService(candidates, reason=reason)
    selection_service = SpySelectionService()
    app.dependency_overrides[get_multi_route_candidate_service] = (
        lambda: candidate_service
    )
    app.dependency_overrides[get_route_option_selection_service] = (
        lambda: selection_service
    )
    try:
        response = TestClient(app).post(
            "/api/v1/routes/options",
            json=VALID_REQUEST,
        )
    finally:
        app.dependency_overrides.clear()
    return response, candidate_service, selection_service


@pytest.mark.parametrize("candidate_count", [1, 2, 3])
def test_options_api_returns_one_to_three_routes_without_preference(
    candidate_count,
) -> None:
    candidates = [
        _candidate(index, duration=600 + index * 100)
        for index in range(candidate_count)
    ]

    response, candidate_service, selection_service = _post(candidates)

    assert response.status_code == 200
    body = response.json()
    assert len(body["routes"]) == candidate_count
    assert len(candidate_service.calls) == 1
    assert candidate_service.calls[0] == {
        "origin_longitude": 144.963,
        "origin_latitude": -37.813,
        "destination_longitude": 144.968,
        "destination_latitude": -37.818,
    }
    assert len(selection_service.calls) == 1
    assert body["comparisonBasis"] == "LIVE"
    assert "preference" not in body


def test_options_api_preserves_route_and_source_separated_flow_contract() -> None:
    response, _, _ = _post(
        [_candidate(0, duration=600, live_p75=20, historical_p75=30)],
        reason=CandidateGenerationReason.WAYPOINT_ALTERNATIVE_ADDED,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["generationReason"] == "WAYPOINT_ALTERNATIVE_ADDED"
    route = body["routes"][0]
    assert route["routeId"] == "route-0"
    assert route["routeIndex"] == 0
    assert route["candidateSource"] == "DIRECT"
    assert route["geometry"]["coordinates"] == [
        [144.963, -37.813],
        [144.965, -37.815],
        [144.968, -37.818],
    ]
    assert route["distanceMeters"] == 1_100
    assert route["durationSeconds"] == 600
    assert route["steps"] == [
        {
            "instruction": "Walk route 0",
            "distanceMeters": 100.0,
            "durationSeconds": 60.0,
            "maneuverLocation": [144.963, -37.813],
        }
    ]
    assert route["roleBadges"] == ["FASTEST"]
    assert route["comparisonPedestrianFlow"] == {
        "basis": "LIVE",
        "typicalMovementsPerMinute": 18.0,
        "p75MovementsPerMinute": 20.0,
        "maximumMovementsPerMinute": 25.0,
        "coveragePct": 100.0,
    }
    assert route["typicalPedestrianMovementsPerMinute"] == 18.0
    assert route["livePedestrianFlow"]["p75MovementsPerMinute"] == 20.0
    assert route["historicalPedestrianFlow"]["p75MovementsPerMinute"] == 30.0


def test_options_api_serializes_historical_common_basis() -> None:
    response, _, _ = _post(
        [
            _candidate(0, duration=600, live_coverage=20),
            _candidate(1, duration=700, live_coverage=20),
        ]
    )

    assert response.status_code == 200
    body = response.json()
    assert body["comparisonBasis"] == "HISTORICAL_ESTIMATE"
    assert all(
        route["comparisonPedestrianFlow"]["basis"]
        == "HISTORICAL_ESTIMATE"
        for route in body["routes"]
    )


def test_options_api_serializes_role_and_response_priority_order() -> None:
    response, _, _ = _post(
        [
            _candidate(0, duration=600, live_p75=60),
            _candidate(1, duration=780, live_p75=35),
            _candidate(2, duration=1_020, live_p75=15),
        ]
    )

    assert response.status_code == 200
    routes = response.json()["routes"]
    assert [route["routeId"] for route in routes] == [
        "route-2",
        "route-0",
        "route-1",
    ]
    assert [route["roleBadges"] for route in routes] == [
        ["CALMEST"],
        ["FASTEST"],
        ["BALANCED"],
    ]
    assert routes[2]["balancedScore"] == pytest.approx(
        0.5 * (180 / 420) + 0.5 * (20 / 45)
    )


def test_options_api_serializes_unknown_basis_with_nullable_selected_metrics() -> None:
    response, _, _ = _post(
        [
            _candidate(
                0,
                duration=600,
                live_coverage=80,
                historical_coverage=20,
            ),
            _candidate(
                1,
                duration=700,
                live_coverage=20,
                historical_coverage=80,
            ),
        ]
    )

    assert response.status_code == 200
    body = response.json()
    assert body["comparisonBasis"] == "UNKNOWN"
    assert body["routes"][0]["roleBadges"] == ["FASTEST"]
    for route in body["routes"]:
        assert route["relativePedestrianActivity"] == "UNKNOWN"
        assert route["typicalPedestrianMovementsPerMinute"] is None
        assert route["comparisonPedestrianFlow"] == {
            "basis": "UNKNOWN",
            "typicalMovementsPerMinute": None,
            "p75MovementsPerMinute": None,
            "maximumMovementsPerMinute": None,
            "coveragePct": None,
        }


def test_options_request_schema_contains_only_origin_and_destination() -> None:
    schema = app.openapi()["components"]["schemas"]["RouteOptionsRequest"]

    assert set(schema["properties"]) == {"origin", "destination"}
    assert set(schema["required"]) == {"origin", "destination"}


@pytest.mark.parametrize(
    ("field", "coordinate", "value"),
    [
        ("origin", "longitude", 181),
        ("origin", "latitude", -91),
        ("destination", "longitude", -181),
        ("destination", "latitude", 91),
        ("origin", "longitude", "NaN"),
    ],
)
def test_options_api_rejects_invalid_coordinates_before_generation(
    field,
    coordinate,
    value,
) -> None:
    request = {key: dict(location) for key, location in VALID_REQUEST.items()}
    request[field][coordinate] = value
    candidate_service = FakeCandidateService([_candidate(0, duration=600)])
    app.dependency_overrides[get_multi_route_candidate_service] = (
        lambda: candidate_service
    )
    try:
        response = TestClient(app).post(
            "/api/v1/routes/options",
            json=request,
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert candidate_service.calls == []


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_detail"),
    [
        (
            MapboxDirectionsConfigurationError("private token"),
            503,
            "Walking routing is not configured.",
        ),
        (
            MapboxDirectionsConnectionError("private upstream"),
            502,
            "Walking routing service is unavailable.",
        ),
        (
            WalkingRouteUnavailableError("private route"),
            502,
            "Walking routes are currently unavailable.",
        ),
        (
            DatabaseQueryError("private database URL"),
            503,
            "Pedestrian-flow data is currently unavailable.",
        ),
        (
            RuntimeError("private candidate detail"),
            500,
            "Unable to generate walking route options.",
        ),
    ],
)
def test_options_api_sanitizes_candidate_generation_failures(
    error,
    expected_status,
    expected_detail,
) -> None:
    app.dependency_overrides[get_multi_route_candidate_service] = lambda: (
        FailingCandidateService(error)
    )
    try:
        response = TestClient(app).post(
            "/api/v1/routes/options",
            json=VALID_REQUEST,
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}
    assert "private" not in response.text
