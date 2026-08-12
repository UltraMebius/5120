"""Normalize Mapbox walking routes into CalmWay request-scoped DTOs."""

from collections.abc import Mapping, Sequence
import math
from typing import Any

from ...schemas.routes import (
    GeoJsonLineString,
    WalkingRouteOption,
    WalkingRouteStep,
)
from .mapbox_directions_client import MapboxDirectionsClient


class WalkingRouteUnavailableError(RuntimeError):
    """Raised when no valid route remains after deterministic validation."""


def _non_negative_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    if not math.isfinite(result) or result < 0:
        return None
    return result


def _coordinate_pair(value: object) -> tuple[float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    longitude = value[0]
    latitude = value[1]
    if (
        isinstance(longitude, bool)
        or not isinstance(longitude, (int, float))
        or isinstance(latitude, bool)
        or not isinstance(latitude, (int, float))
    ):
        return None
    longitude_value = float(longitude)
    latitude_value = float(latitude)
    if (
        not math.isfinite(longitude_value)
        or not -180 <= longitude_value <= 180
        or not math.isfinite(latitude_value)
        or not -90 <= latitude_value <= 90
    ):
        return None
    return longitude_value, latitude_value


def _normalize_geometry(value: object) -> GeoJsonLineString | None:
    if not isinstance(value, Mapping) or value.get("type") != "LineString":
        return None
    raw_coordinates = value.get("coordinates")
    if not isinstance(raw_coordinates, list) or len(raw_coordinates) < 2:
        return None

    coordinates: list[tuple[float, float]] = []
    for raw_coordinate in raw_coordinates:
        coordinate = _coordinate_pair(raw_coordinate)
        if coordinate is None:
            return None
        coordinates.append(coordinate)
    return GeoJsonLineString(coordinates=coordinates)


def _normalize_steps(route: Mapping[str, Any]) -> list[WalkingRouteStep]:
    raw_legs = route.get("legs")
    if not isinstance(raw_legs, list):
        return []

    normalized: list[WalkingRouteStep] = []
    for raw_leg in raw_legs:
        if not isinstance(raw_leg, Mapping):
            continue
        raw_steps = raw_leg.get("steps")
        if not isinstance(raw_steps, list):
            continue
        for raw_step in raw_steps:
            if not isinstance(raw_step, Mapping):
                continue
            distance = _non_negative_number(raw_step.get("distance"))
            duration = _non_negative_number(raw_step.get("duration"))
            maneuver = raw_step.get("maneuver")
            if (
                distance is None
                or duration is None
                or not isinstance(maneuver, Mapping)
            ):
                continue
            instruction = maneuver.get("instruction")
            if not isinstance(instruction, str) or not instruction.strip():
                continue
            normalized.append(
                WalkingRouteStep(
                    instruction=instruction.strip(),
                    distanceMeters=distance,
                    durationSeconds=duration,
                    maneuverLocation=_coordinate_pair(
                        maneuver.get("location")
                    ),
                )
            )
    return normalized


class WalkingRoutingService:
    """Acquire Mapbox routes and retain all valid candidates in source order."""

    def __init__(self, client: MapboxDirectionsClient | None = None) -> None:
        self.client = client or MapboxDirectionsClient()

    @staticmethod
    def normalize_routes(payload: Mapping[str, Any]) -> list[WalkingRouteOption]:
        raw_routes = payload.get("routes")
        if not isinstance(raw_routes, list) or not raw_routes:
            raise WalkingRouteUnavailableError(
                "No walking routes were returned."
            )

        routes: list[WalkingRouteOption] = []
        for route_index, raw_route in enumerate(raw_routes):
            if not isinstance(raw_route, Mapping):
                continue
            distance = _non_negative_number(raw_route.get("distance"))
            duration = _non_negative_number(raw_route.get("duration"))
            geometry = _normalize_geometry(raw_route.get("geometry"))
            if distance is None or duration is None or geometry is None:
                continue

            name = (
                "Walking route"
                if route_index == 0
                else f"Alternative route {route_index}"
            )
            routes.append(
                WalkingRouteOption(
                    id=f"mapbox-route-{route_index}",
                    routeIndex=route_index,
                    name=name,
                    distanceMeters=distance,
                    durationSeconds=duration,
                    geometry=geometry,
                    steps=_normalize_steps(raw_route),
                )
            )

        if not routes:
            raise WalkingRouteUnavailableError(
                "All returned walking routes were malformed."
            )
        return routes

    def find_routes(
        self,
        *,
        origin_longitude: float,
        origin_latitude: float,
        destination_longitude: float,
        destination_latitude: float,
    ) -> list[WalkingRouteOption]:
        payload = self.client.fetch_directions(
            origin_longitude=origin_longitude,
            origin_latitude=origin_latitude,
            destination_longitude=destination_longitude,
            destination_latitude=destination_latitude,
        )
        return self.normalize_routes(payload)

    def find_routes_for_coordinates(
        self,
        coordinates: Sequence[tuple[float, float]],
        *,
        alternatives: bool = True,
    ) -> list[WalkingRouteOption]:
        """Normalize one origin/waypoints/destination Directions response."""

        payload = self.client.fetch_directions_for_coordinates(
            coordinates,
            alternatives=alternatives,
        )
        return self.normalize_routes(payload)
