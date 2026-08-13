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


def test_multiple_waypoint_legs_preserve_steps_in_leg_order() -> None:
    route = _route()
    route["legs"] = [
        {
            "steps": [
                {
                    "distance": 100,
                    "duration": 70,
                    "maneuver": {
                        "instruction": "Walk to waypoint",
                        "location": [144.9671, -37.8183],
                    },
                }
            ]
        },
        {
            "steps": [
                {
                    "distance": 200,
                    "duration": 140,
                    "maneuver": {
                        "instruction": "Continue to destination",
                        "location": [144.965, -37.814],
                    },
                }
            ]
        },
    ]

    routes = WalkingRoutingService.normalize_routes(
        {"code": "Ok", "routes": [route]}
    )

    assert [step.instruction for step in routes[0].steps] == [
        "Walk to waypoint",
        "Continue to destination",
    ]


def _mapbox_step(
    instruction: str,
    maneuver_type: str | None,
    *,
    distance: float = 100,
) -> dict[str, object]:
    maneuver: dict[str, object] = {
        "instruction": instruction,
        "location": [144.965, -37.814],
    }
    if maneuver_type is not None:
        maneuver["type"] = maneuver_type
    return {
        "distance": distance,
        "duration": 60,
        "maneuver": maneuver,
    }


def test_two_leg_route_removes_intermediate_arrival_and_preserves_totals() -> None:
    route = _route(distance=1750, duration=1260)
    original_geometry = route["geometry"]
    route["legs"] = [
        {
            "steps": [
                _mapbox_step("Walk to the waypoint", "depart"),
                _mapbox_step(
                    "You have arrived at your destination.",
                    "arrive",
                    distance=0,
                ),
            ]
        },
        {
            "steps": [
                _mapbox_step("Continue toward the destination", "turn"),
                _mapbox_step(
                    "You have arrived at your destination.",
                    "arrive",
                    distance=0,
                ),
            ]
        },
    ]

    normalized = WalkingRoutingService.normalize_routes(
        {"code": "Ok", "routes": [route]}
    )[0]

    assert [step.instruction for step in normalized.steps] == [
        "Walk to the waypoint",
        "Continue toward the destination",
        "You have arrived at your destination.",
    ]
    assert sum(
        step.instruction == "You have arrived at your destination."
        for step in normalized.steps
    ) == 1
    assert normalized.distanceMeters == 1750
    assert normalized.durationSeconds == 1260
    assert normalized.geometry.type == original_geometry["type"]
    assert normalized.geometry.coordinates == [
        tuple(coordinate) for coordinate in original_geometry["coordinates"]
    ]


def test_three_leg_route_removes_both_intermediate_arrivals() -> None:
    route = _route()
    route["legs"] = [
        {
            "steps": [
                _mapbox_step("Walk to waypoint A", "depart"),
                _mapbox_step("Arrive at waypoint A", "arrive", distance=0),
            ]
        },
        {
            "steps": [
                _mapbox_step("Walk to waypoint B", "depart"),
                _mapbox_step("Arrive at waypoint B", "arrive", distance=0),
            ]
        },
        {
            "steps": [
                _mapbox_step("Walk to the destination", "depart"),
                _mapbox_step(
                    "You have arrived at your destination.",
                    "arrive",
                    distance=0,
                ),
            ]
        },
    ]

    normalized = WalkingRoutingService.normalize_routes(
        {"code": "Ok", "routes": [route]}
    )[0]

    assert [step.instruction for step in normalized.steps] == [
        "Walk to waypoint A",
        "Walk to waypoint B",
        "Walk to the destination",
        "You have arrived at your destination.",
    ]


def test_single_leg_route_preserves_final_arrival_instruction() -> None:
    route = _route()
    route["legs"] = [
        {
            "steps": [
                _mapbox_step("Walk to the destination", "depart"),
                _mapbox_step(
                    "You have arrived at your destination.",
                    "arrive",
                    distance=0,
                ),
            ]
        }
    ]

    normalized = WalkingRoutingService.normalize_routes(
        {"code": "Ok", "routes": [route]}
    )[0]

    assert normalized.steps[-1].instruction == (
        "You have arrived at your destination."
    )


def test_intermediate_arrival_instruction_fallback_applies_without_type() -> None:
    route = _route()
    route["legs"] = [
        {
            "steps": [
                _mapbox_step("Walk to the waypoint", "depart"),
                _mapbox_step(
                    "You have arrived at your destination.",
                    None,
                    distance=0,
                ),
            ]
        },
        {
            "steps": [
                _mapbox_step("Continue to the destination", "depart"),
                _mapbox_step(
                    "You have arrived at your destination.",
                    None,
                    distance=0,
                ),
            ]
        },
    ]

    normalized = WalkingRoutingService.normalize_routes(
        {"code": "Ok", "routes": [route]}
    )[0]

    assert [step.instruction for step in normalized.steps].count(
        "You have arrived at your destination."
    ) == 1


class RecordingClient:
    def __init__(self):
        self.two_point_calls = []
        self.sequence_calls = []

    def fetch_directions(self, **coordinates):
        self.two_point_calls.append(coordinates)
        return {"code": "Ok", "routes": [_route()]}

    def fetch_directions_for_coordinates(self, coordinates, *, alternatives=True):
        self.sequence_calls.append((tuple(coordinates), alternatives))
        return {"code": "Ok", "routes": [_route()]}


def test_existing_two_point_service_boundary_remains_unchanged() -> None:
    client = RecordingClient()

    routes = WalkingRoutingService(client).find_routes(
        origin_longitude=144.96,
        origin_latitude=-37.82,
        destination_longitude=144.97,
        destination_latitude=-37.81,
    )

    assert len(routes) == 1
    assert client.two_point_calls == [
        {
            "origin_longitude": 144.96,
            "origin_latitude": -37.82,
            "destination_longitude": 144.97,
            "destination_latitude": -37.81,
        }
    ]
    assert client.sequence_calls == []


def test_coordinate_sequence_service_boundary_preserves_waypoint() -> None:
    client = RecordingClient()
    coordinates = (
        (144.96, -37.82),
        (144.965, -37.815),
        (144.97, -37.81),
    )

    routes = WalkingRoutingService(client).find_routes_for_coordinates(
        coordinates,
        alternatives=False,
    )

    assert len(routes) == 1
    assert client.sequence_calls == [(coordinates, False)]
    assert client.two_point_calls == []
