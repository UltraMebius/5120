"""Project-approved MVP route crowd aggregation and deterministic ranking."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math

from ...config import SETTINGS
from ...models.crowd import (
    CoverageStatus,
    CrowdLevel,
    CrowdPreference,
    FrontendCrowdLevel,
    RoutePreferenceStatus,
    RouteRankingStatus,
)
from ...schemas.routes import WalkingRouteOption
from ..crowd.current_activity_service import classify_crowd_level
from ..crowd.presentation import to_frontend_crowd_level
from .route_crowd_evaluation_service import (
    RouteCrowdEvaluation,
    RouteCrowdEvaluationService,
)


class RouteCrowdDataConsistencyError(RuntimeError):
    """Phase 3E results cannot be combined into one honest ranking."""


@dataclass(frozen=True, slots=True)
class RouteCrowdSummary:
    """One route's coverage and, when sufficient, crowd metrics."""

    route_id: str
    supported_pct: float
    limited_coverage_pct: float
    data_coverage_pct: float
    no_data_pct: float
    sample_interval_m: float
    sample_count: int
    numeric_sample_count: int
    median_crowd_exposure_score: float | None
    p75_crowd_exposure_score: float | None
    maximum_crowd_exposure_score: float | None
    pct_above_preference: float | None
    pct_very_high: float | None
    route_crowd_level: CrowdLevel | None
    route_crowd_presentation_level: FrontendCrowdLevel | None
    preference_status: RoutePreferenceStatus

    @property
    def evaluable(self) -> bool:
        return self.preference_status is not RoutePreferenceStatus.INSUFFICIENT_DATA


@dataclass(frozen=True, slots=True)
class RankedRouteCrowdResult:
    """A source Mapbox route paired with its backend-owned decision."""

    route: WalkingRouteOption
    evaluation: RouteCrowdEvaluation
    summary: RouteCrowdSummary
    rank: int | None
    is_recommended: bool


@dataclass(frozen=True, slots=True)
class RouteCrowdRankingResult:
    """All routes in final display order plus recommendation metadata."""

    routes: tuple[RankedRouteCrowdResult, ...]
    recommended_route_id: str | None
    ranking_status: RouteRankingStatus


def continuous_percentile(values: Sequence[float], quantile: float) -> float:
    """Return linear-interpolated percentile equivalent to PERCENTILE_CONT."""

    if not values:
        raise ValueError("at least one percentile value is required")
    if not math.isfinite(quantile) or not 0.0 <= quantile <= 1.0:
        raise ValueError("quantile must be finite and between zero and one")
    sorted_values = sorted(float(value) for value in values)
    if any(not math.isfinite(value) for value in sorted_values):
        raise ValueError("percentile values must be finite")

    position = (len(sorted_values) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    fraction = position - lower
    return sorted_values[lower] + fraction * (
        sorted_values[upper] - sorted_values[lower]
    )


def aggregate_route_crowd(
    evaluation: RouteCrowdEvaluation,
    *,
    preference_threshold: float,
    minimum_coverage_pct: float,
) -> RouteCrowdSummary:
    """Apply the approved equal-sample coverage gate and route metrics."""

    if evaluation.route_id is None:
        raise RouteCrowdDataConsistencyError("route evaluation has no route ID")
    if not 0.0 <= minimum_coverage_pct <= 100.0:
        raise ValueError("minimum route crowd coverage must be between 0 and 100")
    if not math.isfinite(preference_threshold) or not 0.0 <= preference_threshold <= 100.0:
        raise ValueError("preference threshold must be between 0 and 100")

    total_count = evaluation.sample_count
    if total_count <= 0:
        raise RouteCrowdDataConsistencyError("route evaluation has no samples")

    supported_count = 0
    limited_count = 0
    no_data_count = 0
    numeric_scores: list[float] = []

    for result in evaluation.sample_results:
        status = result.crowd.coverage_status
        if status == CoverageStatus.SUPPORTED.value:
            supported_count += 1
        elif status == CoverageStatus.LIMITED.value:
            limited_count += 1
        elif status == CoverageStatus.NO_DATA.value:
            no_data_count += 1
        else:
            raise RouteCrowdDataConsistencyError(
                f"route sample has unsupported coverage status: {status}"
            )

        score = result.crowd.crowd_exposure_score
        if status not in (
            CoverageStatus.SUPPORTED.value,
            CoverageStatus.LIMITED.value,
        ) or score is None:
            continue
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise RouteCrowdDataConsistencyError(
                "eligible route sample has a non-numeric crowd score"
            )
        numeric_score = float(score)
        if not math.isfinite(numeric_score) or not 0.0 <= numeric_score <= 100.0:
            raise RouteCrowdDataConsistencyError(
                "eligible route sample score must be between 0 and 100"
            )
        numeric_scores.append(numeric_score)

    percentage_factor = 100.0 / total_count
    data_coverage_pct = len(numeric_scores) * percentage_factor
    base_fields = {
        "route_id": evaluation.route_id,
        "supported_pct": supported_count * percentage_factor,
        "limited_coverage_pct": limited_count * percentage_factor,
        "data_coverage_pct": data_coverage_pct,
        "no_data_pct": no_data_count * percentage_factor,
        "sample_interval_m": evaluation.sampling_interval_meters,
        "sample_count": total_count,
        "numeric_sample_count": len(numeric_scores),
    }

    if data_coverage_pct < minimum_coverage_pct:
        return RouteCrowdSummary(
            **base_fields,
            median_crowd_exposure_score=None,
            p75_crowd_exposure_score=None,
            maximum_crowd_exposure_score=None,
            pct_above_preference=None,
            pct_very_high=None,
            route_crowd_level=None,
            route_crowd_presentation_level=None,
            preference_status=RoutePreferenceStatus.INSUFFICIENT_DATA,
        )

    p75_score = continuous_percentile(numeric_scores, 0.75)
    crowd_level = CrowdLevel(classify_crowd_level(p75_score))
    numeric_count = len(numeric_scores)
    above_count = sum(score > preference_threshold for score in numeric_scores)
    very_high_count = sum(
        classify_crowd_level(score) == CrowdLevel.VERY_HIGH.value
        for score in numeric_scores
    )
    preference_status = (
        RoutePreferenceStatus.WITHIN_PREFERENCE
        if p75_score <= preference_threshold
        else RoutePreferenceStatus.ABOVE_PREFERENCE
    )
    return RouteCrowdSummary(
        **base_fields,
        median_crowd_exposure_score=continuous_percentile(
            numeric_scores, 0.5
        ),
        p75_crowd_exposure_score=p75_score,
        maximum_crowd_exposure_score=max(numeric_scores),
        pct_above_preference=100.0 * above_count / numeric_count,
        pct_very_high=100.0 * very_high_count / numeric_count,
        route_crowd_level=crowd_level,
        route_crowd_presentation_level=to_frontend_crowd_level(crowd_level),
        preference_status=preference_status,
    )


class RouteCrowdRankingService:
    """Reuse Phase 3E and own all route aggregation/ranking decisions."""

    def __init__(
        self,
        evaluation_service: RouteCrowdEvaluationService | None = None,
        *,
        minimum_coverage_pct: float = (
            SETTINGS.route.minimum_crowd_coverage_pct
        ),
        preference_thresholds: Mapping[CrowdPreference, float] | None = None,
    ) -> None:
        self.evaluation_service = (
            evaluation_service or RouteCrowdEvaluationService()
        )
        self.minimum_coverage_pct = float(minimum_coverage_pct)
        if not 0.0 <= self.minimum_coverage_pct <= 100.0:
            raise ValueError(
                "minimum route crowd coverage must be between 0 and 100"
            )
        configured_thresholds = preference_thresholds or {
            CrowdPreference.AVOID_BUSY: SETTINGS.preferences.avoid_busy_max_score,
            CrowdPreference.PREFER_QUIETER: (
                SETTINGS.preferences.prefer_quieter_max_score
            ),
            CrowdPreference.FLEXIBLE: SETTINGS.preferences.flexible_max_score,
        }
        self.preference_thresholds = {
            preference: float(threshold)
            for preference, threshold in configured_thresholds.items()
        }
        if set(self.preference_thresholds) != set(CrowdPreference):
            raise ValueError("all crowd preference thresholds are required")
        if any(
            not math.isfinite(threshold) or not 0.0 <= threshold <= 100.0
            for threshold in self.preference_thresholds.values()
        ):
            raise ValueError("crowd preference thresholds must be between 0 and 100")

    @staticmethod
    def _assert_unique_routes(routes: Sequence[WalkingRouteOption]) -> None:
        ids = [route.id for route in routes]
        indexes = [route.routeIndex for route in routes]
        if len(ids) != len(set(ids)):
            raise RouteCrowdDataConsistencyError("route IDs must be unique")
        if len(indexes) != len(set(indexes)):
            raise RouteCrowdDataConsistencyError(
                "Mapbox route indexes must be unique"
            )

    @staticmethod
    def _assert_one_materialisation(
        evaluations: Sequence[RouteCrowdEvaluation],
    ) -> None:
        snapshots = {
            (
                result.crowd.source_window_start,
                result.crowd.source_window_end,
                result.crowd.updated_at,
            )
            for evaluation in evaluations
            for result in evaluation.sample_results
        }
        if len(snapshots) > 1:
            raise RouteCrowdDataConsistencyError(
                "route samples span multiple current crowd materialisations"
            )

    def rank_routes(
        self,
        routes: Sequence[WalkingRouteOption],
        preference: CrowdPreference,
    ) -> RouteCrowdRankingResult:
        if not routes:
            raise ValueError("at least one walking route is required")
        self._assert_unique_routes(routes)
        threshold = self.preference_thresholds[preference]
        evaluations = tuple(
            self.evaluation_service.evaluate_geometry(
                route.geometry,
                route_id=route.id,
            )
            for route in routes
        )
        self._assert_one_materialisation(evaluations)

        evaluated = [
            (
                route,
                evaluation,
                aggregate_route_crowd(
                    evaluation,
                    preference_threshold=threshold,
                    minimum_coverage_pct=self.minimum_coverage_pct,
                ),
            )
            for route, evaluation in zip(routes, evaluations)
        ]
        sufficient = [item for item in evaluated if item[2].evaluable]
        insufficient = [item for item in evaluated if not item[2].evaluable]
        sufficient.sort(
            key=lambda item: (
                item[2].no_data_pct,
                item[2].pct_above_preference,
                item[2].p75_crowd_exposure_score,
                item[2].maximum_crowd_exposure_score,
                item[0].durationSeconds,
                item[0].routeIndex,
            )
        )
        insufficient.sort(key=lambda item: item[0].routeIndex)

        recommended_route_id = sufficient[0][0].id if sufficient else None
        ordered: list[RankedRouteCrowdResult] = []
        for index, (route, evaluation, summary) in enumerate(
            sufficient,
            start=1,
        ):
            ordered.append(
                RankedRouteCrowdResult(
                    route=route,
                    evaluation=evaluation,
                    summary=summary,
                    rank=index,
                    is_recommended=route.id == recommended_route_id,
                )
            )
        ordered.extend(
            RankedRouteCrowdResult(
                route=route,
                evaluation=evaluation,
                summary=summary,
                rank=None,
                is_recommended=False,
            )
            for route, evaluation, summary in insufficient
        )
        return RouteCrowdRankingResult(
            routes=tuple(ordered),
            recommended_route_id=recommended_route_id,
            ranking_status=(
                RouteRankingStatus.PROVISIONAL
                if sufficient
                else RouteRankingStatus.INSUFFICIENT_DATA
            ),
        )
