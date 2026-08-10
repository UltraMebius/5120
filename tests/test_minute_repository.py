from datetime import datetime
import logging
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError, OperationalError

from backend.app.db.exceptions import DatabaseWriteError
from backend.app.models.minute import MinuteObservation
from backend.app.repositories.minute_repository import MinuteRepository


AS_OF = datetime.fromisoformat("2026-08-10T10:15:00+10:00")
PRIVATE_DETAIL = "sensitive database detail"


class _DriverFailure(Exception):
    def __init__(self, *, sqlstate: str) -> None:
        super().__init__(PRIVATE_DETAIL)
        self.sqlstate = sqlstate


def _observation() -> MinuteObservation:
    return MinuteObservation.create(
        location_id=1,
        source_sensing_datetime=AS_OF,
        sensing_date_local=AS_OF.date(),
        sensing_time_local=AS_OF.time().replace(tzinfo=None),
        direction_1=1,
        direction_2=2,
        total_of_directions=3,
    )


def _ingest(repository: MinuteRepository) -> None:
    repository.ingest(
        (_observation(),),
        source_name="test_source",
        rows_received=1,
        interval_start=AS_OF,
        interval_end=datetime.fromisoformat("2026-08-10T10:16:00+10:00"),
        metadata={},
    )


def test_write_integrity_error_logs_operation_type_and_sqlstate_only(
    caplog,
) -> None:
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value
    known_ids = MagicMock()
    known_ids.scalars.return_value = (1,)
    run_insert = MagicMock()
    run_insert.scalar_one.return_value = 7
    error = IntegrityError(
        "private SQL statement",
        {"private_parameter": PRIVATE_DETAIL},
        _DriverFailure(sqlstate="23505"),
    )
    connection.execute.side_effect = (known_ids, run_insert, error)
    repository = MinuteRepository(engine)

    with caplog.at_level(
        logging.ERROR,
        logger="backend.app.repositories.minute_repository",
    ):
        with pytest.raises(DatabaseWriteError):
            _ingest(repository)

    assert caplog.messages == [
        "database_operation=insert_raw_minute_observations "
        "db_exception_type=IntegrityError sqlstate=23505"
    ]
    assert PRIVATE_DETAIL not in caplog.text
    assert "private SQL statement" not in caplog.text
    assert caplog.records[0].exc_info is None


def test_non_integrity_error_does_not_log_driver_sqlstate_or_contents(
    caplog,
) -> None:
    engine = MagicMock()
    engine.begin.side_effect = OperationalError(
        "private SQL statement",
        {"private_parameter": PRIVATE_DETAIL},
        _DriverFailure(sqlstate="08006"),
    )
    repository = MinuteRepository(engine)

    with caplog.at_level(
        logging.ERROR,
        logger="backend.app.repositories.minute_repository",
    ):
        with pytest.raises(DatabaseWriteError):
            _ingest(repository)

    assert caplog.messages == [
        "database_operation=open_minute_ingestion_transaction "
        "db_exception_type=OperationalError"
    ]
    assert "sqlstate=" not in caplog.text
    assert PRIVATE_DETAIL not in caplog.text
    assert "private SQL statement" not in caplog.text
    assert caplog.records[0].exc_info is None
