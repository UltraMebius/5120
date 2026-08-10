"""Domain records for PostGIS candidates and point-level crowd estimates."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class SpatialSensorCandidate:
    location_id: int
    location_type: str
    status: str | None
    data_state: str | None
    distance_m: float
    current_15m_network_percentile: float | None
    current_1h_local_historical_percentile: float | None
    source_window_start: datetime | None
    source_window_end: datetime | None
    calculated_at: datetime | None

    @property
    def active_outdoor(self) -> bool:
        return (
            self.location_type.strip().casefold() == "outdoor"
            and (self.status or "").strip().upper() == "A"
        )


@dataclass(frozen=True)
class SpatialCurrentSnapshot:
    source_window_start: datetime | None
    source_window_end: datetime | None
    updated_at: datetime | None
    window_variant_count: int


@dataclass(frozen=True)
class SpatialNeighbourhood:
    candidates: tuple[SpatialSensorCandidate, ...]
    nearest_valid_sensor_distance_m: float | None
    snapshot: SpatialCurrentSnapshot


@dataclass(frozen=True)
class SpatialContribution:
    location_id: int
    distance_m: float
    normalised_weight: float
    crowd_exposure_score: float
    local_condition_score: float | None


@dataclass(frozen=True)
class PointCrowdEstimate:
    latitude: float
    longitude: float
    crowd_exposure_score: float | None
    crowd_level: str | None
    local_condition_score: float | None
    local_condition: str | None
    coverage_status: str
    nearby_sensors: int
    nearby_active_outdoor_sensors: int
    supporting_sensors: int
    nearest_sensor_distance_m: float | None
    supporting_score_stddev: float | None
    weighting_method: str
    updated_at: datetime | None
    source_window_start: datetime | None
    source_window_end: datetime | None
    support_radius_m: float
    reason: str | None
    contributions: tuple[SpatialContribution, ...]
