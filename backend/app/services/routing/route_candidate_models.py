"""Internal candidate-generation records; none are public API contracts."""

from dataclasses import dataclass
from enum import Enum

from ...models.pedestrian_flow import (
    PedestrianFlowSnapshot,
    RoutePedestrianFlowSummary,
    SensorPedestrianFlow,
)
from ...schemas.routes import GeoJsonLineString, WalkingRouteStep


class RouteCandidateSource(str, Enum):
    DIRECT = "DIRECT"
    MAPBOX_ALTERNATIVE = "MAPBOX_ALTERNATIVE"
    FLOW_WAYPOINT = "FLOW_WAYPOINT"


class WaypointFlowSource(str, Enum):
    LIVE = "LIVE"
    HISTORICAL_ESTIMATE = "HISTORICAL_ESTIMATE"


class CandidateGenerationReason(str, Enum):
    MULTIPLE_MAPBOX_ROUTES = "MULTIPLE_MAPBOX_ROUTES"
    WAYPOINT_ALTERNATIVE_ADDED = "WAYPOINT_ALTERNATIVE_ADDED"
    ONLY_ONE_MEANINGFUL_CORRIDOR = "ONLY_ONE_MEANINGFUL_CORRIDOR"
    NO_VALID_WAYPOINT = "NO_VALID_WAYPOINT"
    ALTERNATIVES_TOO_SIMILAR = "ALTERNATIVES_TOO_SIMILAR"
    DETOUR_LIMIT_EXCEEDED = "DETOUR_LIMIT_EXCEEDED"
    JOURNEY_TOO_SHORT = "JOURNEY_TOO_SHORT"


@dataclass(frozen=True, slots=True)
class WaypointSensorEvidence:
    """Authoritative sensor location plus source-separated Phase 1 evidence."""

    longitude: float
    latitude: float
    distance_from_origin_meters: float
    distance_from_destination_meters: float
    distance_from_direct_route_meters: float
    estimated_geometric_detour_meters: float
    sensor_flow: SensorPedestrianFlow


@dataclass(frozen=True, slots=True)
class WaypointEvidenceBatch:
    evidence: tuple[WaypointSensorEvidence, ...]
    snapshot: PedestrianFlowSnapshot
    database_elapsed_ms: float
    sql_execution_count: int


@dataclass(frozen=True, slots=True)
class SelectedFlowWaypoint:
    """One bounded routing attempt nominated by sensor flow evidence."""

    location_id: int
    longitude: float
    latitude: float
    flow_source: WaypointFlowSource
    pedestrian_movements_per_minute: float
    estimated_geometric_detour_meters: float
    distance_from_direct_route_meters: float


@dataclass(frozen=True, slots=True)
class RouteCandidate:
    """A real normalized Mapbox geometry with engineering provenance."""

    route_id: str
    source_index: int
    candidate_source: RouteCandidateSource
    geometry: GeoJsonLineString
    distance_meters: float
    duration_seconds: float
    steps: tuple[WalkingRouteStep, ...]
    pedestrian_flow_summary: RoutePedestrianFlowSummary | None = None
    waypoint_metadata: SelectedFlowWaypoint | None = None


@dataclass(frozen=True, slots=True)
class RouteSimilarityResult:
    """Symmetric directional sampled-corridor overlap diagnostics."""

    route_a_sample_count: int
    route_b_sample_count: int
    matched_route_a_samples: int
    matched_route_b_samples: int
    coverage_a_to_b: float
    coverage_b_to_a: float
    too_similar: bool


@dataclass(frozen=True, slots=True)
class CandidateGenerationTimings:
    mapbox_initial_ms: float
    candidate_distinctness_ms: float
    waypoint_selection_ms: float
    waypoint_mapbox_ms: float
    sampling_ms: float
    flow_batch_db_ms: float
    flow_aggregation_ms: float
    total_ms: float
    mapbox_request_count: int
    candidate_count_before_filter: int
    candidate_count_after_filter: int
    flow_sql_execution_count: int


@dataclass(frozen=True, slots=True)
class MultiRouteCandidateResult:
    candidates: tuple[RouteCandidate, ...]
    reason: CandidateGenerationReason
    timings: CandidateGenerationTimings
