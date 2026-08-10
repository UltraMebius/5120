"""Evaluate one WGS84 point against materialised current sensor activity."""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.db import CalmWayDatabaseError, dispose_engine  # noqa: E402
from backend.app.services.crowd.spatial_crowd_service import (  # noqa: E402
    CoordinateValidationError,
    SpatialCrowdService,
    SpatialDataConsistencyError,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate current handoff-defined crowd support at one point."
    )
    parser.add_argument("--longitude", type=float, required=True)
    parser.add_argument("--latitude", type=float, required=True)
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print contributing sensor IDs, distances, scores, and weights.",
    )
    return parser


def _value(value: object, *, decimals: int = 4) -> str:
    if value is None:
        return "unavailable"
    if isinstance(value, float):
        return f"{value:.{decimals}f}"
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = SpatialCrowdService().evaluate(
            longitude=args.longitude,
            latitude=args.latitude,
        )
        print(f"Point: longitude={result.longitude}, latitude={result.latitude}")
        print(f"Support status: {result.coverage_status}")
        print(f"Sensors in radius: {result.nearby_sensors}")
        print(
            "Active Outdoor sensors in radius: "
            f"{result.nearby_active_outdoor_sensors}"
        )
        print(f"Sensors used: {result.supporting_sensors}")
        print(
            "Nearest valid sensor distance: "
            f"{_value(result.nearest_sensor_distance_m, decimals=2)} m"
        )
        print(f"Maximum support radius used: {result.support_radius_m:.0f} m")
        print(f"Weighted exposure: {_value(result.crowd_exposure_score)}")
        print(f"Crowd level: {_value(result.crowd_level)}")
        print(f"Local Condition score: {_value(result.local_condition_score)}")
        print(f"Local Condition: {_value(result.local_condition)}")
        print(f"Weighting: {result.weighting_method}")
        print(
            "Source window: "
            f"[{_value(result.source_window_start)}, "
            f"{_value(result.source_window_end)})"
        )
        print(f"Current materialisation updated at: {_value(result.updated_at)}")
        if result.updated_at is not None:
            age_minutes = max(
                0.0,
                (
                    datetime.now(timezone.utc) - result.updated_at
                ).total_seconds()
                / 60.0,
            )
            print(
                f"Current cache age: {age_minutes:.2f} minutes; "
                "no Phase 2D stale threshold invented"
            )
        if result.reason is not None:
            print(f"Reason: {result.reason}")
        if args.debug:
            if not result.contributions:
                print("Contributors: none")
            for contribution in result.contributions:
                print(
                    "Contributor: "
                    f"location_id={contribution.location_id}, "
                    f"distance_m={contribution.distance_m:.3f}, "
                    f"weight={contribution.normalised_weight:.8f}, "
                    f"crowd_score={contribution.crowd_exposure_score:.4f}, "
                    "local_score="
                    f"{_value(contribution.local_condition_score)}"
                )
        print("Status: OK")
        return 0
    except (
        CalmWayDatabaseError,
        CoordinateValidationError,
        SpatialDataConsistencyError,
        ValueError,
    ) as exc:
        print(f"Point crowd evaluation: FAILED - {exc}", file=sys.stderr)
        return 1
    finally:
        dispose_engine()


if __name__ == "__main__":
    raise SystemExit(main())
