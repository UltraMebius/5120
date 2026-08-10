from datetime import date
from pathlib import Path

import httpx

from backend.app.services.ingestion.city_hourly_client import (
    CityHourlyCountClient,
)


FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "city_hourly_counts_sample.csv"
)


def test_filtered_csv_is_streamed_with_required_live_fields() -> None:
    csv_content = FIXTURE_PATH.read_bytes()
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/records"):
            return httpx.Response(200, json={"total_count": 2, "results": []})
        return httpx.Response(
            200,
            content=csv_content,
            headers={"content-type": "text/csv; charset=utf-8"},
        )

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = CityHourlyCountClient(client=http_client)
    try:
        total = client.count_records(date(2025, 1, 4), date(2025, 1, 4))
        records = list(
            client.iter_records(date(2025, 1, 4), date(2025, 1, 4))
        )
    finally:
        http_client.close()

    assert total == 2
    assert len(records) == 2
    assert records[0]["location_id"] == "25"
    assert records[0]["pedestriancount"] == "0"
    assert "location_id" in client.observed_fields
    assert "sensing_date >= date'2025-01-04'" in requests[0].url.params["where"]
    assert requests[1].url.path.endswith("/exports/csv")
    assert requests[1].url.params["delimiter"] == ","
