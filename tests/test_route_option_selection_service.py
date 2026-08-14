from dataclasses import replace

import pytest

from backend.app.models.pedestrian_flow import RoutePedestrianFlowSummary
from backend.app.schemas.routes import GeoJsonLineString
from backend.app.services.routing.route_candidate_models import (
    CandidateGenerationReason,
    CandidateGenerationTimings,
    MultiRouteCandidateResult,
    RouteCandidate,
    RouteCandidateSource,
)
from backend.app.services.routing.route_option_selection_service import (
    PedestrianFlowComparisonBasis,
    RelativePedestrianActivity,
    RouteOptionRole,
    RouteOptionSelectionService,
)


TIMINGS = CandidateGenerationTimings(
    mapbox_initial_ms=1,
    candidate_distinctness_ms=2,
    waypoint_selection_ms=0,
    waypoint_mapbox_ms=0,
    sampling_ms=3,
    flow_batch_db_ms=4,
    flow_aggregation_ms=5,
    total_ms=15,
    mapbox_request_count=1,
    candidate_count_before_filter=3,
    candidate_count_after_filter=3,
    flow_sql_execution_count=1,
)


def _candidate(
    route_id: str,
    index: int,
    *,
    duration: float,
    distance: float = 1_000,
    live_coverage: float = 100,
    live_median: float | None = 20,
    live_p75: float | None = 30,
    live_maximum: float | None = 40,
    historical_coverage: float = 100,
    historical_median: float | None = 15,
    historical_p75: float | None = 25,
    historical_maximum: float | None = 35,
) -> RouteCandidate:
    summary = RoutePedestrianFlowSummary(
        route_index=index,
        total_sample_count=10,
        live_numeric_sample_count=round(live_coverage / 10),
        historical_numeric_sample_count=round(historical_coverage / 10),
        live_coverage_pct=live_coverage,
        historical_coverage_pct=historical_coverage,
        live_median_pedestrian_movements_per_minute=live_median,
        live_p75_pedestrian_movements_per_minute=live_p75,
        live_maximum_pedestrian_movements_per_minute=live_maximum,
        historical_median_pedestrian_movements_per_minute=historical_median,
        historical_p75_pedestrian_movements_per_minute=historical_p75,
        historical_maximum_pedestrian_movements_per_minute=(
            historical_maximum
        ),
    )
    return RouteCandidate(
        route_id=route_id,
        source_index=index,
        candidate_source=(
            RouteCandidateSource.DIRECT
            if index == 0
            else RouteCandidateSource.MAPBOX_ALTERNATIVE
        ),
        geometry=GeoJsonLineString(
            coordinates=[
                (144.96 + index / 10_000, -37.82),
                (144.96 + index / 10_000, -37.81),
            ]
        ),
        distance_meters=distance,
        duration_seconds=duration,
        steps=(),
        pedestrian_flow_summary=summary,
    )


def _select(*candidates: RouteCandidate):
    result = MultiRouteCandidateResult(
        candidates=tuple(candidates),
        reason=CandidateGenerationReason.MULTIPLE_MAPBOX_ROUTES,
        timings=TIMINGS,
    )
    return RouteOptionSelectionService().select_options(result)


def _by_id(result):
    return {route.candidate.route_id: route for route in result.routes}


def test_all_live_qualified_routes_use_live_comparison_values() -> None:
    result = _select(
        _candidate("a", 0, duration=600, live_median=11, live_p75=21),
        _candidate("b", 1, duration=700, live_median=12, live_p75=22),
    )

    assert result.comparison_basis is PedestrianFlowComparisonBasis.LIVE
    selected = _by_id(result)["a"].comparison_pedestrian_flow
    assert selected.basis is PedestrianFlowComparisonBasis.LIVE
    assert selected.typical_movements_per_minute == 11
    assert selected.p75_movements_per_minute == 21


def test_historical_is_common_fallback_without_mixing_live_values() -> None:
    result = _select(
        _candidate(
            "a",
            0,
            duration=600,
            live_coverage=80,
            live_p75=5,
            historical_p75=40,
        ),
        _candidate(
            "b",
            1,
            duration=700,
            live_coverage=20,
            live_p75=3,
            historical_p75=10,
        ),
    )

    assert result.comparison_basis is (
        PedestrianFlowComparisonBasis.HISTORICAL_ESTIMATE
    )
    assert RouteOptionRole.CALMEST in _by_id(result)["b"].role_badges
    assert _by_id(result)["a"].comparison_pedestrian_flow.p75_movements_per_minute == 40


def test_no_common_basis_assigns_only_fastest_and_null_comparison_values() -> None:
    result = _select(
        _candidate(
            "a",
            0,
            duration=600,
            live_coverage=80,
            historical_coverage=20,
        ),
        _candidate(
            "b",
            1,
            duration=700,
            live_coverage=20,
            historical_coverage=90,
        ),
    )

    assert result.comparison_basis is PedestrianFlowComparisonBasis.UNKNOWN
    assert _by_id(result)["a"].role_badges == (RouteOptionRole.FASTEST,)
    assert _by_id(result)["b"].role_badges == ()
    for route in result.routes:
        assert route.relative_pedestrian_activity is (
            RelativePedestrianActivity.UNKNOWN
        )
        assert route.comparison_pedestrian_flow.p75_movements_per_minute is None
        assert route.comparison_pedestrian_flow.coverage_pct is None


@pytest.mark.parametrize(
    ("coverage", "expected"),
    [
        (55.0, PedestrianFlowComparisonBasis.LIVE),
        (54.99, PedestrianFlowComparisonBasis.HISTORICAL_ESTIMATE),
    ],
)
def test_live_coverage_qualification_boundary(coverage, expected) -> None:
    result = _select(
        _candidate("a", 0, duration=600, live_coverage=coverage),
        _candidate("b", 1, duration=700, live_coverage=100),
    )

    assert result.comparison_basis is expected


def test_numeric_typical_flow_is_required_when_live_coverage_is_sufficient() -> None:
    first = _candidate("a", 0, duration=600, live_coverage=100)
    first = replace(
        first,
        pedestrian_flow_summary=replace(
            first.pedestrian_flow_summary,
            live_median_pedestrian_movements_per_minute=None,
        ),
    )

    result = _select(first, _candidate("b", 1, duration=700))

    assert result.comparison_basis is (
        PedestrianFlowComparisonBasis.HISTORICAL_ESTIMATE
    )


def test_fastest_uses_duration_distance_source_index_and_route_id_ties() -> None:
    result = _select(
        _candidate("z", 4, duration=600, distance=900, live_median=5),
        _candidate("b", 2, duration=600, distance=800, live_median=20),
        _candidate("a", 1, duration=600, distance=800, live_median=30),
    )

    assert RouteOptionRole.FASTEST in _by_id(result)["a"].role_badges


def test_fastest_uses_stable_route_id_after_all_numeric_ties() -> None:
    result = _select(
        _candidate(
            "z",
            0,
            duration=600,
            distance=900,
            live_coverage=80,
            historical_coverage=20,
        ),
        _candidate(
            "a",
            0,
            duration=600,
            distance=900,
            live_coverage=20,
            historical_coverage=80,
        ),
    )

    assert RouteOptionRole.FASTEST in _by_id(result)["a"].role_badges


def test_one_route_has_fastest_but_no_calmest_or_balanced() -> None:
    result = _select(_candidate("only", 0, duration=600))

    assert result.routes[0].role_badges == (RouteOptionRole.FASTEST,)
    assert result.routes[0].balanced_score is None


def test_calmest_uses_displayed_median_then_p75_maximum_and_route_ties() -> None:
    result = _select(
        _candidate(
            "a",
            0,
            duration=700,
            distance=1_000,
            live_p75=20,
            live_median=12,
            live_maximum=30,
        ),
        _candidate(
            "b",
            1,
            duration=600,
            distance=900,
            live_p75=20,
            live_median=10,
            live_maximum=40,
        ),
        _candidate(
            "c",
            2,
            duration=650,
            distance=950,
            live_p75=20,
            live_median=10,
            live_maximum=25,
        ),
    )

    assert RouteOptionRole.CALMEST in _by_id(result)["c"].role_badges


def test_observed_live_values_assign_calmest_to_lowest_displayed_median() -> None:
    result = _select(
        _candidate(
            "a",
            0,
            duration=700,
            live_median=10.713856377122092,
            live_p75=15.108364075652696,
        ),
        _candidate(
            "b",
            1,
            duration=600,
            live_median=15.368663,
            live_p75=17.880795,
        ),
        _candidate(
            "c",
            2,
            duration=800,
            live_median=8.377001002372698,
            live_p75=15.135734107147666,
        ),
    )
    routes = _by_id(result)

    assert result.comparison_basis is PedestrianFlowComparisonBasis.LIVE
    assert routes["c"].role_badges == (RouteOptionRole.CALMEST,)
    assert routes["b"].role_badges == (RouteOptionRole.FASTEST,)
    assert routes["a"].role_badges == (RouteOptionRole.BALANCED,)
    assert routes["c"].relative_pedestrian_activity is (
        RelativePedestrianActivity.LOWEST
    )


def test_lower_displayed_median_is_authoritative_over_lower_p75() -> None:
    result = _select(
        _candidate(
            "a",
            0,
            duration=600,
            live_p75=12.0,
            live_median=11.0,
        ),
        _candidate(
            "b",
            1,
            duration=700,
            live_p75=14.0,
            live_median=8.0,
        ),
    )

    assert RouteOptionRole.CALMEST in _by_id(result)["b"].role_badges


def test_exact_displayed_median_tie_uses_p75() -> None:
    result = _select(
        _candidate(
            "a",
            0,
            duration=600,
            live_p75=15.1,
            live_median=8.0,
        ),
        _candidate(
            "b",
            1,
            duration=700,
            live_p75=14.1,
            live_median=8.0,
        ),
    )

    assert RouteOptionRole.CALMEST in _by_id(result)["b"].role_badges


def test_historical_comparison_uses_historical_displayed_median() -> None:
    result = _select(
        _candidate(
            "a",
            0,
            duration=600,
            live_coverage=20,
            historical_p75=15.10,
            historical_median=10.0,
        ),
        _candidate(
            "b",
            1,
            duration=700,
            live_coverage=20,
            historical_p75=15.13,
            historical_median=8.0,
        ),
    )

    assert result.comparison_basis is (
        PedestrianFlowComparisonBasis.HISTORICAL_ESTIMATE
    )
    assert RouteOptionRole.CALMEST in _by_id(result)["b"].role_badges


def test_calmest_uses_source_index_then_route_id_for_final_ties() -> None:
    result = _select(
        _candidate("z", 1, duration=600, distance=900),
        _candidate("b", 0, duration=600, distance=900),
        _candidate("a", 0, duration=600, distance=900),
    )

    assert RouteOptionRole.CALMEST in _by_id(result)["a"].role_badges


def test_two_routes_receive_distinct_calmest_and_fastest_roles() -> None:
    result = _select(
        _candidate("a", 0, duration=600, live_median=10, live_p75=15),
        _candidate("b", 1, duration=780, live_median=20, live_p75=30),
    )

    assert [route.candidate.route_id for route in result.routes] == ["a", "b"]
    assert result.routes[0].role_badges == (RouteOptionRole.CALMEST,)
    assert result.routes[1].role_badges == (RouteOptionRole.FASTEST,)


def test_three_route_balanced_normalization_and_response_order() -> None:
    result = _select(
        _candidate("a", 0, duration=600, live_median=50, live_p75=60),
        _candidate("b", 1, duration=780, live_median=30, live_p75=35),
        _candidate("c", 2, duration=1_020, live_median=10, live_p75=15),
    )
    routes = _by_id(result)

    assert routes["a"].balanced_score == pytest.approx(0.5)
    assert routes["b"].balanced_score == pytest.approx(
        0.5 * (180 / 420) + 0.5 * (20 / 40)
    )
    assert routes["c"].balanced_score == pytest.approx(0.5)
    assert routes["b"].role_badges == (RouteOptionRole.BALANCED,)
    assert [route.candidate.route_id for route in result.routes] == [
        "c",
        "a",
        "b",
    ]
    assert [route.relative_pedestrian_activity for route in result.routes] == [
        RelativePedestrianActivity.LOWEST,
        RelativePedestrianActivity.HIGHEST,
        RelativePedestrianActivity.MIDDLE,
    ]


def test_balanced_is_absent_for_two_routes_or_unknown_basis() -> None:
    two = _select(
        _candidate("a", 0, duration=600),
        _candidate("b", 1, duration=700),
    )
    unknown = _select(
        _candidate(
            "a",
            0,
            duration=600,
            live_coverage=80,
            historical_coverage=20,
        ),
        _candidate(
            "b",
            1,
            duration=700,
            live_coverage=20,
            historical_coverage=80,
        ),
        _candidate(
            "c",
            2,
            duration=800,
            live_coverage=20,
            historical_coverage=80,
        ),
    )

    assert all(RouteOptionRole.BALANCED not in row.role_badges for row in two.routes)
    assert all(row.balanced_score is None for row in two.routes)
    assert all(
        RouteOptionRole.BALANCED not in row.role_badges for row in unknown.routes
    )


def test_equal_duration_and_crowd_ranges_do_not_divide_by_zero() -> None:
    result = _select(
        _candidate("a", 0, duration=600, distance=900, live_p75=20),
        _candidate("b", 1, duration=600, distance=1_000, live_p75=20),
        _candidate("c", 2, duration=600, distance=1_100, live_p75=20),
    )

    assert [route.balanced_score for route in result.routes] == [0.0, 0.0, 0.0]


def test_calmest_fastest_conflict_assigns_three_distinct_routes() -> None:
    result = _select(
        _candidate("a", 0, duration=600, live_median=10, live_p75=10),
        _candidate("b", 1, duration=700, live_median=20, live_p75=20),
        _candidate("c", 2, duration=800, live_median=30, live_p75=30),
    )
    routes = _by_id(result)

    assert routes["a"].role_badges == (RouteOptionRole.CALMEST,)
    assert routes["b"].role_badges == (RouteOptionRole.FASTEST,)
    assert routes["c"].role_badges == (RouteOptionRole.BALANCED,)
    assert routes["b"].candidate.duration_seconds == min(
        route.candidate.duration_seconds
        for route in routes.values()
        if route.candidate.route_id != "a"
    )
    assert len({route.candidate.route_id for route in result.routes}) == 3


def test_two_comparable_routes_receive_lowest_and_highest_metadata() -> None:
    result = _select(
        _candidate("high", 0, duration=600, live_median=40, live_p75=40),
        _candidate("low", 1, duration=700, live_median=10, live_p75=10),
    )

    assert _by_id(result)["low"].relative_pedestrian_activity is (
        RelativePedestrianActivity.LOWEST
    )
    assert _by_id(result)["high"].relative_pedestrian_activity is (
        RelativePedestrianActivity.HIGHEST
    )


def test_role_selection_preserves_phase_two_diagnostics_and_adds_timing() -> None:
    result = _select(_candidate("only", 0, duration=600))

    assert result.candidate_timings is TIMINGS
    assert result.route_role_selection_ms >= 0.0


def test_role_selector_has_no_io_or_sampling_dependency() -> None:
    service = RouteOptionSelectionService()

    assert not hasattr(service, "repository")
    assert not hasattr(service, "routing_service")
    assert not hasattr(service, "sampling_service")
