import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from backend.app.models.minute import (
    CurrentSensorDefinition,
    HistoricalPercentiles,
    MinuteObservation,
)
from backend.app.services.crowd.current_activity_service import (
    CurrentActivityService,
    calculate_windows,
    classify_crowd_level,
    classify_local_condition,
    empirical_cdf,
)


MELBOURNE = ZoneInfo("Australia/Melbourne")
CONFLICT_FIXTURE = (
    Path(__file__).parents[1]
    / "handoff"
    / "epic1_backend_handoff_v3"
    / "fixtures"
    / "minute_conflict_example.json"
)


class FakeHistoricalRepository:
    def __init__(self, scores=None):
        self.scores = scores or {}
        self.calls = []

    def calculate_historical_percentiles(self, counts, *, hour_day, day_type):
        self.calls.append((dict(counts), hour_day, day_type))
        return {
            location_id: self.scores.get(
                location_id, HistoricalPercentiles(network=50.0, local=50.0)
            )
            for location_id in counts
        }


def _sensor(location_id: int, location_type="Outdoor", status="A"):
    return CurrentSensorDefinition(location_id, location_type, status)


def _observation(location_id: int, sensed_at: datetime, count: int):
    local = sensed_at.astimezone(MELBOURNE)
    return MinuteObservation.create(
        location_id=location_id,
        source_sensing_datetime=sensed_at,
        sensing_date_local=local.date(),
        sensing_time_local=local.time().replace(tzinfo=None),
        direction_1=None,
        direction_2=None,
        total_of_directions=count,
    )


def _record(build, location_id):
    return next(row for row in build.records if row.location_id == location_id)


def test_exact_half_open_15_minute_window_and_network_empirical_cdf() -> None:
    as_of = datetime.fromisoformat("2026-08-10T10:44:00+10:00")
    windows = calculate_windows(as_of)
    observations = [
        _observation(1, windows.current_start, 0),
        _observation(2, windows.current_end - timedelta(minutes=1), 10),
        _observation(3, windows.current_end, 99),
    ]
    build = CurrentActivityService(FakeHistoricalRepository()).build(
        sensors=[_sensor(1), _sensor(2), _sensor(3)],
        observations=observations,
        as_of=as_of,
        source_latest_datetime=as_of - timedelta(minutes=1),
    )

    assert windows.current_end - windows.current_start == timedelta(minutes=15)
    assert _record(build, 1).current_15m_count == 0
    assert _record(build, 1).current_15m_network_percentile == 50.0
    assert _record(build, 2).current_15m_network_percentile == 100.0
    assert _record(build, 3).data_state == "AMBIGUOUS_NO_RECORD"
    assert _record(build, 3).current_15m_count is None


def test_exact_duplicate_is_suppressed_without_becoming_a_conflict() -> None:
    as_of = datetime.fromisoformat("2026-08-10T10:44:00+10:00")
    sensed_at = calculate_windows(as_of).current_start
    observation = _observation(1, sensed_at, 4)
    build = CurrentActivityService(FakeHistoricalRepository()).build(
        sensors=[_sensor(1)],
        observations=[observation, observation],
        as_of=as_of,
        source_latest_datetime=as_of - timedelta(minutes=1),
    )

    assert build.conflict_group_count == 0
    assert _record(build, 1).current_15m_observed_rows == 1
    assert _record(build, 1).current_15m_count == 4


def test_provided_conflicting_duplicate_is_retained_but_excluded_from_score() -> None:
    raw = json.loads(CONFLICT_FIXTURE.read_text(encoding="utf-8"))["records"]
    observations = []
    for source in raw:
        sensed_at = datetime.fromisoformat(
            source["Sensing_DateTime"].replace("Z", "+00:00")
        )
        observations.append(
            MinuteObservation.create(
                location_id=source["Location_ID"],
                source_sensing_datetime=sensed_at,
                sensing_date_local=datetime.fromisoformat(
                    source["Sensing_Date"]
                ).date(),
                sensing_time_local=datetime.strptime(
                    source["Sensing_Time"], "%H:%M:%S"
                ).time(),
                direction_1=source["Direction_1"],
                direction_2=source["Direction_2"],
                total_of_directions=source["Total_of_Directions"],
            )
        )
    as_of = datetime.fromisoformat("2026-08-10T10:44:00+10:00")
    build = CurrentActivityService(FakeHistoricalRepository()).build(
        sensors=[_sensor(11)],
        observations=observations,
        as_of=as_of,
        source_latest_datetime=as_of - timedelta(minutes=1),
    )

    assert build.conflict_group_count == 1
    assert _record(build, 11).data_state == "CONFLICTED"
    assert _record(build, 11).current_15m_count is None
    assert _record(build, 11).current_crowd_exposure_score is None


def test_outdoor_active_eligibility_and_no_record_are_explicit() -> None:
    as_of = datetime.fromisoformat("2026-08-10T10:44:00+10:00")
    build = CurrentActivityService(FakeHistoricalRepository()).build(
        sensors=[
            _sensor(1),
            _sensor(2, "Indoor", "A"),
            _sensor(3, "Outdoor", "I"),
        ],
        observations=[],
        as_of=as_of,
        source_latest_datetime=as_of - timedelta(minutes=1),
    )

    assert _record(build, 1).data_state == "AMBIGUOUS_NO_RECORD"
    assert _record(build, 1).current_15m_count is None
    assert _record(build, 2).data_state == "NO_DATA"
    assert _record(build, 3).data_state == "NO_DATA"
    assert build.eligible_sensor_count == 1


def test_configured_source_staleness_nulls_live_score() -> None:
    as_of = datetime.fromisoformat("2026-08-10T10:44:00+10:00")
    sensed_at = calculate_windows(as_of).current_start
    build = CurrentActivityService(
        FakeHistoricalRepository(), stale_threshold_minutes=10
    ).build(
        sensors=[_sensor(1)],
        observations=[_observation(1, sensed_at, 4)],
        as_of=as_of,
        source_latest_datetime=as_of - timedelta(minutes=30),
    )

    assert _record(build, 1).data_state == "STALE"
    assert _record(build, 1).current_15m_count is None
    assert build.source_freshness_minutes == 30.0


def test_unconfigured_stale_sla_does_not_invent_sensor_gap_threshold() -> None:
    as_of = datetime.fromisoformat("2026-08-10T10:44:00+10:00")
    build = CurrentActivityService(
        FakeHistoricalRepository(), stale_threshold_minutes=None
    ).build(
        sensors=[_sensor(1)],
        observations=[],
        as_of=as_of,
        source_latest_datetime=as_of - timedelta(hours=6),
    )
    assert _record(build, 1).data_state == "AMBIGUOUS_NO_RECORD"


def test_complete_previous_hour_uses_exact_hour_daytype_and_dual_history() -> None:
    as_of = datetime.fromisoformat("2026-08-10T11:44:00+10:00")
    windows = calculate_windows(as_of)
    observations = [
        _observation(14, windows.comparison_start + timedelta(minutes=i), 1)
        for i in range(60)
    ]
    observations.append(_observation(14, windows.current_start, 5))
    repository = FakeHistoricalRepository(
        {14: HistoricalPercentiles(network=40.0, local=91.0)}
    )
    build = CurrentActivityService(repository).build(
        sensors=[_sensor(14)],
        observations=observations,
        as_of=as_of,
        source_latest_datetime=as_of - timedelta(minutes=1),
    )
    record = _record(build, 14)

    assert build.comparison_hour_complete
    assert repository.calls == [({14: 60}, 10, "Weekday")]
    assert record.current_1h_count == 60
    assert record.current_1h_network_historical_percentile == 40.0
    assert record.current_1h_local_historical_percentile == 91.0
    assert record.current_local_condition == "MUCH_BUSIER_THAN_USUAL"


def test_47_and_181_keep_current_activity_without_local_history() -> None:
    as_of = datetime.fromisoformat("2026-08-10T11:44:00+10:00")
    windows = calculate_windows(as_of)
    observations = []
    for location_id in (47, 181):
        observations.extend(
            _observation(
                location_id,
                windows.comparison_start + timedelta(minutes=i),
                1,
            )
            for i in range(60)
        )
        observations.append(_observation(location_id, windows.current_start, 3))
    repository = FakeHistoricalRepository(
        {
            47: HistoricalPercentiles(network=30.0, local=None),
            181: HistoricalPercentiles(network=30.0, local=None),
        }
    )
    build = CurrentActivityService(repository).build(
        sensors=[_sensor(47), _sensor(181)],
        observations=observations,
        as_of=as_of,
        source_latest_datetime=as_of - timedelta(minutes=1),
    )

    for location_id in (47, 181):
        record = _record(build, location_id)
        assert record.data_state == "OK"
        assert record.current_15m_count == 3
        assert record.current_1h_network_historical_percentile == 30.0
        assert record.current_1h_local_historical_percentile is None
        assert record.current_local_condition is None


def test_dst_window_is_fifteen_elapsed_minutes_without_hardcoded_utc_offset() -> None:
    as_of = datetime.fromisoformat("2026-10-04T03:07:00+11:00")
    windows = calculate_windows(as_of)
    assert windows.current_end - windows.current_start == timedelta(minutes=15)
    assert windows.current_end.astimezone(MELBOURNE).isoformat().startswith(
        "2026-10-04T03:00:00+11:00"
    )


def test_percentile_and_internal_category_boundaries() -> None:
    assert empirical_cdf(10, [0, 10, 10, 20]) == 75.0
    assert [classify_crowd_level(value) for value in (25, 50, 75, 90, 91)] == [
        "VERY_LOW",
        "LOW",
        "MODERATE",
        "HIGH",
        "VERY_HIGH",
    ]
    assert [
        classify_local_condition(value) for value in (25, 50, 75, 90, 91)
    ] == [
        "MUCH_QUIETER_THAN_USUAL",
        "QUIETER_THAN_USUAL",
        "TYPICAL",
        "BUSIER_THAN_USUAL",
        "MUCH_BUSIER_THAN_USUAL",
    ]


def test_same_snapshot_and_as_of_produce_same_logical_current_records() -> None:
    as_of = datetime.fromisoformat("2026-08-10T10:44:00+10:00")
    calculated_at = datetime.fromisoformat("2026-08-10T00:45:00+00:00")
    observation = _observation(1, calculate_windows(as_of).current_start, 4)
    service = CurrentActivityService(FakeHistoricalRepository())
    arguments = {
        "sensors": [_sensor(1), _sensor(2)],
        "observations": [observation],
        "as_of": as_of,
        "source_latest_datetime": as_of - timedelta(minutes=1),
        "calculated_at": calculated_at,
    }

    first = service.build(**arguments)
    second = service.build(**arguments)

    assert first.records == second.records
