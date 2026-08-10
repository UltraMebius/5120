"""Pure, deterministic distance-along-route sampling for GeoJSON LineStrings."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math

from ...config import SETTINGS
from ...schemas.routes import GeoJsonLineString


EARTH_MEAN_RADIUS_METERS = 6_371_008.8
_ENDPOINT_DISTANCE_TOLERANCE_METERS = 1e-7

Coordinate = tuple[float, float]


class RouteSamplingError(ValueError):
    """Base class for controlled route-sampling failures."""


class InvalidRouteGeometryError(RouteSamplingError):
    """Raised when input is not a usable WGS84 GeoJSON LineString."""


class DegenerateRouteGeometryError(RouteSamplingError):
    """Raised when every route segment has zero length."""


class RouteSamplingConfigurationError(RouteSamplingError):
    """Raised when the configured sampling interval is invalid."""


@dataclass(frozen=True, slots=True)
class RouteSample:
    """One ordered WGS84 point at a measured distance along a route."""

    index: int
    distance_along_route_meters: float
    longitude: float
    latitude: float


@dataclass(frozen=True, slots=True)
class SampledRoute:
    """Measured route metadata and its immutable ordered sample sequence."""

    route_length_meters: float
    sampling_interval_meters: float
    samples: tuple[RouteSample, ...]


@dataclass(frozen=True, slots=True)
class _MeasuredSegment:
    start: Coordinate
    end: Coordinate
    start_distance_meters: float
    end_distance_meters: float

    @property
    def length_meters(self) -> float:
        return self.end_distance_meters - self.start_distance_meters


def haversine_distance_meters(start: Coordinate, end: Coordinate) -> float:
    """Return great-circle distance using the IUGG mean Earth radius."""

    start_longitude, start_latitude = start
    end_longitude, end_latitude = end
    start_latitude_radians = math.radians(start_latitude)
    end_latitude_radians = math.radians(end_latitude)
    latitude_delta = end_latitude_radians - start_latitude_radians
    longitude_delta = math.radians(end_longitude - start_longitude)

    haversine_value = (
        math.sin(latitude_delta / 2.0) ** 2
        + math.cos(start_latitude_radians)
        * math.cos(end_latitude_radians)
        * math.sin(longitude_delta / 2.0) ** 2
    )
    bounded_value = min(1.0, max(0.0, haversine_value))
    central_angle = 2.0 * math.atan2(
        math.sqrt(bounded_value),
        math.sqrt(1.0 - bounded_value),
    )
    return EARTH_MEAN_RADIUS_METERS * central_angle


def _coordinate_pair(value: object) -> Coordinate:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes))
        or len(value) != 2
    ):
        raise InvalidRouteGeometryError(
            "Each LineString coordinate must contain longitude and latitude."
        )

    longitude, latitude = value
    if (
        isinstance(longitude, bool)
        or not isinstance(longitude, (int, float))
        or isinstance(latitude, bool)
        or not isinstance(latitude, (int, float))
    ):
        raise InvalidRouteGeometryError(
            "LineString longitude and latitude must be numeric."
        )

    longitude_value = float(longitude)
    latitude_value = float(latitude)
    if not math.isfinite(longitude_value) or not -180 <= longitude_value <= 180:
        raise InvalidRouteGeometryError(
            "LineString longitude must be finite and between -180 and 180."
        )
    if not math.isfinite(latitude_value) or not -90 <= latitude_value <= 90:
        raise InvalidRouteGeometryError(
            "LineString latitude must be finite and between -90 and 90."
        )
    return longitude_value, latitude_value


def _coordinates_from_geometry(geometry: object) -> tuple[Coordinate, ...]:
    if isinstance(geometry, GeoJsonLineString):
        geometry_type: object = geometry.type
        raw_coordinates: object = geometry.coordinates
    elif isinstance(geometry, Mapping):
        geometry_type = geometry.get("type")
        raw_coordinates = geometry.get("coordinates")
    else:
        raise InvalidRouteGeometryError(
            "Route geometry must be a GeoJSON LineString object."
        )

    if geometry_type != "LineString":
        raise InvalidRouteGeometryError(
            "Route geometry type must be LineString."
        )
    if (
        not isinstance(raw_coordinates, Sequence)
        or isinstance(raw_coordinates, (str, bytes))
        or len(raw_coordinates) < 2
    ):
        raise InvalidRouteGeometryError(
            "A LineString must contain at least two coordinates."
        )
    return tuple(_coordinate_pair(value) for value in raw_coordinates)


def _validated_interval(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RouteSamplingConfigurationError(
            "Route sampling interval must be numeric."
        )
    interval = float(value)
    if not math.isfinite(interval) or interval <= 0:
        raise RouteSamplingConfigurationError(
            "Route sampling interval must be finite and greater than zero."
        )
    return interval


def _measure_segments(
    coordinates: tuple[Coordinate, ...],
) -> tuple[tuple[_MeasuredSegment, ...], float]:
    measured_segments: list[_MeasuredSegment] = []
    cumulative_distance = 0.0

    for start, end in zip(coordinates, coordinates[1:]):
        segment_length = haversine_distance_meters(start, end)
        if segment_length == 0.0:
            continue
        measured_segments.append(
            _MeasuredSegment(
                start=start,
                end=end,
                start_distance_meters=cumulative_distance,
                end_distance_meters=cumulative_distance + segment_length,
            )
        )
        cumulative_distance += segment_length

    if not measured_segments:
        raise DegenerateRouteGeometryError(
            "Route geometry is degenerate because every segment has zero length."
        )
    return tuple(measured_segments), cumulative_distance


def _scheduled_distances(
    route_length_meters: float,
    interval_meters: float,
) -> tuple[float, ...]:
    distances = [0.0]
    multiplier = 1

    while True:
        target = multiplier * interval_meters
        if target >= route_length_meters or math.isclose(
            target,
            route_length_meters,
            rel_tol=0.0,
            abs_tol=_ENDPOINT_DISTANCE_TOLERANCE_METERS,
        ):
            break
        distances.append(target)
        multiplier += 1

    distances.append(route_length_meters)
    return tuple(distances)


def _interpolate(segment: _MeasuredSegment, target_distance: float) -> Coordinate:
    fraction = (
        target_distance - segment.start_distance_meters
    ) / segment.length_meters
    fraction = min(1.0, max(0.0, fraction))
    start_longitude, start_latitude = segment.start
    end_longitude, end_latitude = segment.end
    return (
        start_longitude + (end_longitude - start_longitude) * fraction,
        start_latitude + (end_latitude - start_latitude) * fraction,
    )


class RouteSamplingService:
    """Sample an existing route at uniform cumulative-distance targets."""

    def __init__(self, interval_meters: float | None = None) -> None:
        configured_interval = (
            SETTINGS.route.sample_interval_m
            if interval_meters is None
            else interval_meters
        )
        self.interval_meters = _validated_interval(configured_interval)

    def sample_geometry(self, geometry: object) -> SampledRoute:
        coordinates = _coordinates_from_geometry(geometry)
        segments, route_length = _measure_segments(coordinates)
        target_distances = _scheduled_distances(
            route_length,
            self.interval_meters,
        )
        samples: list[RouteSample] = []
        segment_index = 0

        for sample_index, target_distance in enumerate(target_distances):
            if sample_index == 0:
                longitude, latitude = coordinates[0]
            elif sample_index == len(target_distances) - 1:
                longitude, latitude = coordinates[-1]
            else:
                while (
                    segment_index < len(segments) - 1
                    and target_distance
                    > segments[segment_index].end_distance_meters
                ):
                    segment_index += 1
                longitude, latitude = _interpolate(
                    segments[segment_index],
                    target_distance,
                )

            samples.append(
                RouteSample(
                    index=sample_index,
                    distance_along_route_meters=target_distance,
                    longitude=longitude,
                    latitude=latitude,
                )
            )

        return SampledRoute(
            route_length_meters=route_length,
            sampling_interval_meters=self.interval_meters,
            samples=tuple(samples),
        )
