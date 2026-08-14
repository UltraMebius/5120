from datetime import date, datetime, timezone

import pytest

from backend.app.models.pedestrian_flow import (
    PedestrianFlowSnapshot,
    SensorPedestrianFlow,
)
from backend.app.services.routing.flow_waypoint_selection_service import (
    FlowWaypointSelectionService,
)
from backend.app.services.routing.route_candidate_models import (
    WaypointEvidenceBatch,
    WaypointFlowSource,
    WaypointSensorEvidence,
)


NOW = datetime(2026, 8, 13, 1, 0, tzinfo=timezone.utc)
SNAPSHOT = PedestrianFlowSnapshot(NOW, NOW, NOW, 1, 11, "Weekday")


def _sensor(
    location_id: int,
    *,
    state: str = "OK",
    live_count: int | None = 150,
    historical_median: float | None = 600,
) -> SensorPedestrianFlow:
    return SensorPedestrianFlow(
        location_id=location_id,
        distance_meters=100,
        location_type="Outdoor",
        status="A",
        data_state=state,
        current_15m_count=live_count,
        current_15m_observed_rows=15,
        window_start=NOW,
        window_end=NOW,
        calculated_at=NOW,
        baseline_hour_day=11,
        baseline_day_type="Weekday",
        baseline_observation_count=50,
        baseline_median_count=historical_median,
        baseline_mean_count=historical_median,
        baseline_p75_count=historical_median,
        baseline_start_date=date(2025, 1, 1),
        baseline_end_date=date(2026, 1, 1),
    )


def _evidence(
    sensor: SensorPedestrianFlow,
    *,
    detour: float = 50,
    progress: float = 0.5,
    route_offset: float = 100,
) -> WaypointSensorEvidence:
    return WaypointSensorEvidence(
        longitude=144.961,
        latitude=-37.815,
        distance_from_origin_meters=500,
        distance_from_destination_meters=500,
        distance_from_direct_route_meters=route_offset,
        estimated_geometric_detour_meters=detour,
        projected_route_progress=progress,
        sensor_flow=sensor,
    )


class FakeRepository:
    def __init__(self, evidence):
        self.evidence = tuple(evidence)
        self.calls = []

    def find_waypoint_evidence(self, **kwargs):
        self.calls.append(kwargs)
        return WaypointEvidenceBatch(self.evidence, SNAPSHOT, 2.0, 1)


def _select(evidence):
    repository = FakeRepository(evidence)
    selected = FlowWaypointSelectionService(repository).select_waypoints(
        origin=(144.96, -37.82),
        destination=(144.96, -37.81),
        direct_route_geometry={"type": "LineString", "coordinates": []},
    )
    assert len(repository.calls) == 1
    return selected


def test_live_waypoints_are_ranked_before_historical_estimates() -> None:
    selected = _select(
        [
            _evidence(
                _sensor(
                    1,
                    state="NO_DATA",
                    live_count=None,
                    historical_median=60,
                )
            ),
            _evidence(_sensor(2, live_count=300)),
        ]
    )

    assert [waypoint.location_id for waypoint in selected] == [2, 1]
    assert [waypoint.flow_source for waypoint in selected] == [
        WaypointFlowSource.LIVE,
        WaypointFlowSource.HISTORICAL_ESTIMATE,
    ]


def test_same_source_orders_by_flow_then_detour_then_location_id() -> None:
    selected = _select(
        [
            _evidence(_sensor(30, live_count=150), detour=40),
            _evidence(_sensor(20, live_count=75), detour=60),
            _evidence(_sensor(10, live_count=75), detour=60),
        ]
    )

    assert [waypoint.location_id for waypoint in selected] == [10, 20]


def test_on_route_or_endpoint_near_evidence_is_not_eligible() -> None:
    endpoint_near = _evidence(_sensor(1))
    endpoint_near = WaypointSensorEvidence(
        longitude=endpoint_near.longitude,
        latitude=endpoint_near.latitude,
        distance_from_origin_meters=149,
        distance_from_destination_meters=500,
        distance_from_direct_route_meters=100,
        estimated_geometric_detour_meters=50,
        projected_route_progress=0.5,
        sensor_flow=endpoint_near.sensor_flow,
    )

    assert _select([endpoint_near, _evidence(_sensor(2), route_offset=35)]) == ()


@pytest.mark.parametrize("progress", [0.10, 0.50, 0.90])
def test_middle_and_inclusive_progress_boundaries_are_eligible(progress) -> None:
    selected = _select([_evidence(_sensor(1), progress=progress)])

    assert len(selected) == 1
    assert selected[0].projected_route_progress == progress


def test_early_late_and_destination_end_progress_are_excluded() -> None:
    selected = _select(
        [
            _evidence(_sensor(1), progress=0.0999),
            _evidence(_sensor(2), progress=0.9001),
            _evidence(_sensor(3), progress=1.0),
        ]
    )

    assert selected == ()


def test_lateral_middle_waypoint_remains_eligible_without_changing_flow_order() -> None:
    selected = _select(
        [
            _evidence(
                _sensor(1, live_count=60),
                progress=0.65,
                route_offset=250,
            ),
            _evidence(
                _sensor(2, live_count=30),
                progress=0.45,
                route_offset=200,
            ),
        ]
    )

    assert [waypoint.location_id for waypoint in selected] == [2, 1]


def test_waypoint_selection_logs_repository_and_selection_timings(caplog) -> None:
    repository = FakeRepository([_evidence(_sensor(1))])

    with caplog.at_level(
        "INFO",
        logger=(
            "backend.app.services.routing.flow_waypoint_selection_service"
        ),
    ):
        selected = FlowWaypointSelectionService(repository).select_waypoints(
            origin=(144.96, -37.82),
            destination=(144.96, -37.81),
            direct_route_geometry={"type": "LineString", "coordinates": []},
        )

    assert len(selected) == 1
    message = next(
        record.getMessage()
        for record in caplog.records
        if record.getMessage().startswith("waypoint_selection_timing ")
    )
    for field in (
        "database_ms=2.000",
        "selection_total_ms=",
        "evidence_count=1",
        "eligible_count=1",
        "selected_count=1",
        "sql_execution_count=1",
    ):
        assert field in message
