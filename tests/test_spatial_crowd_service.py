import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from backend.app.models.spatial import (
    SpatialCurrentSnapshot,
    SpatialNeighbourhood,
    SpatialSensorCandidate,
)
from backend.app.services.crowd.spatial_crowd_service import (
    CoordinateValidationError,
    SpatialCrowdService,
    SpatialDataConsistencyError,
    coverage_for_distance,
    inverse_distance_weights,
    validate_coordinates,
    weighted_point_score,
)


ROOT = Path(__file__).parents[1]
POINT_FIXTURE = (
    ROOT
    / "handoff"
    / "epic1_backend_handoff_v3"
    / "fixtures"
    / "point_response_examples.json"
)
V1B_300 = (
    ROOT
    / "handoff"
    / "epic1_backend_handoff_v3"
    / "evidence"
    / "V1B_network_target_300m_weighting.csv"
)
V1_OLD = (
    ROOT
    / "handoff"
    / "epic1_backend_handoff_v3"
    / "evidence"
    / "V1_spatial_weighting_comparison.csv"
)
WINDOW_START = datetime(2026, 8, 10, 8, 0, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 8, 10, 8, 15, tzinfo=timezone.utc)
UPDATED_AT = datetime(2026, 8, 10, 8, 20, tzinfo=timezone.utc)


class FakeRepository:
    def __init__(self, neighbourhood):
        self.neighbourhood = neighbourhood
        self.calls = []

    def find_neighbourhood(self, **kwargs):
        self.calls.append(kwargs)
        return self.neighbourhood


def _candidate(
    location_id: int,
    distance_m: float,
    crowd: float | None,
    *,
    local: float | None = None,
    data_state: str = "OK",
    location_type: str = "Outdoor",
    status: str = "A",
) -> SpatialSensorCandidate:
    return SpatialSensorCandidate(
        location_id=location_id,
        location_type=location_type,
        status=status,
        data_state=data_state,
        distance_m=distance_m,
        current_15m_network_percentile=crowd,
        current_1h_local_historical_percentile=local,
        source_window_start=WINDOW_START,
        source_window_end=WINDOW_END,
        calculated_at=UPDATED_AT,
    )


def _neighbourhood(candidates=(), nearest=None, variants=1):
    return SpatialNeighbourhood(
        candidates=tuple(candidates),
        nearest_valid_sensor_distance_m=nearest,
        snapshot=SpatialCurrentSnapshot(
            source_window_start=WINDOW_START,
            source_window_end=WINDOW_END,
            updated_at=UPDATED_AT,
            window_variant_count=variants,
        ),
    )


@pytest.mark.parametrize(
    ("longitude", "latitude"),
    [
        (181.0, 0.0),
        (-181.0, 0.0),
        (0.0, 91.0),
        (0.0, -91.0),
        (float("nan"), 0.0),
        (0.0, float("inf")),
    ],
)
def test_coordinate_validation_rejects_invalid_wgs84_values(
    longitude: float, latitude: float
) -> None:
    with pytest.raises(CoordinateValidationError):
        validate_coordinates(longitude=longitude, latitude=latitude)


def test_global_coordinate_boundaries_are_allowed_without_invented_cbd_box() -> None:
    validate_coordinates(longitude=-180.0, latitude=-90.0)
    validate_coordinates(longitude=180.0, latitude=90.0)


def test_inverse_distance_power_floor_and_normalisation() -> None:
    weights = inverse_distance_weights(
        [50.0, 100.0, 200.0, 300.0], power=1, distance_floor_m=1.0
    )
    assert weights[0] > weights[1] > weights[2] > weights[3]
    assert sum(weights) == pytest.approx(1.0)

    power_two = inverse_distance_weights(
        [1.0, 2.0], power=2, distance_floor_m=1.0
    )
    assert power_two == pytest.approx((0.8, 0.2))
    assert weighted_point_score(
        [20.0, 80.0], [0.0, 100.0], power=1, distance_floor_m=1.0
    ) == pytest.approx((20.0 + 0.8) / 1.01)


@pytest.mark.parametrize(
    ("distance", "expected"),
    [
        (250.000, "SUPPORTED"),
        (250.001, "LIMITED"),
        (300.000, "LIMITED"),
        (300.001, "NO_DATA"),
        (None, "NO_DATA"),
    ],
)
def test_authoritative_coverage_boundaries(distance, expected) -> None:
    assert coverage_for_distance(
        distance, core_radius_m=250, maximum_radius_m=300
    ) == expected


def test_supported_point_uses_only_ok_active_outdoor_numeric_scores() -> None:
    candidates = [
        _candidate(1, 50, 20, local=10),
        _candidate(2, 100, 80),
        _candidate(3, 1, None, data_state="AMBIGUOUS_NO_RECORD"),
        _candidate(4, 0, 100, location_type="Indoor"),
        _candidate(5, 0, 100, status="I"),
        _candidate(6, 301, 100),
    ]
    repository = FakeRepository(_neighbourhood(candidates, nearest=50))
    result = SpatialCrowdService(repository).evaluate(
        longitude=144.96, latitude=-37.81
    )

    assert repository.calls == [
        {"longitude": 144.96, "latitude": -37.81, "maximum_radius_m": 300.0}
    ]
    assert result.coverage_status == "SUPPORTED"
    assert result.supporting_sensors == 2
    assert result.crowd_exposure_score == pytest.approx(40.0)
    assert result.crowd_level == "LOW"
    assert result.local_condition_score == 10.0
    assert result.local_condition == "MUCH_QUIETER_THAN_USUAL"
    assert [row.location_id for row in result.contributions] == [1, 2]
    assert sum(row.normalised_weight for row in result.contributions) == pytest.approx(
        1.0
    )


def test_ambiguous_and_no_data_nearby_sensors_never_become_zero_or_low() -> None:
    candidates = [
        _candidate(1, 10, None, data_state="AMBIGUOUS_NO_RECORD"),
        _candidate(2, 20, None, data_state="NO_DATA"),
    ]
    result = SpatialCrowdService(
        FakeRepository(_neighbourhood(candidates, nearest=None))
    ).evaluate(longitude=144.96, latitude=-37.81)

    assert result.coverage_status == "NO_DATA"
    assert result.crowd_exposure_score is None
    assert result.crowd_level is None
    assert result.supporting_sensors == 0
    assert result.reason == "NO_VALID_CURRENT_SCORE_WITHIN_MAX_RADIUS"


def test_indoor_only_point_has_no_current_outdoor_support() -> None:
    result = SpatialCrowdService(
        FakeRepository(
            _neighbourhood(
                [_candidate(1, 0, 80, location_type="Indoor")], nearest=342
            )
        )
    ).evaluate(longitude=144.96, latitude=-37.81)
    assert result.coverage_status == "NO_DATA"
    assert result.crowd_exposure_score is None
    assert result.reason == "NEAREST_VALID_SENSOR_BEYOND_MAX_RADIUS"


def test_same_neighbourhood_evaluates_deterministically() -> None:
    repository = FakeRepository(
        _neighbourhood([_candidate(1, 0, 70), _candidate(2, 100, 10)], nearest=0)
    )
    service = SpatialCrowdService(repository)
    first = service.evaluate(longitude=144.96, latitude=-37.81)
    second = service.evaluate(longitude=144.96, latitude=-37.81)
    assert first == second
    assert first.crowd_exposure_score is not None
    assert first.crowd_exposure_score == pytest.approx((70 + 0.1) / 1.01)


def test_multiple_materialised_windows_are_rejected_instead_of_mixed() -> None:
    service = SpatialCrowdService(
        FakeRepository(_neighbourhood([_candidate(1, 10, 50)], variants=2))
    )
    with pytest.raises(SpatialDataConsistencyError, match="multiple current windows"):
        service.evaluate(longitude=144.96, latitude=-37.81)


def test_authoritative_point_response_fixture_semantics() -> None:
    fixture = json.loads(POINT_FIXTURE.read_text(encoding="utf-8"))
    service = SpatialCrowdService()

    supported = service.evaluate_neighbourhood(
        longitude=144.96,
        latitude=-37.81,
        neighbourhood=_neighbourhood(
            [
                _candidate(index, distance, 82.5, local=43.0)
                for index, distance in enumerate((72, 100, 180, 250), start=1)
            ],
            nearest=72,
        ),
    )
    assert supported.crowd_exposure_score == fixture["supported"][
        "crowdExposureScore"
    ]
    assert supported.crowd_level == fixture["supported"]["crowdLevel"]
    assert supported.local_condition_score == fixture["supported"][
        "localConditionScore"
    ]
    assert supported.local_condition == fixture["supported"]["localCondition"]
    assert supported.coverage_status == fixture["supported"]["coverageStatus"]
    assert supported.supporting_sensors == fixture["supported"]["supportingSensors"]
    assert supported.nearest_sensor_distance_m == fixture["supported"][
        "nearestSensorDistanceM"
    ]
    assert supported.weighting_method == fixture["supported"]["weightingMethod"]

    limited = service.evaluate_neighbourhood(
        longitude=144.96,
        latitude=-37.81,
        neighbourhood=_neighbourhood([_candidate(1, 274, 61.2)], nearest=274),
    )
    assert limited.crowd_exposure_score == fixture["limited"]["crowdExposureScore"]
    assert limited.crowd_level == fixture["limited"]["crowdLevel"]
    assert limited.coverage_status == fixture["limited"]["coverageStatus"]
    assert limited.supporting_sensors == fixture["limited"]["supportingSensors"]

    no_data = service.evaluate_neighbourhood(
        longitude=144.96,
        latitude=-37.81,
        neighbourhood=_neighbourhood(nearest=342),
    )
    assert no_data.crowd_exposure_score is None
    assert no_data.crowd_level is None
    assert no_data.coverage_status == fixture["no_data"]["coverageStatus"]
    assert no_data.supporting_sensors == fixture["no_data"]["supportingSensors"]
    assert no_data.nearest_sensor_distance_m == fixture["no_data"][
        "nearestSensorDistanceM"
    ]


def test_v1b_final_target_evidence_selects_idw1_and_supersedes_old_v1_target() -> None:
    with V1B_300.open(newline="", encoding="utf-8") as source:
        final_rows = list(csv.DictReader(source))
    selected = next(row for row in final_rows if row["method"] == "idw1")
    assert float(selected["coverage"]) == pytest.approx(0.9298376514781177)
    assert float(selected["MAE"]) == min(float(row["MAE"]) for row in final_rows)
    assert float(selected["RMSE"]) == min(float(row["RMSE"]) for row in final_rows)

    with V1_OLD.open(newline="", encoding="utf-8") as source:
        old_rows = list(csv.DictReader(source))
    assert next(row for row in old_rows if row["recommended_by_min_MAE"] == "True")[
        "method"
    ] == "equal"
