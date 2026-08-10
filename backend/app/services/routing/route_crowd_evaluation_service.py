"""Compose uniform route sampling with authoritative point crowd evaluation."""

from dataclasses import dataclass
from typing import Protocol

from ...models.spatial import PointCrowdEstimate
from ..crowd.spatial_crowd_service import SpatialCrowdService
from .route_sampling_service import (
    RouteSample,
    RouteSamplingService,
    SampledRoute,
)


class _RouteSampler(Protocol):
    def sample_geometry(self, geometry: object) -> SampledRoute: ...


class _SpatialPointEvaluator(Protocol):
    def evaluate(
        self,
        *,
        longitude: float,
        latitude: float,
    ) -> PointCrowdEstimate: ...


@dataclass(frozen=True, slots=True)
class RouteSampleCrowdResult:
    """One Phase 3D sample paired with its unchanged Phase 2D point result."""

    sample: RouteSample
    crowd: PointCrowdEstimate


@dataclass(frozen=True, slots=True)
class RouteCrowdEvaluation:
    """Trace metadata and ordered sample-level results for one route."""

    route_id: str | None
    route_length_meters: float
    sampling_interval_meters: float
    sample_results: tuple[RouteSampleCrowdResult, ...]

    @property
    def sample_count(self) -> int:
        return len(self.sample_results)


class RouteCrowdEvaluationService:
    """Evaluate every ordered route sample in process without aggregation."""

    def __init__(
        self,
        sampling_service: _RouteSampler | None = None,
        spatial_crowd_service: _SpatialPointEvaluator | None = None,
    ) -> None:
        self.sampling_service = sampling_service or RouteSamplingService()
        self.spatial_crowd_service = (
            spatial_crowd_service or SpatialCrowdService()
        )

    def evaluate_geometry(
        self,
        geometry: object,
        *,
        route_id: str | None = None,
    ) -> RouteCrowdEvaluation:
        sampled_route = self.sampling_service.sample_geometry(geometry)
        results = tuple(
            RouteSampleCrowdResult(
                sample=sample,
                crowd=self.spatial_crowd_service.evaluate(
                    longitude=sample.longitude,
                    latitude=sample.latitude,
                ),
            )
            for sample in sampled_route.samples
        )
        return RouteCrowdEvaluation(
            route_id=route_id,
            route_length_meters=sampled_route.route_length_meters,
            sampling_interval_meters=sampled_route.sampling_interval_meters,
            sample_results=results,
        )
