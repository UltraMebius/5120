"""Validated sensor-location data passed to the database repository."""

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class SensorLocationRecord:
    """One source sensor plus its optional usable current location."""

    location_id: int
    sensor_description: str | None
    sensor_name: str | None
    installation_date: date | None
    note: str | None
    location_type: str | None
    status: str | None
    direction_1_label: str | None
    direction_2_label: str | None
    latitude: float | None
    longitude: float | None
    source_updated_at: datetime | None = None

    @property
    def has_usable_location(self) -> bool:
        """Whether the authoritative non-null location row can be written."""

        return (
            self.location_type is not None
            and self.latitude is not None
            and self.longitude is not None
        )
