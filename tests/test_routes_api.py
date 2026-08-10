from fastapi.testclient import TestClient
import pytest

from backend.app.api.routes import get_walking_routing_service
from backend.app.main import app
from backend.app.schemas.routes import GeoJsonLineString, WalkingRouteOption
from backend.app.services.routing.mapbox_directions_client import (
    MapboxDirectionsConfigurationError,
    MapboxDirectionsConnectionError,
)


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


def test_walking_route_api_returns_normalized_real_route_contract() -> None:
    app.dependency_overrides[get_walking_routing_service] = (
        FakeWalkingRoutingService
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
    assert body["recommendedRouteId"] is None
    assert body["rankingStatus"] == "NOT_EVALUATED"
    assert len(body["routes"]) == 1
    route = body["routes"][0]
    assert route["source"] == "MAPBOX"
    assert route["geometry"]["type"] == "LineString"
    assert "crowdLevel" not in route
    assert "recommended" not in route


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
