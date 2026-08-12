"""Backend-only HTTP client for Mapbox Walking Directions v5."""

from collections.abc import Mapping, Sequence
import math
from typing import Any

import httpx

from ...config import SETTINGS


class MapboxDirectionsError(RuntimeError):
    """Base class for sanitized, expected Mapbox Directions failures."""


class MapboxDirectionsConfigurationError(MapboxDirectionsError):
    """Raised when backend Directions configuration is unavailable or invalid."""


class MapboxDirectionsConnectionError(MapboxDirectionsError):
    """Raised when Mapbox cannot be reached within the configured timeout."""


class MapboxDirectionsResponseError(MapboxDirectionsError):
    """Raised when Mapbox returns an unusable HTTP or JSON response."""


class MapboxDirectionsClient:
    """Fetch raw walking directions without exposing credentials to callers."""

    def __init__(
        self,
        *,
        access_token: str | None = None,
        base_url: str | None = None,
        profile: str | None = None,
        timeout_seconds: float | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        settings = SETTINGS.mapbox_directions
        self._access_token = (
            settings.access_token if access_token is None else access_token
        ).strip()
        self.base_url = (base_url or settings.base_url).rstrip("/")
        self.profile = (profile or settings.profile).strip()
        self.timeout_seconds = (
            settings.timeout_seconds
            if timeout_seconds is None
            else timeout_seconds
        )
        self.request_timeout = httpx.Timeout(
            self.timeout_seconds,
            connect=min(5.0, self.timeout_seconds),
        )
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=self.request_timeout,
            follow_redirects=True,
            headers={"User-Agent": "CalmWay-FIT5120/Phase-3B"},
        )

    @staticmethod
    def _format_coordinate(value: float) -> str:
        return f"{value:.8f}".rstrip("0").rstrip(".")

    @staticmethod
    def _validated_coordinates(
        coordinates: Sequence[tuple[float, float]],
    ) -> tuple[tuple[float, float], ...]:
        if not 2 <= len(coordinates) <= 25:
            raise ValueError("Mapbox Directions requires 2 to 25 coordinates")
        validated: list[tuple[float, float]] = []
        for coordinate in coordinates:
            if not isinstance(coordinate, (list, tuple)) or len(coordinate) != 2:
                raise ValueError("each Mapbox coordinate must be longitude/latitude")
            longitude, latitude = coordinate
            if (
                isinstance(longitude, bool)
                or not isinstance(longitude, (int, float))
                or not math.isfinite(float(longitude))
                or not -180.0 <= float(longitude) <= 180.0
            ):
                raise ValueError("Mapbox longitude must be finite and valid")
            if (
                isinstance(latitude, bool)
                or not isinstance(latitude, (int, float))
                or not math.isfinite(float(latitude))
                or not -90.0 <= float(latitude) <= 90.0
            ):
                raise ValueError("Mapbox latitude must be finite and valid")
            validated.append((float(longitude), float(latitude)))
        return tuple(validated)

    def _validate_configuration(self) -> None:
        if not self._access_token:
            raise MapboxDirectionsConfigurationError(
                "Mapbox Directions access token is not configured."
            )
        if self.profile != "mapbox/walking":
            raise MapboxDirectionsConfigurationError(
                "Mapbox Directions profile must be mapbox/walking."
            )
        if self.timeout_seconds <= 0:
            raise MapboxDirectionsConfigurationError(
                "Mapbox Directions timeout must be positive."
            )

    def directions_url(
        self,
        *,
        origin_longitude: float,
        origin_latitude: float,
        destination_longitude: float,
        destination_latitude: float,
    ) -> str:
        return self.directions_url_for_coordinates(
            (
                (origin_longitude, origin_latitude),
                (destination_longitude, destination_latitude),
            )
        )

    def directions_url_for_coordinates(
        self,
        coordinates: Sequence[tuple[float, float]],
    ) -> str:
        """Build one Directions URL for origin, optional waypoints, destination."""

        validated = self._validated_coordinates(coordinates)
        coordinate_path = ";".join(
            f"{self._format_coordinate(longitude)},"
            f"{self._format_coordinate(latitude)}"
            for longitude, latitude in validated
        )
        return f"{self.base_url}/{self.profile}/{coordinate_path}"

    def fetch_directions(
        self,
        *,
        origin_longitude: float,
        origin_latitude: float,
        destination_longitude: float,
        destination_latitude: float,
    ) -> Mapping[str, Any]:
        return self.fetch_directions_for_coordinates(
            (
                (origin_longitude, origin_latitude),
                (destination_longitude, destination_latitude),
            )
        )

    def fetch_directions_for_coordinates(
        self,
        coordinates: Sequence[tuple[float, float]],
        *,
        alternatives: bool = True,
    ) -> Mapping[str, Any]:
        """Fetch walking routes for a validated coordinate sequence."""

        self._validate_configuration()
        url = self.directions_url_for_coordinates(coordinates)
        parameters = {
            "access_token": self._access_token,
            "alternatives": "true" if alternatives else "false",
            "geometries": "geojson",
            "overview": "full",
            "steps": "true",
            "language": "en",
        }

        try:
            response = self._client.get(
                url,
                params=parameters,
                timeout=self.request_timeout,
            )
        except httpx.TimeoutException:
            raise MapboxDirectionsConnectionError(
                "Mapbox Directions request timed out."
            ) from None
        except httpx.RequestError:
            raise MapboxDirectionsConnectionError(
                "Unable to reach Mapbox Directions."
            ) from None

        if not 200 <= response.status_code < 300:
            raise MapboxDirectionsResponseError(
                f"Mapbox Directions returned HTTP {response.status_code}."
            )

        try:
            payload = response.json()
        except ValueError:
            raise MapboxDirectionsResponseError(
                "Mapbox Directions returned malformed JSON."
            ) from None

        if not isinstance(payload, Mapping):
            raise MapboxDirectionsResponseError(
                "Mapbox Directions response must be a JSON object."
            )
        if payload.get("code") != "Ok":
            raise MapboxDirectionsResponseError(
                "Mapbox Directions could not produce a walking route."
            )
        return payload

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "MapboxDirectionsClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
