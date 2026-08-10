from datetime import datetime, timezone
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine as sqlalchemy_create_engine, event
from sqlalchemy.pool import QueuePool

from backend.app.db.connection import create_database_engine
from backend.app.repositories.minute_repository import MinuteWriteResult
from backend.app.services.ingestion.current_activity_refresh import (
    CurrentActivityRefreshService,
)
from backend.app.services.ingestion.city_minute_client import CityMinuteSnapshot


AS_OF = datetime.fromisoformat("2026-08-10T10:44:00+10:00")


class SnapshotClient:
    def fetch_snapshot(self, *, start: datetime, end: datetime):
        return CityMinuteSnapshot(
            requested_start=start,
            requested_end=end,
            total_count=1,
            records=(
                {
                    "location_id": 1,
                    "sensing_datetime": "2026-08-10T10:15:00+10:00",
                    "sensing_date": "2026-08-10",
                    "sensing_time": "10:15:00",
                    "direction_1": 1,
                    "direction_2": 2,
                    "total_of_directions": 3,
                },
            ),
            observed_fields=(
                "direction_1",
                "direction_2",
                "location_id",
                "sensing_date",
                "sensing_datetime",
                "sensing_time",
                "total_of_directions",
            ),
            source_minimum_datetime=AS_OF,
            source_latest_datetime=AS_OF,
            source_records_before_end=1,
            fetched_at=datetime.now(timezone.utc),
        )


class EngineBackedMinuteRepository:
    def __init__(self, engine) -> None:
        self.engine = engine
        self.observations = ()

    def _checkout(self) -> None:
        with self.engine.connect():
            pass

    def find_unknown_sensor_ids(self, location_ids):
        self._checkout()
        return set()

    def ingest(self, observations, **arguments):
        self._checkout()
        self.observations = tuple(observations)
        return MinuteWriteResult(
            ingestion_run_id=1,
            rows_received=arguments["rows_received"],
            rows_inserted=len(self.observations),
            rows_skipped_exact_duplicate=0,
            unknown_sensor_rows=0,
            unknown_sensor_ids=(),
            conflict_groups_detected=0,
        )

    def load_observations(self, **arguments):
        self._checkout()
        return self.observations


class EngineBackedCurrentRepository:
    def __init__(self, engine) -> None:
        self.engine = engine

    def load_current_sensors(self):
        with self.engine.connect():
            return ()

    def replace_current_activity(self, records):
        with self.engine.begin():
            return len(records)


class EngineBackedActivityService:
    timezone_name = "Australia/Melbourne"
    window_minutes = 15

    def __init__(self, engine) -> None:
        self.engine = engine

    def build(self, **arguments):
        with self.engine.connect():
            return SimpleNamespace(records=())


def _sqlite_vercel_engine(_url, **options):
    return sqlalchemy_create_engine(
        "sqlite+pysqlite:///:memory:",
        poolclass=QueuePool,
        pool_pre_ping=options["pool_pre_ping"],
        pool_recycle=options["pool_recycle"],
        pool_size=options["pool_size"],
        max_overflow=options["max_overflow"],
        pool_timeout=0.05,
        connect_args={"check_same_thread": False},
    )


def test_refresh_path_completes_with_vercel_single_connection_pool(
    monkeypatch,
) -> None:
    monkeypatch.setenv("VERCEL", "1")
    with patch(
        "backend.app.db.connection.create_engine",
        side_effect=_sqlite_vercel_engine,
    ):
        engine = create_database_engine(
            "postgresql+psycopg://example-user:example-password@"
            "database.example.invalid/example?sslmode=require"
        )

    checkout_count = 0

    @event.listens_for(engine, "checkout")
    def count_checkout(*_arguments) -> None:
        nonlocal checkout_count
        checkout_count += 1

    try:
        service = CurrentActivityRefreshService(
            client=SnapshotClient(),
            minute_repository=EngineBackedMinuteRepository(engine),
            current_repository=EngineBackedCurrentRepository(engine),
            activity_service=EngineBackedActivityService(engine),
        )

        result = service.refresh(as_of=AS_OF, dry_run=False)

        assert result.current_rows_written == 0
        assert checkout_count == 6
        assert engine.pool.size() == 1
        assert engine.pool.checkedout() == 0
    finally:
        engine.dispose()


def test_refresh_diagnostic_logs_only_stage_and_exception_type(caplog) -> None:
    private_detail = "private connection and credential detail"
    client = MagicMock()
    client.fetch_snapshot.side_effect = RuntimeError(private_detail)
    activity_service = SimpleNamespace(
        timezone_name="Australia/Melbourne",
        window_minutes=15,
    )
    service = CurrentActivityRefreshService(
        client=client,
        minute_repository=MagicMock(),
        current_repository=MagicMock(),
        activity_service=activity_service,
    )

    with caplog.at_level(
        logging.ERROR,
        logger=(
            "backend.app.services.ingestion.current_activity_refresh"
        ),
    ):
        with pytest.raises(RuntimeError, match=private_detail):
            service.refresh(as_of=AS_OF, dry_run=False)

    assert (
        "current_activity_refresh_failed refresh_stage=fetch_pages "
        "exception_type=RuntimeError"
    ) in caplog.text
    assert private_detail not in caplog.text
