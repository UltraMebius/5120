"""Measure and uniformly sample a stored GeoJSON LineString without I/O APIs."""

import argparse
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

from backend.app.services.routing.route_sampling_service import (  # noqa: E402
    RouteSample,
    RouteSamplingError,
    RouteSamplingService,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Measure and uniformly sample an existing GeoJSON LineString. "
            "No Mapbox, crowd, or database calls are made."
        )
    )
    parser.add_argument(
        "--geometry-file",
        type=Path,
        default=DEFAULT_FIXTURE,
        help=(
            "GeoJSON LineString file to sample. Defaults to the stored "
            "Melbourne-scale test fixture."
        ),
    )
    return parser


def _sample_text(prefix: str, sample: RouteSample) -> str:
    return (
        f"{prefix}: index={sample.index}, "
        f"distance={sample.distance_along_route_meters:.3f} m, "
        f"longitude={sample.longitude:.6f}, latitude={sample.latitude:.6f}"
    )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        with args.geometry_file.open(encoding="utf-8") as geometry_file:
            geometry = json.load(geometry_file)
        sampled_route = RouteSamplingService().sample_geometry(geometry)
    except (OSError, json.JSONDecodeError, RouteSamplingError) as exc:
        print(f"Route sampling: FAILED - {exc}", file=sys.stderr)
        return 1

    samples = sampled_route.samples
    scheduled_deltas = [
        current.distance_along_route_meters
        - previous.distance_along_route_meters
        for previous, current in zip(samples, samples[1:-1])
    ]
    final_delta = (
        samples[-1].distance_along_route_meters
        - samples[-2].distance_along_route_meters
    )

    print(f"Geometry file: {args.geometry_file}")
    print(f"Route length: {sampled_route.route_length_meters:.3f} m")
    print(
        "Sampling interval: "
        f"{sampled_route.sampling_interval_meters:.3f} m"
    )
    print(f"Sample count: {len(samples)}")
    print(_sample_text("First sample", samples[0]))
    print(_sample_text("Last sample", samples[-1]))
    print(
        "Scheduled spacing: "
        f"{len(scheduled_deltas)} x "
        f"{sampled_route.sampling_interval_meters:.3f} m"
    )
    print(f"Final endpoint remainder: {final_delta:.3f} m")
    print("Status: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
