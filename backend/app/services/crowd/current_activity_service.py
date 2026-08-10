"""Handoff-defined current sensor windows, states, and empirical percentiles."""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from ...config import SETTINGS
from ...models.crowd import CrowdLevel, DataState, LocalCondition
from ...models.minute import (
    CurrentSensorActivityRecord,
    CurrentSensorDefinition,
    MinuteObservation,
)
from ...repositories.current_activity_repository import CurrentActivityRepository


@dataclass(frozen=True)
class CurrentWindows:
    as_of: datetime
    current_start: datetime
    current_end: datetime
    comparison_start: datetime
    comparison_end: datetime


@dataclass(frozen=True)
class CurrentActivityBuild:
    windows: CurrentWindows
    records: tuple[CurrentSensorActivityRecord, ...]
    eligible_sensor_count: int
    observed_current_sensor_count: int
    ambiguous_sensor_count: int
    stale_sensor_count: int
    conflicted_sensor_count: int
    no_data_sensor_count: int
    conflict_group_count: int
    comparison_hour_complete: bool
    comparison_distinct_minute_count: int
    local_historical_available_count: int
    network_historical_available_count: int
    current_network_available_count: int
    source_latest_datetime: datetime | None
    source_freshness_minutes: float | None
    stale_threshold_minutes: int | None


def calculate_windows(
    as_of: datetime,
    *,
    timezone_name: str = SETTINGS.app_timezone,
    window_minutes: int = 15,
) -> CurrentWindows:
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")
    if window_minutes <= 0 or 60 % window_minutes:
        raise ValueError("window_minutes must be a positive divisor of 60")
    local = as_of.astimezone(ZoneInfo(timezone_name))
    current_end_local = local.replace(
        minute=(local.minute // window_minutes) * window_minutes,
        second=0,
        microsecond=0,
    )
    current_end = current_end_local.astimezone(timezone.utc)
    comparison_end_local = local.replace(minute=0, second=0, microsecond=0)
    comparison_end = comparison_end_local.astimezone(timezone.utc)
    return CurrentWindows(
        as_of=as_of,
        current_start=current_end - timedelta(minutes=window_minutes),
        current_end=current_end,
        comparison_start=comparison_end - timedelta(hours=1),
        comparison_end=comparison_end,
    )


def empirical_cdf(value: int, reference_values: Sequence[int]) -> float:
    if not reference_values:
        raise ValueError("reference_values must not be empty")
    return 100.0 * sum(candidate <= value for candidate in reference_values) / len(
        reference_values
    )


def classify_crowd_level(percentile: float) -> str:
    if percentile <= 25:
        return CrowdLevel.VERY_LOW.value
    if percentile <= 50:
        return CrowdLevel.LOW.value
    if percentile <= 75:
        return CrowdLevel.MODERATE.value
    if percentile <= 90:
        return CrowdLevel.HIGH.value
    return CrowdLevel.VERY_HIGH.value


def classify_local_condition(percentile: float) -> str:
    if percentile <= 25:
        return LocalCondition.MUCH_QUIETER_THAN_USUAL.value
    if percentile <= 50:
        return LocalCondition.QUIETER_THAN_USUAL.value
    if percentile <= 75:
        return LocalCondition.TYPICAL.value
    if percentile <= 90:
        return LocalCondition.BUSIER_THAN_USUAL.value
    return LocalCondition.MUCH_BUSIER_THAN_USUAL.value


class CurrentActivityService:
    def __init__(
        self,
        repository: CurrentActivityRepository | None = None,
        *,
        timezone_name: str = SETTINGS.app_timezone,
        window_minutes: int = SETTINGS.realtime.minute_ingestion_interval_minutes,
        stale_threshold_minutes: int | None = (
            SETTINGS.realtime.source_cache_stale_after_minutes
        ),
    ) -> None:
        self.repository = repository or CurrentActivityRepository()
        self.timezone_name = timezone_name
        self.window_minutes = window_minutes
        self.stale_threshold_minutes = stale_threshold_minutes

    def build(
        self,
        *,
        sensors: Sequence[CurrentSensorDefinition],
        observations: Sequence[MinuteObservation],
        as_of: datetime,
        source_latest_datetime: datetime | None,
        calculated_at: datetime | None = None,
    ) -> CurrentActivityBuild:
        windows = calculate_windows(
            as_of,
            timezone_name=self.timezone_name,
            window_minutes=self.window_minutes,
        )
        calculated_at = calculated_at or datetime.now(timezone.utc)
        if calculated_at.tzinfo is None or calculated_at.utcoffset() is None:
            raise ValueError("calculated_at must be timezone-aware")

        unique_payloads = {row.payload_hash: row for row in observations}
        groups: dict[tuple[int, datetime], list[MinuteObservation]] = defaultdict(list)
        for row in unique_payloads.values():
            groups[row.logical_key].append(row)
        conflicted_keys = {
            key for key, rows in groups.items() if len(rows) > 1
        }
        valid_rows = tuple(
            rows[0] for key, rows in groups.items() if key not in conflicted_keys
        )

        source_freshness: float | None = None
        if source_latest_datetime is not None:
            if (
                source_latest_datetime.tzinfo is None
                or source_latest_datetime.utcoffset() is None
            ):
                raise ValueError("source_latest_datetime must be timezone-aware")
            source_freshness = max(
                0.0,
                (as_of - source_latest_datetime).total_seconds() / 60.0,
            )
        source_stale = source_latest_datetime is None or (
            self.stale_threshold_minutes is not None
            and source_freshness is not None
            and source_freshness > self.stale_threshold_minutes
        )

        current_by_sensor: dict[int, list[MinuteObservation]] = defaultdict(list)
        hour_by_sensor: dict[int, list[MinuteObservation]] = defaultdict(list)
        for row in valid_rows:
            if windows.current_start <= row.source_sensing_datetime < windows.current_end:
                current_by_sensor[row.location_id].append(row)
            if (
                windows.comparison_start
                <= row.source_sensing_datetime
                < windows.comparison_end
            ):
                hour_by_sensor[row.location_id].append(row)

        current_conflicted_sensors = {
            location_id
            for location_id, sensed_at in conflicted_keys
            if windows.current_start <= sensed_at < windows.current_end
        }
        comparison_minutes = {
            row.source_sensing_datetime
            for row in unique_payloads.values()
            if windows.comparison_start
            <= row.source_sensing_datetime
            < windows.comparison_end
        }
        comparison_complete = len(comparison_minutes) == 60

        eligible = {sensor.location_id for sensor in sensors if sensor.modelling_eligible}
        current_counts = {
            location_id: sum(row.total_of_directions for row in rows)
            for location_id, rows in current_by_sensor.items()
            if location_id in eligible and not source_stale
        }
        current_percentiles = {
            location_id: empirical_cdf(count, tuple(current_counts.values()))
            for location_id, count in current_counts.items()
        }

        comparison_counts: dict[int, int] = {}
        if comparison_complete:
            comparison_counts = {
                location_id: sum(row.total_of_directions for row in rows)
                for location_id, rows in hour_by_sensor.items()
                if location_id in eligible
            }
        local_hour_start = windows.comparison_start.astimezone(
            ZoneInfo(self.timezone_name)
        )
        day_type = "Weekday" if local_hour_start.isoweekday() < 6 else "Weekend"
        historical = self.repository.calculate_historical_percentiles(
            comparison_counts,
            hour_day=local_hour_start.hour,
            day_type=day_type,
        )

        records: list[CurrentSensorActivityRecord] = []
        for sensor in sorted(sensors, key=lambda value: value.location_id):
            location_id = sensor.location_id
            current_rows = current_by_sensor.get(location_id, [])
            hour_rows = hour_by_sensor.get(location_id, [])
            if not sensor.modelling_eligible:
                data_state = DataState.NO_DATA.value
            elif source_stale:
                data_state = DataState.STALE.value
            elif current_rows:
                data_state = DataState.OK.value
            elif location_id in current_conflicted_sensors:
                data_state = DataState.CONFLICTED.value
            else:
                data_state = DataState.AMBIGUOUS_NO_RECORD.value

            current_count = (
                current_counts.get(location_id)
                if data_state == DataState.OK.value
                else None
            )
            current_percentile = (
                current_percentiles.get(location_id)
                if data_state == DataState.OK.value
                else None
            )
            hour_count = comparison_counts.get(location_id)
            historical_score = historical.get(location_id)
            network_history = (
                historical_score.network if historical_score is not None else None
            )
            local_history = (
                historical_score.local if historical_score is not None else None
            )
            if not sensor.modelling_eligible or source_stale:
                hour_count = None
                network_history = None
                local_history = None

            records.append(
                CurrentSensorActivityRecord(
                    location_id=location_id,
                    current_15m_window_start=windows.current_start,
                    current_15m_window_end=windows.current_end,
                    current_15m_observed_rows=(
                        len(current_rows) if sensor.modelling_eligible else None
                    ),
                    current_15m_count=current_count,
                    current_15m_network_percentile=current_percentile,
                    current_crowd_exposure_score=current_percentile,
                    current_crowd_level=(
                        classify_crowd_level(current_percentile)
                        if current_percentile is not None
                        else None
                    ),
                    comparison_hour_start=windows.comparison_start,
                    current_1h_observed_rows=(
                        len(hour_rows)
                        if sensor.modelling_eligible and comparison_complete
                        else None
                    ),
                    current_1h_count=hour_count,
                    current_1h_network_historical_percentile=network_history,
                    current_1h_local_historical_percentile=local_history,
                    current_local_condition=(
                        classify_local_condition(local_history)
                        if local_history is not None
                        else None
                    ),
                    data_state=data_state,
                    calculated_at=calculated_at,
                )
            )

        return CurrentActivityBuild(
            windows=windows,
            records=tuple(records),
            eligible_sensor_count=len(eligible),
            observed_current_sensor_count=sum(
                row.data_state == DataState.OK.value for row in records
            ),
            ambiguous_sensor_count=sum(
                row.data_state == DataState.AMBIGUOUS_NO_RECORD.value
                for row in records
            ),
            stale_sensor_count=sum(
                row.data_state == DataState.STALE.value for row in records
            ),
            conflicted_sensor_count=sum(
                row.data_state == DataState.CONFLICTED.value for row in records
            ),
            no_data_sensor_count=sum(
                row.data_state == DataState.NO_DATA.value for row in records
            ),
            conflict_group_count=len(conflicted_keys),
            comparison_hour_complete=comparison_complete,
            comparison_distinct_minute_count=len(comparison_minutes),
            local_historical_available_count=sum(
                row.current_1h_local_historical_percentile is not None
                for row in records
            ),
            network_historical_available_count=sum(
                row.current_1h_network_historical_percentile is not None
                for row in records
            ),
            current_network_available_count=len(current_percentiles),
            source_latest_datetime=source_latest_datetime,
            source_freshness_minutes=source_freshness,
            stale_threshold_minutes=self.stale_threshold_minutes,
        )
