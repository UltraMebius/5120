"""Batched authoritative hourly-count upserts and verification."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    DateTime,
    Engine,
    Integer,
    MetaData,
    SmallInteger,
    String,
    Table,
    Text,
    func,
    select,
    text,
    tuple_,
)
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.exc import SQLAlchemyError

from ..db.connection import get_database_engine
from ..db.exceptions import DatabaseQueryError, DatabaseWriteError
from ..models.hourly_count import HourlyCountRecord


_metadata = MetaData()
_sensor = Table("sensor", _metadata, Column("location_id", BigInteger))
_hourly = Table(
    "pedestrian_hourly_count",
    _metadata,
    Column("location_id", BigInteger),
    Column("sensing_date", Date),
    Column("hour_day", SmallInteger),
    Column("day_type", String),
    Column("source_id", BigInteger),
    Column("direction_1", BigInteger),
    Column("direction_2", BigInteger),
    Column("total_of_directions", BigInteger),
    Column("source_sensor_name", Text),
    Column("source_location_text", Text),
    Column("loaded_at", DateTime(timezone=True)),
)


@dataclass(frozen=True)
class HourlyWriteResult:
    inserted: int
    updated: int
    unknown_sensor_rows: int
    unknown_sensor_ids: tuple[int, ...]


@dataclass(frozen=True)
class HourlyImportVerification:
    row_count: int
    distinct_key_count: int
    zero_count_rows: int
    negative_count_rows: int
    invalid_hour_rows: int
    day_type_mismatch_rows: int
    minimum_date: date | None
    maximum_date: date | None
    minute_row_count: int
    sensor_baseline_row_count: int
    network_baseline_row_count: int
    current_activity_row_count: int
    spatial_cache_row_count: int

    @property
    def ok(self) -> bool:
        return (
            self.row_count > 0
            and self.row_count == self.distinct_key_count
            and self.negative_count_rows == 0
            and self.invalid_hour_rows == 0
            and self.day_type_mismatch_rows == 0
            and self.minute_row_count == 0
            and self.sensor_baseline_row_count == 0
            and self.network_baseline_row_count == 0
            and self.current_activity_row_count == 0
            and self.spatial_cache_row_count == 0
        )


class HourlyCountRepository:
    """Write bounded batches without creating unknown sensor identities."""

    def __init__(self, engine: Engine | None = None) -> None:
        self.engine = engine

    def find_unknown_sensor_ids(self, location_ids: set[int]) -> set[int]:
        if not location_ids:
            return set()
        database_engine = self.engine or get_database_engine()
        try:
            with database_engine.connect() as connection:
                known_ids = set(
                    connection.execute(
                        select(_sensor.c.location_id).where(
                            _sensor.c.location_id.in_(location_ids)
                        )
                    ).scalars()
                )
        except SQLAlchemyError:
            raise DatabaseQueryError(
                "Unable to reconcile hourly source IDs with sensor masters."
            ) from None
        return location_ids - known_ids

    def upsert_hourly_counts(
        self,
        records: Sequence[HourlyCountRecord],
    ) -> HourlyWriteResult:
        if not records:
            return HourlyWriteResult(0, 0, 0, ())
        database_engine = self.engine or get_database_engine()
        location_ids = {record.location_id for record in records}

        try:
            with database_engine.begin() as connection:
                known_sensor_ids = set(
                    connection.execute(
                        select(_sensor.c.location_id).where(
                            _sensor.c.location_id.in_(location_ids)
                        )
                    ).scalars()
                )
                unknown_sensor_ids = location_ids - known_sensor_ids
                eligible_records = [
                    record
                    for record in records
                    if record.location_id in known_sensor_ids
                ]
                keys = [record.key for record in eligible_records]
                existing_keys: set[tuple[int, date, int]] = set()
                if keys:
                    existing_keys = {
                        (int(row.location_id), row.sensing_date, int(row.hour_day))
                        for row in connection.execute(
                            select(
                                _hourly.c.location_id,
                                _hourly.c.sensing_date,
                                _hourly.c.hour_day,
                            ).where(
                                tuple_(
                                    _hourly.c.location_id,
                                    _hourly.c.sensing_date,
                                    _hourly.c.hour_day,
                                ).in_(keys)
                            )
                        )
                    }

                    base_insert = postgresql_insert(_hourly)
                    upsert = base_insert.on_conflict_do_update(
                        index_elements=["location_id", "sensing_date", "hour_day"],
                        set_={
                            "day_type": base_insert.excluded.day_type,
                            "source_id": base_insert.excluded.source_id,
                            "direction_1": base_insert.excluded.direction_1,
                            "direction_2": base_insert.excluded.direction_2,
                            "total_of_directions": (
                                base_insert.excluded.total_of_directions
                            ),
                            "source_sensor_name": (
                                base_insert.excluded.source_sensor_name
                            ),
                            "source_location_text": (
                                base_insert.excluded.source_location_text
                            ),
                            "loaded_at": func.now(),
                        },
                    )
                    connection.execute(
                        upsert,
                        [
                            {
                                "location_id": record.location_id,
                                "sensing_date": record.sensing_date,
                                "hour_day": record.hour_day,
                                "day_type": record.day_type,
                                "source_id": record.source_id,
                                "direction_1": record.direction_1,
                                "direction_2": record.direction_2,
                                "total_of_directions": record.total_of_directions,
                                "source_sensor_name": record.source_sensor_name,
                                "source_location_text": record.source_location_text,
                            }
                            for record in eligible_records
                        ],
                    )
        except SQLAlchemyError:
            raise DatabaseWriteError(
                "Hourly-count batch failed and its transaction was rolled back; "
                "earlier successful batches, if any, remain committed."
            ) from None

        eligible_keys = {record.key for record in eligible_records}
        return HourlyWriteResult(
            inserted=len(eligible_keys - existing_keys),
            updated=len(eligible_keys & existing_keys),
            unknown_sensor_rows=sum(
                record.location_id in unknown_sensor_ids for record in records
            ),
            unknown_sensor_ids=tuple(sorted(unknown_sensor_ids)),
        )


def inspect_hourly_import(
    start_date: date,
    end_date: date,
    engine: Engine | None = None,
) -> HourlyImportVerification:
    database_engine = engine or get_database_engine()
    try:
        with database_engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT
                        COUNT(*) AS row_count,
                        COUNT(DISTINCT (location_id, sensing_date, hour_day))
                            AS distinct_key_count,
                        COUNT(*) FILTER (WHERE total_of_directions = 0)
                            AS zero_count_rows,
                        COUNT(*) FILTER (WHERE total_of_directions < 0)
                            AS negative_count_rows,
                        COUNT(*) FILTER (WHERE hour_day NOT BETWEEN 0 AND 23)
                            AS invalid_hour_rows,
                        COUNT(*) FILTER (
                            WHERE day_type <> CASE
                                WHEN EXTRACT(ISODOW FROM sensing_date) < 6
                                    THEN 'Weekday'
                                ELSE 'Weekend'
                            END
                        ) AS day_type_mismatch_rows,
                        MIN(sensing_date) AS minimum_date,
                        MAX(sensing_date) AS maximum_date
                    FROM pedestrian_hourly_count
                    WHERE sensing_date BETWEEN :start_date AND :end_date
                    """
                ),
                {"start_date": start_date, "end_date": end_date},
            ).mappings().one()
            untouched = connection.execute(
                text(
                    """
                    SELECT
                        (SELECT COUNT(*) FROM pedestrian_minute_observation_raw)
                            AS minute_row_count,
                        (SELECT COUNT(*) FROM sensor_hour_daytype_baseline)
                            AS sensor_baseline_row_count,
                        (SELECT COUNT(*) FROM network_hour_daytype_baseline)
                            AS network_baseline_row_count,
                        (SELECT COUNT(*) FROM current_sensor_activity)
                            AS current_activity_row_count,
                        (SELECT COUNT(*) FROM spatial_activity_cache)
                            AS spatial_cache_row_count
                    """
                )
            ).mappings().one()
    except SQLAlchemyError:
        raise DatabaseQueryError(
            "Hourly-count post-import verification failed."
        ) from None

    return HourlyImportVerification(
        row_count=int(row["row_count"]),
        distinct_key_count=int(row["distinct_key_count"]),
        zero_count_rows=int(row["zero_count_rows"]),
        negative_count_rows=int(row["negative_count_rows"]),
        invalid_hour_rows=int(row["invalid_hour_rows"]),
        day_type_mismatch_rows=int(row["day_type_mismatch_rows"]),
        minimum_date=row["minimum_date"],
        maximum_date=row["maximum_date"],
        minute_row_count=int(untouched["minute_row_count"]),
        sensor_baseline_row_count=int(untouched["sensor_baseline_row_count"]),
        network_baseline_row_count=int(untouched["network_baseline_row_count"]),
        current_activity_row_count=int(untouched["current_activity_row_count"]),
        spatial_cache_row_count=int(untouched["spatial_cache_row_count"]),
    )
