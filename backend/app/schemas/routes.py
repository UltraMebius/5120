"""Walking-route request and normalized response schemas."""

from typing import Literal

from pydantic import BaseModel, Field

from ..models.crowd import (
    CrowdLevel,
    CrowdPreference,
    FrontendCrowdLevel,
    RoutePreferenceStatus,
    RouteRankingStatus,
    RouteCrowdAlertReason,
    RouteCrowdAlertState,
)


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


class InitialCrowdAlert(BaseModel):
    decision: RouteCrowdAlertState
    reason: RouteCrowdAlertReason
    preference: CrowdPreference
    threshold: float = Field(ge=0, le=100, allow_inf_nan=False)
    currentProgressMeters: float = Field(ge=0, allow_inf_nan=False)
    lookAheadDistanceMeters: float = Field(gt=0, allow_inf_nan=False)
    totalLookAheadSamples: int = Field(ge=0)
    numericLookAheadSamples: int = Field(ge=0)
    lookAheadCoveragePct: float | None = Field(default=None, ge=0, le=100)
    pctAbovePreference: float | None = Field(default=None, ge=0, le=100)
    triggerStartDistanceMeters: float | None = Field(default=None, ge=0)
    triggerEndDistanceMeters: float | None = Field(default=None, ge=0)
    triggerSampleCount: int | None = Field(default=None, ge=2)
    maximumExposureInTrigger: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )


class WalkingRouteOption(BaseModel):
    id: str
    source: Literal["MAPBOX"] = "MAPBOX"
    routeIndex: int = Field(ge=0)
    name: str
    distanceMeters: float = Field(ge=0, allow_inf_nan=False)
    durationSeconds: float = Field(ge=0, allow_inf_nan=False)
    geometry: GeoJsonLineString
    steps: list[WalkingRouteStep] = Field(default_factory=list)
    routeCrowdLevel: CrowdLevel | None = None
    routeCrowdPresentationLevel: FrontendCrowdLevel | None = None
    preferenceStatus: RoutePreferenceStatus | None = None
    supportedPct: float | None = Field(default=None, ge=0, le=100)
    limitedCoveragePct: float | None = Field(default=None, ge=0, le=100)
    dataCoveragePct: float | None = Field(default=None, ge=0, le=100)
    noDataPct: float | None = Field(default=None, ge=0, le=100)
    medianCrowdExposureScore: float | None = Field(
        default=None, ge=0, le=100
    )
    p75CrowdExposureScore: float | None = Field(
        default=None, ge=0, le=100
    )
    maximumCrowdExposureScore: float | None = Field(
        default=None, ge=0, le=100
    )
    pctAbovePreference: float | None = Field(default=None, ge=0, le=100)
    pctVeryHigh: float | None = Field(default=None, ge=0, le=100)
    sampleIntervalM: float | None = Field(default=None, gt=0)
    sampleCount: int | None = Field(default=None, ge=0)
    numericSampleCount: int | None = Field(default=None, ge=0)
    rank: int | None = Field(default=None, ge=1)
    isRecommended: bool = False
    initialCrowdAlert: InitialCrowdAlert | None = None


class WalkingRoutesResponse(BaseModel):
    preference: CrowdPreference
    routes: list[WalkingRouteOption]
    recommendedRouteId: str | None = None
    rankingStatus: RouteRankingStatus = RouteRankingStatus.NOT_EVALUATED
