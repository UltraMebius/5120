from datetime import datetime, timezone

import pytest

from backend.app.models.crowd import (
    CrowdPreference,
    RoutePreferenceStatus,
    RouteRankingStatus,
)
from backend.app.models.spatial import PointCrowdEstimate
from backend.app.schemas.routes import GeoJsonLineString, WalkingRouteOption
from backend.app.services.routing.route_crowd_evaluation_service import (
    RouteCrowdEvaluation,
    RouteSampleCrowdResult,
)
from backend.app.services.routing.route_crowd_ranking_service import (
    RouteCrowdDataConsistencyError,
    RouteCrowdRankingService,
    aggregate_route_crowd,
    continuous_percentile,
)
from backend.app.services.routing.route_sampling_service import RouteSample


NOW = datetime(2026, 8, 10, 8, 20, tzinfo=timezone.utc)
WINDOW_START = datetime(2026, 8, 10, 8, 0, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 8, 10, 8, 15, tzinfo=timezone.utc)


def _point(
    index: int,
    status: str,
    score: float | None,
    *,
    updated_at: datetime | None = NOW,
) -> RouteSampleCrowdResult:
    sample = RouteSample(
        index=index,
        distance_along_route_meters=float(index * 50),
        longitude=144.96 + index / 1_000_000,
        latitude=-37.81,
    )
    has_support = status != "NO_DATA"
    return RouteSampleCrowdResult(
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
            updated_at=updated_at,
            source_window_start=WINDOW_START,
            source_window_end=WINDOW_END,
            support_radius_m=300.0,
            reason=None if has_support else "NO_VALID_CURRENT_SENSOR_AVAILABLE",
            contributions=(),
        ),
    )


def _evaluation(
    route_id: str,
    entries: list[tuple[str, float | None]],
    *,
    updated_at: datetime | None = NOW,
) -> RouteCrowdEvaluation:
    results = tuple(
        _point(index, status, score, updated_at=updated_at)
        for index, (status, score) in enumerate(entries)
    )
    return RouteCrowdEvaluation(
        route_id=route_id,
        route_length_meters=max(1.0, (len(results) - 1) * 50.0),
        sampling_interval_meters=50.0,
        sample_results=results,
    )


def _route(route_id: str, route_index: int, duration: float = 600.0):
    return WalkingRouteOption(
        id=route_id,
        routeIndex=route_index,
        name=route_id,
        distanceMeters=800.0,
        durationSeconds=duration,
        geometry=GeoJsonLineString(
            coordinates=[(144.96, -37.81), (144.97, -37.80)]
        ),
    )


class FakeEvaluationService:
    def __init__(self, evaluations: dict[str, RouteCrowdEvaluation]) -> None:
        self.evaluations = evaluations
        self.calls: list[str] = []

    def evaluate_geometry(self, geometry, *, route_id=None):
        assert route_id is not None
        self.calls.append(route_id)
        return self.evaluations[route_id]


def _ranking_service(
    evaluations: dict[str, RouteCrowdEvaluation],
) -> RouteCrowdRankingService:
    return RouteCrowdRankingService(
        FakeEvaluationService(evaluations),
        minimum_coverage_pct=55.0,
        preference_thresholds={
            CrowdPreference.AVOID_BUSY: 50.0,
            CrowdPreference.PREFER_QUIETER: 75.0,
            CrowdPreference.FLEXIBLE: 90.0,
        },
    )


@pytest.mark.parametrize(
    ("numeric_count", "total_count", "expected_evaluable"),
    [
        (5_499, 10_000, False),
        (11, 20, True),
        (56, 100, True),
    ],
)
def test_minimum_coverage_boundaries(
    numeric_count: int,
    total_count: int,
    expected_evaluable: bool,
) -> None:
    entries = [("SUPPORTED", 40.0)] * numeric_count + [
        ("NO_DATA", None)
    ] * (total_count - numeric_count)
    summary = aggregate_route_crowd(
        _evaluation("coverage", entries),
        preference_threshold=50.0,
        minimum_coverage_pct=55.0,
    )

    assert summary.data_coverage_pct == pytest.approx(
        100.0 * numeric_count / total_count
    )
    assert summary.evaluable is expected_evaluable
    assert (summary.p75_crowd_exposure_score is not None) is expected_evaluable


def test_supported_and_limited_are_equal_weight_and_no_data_is_excluded() -> None:
    summary = aggregate_route_crowd(
        _evaluation(
            "mixed",
            [
                ("SUPPORTED", 10.0),
                ("LIMITED", 30.0),
                ("NO_DATA", None),
            ],
        ),
        preference_threshold=50.0,
        minimum_coverage_pct=55.0,
    )

    assert summary.numeric_sample_count == 2
    assert summary.data_coverage_pct == pytest.approx(200 / 3)
    assert summary.supported_pct == pytest.approx(100 / 3)
    assert summary.limited_coverage_pct == pytest.approx(100 / 3)
    assert summary.no_data_pct == pytest.approx(100 / 3)
    assert summary.p75_crowd_exposure_score == pytest.approx(25.0)


def test_no_data_score_is_never_used_even_if_upstream_payload_is_contradictory() -> None:
    summary = aggregate_route_crowd(
        _evaluation(
            "no-data-exclusion",
            [("SUPPORTED", 40.0), ("NO_DATA", 0.0)],
        ),
        preference_threshold=50.0,
        minimum_coverage_pct=50.0,
    )

    assert summary.numeric_sample_count == 1
    assert summary.p75_crowd_exposure_score == 40.0
    assert summary.route_crowd_level.value == "LOW"


def test_p75_uses_exact_continuous_linear_interpolation() -> None:
    assert continuous_percentile([0.0, 10.0, 20.0, 30.0], 0.75) == 22.5


def test_threshold_equality_is_within_and_strict_exceedance_is_counted() -> None:
    equal_summary = aggregate_route_crowd(
        _evaluation("equal", [("SUPPORTED", 50.0)]),
        preference_threshold=50.0,
        minimum_coverage_pct=55.0,
    )
    above_summary = aggregate_route_crowd(
        _evaluation(
            "above",
            [("SUPPORTED", 50.0), ("LIMITED", 50.01)],
        ),
        preference_threshold=50.0,
        minimum_coverage_pct=55.0,
    )

    assert equal_summary.preference_status is RoutePreferenceStatus.WITHIN_PREFERENCE
    assert equal_summary.pct_above_preference == 0.0
    assert above_summary.preference_status is RoutePreferenceStatus.ABOVE_PREFERENCE
    assert above_summary.pct_above_preference == 50.0


def test_lexicographic_order_prioritises_no_data_before_crowd() -> None:
    routes = [_route("quiet-partial", 0), _route("busy-complete", 1)]
    service = _ranking_service(
        {
            "quiet-partial": _evaluation(
                "quiet-partial",
                [("SUPPORTED", 0.0)] * 3 + [("NO_DATA", None)],
            ),
            "busy-complete": _evaluation(
                "busy-complete", [("SUPPORTED", 100.0)] * 4
            ),
        }
    )

    result = service.rank_routes(routes, CrowdPreference.AVOID_BUSY)

    assert [item.route.id for item in result.routes] == [
        "busy-complete",
        "quiet-partial",
    ]
    assert result.recommended_route_id == "busy-complete"


def test_lexicographic_order_uses_above_pct_then_p75_then_maximum() -> None:
    routes = [
        _route("above-more", 0),
        _route("above-less", 1),
        _route("p75-lower", 2),
        _route("max-lower", 3),
        _route("max-higher", 4),
    ]
    evaluations = {
        "above-more": _evaluation(
            "above-more",
            [("SUPPORTED", value) for value in [0, 100, 100, 100]],
        ),
        "above-less": _evaluation(
            "above-less",
            [("SUPPORTED", value) for value in [49, 49, 100, 100]],
        ),
        "p75-lower": _evaluation(
            "p75-lower", [("SUPPORTED", 60.0)] * 5
        ),
        "max-lower": _evaluation(
            "max-lower",
            [("SUPPORTED", value) for value in [60, 60, 60, 70, 90]],
        ),
        "max-higher": _evaluation(
            "max-higher",
            [("SUPPORTED", value) for value in [60, 60, 60, 70, 100]],
        ),
    }

    result = _ranking_service(evaluations).rank_routes(
        routes, CrowdPreference.AVOID_BUSY
    )
    ordered = [item.route.id for item in result.routes]

    assert ordered.index("above-less") < ordered.index("above-more")
    assert ordered.index("p75-lower") < ordered.index("max-lower")
    assert ordered.index("max-lower") < ordered.index("max-higher")


def test_duration_and_route_index_are_deterministic_final_tie_breaks() -> None:
    entries = [("SUPPORTED", 40.0)] * 4
    routes = [
        _route("index-two", 2, 600.0),
        _route("slower", 0, 700.0),
        _route("index-one", 1, 600.0),
    ]
    evaluations = {
        route.id: _evaluation(route.id, entries) for route in routes
    }

    result = _ranking_service(evaluations).rank_routes(
        routes, CrowdPreference.AVOID_BUSY
    )

    assert [item.route.id for item in result.routes] == [
        "index-one",
        "index-two",
        "slower",
    ]


def test_no_route_meets_preference_still_recommends_first_evaluable_route() -> None:
    routes = [_route("calmer", 1), _route("busier", 0)]
    service = _ranking_service(
        {
            "calmer": _evaluation("calmer", [("SUPPORTED", 60.0)] * 4),
            "busier": _evaluation("busier", [("SUPPORTED", 80.0)] * 4),
        }
    )

    result = service.rank_routes(routes, CrowdPreference.AVOID_BUSY)

    assert result.ranking_status is RouteRankingStatus.PROVISIONAL
    assert result.recommended_route_id == "calmer"
    assert all(
        item.summary.preference_status
        is RoutePreferenceStatus.ABOVE_PREFERENCE
        for item in result.routes
    )


def test_sufficient_route_precedes_insufficient_and_is_only_recommendation() -> None:
    routes = [_route("insufficient", 0), _route("sufficient", 1)]
    service = _ranking_service(
        {
            "insufficient": _evaluation(
                "insufficient",
                [("SUPPORTED", 10.0), ("NO_DATA", None)],
            ),
            "sufficient": _evaluation(
                "sufficient",
                [("SUPPORTED", 70.0), ("LIMITED", 70.0)],
            ),
        }
    )

    result = service.rank_routes(routes, CrowdPreference.PREFER_QUIETER)

    assert [item.route.id for item in result.routes] == [
        "sufficient",
        "insufficient",
    ]
    assert result.routes[0].rank == 1
    assert result.routes[0].is_recommended is True
    assert result.routes[1].rank is None
    assert result.routes[1].summary.p75_crowd_exposure_score is None


def test_all_no_data_preserves_mapbox_order_without_fake_recommendation() -> None:
    routes = [_route("route-two", 2), _route("route-zero", 0)]
    evaluations = {
        route.id: _evaluation(route.id, [("NO_DATA", None)] * 4)
        for route in routes
    }

    result = _ranking_service(evaluations).rank_routes(
        routes, CrowdPreference.FLEXIBLE
    )

    assert result.ranking_status is RouteRankingStatus.INSUFFICIENT_DATA
    assert result.recommended_route_id is None
    assert [item.route.id for item in result.routes] == [
        "route-zero",
        "route-two",
    ]
    assert all(
        item.summary.route_crowd_level is None
        and item.summary.p75_crowd_exposure_score is None
        and not item.is_recommended
        for item in result.routes
    )


def test_reversing_input_does_not_change_backend_ranking() -> None:
    routes = [_route("quiet", 0), _route("busy", 1)]
    evaluations = {
        "quiet": _evaluation("quiet", [("SUPPORTED", 30.0)] * 3),
        "busy": _evaluation("busy", [("SUPPORTED", 80.0)] * 3),
    }
    service = _ranking_service(evaluations)

    forward = service.rank_routes(routes, CrowdPreference.FLEXIBLE)
    reverse = service.rank_routes(list(reversed(routes)), CrowdPreference.FLEXIBLE)

    assert [item.route.id for item in forward.routes] == ["quiet", "busy"]
    assert [item.route.id for item in reverse.routes] == ["quiet", "busy"]


def test_multiple_current_materialisations_are_an_error_not_insufficient_data() -> None:
    routes = [_route("first", 0), _route("second", 1)]
    evaluations = {
        "first": _evaluation("first", [("SUPPORTED", 30.0)]),
        "second": _evaluation(
            "second",
            [("SUPPORTED", 30.0)],
            updated_at=datetime(2026, 8, 10, 8, 21, tzinfo=timezone.utc),
        ),
    }

    with pytest.raises(RouteCrowdDataConsistencyError):
        _ranking_service(evaluations).rank_routes(
            routes, CrowdPreference.AVOID_BUSY
        )
