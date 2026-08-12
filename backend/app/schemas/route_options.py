"""Additive request/response contract for product walking-route options."""

from pydantic import BaseModel, Field

from ..services.routing.route_candidate_models import (
    CandidateGenerationReason,
    RouteCandidateSource,
)
from ..services.routing.route_option_selection_service import (
    PedestrianFlowComparisonBasis,
    RelativePedestrianActivity,
    RouteOptionRole,
)
from .routes import GeoJsonLineString, WalkingRouteStep


class RouteOptionCoordinate(BaseModel):
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)


class RouteOptionsRequest(BaseModel):
    origin: RouteOptionCoordinate
    destination: RouteOptionCoordinate


class PedestrianFlowEvidenceResponse(BaseModel):
    medianMovementsPerMinute: float | None = Field(default=None, ge=0)
    p75MovementsPerMinute: float | None = Field(default=None, ge=0)
    maximumMovementsPerMinute: float | None = Field(default=None, ge=0)
    coveragePct: float = Field(ge=0, le=100)


class ComparisonPedestrianFlowResponse(BaseModel):
    basis: PedestrianFlowComparisonBasis
    typicalMovementsPerMinute: float | None = Field(default=None, ge=0)
    p75MovementsPerMinute: float | None = Field(default=None, ge=0)
    maximumMovementsPerMinute: float | None = Field(default=None, ge=0)
    coveragePct: float | None = Field(default=None, ge=0, le=100)


class RouteOptionResponse(BaseModel):
    routeId: str
    routeIndex: int = Field(ge=0)
    candidateSource: RouteCandidateSource
    geometry: GeoJsonLineString
    distanceMeters: float = Field(ge=0, allow_inf_nan=False)
    durationSeconds: float = Field(ge=0, allow_inf_nan=False)
    steps: list[WalkingRouteStep]
    roleBadges: list[RouteOptionRole]
    relativePedestrianActivity: RelativePedestrianActivity
    typicalPedestrianMovementsPerMinute: float | None = Field(
        default=None,
        ge=0,
    )
    comparisonPedestrianFlow: ComparisonPedestrianFlowResponse
    livePedestrianFlow: PedestrianFlowEvidenceResponse
    historicalPedestrianFlow: PedestrianFlowEvidenceResponse
    balancedScore: float | None = Field(default=None, ge=0, le=1)


class RouteOptionsResponse(BaseModel):
    comparisonBasis: PedestrianFlowComparisonBasis
    generationReason: CandidateGenerationReason
    routes: list[RouteOptionResponse] = Field(min_length=1, max_length=3)
