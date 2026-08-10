"""Persistence and exact hourly-reference lookup for current sensor activity."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
import json

from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from ..db.connection import get_database_engine
from ..db.exceptions import DatabaseQueryError, DatabaseWriteError
from ..models.minute import (
    CurrentSensorActivityRecord,
    CurrentSensorDefinition,
    HistoricalPercentiles,
)
from ..services.baseline.historical_baseline_service import (
    ACTIVE_SENSOR_STATUS,
    ALL_LOCAL_EXCLUDED_LOCATION_IDS,
    HISTORICAL_MODELLING_LOCATION_TYPE,
    OBSERVED_UNRESOLVED_LOCATION_IDS,
    SENSOR_37_LOCAL_START_DATE,
    TRAINING_END_DATE,
    TRAINING_START_DATE,
)


_HISTORICAL_PERCENTILES = text(
    """
    WITH current_values AS (
        SELECT location_id, current_count
        FROM JSONB_TO_RECORDSET(CAST(:current_values AS JSONB))
            AS x(location_id BIGINT, current_count BIGINT)
    ),
    eligible_history AS (
        SELECT h.location_id, h.sensing_date, h.total_of_directions
        FROM pedestrian_hourly_count h
        JOIN sensor_location_current sl USING (location_id)
        WHERE h.sensing_date BETWEEN :training_start AND :training_end
          AND h.hour_day = :hour_day
          AND h.day_type = :day_type
          AND LOWER(BTRIM(sl.location_type)) = :location_type
          AND UPPER(BTRIM(COALESCE(sl.status, ''))) = :active_status
    ),
    network_reference AS (
        SELECT total_of_directions
        FROM eligible_history
        WHERE location_id <> ALL(CAST(:network_excluded_ids AS BIGINT[]))
    ),
    local_reference AS (
        SELECT location_id, total_of_directions
        FROM eligible_history
        WHERE location_id <> ALL(CAST(:local_excluded_ids AS BIGINT[]))
          AND (location_id <> 37 OR sensing_date >= :sensor_37_start)
    ),
    network_score AS (
        SELECT
            c.location_id,
            CASE WHEN COUNT(n.total_of_directions) = 0 THEN NULL
                 ELSE 100.0 * COUNT(n.total_of_directions) FILTER (
                     WHERE n.total_of_directions <= c.current_count
                 ) / COUNT(n.total_of_directions)
            END AS percentile
        FROM current_values c
        LEFT JOIN network_reference n ON TRUE
        GROUP BY c.location_id, c.current_count
    ),
    local_score AS (
        SELECT
            c.location_id,
            CASE WHEN COUNT(l.total_of_directions) = 0 THEN NULL
                 ELSE 100.0 * COUNT(l.total_of_directions) FILTER (
                     WHERE l.total_of_directions <= c.current_count
                 ) / COUNT(l.total_of_directions)
            END AS percentile
        FROM current_values c
        LEFT JOIN local_reference l ON l.location_id = c.location_id
        GROUP BY c.location_id, c.current_count
    )
    SELECT
        c.location_id,
        n.percentile AS network_percentile,
        l.percentile AS local_percentile
    FROM current_values c
    LEFT JOIN network_score n USING (location_id)
    LEFT JOIN local_score l USING (location_id)
    ORDER BY c.location_id
    """
)


_REPLACE_CURRENT = text(
    """
    INSERT INTO current_sensor_activity (
        location_id,
        current_15m_window_start,
        current_15m_window_end,
        current_15m_observed_rows,
        current_15m_count,
        current_15m_network_percentile,
        current_crowd_exposure_score,
        current_crowd_level,
        comparison_hour_start,
        current_1h_observed_rows,
        current_1h_count,
        current_1h_network_historical_percentile,
        current_1h_local_historical_percentile,
        current_local_condition,
        data_state,
        calculated_at
    ) VALUES (
        :location_id,
        :current_15m_window_start,
        :current_15m_window_end,
        :current_15m_observed_rows,
        :current_15m_count,
        :current_15m_network_percentile,
        :current_crowd_exposure_score,
        :current_crowd_level,
        :comparison_hour_start,
        :current_1h_observed_rows,
        :current_1h_count,
        :current_1h_network_historical_percentile,
        :current_1h_local_historical_percentile,
        :current_local_condition,
        :data_state,
        :calculated_at
    )
    """
)


@dataclass(frozen=True)
class CurrentActivityVerification:
    row_count: int
    duplicate_location_count: int
    orphan_location_count: int
    negative_count_rows: int
    invalid_window_rows: int
    invalid_window_length_rows: int
    ambiguous_numeric_count_rows: int
    ineligible_scored_rows: int
    spatial_cache_row_count: int
    logical_checksum: str

    @property
    def ok(self) -> bool:
        return (
            self.row_count > 0
            and self.duplicate_location_count == 0
            and self.orphan_location_count == 0
            and self.negative_count_rows == 0
            and self.invalid_window_rows == 0
            and self.invalid_window_length_rows == 0
            and self.ambiguous_numeric_count_rows == 0
            and self.ineligible_scored_rows == 0
            and self.spatial_cache_row_count == 0
        )


class CurrentActivityRepository:
    def __init__(self, engine: Engine | None = None) -> None:
        self.engine = engine

    def load_current_sensors(self) -> tuple[CurrentSensorDefinition, ...]:
        try:
            database_engine = self.engine or get_database_engine()
            with database_engine.connect() as connection:
                rows = connection.execute(
                    text(
                        """
                        SELECT location_id, location_type, status
                        FROM sensor_location_current
                        ORDER BY location_id
                        """
                    )
                )
                return tuple(
                    CurrentSensorDefinition(
                        location_id=int(row.location_id),
                        location_type=str(row.location_type),
                        status=row.status,
                    )
                    for row in rows
                )
        except SQLAlchemyError:
            raise DatabaseQueryError(
                "Unable to load authoritative current sensor definitions."
            ) from None

    def calculate_historical_percentiles(
        self,
        counts: Mapping[int, int],
        *,
        hour_day: int,
        day_type: str,
    ) -> dict[int, HistoricalPercentiles]:
        if not counts:
            return {}
        payload = json.dumps(
            [
                {"location_id": location_id, "current_count": current_count}
                for location_id, current_count in sorted(counts.items())
            ]
        )
        parameters = {
            "current_values": payload,
            "training_start": TRAINING_START_DATE,
            "training_end": TRAINING_END_DATE,
            "hour_day": hour_day,
            "day_type": day_type,
            "location_type": HISTORICAL_MODELLING_LOCATION_TYPE.casefold(),
            "active_status": ACTIVE_SENSOR_STATUS,
            "network_excluded_ids": list(OBSERVED_UNRESOLVED_LOCATION_IDS),
            "local_excluded_ids": list(ALL_LOCAL_EXCLUDED_LOCATION_IDS),
            "sensor_37_start": SENSOR_37_LOCAL_START_DATE,
        }
        try:
            database_engine = self.engine or get_database_engine()
            with database_engine.connect() as connection:
                rows = connection.execute(
                    _HISTORICAL_PERCENTILES, parameters
                ).mappings()
                return {
                    int(row["location_id"]): HistoricalPercentiles(
                        network=(
                            None
                            if row["network_percentile"] is None
                            else float(row["network_percentile"])
                        ),
                        local=(
                            None
                            if row["local_percentile"] is None
                            else float(row["local_percentile"])
                        ),
                    )
                    for row in rows
                }
        except SQLAlchemyError:
            raise DatabaseQueryError(
                "Unable to calculate exact historical empirical CDF values."
            ) from None

    def replace_current_activity(
        self, records: Sequence[CurrentSensorActivityRecord]
    ) -> int:
        try:
            database_engine = self.engine or get_database_engine()
            with database_engine.begin() as connection:
                connection.execute(text("DELETE FROM current_sensor_activity"))
                if records:
                    connection.execute(
                        _REPLACE_CURRENT,
                        [record.__dict__ for record in records],
                    )
        except SQLAlchemyError:
            raise DatabaseWriteError(
                "Current activity replacement failed; the derived table was "
                "rolled back to its prior state."
            ) from None
        return len(records)

    def inspect_current_activity(self) -> CurrentActivityVerification:
        try:
            database_engine = self.engine or get_database_engine()
            with database_engine.connect() as connection:
                row = connection.execute(
                    text(
                        """
                        SELECT
                            (SELECT COUNT(*) FROM current_sensor_activity)
                                AS row_count,
                            (SELECT COUNT(*) FROM (
                                SELECT location_id
                                FROM current_sensor_activity
                                GROUP BY location_id HAVING COUNT(*) > 1
                            ) d) AS duplicate_location_count,
                            (SELECT COUNT(*)
                             FROM current_sensor_activity a
                             LEFT JOIN sensor s USING (location_id)
                             WHERE s.location_id IS NULL) AS orphan_location_count,
                            (SELECT COUNT(*) FROM current_sensor_activity
                             WHERE current_15m_count < 0 OR current_1h_count < 0)
                                AS negative_count_rows,
                            (SELECT COUNT(*) FROM current_sensor_activity
                             WHERE current_15m_window_start >= current_15m_window_end)
                                AS invalid_window_rows,
                            (SELECT COUNT(*) FROM current_sensor_activity
                             WHERE current_15m_window_end
                                   - current_15m_window_start
                                   <> INTERVAL '15 minutes')
                                AS invalid_window_length_rows,
                            (SELECT COUNT(*) FROM current_sensor_activity
                             WHERE data_state IN (
                                'AMBIGUOUS_NO_RECORD', 'STALE', 'CONFLICTED'
                             )
                               AND (current_15m_count IS NOT NULL
                                 OR current_15m_network_percentile IS NOT NULL
                                 OR current_crowd_exposure_score IS NOT NULL))
                                AS ambiguous_numeric_count_rows,
                            (SELECT COUNT(*)
                             FROM current_sensor_activity a
                             JOIN sensor_location_current sl USING (location_id)
                             WHERE (LOWER(BTRIM(sl.location_type)) <> 'outdoor'
                                OR UPPER(BTRIM(COALESCE(sl.status, ''))) <> 'A')
                               AND (a.current_15m_count IS NOT NULL
                                 OR a.current_crowd_exposure_score IS NOT NULL))
                                AS ineligible_scored_rows,
                            (SELECT COUNT(*) FROM spatial_activity_cache)
                                AS spatial_cache_row_count,
                            (SELECT MD5(COALESCE(STRING_AGG(payload, ',' ORDER BY payload), ''))
                             FROM (
                                SELECT JSONB_BUILD_ARRAY(
                                    location_id, current_15m_window_start,
                                    current_15m_window_end,
                                    current_15m_observed_rows, current_15m_count,
                                    current_15m_network_percentile,
                                    current_crowd_exposure_score,
                                    current_crowd_level, comparison_hour_start,
                                    current_1h_observed_rows, current_1h_count,
                                    current_1h_network_historical_percentile,
                                    current_1h_local_historical_percentile,
                                    current_local_condition, data_state
                                )::TEXT AS payload
                                FROM current_sensor_activity
                             ) values_to_hash) AS logical_checksum
                        """
                    )
                ).mappings().one()
        except SQLAlchemyError:
            raise DatabaseQueryError(
                "Current sensor activity verification failed."
            ) from None
        return CurrentActivityVerification(
            row_count=int(row["row_count"]),
            duplicate_location_count=int(row["duplicate_location_count"]),
            orphan_location_count=int(row["orphan_location_count"]),
            negative_count_rows=int(row["negative_count_rows"]),
            invalid_window_rows=int(row["invalid_window_rows"]),
            invalid_window_length_rows=int(row["invalid_window_length_rows"]),
            ambiguous_numeric_count_rows=int(row["ambiguous_numeric_count_rows"]),
            ineligible_scored_rows=int(row["ineligible_scored_rows"]),
            spatial_cache_row_count=int(row["spatial_cache_row_count"]),
            logical_checksum=str(row["logical_checksum"]),
        )
