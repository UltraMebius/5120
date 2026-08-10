"""Transactional raw-minute ingestion with exact deduplication and conflict retention."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CHAR,
    Column,
    Date,
    DateTime,
    Engine,
    Integer,
    JSON,
    MetaData,
    String,
    Table,
    Time,
    func,
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.exc import SQLAlchemyError

from ..db.connection import get_database_engine
from ..db.exceptions import DatabaseQueryError, DatabaseWriteError
from ..models.minute import MinuteObservation


_metadata = MetaData()
_sensor = Table("sensor", _metadata, Column("location_id", BigInteger))
_run = Table(
    "ingestion_run",
    _metadata,
    Column("ingestion_run_id", BigInteger, primary_key=True),
    Column("source_name", String),
    Column("started_at", DateTime(timezone=True)),
    Column("finished_at", DateTime(timezone=True)),
    Column("status", String),
    Column("rows_received", BigInteger),
    Column("rows_inserted", BigInteger),
    Column("rows_skipped_exact_duplicate", BigInteger),
    Column("conflict_groups_detected", BigInteger),
    Column("error_message", String),
    Column("metadata", JSON),
)
_minute = Table(
    "pedestrian_minute_observation_raw",
    _metadata,
    Column("minute_record_id", BigInteger, primary_key=True),
    Column("location_id", BigInteger),
    Column("source_sensing_datetime", DateTime(timezone=True)),
    Column("sensing_date_local", Date),
    Column("sensing_time_local", Time),
    Column("direction_1", BigInteger),
    Column("direction_2", BigInteger),
    Column("total_of_directions", BigInteger),
    Column("payload_hash", CHAR(64)),
    Column("ingestion_run_id", BigInteger),
    Column("ingested_at", DateTime(timezone=True)),
)


@dataclass(frozen=True)
class MinuteWriteResult:
    ingestion_run_id: int
    rows_received: int
    rows_inserted: int
    rows_skipped_exact_duplicate: int
    unknown_sensor_rows: int
    unknown_sensor_ids: tuple[int, ...]
    conflict_groups_detected: int


class MinuteRepository:
    """Persist immutable payload variants; retention is intentionally deferred."""

    def __init__(self, engine: Engine | None = None) -> None:
        self.engine = engine

    def find_unknown_sensor_ids(self, location_ids: set[int]) -> set[int]:
        if not location_ids:
            return set()
        database_engine = self.engine or get_database_engine()
        try:
            with database_engine.connect() as connection:
                known = set(
                    connection.execute(
                        select(_sensor.c.location_id).where(
                            _sensor.c.location_id.in_(location_ids)
                        )
                    ).scalars()
                )
        except SQLAlchemyError:
            raise DatabaseQueryError(
                "Unable to reconcile live minute IDs with sensor masters."
            ) from None
        return location_ids - {int(value) for value in known}

    def load_observations(
        self, *, start: datetime, end: datetime
    ) -> tuple[MinuteObservation, ...]:
        try:
            database_engine = self.engine or get_database_engine()
            with database_engine.connect() as connection:
                rows = connection.execute(
                    select(
                        _minute.c.location_id,
                        _minute.c.source_sensing_datetime,
                        _minute.c.sensing_date_local,
                        _minute.c.sensing_time_local,
                        _minute.c.direction_1,
                        _minute.c.direction_2,
                        _minute.c.total_of_directions,
                        _minute.c.payload_hash,
                    ).where(
                        _minute.c.source_sensing_datetime >= start,
                        _minute.c.source_sensing_datetime < end,
                    )
                ).mappings()
                return tuple(
                    MinuteObservation(
                        location_id=int(row["location_id"]),
                        source_sensing_datetime=row["source_sensing_datetime"],
                        sensing_date_local=row["sensing_date_local"],
                        sensing_time_local=row["sensing_time_local"],
                        direction_1=(
                            None
                            if row["direction_1"] is None
                            else int(row["direction_1"])
                        ),
                        direction_2=(
                            None
                            if row["direction_2"] is None
                            else int(row["direction_2"])
                        ),
                        total_of_directions=int(row["total_of_directions"]),
                        payload_hash=str(row["payload_hash"]),
                    )
                    for row in rows
                )
        except SQLAlchemyError:
            raise DatabaseQueryError(
                "Unable to read the raw minute calculation interval."
            ) from None

    def ingest(
        self,
        observations: Sequence[MinuteObservation],
        *,
        source_name: str,
        rows_received: int,
        interval_start: datetime,
        interval_end: datetime,
        metadata: Mapping[str, Any],
    ) -> MinuteWriteResult:
        database_engine = self.engine or get_database_engine()
        location_ids = {row.location_id for row in observations}
        try:
            with database_engine.begin() as connection:
                known_ids = {
                    int(value)
                    for value in connection.execute(
                        select(_sensor.c.location_id).where(
                            _sensor.c.location_id.in_(location_ids)
                        )
                    ).scalars()
                }
                unknown_ids = location_ids - known_ids
                eligible = [
                    row for row in observations if row.location_id in known_ids
                ]

                run_id = int(
                    connection.execute(
                        postgresql_insert(_run)
                        .values(
                            source_name=source_name,
                            status="RUNNING",
                            rows_received=rows_received,
                            metadata=dict(metadata),
                        )
                        .returning(_run.c.ingestion_run_id)
                    ).scalar_one()
                )

                unique_by_hash = {row.payload_hash: row for row in eligible}
                inserted_hashes: tuple[str, ...] = ()
                if unique_by_hash:
                    insert_statement = (
                        postgresql_insert(_minute)
                        .values(
                            [
                                {
                                    "location_id": row.location_id,
                                    "source_sensing_datetime": (
                                        row.source_sensing_datetime
                                    ),
                                    "sensing_date_local": row.sensing_date_local,
                                    "sensing_time_local": row.sensing_time_local,
                                    "direction_1": row.direction_1,
                                    "direction_2": row.direction_2,
                                    "total_of_directions": (
                                        row.total_of_directions
                                    ),
                                    "payload_hash": row.payload_hash,
                                    "ingestion_run_id": run_id,
                                }
                                for row in unique_by_hash.values()
                            ]
                        )
                        .on_conflict_do_nothing(index_elements=["payload_hash"])
                        .returning(_minute.c.payload_hash)
                    )
                    inserted_hashes = tuple(
                        str(value)
                        for value in connection.execute(
                            insert_statement
                        ).scalars()
                    )

                conflict_groups = int(
                    connection.execute(
                        text(
                            """
                            SELECT COUNT(*)
                            FROM v_minute_conflict_groups
                            WHERE source_sensing_datetime >= :interval_start
                              AND source_sensing_datetime < :interval_end
                            """
                        ),
                        {
                            "interval_start": interval_start,
                            "interval_end": interval_end,
                        },
                    ).scalar_one()
                )
                exact_skipped = len(eligible) - len(inserted_hashes)
                connection.execute(
                    update(_run)
                    .where(_run.c.ingestion_run_id == run_id)
                    .values(
                        finished_at=func.now(),
                        status="SUCCEEDED",
                        rows_inserted=len(inserted_hashes),
                        rows_skipped_exact_duplicate=exact_skipped,
                        conflict_groups_detected=conflict_groups,
                    )
                )
        except SQLAlchemyError:
            raise DatabaseWriteError(
                "Minute ingestion failed; the raw rows and run ledger were "
                "rolled back together."
            ) from None

        return MinuteWriteResult(
            ingestion_run_id=run_id,
            rows_received=rows_received,
            rows_inserted=len(inserted_hashes),
            rows_skipped_exact_duplicate=exact_skipped,
            unknown_sensor_rows=sum(
                row.location_id in unknown_ids for row in observations
            ),
            unknown_sensor_ids=tuple(sorted(unknown_ids)),
            conflict_groups_detected=conflict_groups,
        )
