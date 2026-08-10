"""Fetch, ingest, and materialise Phase 2C current sensor activity."""

import argparse
from datetime import datetime
from pathlib import Path
import sys
from zoneinfo import ZoneInfo


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.config import SETTINGS  # noqa: E402
from backend.app.db import CalmWayDatabaseError, dispose_engine  # noqa: E402
from backend.app.repositories.current_activity_repository import (  # noqa: E402
    CurrentActivityRepository,
)
from backend.app.services.ingestion.city_sensor_client import (  # noqa: E402
    CityDataError,
)
from backend.app.services.ingestion.current_activity_refresh import (  # noqa: E402
    CurrentActivityRefreshService,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Refresh the authoritative Phase 2C sensor activity layer."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch, parse, inspect, and calculate without database writes.",
    )
    parser.add_argument(
        "--as-of",
        help="Offset-aware ISO timestamp used to freeze window boundaries.",
    )
    return parser


def _as_of(raw: str | None) -> datetime:
    if raw is None:
        return datetime.now(ZoneInfo(SETTINGS.app_timezone))
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("--as-of must be a valid ISO timestamp") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("--as-of must include a UTC offset or Z")
    return parsed


def _format(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return "unavailable" if value is None else str(value)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    service = CurrentActivityRefreshService()
    try:
        as_of = _as_of(args.as_of)
        result = service.refresh(as_of=as_of, dry_run=args.dry_run)
        activity = result.activity
        print(f"Dataset: {service.client.dataset_id}")
        print(f"As of: {as_of.isoformat()}")
        print(
            "Calculation fetch interval: "
            f"[{result.snapshot.requested_start.isoformat()}, "
            f"{result.snapshot.requested_end.isoformat()})"
        )
        print(f"Source records fetched: {result.snapshot.total_count}")
        print(
            "Observed source time range: "
            f"{_format(result.source_observation_minimum)} to "
            f"{_format(result.source_observation_maximum)}"
        )
        print(
            "Latest source timestamp before window end: "
            f"{_format(result.snapshot.source_latest_datetime)}"
        )
        print(
            "Source freshness: "
            + (
                f"{activity.source_freshness_minutes:.2f} minutes"
                if activity.source_freshness_minutes is not None
                else "unavailable"
            )
            + (
                "; operational SLA not configured"
                if activity.stale_threshold_minutes is None
                else f"; SLA={activity.stale_threshold_minutes} minutes"
            )
        )
        print(f"Source sensors observed: {result.distinct_source_sensor_count}")
        print(f"Invalid source records excluded: {result.transform.invalid_record_count}")
        if result.transform.invalid_reasons:
            print(f"Invalid reasons: {dict(result.transform.invalid_reasons)}")
        print(f"Raw rows inserted: {result.raw.rows_inserted}")
        print(
            "Raw exact duplicates skipped: "
            f"{result.raw.rows_skipped_exact_duplicate}"
        )
        print(f"Raw conflict groups in interval: {result.raw.conflict_groups_detected}")
        print(
            "Unknown live location IDs: "
            + (
                ", ".join(map(str, result.raw.unknown_sensor_ids))
                if result.raw.unknown_sensor_ids
                else "none"
            )
        )
        print(f"Eligible current sensors: {activity.eligible_sensor_count}")
        print(f"Observed current sensors: {activity.observed_current_sensor_count}")
        print(f"AMBIGUOUS_NO_RECORD sensors: {activity.ambiguous_sensor_count}")
        print(f"Conflicted-only current sensors: {activity.conflicted_sensor_count}")
        print(f"Stale/unavailable sensors: {activity.stale_sensor_count}")
        print(f"Indoor/ineligible NO_DATA sensors: {activity.no_data_sensor_count}")
        print(
            "Previous hour coverage: "
            f"{activity.comparison_distinct_minute_count}/60 distinct minutes; "
            f"complete={activity.comparison_hour_complete}"
        )
        print(
            "Local historical comparison available: "
            f"{activity.local_historical_available_count}"
        )
        print(
            "Network historical comparison available: "
            f"{activity.network_historical_available_count}"
        )
        print(
            "Current Network comparison available: "
            f"{activity.current_network_available_count}"
        )
        print(f"Current activity rows written: {result.current_rows_written}")
        if args.dry_run:
            print("Database writes: none (--dry-run)")
            print("Status: DRY RUN OK")
        else:
            verification = CurrentActivityRepository().inspect_current_activity()
            print(f"Current logical checksum: {verification.logical_checksum}")
            print(f"Current verification: {'OK' if verification.ok else 'FAILED'}")
            print("Status: OK" if verification.ok else "Status: FAILED")
            return 0 if verification.ok else 1
        return 0
    except (CalmWayDatabaseError, CityDataError, ValueError) as exc:
        print(f"Current activity refresh: FAILED - {exc}", file=sys.stderr)
        return 1
    finally:
        service.client.close()
        dispose_engine()


if __name__ == "__main__":
    raise SystemExit(main())
