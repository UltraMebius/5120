"""Deterministic symmetric sampled-corridor route comparison."""

from collections.abc import Sequence

from .route_candidate_config import (
    ROUTE_COMPARISON_SAMPLE_INTERVAL_M,
    ROUTE_SIMILARITY_DIRECTIONAL_THRESHOLD,
    ROUTE_SPATIAL_MATCH_TOLERANCE_M,
)
from .route_candidate_models import RouteSimilarityResult
from .route_sampling_service import (
    RouteSample,
    RouteSamplingService,
    haversine_distance_meters,
)


class RouteDistinctnessService:
    """Compare routes by bidirectional proximity of 50m samples."""

    def __init__(
        self,
        *,
        sample_interval_meters: float = ROUTE_COMPARISON_SAMPLE_INTERVAL_M,
        match_tolerance_meters: float = ROUTE_SPATIAL_MATCH_TOLERANCE_M,
        similarity_threshold: float = ROUTE_SIMILARITY_DIRECTIONAL_THRESHOLD,
    ) -> None:
        if match_tolerance_meters <= 0.0:
            raise ValueError("route match tolerance must be positive")
        if not 0.0 <= similarity_threshold <= 1.0:
            raise ValueError("route similarity threshold must be between 0 and 1")
        self.sampling_service = RouteSamplingService(sample_interval_meters)
        self.match_tolerance_meters = float(match_tolerance_meters)
        self.similarity_threshold = float(similarity_threshold)

    def coverages_are_too_similar(
        self,
        coverage_a_to_b: float,
        coverage_b_to_a: float,
    ) -> bool:
        """Apply the inclusive threshold to both directional coverages."""

        return (
            coverage_a_to_b >= self.similarity_threshold
            and coverage_b_to_a >= self.similarity_threshold
        )

    def _matched_count(
        self,
        source: Sequence[RouteSample],
        comparison: Sequence[RouteSample],
    ) -> int:
        return sum(
            any(
                haversine_distance_meters(
                    (sample.longitude, sample.latitude),
                    (other.longitude, other.latitude),
                )
                <= self.match_tolerance_meters
                for other in comparison
            )
            for sample in source
        )

    def compare(self, geometry_a: object, geometry_b: object) -> RouteSimilarityResult:
        sampled_a = self.sampling_service.sample_geometry(geometry_a).samples
        sampled_b = self.sampling_service.sample_geometry(geometry_b).samples
        matched_a = self._matched_count(sampled_a, sampled_b)
        matched_b = self._matched_count(sampled_b, sampled_a)
        coverage_a = matched_a / len(sampled_a)
        coverage_b = matched_b / len(sampled_b)
        return RouteSimilarityResult(
            route_a_sample_count=len(sampled_a),
            route_b_sample_count=len(sampled_b),
            matched_route_a_samples=matched_a,
            matched_route_b_samples=matched_b,
            coverage_a_to_b=coverage_a,
            coverage_b_to_a=coverage_b,
            too_similar=self.coverages_are_too_similar(
                coverage_a,
                coverage_b,
            ),
        )
