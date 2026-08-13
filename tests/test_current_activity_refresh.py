from datetime import datetime, timedelta, timezone
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine as sqlalchemy_create_engine, event
from sqlalchemy.pool import QueuePool

from backend.app.db.connection import create_database_engine
from backend.app.models.minute import CurrentSensorDefinition, MinuteObservation
from backend.app.repositories.minute_repository import MinuteWriteResult
from backend.app.services.crowd.current_activity_service import (
    CurrentActivityService,
)
from backend.app.services.ingestion.current_activity_refresh import (
    CurrentActivityRefreshService,
    NoCompleteSourceWindowError,
    select_latest_complete_source_window,
)
from backend.app.services.ingestion.city_minute_client import CityMinuteSnapshot


AS_OF = datetime.fromisoformat("2026-08-10T10:44:00+10:00")
REAL_AS_OF = datetime.fromisoformat("2026-08-13T12:02:00+10:00")
MELBOURNE = ZoneInfo("Australia/Melbourne")
MINUTE_FIELDS = (
    "direction_1",
    "direction_2",
    "location_id",
    "sensing_date",
    "sensing_datetime",
    "sensing_time",
    "total_of_directions",
)


def _source_record(sensed_at: datetime, *, location_id: int = 1) -> dict:
    local = sensed_at.astimezone(MELBOURNE)
    return {
        "location_id": location_id,
        "sensing_datetime": sensed_at.isoformat(),
        "sensing_date": local.date().isoformat(),
        "sensing_time": local.time().replace(tzinfo=None).isoformat(),
        "direction_1": 1,
        "direction_2": 2,
        "total_of_directions": 3,
    }


def _observation(sensed_at: datetime, *, location_id: int = 1):
    local = sensed_at.astimezone(MELBOURNE)
    return MinuteObservation.create(
        location_id=location_id,
        source_sensing_datetime=sensed_at,
        sensing_date_local=local.date(),
        sensing_time_local=local.time().replace(tzinfo=None),
        direction_1=1,
        direction_2=2,
        total_of_directions=3,
    )


def _snapshot(
    records,
    *,
    start: datetime,
    end: datetime,
    metadata_latest: datetime | None = None,
) -> CityMinuteSnapshot:
    requested = tuple(records)
    return CityMinuteSnapshot(
        requested_start=start,
        requested_end=end,
        total_count=len(requested),
        records=requested,
        observed_fields=MINUTE_FIELDS,
        source_minimum_datetime=start,
        source_latest_datetime=metadata_latest,
        source_records_before_end=len(requested),
        fetched_at=datetime.now(timezone.utc),
    )


class SnapshotClient:
    def __init__(self) -> None:
        self.calls = 0

    def fetch_snapshot(self, *, start: datetime, end: datetime):
        self.calls += 1
        first = datetime.fromisoformat("2026-08-10T10:00:00+10:00")
        records = (
            *(
                _source_record(first + timedelta(minutes=offset))
                for offset in range(15)
            ),
            _source_record(first + timedelta(minutes=29)),
        )
        return _snapshot(
            records,
            start=start,
            end=end,
            metadata_latest=first + timedelta(minutes=29),
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


class MemoryMinuteRepository:
    def __init__(self) -> None:
        self.observations = ()
        self.ingest_calls = 0

    def find_unknown_sensor_ids(self, location_ids):
        return set()

    def ingest(self, observations, **arguments):
        self.ingest_calls += 1
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
        return self.observations


class EmptyHistoricalRepository:
    def calculate_historical_percentiles(self, counts, *, hour_day, day_type):
        return {}


def _refresh_service(records, *, metadata_latest=None):
    client = MagicMock()
    window_start = datetime.fromisoformat("2026-08-13T11:00:00+10:00")
    window_end = datetime.fromisoformat("2026-08-13T12:00:00+10:00")
    client.fetch_snapshot.return_value = _snapshot(
        records,
        start=window_start,
        end=window_end,
        metadata_latest=metadata_latest,
    )
    minute_repository = MemoryMinuteRepository()
    current_repository = MagicMock()
    current_repository.load_current_sensors.return_value = (
        CurrentSensorDefinition(1, "Outdoor", "A"),
        CurrentSensorDefinition(2, "Outdoor", "A"),
    )
    current_repository.replace_current_activity.side_effect = len
    service = CurrentActivityRefreshService(
        client=client,
        minute_repository=minute_repository,
        current_repository=current_repository,
        activity_service=CurrentActivityService(EmptyHistoricalRepository()),
    )
    return service, client, minute_repository, current_repository


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


@pytest.mark.parametrize(
    ("latest_time", "complete_start", "expected_start"),
    [
        ("11:25", "11:00", "11:00"),
        ("11:29", "11:00", "11:00"),
        ("11:30", "11:15", "11:15"),
        ("11:34", "11:15", "11:15"),
        ("11:44", "11:15", "11:15"),
        ("11:45", "11:30", "11:30"),
    ],
)
def test_source_window_uses_exact_completed_quarter_boundaries(
    latest_time: str,
    complete_start: str,
    expected_start: str,
) -> None:
    complete = datetime.fromisoformat(
        f"2026-08-13T{complete_start}:00+10:00"
    )
    latest = datetime.fromisoformat(
        f"2026-08-13T{latest_time}:00+10:00"
    )
    observations = [
        _observation(complete + timedelta(minutes=offset))
        for offset in range(15)
    ]
    if all(row.source_sensing_datetime != latest for row in observations):
        observations.append(_observation(latest))

    selected = select_latest_complete_source_window(
        tuple(observations),
        snapshot_start=datetime.fromisoformat(
            "2026-08-13T11:00:00+10:00"
        ),
        snapshot_end=datetime.fromisoformat(
            "2026-08-13T12:00:00+10:00"
        ),
        timezone_name="Australia/Melbourne",
        window_minutes=15,
    )

    expected = datetime.fromisoformat(
        f"2026-08-13T{expected_start}:00+10:00"
    )
    assert selected.start == expected
    assert selected.end == expected + timedelta(minutes=15)
    assert selected.distinct_minute_count == 15
    assert selected.complete_windows_considered == 1
    assert selected.incomplete_windows_skipped == 0


def test_source_window_skips_global_gap_and_uses_previous_complete_quarter(
) -> None:
    first = datetime.fromisoformat("2026-08-13T11:00:00+10:00")
    observations = tuple(
        _observation(first + timedelta(minutes=offset))
        for offset in range(35)
        if offset != 22
    )

    selected = select_latest_complete_source_window(
        observations,
        snapshot_start=first,
        snapshot_end=datetime.fromisoformat(
            "2026-08-13T12:00:00+10:00"
        ),
        timezone_name="Australia/Melbourne",
        window_minutes=15,
    )

    assert selected.start == first
    assert selected.end == first + timedelta(minutes=15)
    assert selected.incomplete_windows_skipped == 1
    assert selected.complete_windows_considered == 1


def test_real_lag_fixture_selects_source_window_and_materialises_live_sensor(
    caplog,
) -> None:
    first = datetime.fromisoformat("2026-08-13T11:00:00+10:00")
    records = tuple(
        _source_record(first + timedelta(minutes=offset))
        for offset in range(35)
    )
    service, client, minute_repository, current_repository = _refresh_service(
        records,
        metadata_latest=first + timedelta(minutes=34),
    )

    with caplog.at_level(
        logging.INFO,
        logger="backend.app.services.ingestion.current_activity_refresh",
    ):
        result = service.refresh(as_of=REAL_AS_OF, dry_run=False)

    assert result.selected_window_start == first + timedelta(minutes=15)
    assert result.selected_window_end == first + timedelta(minutes=30)
    assert result.selected_window_distinct_minutes == 15
    assert result.source_observation_maximum == first + timedelta(minutes=34)
    assert result.source_lag_seconds == 28 * 60
    assert result.activity.windows.current_start == result.selected_window_start
    assert result.activity.windows.current_end == result.selected_window_end
    assert result.activity.windows.comparison_start == first
    records_by_id = {row.location_id: row for row in result.activity.records}
    assert records_by_id[1].data_state == "OK"
    assert records_by_id[1].current_15m_observed_rows == 15
    assert records_by_id[1].current_15m_count == 45
    assert records_by_id[2].data_state == "AMBIGUOUS_NO_RECORD"
    assert records_by_id[2].current_15m_count is None
    assert minute_repository.ingest_calls == 1
    assert len(minute_repository.observations) == 35
    client.fetch_snapshot.assert_called_once()
    current_repository.replace_current_activity.assert_called_once()
    assert "selected_window_distinct_minutes=15" in caplog.text
    assert "incomplete_windows_skipped=0" in caplog.text


def test_no_complete_window_preserves_existing_current_materialisation(
    caplog,
) -> None:
    first = datetime.fromisoformat("2026-08-13T11:00:00+10:00")
    records = tuple(
        _source_record(first + timedelta(minutes=offset))
        for offset in range(35)
        if offset not in {10, 22}
    )
    service, client, minute_repository, current_repository = _refresh_service(
        records,
        metadata_latest=first + timedelta(minutes=34),
    )

    with caplog.at_level(
        logging.ERROR,
        logger="backend.app.services.ingestion.current_activity_refresh",
    ):
        with pytest.raises(NoCompleteSourceWindowError):
            service.refresh(as_of=REAL_AS_OF, dry_run=False)

    client.fetch_snapshot.assert_called_once()
    assert minute_repository.ingest_calls == 0
    current_repository.load_current_sensors.assert_not_called()
    current_repository.replace_current_activity.assert_not_called()
    assert (
        "current_activity_refresh_failed "
        "refresh_stage=select_current_window "
        "exception_type=NoCompleteSourceWindowError"
    ) in caplog.text


def test_zero_valid_source_timestamps_preserves_current_materialisation() -> None:
    invalid = _source_record(
        datetime.fromisoformat("2026-08-13T11:45:00+10:00")
    )
    invalid["sensing_datetime"] = "not-a-valid-source-timestamp"
    service, client, minute_repository, current_repository = _refresh_service(
        (invalid,),
        metadata_latest=datetime.fromisoformat(
            "2026-08-13T11:45:00+10:00"
        ),
    )

    with pytest.raises(NoCompleteSourceWindowError):
        service.refresh(as_of=REAL_AS_OF, dry_run=False)

    client.fetch_snapshot.assert_called_once()
    assert minute_repository.ingest_calls == 0
    current_repository.replace_current_activity.assert_not_called()


def test_malformed_later_timestamp_cannot_establish_window_completeness() -> None:
    first = datetime.fromisoformat("2026-08-13T11:00:00+10:00")
    valid_records = [
        _source_record(first + timedelta(minutes=offset))
        for offset in range(15)
    ]
    valid_records.append(_source_record(first + timedelta(minutes=25)))
    malformed = _source_record(first + timedelta(minutes=45))
    malformed["sensing_datetime"] = "malformed-later-timestamp"
    service, client, _, _ = _refresh_service(
        (*valid_records, malformed),
        metadata_latest=first + timedelta(minutes=45),
    )

    result = service.refresh(as_of=REAL_AS_OF, dry_run=False)

    assert result.transform.invalid_record_count == 1
    assert result.source_observation_maximum == first + timedelta(minutes=25)
    assert result.selected_window_start == first
    assert result.selected_window_end == first + timedelta(minutes=15)
    client.fetch_snapshot.assert_called_once()


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
