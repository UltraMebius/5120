"""Import an explicit bounded range of official hourly pedestrian counts."""

import argparse
from collections.abc import Mapping
from datetime import date
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.config import SETTINGS  # noqa: E402
from backend.app.db import CalmWayDatabaseError, dispose_engine  # noqa: E402
from backend.app.repositories.hourly_count_repository import (  # noqa: E402
    HourlyCountRepository,
    inspect_hourly_import,
)
from backend.app.services.ingestion.city_hourly_client import (  # noqa: E402
    CityHourlyCountClient,
)
from backend.app.services.ingestion.city_sensor_client import (  # noqa: E402
    CityDataError,
)
from backend.app.services.ingestion.hourly_count_ingestion import (  # noqa: E402
    HourlyCountIngestionError,
    HourlyCountIngestionService,
)


def _date_argument(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            "dates must use YYYY-MM-DD format"
        ) from None


def _format_counts(counts: Mapping[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{name}={count}" for name, count in sorted(counts.items()))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Import a bounded City hourly-count range. The handoff does not "
            "define a production default range, so both dates are required."
        )
    )
    parser.add_argument("--start-date", required=True, type=_date_argument)
    parser.add_argument("--end-date", required=True, type=_date_argument)
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Database rows per transaction (default: 1000, maximum: 5000).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Stream and validate the live export without database writes.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.end_date < args.start_date:
        parser.error("--end-date must be on or after --start-date")

    try:
        repository = None
        if not args.dry_run or SETTINGS.database_url.strip():
            repository = HourlyCountRepository()
        with CityHourlyCountClient() as client:
            result = HourlyCountIngestionService(client, repository).run(
                start_date=args.start_date,
                end_date=args.end_date,
                dry_run=args.dry_run,
                batch_size=args.batch_size,
            )

        print(
            "Source strategy: server-filtered streaming official CSV export"
        )
        print(
            "Handoff evidence window: 2024-08-08 to 2026-08-07 "
            "(not declared as a production default)"
        )
        print(f"Date range: {args.start_date} to {args.end_date}")
        print(f"Observed source fields: {', '.join(result.observed_fields)}")
        print("Identifier mapping: location_id -> existing sensor.location_id")
        print(f"Source rows estimated: {result.estimated_source_rows}")
        print(f"Source rows fetched: {result.source_rows_fetched}")
        print(f"Valid source rows: {result.valid_source_rows}")
        print(f"Zero-count rows: {result.zero_count_rows}")
        print(f"Invalid rows skipped: {result.invalid_skipped_rows}")
        print(
            "Invalid skip reasons: "
            f"{_format_counts(result.invalid_skip_reasons)}"
        )
        print(f"Validation warnings: {_format_counts(result.warning_reasons)}")
        if result.reconciliation_performed:
            print(f"Unknown sensor rows skipped: {result.unknown_sensor_rows}")
            print(
                "Unknown historical sensor IDs: "
                + (
                    ", ".join(map(str, result.unknown_sensor_ids))
                    if result.unknown_sensor_ids
                    else "none"
                )
            )
        else:
            print("Unknown sensor reconciliation: not checked (no DATABASE_URL)")

        if args.dry_run:
            print("Database writes: none (--dry-run)")
            print("Import status: DRY RUN OK")
            return 0

        print(f"Database-eligible rows: {result.database_eligible_rows}")
        print(f"Inserted: {result.inserted}")
        print(f"Updated: {result.updated}")
        verification = inspect_hourly_import(args.start_date, args.end_date)
        print(f"Database range rows: {verification.row_count}")
        print(f"Distinct authoritative keys: {verification.distinct_key_count}")
        print(f"Stored zero-count rows: {verification.zero_count_rows}")
        print(
            "Stored date bounds: "
            f"{verification.minimum_date} to {verification.maximum_date}"
        )
        print(f"Invalid stored hours: {verification.invalid_hour_rows}")
        print(f"Negative stored counts: {verification.negative_count_rows}")
        print(
            "Derived Day_Type mismatches: "
            f"{verification.day_type_mismatch_rows}"
        )
        print(
            "Later-phase table rows "
            "(minute/sensor baseline/network baseline/current/spatial): "
            f"{verification.minute_row_count}/"
            f"{verification.sensor_baseline_row_count}/"
            f"{verification.network_baseline_row_count}/"
            f"{verification.current_activity_row_count}/"
            f"{verification.spatial_cache_row_count}"
        )
        if verification.row_count < result.database_eligible_rows:
            raise HourlyCountIngestionError(
                "Database range contains fewer rows than the eligible source."
            )
        if not verification.ok:
            raise HourlyCountIngestionError(
                "Post-import hourly-count verification did not pass."
            )
        print("Import status: OK")
        return 0
    except (CalmWayDatabaseError, CityDataError, HourlyCountIngestionError) as exc:
        print(f"Hourly-count import: FAILED - {exc}", file=sys.stderr)
        return 1
    finally:
        dispose_engine()


if __name__ == "__main__":
    raise SystemExit(main())
