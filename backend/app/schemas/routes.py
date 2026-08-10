"""Walking-route request and normalized response schemas."""

from typing import Literal

from pydantic import BaseModel, Field

from ..models.crowd import CrowdPreference


class RouteLocationRequest(BaseModel):
    label: str = Field(min_length=1, max_length=256)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)


class WalkingRouteRequest(BaseModel):
    origin: RouteLocationRequest
    destination: RouteLocationRequest
    preference: CrowdPreference


class GeoJsonLineString(BaseModel):
    type: Literal["LineString"] = "LineString"
    coordinates: list[tuple[float, float]] = Field(min_length=2)


class WalkingRouteStep(BaseModel):
    instruction: str
    distanceMeters: float = Field(ge=0, allow_inf_nan=False)
    durationSeconds: float = Field(ge=0, allow_inf_nan=False)
    maneuverLocation: tuple[float, float] | None = None


class WalkingRouteOption(BaseModel):
    id: str
    source: Literal["MAPBOX"] = "MAPBOX"
    routeIndex: int = Field(ge=0)
    name: str
    distanceMeters: float = Field(ge=0, allow_inf_nan=False)
    durationSeconds: float = Field(ge=0, allow_inf_nan=False)
    geometry: GeoJsonLineString
    steps: list[WalkingRouteStep] = Field(default_factory=list)


class WalkingRoutesResponse(BaseModel):
    preference: CrowdPreference
    routes: list[WalkingRouteOption]
    recommendedRouteId: None = None
    rankingStatus: Literal["NOT_EVALUATED"] = "NOT_EVALUATED"
