from datetime import datetime, timezone

import pytest

from backend.app.models.pedestrian_flow import (
    PedestrianFlowBatchEvaluation,
    PedestrianFlowContribution,
    PedestrianFlowSnapshot,
    SamplePedestrianFlow,
)
from backend.app.services.routing.route_pedestrian_flow_service import (
    RoutePedestrianFlowAggregationService,
    RoutePedestrianFlowInput,
    RoutePedestrianFlowService,
)
from backend.app.services.routing.route_sampling_service import (
    RouteSample,
    SampledRoute,
)


SNAPSHOT = PedestrianFlowSnapshot(
    window_start=datetime(2026, 8, 13, 1, 0, tzinfo=timezone.utc),
    window_end=datetime(2026, 8, 13, 1, 15, tzinfo=timezone.utc),
    calculated_at=datetime(2026, 8, 13, 1, 20, tzinfo=timezone.utc),
    window_variant_count=1,
    baseline_hour_day=11,
    baseline_day_type="Weekday",
)


def _flow_sample(
    route_index: int,
    sample_index: int,
    *,
    live: float | None,
    historical: float | None,
) -> SamplePedestrianFlow:
    live_contributions = (
        ()
        if live is None
        else (
            PedestrianFlowContribution(1, 100.0, 1.0, live),
        )
    )
    historical_contributions = (
        ()
        if historical is None
        else (
            PedestrianFlowContribution(1, 100.0, 1.0, historical),
        )
    )
    return SamplePedestrianFlow(
        route_index=route_index,
        sample_index=sample_index,
        distance_along_route_meters=float(sample_index * 50),
        live_support_status="NO_DATA" if live is None else "SUPPORTED",
        historical_support_status=(
            "NO_DATA" if historical is None else "SUPPORTED"
        ),
        live_pedestrian_movements_per_minute=live,
        historical_typical_movements_per_minute=historical,
        live_contributor_count=0 if live is None else 1,
        historical_contributor_count=0 if historical is None else 1,
        nearest_live_sensor_distance_meters=None if live is None else 100.0,
        nearest_historical_sensor_distance_meters=(
            None if historical is None else 100.0
        ),
        window_start=SNAPSHOT.window_start,
        window_end=SNAPSHOT.window_end,
        calculated_at=SNAPSHOT.calculated_at,
        baseline_hour_day=SNAPSHOT.baseline_hour_day,
        baseline_day_type=SNAPSHOT.baseline_day_type,
        live_contributions=live_contributions,
        historical_contributions=historical_contributions,
    )


def test_route_live_and_historical_statistics_are_aggregated_separately() -> None:
    samples = [
        _flow_sample(0, 0, live=10, historical=5),
        _flow_sample(0, 1, live=20, historical=None),
        _flow_sample(0, 2, live=30, historical=15),
        _flow_sample(0, 3, live=40, historical=25),
    ]

    summary = RoutePedestrianFlowAggregationService().aggregate_route(
        0, samples
    )

    assert summary.live_median_pedestrian_movements_per_minute == 25.0
    assert summary.live_p75_pedestrian_movements_per_minute == 32.5
    assert summary.live_maximum_pedestrian_movements_per_minute == 40.0
    assert summary.historical_median_pedestrian_movements_per_minute == 15.0
    assert summary.historical_p75_pedestrian_movements_per_minute == 20.0
    assert summary.historical_maximum_pedestrian_movements_per_minute == 25.0
    assert summary.live_coverage_pct == 100.0
    assert summary.historical_coverage_pct == 75.0


def test_missing_sample_values_do_not_become_zero_in_statistics() -> None:
    samples = [
        _flow_sample(0, 0, live=None, historical=None),
        _flow_sample(0, 1, live=10, historical=20),
        _flow_sample(0, 2, live=None, historical=40),
        _flow_sample(0, 3, live=30, historical=None),
    ]

    summary = RoutePedestrianFlowAggregationService().aggregate_route(
        0, samples
    )

    assert summary.live_numeric_sample_count == 2
    assert summary.historical_numeric_sample_count == 2
    assert summary.live_coverage_pct == 50.0
    assert summary.historical_coverage_pct == 50.0
    assert summary.live_median_pedestrian_movements_per_minute == 20.0
    assert summary.historical_median_pedestrian_movements_per_minute == 30.0


class FakeSamplingService:
    def __init__(self):
        self.calls = []

    def sample_geometry(self, geometry):
        self.calls.append(geometry)
        count = int(geometry)
        return SampledRoute(
            route_length_meters=float((count - 1) * 50),
            sampling_interval_meters=50.0,
            samples=tuple(
                RouteSample(
                    index=index,
                    distance_along_route_meters=float(index * 50),
                    longitude=144.96 + index * 0.0001,
                    latitude=-37.81,
                )
                for index in range(count)
            ),
        )


class FakeFlowService:
    def __init__(self):
        self.calls = []

    def evaluate_samples(self, samples):
        requested = tuple(samples)
        self.calls.append(requested)
        return PedestrianFlowBatchEvaluation(
            samples=tuple(
                _flow_sample(
                    sample.route_index,
                    sample.sample_index,
                    live=float(10 + sample.route_index + sample.sample_index),
                    historical=float(20 + sample.route_index),
                )
                for sample in requested
            ),
            snapshot=SNAPSHOT,
            flow_batch_db_ms=3.25,
            sql_execution_count=1,
        )


def test_three_routes_share_one_flow_batch_and_map_back_correctly() -> None:
    sampling = FakeSamplingService()
    flow = FakeFlowService()
    service = RoutePedestrianFlowService(sampling, flow)
    routes = [
        RoutePedestrianFlowInput(0, 2, "route-0"),
        RoutePedestrianFlowInput(1, 3, "route-1"),
        RoutePedestrianFlowInput(2, 1, "route-2"),
    ]

    result = service.evaluate_routes(routes)

    assert sampling.calls == [2, 3, 1]
    assert len(flow.calls) == 1
    assert [(sample.route_index, sample.sample_index) for sample in flow.calls[0]] == [
        (0, 0),
        (0, 1),
        (1, 0),
        (1, 1),
        (1, 2),
        (2, 0),
    ]
    assert [route.route_index for route in result.routes] == [0, 1, 2]
    assert [len(route.samples) for route in result.routes] == [2, 3, 1]
    assert result.routes[1].route_id == "route-1"
    assert result.routes[1].summary.live_coverage_pct == 100.0
    assert result.timings.sampling_ms >= 0.0
    assert result.timings.flow_batch_db_ms == 3.25
    assert result.timings.flow_aggregation_ms >= 0.0
    assert result.timings.sql_execution_count == 1


def test_route_pipeline_does_not_assign_route_roles_or_rankings() -> None:
    result = RoutePedestrianFlowService(
        FakeSamplingService(), FakeFlowService()
    ).evaluate_routes([RoutePedestrianFlowInput(0, 1, "route-0")])

    route = result.routes[0]
    assert not hasattr(route, "rank")
    assert not hasattr(route, "role_badges")
