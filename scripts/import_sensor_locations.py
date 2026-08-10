"""Import current City of Melbourne sensor metadata into CalmWay."""

import argparse
from collections.abc import Mapping
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.db import CalmWayDatabaseError, dispose_engine  # noqa: E402
from backend.app.repositories.sensor_repository import (  # noqa: E402
    SensorRepository,
    inspect_sensor_import,
)
from backend.app.services.ingestion.city_sensor_client import (  # noqa: E402
    CityDataError,
    CitySensorLocationClient,
)
from backend.app.services.ingestion.sensor_location_ingestion import (  # noqa: E402
    SensorIngestionError,
    SensorLocationIngestionService,
)


def _format_counts(counts: Mapping[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{reason}={count}" for reason, count in sorted(counts.items()))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import the official current pedestrian sensor locations."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and validate the live source without writing to PostgreSQL.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        with CitySensorLocationClient() as client:
            repository = None if args.dry_run else SensorRepository()
            service = SensorLocationIngestionService(client, repository)
            result = service.run(dry_run=args.dry_run)

        validation = result.validation
        valid_locations = sum(
            record.has_usable_location for record in validation.records
        )
        print("API strategy: records endpoint with ordered offset pagination")
        print(f"Observed source fields: {', '.join(result.snapshot.observed_fields)}")
        print("Identifier mapping: location_id -> sensor.location_id")
        print("Geometry mapping: longitude=X, latitude=Y, SRID=4326")
        print(f"Source records fetched: {len(result.snapshot.records)}")
        print(f"Valid sensors: {len(validation.records)}")
        print(f"Valid current locations: {valid_locations}")
        print(f"Records skipped: {len(validation.skipped_records)}")
        print(f"Record skip reasons: {_format_counts(validation.skip_reason_counts)}")
        print(f"Locations skipped: {len(validation.skipped_locations)}")
        print(
            "Location skip reasons: "
            f"{_format_counts(validation.location_skip_reason_counts)}"
        )
        print(f"Validation warnings: {len(validation.warnings)}")

        if args.dry_run:
            print("Database writes: none (--dry-run)")
            print("Import status: DRY RUN OK")
            return 0

        write_result = result.write_result
        if write_result is None:
            raise SensorIngestionError("Database write result was not produced.")
        print(f"Sensors inserted: {write_result.sensors_inserted}")
        print(f"Sensors updated: {write_result.sensors_updated}")
        print(f"Locations inserted: {write_result.locations_inserted}")
        print(f"Locations updated: {write_result.locations_updated}")
        print(f"Unusable current locations removed: {write_result.locations_removed}")

        verification = inspect_sensor_import(validation.records)
        print(f"Database sensor rows: {verification.sensor_count}")
        print(f"Database current-location rows: {verification.location_count}")
        print(f"Duplicate sensor IDs: {verification.duplicate_sensor_ids}")
        print(f"Invalid geometry SRIDs: {verification.invalid_srid_count}")
        print(
            "Geometry coordinate-order mismatches: "
            f"{verification.coordinate_order_mismatch_count}"
        )
        print(
            "Coordinates outside Melbourne sanity bounds: "
            f"{verification.outside_melbourne_bounds_count}"
        )
        print(f"Stored status values: {verification.status_values}")
        if not verification.ok:
            raise SensorIngestionError(
                "Post-import sensor/location verification did not pass."
            )
        print("Import status: OK")
        return 0
    except (CalmWayDatabaseError, CityDataError, SensorIngestionError) as exc:
        print(f"Sensor-location import: FAILED - {exc}", file=sys.stderr)
        return 1
    finally:
        dispose_engine()


if __name__ == "__main__":
    raise SystemExit(main())
