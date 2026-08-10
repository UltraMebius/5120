import json
from pathlib import Path

import httpx
import pytest

from backend.app.services.ingestion.city_sensor_client import (
    CityDataResponseError,
    CitySensorLocationClient,
)


FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "city_sensor_locations_sample.json"
)


def _fixture_payload() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_client_paginates_and_records_observed_live_fields() -> None:
    payload = _fixture_payload()
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        offset = int(request.url.params["offset"])
        limit = int(request.url.params["limit"])
        results = payload["results"]
        assert isinstance(results, list)
        return httpx.Response(
            200,
            json={
                "total_count": payload["total_count"],
                "results": results[offset : offset + limit],
            },
        )

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = CitySensorLocationClient(client=http_client, page_size=2)
    try:
        snapshot = client.fetch_all()
    finally:
        http_client.close()

    assert snapshot.total_count == 3
    assert len(snapshot.records) == 3
    assert len(requests) == 2
    assert requests[0].url.params["order_by"] == "location_id"
    assert requests[0].url.params["offset"] == "0"
    assert requests[1].url.params["offset"] == "2"
    assert "location_id" in snapshot.observed_fields
    assert "location" in snapshot.observed_fields


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"total_count": "3", "results": []},
        {"total_count": 1, "results": ["not-an-object"]},
    ],
)
def test_client_rejects_missing_or_malformed_result_structure(
    payload: object,
) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=payload)
    )
    http_client = httpx.Client(transport=transport)
    client = CitySensorLocationClient(client=http_client)
    try:
        with pytest.raises(CityDataResponseError):
            client.fetch_all()
    finally:
        http_client.close()


def test_client_reports_non_success_http_without_dumping_response() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(503, text="private upstream details")
    )
    http_client = httpx.Client(transport=transport)
    client = CitySensorLocationClient(client=http_client)
    try:
        with pytest.raises(CityDataResponseError) as exc_info:
            client.fetch_all()
    finally:
        http_client.close()

    assert "HTTP 503" in str(exc_info.value)
    assert "private upstream details" not in str(exc_info.value)


def test_client_reports_malformed_json() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            content=b"{not-json",
            headers={"content-type": "application/json"},
        )
    )
    http_client = httpx.Client(transport=transport)
    client = CitySensorLocationClient(client=http_client)
    try:
        with pytest.raises(CityDataResponseError, match="malformed JSON"):
            client.fetch_all()
    finally:
        http_client.close()
