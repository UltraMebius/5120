from datetime import datetime, timezone

import pytest

from backend.app.db.exceptions import DatabaseQueryError
from backend.app.models.spatial import PointCrowdEstimate
from backend.app.services.routing.route_crowd_evaluation_service import (
    RouteCrowdEvaluationService,
)
from backend.app.services.routing.route_sampling_service import (
    InvalidRouteGeometryError,
    RouteSample,
    RouteSamplingService,
    SampledRoute,
)


WINDOW_START = datetime(2026, 8, 10, 8, 0, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 8, 10, 8, 15, tzinfo=timezone.utc)
UPDATED_AT = datetime(2026, 8, 10, 8, 20, tzinfo=timezone.utc)
SAMPLES = (
    RouteSample(0, 0.0, 144.9671, -37.8183),
    RouteSample(1, 50.0, 144.9668, -37.8179),
    RouteSample(2, 93.25, 144.9664, -37.8175),
)


def _sampled_route(
    samples: tuple[RouteSample, ...] = SAMPLES,
) -> SampledRoute:
    return SampledRoute(
        route_length_meters=samples[-1].distance_along_route_meters,
        sampling_interval_meters=50.0,
        samples=samples,
    )


def _point_result(
    sample: RouteSample,
    *,
    coverage_status: str = "SUPPORTED",
    crowd_score: float | None = 62.5,
    crowd_level: str | None = "MODERATE",
    local_score: float | None = 42.0,
    local_condition: str | None = "QUIETER_THAN_USUAL",
) -> PointCrowdEstimate:
    has_support = coverage_status != "NO_DATA"
    nearest_distance = (
        275.0
        if coverage_status == "LIMITED"
        else 75.0 if coverage_status == "SUPPORTED" else None
    )
    return PointCrowdEstimate(
        latitude=sample.latitude,
        longitude=sample.longitude,
        crowd_exposure_score=crowd_score,
        crowd_level=crowd_level,
        local_condition_score=local_score,
        local_condition=local_condition,
        coverage_status=coverage_status,
        nearby_sensors=2 if has_support else 0,
        nearby_active_outdoor_sensors=2 if has_support else 0,
        supporting_sensors=2 if has_support else 0,
        nearest_sensor_distance_m=nearest_distance,
        supporting_score_stddev=None,
        weighting_method="inverse_distance_1_over_d",
        updated_at=UPDATED_AT,
        source_window_start=WINDOW_START,
        source_window_end=WINDOW_END,
        support_radius_m=300.0,
        reason=None if has_support else "NO_VALID_CURRENT_SENSOR_AVAILABLE",
        contributions=(),
    )


class FakeSamplingService:
    def __init__(self, sampled_route: SampledRoute) -> None:
        self.sampled_route = sampled_route
        self.calls: list[object] = []

    def sample_geometry(self, geometry: object) -> SampledRoute:
        self.calls.append(geometry)
        return self.sampled_route


class FakeSpatialCrowdService:
    def __init__(
        self,
        results: tuple[PointCrowdEstimate, ...] = (),
        *,
        error: Exception | None = None,
    ) -> None:
        self.results = results
        self.error = error
        self.calls: list[dict[str, float]] = []

    def evaluate(
        self,
        *,
        longitude: float,
        latitude: float,
    ) -> PointCrowdEstimate:
        self.calls.append({"longitude": longitude, "latitude": latitude})
        if self.error is not None:
            raise self.error
        return self.results[len(self.calls) - 1]


def _service_with_results(
    samples: tuple[RouteSample, ...] = SAMPLES,
    results: tuple[PointCrowdEstimate, ...] | None = None,
) -> tuple[
    RouteCrowdEvaluationService,
    FakeSamplingService,
    FakeSpatialCrowdService,
]:
    sampling = FakeSamplingService(_sampled_route(samples))
    spatial = FakeSpatialCrowdService(
        results
        if results is not None
        else tuple(_point_result(sample) for sample in samples)
    )
    return RouteCrowdEvaluationService(sampling, spatial), sampling, spatial


def test_sampling_service_is_invoked_once_per_route() -> None:
    service, sampling, _ = _service_with_results()
    geometry = {"type": "LineString", "coordinates": [[0, 0], [1, 1]]}

    service.evaluate_geometry(geometry, route_id="route-1")

    assert sampling.calls == [geometry]


def test_every_sample_is_evaluated_exactly_once() -> None:
    service, _, spatial = _service_with_results()

    service.evaluate_geometry(object())

    assert spatial.calls == [
        {"longitude": sample.longitude, "latitude": sample.latitude}
        for sample in SAMPLES
    ]


def test_sample_order_is_preserved_without_crowd_sorting() -> None:
    results = (
        _point_result(SAMPLES[0], crowd_score=90.0, crowd_level="HIGH"),
        _point_result(SAMPLES[1], crowd_score=10.0, crowd_level="VERY_LOW"),
        _point_result(SAMPLES[2], crowd_score=50.0, crowd_level="LOW"),
    )
    service, _, _ = _service_with_results(results=results)

    evaluation = service.evaluate_geometry(object())

    assert [row.sample.index for row in evaluation.sample_results] == [0, 1, 2]
    assert [row.crowd.crowd_exposure_score for row in evaluation.sample_results] == [
        90.0,
        10.0,
        50.0,
    ]


def test_sample_distances_are_preserved_exactly() -> None:
    service, _, _ = _service_with_results()

    evaluation = service.evaluate_geometry(object())

    assert [
        row.sample.distance_along_route_meters
        for row in evaluation.sample_results
    ] == [0.0, 50.0, 93.25]


def test_sample_coordinates_are_preserved_exactly() -> None:
    service, _, spatial = _service_with_results()

    evaluation = service.evaluate_geometry(object())

    assert [
        (row.sample.longitude, row.sample.latitude)
        for row in evaluation.sample_results
    ] == [(sample.longitude, sample.latitude) for sample in SAMPLES]
    assert spatial.calls[0] == {
        "longitude": SAMPLES[0].longitude,
        "latitude": SAMPLES[0].latitude,
    }


def test_supported_point_result_is_propagated_unchanged() -> None:
    result = _point_result(SAMPLES[0], coverage_status="SUPPORTED")
    service, _, _ = _service_with_results(
        samples=(SAMPLES[0],),
        results=(result,),
    )

    evaluation = service.evaluate_geometry(object())

    assert evaluation.sample_results[0].crowd is result
    assert evaluation.sample_results[0].crowd.coverage_status == "SUPPORTED"


def test_limited_point_result_is_propagated_without_upgrade() -> None:
    result = _point_result(SAMPLES[0], coverage_status="LIMITED")
    service, _, _ = _service_with_results(
        samples=(SAMPLES[0],),
        results=(result,),
    )

    evaluation = service.evaluate_geometry(object())

    assert evaluation.sample_results[0].crowd is result
    assert evaluation.sample_results[0].crowd.coverage_status == "LIMITED"


def test_no_data_point_result_is_propagated_as_valid_domain_result() -> None:
    result = _point_result(
        SAMPLES[0],
        coverage_status="NO_DATA",
        crowd_score=None,
        crowd_level=None,
        local_score=None,
        local_condition=None,
    )
    service, _, _ = _service_with_results(
        samples=(SAMPLES[0],),
        results=(result,),
    )

    evaluation = service.evaluate_geometry(object())

    assert evaluation.sample_count == 1
    assert evaluation.sample_results[0].crowd is result
    assert evaluation.sample_results[0].crowd.coverage_status == "NO_DATA"


def test_numeric_crowd_exposure_is_propagated_without_recalculation() -> None:
    result = _point_result(SAMPLES[0], crowd_score=67.125)
    service, _, _ = _service_with_results(
        samples=(SAMPLES[0],),
        results=(result,),
    )

    evaluation = service.evaluate_geometry(object())

    assert evaluation.sample_results[0].crowd.crowd_exposure_score == 67.125


def test_null_crowd_exposure_never_becomes_zero_or_low() -> None:
    result = _point_result(
        SAMPLES[0],
        coverage_status="NO_DATA",
        crowd_score=None,
        crowd_level=None,
        local_score=None,
        local_condition=None,
    )
    service, _, _ = _service_with_results(
        samples=(SAMPLES[0],),
        results=(result,),
    )

    crowd = service.evaluate_geometry(object()).sample_results[0].crowd

    assert crowd.crowd_exposure_score is None
    assert crowd.crowd_level is None


def test_local_condition_fields_are_propagated_unchanged() -> None:
    result = _point_result(
        SAMPLES[0],
        local_score=88.75,
        local_condition="BUSIER_THAN_USUAL",
    )
    service, _, _ = _service_with_results(
        samples=(SAMPLES[0],),
        results=(result,),
    )

    crowd = service.evaluate_geometry(object()).sample_results[0].crowd

    assert crowd.local_condition_score == 88.75
    assert crowd.local_condition == "BUSIER_THAN_USUAL"


def test_first_and_last_samples_are_preserved() -> None:
    service, _, _ = _service_with_results()

    evaluation = service.evaluate_geometry(object())

    assert evaluation.sample_results[0].sample is SAMPLES[0]
    assert evaluation.sample_results[-1].sample is SAMPLES[-1]


def test_short_two_sample_route_evaluates_both_endpoints() -> None:
    short_samples = (SAMPLES[0], SAMPLES[-1])
    service, _, spatial = _service_with_results(samples=short_samples)

    evaluation = service.evaluate_geometry(object())

    assert evaluation.sample_count == 2
    assert len(spatial.calls) == 2


def test_reverse_direction_route_keeps_reverse_origin_to_destination_order() -> None:
    geometry = {
        "type": "LineString",
        "coordinates": [
            [144.9631, -37.8102],
            [144.9671, -37.8183],
        ],
    }
    sampling_service = RouteSamplingService(interval_meters=500)
    sampled = sampling_service.sample_geometry(geometry)
    spatial = FakeSpatialCrowdService(
        tuple(_point_result(sample) for sample in sampled.samples)
    )
    service = RouteCrowdEvaluationService(sampling_service, spatial)

    evaluation = service.evaluate_geometry(geometry)

    assert (
        evaluation.sample_results[0].sample.longitude,
        evaluation.sample_results[0].sample.latitude,
    ) == (144.9631, -37.8102)
    assert (
        evaluation.sample_results[-1].sample.longitude,
        evaluation.sample_results[-1].sample.latitude,
    ) == (144.9671, -37.8183)


def test_invalid_geometry_sampling_error_propagates_before_spatial_calls() -> None:
    spatial = FakeSpatialCrowdService()
    service = RouteCrowdEvaluationService(RouteSamplingService(), spatial)

    with pytest.raises(InvalidRouteGeometryError):
        service.evaluate_geometry(
            {"type": "LineString", "coordinates": [[144.96, -37.81]]}
        )

    assert spatial.calls == []


def test_database_failure_is_propagated_and_not_converted_to_no_data() -> None:
    sampling = FakeSamplingService(_sampled_route())
    error = DatabaseQueryError("controlled database failure")
    spatial = FakeSpatialCrowdService(error=error)
    service = RouteCrowdEvaluationService(sampling, spatial)

    with pytest.raises(DatabaseQueryError, match="controlled database failure"):
        service.evaluate_geometry(object())

    assert len(spatial.calls) == 1


def test_all_no_data_samples_are_returned_without_route_rejection() -> None:
    results = tuple(
        _point_result(
            sample,
            coverage_status="NO_DATA",
            crowd_score=None,
            crowd_level=None,
            local_score=None,
            local_condition=None,
        )
        for sample in SAMPLES
    )
    service, _, _ = _service_with_results(results=results)

    evaluation = service.evaluate_geometry(object())

    assert evaluation.sample_count == len(SAMPLES)
    assert all(
        row.crowd.coverage_status == "NO_DATA"
        and row.crowd.crowd_exposure_score is None
        and row.crowd.crowd_level is None
        for row in evaluation.sample_results
    )


def test_route_trace_metadata_contains_no_route_level_crowd_metrics() -> None:
    service, _, _ = _service_with_results()

    evaluation = service.evaluate_geometry(object(), route_id="mapbox-route-2")

    assert evaluation.route_id == "mapbox-route-2"
    assert evaluation.route_length_meters == 93.25
    assert evaluation.sampling_interval_meters == 50.0
    assert evaluation.sample_count == 3
    assert not hasattr(evaluation, "route_crowd_level")
    assert not hasattr(evaluation, "p75_crowd_exposure_score")
    assert not hasattr(evaluation, "recommended")
