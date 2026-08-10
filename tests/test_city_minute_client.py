from datetime import datetime

import httpx
import pytest

from backend.app.services.ingestion.city_minute_client import CityMinuteCountClient
from backend.app.services.ingestion.city_sensor_client import (
    CityDataConnectionError,
    CityDataResponseError,
)


START = datetime.fromisoformat("2026-08-10T10:00:00+10:00")
END = datetime.fromisoformat("2026-08-10T10:30:00+10:00")


def _row(location_id: int, minute: int) -> dict[str, object]:
    return {
        "location_id": location_id,
        "sensing_datetime": f"2026-08-10T10:{minute:02d}:00+10:00",
        "sensing_date": "2026-08-10",
        "sensing_time": f"10:{minute:02d}:00",
        "direction_1": 1,
        "direction_2": 2,
        "total_of_directions": 3,
    }


def test_bounded_records_endpoint_is_paginated_and_metadata_is_preserved() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if "select" in request.url.params:
            return httpx.Response(
                200,
                json={
                    "total_count": 1,
                    "results": [
                        {
                            "minimum_datetime": "2026-08-07T23:55:00+10:00",
                            "maximum_datetime": "2026-08-10T10:16:00+10:00",
                            "record_count": 149000,
                        }
                    ],
                },
            )
        offset = int(request.url.params["offset"])
        return httpx.Response(
            200,
            json={"total_count": 2, "results": [_row(11 + offset, 15 + offset)]},
        )

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        snapshot = CityMinuteCountClient(
            client=http_client, page_size=1
        ).fetch_snapshot(start=START, end=END)
    finally:
        http_client.close()

    assert snapshot.total_count == 2
    assert len(snapshot.records) == 2
    assert snapshot.source_records_before_end == 149000
    assert snapshot.source_latest_datetime == datetime.fromisoformat(
        "2026-08-10T10:16:00+10:00"
    )
    assert "sensing_datetime >= date'2026-08-10T10:00:00+10:00'" in requests[
        1
    ].url.params["where"]
    assert [request.url.params.get("offset") for request in requests[1:]] == [
        "0",
        "1",
    ]


def test_malformed_page_shape_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "select" in request.url.params:
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "minimum_datetime": None,
                            "maximum_datetime": None,
                            "record_count": 0,
                        }
                    ]
                },
            )
        return httpx.Response(200, json={"total_count": "two", "results": []})

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(CityDataResponseError):
            CityMinuteCountClient(client=http_client).fetch_snapshot(
                start=START, end=END
            )
    finally:
        http_client.close()


def test_later_page_failure_aborts_without_returning_partial_snapshot() -> None:
    requested_offsets: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if "select" in request.url.params:
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "minimum_datetime": None,
                            "maximum_datetime": None,
                            "record_count": 0,
                        }
                    ]
                },
            )
        offset = request.url.params["offset"]
        requested_offsets.append(offset)
        if offset == "1":
            raise httpx.ReadTimeout("private upstream timeout", request=request)
        return httpx.Response(
            200,
            json={"total_count": 2, "results": [_row(11, 15)]},
        )

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(CityDataConnectionError):
            CityMinuteCountClient(
                client=http_client,
                page_size=1,
            ).fetch_snapshot(start=START, end=END)
    finally:
        http_client.close()

    assert requested_offsets == ["0", "1"]
