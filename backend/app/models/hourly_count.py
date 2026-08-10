"""Validated authoritative hourly pedestrian-count observation."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class HourlyCountRecord:
    location_id: int
    sensing_date: date
    hour_day: int
    day_type: str
    source_id: int | None
    direction_1: int | None
    direction_2: int | None
    total_of_directions: int
    source_sensor_name: str | None
    source_location_text: str | None

    @property
    def key(self) -> tuple[int, date, int]:
        return self.location_id, self.sensing_date, self.hour_day
