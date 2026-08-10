"""Explicitly temporary route data retained to keep Phase 1 runnable."""

from ...models.crowd import CoverageStatus, CrowdLevel, CrowdPreference
from ...schemas.routes import RouteOption
from ..crowd.presentation import to_frontend_crowd_level


def get_preview_routes(
    preference: CrowdPreference = CrowdPreference.PREFER_QUIETER,
) -> list[RouteOption]:
    """Return two mock candidates; no routing or crowd ranking occurs here."""
    _ = preference
    definitions = (
        {
            "id": "route-a",
            "name": "Garden Streets",
            "distanceKm": 1.2,
            "durationMin": 15,
            "internalCrowdLevel": CrowdLevel.LOW,
            "recommended": True,
        },
        {
            "id": "route-b",
            "name": "Direct City Walk",
            "distanceKm": 1.0,
            "durationMin": 12,
            "internalCrowdLevel": CrowdLevel.HIGH,
            "recommended": False,
        },
    )

    routes: list[RouteOption] = []
    for definition in definitions:
        internal_level = definition["internalCrowdLevel"]
        if not isinstance(internal_level, CrowdLevel):
            raise TypeError("Preview internal level must be a CrowdLevel.")
        frontend_level = to_frontend_crowd_level(internal_level)
        routes.append(
            RouteOption(
                **definition,
                crowdLevel=frontend_level,
                sensoryLevel=frontend_level,
                coverageStatus=CoverageStatus.SUPPORTED,
            )
        )

    return routes
