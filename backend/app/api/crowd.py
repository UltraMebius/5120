"""Internal V3 point Crowd Exposure endpoint."""

from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Query

from ..db.exceptions import CalmWayDatabaseError
from ..schemas.spatial import PointCrowdEstimateResponse
from ..services.crowd.spatial_crowd_service import (
    CoordinateValidationError,
    SpatialCrowdService,
    SpatialDataConsistencyError,
)


router = APIRouter(tags=["crowd"])


@lru_cache
def get_spatial_crowd_service() -> SpatialCrowdService:
    """Construct lazily so FastAPI remains startable without a database."""

    return SpatialCrowdService()


@router.get("/crowd/point", response_model=PointCrowdEstimateResponse)
def evaluate_crowd_point(
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
    service: SpatialCrowdService = Depends(get_spatial_crowd_service),
) -> PointCrowdEstimateResponse:
    try:
        result = service.evaluate(longitude=lon, latitude=lat)
    except CoordinateValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except (CalmWayDatabaseError, SpatialDataConsistencyError) as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Current point crowd estimate unavailable: {exc}",
        ) from None

    return PointCrowdEstimateResponse(
        latitude=result.latitude,
        longitude=result.longitude,
        crowdExposureScore=result.crowd_exposure_score,
        crowdLevel=result.crowd_level,
        localConditionScore=result.local_condition_score,
        localCondition=result.local_condition,
        coverageStatus=result.coverage_status,
        supportingSensors=result.supporting_sensors,
        nearestSensorDistanceM=result.nearest_sensor_distance_m,
        supportingScoreStddev=result.supporting_score_stddev,
        weightingMethod=result.weighting_method,
        updatedAt=result.updated_at,
    )
