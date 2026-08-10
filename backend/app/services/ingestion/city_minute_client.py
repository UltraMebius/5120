"""Paginated client for a bounded City Past Hour minute snapshot."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx

from ...config import SETTINGS
from .city_sensor_client import CityDataConnectionError, CityDataResponseError


REQUIRED_MINUTE_FIELDS = frozenset(
    {
        "location_id",
        "sensing_datetime",
        "sensing_date",
        "sensing_time",
        "direction_1",
        "direction_2",
        "total_of_directions",
    }
)


@dataclass(frozen=True)
class CityMinuteSnapshot:
    requested_start: datetime
    requested_end: datetime
    total_count: int
    records: tuple[dict[str, Any], ...]
    observed_fields: tuple[str, ...]
    source_minimum_datetime: datetime | None
    source_latest_datetime: datetime | None
    source_records_before_end: int
    fetched_at: datetime


class CityMinuteCountClient:
    """Fetch only the complete calculation interval through stable pagination."""

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
        self.dataset_id = dataset_id or settings.minute_dataset_id
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.request_timeout_seconds
        )
        self.request_timeout = httpx.Timeout(
            self.timeout_seconds,
            connect=min(5.0, self.timeout_seconds),
        )
        if not 1 <= page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")
        self.page_size = page_size
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=self.request_timeout,
            follow_redirects=True,
            headers={"User-Agent": "CalmWay-FIT5120/Phase-2C"},
        )

    @property
    def records_url(self) -> str:
        dataset_id = quote(self.dataset_id, safe="-")
        return f"{self.base_url}/catalog/datasets/{dataset_id}/records"

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "CityMinuteCountClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    @staticmethod
    def _require_aware(value: datetime, name: str) -> None:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{name} must be timezone-aware")

    @staticmethod
    def _where_clause(start: datetime, end: datetime) -> str:
        return (
            f"sensing_datetime >= date'{start.isoformat()}' "
            f"AND sensing_datetime < date'{end.isoformat()}'"
        )

    @staticmethod
    def _metadata_where_clause(end: datetime) -> str:
        return f"sensing_datetime < date'{end.isoformat()}'"

    def _get_json(self, params: dict[str, object]) -> Mapping[str, Any]:
        try:
            response = self._client.get(
                self.records_url,
                params=params,
                timeout=self.request_timeout,
            )
        except httpx.RequestError:
            raise CityDataConnectionError(
                "Unable to reach the City minute-count API."
            ) from None
        if not 200 <= response.status_code < 300:
            raise CityDataResponseError(
                f"City minute-count API returned HTTP {response.status_code}."
            )
        try:
            payload = response.json()
        except ValueError:
            raise CityDataResponseError(
                "City minute-count API returned malformed JSON."
            ) from None
        if not isinstance(payload, Mapping):
            raise CityDataResponseError(
                "City minute-count response must be a JSON object."
            )
        return payload

    @staticmethod
    def _parse_source_datetime(value: object) -> datetime | None:
        if value is None:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            raise CityDataResponseError(
                "City minute metadata contains an invalid source timestamp."
            ) from None
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise CityDataResponseError(
                "City minute metadata source timestamp must include an offset."
            )
        return parsed

    def _fetch_source_metadata(
        self, end: datetime
    ) -> tuple[datetime | None, datetime | None, int]:
        payload = self._get_json(
            {
                "select": (
                    "min(sensing_datetime) as minimum_datetime, "
                    "max(sensing_datetime) as maximum_datetime, "
                    "count(*) as record_count"
                ),
                "where": self._metadata_where_clause(end),
                "limit": 1,
                "timezone": SETTINGS.app_timezone,
            }
        )
        results = payload.get("results")
        if (
            not isinstance(results, list)
            or len(results) != 1
            or not isinstance(results[0], Mapping)
        ):
            raise CityDataResponseError(
                "City minute metadata response is missing one aggregate result."
            )
        row = results[0]
        record_count = row.get("record_count")
        if (
            isinstance(record_count, bool)
            or not isinstance(record_count, int)
            or record_count < 0
        ):
            raise CityDataResponseError(
                "City minute metadata contains an invalid record_count."
            )
        return (
            self._parse_source_datetime(row.get("minimum_datetime")),
            self._parse_source_datetime(row.get("maximum_datetime")),
            record_count,
        )

    def _fetch_page(
        self, start: datetime, end: datetime, offset: int
    ) -> tuple[int, list[dict[str, Any]]]:
        payload = self._get_json(
            {
                "where": self._where_clause(start, end),
                "order_by": (
                    "sensing_datetime,location_id,direction_1,direction_2,"
                    "total_of_directions"
                ),
                "limit": self.page_size,
                "offset": offset,
                "timezone": SETTINGS.app_timezone,
            }
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
                "City minute response is missing valid total_count/results."
            )
        if not all(isinstance(record, Mapping) for record in results):
            raise CityDataResponseError(
                "City minute results must contain JSON objects."
            )
        return total_count, [dict(record) for record in results]

    def fetch_snapshot(
        self, *, start: datetime, end: datetime
    ) -> CityMinuteSnapshot:
        self._require_aware(start, "start")
        self._require_aware(end, "end")
        if end <= start:
            raise ValueError("end must be after start")

        source_minimum, source_latest, records_before_end = (
            self._fetch_source_metadata(end)
        )
        records: list[dict[str, Any]] = []
        expected_total: int | None = None
        while expected_total is None or len(records) < expected_total:
            page_total, page_records = self._fetch_page(
                start, end, len(records)
            )
            if expected_total is None:
                expected_total = page_total
            elif page_total != expected_total:
                raise CityDataResponseError(
                    "City minute total changed during bounded pagination; retry "
                    "to obtain one consistent snapshot."
                )
            if not page_records and len(records) < expected_total:
                raise CityDataResponseError(
                    "City minute pagination ended before total_count."
                )
            records.extend(page_records)
            if len(records) > expected_total:
                raise CityDataResponseError(
                    "City minute API returned more rows than total_count."
                )

        observed_fields = tuple(
            sorted({field for record in records for field in record})
        )
        missing_fields = REQUIRED_MINUTE_FIELDS - set(observed_fields)
        if records and missing_fields:
            raise CityDataResponseError(
                "City minute results are missing required fields: "
                + ", ".join(sorted(missing_fields))
            )
        return CityMinuteSnapshot(
            requested_start=start,
            requested_end=end,
            total_count=expected_total or 0,
            records=tuple(records),
            observed_fields=observed_fields,
            source_minimum_datetime=source_minimum,
            source_latest_datetime=source_latest,
            source_records_before_end=records_before_end,
            fetched_at=datetime.now(timezone.utc),
        )
