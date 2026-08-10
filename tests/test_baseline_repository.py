from types import SimpleNamespace
from unittest.mock import MagicMock

from backend.app.repositories.baseline_repository import BaselineRepository
from backend.app.services.baseline.historical_baseline_service import (
    ACTIVE_SENSOR_STATUS,
    ALL_LOCAL_EXCLUDED_LOCATION_IDS,
    HISTORICAL_MODELLING_LOCATION_TYPE,
    OBSERVED_UNRESOLVED_LOCATION_IDS,
    SENSOR_37_LOCAL_START_DATE,
    TRAINING_END_DATE,
    TRAINING_START_DATE,
)


def _repository() -> tuple[BaselineRepository, MagicMock, MagicMock]:
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value
    connection.execute.side_effect = [
        None,
        None,
        SimpleNamespace(rowcount=4700),
        SimpleNamespace(rowcount=48),
    ]
    return BaselineRepository(engine), engine, connection


def _rebuild(repository: BaselineRepository):
    return repository.rebuild_baselines(
        training_start=TRAINING_START_DATE,
        training_end=TRAINING_END_DATE,
        sensor_37_start=SENSOR_37_LOCAL_START_DATE,
        local_excluded_ids=ALL_LOCAL_EXCLUDED_LOCATION_IDS,
        unresolved_ids=OBSERVED_UNRESOLVED_LOCATION_IDS,
        location_type=HISTORICAL_MODELLING_LOCATION_TYPE,
        active_status=ACTIVE_SENSOR_STATUS,
    )


def test_rebuild_replaces_only_two_derived_tables_in_one_transaction() -> None:
    repository, engine, connection = _repository()

    result = _rebuild(repository)

    assert engine.begin.call_count == 1
    assert result.local_rows_written == 4700
    assert result.network_rows_written == 48
    statements = [str(call.args[0]) for call in connection.execute.call_args_list]
    assert statements[0].strip() == "DELETE FROM sensor_hour_daytype_baseline"
    assert statements[1].strip() == "DELETE FROM network_hour_daytype_baseline"
    assert all("pedestrian_hourly_count" not in statement for statement in statements[:2])


def test_local_sql_uses_exact_grouping_statistics_and_relocation_parameters() -> None:
    repository, _, connection = _repository()

    _rebuild(repository)

    statement = str(connection.execute.call_args_list[2].args[0])
    parameters = connection.execute.call_args_list[2].args[1]
    assert "GROUP BY h.location_id, h.hour_day, h.day_type" in statement
    assert statement.count("PERCENTILE_CONT") == 11
    assert "h.total_of_directions = 0" not in statement
    assert "h.location_id <> 37" in statement
    assert parameters["local_excluded_ids"] == ALL_LOCAL_EXCLUDED_LOCATION_IDS
    assert parameters["sensor_37_start"] == SENSOR_37_LOCAL_START_DATE


def test_network_sql_uses_raw_observations_and_retains_local_only_ids() -> None:
    repository, _, connection = _repository()

    _rebuild(repository)

    statement = str(connection.execute.call_args_list[3].args[0])
    parameters = connection.execute.call_args_list[3].args[1]
    assert "GROUP BY h.hour_day, h.day_type" in statement
    assert "GROUP BY h.location_id" not in statement
    assert "sensor_hour_daytype_baseline" not in statement
    assert parameters["unresolved_ids"] == OBSERVED_UNRESOLVED_LOCATION_IDS
    assert 47 not in parameters["unresolved_ids"]
    assert 181 not in parameters["unresolved_ids"]


def test_same_rebuild_operation_is_structurally_idempotent() -> None:
    repository, engine, connection = _repository()
    _rebuild(repository)
    connection.execute.side_effect = [
        None,
        None,
        SimpleNamespace(rowcount=4700),
        SimpleNamespace(rowcount=48),
    ]

    second = _rebuild(repository)

    assert engine.begin.call_count == 2
    assert second.local_rows_written == 4700
    assert second.network_rows_written == 48
