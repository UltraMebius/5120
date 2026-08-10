"""Demonstrate Phase 5B-1 alert decisions with controlled in-memory data."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.models.crowd import CrowdPreference  # noqa: E402
from backend.app.models.spatial import PointCrowdEstimate  # noqa: E402
from backend.app.services.routing.route_crowd_alert_service import (  # noqa: E402
    RouteCrowdAlertService,
    RouteCrowdAlertState,
)
from backend.app.services.routing.route_crowd_evaluation_service import (  # noqa: E402
    RouteCrowdEvaluation,
    RouteSampleCrowdResult,
)
from backend.app.services.routing.route_sampling_service import (  # noqa: E402
    RouteSample,
)


def _evaluation(
    route_id: str,
    entries: tuple[tuple[str, float | None], ...],
) -> RouteCrowdEvaluation:
    results: list[RouteSampleCrowdResult] = []
    for index, (status, score) in enumerate(entries):
        sample = RouteSample(
            index=index,
            distance_along_route_meters=float(index * 50),
            longitude=144.9671,
            latitude=-37.8183 + index / 100_000,
        )
        has_support = status != "NO_DATA"
        results.append(
            RouteSampleCrowdResult(
                sample=sample,
                crowd=PointCrowdEstimate(
                    latitude=sample.latitude,
                    longitude=sample.longitude,
                    crowd_exposure_score=score,
                    crowd_level=None,
                    local_condition_score=None,
                    local_condition=None,
                    coverage_status=status,
                    nearby_sensors=1 if has_support else 0,
                    nearby_active_outdoor_sensors=1 if has_support else 0,
                    supporting_sensors=1 if has_support else 0,
                    nearest_sensor_distance_m=100.0 if has_support else None,
                    supporting_score_stddev=None,
                    weighting_method="inverse_distance_1_over_d",
                    updated_at=None,
                    source_window_start=None,
                    source_window_end=None,
                    support_radius_m=300.0,
                    reason=(
                        None
                        if has_support
                        else "NO_VALID_CURRENT_SENSOR_AVAILABLE"
                    ),
                    contributions=(),
                ),
            )
        )

    return RouteCrowdEvaluation(
        route_id=route_id,
        route_length_meters=float((len(results) - 1) * 50),
        sampling_interval_meters=50.0,
        sample_results=tuple(results),
    )


def main() -> int:
    controlled_cases = (
        (
            "ALERT controlled case",
            RouteCrowdAlertState.ALERT,
            _evaluation(
                "controlled-alert",
                (
                    ("SUPPORTED", 10.0),
                    ("SUPPORTED", 60.0),
                    ("LIMITED", 70.0),
                ),
            ),
        ),
        (
            "CLEAR controlled case",
            RouteCrowdAlertState.CLEAR,
            _evaluation(
                "controlled-clear",
                (
                    ("SUPPORTED", 10.0),
                    ("SUPPORTED", 60.0),
                    ("NO_DATA", None),
                ),
            ),
        ),
        (
            "INSUFFICIENT_DATA controlled case",
            RouteCrowdAlertState.INSUFFICIENT_DATA,
            _evaluation(
                "controlled-insufficient",
                (
                    ("NO_DATA", None),
                    ("NO_DATA", None),
                    ("NO_DATA", None),
                ),
            ),
        ),
    )
    service = RouteCrowdAlertService()

    for label, expected, evaluation in controlled_cases:
        result = service.evaluate_ahead(
            evaluation,
            CrowdPreference.AVOID_BUSY,
            current_progress_meters=0.0,
        )
        if result.decision is not expected:
            print(
                f"{label}: FAILED - expected {expected.value}, "
                f"received {result.decision.value}",
                file=sys.stderr,
            )
            return 1
        trigger = (
            "none"
            if result.trigger_start_sample_index is None
            else (
                f"{result.trigger_start_sample_index}-"
                f"{result.trigger_end_sample_index}"
            )
        )
        coverage = (
            "unavailable"
            if result.look_ahead_coverage_pct is None
            else f"{result.look_ahead_coverage_pct:.2f}%"
        )
        print(
            f"{label}: decision={result.decision.value}, "
            f"reason={result.reason.value}, trigger={trigger}, "
            f"coverage={coverage}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
