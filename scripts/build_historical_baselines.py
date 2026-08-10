"""Inspect or build the frozen Phase 2B historical baselines."""

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.db import CalmWayDatabaseError, dispose_engine  # noqa: E402
from backend.app.repositories.baseline_repository import (  # noqa: E402
    TrainingDataSummary,
)
from backend.app.services.baseline.historical_baseline_service import (  # noqa: E402
    ACTIVE_SENSOR_STATUS,
    HISTORICAL_MODELLING_LOCATION_TYPE,
    LOCAL_BASELINE_EXCLUDED_LOCATION_IDS,
    OBSERVED_UNRESOLVED_LOCATION_IDS,
    SENSOR_37_LOCAL_START_DATE,
    TEAM_KNOWN_UNRESOLVED_LOCATION_IDS,
    TRAINING_END_DATE,
    TRAINING_START_DATE,
    HistoricalBaselineError,
    HistoricalBaselineService,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build Local and Network baselines for the frozen inclusive "
            "2024-08-10 to 2026-02-07 training window."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate source coverage and eligibility without baseline writes.",
    )
    return parser


def _print_source(summary: TrainingDataSummary) -> None:
    print(f"Training window: {TRAINING_START_DATE} to {TRAINING_END_DATE} inclusive")
    print(
        "Modelling eligibility: authoritative "
        f"{ACTIVE_SENSOR_STATUS}-status {HISTORICAL_MODELLING_LOCATION_TYPE} sensors"
    )
    print(f"Training rows: {summary.total_training_rows}")
    print(
        "Training coverage: "
        f"{summary.minimum_date} to {summary.maximum_date}; "
        f"dates={summary.distinct_date_count}, "
        f"hours={summary.distinct_hour_count}, "
        f"day_types={','.join(summary.day_types)}"
    )
    print(
        "Raw training population: "
        f"sensors={summary.distinct_sensor_count}, "
        f"Outdoor rows={summary.outdoor_rows}, Indoor rows={summary.indoor_rows}"
    )
    print(
        "Eligible modelling population: "
        f"sensors={summary.eligible_sensor_count}, "
        f"observations={summary.eligible_observation_count}"
    )
    print(
        "Local-baseline population: "
        f"sensors={summary.local_baseline_sensor_count}, "
        f"observations={summary.local_observation_count}"
    )
    print(f"Legitimate zero-count rows retained: {summary.zero_count_rows}")
    print(
        "Excluded unresolved source IDs: "
        + ", ".join(map(str, OBSERVED_UNRESOLVED_LOCATION_IDS))
        + " (team-known: "
        + ", ".join(map(str, TEAM_KNOWN_UNRESOLVED_LOCATION_IDS))
        + "; ID 65 discovered by the full-window dry run)"
    )
    print(
        "Unresolved rows stored in pedestrian_hourly_count: "
        f"{summary.unresolved_stored_rows}"
    )
    print(
        "Local relocation exclusions: "
        + ", ".join(map(str, LOCAL_BASELINE_EXCLUDED_LOCATION_IDS))
    )
    print(
        "Sensor 14: full window; "
        f"observations={summary.sensor_14_observation_count}, "
        f"coverage={summary.sensor_14_minimum_date} to "
        f"{summary.sensor_14_maximum_date}"
    )
    print(
        f"Sensor 37: Local starts {SENSOR_37_LOCAL_START_DATE}; "
        f"included={summary.sensor_37_local_observation_count}, "
        f"pre-cut rows excluded={summary.sensor_37_local_excluded_rows}"
    )
    print(
        "Rows from 47/181 excluded from Local but retained for Network: "
        f"{summary.relocation_local_excluded_rows}"
    )


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    service = HistoricalBaselineService()
    try:
        source = service.inspect_source()
        _print_source(source)
        if args.dry_run:
            print("Baseline table writes: none (--dry-run)")
            print("Status: DRY RUN OK")
            return 0

        result = service.build()
        verification = result.verification
        print(
            "Rebuild strategy: transactional replacement of only "
            "sensor_hour_daytype_baseline and network_hour_daytype_baseline"
        )
        print(f"Local baseline rows written: {result.write.local_rows_written}")
        print(f"Network baseline rows written: {result.write.network_rows_written}")
        print(f"Local baseline sensors: {verification.local_sensor_count}")
        print(
            "Network key coverage: "
            f"hours={verification.network_hour_count}, "
            f"day_types={verification.network_day_type_count}, "
            f"keys={verification.network_row_count}"
        )
        print(
            "Logical checksums: "
            f"local={verification.local_logical_checksum}, "
            f"network={verification.network_logical_checksum}"
        )
        print(
            "Eligible zero-count observations verified: "
            f"{verification.eligible_zero_count_rows}"
        )
        print("Status: OK")
        return 0
    except (CalmWayDatabaseError, HistoricalBaselineError) as exc:
        print(f"Historical baseline build: FAILED - {exc}", file=sys.stderr)
        return 1
    finally:
        dispose_engine()


if __name__ == "__main__":
    raise SystemExit(main())
