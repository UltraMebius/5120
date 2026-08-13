"""One bounded City-to-raw-to-current refresh, with a read-only dry-run path."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
from typing import TypeVar
from zoneinfo import ZoneInfo

from ...models.minute import MinuteObservation
from ...repositories.current_activity_repository import CurrentActivityRepository
from ...repositories.minute_repository import MinuteRepository, MinuteWriteResult
from ..crowd.current_activity_service import (
    CurrentActivityBuild,
    CurrentActivityService,
    calculate_windows,
)
from .city_minute_client import CityMinuteCountClient, CityMinuteSnapshot
from .minute_ingestion import MinuteTransformResult, transform_minute_records


_LOGGER = logging.getLogger(__name__)
_ResultT = TypeVar("_ResultT")


def _run_diagnostic_stage(
    stage: str,
    operation: Callable[[], _ResultT],
) -> _ResultT:
    """Log only a safe stage and exception class before preserving the error."""

    try:
        return operation()
    except Exception as exc:
        _LOGGER.error(
            "current_activity_refresh_failed "
            "refresh_stage=%s exception_type=%s",
            stage,
            type(exc).__name__,
        )
        raise


@dataclass(frozen=True)
class RawRefreshSummary:
    ingestion_run_id: int | None
    rows_received: int
    rows_inserted: int
    rows_skipped_exact_duplicate: int
    unknown_sensor_rows: int
    unknown_sensor_ids: tuple[int, ...]
    conflict_groups_detected: int


class NoCompleteSourceWindowError(ValueError):
    """The fetched valid source rows contain no complete fixed current window."""


@dataclass(frozen=True)
class CompleteSourceWindow:
    start: datetime
    end: datetime
    latest_source_observation: datetime
    distinct_minute_count: int
    complete_windows_considered: int
    incomplete_windows_skipped: int


def select_latest_complete_source_window(
    observations: tuple[MinuteObservation, ...],
    *,
    snapshot_start: datetime,
    snapshot_end: datetime,
    timezone_name: str,
    window_minutes: int,
) -> CompleteSourceWindow:
    """Return the newest globally complete source-backed fixed minute window."""

    if window_minutes <= 0 or 60 % window_minutes:
        raise ValueError("window_minutes must be a positive divisor of 60")
    for value, name in (
        (snapshot_start, "snapshot_start"),
        (snapshot_end, "snapshot_end"),
    ):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{name} must be timezone-aware")
    search_start = snapshot_start.astimezone(timezone.utc)
    search_end = snapshot_end.astimezone(timezone.utc)
    if search_end <= search_start:
        raise ValueError("snapshot_end must be after snapshot_start")

    valid_timestamps = tuple(
        row.source_sensing_datetime.astimezone(timezone.utc)
        for row in observations
        if search_start
        <= row.source_sensing_datetime.astimezone(timezone.utc)
        < search_end
    )
    if not valid_timestamps:
        raise NoCompleteSourceWindowError(
            "No valid source timestamps are available in the fetched snapshot."
        )

    latest_source = max(valid_timestamps)
    source_minute_buckets = {
        value.replace(second=0, microsecond=0) for value in valid_timestamps
    }
    local_latest = latest_source.astimezone(ZoneInfo(timezone_name))
    candidate_end = local_latest.replace(
        minute=(local_latest.minute // window_minutes) * window_minutes,
        second=0,
        microsecond=0,
    ).astimezone(timezone.utc)
    interval = timedelta(minutes=window_minutes)
    incomplete_windows = 0

    while candidate_end - interval >= search_start:
        candidate_start = candidate_end - interval
        distinct_minutes = sum(
            candidate_start + timedelta(minutes=offset)
            in source_minute_buckets
            for offset in range(window_minutes)
        )
        if distinct_minutes == window_minutes:
            return CompleteSourceWindow(
                start=candidate_start,
                end=candidate_end,
                latest_source_observation=latest_source,
                distinct_minute_count=distinct_minutes,
                complete_windows_considered=1,
                incomplete_windows_skipped=incomplete_windows,
            )
        incomplete_windows += 1
        candidate_end = candidate_start

    raise NoCompleteSourceWindowError(
        "No complete source-backed current window exists in the fetched snapshot."
    )


@dataclass(frozen=True)
class CurrentActivityRefreshResult:
    dry_run: bool
    as_of: datetime
    snapshot: CityMinuteSnapshot
    transform: MinuteTransformResult
    source_observation_minimum: datetime | None
    source_observation_maximum: datetime | None
    distinct_source_sensor_count: int
    source_lag_seconds: float
    selected_window_start: datetime
    selected_window_end: datetime
    selected_window_distinct_minutes: int
    complete_windows_considered: int
    incomplete_windows_skipped: int
    raw: RawRefreshSummary
    activity: CurrentActivityBuild
    current_rows_written: int


class CurrentActivityRefreshService:
    SOURCE_NAME = "city_past_hour_counts_per_minute"

    def __init__(
        self,
        *,
        client: CityMinuteCountClient | None = None,
        minute_repository: MinuteRepository | None = None,
        current_repository: CurrentActivityRepository | None = None,
        activity_service: CurrentActivityService | None = None,
    ) -> None:
        self.client = client or CityMinuteCountClient()
        self.minute_repository = minute_repository or MinuteRepository()
        self.current_repository = current_repository or CurrentActivityRepository()
        self.activity_service = activity_service or CurrentActivityService(
            self.current_repository
        )

    @staticmethod
    def _preview_raw_summary(
        observations: tuple[MinuteObservation, ...],
        existing: tuple[MinuteObservation, ...],
        unknown_ids: set[int],
        *,
        rows_received: int,
        conflict_groups: int,
    ) -> RawRefreshSummary:
        eligible = [
            row for row in observations if row.location_id not in unknown_ids
        ]
        existing_hashes = {row.payload_hash for row in existing}
        unique_candidate_hashes = {row.payload_hash for row in eligible}
        inserted = len(unique_candidate_hashes - existing_hashes)
        return RawRefreshSummary(
            ingestion_run_id=None,
            rows_received=rows_received,
            rows_inserted=inserted,
            rows_skipped_exact_duplicate=len(eligible) - inserted,
            unknown_sensor_rows=sum(
                row.location_id in unknown_ids for row in observations
            ),
            unknown_sensor_ids=tuple(sorted(unknown_ids)),
            conflict_groups_detected=conflict_groups,
        )

    @staticmethod
    def _write_summary(result: MinuteWriteResult) -> RawRefreshSummary:
        return RawRefreshSummary(
            ingestion_run_id=result.ingestion_run_id,
            rows_received=result.rows_received,
            rows_inserted=result.rows_inserted,
            rows_skipped_exact_duplicate=result.rows_skipped_exact_duplicate,
            unknown_sensor_rows=result.unknown_sensor_rows,
            unknown_sensor_ids=result.unknown_sensor_ids,
            conflict_groups_detected=result.conflict_groups_detected,
        )

    def refresh(
        self, *, as_of: datetime, dry_run: bool = False
    ) -> CurrentActivityRefreshResult:
        windows = _run_diagnostic_stage(
            "discover_window",
            lambda: calculate_windows(
                as_of,
                timezone_name=self.activity_service.timezone_name,
                window_minutes=self.activity_service.window_minutes,
            ),
        )
        fetch_start = min(windows.comparison_start, windows.current_start)
        snapshot = _run_diagnostic_stage(
            "fetch_pages",
            lambda: self.client.fetch_snapshot(
                start=fetch_start,
                end=windows.current_end,
            ),
        )
        transformed = _run_diagnostic_stage(
            "transform",
            lambda: transform_minute_records(
                snapshot.records,
                as_of=as_of,
            ),
        )
        observations = transformed.observations
        source_minimum = min(
            (row.source_sensing_datetime for row in observations), default=None
        )
        source_maximum = max(
            (row.source_sensing_datetime for row in observations), default=None
        )
        selected_window = _run_diagnostic_stage(
            "select_current_window",
            lambda: select_latest_complete_source_window(
                observations,
                snapshot_start=snapshot.requested_start,
                snapshot_end=snapshot.requested_end,
                timezone_name=self.activity_service.timezone_name,
                window_minutes=self.activity_service.window_minutes,
            ),
        )
        source_lag_seconds = max(
            0.0,
            (
                as_of - selected_window.latest_source_observation
            ).total_seconds(),
        )
        _LOGGER.info(
            "current_activity_source_window as_of=%s "
            "latest_source_observation=%s source_lag_seconds=%.3f "
            "selected_window_start=%s selected_window_end=%s "
            "selected_window_distinct_minutes=%d "
            "complete_windows_considered=%d "
            "incomplete_windows_skipped=%d",
            as_of.isoformat(),
            selected_window.latest_source_observation.isoformat(),
            source_lag_seconds,
            selected_window.start.isoformat(),
            selected_window.end.isoformat(),
            selected_window.distinct_minute_count,
            selected_window.complete_windows_considered,
            selected_window.incomplete_windows_skipped,
        )
        unknown_ids = _run_diagnostic_stage(
            "reconcile_sensors",
            lambda: self.minute_repository.find_unknown_sensor_ids(
                {row.location_id for row in observations}
            ),
        )

        if dry_run:
            existing = _run_diagnostic_stage(
                "load_calculation_interval",
                lambda: self.minute_repository.load_observations(
                    start=fetch_start, end=windows.current_end
                ),
            )
            known_candidates = tuple(
                row for row in observations if row.location_id not in unknown_ids
            )
            combined_by_hash = {
                row.payload_hash: row for row in (*existing, *known_candidates)
            }
            calculation_rows = tuple(combined_by_hash.values())
            grouped_keys: dict[tuple[int, datetime], set[str]] = {}
            for row in calculation_rows:
                grouped_keys.setdefault(row.logical_key, set()).add(row.payload_hash)
            conflict_groups = sum(
                len(hashes) > 1 for hashes in grouped_keys.values()
            )
            raw_summary = self._preview_raw_summary(
                observations,
                existing,
                unknown_ids,
                rows_received=snapshot.total_count,
                conflict_groups=conflict_groups,
            )
        else:
            write = _run_diagnostic_stage(
                "persist_raw",
                lambda: self.minute_repository.ingest(
                    observations,
                    source_name=self.SOURCE_NAME,
                    rows_received=snapshot.total_count,
                    interval_start=fetch_start,
                    interval_end=windows.current_end,
                    metadata={
                        "requested_start": snapshot.requested_start.isoformat(),
                        "requested_end": snapshot.requested_end.isoformat(),
                        "source_minimum_datetime": (
                            source_minimum.isoformat()
                            if source_minimum
                            else None
                        ),
                        "source_latest_datetime": (
                            source_maximum.isoformat()
                            if source_maximum
                            else None
                        ),
                        "source_lag_seconds": source_lag_seconds,
                        "selected_window_start": (
                            selected_window.start.isoformat()
                        ),
                        "selected_window_end": selected_window.end.isoformat(),
                        "selected_window_distinct_minutes": (
                            selected_window.distinct_minute_count
                        ),
                        "complete_windows_considered": (
                            selected_window.complete_windows_considered
                        ),
                        "incomplete_windows_skipped": (
                            selected_window.incomplete_windows_skipped
                        ),
                        "source_records_before_end": (
                            snapshot.source_records_before_end
                        ),
                        "invalid_record_count": (
                            transformed.invalid_record_count
                        ),
                        "invalid_reasons": dict(transformed.invalid_reasons),
                        "unknown_sensor_ids": sorted(unknown_ids),
                    },
                ),
            )
            raw_summary = self._write_summary(write)
            calculation_rows = _run_diagnostic_stage(
                "load_calculation_interval",
                lambda: self.minute_repository.load_observations(
                    start=fetch_start, end=windows.current_end
                ),
            )

        sensors = _run_diagnostic_stage(
            "materialize_current_activity",
            self.current_repository.load_current_sensors,
        )
        activity = _run_diagnostic_stage(
            "materialize_current_activity",
            lambda: self.activity_service.build(
                sensors=sensors,
                observations=calculation_rows,
                as_of=as_of,
                source_latest_datetime=(
                    selected_window.latest_source_observation
                ),
                current_window_start=selected_window.start,
                current_window_end=selected_window.end,
            ),
        )

        rows_written = 0
        if not dry_run:
            rows_written = _run_diagnostic_stage(
                "commit",
                lambda: self.current_repository.replace_current_activity(
                    activity.records
                ),
            )

        return CurrentActivityRefreshResult(
            dry_run=dry_run,
            as_of=as_of,
            snapshot=snapshot,
            transform=transformed,
            source_observation_minimum=source_minimum,
            source_observation_maximum=source_maximum,
            distinct_source_sensor_count=len(
                {row.location_id for row in observations}
            ),
            source_lag_seconds=source_lag_seconds,
            selected_window_start=selected_window.start,
            selected_window_end=selected_window.end,
            selected_window_distinct_minutes=(
                selected_window.distinct_minute_count
            ),
            complete_windows_considered=(
                selected_window.complete_windows_considered
            ),
            incomplete_windows_skipped=(
                selected_window.incomplete_windows_skipped
            ),
            raw=raw_summary,
            activity=activity,
            current_rows_written=rows_written,
        )
