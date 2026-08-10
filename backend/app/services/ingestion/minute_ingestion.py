"""Strict transformation of City minute rows into the raw storage contract."""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from ...config import SETTINGS
from ...models.minute import MinuteObservation


class MinuteRecordError(ValueError):
    """A source row cannot be represented safely in the authoritative raw table."""


@dataclass(frozen=True)
class MinuteTransformResult:
    observations: tuple[MinuteObservation, ...]
    invalid_record_count: int
    invalid_reasons: tuple[tuple[str, int], ...]


def _integer(value: object, field: str, *, optional: bool = False) -> int | None:
    if value is None and optional:
        return None
    if isinstance(value, bool):
        raise MinuteRecordError(f"{field}_invalid")
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        raise MinuteRecordError(f"{field}_invalid") from None
    if str(value).strip() not in {str(parsed), f"+{parsed}"}:
        raise MinuteRecordError(f"{field}_invalid")
    if parsed < 0:
        raise MinuteRecordError(f"{field}_negative")
    return parsed


def _aware_datetime(value: object) -> datetime:
    if value is None:
        raise MinuteRecordError("sensing_datetime_missing")
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        raise MinuteRecordError("sensing_datetime_invalid") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise MinuteRecordError("sensing_datetime_missing_offset")
    return parsed


def _source_date(value: object) -> date:
    try:
        return date.fromisoformat(str(value).strip())
    except (TypeError, ValueError):
        raise MinuteRecordError("sensing_date_invalid") from None


def _source_time(value: object) -> time:
    try:
        return time.fromisoformat(str(value).strip())
    except (TypeError, ValueError):
        raise MinuteRecordError("sensing_time_invalid") from None


def transform_minute_record(
    source: Mapping[str, Any],
    *,
    as_of: datetime,
    timezone_name: str = SETTINGS.app_timezone,
) -> MinuteObservation:
    """Validate one row; an absent row is never synthesized by this function."""

    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")
    location_id = _integer(source.get("location_id"), "location_id")
    source_datetime = _aware_datetime(source.get("sensing_datetime"))
    if source_datetime > as_of:
        raise MinuteRecordError("future_sensing_datetime")

    local_datetime = source_datetime.astimezone(ZoneInfo(timezone_name))
    supplied_date = _source_date(source.get("sensing_date"))
    supplied_time = _source_time(source.get("sensing_time"))
    if supplied_date != local_datetime.date():
        raise MinuteRecordError("sensing_date_mismatch")
    if supplied_time.replace(tzinfo=None) != local_datetime.time().replace(tzinfo=None):
        raise MinuteRecordError("sensing_time_mismatch")

    direction_1 = _integer(source.get("direction_1"), "direction_1", optional=True)
    direction_2 = _integer(source.get("direction_2"), "direction_2", optional=True)
    total = _integer(source.get("total_of_directions"), "total_of_directions")
    if direction_1 is not None and direction_2 is not None:
        if direction_1 + direction_2 != total:
            raise MinuteRecordError("direction_total_mismatch")

    return MinuteObservation.create(
        location_id=int(location_id),
        source_sensing_datetime=source_datetime,
        sensing_date_local=local_datetime.date(),
        sensing_time_local=local_datetime.time().replace(tzinfo=None),
        direction_1=direction_1,
        direction_2=direction_2,
        total_of_directions=int(total),
    )


def transform_minute_records(
    records: Sequence[Mapping[str, Any]],
    *,
    as_of: datetime,
    timezone_name: str = SETTINGS.app_timezone,
) -> MinuteTransformResult:
    observations: list[MinuteObservation] = []
    reasons: Counter[str] = Counter()
    for record in records:
        try:
            observations.append(
                transform_minute_record(
                    record,
                    as_of=as_of,
                    timezone_name=timezone_name,
                )
            )
        except MinuteRecordError as exc:
            reasons[str(exc)] += 1
    return MinuteTransformResult(
        observations=tuple(observations),
        invalid_record_count=sum(reasons.values()),
        invalid_reasons=tuple(sorted(reasons.items())),
    )
