import json
import math
from pathlib import Path

import pytest

from backend.app.config import SETTINGS
from backend.app.schemas.routes import GeoJsonLineString
from backend.app.services.routing.route_sampling_service import (
    EARTH_MEAN_RADIUS_METERS,
    DegenerateRouteGeometryError,
    InvalidRouteGeometryError,
    RouteSamplingConfigurationError,
    RouteSamplingService,
    haversine_distance_meters,
)


FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "flinders_to_melbourne_central_geometry.json"
)


def _eastward_coordinate(distance_meters: float) -> list[float]:
    return [math.degrees(distance_meters / EARTH_MEAN_RADIUS_METERS), 0.0]


def _straight_geometry(distance_meters: float) -> dict[str, object]:
    return {
        "type": "LineString",
        "coordinates": [[0.0, 0.0], _eastward_coordinate(distance_meters)],
    }


def _load_melbourne_fixture() -> dict[str, object]:
    with FIXTURE_PATH.open(encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


def test_straight_line_route_is_sampled_at_cumulative_targets() -> None:
    result = RouteSamplingService(interval_meters=50).sample_geometry(
        _straight_geometry(120)
    )

    assert result.route_length_meters == pytest.approx(120, abs=1e-9)
    assert [sample.distance_along_route_meters for sample in result.samples] == (
        pytest.approx([0, 50, 100, 120], abs=1e-9)
    )
    assert [sample.longitude for sample in result.samples] == pytest.approx(
        [
            0,
            _eastward_coordinate(50)[0],
            _eastward_coordinate(100)[0],
            _eastward_coordinate(120)[0],
        ],
        abs=1e-12,
    )


def test_multi_segment_route_interpolates_on_the_containing_segment() -> None:
    first_end = _eastward_coordinate(60)
    second_end = [first_end[0], math.degrees(60 / EARTH_MEAN_RADIUS_METERS)]
    result = RouteSamplingService(interval_meters=50).sample_geometry(
        {
            "type": "LineString",
            "coordinates": [[0.0, 0.0], first_end, second_end],
        }
    )

    assert result.route_length_meters == pytest.approx(120, abs=1e-6)
    assert result.samples[1].latitude == pytest.approx(0.0, abs=1e-12)
    assert result.samples[2].longitude == pytest.approx(first_end[0], abs=1e-12)
    assert result.samples[2].latitude > 0


def test_first_sample_is_the_exact_start_coordinate() -> None:
    geometry = {
        "type": "LineString",
        "coordinates": [[144.967123, -37.818345], [144.966, -37.817]],
    }
    first = RouteSamplingService().sample_geometry(geometry).samples[0]

    assert (first.longitude, first.latitude) == (144.967123, -37.818345)
    assert first.distance_along_route_meters == 0.0


def test_last_sample_is_the_exact_end_coordinate() -> None:
    geometry = {
        "type": "LineString",
        "coordinates": [[144.9671, -37.8183], [144.963123, -37.810234]],
    }
    result = RouteSamplingService().sample_geometry(geometry)
    last = result.samples[-1]

    assert (last.longitude, last.latitude) == (144.963123, -37.810234)
    assert last.distance_along_route_meters == result.route_length_meters


def test_interior_spacing_is_the_configured_interval() -> None:
    result = RouteSamplingService(interval_meters=50).sample_geometry(
        _straight_geometry(223)
    )
    distance_deltas = [
        current.distance_along_route_meters
        - previous.distance_along_route_meters
        for previous, current in zip(result.samples, result.samples[1:])
    ]

    assert distance_deltas[:-1] == pytest.approx([50, 50, 50, 50])
    assert distance_deltas[-1] == pytest.approx(23)
    for previous, current in zip(result.samples[:-2], result.samples[1:-1]):
        coordinate_distance = haversine_distance_meters(
            (previous.longitude, previous.latitude),
            (current.longitude, current.latitude),
        )
        assert coordinate_distance == pytest.approx(50, abs=1e-6)


def test_route_shorter_than_interval_returns_only_start_and_end() -> None:
    result = RouteSamplingService(interval_meters=50).sample_geometry(
        _straight_geometry(30)
    )

    assert len(result.samples) == 2
    assert [sample.distance_along_route_meters for sample in result.samples] == (
        pytest.approx([0, 30], abs=1e-9)
    )


def test_exact_interval_multiple_uses_scheduled_endpoint_once() -> None:
    result = RouteSamplingService(interval_meters=50).sample_geometry(
        _straight_geometry(100)
    )

    assert [sample.distance_along_route_meters for sample in result.samples] == (
        pytest.approx([0, 50, 100], abs=1e-8)
    )
    assert result.samples[-1].longitude == _eastward_coordinate(100)[0]


def test_endpoint_is_not_duplicated() -> None:
    endpoint = tuple(_eastward_coordinate(100))
    result = RouteSamplingService(interval_meters=50).sample_geometry(
        _straight_geometry(100)
    )

    endpoint_occurrences = sum(
        (sample.longitude, sample.latitude) == endpoint
        for sample in result.samples
    )
    assert endpoint_occurrences == 1
    assert len(result.samples) == 3


def test_consecutive_duplicate_coordinates_are_skipped_safely() -> None:
    endpoint = _eastward_coordinate(120)
    duplicated = {
        "type": "LineString",
        "coordinates": [[0.0, 0.0], [0.0, 0.0], endpoint, endpoint],
    }
    service = RouteSamplingService(interval_meters=50)

    result = service.sample_geometry(duplicated)
    clean_result = service.sample_geometry(_straight_geometry(120))

    assert result == clean_result


@pytest.mark.parametrize("longitude", [-180.1, 180.1, float("nan"), float("inf")])
def test_invalid_longitude_is_rejected(longitude: float) -> None:
    with pytest.raises(InvalidRouteGeometryError, match="longitude"):
        RouteSamplingService().sample_geometry(
            {
                "type": "LineString",
                "coordinates": [[144.96, -37.81], [longitude, -37.8]],
            }
        )


@pytest.mark.parametrize("latitude", [-90.1, 90.1, float("nan"), float("inf")])
def test_invalid_latitude_is_rejected(latitude: float) -> None:
    with pytest.raises(InvalidRouteGeometryError, match="latitude"):
        RouteSamplingService().sample_geometry(
            {
                "type": "LineString",
                "coordinates": [[144.96, -37.81], [144.97, latitude]],
            }
        )


@pytest.mark.parametrize(
    "geometry",
    [
        None,
        {},
        {"type": "Point", "coordinates": [[0, 0], [1, 1]]},
        {"type": "LineString", "coordinates": []},
        {"type": "LineString", "coordinates": [[0, 0]]},
        {"type": "LineString", "coordinates": [[0, 0, 1], [1, 1]]},
        {"type": "LineString", "coordinates": [[0, 0], ["1", 1]]},
        {"type": "LineString", "coordinates": [[0, 0], [True, 1]]},
    ],
)
def test_malformed_linestring_is_rejected(geometry: object) -> None:
    with pytest.raises(InvalidRouteGeometryError):
        RouteSamplingService().sample_geometry(geometry)


def test_all_zero_length_segments_raise_controlled_degenerate_error() -> None:
    with pytest.raises(DegenerateRouteGeometryError, match="degenerate"):
        RouteSamplingService().sample_geometry(
            {
                "type": "LineString",
                "coordinates": [
                    [144.9631, -37.8102],
                    [144.9631, -37.8102],
                    [144.9631, -37.8102],
                ],
            }
        )


def test_sample_order_and_indexes_are_deterministic() -> None:
    geometry = _load_melbourne_fixture()
    service = RouteSamplingService()

    first_result = service.sample_geometry(geometry)
    second_result = service.sample_geometry(geometry)

    assert first_result == second_result
    assert [sample.index for sample in first_result.samples] == list(
        range(len(first_result.samples))
    )
    assert [
        sample.distance_along_route_meters for sample in first_result.samples
    ] == sorted(
        sample.distance_along_route_meters for sample in first_result.samples
    )


def test_reverse_direction_preserves_origin_to_destination_order() -> None:
    geometry = _load_melbourne_fixture()
    coordinates = geometry["coordinates"]
    assert isinstance(coordinates, list)
    reversed_geometry = {
        "type": "LineString",
        "coordinates": list(reversed(coordinates)),
    }
    service = RouteSamplingService()

    forward = service.sample_geometry(geometry)
    reverse = service.sample_geometry(reversed_geometry)

    assert reverse.route_length_meters == pytest.approx(
        forward.route_length_meters
    )
    assert (reverse.samples[0].longitude, reverse.samples[0].latitude) == tuple(
        coordinates[-1]
    )
    assert (
        reverse.samples[-1].longitude,
        reverse.samples[-1].latitude,
    ) == tuple(coordinates[0])
    assert [sample.index for sample in reverse.samples] == list(
        range(len(reverse.samples))
    )


def test_melbourne_scale_fixture_has_reasonable_length_count_and_spacing() -> None:
    geometry = _load_melbourne_fixture()
    result = RouteSamplingService().sample_geometry(geometry)
    coordinates = geometry["coordinates"]
    assert isinstance(coordinates, list)

    assert 1_100 < result.route_length_meters < 1_200
    assert 23 <= len(result.samples) <= 26
    assert (result.samples[0].longitude, result.samples[0].latitude) == tuple(
        coordinates[0]
    )
    assert (
        result.samples[-1].longitude,
        result.samples[-1].latitude,
    ) == tuple(coordinates[-1])
    interior_deltas = [
        current.distance_along_route_meters
        - previous.distance_along_route_meters
        for previous, current in zip(result.samples, result.samples[1:-1])
    ]
    assert interior_deltas == pytest.approx(
        [SETTINGS.route.sample_interval_m] * len(interior_deltas)
    )


def test_default_interval_comes_from_authoritative_settings() -> None:
    service = RouteSamplingService()

    assert service.interval_meters == SETTINGS.route.sample_interval_m == 50


def test_normalized_geometry_model_is_accepted_without_api_changes() -> None:
    geometry = GeoJsonLineString(
        coordinates=[(0.0, 0.0), tuple(_eastward_coordinate(60))]
    )
    result = RouteSamplingService().sample_geometry(geometry)

    assert len(result.samples) == 3


@pytest.mark.parametrize("interval", [0, -1, float("nan"), float("inf"), True])
def test_invalid_sampling_interval_is_rejected(interval: object) -> None:
    with pytest.raises(RouteSamplingConfigurationError):
        RouteSamplingService(interval_meters=interval)  # type: ignore[arg-type]
