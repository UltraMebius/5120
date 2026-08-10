"""Validate, transform, and orchestrate current sensor-location ingestion."""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
import math
from typing import Any

from ...models.sensor import SensorLocationRecord
from ...repositories.sensor_repository import (
    SensorRepository,
    SensorWriteResult,
)
from .city_sensor_client import CitySensorLocationClient, CitySensorSnapshot


class SensorIngestionError(RuntimeError):
    """Raised when a source snapshot has no safe sensor mapping."""


@dataclass(frozen=True)
class ValidationIssue:
    source_index: int
    location_id: int | None
    reason: str


@dataclass(frozen=True)
class SensorValidationResult:
    records: tuple[SensorLocationRecord, ...]
    skipped_records: tuple[ValidationIssue, ...]
    skipped_locations: tuple[ValidationIssue, ...]
    warnings: tuple[ValidationIssue, ...]

    @property
    def skip_reason_counts(self) -> dict[str, int]:
        return dict(Counter(issue.reason for issue in self.skipped_records))

    @property
    def location_skip_reason_counts(self) -> dict[str, int]:
        return dict(Counter(issue.reason for issue in self.skipped_locations))


@dataclass(frozen=True)
class SensorIngestionResult:
    snapshot: CitySensorSnapshot
    validation: SensorValidationResult
    write_result: SensorWriteResult | None
    dry_run: bool


def _parse_location_id(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        numeric_value = float(value)
        integer_value = int(numeric_value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(numeric_value) or numeric_value != integer_value:
        return None
    return integer_value if integer_value > 0 else None


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return None
    text_value = str(value).strip()
    return text_value or None


def _parse_date(value: object) -> date | None:
    text_value = _optional_text(value)
    if text_value is None:
        return None
    try:
        return date.fromisoformat(text_value)
    except ValueError:
        return None


def _parse_coordinate(value: object, minimum: float, maximum: float) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        coordinate = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(coordinate) or not minimum <= coordinate <= maximum:
        return None
    return coordinate


def transform_sensor_records(
    source_records: Sequence[Mapping[str, Any]],
) -> SensorValidationResult:
    """Map live source fields without inventing missing classifications/data."""

    records: list[SensorLocationRecord] = []
    skipped_records: list[ValidationIssue] = []
    skipped_locations: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    seen_ids: set[int] = set()

    for source_index, source in enumerate(source_records):
        location_id = _parse_location_id(source.get("location_id"))
        if location_id is None:
            skipped_records.append(
                ValidationIssue(source_index, None, "missing_or_invalid_location_id")
            )
            continue
        if location_id in seen_ids:
            skipped_records.append(
                ValidationIssue(source_index, location_id, "duplicate_location_id")
            )
            continue
        seen_ids.add(location_id)

        raw_latitude = source.get("latitude")
        raw_longitude = source.get("longitude")
        latitude = _parse_coordinate(raw_latitude, -90.0, 90.0)
        longitude = _parse_coordinate(raw_longitude, -180.0, 180.0)
        location_type = _optional_text(source.get("location_type"))

        location_skip_reason: str | None = None
        if raw_latitude is None or raw_longitude is None:
            location_skip_reason = "missing_coordinates"
        elif latitude is None or longitude is None:
            location_skip_reason = "invalid_coordinates"
        elif location_type is None:
            location_skip_reason = "missing_location_type"
        else:
            nested_location = source.get("location")
            if isinstance(nested_location, Mapping):
                nested_latitude = _parse_coordinate(
                    nested_location.get("lat"), -90.0, 90.0
                )
                nested_longitude = _parse_coordinate(
                    nested_location.get("lon"), -180.0, 180.0
                )
                if (
                    nested_latitude is not None
                    and nested_longitude is not None
                    and (
                        not math.isclose(latitude, nested_latitude, abs_tol=1e-9)
                        or not math.isclose(longitude, nested_longitude, abs_tol=1e-9)
                    )
                ):
                    location_skip_reason = "coordinate_fields_disagree"

        if location_skip_reason is not None:
            skipped_locations.append(
                ValidationIssue(source_index, location_id, location_skip_reason)
            )
            latitude = None
            longitude = None

        installation_date = _parse_date(source.get("installation_date"))
        if source.get("installation_date") and installation_date is None:
            warnings.append(
                ValidationIssue(source_index, location_id, "invalid_installation_date")
            )

        records.append(
            SensorLocationRecord(
                location_id=location_id,
                sensor_description=_optional_text(source.get("sensor_description")),
                sensor_name=_optional_text(source.get("sensor_name")),
                installation_date=installation_date,
                note=_optional_text(source.get("note")),
                location_type=location_type,
                status=_optional_text(source.get("status")),
                direction_1_label=_optional_text(source.get("direction_1")),
                direction_2_label=_optional_text(source.get("direction_2")),
                latitude=latitude,
                longitude=longitude,
            )
        )

    return SensorValidationResult(
        records=tuple(records),
        skipped_records=tuple(skipped_records),
        skipped_locations=tuple(skipped_locations),
        warnings=tuple(warnings),
    )


class SensorLocationIngestionService:
    """Coordinate fetching, pure validation, and one transactional write."""

    def __init__(
        self,
        client: CitySensorLocationClient,
        repository: SensorRepository | None = None,
    ) -> None:
        self.client = client
        self.repository = repository

    def run(self, *, dry_run: bool = False) -> SensorIngestionResult:
        snapshot = self.client.fetch_all()
        validation = transform_sensor_records(snapshot.records)
        if not snapshot.records:
            raise SensorIngestionError(
                "City sensor-location API returned an empty source snapshot."
            )
        if not validation.records:
            raise SensorIngestionError(
                "No source records contained the required location_id field."
            )

        write_result = None
        if not dry_run:
            repository = self.repository or SensorRepository()
            write_result = repository.upsert_sensor_locations(validation.records)

        return SensorIngestionResult(
            snapshot=snapshot,
            validation=validation,
            write_result=write_result,
            dry_run=dry_run,
        )
