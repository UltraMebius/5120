from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.app.api.crowd import get_spatial_crowd_service
from backend.app.db.exceptions import DatabaseQueryError
from backend.app.main import app
from backend.app.models.spatial import PointCrowdEstimate


class FakeSpatialService:
    def evaluate(self, *, longitude, latitude):
        return PointCrowdEstimate(
            latitude=latitude,
            longitude=longitude,
            crowd_exposure_score=82.5,
            crowd_level="HIGH",
            local_condition_score=43.0,
            local_condition="QUIETER_THAN_USUAL",
            coverage_status="SUPPORTED",
            nearby_sensors=6,
            nearby_active_outdoor_sensors=4,
            supporting_sensors=4,
            nearest_sensor_distance_m=72.0,
            supporting_score_stddev=None,
            weighting_method="inverse_distance_1_over_d",
            updated_at=datetime(2026, 8, 10, 8, 20, tzinfo=timezone.utc),
            source_window_start=datetime(2026, 8, 10, 8, 0, tzinfo=timezone.utc),
            source_window_end=datetime(2026, 8, 10, 8, 15, tzinfo=timezone.utc),
            support_radius_m=300,
            reason=None,
            contributions=(),
        )


class FailingSpatialService:
    def evaluate(self, *, longitude, latitude):
        raise DatabaseQueryError("database unavailable")


def test_exact_internal_point_api_contract() -> None:
    app.dependency_overrides[get_spatial_crowd_service] = FakeSpatialService
    try:
        response = TestClient(app).get(
            "/api/v1/crowd/point", params={"lat": -37.81, "lon": 144.96}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "latitude": -37.81,
        "longitude": 144.96,
        "crowdExposureScore": 82.5,
        "crowdLevel": "HIGH",
        "localConditionScore": 43.0,
        "localCondition": "QUIETER_THAN_USUAL",
        "coverageStatus": "SUPPORTED",
        "supportingSensors": 4,
        "nearestSensorDistanceM": 72.0,
        "supportingScoreStddev": None,
        "weightingMethod": "inverse_distance_1_over_d",
        "updatedAt": "2026-08-10T08:20:00Z",
    }


def test_invalid_api_coordinate_is_rejected_without_calling_database() -> None:
    app.dependency_overrides[get_spatial_crowd_service] = FakeSpatialService
    try:
        response = TestClient(app).get(
            "/api/v1/crowd/point", params={"lat": 91, "lon": 144.96}
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422


def test_database_failure_is_request_scoped_and_health_remains_live() -> None:
    app.dependency_overrides[get_spatial_crowd_service] = FailingSpatialService
    client = TestClient(app)
    try:
        point_response = client.get(
            "/api/v1/crowd/point", params={"lat": -37.81, "lon": 144.96}
        )
        health_response = client.get("/health")
    finally:
        app.dependency_overrides.clear()
    assert point_response.status_code == 503
    assert health_response.status_code == 200
    assert health_response.json() == {"status": "ok"}
