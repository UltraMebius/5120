import pytest

from backend.app.services.routing.route_distinctness_service import (
    RouteDistinctnessService,
)


DIRECT = {
    "type": "LineString",
    "coordinates": [[144.96, -37.82], [144.96, -37.81]],
}
SMALL_VARIATION = {
    "type": "LineString",
    "coordinates": [[144.9601, -37.82], [144.9601, -37.81]],
}
PARALLEL_CORRIDOR = {
    "type": "LineString",
    "coordinates": [
        [144.96, -37.82],
        [144.9612, -37.818],
        [144.9612, -37.812],
        [144.96, -37.81],
    ],
}
DIFFERENT_MIDDLE = {
    "type": "LineString",
    "coordinates": [
        [144.96, -37.82],
        [144.96, -37.818],
        [144.9620, -37.817],
        [144.9620, -37.813],
        [144.96, -37.812],
        [144.96, -37.81],
    ],
}


def test_identical_routes_are_similar_in_both_directions() -> None:
    result = RouteDistinctnessService().compare(DIRECT, DIRECT)

    assert result.coverage_a_to_b == 1.0
    assert result.coverage_b_to_a == 1.0
    assert result.too_similar is True


def test_same_corridor_with_small_coordinate_variation_is_similar() -> None:
    result = RouteDistinctnessService().compare(DIRECT, SMALL_VARIATION)

    assert result.coverage_a_to_b >= 0.85
    assert result.coverage_b_to_a >= 0.85
    assert result.too_similar is True


@pytest.mark.parametrize("alternative", [PARALLEL_CORRIDOR, DIFFERENT_MIDDLE])
def test_substantial_parallel_or_middle_divergence_is_distinct(alternative) -> None:
    result = RouteDistinctnessService().compare(DIRECT, alternative)

    assert not (
        result.coverage_a_to_b >= 0.85
        and result.coverage_b_to_a >= 0.85
    )
    assert result.too_similar is False


def test_similarity_requires_both_directional_coverages() -> None:
    service = RouteDistinctnessService()

    assert service.coverages_are_too_similar(0.85, 0.85) is True
    assert service.coverages_are_too_similar(0.849999, 1.0) is False
    assert service.coverages_are_too_similar(1.0, 0.849999) is False
