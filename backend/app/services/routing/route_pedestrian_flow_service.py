"""Multi-route sampling, batched flow evaluation, aggregation, and timings."""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
import logging
import math
from time import perf_counter
from typing import Protocol

from ...models.pedestrian_flow import (
    FlowSamplePoint,
    PedestrianFlowBatchEvaluation,
    PedestrianFlowPipelineTimings,
    RoutePedestrianFlowSummary,
    SamplePedestrianFlow,
)
from ..crowd.pedestrian_flow_service import PedestrianFlowService
from .route_crowd_ranking_service import continuous_percentile
from .route_sampling_service import RouteSamplingService, SampledRoute


_LOGGER = logging.getLogger(__name__)


class RoutePedestrianFlowDataConsistencyError(RuntimeError):
    """Route samples or batched flow outputs cannot be mapped safely."""


class _RouteSampler(Protocol):
    def sample_geometry(self, geometry: object) -> SampledRoute: ...


class _FlowEvaluator(Protocol):
    def evaluate_samples(
        self,
        samples: Sequence[FlowSamplePoint],
    ) -> PedestrianFlowBatchEvaluation: ...


@dataclass(frozen=True, slots=True)
class RoutePedestrianFlowInput:
    """One route geometry identified independently of display ordering."""

    route_index: int
    geometry: object
    route_id: str | None = None


@dataclass(frozen=True, slots=True)
class RoutePedestrianFlowEvaluation:
    """One sampled route plus its source-separated flow summary."""

    route_index: int
    route_id: str | None
    route_length_meters: float
    sampling_interval_meters: float
    samples: tuple[SamplePedestrianFlow, ...]
    summary: RoutePedestrianFlowSummary
    sampling_ms: float = 0.0
    aggregation_ms: float = 0.0


@dataclass(frozen=True, slots=True)
class RoutePedestrianFlowPipelineResult:
    """All route evaluations from one shared spatial batch."""

    routes: tuple[RoutePedestrianFlowEvaluation, ...]
    timings: PedestrianFlowPipelineTimings


def _valid_flow_values(
    values: Sequence[float | None],
) -> tuple[float, ...]:
    numeric: list[float] = []
    for value in values:
        if value is None:
            continue
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or float(value) < 0.0
        ):
            raise RoutePedestrianFlowDataConsistencyError(
                "route pedestrian-flow values must be finite and non-negative"
            )
        numeric.append(float(value))
    return tuple(numeric)


def _statistics(
    values: Sequence[float],
) -> tuple[float | None, float | None, float | None]:
    if not values:
        return None, None, None
    return (
        continuous_percentile(values, 0.50),
        continuous_percentile(values, 0.75),
        max(values),
    )


class RoutePedestrianFlowAggregationService:
    """Aggregate live and historical sample values independently."""

    def aggregate_route(
        self,
        route_index: int,
        samples: Sequence[SamplePedestrianFlow],
    ) -> RoutePedestrianFlowSummary:
        route_samples = tuple(samples)
        if not route_samples:
            raise ValueError("at least one pedestrian-flow sample is required")
        if any(row.route_index != route_index for row in route_samples):
            raise RoutePedestrianFlowDataConsistencyError(
                "route aggregation received a different route index"
            )

        live_values = _valid_flow_values(
            tuple(
                row.live_pedestrian_movements_per_minute
                for row in route_samples
            )
        )
        historical_values = _valid_flow_values(
            tuple(
                row.historical_typical_movements_per_minute
                for row in route_samples
            )
        )
        live_median, live_p75, live_maximum = _statistics(live_values)
        historical_median, historical_p75, historical_maximum = _statistics(
            historical_values
        )
        total = len(route_samples)
        return RoutePedestrianFlowSummary(
            route_index=route_index,
            total_sample_count=total,
            live_numeric_sample_count=len(live_values),
            historical_numeric_sample_count=len(historical_values),
            live_coverage_pct=100.0 * len(live_values) / total,
            historical_coverage_pct=100.0 * len(historical_values) / total,
            live_median_pedestrian_movements_per_minute=live_median,
            live_p75_pedestrian_movements_per_minute=live_p75,
            live_maximum_pedestrian_movements_per_minute=live_maximum,
            historical_median_pedestrian_movements_per_minute=(
                historical_median
            ),
            historical_p75_pedestrian_movements_per_minute=historical_p75,
            historical_maximum_pedestrian_movements_per_minute=(
                historical_maximum
            ),
        )


class RoutePedestrianFlowService:
    """Sample multiple routes and evaluate all points through one batch call."""

    def __init__(
        self,
        sampling_service: _RouteSampler | None = None,
        flow_service: _FlowEvaluator | None = None,
        aggregation_service: RoutePedestrianFlowAggregationService | None = None,
    ) -> None:
        self.sampling_service = sampling_service or RouteSamplingService()
        self.flow_service = flow_service or PedestrianFlowService()
        self.aggregation_service = (
            aggregation_service or RoutePedestrianFlowAggregationService()
        )

    @staticmethod
    def _validate_routes(routes: Sequence[RoutePedestrianFlowInput]) -> None:
        indexes = [route.route_index for route in routes]
        if not routes:
            raise ValueError("at least one route is required")
        if any(
            isinstance(index, bool)
            or not isinstance(index, int)
            or index < 0
            for index in indexes
        ):
            raise ValueError("route indexes must be non-negative integers")
        if len(indexes) != len(set(indexes)):
            raise ValueError("route indexes must be unique")

    def evaluate_routes(
        self,
        routes: Sequence[RoutePedestrianFlowInput],
    ) -> RoutePedestrianFlowPipelineResult:
        """Return source-separated summaries without ranking or role selection."""

        requested = tuple(routes)
        self._validate_routes(requested)

        sampling_started = perf_counter()
        sampled_routes: dict[int, SampledRoute] = {}
        route_sampling_ms: dict[int, float] = {}
        batch_samples: list[FlowSamplePoint] = []
        for route in requested:
            route_sampling_started = perf_counter()
            sampled = self.sampling_service.sample_geometry(route.geometry)
            sampled_routes[route.route_index] = sampled
            batch_samples.extend(
                FlowSamplePoint(
                    route_index=route.route_index,
                    sample_index=sample.index,
                    distance_along_route_meters=(
                        sample.distance_along_route_meters
                    ),
                    longitude=sample.longitude,
                    latitude=sample.latitude,
                )
                for sample in sampled.samples
            )
            route_sampling_ms[route.route_index] = (
                perf_counter() - route_sampling_started
            ) * 1000.0
        sampling_ms = (perf_counter() - sampling_started) * 1000.0

        batch_result = self.flow_service.evaluate_samples(tuple(batch_samples))
        expected_keys = {sample.key for sample in batch_samples}
        actual_keys = {
            (sample.route_index, sample.sample_index)
            for sample in batch_result.samples
        }
        if actual_keys != expected_keys or len(actual_keys) != len(
            batch_result.samples
        ):
            raise RoutePedestrianFlowDataConsistencyError(
                "batched flow output does not match requested route samples"
            )

        aggregation_started = perf_counter()
        flows_by_route: dict[int, list[SamplePedestrianFlow]] = defaultdict(list)
        for sample in batch_result.samples:
            flows_by_route[sample.route_index].append(sample)
        evaluations: list[RoutePedestrianFlowEvaluation] = []
        for route in requested:
            route_aggregation_started = perf_counter()
            ordered_flows = tuple(
                sorted(
                    flows_by_route[route.route_index],
                    key=lambda sample: sample.sample_index,
                )
            )
            sampled = sampled_routes[route.route_index]
            summary = self.aggregation_service.aggregate_route(
                route.route_index,
                ordered_flows,
            )
            route_aggregation_ms = (
                perf_counter() - route_aggregation_started
            ) * 1000.0
            evaluations.append(
                RoutePedestrianFlowEvaluation(
                    route_index=route.route_index,
                    route_id=route.route_id,
                    route_length_meters=sampled.route_length_meters,
                    sampling_interval_meters=sampled.sampling_interval_meters,
                    samples=ordered_flows,
                    summary=summary,
                    sampling_ms=route_sampling_ms[route.route_index],
                    aggregation_ms=route_aggregation_ms,
                )
            )
            _LOGGER.info(
                "route_crowd_evaluation_timing route_id=%s route_index=%d "
                "sampling_ms=%.3f aggregation_ms=%.3f "
                "local_evaluation_ms=%.3f shared_database_ms=%.3f "
                "sample_count=%d database_scope=shared_route_batch",
                route.route_id,
                route.route_index,
                route_sampling_ms[route.route_index],
                route_aggregation_ms,
                route_sampling_ms[route.route_index] + route_aggregation_ms,
                batch_result.flow_batch_db_ms,
                len(ordered_flows),
            )
        aggregation_ms = (perf_counter() - aggregation_started) * 1000.0

        timings = PedestrianFlowPipelineTimings(
            sampling_ms=sampling_ms,
            flow_batch_db_ms=batch_result.flow_batch_db_ms,
            flow_aggregation_ms=aggregation_ms,
            sql_execution_count=batch_result.sql_execution_count,
        )
        _LOGGER.info(
            "pedestrian_flow_pipeline sampling_ms=%.3f "
            "flow_batch_db_ms=%.3f flow_aggregation_ms=%.3f "
            "sql_execution_count=%d route_count=%d sample_count=%d",
            timings.sampling_ms,
            timings.flow_batch_db_ms,
            timings.flow_aggregation_ms,
            timings.sql_execution_count,
            len(requested),
            len(batch_samples),
        )
        return RoutePedestrianFlowPipelineResult(
            routes=tuple(evaluations),
            timings=timings,
        )
