"""One bounded City-to-raw-to-current refresh, with a read-only dry-run path."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import TypeVar

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


@dataclass(frozen=True)
class CurrentActivityRefreshResult:
    dry_run: bool
    as_of: datetime
    snapshot: CityMinuteSnapshot
    transform: MinuteTransformResult
    source_observation_minimum: datetime | None
    source_observation_maximum: datetime | None
    distinct_source_sensor_count: int
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
                            snapshot.source_minimum_datetime.isoformat()
                            if snapshot.source_minimum_datetime
                            else None
                        ),
                        "source_latest_datetime": (
                            snapshot.source_latest_datetime.isoformat()
                            if snapshot.source_latest_datetime
                            else None
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
                source_latest_datetime=snapshot.source_latest_datetime,
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

        source_minimum = min(
            (row.source_sensing_datetime for row in observations), default=None
        )
        source_maximum = max(
            (row.source_sensing_datetime for row in observations), default=None
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
            raw=raw_summary,
            activity=activity,
            current_rows_written=rows_written,
        )
