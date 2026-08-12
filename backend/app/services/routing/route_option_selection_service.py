"""Pure in-memory product-role selection for evaluated route candidates."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
import logging
import math
from time import perf_counter

from ...config import SETTINGS
from ...models.pedestrian_flow import RoutePedestrianFlowSummary
from .route_candidate_models import (
    CandidateGenerationReason,
    CandidateGenerationTimings,
    MultiRouteCandidateResult,
    RouteCandidate,
)


_LOGGER = logging.getLogger(__name__)


class PedestrianFlowComparisonBasis(str, Enum):
    LIVE = "LIVE"
    HISTORICAL_ESTIMATE = "HISTORICAL_ESTIMATE"
    UNKNOWN = "UNKNOWN"


class RouteOptionRole(str, Enum):
    CALMEST = "CALMEST"
    FASTEST = "FASTEST"
    BALANCED = "BALANCED"


class RelativePedestrianActivity(str, Enum):
    LOWEST = "LOWEST"
    MIDDLE = "MIDDLE"
    HIGHEST = "HIGHEST"
    UNKNOWN = "UNKNOWN"


ROLE_BADGE_ORDER = (
    RouteOptionRole.CALMEST,
    RouteOptionRole.FASTEST,
    RouteOptionRole.BALANCED,
)


class RouteOptionSelectionError(RuntimeError):
    """Candidate evidence cannot be compared or assigned safely."""


@dataclass(frozen=True, slots=True)
class ComparisonPedestrianFlow:
    basis: PedestrianFlowComparisonBasis
    typical_movements_per_minute: float | None
    p75_movements_per_minute: float | None
    maximum_movements_per_minute: float | None
    coverage_pct: float | None


@dataclass(frozen=True, slots=True)
class SelectedRouteOption:
    candidate: RouteCandidate
    role_badges: tuple[RouteOptionRole, ...]
    relative_pedestrian_activity: RelativePedestrianActivity
    comparison_pedestrian_flow: ComparisonPedestrianFlow
    balanced_score: float | None


@dataclass(frozen=True, slots=True)
class RouteOptionSelectionResult:
    comparison_basis: PedestrianFlowComparisonBasis
    generation_reason: CandidateGenerationReason
    routes: tuple[SelectedRouteOption, ...]
    candidate_timings: CandidateGenerationTimings
    route_role_selection_ms: float


def _finite_non_negative(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    if not math.isfinite(numeric) or numeric < 0.0:
        return None
    return numeric


def _summary(candidate: RouteCandidate) -> RoutePedestrianFlowSummary:
    summary = candidate.pedestrian_flow_summary
    if summary is None:
        raise RouteOptionSelectionError(
            "every route candidate must already have a pedestrian-flow summary"
        )
    return summary


def _basis_values(
    candidate: RouteCandidate,
    basis: PedestrianFlowComparisonBasis,
) -> tuple[float | None, float | None, float | None, float | None]:
    summary = _summary(candidate)
    if basis is PedestrianFlowComparisonBasis.LIVE:
        return (
            _finite_non_negative(
                summary.live_median_pedestrian_movements_per_minute
            ),
            _finite_non_negative(
                summary.live_p75_pedestrian_movements_per_minute
            ),
            _finite_non_negative(
                summary.live_maximum_pedestrian_movements_per_minute
            ),
            _finite_non_negative(summary.live_coverage_pct),
        )
    if basis is PedestrianFlowComparisonBasis.HISTORICAL_ESTIMATE:
        return (
            _finite_non_negative(
                summary.historical_median_pedestrian_movements_per_minute
            ),
            _finite_non_negative(
                summary.historical_p75_pedestrian_movements_per_minute
            ),
            _finite_non_negative(
                summary.historical_maximum_pedestrian_movements_per_minute
            ),
            _finite_non_negative(summary.historical_coverage_pct),
        )
    return None, None, None, None


def _optional_number_key(value: float | None) -> tuple[bool, float]:
    return value is None, math.inf if value is None else value


class RouteOptionSelectionService:
    """Assign FASTEST and defensible flow roles without I/O or resampling."""

    def __init__(
        self,
        *,
        minimum_coverage_pct: float = (
            SETTINGS.route.minimum_crowd_coverage_pct
        ),
    ) -> None:
        if not 0.0 <= minimum_coverage_pct <= 100.0:
            raise ValueError("minimum route flow coverage must be 0 to 100")
        self.minimum_coverage_pct = float(minimum_coverage_pct)

    def _qualified(
        self,
        candidate: RouteCandidate,
        basis: PedestrianFlowComparisonBasis,
    ) -> bool:
        _, p75, _, coverage = _basis_values(candidate, basis)
        return (
            coverage is not None
            and coverage >= self.minimum_coverage_pct
            and p75 is not None
        )

    def _comparison_basis(
        self,
        candidates: Sequence[RouteCandidate],
    ) -> PedestrianFlowComparisonBasis:
        if all(
            self._qualified(candidate, PedestrianFlowComparisonBasis.LIVE)
            for candidate in candidates
        ):
            return PedestrianFlowComparisonBasis.LIVE
        if all(
            self._qualified(
                candidate,
                PedestrianFlowComparisonBasis.HISTORICAL_ESTIMATE,
            )
            for candidate in candidates
        ):
            return PedestrianFlowComparisonBasis.HISTORICAL_ESTIMATE
        return PedestrianFlowComparisonBasis.UNKNOWN

    @staticmethod
    def _fastest_key(candidate: RouteCandidate) -> tuple[float, float, int, str]:
        return (
            candidate.duration_seconds,
            candidate.distance_meters,
            candidate.source_index,
            candidate.route_id,
        )

    @staticmethod
    def _calmest_key(
        candidate: RouteCandidate,
        basis: PedestrianFlowComparisonBasis,
    ) -> tuple[float, tuple[bool, float], tuple[bool, float], float, float, int, str]:
        median, p75, maximum, _ = _basis_values(candidate, basis)
        if p75 is None:
            raise RouteOptionSelectionError(
                "calmest selection requires a qualified common P75"
            )
        return (
            p75,
            _optional_number_key(median),
            _optional_number_key(maximum),
            candidate.duration_seconds,
            candidate.distance_meters,
            candidate.source_index,
            candidate.route_id,
        )

    @staticmethod
    def _normalized(
        value: float,
        minimum: float,
        maximum: float,
    ) -> float:
        if maximum == minimum:
            return 0.0
        return (value - minimum) / (maximum - minimum)

    def _balanced_scores(
        self,
        candidates: Sequence[RouteCandidate],
        basis: PedestrianFlowComparisonBasis,
    ) -> dict[str, float]:
        durations = tuple(candidate.duration_seconds for candidate in candidates)
        crowd_scores: list[float] = []
        for candidate in candidates:
            _, p75, _, _ = _basis_values(candidate, basis)
            if p75 is None:
                raise RouteOptionSelectionError(
                    "balanced selection requires a qualified common P75"
                )
            crowd_scores.append(p75)
        minimum_duration, maximum_duration = min(durations), max(durations)
        minimum_crowd, maximum_crowd = min(crowd_scores), max(crowd_scores)
        return {
            candidate.route_id: (
                0.5
                * self._normalized(
                    candidate.duration_seconds,
                    minimum_duration,
                    maximum_duration,
                )
                + 0.5
                * self._normalized(
                    crowd_score,
                    minimum_crowd,
                    maximum_crowd,
                )
            )
            for candidate, crowd_score in zip(candidates, crowd_scores)
        }

    def _relative_activity(
        self,
        candidates: Sequence[RouteCandidate],
        basis: PedestrianFlowComparisonBasis,
    ) -> dict[str, RelativePedestrianActivity]:
        result = {
            candidate.route_id: RelativePedestrianActivity.UNKNOWN
            for candidate in candidates
        }
        if basis is PedestrianFlowComparisonBasis.UNKNOWN or len(candidates) < 2:
            return result
        ordered = sorted(
            candidates,
            key=lambda candidate: self._calmest_key(candidate, basis),
        )
        result[ordered[0].route_id] = RelativePedestrianActivity.LOWEST
        result[ordered[-1].route_id] = RelativePedestrianActivity.HIGHEST
        for candidate in ordered[1:-1]:
            result[candidate.route_id] = RelativePedestrianActivity.MIDDLE
        return result

    @staticmethod
    def _response_order(
        candidates: Sequence[RouteCandidate],
        role_routes: dict[RouteOptionRole, RouteCandidate],
    ) -> tuple[RouteCandidate, ...]:
        ordered: list[RouteCandidate] = []
        seen: set[str] = set()
        for role in ROLE_BADGE_ORDER:
            candidate = role_routes.get(role)
            if candidate is not None and candidate.route_id not in seen:
                ordered.append(candidate)
                seen.add(candidate.route_id)
        for candidate in sorted(
            candidates,
            key=RouteOptionSelectionService._fastest_key,
        ):
            if candidate.route_id not in seen:
                ordered.append(candidate)
                seen.add(candidate.route_id)
        return tuple(ordered)

    def select_options(
        self,
        candidate_result: MultiRouteCandidateResult,
    ) -> RouteOptionSelectionResult:
        """Assign roles from existing summaries; perform no external work."""

        started = perf_counter()
        candidates = tuple(candidate_result.candidates)
        if not candidates:
            raise RouteOptionSelectionError("at least one route candidate is required")
        if len({candidate.route_id for candidate in candidates}) != len(candidates):
            raise RouteOptionSelectionError("route candidate IDs must be unique")
        for candidate in candidates:
            _summary(candidate)

        basis = self._comparison_basis(candidates)
        fastest = min(candidates, key=self._fastest_key)
        role_routes: dict[RouteOptionRole, RouteCandidate] = {
            RouteOptionRole.FASTEST: fastest
        }
        calmest: RouteCandidate | None = None
        if len(candidates) >= 2 and basis is not PedestrianFlowComparisonBasis.UNKNOWN:
            calmest = min(
                candidates,
                key=lambda candidate: self._calmest_key(candidate, basis),
            )
            role_routes[RouteOptionRole.CALMEST] = calmest

        balanced_scores: dict[str, float] = {}
        if len(candidates) >= 3 and basis is not PedestrianFlowComparisonBasis.UNKNOWN:
            balanced_scores = self._balanced_scores(candidates, basis)
            excluded_ids = {fastest.route_id}
            if calmest is not None:
                excluded_ids.add(calmest.route_id)
            eligible = tuple(
                candidate
                for candidate in candidates
                if candidate.route_id not in excluded_ids
            )
            balanced = min(
                eligible,
                key=lambda candidate: (
                    balanced_scores[candidate.route_id],
                    self._calmest_key(candidate, basis)[0],
                    candidate.duration_seconds,
                    candidate.distance_meters,
                    candidate.source_index,
                    candidate.route_id,
                ),
            )
            role_routes[RouteOptionRole.BALANCED] = balanced

        roles_by_id: dict[str, set[RouteOptionRole]] = {
            candidate.route_id: set() for candidate in candidates
        }
        for role, candidate in role_routes.items():
            roles_by_id[candidate.route_id].add(role)
        relative_by_id = self._relative_activity(candidates, basis)
        response_order = self._response_order(candidates, role_routes)
        routes = tuple(
            SelectedRouteOption(
                candidate=candidate,
                role_badges=tuple(
                    role
                    for role in ROLE_BADGE_ORDER
                    if role in roles_by_id[candidate.route_id]
                ),
                relative_pedestrian_activity=relative_by_id[candidate.route_id],
                comparison_pedestrian_flow=ComparisonPedestrianFlow(
                    basis=basis,
                    typical_movements_per_minute=_basis_values(
                        candidate, basis
                    )[0],
                    p75_movements_per_minute=_basis_values(candidate, basis)[1],
                    maximum_movements_per_minute=_basis_values(
                        candidate, basis
                    )[2],
                    coverage_pct=_basis_values(candidate, basis)[3],
                ),
                balanced_score=balanced_scores.get(candidate.route_id),
            )
            for candidate in response_order
        )
        elapsed_ms = (perf_counter() - started) * 1000.0
        _LOGGER.info(
            "route_option_selection route_role_selection_ms=%.3f "
            "candidate_count=%d mapbox_request_count=%d "
            "flow_sql_execution_count=%d total_ms=%.3f",
            elapsed_ms,
            len(candidates),
            candidate_result.timings.mapbox_request_count,
            candidate_result.timings.flow_sql_execution_count,
            candidate_result.timings.total_ms + elapsed_ms,
        )
        return RouteOptionSelectionResult(
            comparison_basis=basis,
            generation_reason=candidate_result.reason,
            routes=routes,
            candidate_timings=candidate_result.timings,
            route_role_selection_ms=elapsed_ms,
        )
