"""Transactional writes and read-only checks for current sensor locations."""

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import Engine, bindparam, text
from sqlalchemy.exc import SQLAlchemyError

from ..db.connection import get_database_engine
from ..db.exceptions import DatabaseQueryError, DatabaseWriteError
from ..models.sensor import SensorLocationRecord


@dataclass(frozen=True)
class SensorWriteResult:
    sensors_inserted: int
    sensors_updated: int
    locations_inserted: int
    locations_updated: int
    locations_removed: int


@dataclass(frozen=True)
class SensorImportVerification:
    sensor_count: int
    location_count: int
    duplicate_sensor_ids: int
    invalid_srid_count: int
    coordinate_order_mismatch_count: int
    invalid_coordinate_range_count: int
    outside_melbourne_bounds_count: int
    sensors_without_current_location_count: int
    status_values: tuple[tuple[str | None, int], ...]
    missing_source_sensor_ids: tuple[int, ...]
    missing_expected_location_ids: tuple[int, ...]
    unexpected_location_ids: tuple[int, ...]
    status_mismatch_ids: tuple[int, ...]

    @property
    def ok(self) -> bool:
        return (
            self.sensor_count > 0
            and self.location_count > 0
            and self.duplicate_sensor_ids == 0
            and self.invalid_srid_count == 0
            and self.coordinate_order_mismatch_count == 0
            and self.invalid_coordinate_range_count == 0
            and self.outside_melbourne_bounds_count == 0
            and not self.missing_source_sensor_ids
            and not self.missing_expected_location_ids
            and not self.unexpected_location_ids
            and not self.status_mismatch_ids
        )


_SELECT_SENSOR_IDS = text(
    "SELECT location_id FROM sensor WHERE location_id IN :location_ids"
).bindparams(bindparam("location_ids", expanding=True))

_SELECT_LOCATION_IDS = text(
    """
    SELECT location_id
    FROM sensor_location_current
    WHERE location_id IN :location_ids
    """
).bindparams(bindparam("location_ids", expanding=True))

_UPSERT_SENSOR = text(
    """
    INSERT INTO sensor (location_id)
    VALUES (:location_id)
    ON CONFLICT (location_id) DO UPDATE
    SET last_seen_at = NOW()
    """
)

_UPSERT_LOCATION = text(
    """
    INSERT INTO sensor_location_current (
        location_id,
        sensor_description,
        sensor_name,
        installation_date,
        note,
        location_type,
        status,
        direction_1_label,
        direction_2_label,
        latitude,
        longitude,
        geom,
        source_updated_at
    ) VALUES (
        :location_id,
        :sensor_description,
        :sensor_name,
        :installation_date,
        :note,
        :location_type,
        :status,
        :direction_1_label,
        :direction_2_label,
        :latitude,
        :longitude,
        ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography,
        :source_updated_at
    )
    ON CONFLICT (location_id) DO UPDATE SET
        sensor_description = EXCLUDED.sensor_description,
        sensor_name = EXCLUDED.sensor_name,
        installation_date = EXCLUDED.installation_date,
        note = EXCLUDED.note,
        location_type = EXCLUDED.location_type,
        status = EXCLUDED.status,
        direction_1_label = EXCLUDED.direction_1_label,
        direction_2_label = EXCLUDED.direction_2_label,
        latitude = EXCLUDED.latitude,
        longitude = EXCLUDED.longitude,
        geom = EXCLUDED.geom,
        source_updated_at = EXCLUDED.source_updated_at,
        loaded_at = NOW()
    """
)

_DELETE_UNUSABLE_LOCATIONS = text(
    """
    DELETE FROM sensor_location_current
    WHERE location_id IN :location_ids
    """
).bindparams(bindparam("location_ids", expanding=True))


class SensorRepository:
    """Persist one full source snapshot without per-row commits."""

    def __init__(self, engine: Engine | None = None) -> None:
        self.engine = engine

    def upsert_sensor_locations(
        self,
        records: Sequence[SensorLocationRecord],
    ) -> SensorWriteResult:
        if not records:
            return SensorWriteResult(0, 0, 0, 0, 0)

        database_engine = self.engine or get_database_engine()
        location_ids = [record.location_id for record in records]
        location_records = [record for record in records if record.has_usable_location]
        usable_location_ids = {record.location_id for record in location_records}
        unusable_location_ids = [
            location_id
            for location_id in location_ids
            if location_id not in usable_location_ids
        ]

        try:
            with database_engine.begin() as connection:
                existing_sensor_ids = set(
                    connection.execute(
                        _SELECT_SENSOR_IDS, {"location_ids": location_ids}
                    ).scalars()
                )
                existing_location_ids = set(
                    connection.execute(
                        _SELECT_LOCATION_IDS, {"location_ids": location_ids}
                    ).scalars()
                )

                connection.execute(
                    _UPSERT_SENSOR,
                    [{"location_id": location_id} for location_id in location_ids],
                )

                if unusable_location_ids:
                    connection.execute(
                        _DELETE_UNUSABLE_LOCATIONS,
                        {"location_ids": unusable_location_ids},
                    )

                if location_records:
                    connection.execute(
                        _UPSERT_LOCATION,
                        [
                            {
                                "location_id": record.location_id,
                                "sensor_description": record.sensor_description,
                                "sensor_name": record.sensor_name,
                                "installation_date": record.installation_date,
                                "note": record.note,
                                "location_type": record.location_type,
                                "status": record.status,
                                "direction_1_label": record.direction_1_label,
                                "direction_2_label": record.direction_2_label,
                                "latitude": record.latitude,
                                "longitude": record.longitude,
                                "source_updated_at": record.source_updated_at,
                            }
                            for record in location_records
                        ],
                    )
        except SQLAlchemyError:
            raise DatabaseWriteError(
                "Sensor-location import failed; the database transaction was "
                "rolled back."
            ) from None

        return SensorWriteResult(
            sensors_inserted=len(set(location_ids) - existing_sensor_ids),
            sensors_updated=len(set(location_ids) & existing_sensor_ids),
            locations_inserted=len(usable_location_ids - existing_location_ids),
            locations_updated=len(usable_location_ids & existing_location_ids),
            locations_removed=len(
                set(unusable_location_ids) & existing_location_ids
            ),
        )


def inspect_sensor_import(
    source_records: Sequence[SensorLocationRecord],
    engine: Engine | None = None,
) -> SensorImportVerification:
    """Verify IDs, status preservation, and PostGIS coordinate integrity."""

    database_engine = engine or get_database_engine()
    try:
        with database_engine.connect() as connection:
            summary = connection.execute(
                text(
                    """
                    SELECT
                        (SELECT COUNT(*) FROM sensor) AS sensor_count,
                        (SELECT COUNT(*) FROM sensor_location_current)
                            AS location_count,
                        (
                            SELECT COUNT(*) FROM (
                                SELECT location_id
                                FROM sensor
                                GROUP BY location_id
                                HAVING COUNT(*) > 1
                            ) duplicate_groups
                        ) AS duplicate_sensor_ids,
                        COUNT(*) FILTER (
                            WHERE ST_SRID(geom::geometry) <> 4326
                        ) AS invalid_srid_count,
                        COUNT(*) FILTER (
                            WHERE ABS(ST_X(geom::geometry) - longitude) > 1e-9
                               OR ABS(ST_Y(geom::geometry) - latitude) > 1e-9
                        ) AS coordinate_order_mismatch_count,
                        COUNT(*) FILTER (
                            WHERE latitude NOT BETWEEN -90 AND 90
                               OR longitude NOT BETWEEN -180 AND 180
                        ) AS invalid_coordinate_range_count,
                        COUNT(*) FILTER (
                            WHERE latitude NOT BETWEEN -39 AND -36
                               OR longitude NOT BETWEEN 144 AND 146
                        ) AS outside_melbourne_bounds_count
                    FROM sensor_location_current
                    """
                )
            ).mappings().one()
            status_values = tuple(
                (row.status, int(row.record_count))
                for row in connection.execute(
                    text(
                        """
                        SELECT status, COUNT(*) AS record_count
                        FROM sensor_location_current
                        GROUP BY status
                        ORDER BY status NULLS FIRST
                        """
                    )
                )
            )

            source_ids = [record.location_id for record in source_records]
            database_sensor_ids: set[int] = set()
            database_locations: dict[int, str | None] = {}
            if source_ids:
                database_sensor_ids = set(
                    connection.execute(
                        _SELECT_SENSOR_IDS, {"location_ids": source_ids}
                    ).scalars()
                )
                location_rows = connection.execute(
                    text(
                        """
                        SELECT location_id, status
                        FROM sensor_location_current
                        WHERE location_id IN :location_ids
                        """
                    ).bindparams(bindparam("location_ids", expanding=True)),
                    {"location_ids": source_ids},
                )
                database_locations = {
                    int(row.location_id): row.status for row in location_rows
                }
    except SQLAlchemyError:
        raise DatabaseQueryError(
            "Sensor-location post-import verification failed."
        ) from None

    expected_source_ids = {record.location_id for record in source_records}
    expected_location_ids = {
        record.location_id for record in source_records if record.has_usable_location
    }
    expected_status = {
        record.location_id: record.status
        for record in source_records
        if record.has_usable_location
    }
    actual_location_ids = set(database_locations)

    return SensorImportVerification(
        sensor_count=int(summary["sensor_count"]),
        location_count=int(summary["location_count"]),
        duplicate_sensor_ids=int(summary["duplicate_sensor_ids"]),
        invalid_srid_count=int(summary["invalid_srid_count"]),
        coordinate_order_mismatch_count=int(
            summary["coordinate_order_mismatch_count"]
        ),
        invalid_coordinate_range_count=int(
            summary["invalid_coordinate_range_count"]
        ),
        outside_melbourne_bounds_count=int(
            summary["outside_melbourne_bounds_count"]
        ),
        sensors_without_current_location_count=(
            int(summary["sensor_count"]) - int(summary["location_count"])
        ),
        status_values=status_values,
        missing_source_sensor_ids=tuple(
            sorted(expected_source_ids - database_sensor_ids)
        ),
        missing_expected_location_ids=tuple(
            sorted(expected_location_ids - actual_location_ids)
        ),
        unexpected_location_ids=tuple(
            sorted((expected_source_ids - expected_location_ids) & actual_location_ids)
        ),
        status_mismatch_ids=tuple(
            sorted(
                location_id
                for location_id in expected_location_ids & actual_location_ids
                if database_locations[location_id] != expected_status[location_id]
            )
        ),
    )
