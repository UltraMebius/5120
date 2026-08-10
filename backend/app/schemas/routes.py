"""Phase 1 route preview schema and future walking-route API boundary."""

from pydantic import BaseModel, Field

from ..models.crowd import (
    CoverageStatus,
    CrowdLevel,
    FrontendCrowdLevel,
)


class RouteOption(BaseModel):
    id: str
    name: str
    distanceKm: float = Field(ge=0)
    durationMin: int = Field(ge=0)
    crowdLevel: FrontendCrowdLevel
    internalCrowdLevel: CrowdLevel
    coverageStatus: CoverageStatus
    recommended: bool
    sensoryLevel: FrontendCrowdLevel = Field(
        description="Deprecated Phase 1 compatibility alias for crowdLevel."
    )
