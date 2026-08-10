"""Validated minute observation and derived current sensor state records."""

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
import hashlib
import json


@dataclass(frozen=True)
class MinuteObservation:
    location_id: int
    source_sensing_datetime: datetime
    sensing_date_local: date
    sensing_time_local: time
    direction_1: int | None
    direction_2: int | None
    total_of_directions: int
    payload_hash: str

    @property
    def logical_key(self) -> tuple[int, datetime]:
        return self.location_id, self.source_sensing_datetime

    @classmethod
    def create(
        cls,
        *,
        location_id: int,
        source_sensing_datetime: datetime,
        sensing_date_local: date,
        sensing_time_local: time,
        direction_1: int | None,
        direction_2: int | None,
        total_of_directions: int,
    ) -> "MinuteObservation":
        canonical_timestamp = (
            source_sensing_datetime.astimezone(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        )
        canonical_payload = json.dumps(
            {
                "direction_1": direction_1,
                "direction_2": direction_2,
                "location_id": location_id,
                "source_sensing_datetime": canonical_timestamp,
                "total_of_directions": total_of_directions,
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return cls(
            location_id=location_id,
            source_sensing_datetime=source_sensing_datetime,
            sensing_date_local=sensing_date_local,
            sensing_time_local=sensing_time_local,
            direction_1=direction_1,
            direction_2=direction_2,
            total_of_directions=total_of_directions,
            payload_hash=hashlib.sha256(canonical_payload).hexdigest(),
        )


@dataclass(frozen=True)
class CurrentSensorDefinition:
    location_id: int
    location_type: str
    status: str | None

    @property
    def modelling_eligible(self) -> bool:
        return (
            self.location_type.strip().casefold() == "outdoor"
            and (self.status or "").strip().upper() == "A"
        )


@dataclass(frozen=True)
class HistoricalPercentiles:
    network: float | None
    local: float | None


@dataclass(frozen=True)
class CurrentSensorActivityRecord:
    location_id: int
    current_15m_window_start: datetime | None
    current_15m_window_end: datetime | None
    current_15m_observed_rows: int | None
    current_15m_count: int | None
    current_15m_network_percentile: float | None
    current_crowd_exposure_score: float | None
    current_crowd_level: str | None
    comparison_hour_start: datetime | None
    current_1h_observed_rows: int | None
    current_1h_count: int | None
    current_1h_network_historical_percentile: float | None
    current_1h_local_historical_percentile: float | None
    current_local_condition: str | None
    data_state: str
    calculated_at: datetime
