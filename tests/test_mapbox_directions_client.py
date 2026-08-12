import httpx
import pytest

from backend.app.services.routing.mapbox_directions_client import (
    MapboxDirectionsClient,
    MapboxDirectionsConfigurationError,
    MapboxDirectionsConnectionError,
    MapboxDirectionsResponseError,
)


def _ok_payload() -> dict[str, object]:
    return {"code": "Ok", "routes": []}


def test_client_constructs_walking_url_coordinates_and_required_parameters() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=_ok_payload())

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = MapboxDirectionsClient(
        access_token="test-token",
        base_url="https://directions.test/directions/v5",
        profile="mapbox/walking",
        client=http_client,
    )
    try:
        client.fetch_directions(
            origin_longitude=144.9671,
            origin_latitude=-37.8183,
            destination_longitude=144.9631,
            destination_latitude=-37.8102,
        )
    finally:
        http_client.close()

    assert len(requests) == 1
    request = requests[0]
    assert request.method == "GET"
    assert request.url.path == (
        "/directions/v5/mapbox/walking/"
        "144.9671,-37.8183;144.9631,-37.8102"
    )
    assert request.url.params["alternatives"] == "true"
    assert request.url.params["geometries"] == "geojson"
    assert request.url.params["overview"] == "full"
    assert request.url.params["steps"] == "true"
    assert request.url.params["language"] == "en"
    assert request.url.params["access_token"] == "test-token"


def test_coordinate_sequence_supports_one_waypoint_and_bounded_alternatives() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=_ok_payload())

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = MapboxDirectionsClient(
        access_token="test-token",
        base_url="https://directions.test/directions/v5",
        client=http_client,
    )
    try:
        client.fetch_directions_for_coordinates(
            (
                (144.9671, -37.8183),
                (144.9650, -37.8140),
                (144.9631, -37.8102),
            ),
            alternatives=False,
        )
    finally:
        http_client.close()

    assert len(requests) == 1
    request = requests[0]
    assert request.url.path.endswith(
        "/144.9671,-37.8183;144.965,-37.814;144.9631,-37.8102"
    )
    assert request.url.params["alternatives"] == "false"


@pytest.mark.parametrize(
    "coordinates",
    [
        [(144.96, -37.81)],
        [(144.96, -37.81), (181.0, -37.82)],
        [(144.96, -37.81), (144.97, float("nan"))],
    ],
)
def test_coordinate_sequence_rejects_invalid_input(coordinates) -> None:
    client = MapboxDirectionsClient(access_token="test-token")
    try:
        with pytest.raises(ValueError, match="Mapbox"):
            client.directions_url_for_coordinates(coordinates)
    finally:
        client.close()


def test_missing_token_is_a_controlled_configuration_error() -> None:
    client = MapboxDirectionsClient(access_token="")
    try:
        with pytest.raises(MapboxDirectionsConfigurationError) as exc_info:
            client.fetch_directions(
                origin_longitude=144.96,
                origin_latitude=-37.81,
                destination_longitude=144.97,
                destination_latitude=-37.82,
            )
    finally:
        client.close()

    assert "token" in str(exc_info.value).lower()


def test_non_success_http_does_not_expose_token_or_upstream_body() -> None:
    secret = "test-secret-token"
    transport = httpx.MockTransport(
        lambda request: httpx.Response(503, text="private upstream details")
    )
    http_client = httpx.Client(transport=transport)
    client = MapboxDirectionsClient(access_token=secret, client=http_client)
    try:
        with pytest.raises(MapboxDirectionsResponseError) as exc_info:
            client.fetch_directions(
                origin_longitude=144.96,
                origin_latitude=-37.81,
                destination_longitude=144.97,
                destination_latitude=-37.82,
            )
    finally:
        http_client.close()

    message = str(exc_info.value)
    assert "HTTP 503" in message
    assert secret not in message
    assert "private upstream details" not in message


def test_non_ok_mapbox_code_is_sanitized() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"code": "NoRoute", "message": "sensitive upstream detail"},
        )
    )
    http_client = httpx.Client(transport=transport)
    client = MapboxDirectionsClient(
        access_token="test-token", client=http_client
    )
    try:
        with pytest.raises(MapboxDirectionsResponseError) as exc_info:
            client.fetch_directions(
                origin_longitude=144.96,
                origin_latitude=-37.81,
                destination_longitude=144.97,
                destination_latitude=-37.82,
            )
    finally:
        http_client.close()

    assert "sensitive upstream detail" not in str(exc_info.value)


def test_malformed_json_is_controlled() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            content=b"{not-json",
            headers={"content-type": "application/json"},
        )
    )
    http_client = httpx.Client(transport=transport)
    client = MapboxDirectionsClient(
        access_token="test-token", client=http_client
    )
    try:
        with pytest.raises(MapboxDirectionsResponseError, match="malformed JSON"):
            client.fetch_directions(
                origin_longitude=144.96,
                origin_latitude=-37.81,
                destination_longitude=144.97,
                destination_latitude=-37.82,
            )
    finally:
        http_client.close()


def test_timeout_is_reported_without_raw_exception_details() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("private timeout detail", request=request)

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = MapboxDirectionsClient(
        access_token="test-token", client=http_client
    )
    try:
        with pytest.raises(MapboxDirectionsConnectionError) as exc_info:
            client.fetch_directions(
                origin_longitude=144.96,
                origin_latitude=-37.81,
                destination_longitude=144.97,
                destination_latitude=-37.82,
            )
    finally:
        http_client.close()

    assert "private timeout detail" not in str(exc_info.value)
    assert "timed out" in str(exc_info.value)
