"""Evaluate stored route samples against current local PostGIS crowd state."""

import argparse
from collections import Counter
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "flinders_to_melbourne_central_geometry.json"
)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.db import CalmWayDatabaseError, dispose_engine  # noqa: E402
from backend.app.services.crowd.spatial_crowd_service import (  # noqa: E402
    CoordinateValidationError,
    SpatialDataConsistencyError,
)
from backend.app.services.routing.route_crowd_evaluation_service import (  # noqa: E402
    RouteCrowdEvaluationService,
    RouteSampleCrowdResult,
)
from backend.app.services.routing.route_sampling_service import (  # noqa: E402
    RouteSamplingError,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Sample an existing GeoJSON LineString and evaluate each point "
            "against current local crowd materialisation."
        )
    )
    parser.add_argument(
        "--geometry-file",
        type=Path,
        default=DEFAULT_FIXTURE,
        help=(
            "GeoJSON LineString file to evaluate. Defaults to the stored "
            "Flinders Street to Melbourne Central fixture."
        ),
    )
    parser.add_argument(
        "--details",
        action="store_true",
        help="Print one concise line for every ordered route sample.",
    )
    return parser


def _score(value: float | None) -> str:
    return "unavailable" if value is None else f"{value:.4f}"


def _sample_summary(label: str, result: RouteSampleCrowdResult) -> str:
    return (
        f"{label}: index={result.sample.index}, "
        f"distance={result.sample.distance_along_route_meters:.3f} m, "
        f"support={result.crowd.coverage_status}, "
        f"exposure={_score(result.crowd.crowd_exposure_score)}"
    )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        with args.geometry_file.open(encoding="utf-8") as geometry_file:
            geometry = json.load(geometry_file)
        evaluation = RouteCrowdEvaluationService().evaluate_geometry(
            geometry,
            route_id=args.geometry_file.stem,
        )
    except (
        OSError,
        json.JSONDecodeError,
        RouteSamplingError,
        CoordinateValidationError,
        SpatialDataConsistencyError,
        CalmWayDatabaseError,
    ) as exc:
        print(f"Route crowd evaluation: FAILED - {exc}", file=sys.stderr)
        return 1
    finally:
        dispose_engine()

    coverage_counts = Counter(
        row.crowd.coverage_status for row in evaluation.sample_results
    )
    numeric_count = sum(
        row.crowd.crowd_exposure_score is not None
        for row in evaluation.sample_results
    )
    unavailable_count = evaluation.sample_count - numeric_count

    print(f"Geometry file: {args.geometry_file}")
    print(f"Route length: {evaluation.route_length_meters:.3f} m")
    print(f"Sampling interval: {evaluation.sampling_interval_meters:.3f} m")
    print(f"Samples: {evaluation.sample_count}")
    for status in ("SUPPORTED", "LIMITED", "NO_DATA"):
        print(f"{status}: {coverage_counts[status]}")
    print(f"Numeric crowd samples: {numeric_count}")
    print(f"Unavailable samples: {unavailable_count}")
    print(_sample_summary("First sample", evaluation.sample_results[0]))
    print(_sample_summary("Last sample", evaluation.sample_results[-1]))

    if args.details:
        print("Details:")
        for result in evaluation.sample_results:
            print(
                "  "
                f"index={result.sample.index}, "
                f"distance={result.sample.distance_along_route_meters:.3f} m, "
                f"longitude={result.sample.longitude:.6f}, "
                f"latitude={result.sample.latitude:.6f}, "
                f"support={result.crowd.coverage_status}, "
                f"exposure={_score(result.crowd.crowd_exposure_score)}, "
                f"local={_score(result.crowd.local_condition_score)}"
            )
    if coverage_counts["NO_DATA"] == evaluation.sample_count:
        print("Current crowd data unavailable along this route.")
    print("Status: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
