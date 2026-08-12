"""One-statement PostGIS lookup for many route pedestrian-flow samples."""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
import json
import math
from time import perf_counter

from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import SQLAlchemyError

from ..config import SETTINGS
from ..db.connection import get_database_engine
from ..db.exceptions import DatabaseQueryError
from ..models.pedestrian_flow import (
    FlowNeighbourhood,
    FlowNeighbourhoodBatch,
    FlowSamplePoint,
    PedestrianFlowSnapshot,
    SensorPedestrianFlow,
)


_BATCH_FLOW_NEIGHBOURHOODS = text(
    """
    WITH requested_samples AS (
        SELECT
            raw.route_index,
            raw.sample_index,
            raw.distance_along_route_meters,
            raw.longitude,
            raw.latitude,
            ST_SetSRID(
                ST_MakePoint(raw.longitude, raw.latitude), 4326
            )::geography AS geom
        FROM JSONB_TO_RECORDSET(CAST(:samples AS JSONB)) AS raw(
            route_index INTEGER,
            sample_index INTEGER,
            distance_along_route_meters DOUBLE PRECISION,
            longitude DOUBLE PRECISION,
            latitude DOUBLE PRECISION
        )
    ),
    current_snapshot AS (
        SELECT
            MIN(current_15m_window_start) AS window_start,
            MAX(current_15m_window_end) AS window_end,
            MAX(calculated_at) AS calculated_at,
            COUNT(DISTINCT JSONB_BUILD_ARRAY(
                current_15m_window_start,
                current_15m_window_end
            )) AS window_variant_count
        FROM current_sensor_activity
    ),
    time_context AS (
        SELECT
            window_start,
            window_end,
            calculated_at,
            window_variant_count,
            CASE
                WHEN window_start IS NULL THEN NULL
                ELSE EXTRACT(
                    HOUR FROM window_start AT TIME ZONE :timezone_name
                )::SMALLINT
            END AS baseline_hour_day,
            CASE
                WHEN window_start IS NULL THEN NULL
                WHEN EXTRACT(
                    ISODOW FROM window_start AT TIME ZONE :timezone_name
                ) BETWEEN 1 AND 5 THEN 'Weekday'
                ELSE 'Weekend'
            END AS baseline_day_type
        FROM current_snapshot
    )
    SELECT
        sample.route_index,
        sample.sample_index,
        sample.distance_along_route_meters,
        sample.longitude,
        sample.latitude,
        context.window_start AS snapshot_window_start,
        context.window_end AS snapshot_window_end,
        context.calculated_at AS snapshot_calculated_at,
        context.window_variant_count,
        context.baseline_hour_day AS context_hour_day,
        context.baseline_day_type AS context_day_type,
        location.location_id,
        location.location_type,
        location.status,
        CASE
            WHEN location.location_id IS NULL THEN NULL
            ELSE ST_Distance(location.geom, sample.geom)
        END AS distance_meters,
        activity.data_state,
        activity.current_15m_count,
        activity.current_15m_observed_rows,
        activity.current_15m_window_start,
        activity.current_15m_window_end,
        activity.calculated_at,
        baseline.hour_day AS baseline_hour_day,
        baseline.day_type AS baseline_day_type,
        baseline.observation_count AS baseline_observation_count,
        baseline.median_count AS baseline_median_count,
        baseline.mean_count AS baseline_mean_count,
        baseline.p75 AS baseline_p75_count,
        baseline.baseline_start_date,
        baseline.baseline_end_date
    FROM requested_samples sample
    CROSS JOIN time_context context
    LEFT JOIN sensor_location_current location
      ON ST_DWithin(location.geom, sample.geom, :maximum_radius_m)
    LEFT JOIN current_sensor_activity activity
      ON activity.location_id = location.location_id
    LEFT JOIN sensor_hour_daytype_baseline baseline
      ON baseline.location_id = location.location_id
     AND baseline.hour_day = context.baseline_hour_day
     AND baseline.day_type = context.baseline_day_type
    ORDER BY sample.route_index, sample.sample_index,
             distance_meters NULLS LAST, location.location_id
    """
)


def _optional_int(value: object) -> int | None:
    return None if value is None else int(value)


def _optional_float(value: object) -> float | None:
    return None if value is None else float(value)


class PedestrianFlowRepository:
    """Map multiple routes' samples to nearby flow evidence in one query."""

    def __init__(
        self,
        engine: Engine | None = None,
        *,
        connection: Connection | None = None,
    ) -> None:
        self.engine = engine
        self.connection = connection

    @contextmanager
    def _connect(self) -> Iterator[Connection]:
        if self.connection is not None:
            yield self.connection
            return
        database_engine = self.engine or get_database_engine()
        with database_engine.connect() as connection:
            yield connection

    @staticmethod
    def _validate_samples(samples: Sequence[FlowSamplePoint]) -> None:
        seen_keys: set[tuple[int, int]] = set()
        for sample in samples:
            if (
                isinstance(sample.route_index, bool)
                or not isinstance(sample.route_index, int)
                or sample.route_index < 0
            ):
                raise ValueError("route_index must be a non-negative integer")
            if (
                isinstance(sample.sample_index, bool)
                or not isinstance(sample.sample_index, int)
                or sample.sample_index < 0
            ):
                raise ValueError("sample_index must be a non-negative integer")
            numeric_values = (
                sample.distance_along_route_meters,
                sample.longitude,
                sample.latitude,
            )
            if any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                for value in numeric_values
            ):
                raise ValueError("sample distances and coordinates must be finite")
            if sample.distance_along_route_meters < 0.0:
                raise ValueError("sample distance must be non-negative")
            if not -180.0 <= sample.longitude <= 180.0:
                raise ValueError("sample longitude must be between -180 and 180")
            if not -90.0 <= sample.latitude <= 90.0:
                raise ValueError("sample latitude must be between -90 and 90")
            if sample.key in seen_keys:
                raise ValueError("route/sample keys must be unique within a batch")
            seen_keys.add(sample.key)

    def find_flow_neighbourhoods(
        self,
        samples: Sequence[FlowSamplePoint],
        *,
        maximum_radius_m: float = SETTINGS.spatial.max_support_radius_m,
    ) -> FlowNeighbourhoodBatch:
        """Return every requested sample using one connection and SQL execute."""

        requested = tuple(samples)
        self._validate_samples(requested)
        if not math.isfinite(maximum_radius_m) or maximum_radius_m <= 0.0:
            raise ValueError("maximum_radius_m must be finite and positive")
        empty_snapshot = PedestrianFlowSnapshot(None, None, None, 0, None, None)
        if not requested:
            return FlowNeighbourhoodBatch((), empty_snapshot, 0.0, 0)

        payload = json.dumps(
            [
                {
                    "route_index": sample.route_index,
                    "sample_index": sample.sample_index,
                    "distance_along_route_meters": (
                        sample.distance_along_route_meters
                    ),
                    "longitude": sample.longitude,
                    "latitude": sample.latitude,
                }
                for sample in requested
            ],
            separators=(",", ":"),
        )
        parameters = {
            "samples": payload,
            "maximum_radius_m": float(maximum_radius_m),
            "timezone_name": SETTINGS.app_timezone,
        }
        started = perf_counter()
        try:
            with self._connect() as connection:
                rows = tuple(
                    connection.execute(
                        _BATCH_FLOW_NEIGHBOURHOODS,
                        parameters,
                    ).mappings()
                )
        except SQLAlchemyError:
            raise DatabaseQueryError(
                "Unable to evaluate batched pedestrian-flow sensor support."
            ) from None
        database_elapsed_ms = (perf_counter() - started) * 1000.0

        sensors_by_key: dict[tuple[int, int], list[SensorPedestrianFlow]] = {
            sample.key: [] for sample in requested
        }
        snapshot = empty_snapshot
        if rows:
            first = rows[0]
            snapshot = PedestrianFlowSnapshot(
                window_start=first["snapshot_window_start"],
                window_end=first["snapshot_window_end"],
                calculated_at=first["snapshot_calculated_at"],
                window_variant_count=int(first["window_variant_count"]),
                baseline_hour_day=_optional_int(first["context_hour_day"]),
                baseline_day_type=first["context_day_type"],
            )

        for row in rows:
            key = (int(row["route_index"]), int(row["sample_index"]))
            if key not in sensors_by_key or row["location_id"] is None:
                continue
            sensors_by_key[key].append(
                SensorPedestrianFlow(
                    location_id=int(row["location_id"]),
                    distance_meters=float(row["distance_meters"]),
                    location_type=str(row["location_type"]),
                    status=row["status"],
                    data_state=row["data_state"],
                    current_15m_count=_optional_int(row["current_15m_count"]),
                    current_15m_observed_rows=_optional_int(
                        row["current_15m_observed_rows"]
                    ),
                    window_start=row["current_15m_window_start"],
                    window_end=row["current_15m_window_end"],
                    calculated_at=row["calculated_at"],
                    baseline_hour_day=_optional_int(row["baseline_hour_day"]),
                    baseline_day_type=row["baseline_day_type"],
                    baseline_observation_count=_optional_int(
                        row["baseline_observation_count"]
                    ),
                    baseline_median_count=_optional_float(
                        row["baseline_median_count"]
                    ),
                    baseline_mean_count=_optional_float(
                        row["baseline_mean_count"]
                    ),
                    baseline_p75_count=_optional_float(
                        row["baseline_p75_count"]
                    ),
                    baseline_start_date=row["baseline_start_date"],
                    baseline_end_date=row["baseline_end_date"],
                )
            )

        return FlowNeighbourhoodBatch(
            neighbourhoods=tuple(
                FlowNeighbourhood(
                    sample=sample,
                    sensors=tuple(sensors_by_key[sample.key]),
                )
                for sample in requested
            ),
            snapshot=snapshot,
            database_elapsed_ms=database_elapsed_ms,
            sql_execution_count=1,
        )
