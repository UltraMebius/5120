from fastapi.testclient import TestClient
import pytest

from backend.app.api.routes import (
    get_route_crowd_ranking_service,
    get_walking_routing_service,
)
from backend.app.main import app
from backend.app.models.crowd import (
    CrowdLevel,
    FrontendCrowdLevel,
    RoutePreferenceStatus,
    RouteRankingStatus,
)
from backend.app.models.spatial import PointCrowdEstimate
from backend.app.schemas.routes import GeoJsonLineString, WalkingRouteOption
from backend.app.services.routing.mapbox_directions_client import (
    MapboxDirectionsConfigurationError,
    MapboxDirectionsConnectionError,
)
from backend.app.services.routing.route_crowd_evaluation_service import (
    RouteCrowdEvaluation,
    RouteSampleCrowdResult,
)
from backend.app.services.routing.route_crowd_ranking_service import (
    RankedRouteCrowdResult,
    RouteCrowdRankingResult,
    RouteCrowdSummary,
)
from backend.app.services.routing.route_sampling_service import RouteSample


VALID_REQUEST = {
    "origin": {
        "label": "Flinders Street Station",
        "longitude": 144.9671,
        "latitude": -37.8183,
    },
    "destination": {
        "label": "Melbourne Central",
        "longitude": 144.9631,
        "latitude": -37.8102,
    },
    "preference": "PREFER_QUIETER",
}


class FakeWalkingRoutingService:
    def find_routes(self, **coordinates):
        assert coordinates == {
            "origin_longitude": 144.9671,
            "origin_latitude": -37.8183,
            "destination_longitude": 144.9631,
            "destination_latitude": -37.8102,
        }
        return [
            WalkingRouteOption(
                id="mapbox-route-0",
                routeIndex=0,
                name="Walking route",
                distanceMeters=1162.4,
                durationSeconds=888.0,
                geometry=GeoJsonLineString(
                    coordinates=[
                        (144.9671, -37.8183),
                        (144.9631, -37.8102),
                    ]
                ),
                steps=[],
            )
        ]


class FailingWalkingRoutingService:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def find_routes(self, **coordinates):
        raise self.error


class TwoRouteWalkingRoutingService(FakeWalkingRoutingService):
    def find_routes(self, **coordinates):
        first = super().find_routes(**coordinates)[0]
        second = first.model_copy(
            update={
                "id": "mapbox-route-1",
                "routeIndex": 1,
                "name": "Alternative route 1",
                "durationSeconds": 900.0,
            }
        )
        return [first, second]


def _evaluation(
    route_id: str,
    entries: list[tuple[str, float | None]] | None = None,
) -> RouteCrowdEvaluation:
    controlled_entries = entries or [
        ("SUPPORTED", 10.0),
        ("SUPPORTED", 40.0),
        ("LIMITED", 45.0),
    ]
    results: list[RouteSampleCrowdResult] = []
    for index, (status, score) in enumerate(controlled_entries):
        sample = RouteSample(
            index=index,
            distance_along_route_meters=float(index * 50),
            longitude=144.9671,
            latitude=-37.8183 + index / 100_000,
        )
        has_support = status != "NO_DATA"
        results.append(
            RouteSampleCrowdResult(
                sample=sample,
                crowd=PointCrowdEstimate(
                    latitude=sample.latitude,
                    longitude=sample.longitude,
                    crowd_exposure_score=score,
                    crowd_level=None,
                    local_condition_score=None,
                    local_condition=None,
                    coverage_status=status,
                    nearby_sensors=1 if has_support else 0,
                    nearby_active_outdoor_sensors=1 if has_support else 0,
                    supporting_sensors=1 if has_support else 0,
                    nearest_sensor_distance_m=100.0 if has_support else None,
                    supporting_score_stddev=None,
                    weighting_method="inverse_distance_1_over_d",
                    updated_at=None,
                    source_window_start=None,
                    source_window_end=None,
                    support_radius_m=300.0,
                    reason=None if has_support else "NO_CURRENT_DATA",
                    contributions=(),
                ),
            )
        )
    return RouteCrowdEvaluation(
        route_id=route_id,
        route_length_meters=float((len(results) - 1) * 50),
        sampling_interval_meters=50.0,
        sample_results=tuple(results),
    )


def _summary(
    route_id: str,
    *,
    sufficient: bool = True,
) -> RouteCrowdSummary:
    return RouteCrowdSummary(
        route_id=route_id,
        supported_pct=100.0 if sufficient else 0.0,
        limited_coverage_pct=0.0,
        data_coverage_pct=100.0 if sufficient else 0.0,
        no_data_pct=0.0 if sufficient else 100.0,
        sample_interval_m=50.0,
        sample_count=25,
        numeric_sample_count=25 if sufficient else 0,
        median_crowd_exposure_score=40.0 if sufficient else None,
        p75_crowd_exposure_score=45.0 if sufficient else None,
        maximum_crowd_exposure_score=50.0 if sufficient else None,
        pct_above_preference=0.0 if sufficient else None,
        pct_very_high=0.0 if sufficient else None,
        route_crowd_level=CrowdLevel.LOW if sufficient else None,
        route_crowd_presentation_level=(
            FrontendCrowdLevel.LOW if sufficient else None
        ),
        preference_status=(
            RoutePreferenceStatus.WITHIN_PREFERENCE
            if sufficient
            else RoutePreferenceStatus.INSUFFICIENT_DATA
        ),
    )


class FakeRouteCrowdRankingService:
    def __init__(
        self,
        *,
        sufficient: bool = True,
        alert_entries: list[tuple[str, float | None]] | None = None,
    ) -> None:
        self.sufficient = sufficient
        self.alert_entries = alert_entries

    def rank_routes(self, routes, preference):
        route = routes[0]
        alert_entries = self.alert_entries
        if alert_entries is None and not self.sufficient:
            alert_entries = [("NO_DATA", None)] * 3
        return RouteCrowdRankingResult(
            routes=(
                RankedRouteCrowdResult(
                    route=route,
                    evaluation=_evaluation(route.id, alert_entries),
                    summary=_summary(route.id, sufficient=self.sufficient),
                    rank=1 if self.sufficient else None,
                    is_recommended=self.sufficient,
                ),
            ),
            recommended_route_id=route.id if self.sufficient else None,
            ranking_status=(
                RouteRankingStatus.PROVISIONAL
                if self.sufficient
                else RouteRankingStatus.INSUFFICIENT_DATA
            ),
        )


class ReverseRouteCrowdRankingService:
    def rank_routes(self, routes, preference):
        ordered = list(reversed(routes))
        return RouteCrowdRankingResult(
            routes=tuple(
                RankedRouteCrowdResult(
                    route=route,
                    evaluation=_evaluation(route.id),
                    summary=_summary(route.id),
                    rank=index,
                    is_recommended=index == 1,
                )
                for index, route in enumerate(ordered, start=1)
            ),
            recommended_route_id=ordered[0].id,
            ranking_status=RouteRankingStatus.PROVISIONAL,
        )


def test_walking_route_api_returns_normalized_real_route_contract() -> None:
    app.dependency_overrides[get_walking_routing_service] = (
        FakeWalkingRoutingService
    )
    app.dependency_overrides[get_route_crowd_ranking_service] = (
        lambda: FakeRouteCrowdRankingService()
    )
    try:
        response = TestClient(app).post(
            "/api/v1/routes/walking", json=VALID_REQUEST
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["preference"] == "PREFER_QUIETER"
    assert body["recommendedRouteId"] == "mapbox-route-0"
    assert body["rankingStatus"] == "PROVISIONAL"
    assert len(body["routes"]) == 1
    route = body["routes"][0]
    assert route["source"] == "MAPBOX"
    assert route["geometry"]["type"] == "LineString"
    assert route["routeCrowdLevel"] == "LOW"
    assert route["routeCrowdPresentationLevel"] == "LOW"
    assert route["preferenceStatus"] == "WITHIN_PREFERENCE"
    assert route["dataCoveragePct"] == 100.0
    assert route["p75CrowdExposureScore"] == 45.0
    assert route["rank"] == 1
    assert route["isRecommended"] is True
    assert route["initialCrowdAlert"] == {
        "decision": "CLEAR",
        "reason": "NO_CONSECUTIVE_ABOVE_PREFERENCE",
        "preference": "PREFER_QUIETER",
        "threshold": 75.0,
        "currentProgressMeters": 0.0,
        "lookAheadDistanceMeters": 300.0,
        "totalLookAheadSamples": 2,
        "numericLookAheadSamples": 2,
        "lookAheadCoveragePct": 100.0,
        "pctAbovePreference": 0.0,
        "triggerStartDistanceMeters": None,
        "triggerEndDistanceMeters": None,
        "triggerSampleCount": None,
        "maximumExposureInTrigger": None,
    }


def test_all_insufficient_routes_return_no_fake_recommendation() -> None:
    app.dependency_overrides[get_walking_routing_service] = (
        FakeWalkingRoutingService
    )
    app.dependency_overrides[get_route_crowd_ranking_service] = lambda: (
        FakeRouteCrowdRankingService(sufficient=False)
    )
    try:
        response = TestClient(app).post(
            "/api/v1/routes/walking", json=VALID_REQUEST
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["rankingStatus"] == "INSUFFICIENT_DATA"
    assert body["recommendedRouteId"] is None
    route = body["routes"][0]
    assert route["preferenceStatus"] == "INSUFFICIENT_DATA"
    assert route["p75CrowdExposureScore"] is None
    assert route["routeCrowdLevel"] is None
    assert route["isRecommended"] is False
    assert route["initialCrowdAlert"]["decision"] == "INSUFFICIENT_DATA"
    assert route["initialCrowdAlert"]["reason"] == (
        "NO_USABLE_LOOK_AHEAD_CROWD_DATA"
    )


@pytest.mark.parametrize(
    ("entries", "expected"),
    [
        (
            [
                ("SUPPORTED", 10.0),
                ("SUPPORTED", 80.0),
                ("LIMITED", 90.0),
            ],
            {
                "decision": "ALERT",
                "reason": "CONSECUTIVE_ABOVE_PREFERENCE_DETECTED",
                "lookAheadCoveragePct": 100.0,
                "pctAbovePreference": 100.0,
                "triggerStartDistanceMeters": 50.0,
                "triggerEndDistanceMeters": 100.0,
                "triggerSampleCount": 2,
                "maximumExposureInTrigger": 90.0,
            },
        ),
        (
            [
                ("SUPPORTED", 10.0),
                ("SUPPORTED", 80.0),
                ("SUPPORTED", 70.0),
            ],
            {
                "decision": "CLEAR",
                "reason": "NO_CONSECUTIVE_ABOVE_PREFERENCE",
                "lookAheadCoveragePct": 100.0,
                "pctAbovePreference": 50.0,
                "triggerStartDistanceMeters": None,
                "triggerEndDistanceMeters": None,
                "triggerSampleCount": None,
                "maximumExposureInTrigger": None,
            },
        ),
        (
            [("NO_DATA", None)] * 3,
            {
                "decision": "INSUFFICIENT_DATA",
                "reason": "NO_USABLE_LOOK_AHEAD_CROWD_DATA",
                "lookAheadCoveragePct": 0.0,
                "pctAbovePreference": None,
                "triggerStartDistanceMeters": None,
                "triggerEndDistanceMeters": None,
                "triggerSampleCount": None,
                "maximumExposureInTrigger": None,
            },
        ),
    ],
)
def test_initial_alert_contract_exposes_all_public_states(
    entries: list[tuple[str, float | None]],
    expected: dict[str, object],
) -> None:
    app.dependency_overrides[get_walking_routing_service] = (
        FakeWalkingRoutingService
    )
    app.dependency_overrides[get_route_crowd_ranking_service] = lambda: (
        FakeRouteCrowdRankingService(alert_entries=entries)
    )
    try:
        response = TestClient(app).post(
            "/api/v1/routes/walking", json=VALID_REQUEST
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    alert = response.json()["routes"][0]["initialCrowdAlert"]
    assert alert["preference"] == "PREFER_QUIETER"
    assert alert["threshold"] == 75.0
    assert alert["currentProgressMeters"] == 0.0
    assert alert["lookAheadDistanceMeters"] == 300.0
    assert alert["totalLookAheadSamples"] == 2
    assert alert["numericLookAheadSamples"] == (
        0 if expected["decision"] == "INSUFFICIENT_DATA" else 2
    )
    for key, value in expected.items():
        assert alert[key] == value


def test_api_preserves_backend_ranking_order_instead_of_mapbox_order() -> None:
    app.dependency_overrides[get_walking_routing_service] = (
        TwoRouteWalkingRoutingService
    )
    app.dependency_overrides[get_route_crowd_ranking_service] = (
        ReverseRouteCrowdRankingService
    )
    try:
        response = TestClient(app).post(
            "/api/v1/routes/walking", json=VALID_REQUEST
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert [route["id"] for route in body["routes"]] == [
        "mapbox-route-1",
        "mapbox-route-0",
    ]
    assert body["recommendedRouteId"] == "mapbox-route-1"


def test_openapi_exposes_all_project_owned_route_ranking_states() -> None:
    schema = app.openapi()
    ranking_schema = schema["components"]["schemas"]["RouteRankingStatus"]

    assert ranking_schema["enum"] == [
        "NOT_EVALUATED",
        "PROVISIONAL",
        "INSUFFICIENT_DATA",
        "VALIDATED",
    ]


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
def test_invalid_route_coordinate_is_rejected_before_service_call(
    field: str, coordinate: str, value: object
) -> None:
    request = {
        key: dict(location) if isinstance(location, dict) else location
        for key, location in VALID_REQUEST.items()
    }
    request[field][coordinate] = value
    app.dependency_overrides[get_walking_routing_service] = (
        FakeWalkingRoutingService
    )
    try:
        response = TestClient(app).post(
            "/api/v1/routes/walking", json=request
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (MapboxDirectionsConfigurationError("secret"), 503),
        (MapboxDirectionsConnectionError("secret"), 502),
    ],
)
def test_route_failure_is_sanitized_and_health_remains_available(
    error: Exception, expected_status: int
) -> None:
    app.dependency_overrides[get_walking_routing_service] = lambda: (
        FailingWalkingRoutingService(error)
    )
    client = TestClient(app)
    try:
        route_response = client.post(
            "/api/v1/routes/walking", json=VALID_REQUEST
        )
        health_response = client.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert route_response.status_code == expected_status
    assert "secret" not in route_response.text
    assert health_response.status_code == 200
    assert health_response.json() == {"status": "ok"}
