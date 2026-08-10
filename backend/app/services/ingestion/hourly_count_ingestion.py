"""Streaming validation and bounded-batch hourly-count orchestration."""

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
import math
from typing import Any

from ...models.hourly_count import HourlyCountRecord
from ...repositories.hourly_count_repository import (
    HourlyCountRepository,
    HourlyWriteResult,
)
from .city_hourly_client import CityHourlyCountClient


class HourlyCountIngestionError(RuntimeError):
    """Raised when a bounded source import is inconsistent or unsafe."""


@dataclass(frozen=True)
class HourlyTransformResult:
    record: HourlyCountRecord | None
    skip_reason: str | None = None
    warning_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class HourlyIngestionResult:
    start_date: date
    end_date: date
    estimated_source_rows: int
    source_rows_fetched: int
    valid_source_rows: int
    zero_count_rows: int
    invalid_skipped_rows: int
    invalid_skip_reasons: dict[str, int]
    warning_reasons: dict[str, int]
    inserted: int
    updated: int
    unknown_sensor_rows: int
    unknown_sensor_ids: tuple[int, ...]
    reconciliation_performed: bool
    observed_fields: tuple[str, ...]
    dry_run: bool

    @property
    def database_eligible_rows(self) -> int:
        return self.valid_source_rows - self.unknown_sensor_rows


def _parse_integer(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if math.isfinite(value) and value.is_integer() else None
    text_value = str(value).strip()
    if not text_value:
        return None
    try:
        return int(text_value)
    except ValueError:
        return None


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text_value = str(value).strip()
    return text_value or None


def transform_hourly_record(
    source: Mapping[str, Any],
    *,
    start_date: date,
    end_date: date,
) -> HourlyTransformResult:
    location_id = _parse_integer(source.get("location_id"))
    if location_id is None or location_id <= 0:
        return HourlyTransformResult(None, "missing_or_invalid_location_id")

    raw_date = _optional_text(source.get("sensing_date"))
    try:
        sensing_date = date.fromisoformat(raw_date) if raw_date else None
    except ValueError:
        sensing_date = None
    if sensing_date is None:
        return HourlyTransformResult(None, "missing_or_invalid_sensing_date")
    if not start_date <= sensing_date <= end_date:
        return HourlyTransformResult(None, "outside_requested_date_range")

    hour_day = _parse_integer(source.get("hourday"))
    if hour_day is None or not 0 <= hour_day <= 23:
        return HourlyTransformResult(None, "missing_or_invalid_hour")

    raw_count = source.get("pedestriancount")
    if raw_count is None or not str(raw_count).strip():
        return HourlyTransformResult(None, "missing_count")
    total_count = _parse_integer(raw_count)
    if total_count is None:
        return HourlyTransformResult(None, "invalid_count")
    if total_count < 0:
        return HourlyTransformResult(None, "negative_count")

    warnings: list[str] = []
    source_id = _parse_integer(source.get("id"))
    if source.get("id") not in (None, "") and source_id is None:
        warnings.append("invalid_source_id_ignored")

    directions: list[int | None] = []
    for field_name in ("direction_1", "direction_2"):
        raw_direction = source.get(field_name)
        direction = _parse_integer(raw_direction)
        if raw_direction in (None, ""):
            direction = None
        elif direction is None or direction < 0:
            warnings.append(f"invalid_{field_name}_ignored")
            direction = None
        directions.append(direction)

    day_type = "Weekday" if sensing_date.weekday() < 5 else "Weekend"
    return HourlyTransformResult(
        HourlyCountRecord(
            location_id=location_id,
            sensing_date=sensing_date,
            hour_day=hour_day,
            day_type=day_type,
            source_id=source_id,
            direction_1=directions[0],
            direction_2=directions[1],
            total_of_directions=total_count,
            source_sensor_name=_optional_text(source.get("sensor_name")),
            source_location_text=_optional_text(source.get("location")),
        ),
        warning_reasons=tuple(warnings),
    )


class HourlyCountIngestionService:
    def __init__(
        self,
        client: CityHourlyCountClient,
        repository: HourlyCountRepository | None = None,
    ) -> None:
        self.client = client
        self.repository = repository

    def run(
        self,
        *,
        start_date: date,
        end_date: date,
        dry_run: bool = False,
        batch_size: int = 1000,
    ) -> HourlyIngestionResult:
        if end_date < start_date:
            raise HourlyCountIngestionError(
                "end_date must be on or after start_date."
            )
        if not 1 <= batch_size <= 5000:
            raise HourlyCountIngestionError(
                "batch_size must be between 1 and 5000."
            )
        if not dry_run and self.repository is None:
            raise HourlyCountIngestionError(
                "A database repository is required for a real import."
            )

        estimated_rows = self.client.count_records(start_date, end_date)
        source_rows = 0
        valid_rows = 0
        zero_rows = 0
        invalid_reasons: Counter[str] = Counter()
        warning_reasons: Counter[str] = Counter()
        inserted = 0
        updated = 0
        unknown_rows = 0
        unknown_ids: set[int] = set()
        valid_id_counts: Counter[int] = Counter()
        batch: list[HourlyCountRecord] = []
        previous_key: tuple[int, date, int] | None = None

        def flush_batch() -> None:
            nonlocal inserted, updated, unknown_rows
            if not batch or dry_run:
                batch.clear()
                return
            assert self.repository is not None
            write_result: HourlyWriteResult = (
                self.repository.upsert_hourly_counts(batch)
            )
            inserted += write_result.inserted
            updated += write_result.updated
            unknown_rows += write_result.unknown_sensor_rows
            unknown_ids.update(write_result.unknown_sensor_ids)
            batch.clear()

        for source in self.client.iter_records(start_date, end_date):
            source_rows += 1
            transformed = transform_hourly_record(
                source, start_date=start_date, end_date=end_date
            )
            warning_reasons.update(transformed.warning_reasons)
            if transformed.record is None:
                reason = transformed.skip_reason or "unknown_validation_error"
                invalid_reasons[reason] += 1
                continue
            record = transformed.record
            if record.key == previous_key:
                invalid_reasons["duplicate_authoritative_key"] += 1
                continue
            previous_key = record.key
            valid_rows += 1
            valid_id_counts[record.location_id] += 1
            if record.total_of_directions == 0:
                zero_rows += 1
            batch.append(record)
            if len(batch) >= batch_size:
                flush_batch()
        flush_batch()

        if source_rows != estimated_rows:
            raise HourlyCountIngestionError(
                "Filtered CSV row count did not match API total_count; retry the "
                "bounded import to obtain a consistent snapshot."
            )

        reconciliation_performed = self.repository is not None
        if dry_run and self.repository is not None:
            unknown_ids = self.repository.find_unknown_sensor_ids(
                set(valid_id_counts)
            )
            unknown_rows = sum(
                valid_id_counts[location_id] for location_id in unknown_ids
            )

        return HourlyIngestionResult(
            start_date=start_date,
            end_date=end_date,
            estimated_source_rows=estimated_rows,
            source_rows_fetched=source_rows,
            valid_source_rows=valid_rows,
            zero_count_rows=zero_rows,
            invalid_skipped_rows=sum(invalid_reasons.values()),
            invalid_skip_reasons=dict(invalid_reasons),
            warning_reasons=dict(warning_reasons),
            inserted=inserted,
            updated=updated,
            unknown_sensor_rows=unknown_rows,
            unknown_sensor_ids=tuple(sorted(unknown_ids)),
            reconciliation_performed=reconciliation_performed,
            observed_fields=self.client.observed_fields,
            dry_run=dry_run,
        )
