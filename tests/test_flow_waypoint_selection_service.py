from datetime import date, datetime, timezone

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
    route_offset: float = 100,
) -> WaypointSensorEvidence:
    return WaypointSensorEvidence(
        longitude=144.961,
        latitude=-37.815,
        distance_from_origin_meters=500,
        distance_from_destination_meters=500,
        distance_from_direct_route_meters=route_offset,
        estimated_geometric_detour_meters=detour,
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
        sensor_flow=endpoint_near.sensor_flow,
    )

    assert _select([endpoint_near, _evidence(_sensor(2), route_offset=35)]) == ()
