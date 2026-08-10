"""Streaming client for filtered official hourly-count CSV exports."""

import csv
from datetime import date
from itertools import chain
from typing import Iterator
from urllib.parse import quote

import httpx

from ...config import SETTINGS
from .city_sensor_client import CityDataConnectionError, CityDataResponseError


REQUIRED_HOURLY_FIELDS = frozenset(
    {"location_id", "sensing_date", "hourday", "pedestriancount"}
)


class CityHourlyCountClient:
    """Count and stream one explicit date range without loading it all."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        dataset_id: str | None = None,
        timeout_seconds: float | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        settings = SETTINGS.city_data
        self.base_url = (base_url or settings.base_url).rstrip("/")
        self.dataset_id = dataset_id or settings.hourly_dataset_id
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.request_timeout_seconds
        )
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=self.timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": "CalmWay-FIT5120/Phase-2A-3"},
        )
        self.observed_fields: tuple[str, ...] = ()

    @property
    def dataset_url(self) -> str:
        dataset_id = quote(self.dataset_id, safe="-")
        return f"{self.base_url}/catalog/datasets/{dataset_id}"

    @staticmethod
    def _where_clause(start_date: date, end_date: date) -> str:
        return (
            f"sensing_date >= date'{start_date.isoformat()}' "
            f"AND sensing_date <= date'{end_date.isoformat()}'"
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "CityHourlyCountClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def count_records(self, start_date: date, end_date: date) -> int:
        try:
            response = self._client.get(
                f"{self.dataset_url}/records",
                params={
                    "where": self._where_clause(start_date, end_date),
                    "limit": 1,
                    "timezone": SETTINGS.app_timezone,
                },
                timeout=self.timeout_seconds,
            )
        except httpx.RequestError:
            raise CityDataConnectionError(
                "Unable to reach the City hourly-count API."
            ) from None
        if not 200 <= response.status_code < 300:
            raise CityDataResponseError(
                f"City hourly-count API returned HTTP {response.status_code}."
            )
        try:
            payload = response.json()
        except ValueError:
            raise CityDataResponseError(
                "City hourly-count API returned malformed JSON metadata."
            ) from None
        total_count = payload.get("total_count") if isinstance(payload, dict) else None
        if (
            isinstance(total_count, bool)
            or not isinstance(total_count, int)
            or total_count < 0
        ):
            raise CityDataResponseError(
                "City hourly-count response is missing a valid total_count."
            )
        return total_count

    def iter_records(
        self,
        start_date: date,
        end_date: date,
    ) -> Iterator[dict[str, str | None]]:
        params = {
            "where": self._where_clause(start_date, end_date),
            "order_by": "sensing_date,location_id,hourday",
            "delimiter": ",",
            "timezone": SETTINGS.app_timezone,
        }
        try:
            with self._client.stream(
                "GET",
                f"{self.dataset_url}/exports/csv",
                params=params,
                timeout=self.timeout_seconds,
            ) as response:
                if not 200 <= response.status_code < 300:
                    raise CityDataResponseError(
                        "City hourly-count CSV export returned HTTP "
                        f"{response.status_code}."
                    )
                lines = response.iter_lines()
                try:
                    header = next(lines).lstrip("\ufeff")
                except StopIteration:
                    raise CityDataResponseError(
                        "City hourly-count CSV export returned no header."
                    ) from None
                reader = csv.DictReader(chain([header], lines), delimiter=",")
                fieldnames = tuple(reader.fieldnames or ())
                missing_fields = REQUIRED_HOURLY_FIELDS - set(fieldnames)
                if missing_fields:
                    raise CityDataResponseError(
                        "City hourly-count CSV is missing required fields: "
                        + ", ".join(sorted(missing_fields))
                    )
                self.observed_fields = fieldnames
                for record in reader:
                    yield record
        except httpx.RequestError:
            raise CityDataConnectionError(
                "Unable to stream the City hourly-count CSV export."
            ) from None
