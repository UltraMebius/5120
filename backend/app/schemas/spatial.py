"""Exact V3 API response model for one point Crowd Exposure estimate."""

from datetime import datetime

from pydantic import BaseModel, Field

from ..models.crowd import CoverageStatus, CrowdLevel, LocalCondition


class PointCrowdEstimateResponse(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    crowdExposureScore: float | None = Field(default=None, ge=0, le=100)
    crowdLevel: CrowdLevel | None = None
    localConditionScore: float | None = Field(default=None, ge=0, le=100)
    localCondition: LocalCondition | None = None
    coverageStatus: CoverageStatus
    supportingSensors: int = Field(ge=0)
    nearestSensorDistanceM: float | None = Field(default=None, ge=0)
    supportingScoreStddev: float | None = Field(default=None, ge=0)
    weightingMethod: str
    updatedAt: datetime | None = None
