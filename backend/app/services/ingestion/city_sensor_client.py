"""HTTP client for the official City sensor-location records endpoint."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

from ...config import SETTINGS


class CityDataError(RuntimeError):
    """Base class for expected City Open Data failures."""


class CityDataConnectionError(CityDataError):
    """Raised when the public API cannot be reached."""


class CityDataResponseError(CityDataError):
    """Raised for HTTP, JSON, or response-structure failures."""


@dataclass(frozen=True)
class CitySensorSnapshot:
    """Complete current source snapshot returned through pagination."""

    total_count: int
    records: tuple[dict[str, Any], ...]
    observed_fields: tuple[str, ...]


class CitySensorLocationClient:
    """Fetch every current sensor-location row with stable offset pagination."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        dataset_id: str | None = None,
        timeout_seconds: float | None = None,
        page_size: int = 100,
        client: httpx.Client | None = None,
    ) -> None:
        settings = SETTINGS.city_data
        self.base_url = (base_url or settings.base_url).rstrip("/")
        self.dataset_id = dataset_id or settings.sensor_dataset_id
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.request_timeout_seconds
        )
        if not 1 <= page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")
        self.page_size = page_size
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=self.timeout_seconds,
            headers={"User-Agent": "CalmWay-FIT5120/Phase-2A-2"},
        )

    @property
    def records_url(self) -> str:
        dataset_id = quote(self.dataset_id, safe="-")
        return f"{self.base_url}/catalog/datasets/{dataset_id}/records"

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "CitySensorLocationClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _fetch_page(self, offset: int) -> tuple[int, list[dict[str, Any]]]:
        try:
            response = self._client.get(
                self.records_url,
                params={
                    "order_by": "location_id",
                    "limit": self.page_size,
                    "offset": offset,
                },
                timeout=self.timeout_seconds,
            )
        except httpx.RequestError:
            raise CityDataConnectionError(
                "Unable to reach the City of Melbourne sensor-location API."
            ) from None

        if not 200 <= response.status_code < 300:
            raise CityDataResponseError(
                "City sensor-location API returned HTTP "
                f"{response.status_code}."
            )

        try:
            payload = response.json()
        except ValueError:
            raise CityDataResponseError(
                "City sensor-location API returned malformed JSON."
            ) from None

        if not isinstance(payload, Mapping):
            raise CityDataResponseError(
                "City sensor-location response must be a JSON object."
            )
        total_count = payload.get("total_count")
        results = payload.get("results")
        if (
            isinstance(total_count, bool)
            or not isinstance(total_count, int)
            or total_count < 0
            or not isinstance(results, list)
        ):
            raise CityDataResponseError(
                "City sensor-location response is missing valid total_count/results."
            )
        if not all(isinstance(record, Mapping) for record in results):
            raise CityDataResponseError(
                "City sensor-location results must contain JSON objects."
            )
        return total_count, [dict(record) for record in results]

    def fetch_all(self) -> CitySensorSnapshot:
        records: list[dict[str, Any]] = []
        expected_total: int | None = None

        while expected_total is None or len(records) < expected_total:
            page_total, page_records = self._fetch_page(len(records))
            if expected_total is None:
                expected_total = page_total
            elif page_total != expected_total:
                raise CityDataResponseError(
                    "City sensor-location total changed during pagination; retry "
                    "the import to obtain one consistent snapshot."
                )
            if not page_records and len(records) < expected_total:
                raise CityDataResponseError(
                    "City sensor-location pagination ended before total_count."
                )
            records.extend(page_records)
            if len(records) > expected_total:
                raise CityDataResponseError(
                    "City sensor-location API returned more rows than total_count."
                )

        observed_fields = tuple(
            sorted({field for record in records for field in record})
        )
        return CitySensorSnapshot(
            total_count=expected_total or 0,
            records=tuple(records),
            observed_fields=observed_fields,
        )
