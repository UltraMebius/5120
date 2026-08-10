"""Frozen Phase 2B eligibility, statistics contract, and build workflow."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
import math

from ...repositories.baseline_repository import (
    BaselineRepository,
    BaselineVerification,
    BaselineWriteResult,
    TrainingDataSummary,
)


TRAINING_START_DATE = date(2024, 8, 10)
TRAINING_END_DATE = date(2026, 2, 7)
SENSOR_37_LOCAL_START_DATE = date(2024, 8, 12)

HISTORICAL_MODELLING_LOCATION_TYPE = "Outdoor"
ACTIVE_SENSOR_STATUS = "A"

TEAM_KNOWN_UNRESOLVED_LOCATION_IDS = (28, 78)
# Phase 2B's full-window dry run also found source ID 65 absent from the
# authoritative current master. It is reported and excluded, never fabricated.
OBSERVED_UNRESOLVED_LOCATION_IDS = (28, 65, 78)
LOCAL_BASELINE_EXCLUDED_LOCATION_IDS = (47, 181)
ALL_LOCAL_EXCLUDED_LOCATION_IDS = tuple(
    sorted(
        set(OBSERVED_UNRESOLVED_LOCATION_IDS)
        | set(LOCAL_BASELINE_EXCLUDED_LOCATION_IDS)
    )
)

EXPECTED_DAY_TYPES = ("Weekday", "Weekend")
BASELINE_QUANTILES = (
    0.10,
    0.20,
    0.25,
    0.40,
    0.50,
    0.60,
    0.75,
    0.80,
    0.90,
    0.95,
)


class HistoricalBaselineError(RuntimeError):
    """Raised when source coverage or a built baseline violates Phase 2B."""


@dataclass(frozen=True)
class BaselineStatistics:
    observation_count: int
    mean_count: float
    median_count: float
    p10: float
    p20: float
    p25: float
    p40: float
    p50: float
    p60: float
    p75: float
    p80: float
    p90: float
    p95: float


@dataclass(frozen=True)
class HistoricalBaselineBuild:
    source: TrainingDataSummary
    write: BaselineWriteResult
    verification: BaselineVerification


def is_training_date(sensing_date: date) -> bool:
    """Return whether a source date is inside the inclusive frozen window."""

    return TRAINING_START_DATE <= sensing_date <= TRAINING_END_DATE


def is_modelling_sensor(location_type: str | None, status: str | None) -> bool:
    """Historical model population: authoritative active Outdoor sensors."""

    return (
        (location_type or "").strip().casefold()
        == HISTORICAL_MODELLING_LOCATION_TYPE.casefold()
        and (status or "").strip().upper() == ACTIVE_SENSOR_STATUS
    )


def is_local_observation_eligible(
    *,
    location_id: int,
    sensing_date: date,
    location_type: str | None,
    status: str | None,
) -> bool:
    """Apply frozen window, sensor-state, unresolved, and relocation rules."""

    if not is_training_date(sensing_date) or not is_modelling_sensor(
        location_type, status
    ):
        return False
    if location_id in ALL_LOCAL_EXCLUDED_LOCATION_IDS:
        return False
    if location_id == 37 and sensing_date < SENSOR_37_LOCAL_START_DATE:
        return False
    return True


def is_network_observation_eligible(
    *,
    location_id: int,
    sensing_date: date,
    location_type: str | None,
    status: str | None,
) -> bool:
    """Keep 47/181 for Network history while excluding unresolved identities."""

    return (
        is_training_date(sensing_date)
        and is_modelling_sensor(location_type, status)
        and location_id not in OBSERVED_UNRESOLVED_LOCATION_IDS
    )


def local_group_key(
    location_id: int, hour_day: int, day_type: str
) -> tuple[int, int, str]:
    return location_id, hour_day, day_type


def network_group_key(hour_day: int, day_type: str) -> tuple[int, str]:
    return hour_day, day_type


def continuous_percentile(values: Sequence[int | float], fraction: float) -> float:
    """Match PostgreSQL PERCENTILE_CONT linear interpolation for testable QA."""

    if not values:
        raise ValueError("At least one observed count is required.")
    if not 0.0 <= fraction <= 1.0:
        raise ValueError("Percentile fraction must be between 0 and 1.")
    ordered = sorted(float(value) for value in values)
    if any(not math.isfinite(value) for value in ordered):
        raise ValueError("Observed counts must be finite.")
    index = (len(ordered) - 1) * fraction
    lower_index = math.floor(index)
    upper_index = math.ceil(index)
    if lower_index == upper_index:
        return ordered[lower_index]
    weight = index - lower_index
    return ordered[lower_index] + (
        ordered[upper_index] - ordered[lower_index]
    ) * weight


def calculate_baseline_statistics(
    values: Sequence[int | float],
) -> BaselineStatistics:
    """Reference implementation of every statistic stored by the DS schema."""

    if not values:
        raise ValueError("At least one observed count is required.")
    numeric_values = tuple(float(value) for value in values)
    if any(value < 0 or not math.isfinite(value) for value in numeric_values):
        raise ValueError("Observed counts must be finite and non-negative.")
    quantiles = {
        fraction: continuous_percentile(numeric_values, fraction)
        for fraction in BASELINE_QUANTILES
    }
    return BaselineStatistics(
        observation_count=len(numeric_values),
        mean_count=sum(numeric_values) / len(numeric_values),
        median_count=quantiles[0.50],
        p10=quantiles[0.10],
        p20=quantiles[0.20],
        p25=quantiles[0.25],
        p40=quantiles[0.40],
        p50=quantiles[0.50],
        p60=quantiles[0.60],
        p75=quantiles[0.75],
        p80=quantiles[0.80],
        p90=quantiles[0.90],
        p95=quantiles[0.95],
    )


class HistoricalBaselineService:
    """Validate full source coverage and orchestrate the derived-table build."""

    def __init__(self, repository: BaselineRepository | None = None) -> None:
        self.repository = repository or BaselineRepository()

    def inspect_source(self) -> TrainingDataSummary:
        summary = self.repository.inspect_training_data(
            training_start=TRAINING_START_DATE,
            training_end=TRAINING_END_DATE,
            sensor_37_start=SENSOR_37_LOCAL_START_DATE,
            local_excluded_ids=ALL_LOCAL_EXCLUDED_LOCATION_IDS,
            location_type=HISTORICAL_MODELLING_LOCATION_TYPE,
            active_status=ACTIVE_SENSOR_STATUS,
        )
        self._validate_source(summary)
        return summary

    def build(self) -> HistoricalBaselineBuild:
        summary = self.inspect_source()
        write_result = self.repository.rebuild_baselines(
            training_start=TRAINING_START_DATE,
            training_end=TRAINING_END_DATE,
            sensor_37_start=SENSOR_37_LOCAL_START_DATE,
            local_excluded_ids=ALL_LOCAL_EXCLUDED_LOCATION_IDS,
            unresolved_ids=OBSERVED_UNRESOLVED_LOCATION_IDS,
            location_type=HISTORICAL_MODELLING_LOCATION_TYPE,
            active_status=ACTIVE_SENSOR_STATUS,
        )
        verification = self.inspect_baselines()
        if not verification.ok:
            raise HistoricalBaselineError(
                "Built baseline tables failed Phase 2B verification."
            )
        return HistoricalBaselineBuild(summary, write_result, verification)

    def inspect_baselines(self) -> BaselineVerification:
        return self.repository.inspect_baselines(
            training_start=TRAINING_START_DATE,
            training_end=TRAINING_END_DATE,
            sensor_37_start=SENSOR_37_LOCAL_START_DATE,
            local_excluded_ids=ALL_LOCAL_EXCLUDED_LOCATION_IDS,
            location_type=HISTORICAL_MODELLING_LOCATION_TYPE,
            active_status=ACTIVE_SENSOR_STATUS,
        )

    @staticmethod
    def _validate_source(summary: TrainingDataSummary) -> None:
        expected_date_count = (TRAINING_END_DATE - TRAINING_START_DATE).days + 1
        problems: list[str] = []
        if summary.total_training_rows <= 0:
            problems.append("no hourly observations exist in the training window")
        if summary.minimum_date != TRAINING_START_DATE:
            problems.append(
                f"minimum date is {summary.minimum_date}, expected "
                f"{TRAINING_START_DATE}"
            )
        if summary.maximum_date != TRAINING_END_DATE:
            problems.append(
                f"maximum date is {summary.maximum_date}, expected "
                f"{TRAINING_END_DATE}"
            )
        if summary.distinct_date_count != expected_date_count:
            problems.append(
                f"date coverage is {summary.distinct_date_count}/{expected_date_count}"
            )
        if summary.distinct_hour_count != 24:
            problems.append(
                f"hour coverage is {summary.distinct_hour_count}/24"
            )
        if set(summary.day_types) != set(EXPECTED_DAY_TYPES):
            problems.append(f"unexpected Day_Type values: {summary.day_types}")
        if summary.negative_count_rows:
            problems.append("negative observed counts are present")
        if summary.day_type_mismatch_rows:
            problems.append("stored Day_Type values disagree with sensing dates")
        if summary.unresolved_stored_rows:
            problems.append(
                "hourly rows without authoritative current location are present: "
                f"{summary.unresolved_stored_ids}"
            )
        if summary.eligible_sensor_count <= 0:
            problems.append("no active Outdoor modelling sensors are eligible")
        if summary.eligible_observation_count <= 0:
            problems.append("no active Outdoor observations are eligible")
        if summary.local_baseline_sensor_count <= 0:
            problems.append("no local-baseline sensors remain after relocation rules")
        if summary.sensor_14_observation_count <= 0:
            problems.append("Sensor 14 has no eligible full-window observations")
        if summary.sensor_14_minimum_date != TRAINING_START_DATE:
            problems.append("Sensor 14 does not begin at the frozen start date")
        if summary.sensor_37_local_minimum_date != SENSOR_37_LOCAL_START_DATE:
            problems.append("Sensor 37 Local history does not begin on 2024-08-12")
        if summary.zero_count_rows <= 0:
            problems.append("no legitimate zero observations were retained")
        if problems:
            raise HistoricalBaselineError(
                "Training data is incomplete or invalid: " + "; ".join(problems)
            )
