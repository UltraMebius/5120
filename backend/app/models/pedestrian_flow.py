"""Internal pedestrian-flow records with explicit source provenance."""

from dataclasses import dataclass
from datetime import date, datetime
import math


LIVE_WINDOW_MINUTES = 15.0
HISTORICAL_HOUR_MINUTES = 60.0
HISTORICAL_TYPICAL_STATISTIC_BASIS = "hourly_median_count"


def _non_negative_rate(value: int | float | None, minutes: float) -> float | None:
    """Convert a valid fixed-window count to a per-minute rate."""

    if (
        value is None
        or isinstance(value, bool)
        or not isinstance(value, (int, float))
    ):
        return None
    numeric_value = float(value)
    if not math.isfinite(numeric_value) or numeric_value < 0.0:
        return None
    return numeric_value / minutes


@dataclass(frozen=True, slots=True)
class FlowSamplePoint:
    """One route sample prepared for batched PostGIS discovery."""

    route_index: int
    sample_index: int
    distance_along_route_meters: float
    longitude: float
    latitude: float

    @property
    def key(self) -> tuple[int, int]:
        return self.route_index, self.sample_index


@dataclass(frozen=True, slots=True)
class PedestrianFlowSnapshot:
    """One current materialisation and its Melbourne baseline context."""

    window_start: datetime | None
    window_end: datetime | None
    calculated_at: datetime | None
    window_variant_count: int
    baseline_hour_day: int | None
    baseline_day_type: str | None


@dataclass(frozen=True, slots=True)
class SensorPedestrianFlow:
    """Raw spatial, current, and historical evidence for one sensor."""

    location_id: int
    distance_meters: float
    location_type: str
    status: str | None
    data_state: str | None
    current_15m_count: int | None
    current_15m_observed_rows: int | None
    window_start: datetime | None
    window_end: datetime | None
    calculated_at: datetime | None
    baseline_hour_day: int | None
    baseline_day_type: str | None
    baseline_observation_count: int | None
    baseline_median_count: float | None
    baseline_mean_count: float | None
    baseline_p75_count: float | None
    baseline_start_date: date | None
    baseline_end_date: date | None

    @property
    def active_outdoor(self) -> bool:
        return (
            self.location_type.strip().casefold() == "outdoor"
            and (self.status or "").strip().upper() == "A"
        )

    @property
    def live_pedestrian_movements_per_minute(self) -> float | None:
        """Return only a valid live fixed-15-minute rate."""

        if (self.data_state or "").strip().upper() != "OK":
            return None
        return _non_negative_rate(
            self.current_15m_count,
            LIVE_WINDOW_MINUTES,
        )

    @property
    def historical_typical_movements_per_minute(self) -> float | None:
        """Median historical hourly count expressed as an hourly-average rate."""

        return _non_negative_rate(
            self.baseline_median_count,
            HISTORICAL_HOUR_MINUTES,
        )

    @property
    def historical_typical_statistic_basis(self) -> str:
        """Identify the source statistic without implying minute-level samples."""

        return HISTORICAL_TYPICAL_STATISTIC_BASIS

    @property
    def historical_mean_movements_per_minute(self) -> float | None:
        """Mean historical hourly count expressed as an hourly-average rate."""

        return _non_negative_rate(
            self.baseline_mean_count,
            HISTORICAL_HOUR_MINUTES,
        )

    @property
    def historical_p75_movements_per_minute(self) -> float | None:
        """P75 historical hourly count expressed as an hourly-average rate."""

        return _non_negative_rate(
            self.baseline_p75_count,
            HISTORICAL_HOUR_MINUTES,
        )


@dataclass(frozen=True, slots=True)
class FlowNeighbourhood:
    """All sensor evidence returned for one requested route sample."""

    sample: FlowSamplePoint
    sensors: tuple[SensorPedestrianFlow, ...]


@dataclass(frozen=True, slots=True)
class FlowNeighbourhoodBatch:
    """One fixed-statement repository result for every requested sample."""

    neighbourhoods: tuple[FlowNeighbourhood, ...]
    snapshot: PedestrianFlowSnapshot
    database_elapsed_ms: float
    sql_execution_count: int


@dataclass(frozen=True, slots=True)
class PedestrianFlowContribution:
    """One sensor's normalized contribution to one source-specific point flow."""

    location_id: int
    distance_meters: float
    normalised_weight: float
    pedestrian_movements_per_minute: float


@dataclass(frozen=True, slots=True)
class SamplePedestrianFlow:
    """Source-separated pedestrian flow for one ordered route sample."""

    route_index: int
    sample_index: int
    distance_along_route_meters: float
    live_support_status: str
    historical_support_status: str
    live_pedestrian_movements_per_minute: float | None
    historical_typical_movements_per_minute: float | None
    live_contributor_count: int
    historical_contributor_count: int
    nearest_live_sensor_distance_meters: float | None
    nearest_historical_sensor_distance_meters: float | None
    window_start: datetime | None
    window_end: datetime | None
    calculated_at: datetime | None
    baseline_hour_day: int | None
    baseline_day_type: str | None
    live_contributions: tuple[PedestrianFlowContribution, ...]
    historical_contributions: tuple[PedestrianFlowContribution, ...]


@dataclass(frozen=True, slots=True)
class PedestrianFlowBatchEvaluation:
    """Point-flow outputs plus fixed-query performance diagnostics."""

    samples: tuple[SamplePedestrianFlow, ...]
    snapshot: PedestrianFlowSnapshot
    flow_batch_db_ms: float
    sql_execution_count: int


@dataclass(frozen=True, slots=True)
class RoutePedestrianFlowSummary:
    """Independent live and historical route-flow statistics."""

    route_index: int
    total_sample_count: int
    live_numeric_sample_count: int
    historical_numeric_sample_count: int
    live_coverage_pct: float
    historical_coverage_pct: float
    live_median_pedestrian_movements_per_minute: float | None
    live_p75_pedestrian_movements_per_minute: float | None
    live_maximum_pedestrian_movements_per_minute: float | None
    historical_median_pedestrian_movements_per_minute: float | None
    historical_p75_pedestrian_movements_per_minute: float | None
    historical_maximum_pedestrian_movements_per_minute: float | None


@dataclass(frozen=True, slots=True)
class PedestrianFlowPipelineTimings:
    """Safe request-stage timings with no location or credential data."""

    sampling_ms: float
    flow_batch_db_ms: float
    flow_aggregation_ms: float
    sql_execution_count: int
