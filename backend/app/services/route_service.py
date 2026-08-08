"""Route option handling for CalmWay."""

from .sensory_service import get_mock_sensory_level


def get_mock_routes() -> list[dict[str, object]]:
    """Return temporary mock routes for the small practice iteration.

    These values do not come from City of Melbourne data or a routing provider.
    """
    # TODO: Replace this mock response after a real route-generation approach is chosen.
    return [
        {
            "id": "route-a",
            "name": "Route A",
            "distanceKm": 1.2,
            "durationMin": 15,
            "sensoryLevel": get_mock_sensory_level("route-a"),
            "recommended": True,
        },
        {
            "id": "route-b",
            "name": "Route B",
            "distanceKm": 1.0,
            "durationMin": 12,
            "sensoryLevel": get_mock_sensory_level("route-b"),
            "recommended": False,
        },
    ]
