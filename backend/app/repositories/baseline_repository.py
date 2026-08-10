"""PostgreSQL persistence and audits for frozen historical baselines."""

from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import Engine, bindparam, text
from sqlalchemy.exc import SQLAlchemyError

from ..db.connection import get_database_engine
from ..db.exceptions import DatabaseQueryError, DatabaseWriteError


_TRAINING_SUMMARY = text(
    """
    WITH training AS (
        SELECT
            h.location_id,
            h.sensing_date,
            h.hour_day,
            h.day_type,
            h.total_of_directions,
            sl.location_id IS NOT NULL AS has_authoritative_location,
            LOWER(BTRIM(COALESCE(sl.location_type, ''))) = :location_type
                AND UPPER(BTRIM(COALESCE(sl.status, ''))) = :active_status
                AS modelling_eligible,
            LOWER(BTRIM(COALESCE(sl.location_type, ''))) AS location_type,
            UPPER(BTRIM(COALESCE(sl.status, ''))) AS status
        FROM pedestrian_hourly_count h
        LEFT JOIN sensor_location_current sl USING (location_id)
        WHERE h.sensing_date BETWEEN :training_start AND :training_end
    )
    SELECT
        COUNT(*) AS total_training_rows,
        MIN(sensing_date) AS minimum_date,
        MAX(sensing_date) AS maximum_date,
        COUNT(DISTINCT sensing_date) AS distinct_date_count,
        COUNT(DISTINCT location_id) AS distinct_sensor_count,
        COUNT(DISTINCT hour_day) AS distinct_hour_count,
        COALESCE(
            ARRAY_AGG(DISTINCT day_type ORDER BY day_type),
            ARRAY[]::TEXT[]
        ) AS day_types,
        COUNT(*) FILTER (WHERE total_of_directions = 0) AS zero_count_rows,
        COUNT(*) FILTER (WHERE total_of_directions < 0) AS negative_count_rows,
        COUNT(*) FILTER (
            WHERE day_type <> CASE
                WHEN EXTRACT(ISODOW FROM sensing_date) < 6
                    THEN 'Weekday'
                ELSE 'Weekend'
            END
        ) AS day_type_mismatch_rows,
        COUNT(*) FILTER (WHERE location_type = 'outdoor') AS outdoor_rows,
        COUNT(*) FILTER (WHERE location_type = 'indoor') AS indoor_rows,
        COUNT(*) FILTER (
            WHERE has_authoritative_location AND status <> :active_status
        ) AS non_active_rows,
        COUNT(*) FILTER (WHERE NOT has_authoritative_location)
            AS unresolved_stored_rows,
        COALESCE(
            ARRAY_AGG(DISTINCT location_id ORDER BY location_id)
                FILTER (WHERE NOT has_authoritative_location),
            ARRAY[]::BIGINT[]
        ) AS unresolved_stored_ids,
        COUNT(DISTINCT location_id) FILTER (WHERE modelling_eligible)
            AS eligible_sensor_count,
        COUNT(*) FILTER (WHERE modelling_eligible)
            AS eligible_observation_count,
        COUNT(DISTINCT location_id) FILTER (
            WHERE modelling_eligible
              AND location_id NOT IN :local_excluded_ids
              AND (location_id <> 37 OR sensing_date >= :sensor_37_start)
        ) AS local_baseline_sensor_count,
        COUNT(*) FILTER (
            WHERE modelling_eligible
              AND location_id NOT IN :local_excluded_ids
              AND (location_id <> 37 OR sensing_date >= :sensor_37_start)
        ) AS local_observation_count,
        COUNT(*) FILTER (
            WHERE modelling_eligible AND location_id = 14
        ) AS sensor_14_observation_count,
        MIN(sensing_date) FILTER (
            WHERE modelling_eligible AND location_id = 14
        ) AS sensor_14_minimum_date,
        MAX(sensing_date) FILTER (
            WHERE modelling_eligible AND location_id = 14
        ) AS sensor_14_maximum_date,
        COUNT(*) FILTER (
            WHERE modelling_eligible
              AND location_id = 37
              AND sensing_date >= :sensor_37_start
        ) AS sensor_37_local_observation_count,
        MIN(sensing_date) FILTER (
            WHERE modelling_eligible
              AND location_id = 37
              AND sensing_date >= :sensor_37_start
        ) AS sensor_37_local_minimum_date,
        COUNT(*) FILTER (
            WHERE modelling_eligible
              AND location_id = 37
              AND sensing_date < :sensor_37_start
        ) AS sensor_37_local_excluded_rows,
        COUNT(*) FILTER (
            WHERE modelling_eligible AND location_id IN :local_excluded_ids
        ) AS relocation_local_excluded_rows
    FROM training
    """
).bindparams(
    bindparam("local_excluded_ids", expanding=True),
)


_DELETE_LOCAL_BASELINES = text("DELETE FROM sensor_hour_daytype_baseline")
_DELETE_NETWORK_BASELINES = text("DELETE FROM network_hour_daytype_baseline")


_INSERT_LOCAL_BASELINES = text(
    """
    INSERT INTO sensor_hour_daytype_baseline (
        location_id,
        hour_day,
        day_type,
        observation_count,
        mean_count,
        median_count,
        p10,
        p20,
        p25,
        p40,
        p50,
        p60,
        p75,
        p80,
        p90,
        p95,
        baseline_start_date,
        baseline_end_date,
        calculated_at
    )
    SELECT
        h.location_id,
        h.hour_day,
        h.day_type,
        COUNT(*) AS observation_count,
        AVG(h.total_of_directions)::DOUBLE PRECISION AS mean_count,
        PERCENTILE_CONT(0.50) WITHIN GROUP (
            ORDER BY h.total_of_directions
        )::DOUBLE PRECISION AS median_count,
        PERCENTILE_CONT(0.10) WITHIN GROUP (
            ORDER BY h.total_of_directions
        )::DOUBLE PRECISION AS p10,
        PERCENTILE_CONT(0.20) WITHIN GROUP (
            ORDER BY h.total_of_directions
        )::DOUBLE PRECISION AS p20,
        PERCENTILE_CONT(0.25) WITHIN GROUP (
            ORDER BY h.total_of_directions
        )::DOUBLE PRECISION AS p25,
        PERCENTILE_CONT(0.40) WITHIN GROUP (
            ORDER BY h.total_of_directions
        )::DOUBLE PRECISION AS p40,
        PERCENTILE_CONT(0.50) WITHIN GROUP (
            ORDER BY h.total_of_directions
        )::DOUBLE PRECISION AS p50,
        PERCENTILE_CONT(0.60) WITHIN GROUP (
            ORDER BY h.total_of_directions
        )::DOUBLE PRECISION AS p60,
        PERCENTILE_CONT(0.75) WITHIN GROUP (
            ORDER BY h.total_of_directions
        )::DOUBLE PRECISION AS p75,
        PERCENTILE_CONT(0.80) WITHIN GROUP (
            ORDER BY h.total_of_directions
        )::DOUBLE PRECISION AS p80,
        PERCENTILE_CONT(0.90) WITHIN GROUP (
            ORDER BY h.total_of_directions
        )::DOUBLE PRECISION AS p90,
        PERCENTILE_CONT(0.95) WITHIN GROUP (
            ORDER BY h.total_of_directions
        )::DOUBLE PRECISION AS p95,
        MIN(h.sensing_date) AS baseline_start_date,
        MAX(h.sensing_date) AS baseline_end_date,
        :calculated_at AS calculated_at
    FROM pedestrian_hourly_count h
    JOIN sensor_location_current sl USING (location_id)
    WHERE h.sensing_date BETWEEN :training_start AND :training_end
      AND LOWER(BTRIM(sl.location_type)) = :location_type
      AND UPPER(BTRIM(COALESCE(sl.status, ''))) = :active_status
      AND h.location_id NOT IN :local_excluded_ids
      AND (h.location_id <> 37 OR h.sensing_date >= :sensor_37_start)
    GROUP BY h.location_id, h.hour_day, h.day_type
    """
).bindparams(
    bindparam("local_excluded_ids", expanding=True),
)


_INSERT_NETWORK_BASELINES = text(
    """
    INSERT INTO network_hour_daytype_baseline (
        hour_day,
        day_type,
        observation_count,
        sensor_count,
        mean_count,
        median_count,
        p10,
        p20,
        p25,
        p40,
        p50,
        p60,
        p75,
        p80,
        p90,
        p95,
        baseline_start_date,
        baseline_end_date,
        calculated_at
    )
    SELECT
        h.hour_day,
        h.day_type,
        COUNT(*) AS observation_count,
        COUNT(DISTINCT h.location_id) AS sensor_count,
        AVG(h.total_of_directions)::DOUBLE PRECISION AS mean_count,
        PERCENTILE_CONT(0.50) WITHIN GROUP (
            ORDER BY h.total_of_directions
        )::DOUBLE PRECISION AS median_count,
        PERCENTILE_CONT(0.10) WITHIN GROUP (
            ORDER BY h.total_of_directions
        )::DOUBLE PRECISION AS p10,
        PERCENTILE_CONT(0.20) WITHIN GROUP (
            ORDER BY h.total_of_directions
        )::DOUBLE PRECISION AS p20,
        PERCENTILE_CONT(0.25) WITHIN GROUP (
            ORDER BY h.total_of_directions
        )::DOUBLE PRECISION AS p25,
        PERCENTILE_CONT(0.40) WITHIN GROUP (
            ORDER BY h.total_of_directions
        )::DOUBLE PRECISION AS p40,
        PERCENTILE_CONT(0.50) WITHIN GROUP (
            ORDER BY h.total_of_directions
        )::DOUBLE PRECISION AS p50,
        PERCENTILE_CONT(0.60) WITHIN GROUP (
            ORDER BY h.total_of_directions
        )::DOUBLE PRECISION AS p60,
        PERCENTILE_CONT(0.75) WITHIN GROUP (
            ORDER BY h.total_of_directions
        )::DOUBLE PRECISION AS p75,
        PERCENTILE_CONT(0.80) WITHIN GROUP (
            ORDER BY h.total_of_directions
        )::DOUBLE PRECISION AS p80,
        PERCENTILE_CONT(0.90) WITHIN GROUP (
            ORDER BY h.total_of_directions
        )::DOUBLE PRECISION AS p90,
        PERCENTILE_CONT(0.95) WITHIN GROUP (
            ORDER BY h.total_of_directions
        )::DOUBLE PRECISION AS p95,
        MIN(h.sensing_date) AS baseline_start_date,
        MAX(h.sensing_date) AS baseline_end_date,
        :calculated_at AS calculated_at
    FROM pedestrian_hourly_count h
    JOIN sensor_location_current sl USING (location_id)
    WHERE h.sensing_date BETWEEN :training_start AND :training_end
      AND LOWER(BTRIM(sl.location_type)) = :location_type
      AND UPPER(BTRIM(COALESCE(sl.status, ''))) = :active_status
      AND h.location_id NOT IN :unresolved_ids
    GROUP BY h.hour_day, h.day_type
    """
).bindparams(
    bindparam("unresolved_ids", expanding=True),
)


_BASELINE_VERIFICATION = text(
    """
    SELECT
        (SELECT COUNT(*) FROM sensor_hour_daytype_baseline)
            AS local_row_count,
        (SELECT COUNT(DISTINCT location_id)
         FROM sensor_hour_daytype_baseline) AS local_sensor_count,
        (SELECT COUNT(*) FROM network_hour_daytype_baseline)
            AS network_row_count,
        (SELECT COUNT(DISTINCT hour_day)
         FROM network_hour_daytype_baseline) AS network_hour_count,
        (SELECT COUNT(DISTINCT day_type)
         FROM network_hour_daytype_baseline) AS network_day_type_count,
        (SELECT COUNT(*) FROM (
            SELECT location_id, hour_day, day_type
            FROM sensor_hour_daytype_baseline
            GROUP BY location_id, hour_day, day_type
            HAVING COUNT(*) > 1
         ) duplicates) AS local_duplicate_key_count,
        (SELECT COUNT(*) FROM (
            SELECT hour_day, day_type
            FROM network_hour_daytype_baseline
            GROUP BY hour_day, day_type
            HAVING COUNT(*) > 1
         ) duplicates) AS network_duplicate_key_count,
        (SELECT COUNT(*)
         FROM sensor_hour_daytype_baseline
         WHERE observation_count <= 0) AS local_non_positive_support_count,
        (SELECT COUNT(*)
         FROM network_hour_daytype_baseline
         WHERE observation_count <= 0 OR sensor_count <= 0)
            AS network_non_positive_support_count,
        (SELECT COUNT(*)
         FROM sensor_hour_daytype_baseline
         WHERE baseline_start_date < :training_start
            OR baseline_end_date > :training_end)
            AS local_outside_window_count,
        (SELECT COUNT(*)
         FROM network_hour_daytype_baseline
         WHERE baseline_start_date < :training_start
            OR baseline_end_date > :training_end)
            AS network_outside_window_count,
        (SELECT COUNT(*)
         FROM sensor_hour_daytype_baseline
         WHERE location_id IN :local_excluded_ids)
            AS forbidden_local_sensor_count,
        (SELECT COUNT(*)
         FROM sensor_hour_daytype_baseline
         WHERE location_id = 37
           AND baseline_start_date < :sensor_37_start)
            AS sensor_37_pre_cutoff_count,
        (SELECT COUNT(*)
         FROM sensor_hour_daytype_baseline
         WHERE location_id = 14) AS sensor_14_baseline_rows,
        (SELECT COUNT(*)
         FROM sensor_hour_daytype_baseline
         WHERE location_id = 37) AS sensor_37_baseline_rows,
        (SELECT COUNT(*)
         FROM sensor_hour_daytype_baseline
         WHERE NOT (
             p10 <= p20 AND p20 <= p25 AND p25 <= p40
             AND p40 <= p50 AND p50 <= p60 AND p60 <= p75
             AND p75 <= p80 AND p80 <= p90 AND p90 <= p95
             AND ABS(median_count - p50) < 1e-9
             AND mean_count >= 0
         )) AS local_invalid_stat_order_count,
        (SELECT COUNT(*)
         FROM network_hour_daytype_baseline
         WHERE NOT (
             p10 <= p20 AND p20 <= p25 AND p25 <= p40
             AND p40 <= p50 AND p50 <= p60 AND p60 <= p75
             AND p75 <= p80 AND p80 <= p90 AND p90 <= p95
             AND ABS(median_count - p50) < 1e-9
             AND mean_count >= 0
         )) AS network_invalid_stat_order_count,
        (SELECT COUNT(*)
         FROM pedestrian_hourly_count h
         JOIN sensor_location_current sl USING (location_id)
         WHERE h.sensing_date BETWEEN :training_start AND :training_end
           AND LOWER(BTRIM(sl.location_type)) = :location_type
           AND UPPER(BTRIM(COALESCE(sl.status, ''))) = :active_status
           AND h.total_of_directions = 0) AS eligible_zero_count_rows,
        (SELECT MD5(COALESCE(STRING_AGG(payload, ',' ORDER BY payload), ''))
         FROM (
             SELECT JSONB_BUILD_ARRAY(
                 location_id, hour_day, day_type, observation_count,
                 mean_count, median_count, p10, p20, p25, p40, p50,
                 p60, p75, p80, p90, p95, baseline_start_date,
                 baseline_end_date
             )::TEXT AS payload
             FROM sensor_hour_daytype_baseline
         ) local_rows) AS local_logical_checksum,
        (SELECT MD5(COALESCE(STRING_AGG(payload, ',' ORDER BY payload), ''))
         FROM (
             SELECT JSONB_BUILD_ARRAY(
                 hour_day, day_type, observation_count, sensor_count,
                 mean_count, median_count, p10, p20, p25, p40, p50,
                 p60, p75, p80, p90, p95, baseline_start_date,
                 baseline_end_date
             )::TEXT AS payload
             FROM network_hour_daytype_baseline
         ) network_rows) AS network_logical_checksum
    """
).bindparams(
    bindparam("local_excluded_ids", expanding=True),
)


@dataclass(frozen=True)
class TrainingDataSummary:
    total_training_rows: int
    minimum_date: date | None
    maximum_date: date | None
    distinct_date_count: int
    distinct_sensor_count: int
    distinct_hour_count: int
    day_types: tuple[str, ...]
    zero_count_rows: int
    negative_count_rows: int
    day_type_mismatch_rows: int
    outdoor_rows: int
    indoor_rows: int
    non_active_rows: int
    unresolved_stored_rows: int
    unresolved_stored_ids: tuple[int, ...]
    eligible_sensor_count: int
    eligible_observation_count: int
    local_baseline_sensor_count: int
    local_observation_count: int
    sensor_14_observation_count: int
    sensor_14_minimum_date: date | None
    sensor_14_maximum_date: date | None
    sensor_37_local_observation_count: int
    sensor_37_local_minimum_date: date | None
    sensor_37_local_excluded_rows: int
    relocation_local_excluded_rows: int


@dataclass(frozen=True)
class BaselineWriteResult:
    local_rows_written: int
    network_rows_written: int
    calculated_at: datetime


@dataclass(frozen=True)
class BaselineVerification:
    local_row_count: int
    local_sensor_count: int
    network_row_count: int
    network_hour_count: int
    network_day_type_count: int
    local_duplicate_key_count: int
    network_duplicate_key_count: int
    local_non_positive_support_count: int
    network_non_positive_support_count: int
    local_outside_window_count: int
    network_outside_window_count: int
    forbidden_local_sensor_count: int
    sensor_37_pre_cutoff_count: int
    sensor_14_baseline_rows: int
    sensor_37_baseline_rows: int
    local_invalid_stat_order_count: int
    network_invalid_stat_order_count: int
    eligible_zero_count_rows: int
    local_logical_checksum: str
    network_logical_checksum: str

    @property
    def ok(self) -> bool:
        return (
            self.local_row_count > 0
            and self.local_sensor_count > 0
            and self.network_row_count == 48
            and self.network_hour_count == 24
            and self.network_day_type_count == 2
            and self.local_duplicate_key_count == 0
            and self.network_duplicate_key_count == 0
            and self.local_non_positive_support_count == 0
            and self.network_non_positive_support_count == 0
            and self.local_outside_window_count == 0
            and self.network_outside_window_count == 0
            and self.forbidden_local_sensor_count == 0
            and self.sensor_37_pre_cutoff_count == 0
            and self.sensor_14_baseline_rows > 0
            and self.sensor_37_baseline_rows > 0
            and self.local_invalid_stat_order_count == 0
            and self.network_invalid_stat_order_count == 0
            and self.eligible_zero_count_rows > 0
        )


class BaselineRepository:
    """Inspect source facts and transactionally replace derived baselines."""

    def __init__(self, engine: Engine | None = None) -> None:
        self.engine = engine

    def inspect_training_data(
        self,
        *,
        training_start: date,
        training_end: date,
        sensor_37_start: date,
        local_excluded_ids: tuple[int, ...],
        location_type: str,
        active_status: str,
    ) -> TrainingDataSummary:
        database_engine = self.engine or get_database_engine()
        parameters = {
            "training_start": training_start,
            "training_end": training_end,
            "sensor_37_start": sensor_37_start,
            "local_excluded_ids": local_excluded_ids,
            "location_type": location_type.lower(),
            "active_status": active_status.upper(),
        }
        try:
            with database_engine.connect() as connection:
                row = connection.execute(
                    _TRAINING_SUMMARY, parameters
                ).mappings().one()
        except SQLAlchemyError:
            raise DatabaseQueryError(
                "Historical training-data inspection failed."
            ) from None

        return TrainingDataSummary(
            total_training_rows=int(row["total_training_rows"]),
            minimum_date=row["minimum_date"],
            maximum_date=row["maximum_date"],
            distinct_date_count=int(row["distinct_date_count"]),
            distinct_sensor_count=int(row["distinct_sensor_count"]),
            distinct_hour_count=int(row["distinct_hour_count"]),
            day_types=tuple(row["day_types"]),
            zero_count_rows=int(row["zero_count_rows"]),
            negative_count_rows=int(row["negative_count_rows"]),
            day_type_mismatch_rows=int(row["day_type_mismatch_rows"]),
            outdoor_rows=int(row["outdoor_rows"]),
            indoor_rows=int(row["indoor_rows"]),
            non_active_rows=int(row["non_active_rows"]),
            unresolved_stored_rows=int(row["unresolved_stored_rows"]),
            unresolved_stored_ids=tuple(
                int(value) for value in row["unresolved_stored_ids"]
            ),
            eligible_sensor_count=int(row["eligible_sensor_count"]),
            eligible_observation_count=int(row["eligible_observation_count"]),
            local_baseline_sensor_count=int(
                row["local_baseline_sensor_count"]
            ),
            local_observation_count=int(row["local_observation_count"]),
            sensor_14_observation_count=int(
                row["sensor_14_observation_count"]
            ),
            sensor_14_minimum_date=row["sensor_14_minimum_date"],
            sensor_14_maximum_date=row["sensor_14_maximum_date"],
            sensor_37_local_observation_count=int(
                row["sensor_37_local_observation_count"]
            ),
            sensor_37_local_minimum_date=row[
                "sensor_37_local_minimum_date"
            ],
            sensor_37_local_excluded_rows=int(
                row["sensor_37_local_excluded_rows"]
            ),
            relocation_local_excluded_rows=int(
                row["relocation_local_excluded_rows"]
            ),
        )

    def rebuild_baselines(
        self,
        *,
        training_start: date,
        training_end: date,
        sensor_37_start: date,
        local_excluded_ids: tuple[int, ...],
        unresolved_ids: tuple[int, ...],
        location_type: str,
        active_status: str,
    ) -> BaselineWriteResult:
        database_engine = self.engine or get_database_engine()
        calculated_at = datetime.now(timezone.utc)
        common = {
            "training_start": training_start,
            "training_end": training_end,
            "sensor_37_start": sensor_37_start,
            "location_type": location_type.lower(),
            "active_status": active_status.upper(),
            "calculated_at": calculated_at,
        }
        try:
            with database_engine.begin() as connection:
                connection.execute(_DELETE_LOCAL_BASELINES)
                connection.execute(_DELETE_NETWORK_BASELINES)
                local_result = connection.execute(
                    _INSERT_LOCAL_BASELINES,
                    {**common, "local_excluded_ids": local_excluded_ids},
                )
                network_result = connection.execute(
                    _INSERT_NETWORK_BASELINES,
                    {**common, "unresolved_ids": unresolved_ids},
                )
        except SQLAlchemyError:
            raise DatabaseWriteError(
                "Historical baseline rebuild failed; both derived tables were "
                "rolled back together."
            ) from None

        return BaselineWriteResult(
            local_rows_written=int(local_result.rowcount),
            network_rows_written=int(network_result.rowcount),
            calculated_at=calculated_at,
        )

    def inspect_baselines(
        self,
        *,
        training_start: date,
        training_end: date,
        sensor_37_start: date,
        local_excluded_ids: tuple[int, ...],
        location_type: str,
        active_status: str,
    ) -> BaselineVerification:
        database_engine = self.engine or get_database_engine()
        parameters = {
            "training_start": training_start,
            "training_end": training_end,
            "sensor_37_start": sensor_37_start,
            "local_excluded_ids": local_excluded_ids,
            "location_type": location_type.lower(),
            "active_status": active_status.upper(),
        }
        try:
            with database_engine.connect() as connection:
                row = connection.execute(
                    _BASELINE_VERIFICATION, parameters
                ).mappings().one()
        except SQLAlchemyError:
            raise DatabaseQueryError(
                "Historical baseline verification failed."
            ) from None

        return BaselineVerification(
            local_row_count=int(row["local_row_count"]),
            local_sensor_count=int(row["local_sensor_count"]),
            network_row_count=int(row["network_row_count"]),
            network_hour_count=int(row["network_hour_count"]),
            network_day_type_count=int(row["network_day_type_count"]),
            local_duplicate_key_count=int(row["local_duplicate_key_count"]),
            network_duplicate_key_count=int(row["network_duplicate_key_count"]),
            local_non_positive_support_count=int(
                row["local_non_positive_support_count"]
            ),
            network_non_positive_support_count=int(
                row["network_non_positive_support_count"]
            ),
            local_outside_window_count=int(row["local_outside_window_count"]),
            network_outside_window_count=int(
                row["network_outside_window_count"]
            ),
            forbidden_local_sensor_count=int(row["forbidden_local_sensor_count"]),
            sensor_37_pre_cutoff_count=int(row["sensor_37_pre_cutoff_count"]),
            sensor_14_baseline_rows=int(row["sensor_14_baseline_rows"]),
            sensor_37_baseline_rows=int(row["sensor_37_baseline_rows"]),
            local_invalid_stat_order_count=int(
                row["local_invalid_stat_order_count"]
            ),
            network_invalid_stat_order_count=int(
                row["network_invalid_stat_order_count"]
            ),
            eligible_zero_count_rows=int(row["eligible_zero_count_rows"]),
            local_logical_checksum=str(row["local_logical_checksum"]),
            network_logical_checksum=str(row["network_logical_checksum"]),
        )
