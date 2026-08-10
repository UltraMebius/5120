"""Explicitly gated real Mapbox walking Directions smoke test."""

import os

import pytest

from backend.app.config import SETTINGS
from backend.app.services.routing.routing_service import WalkingRoutingService


RUN_LIVE = os.getenv("RUN_MAPBOX_DIRECTIONS_INTEGRATION", "") == "1"
HAS_TOKEN = bool(SETTINGS.mapbox_directions.access_token)


@pytest.mark.skipif(
    not RUN_LIVE or not HAS_TOKEN,
    reason=(
        "Set MAPBOX_ACCESS_TOKEN and RUN_MAPBOX_DIRECTIONS_INTEGRATION=1 "
        "to run the live Mapbox walking test."
    ),
)
def test_live_flinders_to_melbourne_central_walking_route() -> None:
    service = WalkingRoutingService()
    try:
        routes = service.find_routes(
            origin_longitude=144.9671,
            origin_latitude=-37.8183,
            destination_longitude=144.9631,
            destination_latitude=-37.8102,
        )
    finally:
        service.client.close()

    assert len(routes) >= 1
    for route in routes:
        assert route.source == "MAPBOX"
        assert route.distanceMeters > 0
        assert route.durationSeconds > 0
        assert route.geometry.type == "LineString"
        assert len(route.geometry.coordinates) >= 2
        print(
            "live route summary: "
            f"index={route.routeIndex}, "
            f"distanceMeters={route.distanceMeters:.1f}, "
            f"durationSeconds={route.durationSeconds:.1f}, "
            f"geometry={route.geometry.type}, "
            f"coordinateCount={len(route.geometry.coordinates)}, "
            f"stepCount={len(route.steps)}"
        )
