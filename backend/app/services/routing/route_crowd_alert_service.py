"""Pure Phase 5B-1 ahead-of-route crowd-alert decision engine."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math

from ...config import SETTINGS
from ...models.crowd import (
    CoverageStatus,
    CrowdPreference,
    RouteCrowdAlertReason,
    RouteCrowdAlertState,
)
from .route_crowd_evaluation_service import (
    RouteCrowdEvaluation,
    RouteSampleCrowdResult,
)


class RouteCrowdAlertConfigurationError(ValueError):
    """Raised when project-owned alert settings are invalid."""


class RouteCrowdAlertDataConsistencyError(RuntimeError):
    """Raised when a Phase 3E evaluation violates the ordered data contract."""


@dataclass(frozen=True, slots=True)
class RouteCrowdAlertDecision:
    """Immutable alert decision and honest look-ahead diagnostics."""

    route_id: str | None
    decision: RouteCrowdAlertState
    reason: RouteCrowdAlertReason
    preference: CrowdPreference
    threshold: float
    current_progress_meters: float
    look_ahead_distance_meters: float
    required_consecutive_samples: int
    window_start_meters: float
    window_end_meters: float
    total_look_ahead_samples: int
    numeric_look_ahead_samples: int
    supported_samples: int
    limited_samples: int
    no_data_samples: int
    look_ahead_coverage_pct: float | None
    pct_above_preference_in_window: float | None
    maximum_exposure_in_window: float | None
    trigger_start_sample_index: int | None
    trigger_end_sample_index: int | None
    trigger_start_distance_meters: float | None
    trigger_end_distance_meters: float | None
    trigger_sample_count: int | None
    maximum_exposure_in_trigger: float | None
    first_trigger_exposure: float | None
    second_trigger_exposure: float | None


@dataclass(frozen=True, slots=True)
class _WindowSample:
    result: RouteSampleCrowdResult
    usable_score: float | None


def _validated_positive_number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RouteCrowdAlertConfigurationError(f"{name} must be numeric")
    numeric_value = float(value)
    if not math.isfinite(numeric_value) or numeric_value <= 0:
        raise RouteCrowdAlertConfigurationError(
            f"{name} must be finite and greater than zero"
        )
    return numeric_value


def _validated_required_samples(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 2:
        raise RouteCrowdAlertConfigurationError(
            "required consecutive samples must be an integer of at least two"
        )
    return value


def _validated_thresholds(
    configured_thresholds: Mapping[CrowdPreference, float],
) -> dict[CrowdPreference, float]:
    if any(
        isinstance(threshold, bool)
        or not isinstance(threshold, (int, float))
        for threshold in configured_thresholds.values()
    ):
        raise RouteCrowdAlertConfigurationError(
            "crowd preference thresholds must be numeric"
        )
    thresholds = {
        preference: float(threshold)
        for preference, threshold in configured_thresholds.items()
    }
    if set(thresholds) != set(CrowdPreference):
        raise RouteCrowdAlertConfigurationError(
            "all crowd preference thresholds are required"
        )
    if any(
        not math.isfinite(threshold) or not 0.0 <= threshold <= 100.0
        for threshold in thresholds.values()
    ):
        raise RouteCrowdAlertConfigurationError(
            "crowd preference thresholds must be between zero and 100"
        )
    return thresholds


def _validate_sample_order(
    sample_results: Sequence[RouteSampleCrowdResult],
) -> None:
    previous_index: int | None = None
    previous_distance: float | None = None

    for result in sample_results:
        sample = result.sample
        index = sample.index
        distance = sample.distance_along_route_meters
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            raise RouteCrowdAlertDataConsistencyError(
                "route sample indexes must be non-negative integers"
            )
        if (
            isinstance(distance, bool)
            or not isinstance(distance, (int, float))
            or not math.isfinite(float(distance))
            or float(distance) < 0.0
        ):
            raise RouteCrowdAlertDataConsistencyError(
                "route sample distances must be finite and non-negative"
            )
        numeric_distance = float(distance)
        if previous_index is not None and index != previous_index + 1:
            raise RouteCrowdAlertDataConsistencyError(
                "route sample indexes must be contiguous in route order"
            )
        if (
            previous_distance is not None
            and numeric_distance <= previous_distance
        ):
            raise RouteCrowdAlertDataConsistencyError(
                "route sample distances must increase in route order"
            )
        previous_index = index
        previous_distance = numeric_distance


def _usable_score(result: RouteSampleCrowdResult) -> float | None:
    status = result.crowd.coverage_status
    valid_statuses = {
        CoverageStatus.SUPPORTED.value,
        CoverageStatus.LIMITED.value,
        CoverageStatus.NO_DATA.value,
    }
    if status not in valid_statuses:
        raise RouteCrowdAlertDataConsistencyError(
            f"route sample has unsupported coverage status: {status}"
        )
    if status == CoverageStatus.NO_DATA.value:
        return None

    score = result.crowd.crowd_exposure_score
    if score is None:
        return None
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        raise RouteCrowdAlertDataConsistencyError(
            "eligible route sample has a non-numeric crowd score"
        )
    numeric_score = float(score)
    if not math.isfinite(numeric_score) or not 0.0 <= numeric_score <= 100.0:
        raise RouteCrowdAlertDataConsistencyError(
            "eligible route sample score must be between zero and 100"
        )
    return numeric_score


def _first_qualifying_streak(
    window_samples: Sequence[_WindowSample],
    *,
    required_samples: int,
    threshold: float,
) -> tuple[_WindowSample, ...] | None:
    current_streak: list[_WindowSample] = []

    for window_sample in window_samples:
        score = window_sample.usable_score
        if score is not None and score > threshold:
            current_streak.append(window_sample)
            continue
        if len(current_streak) >= required_samples:
            return tuple(current_streak)
        current_streak = []

    return (
        tuple(current_streak)
        if len(current_streak) >= required_samples
        else None
    )


class RouteCrowdAlertService:
    """Evaluate an existing Phase 3E route result without I/O or persistence."""

    def __init__(
        self,
        *,
        look_ahead_distance_meters: float = (
            SETTINGS.route_alert.look_ahead_distance_m
        ),
        required_consecutive_samples: int = (
            SETTINGS.route_alert.required_consecutive_samples
        ),
        preference_thresholds: Mapping[CrowdPreference, float] | None = None,
    ) -> None:
        self.look_ahead_distance_meters = _validated_positive_number(
            look_ahead_distance_meters,
            "look-ahead distance",
        )
        self.required_consecutive_samples = _validated_required_samples(
            required_consecutive_samples
        )
        configured_thresholds = (
            {
                CrowdPreference.AVOID_BUSY: (
                    SETTINGS.preferences.avoid_busy_max_score
                ),
                CrowdPreference.PREFER_QUIETER: (
                    SETTINGS.preferences.prefer_quieter_max_score
                ),
                CrowdPreference.FLEXIBLE: (
                    SETTINGS.preferences.flexible_max_score
                ),
            }
            if preference_thresholds is None
            else preference_thresholds
        )
        self.preference_thresholds = _validated_thresholds(
            configured_thresholds
        )

    def evaluate_ahead(
        self,
        route_evaluation: RouteCrowdEvaluation,
        preference: CrowdPreference,
        current_progress_meters: float = 0.0,
    ) -> RouteCrowdAlertDecision:
        """Return the deterministic decision for `(progress, progress + L]`."""

        if (
            isinstance(current_progress_meters, bool)
            or not isinstance(current_progress_meters, (int, float))
        ):
            raise ValueError("current progress must be numeric")
        progress = float(current_progress_meters)
        if not math.isfinite(progress) or progress < 0.0:
            raise ValueError(
                "current progress must be finite and non-negative"
            )
        window_end = progress + self.look_ahead_distance_meters
        if not math.isfinite(window_end):
            raise ValueError("look-ahead window end must be finite")

        if not isinstance(preference, CrowdPreference):
            raise ValueError("unsupported crowd preference") from None
        threshold = self.preference_thresholds[preference]

        _validate_sample_order(route_evaluation.sample_results)
        window_results = tuple(
            result
            for result in route_evaluation.sample_results
            if result.sample.distance_along_route_meters > progress
            and result.sample.distance_along_route_meters <= window_end
        )
        window_samples = tuple(
            _WindowSample(result=result, usable_score=_usable_score(result))
            for result in window_results
        )

        total_count = len(window_samples)
        supported_count = sum(
            sample.result.crowd.coverage_status
            == CoverageStatus.SUPPORTED.value
            for sample in window_samples
        )
        limited_count = sum(
            sample.result.crowd.coverage_status
            == CoverageStatus.LIMITED.value
            for sample in window_samples
        )
        no_data_count = sum(
            sample.result.crowd.coverage_status
            == CoverageStatus.NO_DATA.value
            for sample in window_samples
        )
        numeric_scores = tuple(
            sample.usable_score
            for sample in window_samples
            if sample.usable_score is not None
        )
        numeric_count = len(numeric_scores)
        above_count = sum(score > threshold for score in numeric_scores)
        trigger = _first_qualifying_streak(
            window_samples,
            required_samples=self.required_consecutive_samples,
            threshold=threshold,
        )

        if trigger is not None:
            decision = RouteCrowdAlertState.ALERT
            reason = (
                RouteCrowdAlertReason.CONSECUTIVE_ABOVE_PREFERENCE_DETECTED
            )
        elif total_count == 0:
            decision = RouteCrowdAlertState.INSUFFICIENT_DATA
            reason = RouteCrowdAlertReason.NO_SAMPLES_AHEAD
        elif numeric_count == 0:
            decision = RouteCrowdAlertState.INSUFFICIENT_DATA
            reason = RouteCrowdAlertReason.NO_USABLE_LOOK_AHEAD_CROWD_DATA
        else:
            decision = RouteCrowdAlertState.CLEAR
            reason = RouteCrowdAlertReason.NO_CONSECUTIVE_ABOVE_PREFERENCE

        trigger_scores = (
            tuple(
                sample.usable_score
                for sample in trigger
                if sample.usable_score is not None
            )
            if trigger is not None
            else ()
        )
        trigger_start = trigger[0].result.sample if trigger else None
        trigger_end = trigger[-1].result.sample if trigger else None
        return RouteCrowdAlertDecision(
            route_id=route_evaluation.route_id,
            decision=decision,
            reason=reason,
            preference=preference,
            threshold=threshold,
            current_progress_meters=progress,
            look_ahead_distance_meters=self.look_ahead_distance_meters,
            required_consecutive_samples=self.required_consecutive_samples,
            window_start_meters=progress,
            window_end_meters=window_end,
            total_look_ahead_samples=total_count,
            numeric_look_ahead_samples=numeric_count,
            supported_samples=supported_count,
            limited_samples=limited_count,
            no_data_samples=no_data_count,
            look_ahead_coverage_pct=(
                100.0 * numeric_count / total_count if total_count else None
            ),
            pct_above_preference_in_window=(
                100.0 * above_count / numeric_count
                if numeric_count
                else None
            ),
            maximum_exposure_in_window=(
                max(numeric_scores) if numeric_scores else None
            ),
            trigger_start_sample_index=(
                trigger_start.index if trigger_start else None
            ),
            trigger_end_sample_index=(
                trigger_end.index if trigger_end else None
            ),
            trigger_start_distance_meters=(
                trigger_start.distance_along_route_meters
                if trigger_start
                else None
            ),
            trigger_end_distance_meters=(
                trigger_end.distance_along_route_meters
                if trigger_end
                else None
            ),
            trigger_sample_count=len(trigger) if trigger else None,
            maximum_exposure_in_trigger=(
                max(trigger_scores) if trigger_scores else None
            ),
            first_trigger_exposure=(
                trigger_scores[0] if trigger_scores else None
            ),
            second_trigger_exposure=(
                trigger_scores[1] if len(trigger_scores) >= 2 else None
            ),
        )
