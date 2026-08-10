"""Evaluate and rank real Mapbox walking routes against local crowd state."""

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.db import CalmWayDatabaseError, dispose_engine  # noqa: E402
from backend.app.models.crowd import CrowdPreference  # noqa: E402
from backend.app.services.crowd.spatial_crowd_service import (  # noqa: E402
    CoordinateValidationError,
    SpatialDataConsistencyError,
)
from backend.app.services.routing.mapbox_directions_client import (  # noqa: E402
    MapboxDirectionsError,
)
from backend.app.services.routing.route_crowd_ranking_service import (  # noqa: E402
    RouteCrowdDataConsistencyError,
    RouteCrowdRankingService,
)
from backend.app.services.routing.route_sampling_service import (  # noqa: E402
    RouteSamplingError,
)
from backend.app.services.routing.routing_service import (  # noqa: E402
    WalkingRouteUnavailableError,
    WalkingRoutingService,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch real Mapbox walking candidates and apply the Phase 4 "
            "backend crowd-ranking policy without refreshing or writing data."
        )
    )
    parser.add_argument("--origin-longitude", type=float, default=144.9671)
    parser.add_argument("--origin-latitude", type=float, default=-37.8183)
    parser.add_argument("--destination-longitude", type=float, default=144.9631)
    parser.add_argument("--destination-latitude", type=float, default=-37.8102)
    parser.add_argument(
        "--preference",
        choices=[preference.value for preference in CrowdPreference],
        default=CrowdPreference.PREFER_QUIETER.value,
    )
    return parser


def _number(value: float | None, suffix: str = "") -> str:
    return "unavailable" if value is None else f"{value:.2f}{suffix}"


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        routes = WalkingRoutingService().find_routes(
            origin_longitude=args.origin_longitude,
            origin_latitude=args.origin_latitude,
            destination_longitude=args.destination_longitude,
            destination_latitude=args.destination_latitude,
        )
        result = RouteCrowdRankingService().rank_routes(
            routes,
            CrowdPreference(args.preference),
        )
    except (
        MapboxDirectionsError,
        WalkingRouteUnavailableError,
        RouteSamplingError,
        CoordinateValidationError,
        SpatialDataConsistencyError,
        RouteCrowdDataConsistencyError,
        CalmWayDatabaseError,
    ) as exc:
        print(f"Route ranking: FAILED - {exc}", file=sys.stderr)
        return 1
    finally:
        dispose_engine()

    print(f"Preference: {args.preference}")
    print(f"Ranking status: {result.ranking_status.value}")
    print(
        "Recommended route: "
        f"{result.recommended_route_id or 'none'}"
    )
    for item in result.routes:
        route = item.route
        summary = item.summary
        print(
            f"Route ID={route.id}; "
            f"distance={route.distanceMeters:.2f} m; "
            f"duration={route.durationSeconds:.2f} s; "
            f"coverage={summary.data_coverage_pct:.2f}%; "
            f"crowd={_number(summary.p75_crowd_exposure_score)}; "
            f"preference={summary.preference_status.value}; "
            f"rank={item.rank or 'none'}; "
            f"recommended={'yes' if item.is_recommended else 'no'}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
