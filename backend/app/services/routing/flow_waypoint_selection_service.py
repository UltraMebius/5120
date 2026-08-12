"""Deterministic selection of lower-flow, corridor-useful sensor waypoints."""

from collections.abc import Sequence
import math
from typing import Protocol

from .route_candidate_config import (
    MAXIMUM_WAYPOINT_ATTEMPTS,
    MINIMUM_WAYPOINT_ENDPOINT_DISTANCE_M,
    MINIMUM_WAYPOINT_ROUTE_OFFSET_M,
    WAYPOINT_SEARCH_CORRIDOR_RADIUS_M,
)
from .route_candidate_models import (
    SelectedFlowWaypoint,
    WaypointEvidenceBatch,
    WaypointFlowSource,
    WaypointSensorEvidence,
)


class WaypointEvidenceConsistencyError(RuntimeError):
    """Authoritative waypoint evidence cannot be ranked safely."""


class _WaypointEvidenceRepository(Protocol):
    def find_waypoint_evidence(
        self,
        *,
        origin: tuple[float, float],
        destination: tuple[float, float],
        direct_route_geometry: object,
    ) -> WaypointEvidenceBatch: ...


class FlowWaypointSelectionService:
    """Prefer LIVE evidence, then historical estimates, within fixed bounds."""

    def __init__(self, repository: _WaypointEvidenceRepository | None = None) -> None:
        if repository is None:
            from ...repositories.route_waypoint_repository import (
                RouteWaypointRepository,
            )

            repository = RouteWaypointRepository()
        self.repository = repository

    @staticmethod
    def _eligible(evidence: WaypointSensorEvidence) -> bool:
        numeric = (
            evidence.longitude,
            evidence.latitude,
            evidence.distance_from_origin_meters,
            evidence.distance_from_destination_meters,
            evidence.distance_from_direct_route_meters,
            evidence.estimated_geometric_detour_meters,
        )
        if any(not math.isfinite(value) for value in numeric):
            raise WaypointEvidenceConsistencyError(
                "waypoint spatial evidence must be finite"
            )
        return (
            evidence.sensor_flow.active_outdoor
            and evidence.distance_from_origin_meters
            >= MINIMUM_WAYPOINT_ENDPOINT_DISTANCE_M
            and evidence.distance_from_destination_meters
            >= MINIMUM_WAYPOINT_ENDPOINT_DISTANCE_M
            and evidence.distance_from_direct_route_meters
            > MINIMUM_WAYPOINT_ROUTE_OFFSET_M
            and evidence.distance_from_direct_route_meters
            <= WAYPOINT_SEARCH_CORRIDOR_RADIUS_M
            and evidence.estimated_geometric_detour_meters >= 0.0
        )

    @staticmethod
    def _selected(
        evidence: WaypointSensorEvidence,
        source: WaypointFlowSource,
        flow: float,
    ) -> SelectedFlowWaypoint:
        return SelectedFlowWaypoint(
            location_id=evidence.sensor_flow.location_id,
            longitude=evidence.longitude,
            latitude=evidence.latitude,
            flow_source=source,
            pedestrian_movements_per_minute=flow,
            estimated_geometric_detour_meters=(
                evidence.estimated_geometric_detour_meters
            ),
            distance_from_direct_route_meters=(
                evidence.distance_from_direct_route_meters
            ),
        )

    def select_waypoints(
        self,
        *,
        origin: tuple[float, float],
        destination: tuple[float, float],
        direct_route_geometry: object,
        limit: int = MAXIMUM_WAYPOINT_ATTEMPTS,
    ) -> tuple[SelectedFlowWaypoint, ...]:
        if not 0 <= limit <= MAXIMUM_WAYPOINT_ATTEMPTS:
            raise ValueError("waypoint limit exceeds the bounded attempt count")
        batch = self.repository.find_waypoint_evidence(
            origin=origin,
            destination=destination,
            direct_route_geometry=direct_route_geometry,
        )
        if batch.snapshot.window_variant_count > 1:
            raise WaypointEvidenceConsistencyError(
                "current_sensor_activity contains multiple current windows"
            )

        live: list[SelectedFlowWaypoint] = []
        historical: list[SelectedFlowWaypoint] = []
        for evidence in batch.evidence:
            if not self._eligible(evidence):
                continue
            live_flow = (
                evidence.sensor_flow.live_pedestrian_movements_per_minute
            )
            if live_flow is not None:
                live.append(
                    self._selected(evidence, WaypointFlowSource.LIVE, live_flow)
                )
                continue
            historical_flow = (
                evidence.sensor_flow.historical_typical_movements_per_minute
            )
            if historical_flow is not None:
                historical.append(
                    self._selected(
                        evidence,
                        WaypointFlowSource.HISTORICAL_ESTIMATE,
                        historical_flow,
                    )
                )

        rank_key = lambda waypoint: (
            waypoint.pedestrian_movements_per_minute,
            waypoint.estimated_geometric_detour_meters,
            waypoint.location_id,
        )
        live.sort(key=rank_key)
        historical.sort(key=rank_key)
        return tuple((live + historical)[:limit])
