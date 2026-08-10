import pytest

from backend.app.services.routing.routing_service import (
    WalkingRouteUnavailableError,
    WalkingRoutingService,
)


def _route(
    *,
    distance: object = 1162.4,
    duration: object = 888.0,
    coordinates: object | None = None,
    steps: object | None = None,
) -> dict[str, object]:
    return {
        "distance": distance,
        "duration": duration,
        "geometry": {
            "type": "LineString",
            "coordinates": coordinates
            if coordinates is not None
            else [[144.9671, -37.8183], [144.9631, -37.8102]],
        },
        "legs": [
            {
                "steps": steps
                if steps is not None
                else [
                    {
                        "distance": 120.5,
                        "duration": 91.0,
                        "maneuver": {
                            "instruction": "Walk north on Swanston Street",
                            "location": [144.9671, -37.8183],
                        },
                    }
                ]
            }
        ],
    }


def test_one_route_response_preserves_full_geometry_and_steps() -> None:
    coordinates = [
        [144.9671, -37.8183],
        [144.9660, -37.8150],
        [144.9631, -37.8102],
    ]
    routes = WalkingRoutingService.normalize_routes(
        {"code": "Ok", "routes": [_route(coordinates=coordinates)]}
    )

    assert len(routes) == 1
    route = routes[0]
    assert route.id == "mapbox-route-0"
    assert route.source == "MAPBOX"
    assert route.routeIndex == 0
    assert route.name == "Walking route"
    assert route.distanceMeters == 1162.4
    assert route.durationSeconds == 888.0
    assert route.geometry.type == "LineString"
    assert route.geometry.coordinates == [tuple(pair) for pair in coordinates]
    assert len(route.steps) == 1
    assert route.steps[0].instruction == "Walk north on Swanston Street"
    assert route.steps[0].distanceMeters == 120.5
    assert route.steps[0].durationSeconds == 91.0
    assert route.steps[0].maneuverLocation == (144.9671, -37.8183)


def test_multiple_routes_keep_mapbox_order_and_stable_request_local_ids() -> None:
    routes = WalkingRoutingService.normalize_routes(
        {
            "code": "Ok",
            "routes": [
                _route(distance=1000.0),
                _route(distance=1200.0),
                _route(distance=1400.0),
            ],
        }
    )

    assert [route.id for route in routes] == [
        "mapbox-route-0",
        "mapbox-route-1",
        "mapbox-route-2",
    ]
    assert [route.routeIndex for route in routes] == [0, 1, 2]
    assert [route.distanceMeters for route in routes] == [1000.0, 1200.0, 1400.0]
    assert [route.name for route in routes] == [
        "Walking route",
        "Alternative route 1",
        "Alternative route 2",
    ]


def test_zero_route_response_is_unavailable() -> None:
    with pytest.raises(WalkingRouteUnavailableError, match="No walking routes"):
        WalkingRoutingService.normalize_routes({"code": "Ok", "routes": []})


@pytest.mark.parametrize("distance", [-1, float("nan"), float("inf"), "12"])
def test_negative_or_invalid_distance_rejects_route(distance: object) -> None:
    with pytest.raises(WalkingRouteUnavailableError, match="malformed"):
        WalkingRoutingService.normalize_routes(
            {"code": "Ok", "routes": [_route(distance=distance)]}
        )


@pytest.mark.parametrize(
    "coordinates",
    [
        [],
        [[144.96, -37.81]],
        [[144.96, -37.81], [181.0, -37.82]],
        [[144.96, -37.81], [144.97, float("nan")]],
        [[-37.81, 144.96], [-37.82, 144.97]],
        [[144.96, -37.81, 10], [144.97, -37.82]],
    ],
)
def test_malformed_geometry_rejects_route(coordinates: object) -> None:
    with pytest.raises(WalkingRouteUnavailableError, match="malformed"):
        WalkingRoutingService.normalize_routes(
            {"code": "Ok", "routes": [_route(coordinates=coordinates)]}
        )


def test_malformed_candidate_is_skipped_without_reordering_valid_routes() -> None:
    routes = WalkingRoutingService.normalize_routes(
        {
            "code": "Ok",
            "routes": [
                _route(distance=-1),
                _route(distance=1200.0),
                _route(distance=1400.0),
            ],
        }
    )

    assert [route.id for route in routes] == ["mapbox-route-1", "mapbox-route-2"]
    assert [route.distanceMeters for route in routes] == [1200.0, 1400.0]


def test_missing_or_malformed_steps_do_not_break_route_acquisition() -> None:
    malformed_steps = [
        {"distance": -1, "duration": 2, "maneuver": {"instruction": "Bad"}},
        {"distance": 3, "duration": 2, "maneuver": {}},
    ]
    routes = WalkingRoutingService.normalize_routes(
        {"code": "Ok", "routes": [_route(steps=malformed_steps)]}
    )

    assert len(routes) == 1
    assert routes[0].steps == []
