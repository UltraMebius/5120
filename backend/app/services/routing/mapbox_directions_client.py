"""Backend-only HTTP client for Mapbox Walking Directions v5."""

from collections.abc import Mapping
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
        coordinates = ";".join(
            (
                f"{self._format_coordinate(origin_longitude)},{self._format_coordinate(origin_latitude)}",
                f"{self._format_coordinate(destination_longitude)},{self._format_coordinate(destination_latitude)}",
            )
        )
        return f"{self.base_url}/{self.profile}/{coordinates}"

    def fetch_directions(
        self,
        *,
        origin_longitude: float,
        origin_latitude: float,
        destination_longitude: float,
        destination_latitude: float,
    ) -> Mapping[str, Any]:
        self._validate_configuration()
        url = self.directions_url(
            origin_longitude=origin_longitude,
            origin_latitude=origin_latitude,
            destination_longitude=destination_longitude,
            destination_latitude=destination_latitude,
        )
        parameters = {
            "access_token": self._access_token,
            "alternatives": "true",
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
