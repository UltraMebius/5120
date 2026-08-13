"""Journey-corridor lookup for authoritative pedestrian sensor waypoints."""

from collections.abc import Iterator
from contextlib import contextmanager
import json
from time import perf_counter

from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import SQLAlchemyError

from ..config import SETTINGS
from ..db.connection import get_database_engine
from ..db.exceptions import DatabaseQueryError
from ..models.pedestrian_flow import PedestrianFlowSnapshot, SensorPedestrianFlow
from ..services.routing.route_candidate_config import (
    MAXIMUM_WAYPOINT_ROUTE_PROGRESS,
    MAXIMUM_WAYPOINT_GEOMETRIC_DETOUR_MULTIPLIER,
    MINIMUM_WAYPOINT_ENDPOINT_DISTANCE_M,
    MINIMUM_WAYPOINT_ROUTE_OFFSET_M,
    MINIMUM_WAYPOINT_ROUTE_PROGRESS,
    WAYPOINT_SEARCH_CORRIDOR_RADIUS_M,
)
from ..services.routing.route_candidate_models import (
    WaypointEvidenceBatch,
    WaypointSensorEvidence,
)


_FIND_WAYPOINT_EVIDENCE = text(
    """
    WITH journey AS (
        SELECT
            ST_SetSRID(
                ST_MakePoint(:origin_longitude, :origin_latitude), 4326
            )::geography AS origin_geom,
            ST_SetSRID(
                ST_MakePoint(:destination_longitude, :destination_latitude),
                4326
            )::geography AS destination_geom,
            ST_SetSRID(ST_GeomFromGeoJSON(:route_geojson), 4326)
                AS route_geom
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
            CASE WHEN window_start IS NULL THEN NULL ELSE EXTRACT(
                HOUR FROM window_start AT TIME ZONE :timezone_name
            )::SMALLINT END AS baseline_hour_day,
            CASE
                WHEN window_start IS NULL THEN NULL
                WHEN EXTRACT(
                    ISODOW FROM window_start AT TIME ZONE :timezone_name
                ) BETWEEN 1 AND 5 THEN 'Weekday'
                ELSE 'Weekend'
            END AS baseline_day_type
        FROM current_snapshot
    ),
    spatial_candidates AS (
        SELECT
            location.*,
            ST_X(location.geom::geometry) AS candidate_longitude,
            ST_Y(location.geom::geometry) AS candidate_latitude,
            ST_Distance(location.geom, journey.origin_geom)
                AS distance_from_origin_meters,
            ST_Distance(location.geom, journey.destination_geom)
                AS distance_from_destination_meters,
            ST_Distance(location.geom, journey.route_geom::geography)
                AS distance_from_direct_route_meters,
            ST_LineLocatePoint(
                journey.route_geom,
                location.geom::geometry
            ) AS projected_route_progress,
            GREATEST(
                ST_Distance(location.geom, journey.origin_geom)
                + ST_Distance(location.geom, journey.destination_geom)
                - ST_Distance(journey.origin_geom, journey.destination_geom),
                0.0
            ) AS estimated_geometric_detour_meters
        FROM sensor_location_current location
        CROSS JOIN journey
        WHERE LOWER(TRIM(location.location_type)) = 'outdoor'
          AND UPPER(TRIM(location.status)) = 'A'
          AND ST_DWithin(
              location.geom,
              journey.route_geom::geography,
              :search_corridor_radius_m
          )
          AND ST_Distance(location.geom, journey.route_geom::geography)
              > :minimum_route_offset_m
          AND ST_Distance(location.geom, journey.origin_geom)
              >= :minimum_endpoint_distance_m
          AND ST_Distance(location.geom, journey.destination_geom)
              >= :minimum_endpoint_distance_m
          AND ST_Distance(location.geom, journey.origin_geom)
              + ST_Distance(location.geom, journey.destination_geom)
              <= :geometric_detour_multiplier
                 * ST_Distance(journey.origin_geom, journey.destination_geom)
          AND ST_LineLocatePoint(
              journey.route_geom,
              location.geom::geometry
          ) >= :minimum_route_progress
          AND ST_LineLocatePoint(
              journey.route_geom,
              location.geom::geometry
          ) <= :maximum_route_progress
    )
    SELECT
        candidate.location_id,
        candidate.location_type,
        candidate.status,
        candidate.candidate_longitude,
        candidate.candidate_latitude,
        candidate.distance_from_origin_meters,
        candidate.distance_from_destination_meters,
        candidate.distance_from_direct_route_meters,
        candidate.estimated_geometric_detour_meters,
        candidate.projected_route_progress,
        context.window_start AS snapshot_window_start,
        context.window_end AS snapshot_window_end,
        context.calculated_at AS snapshot_calculated_at,
        context.window_variant_count,
        context.baseline_hour_day AS context_hour_day,
        context.baseline_day_type AS context_day_type,
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
    FROM spatial_candidates candidate
    CROSS JOIN time_context context
    LEFT JOIN current_sensor_activity activity
      ON activity.location_id = candidate.location_id
    LEFT JOIN sensor_hour_daytype_baseline baseline
      ON baseline.location_id = candidate.location_id
     AND baseline.hour_day = context.baseline_hour_day
     AND baseline.day_type = context.baseline_day_type
    ORDER BY candidate.location_id
    """
)


def _optional_int(value: object) -> int | None:
    return None if value is None else int(value)


def _optional_float(value: object) -> float | None:
    return None if value is None else float(value)


class RouteWaypointRepository:
    """Retrieve only active outdoor sensors in one journey corridor query."""

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
        engine = self.engine or get_database_engine()
        with engine.connect() as connection:
            yield connection

    def find_waypoint_evidence(
        self,
        *,
        origin: tuple[float, float],
        destination: tuple[float, float],
        direct_route_geometry: object,
    ) -> WaypointEvidenceBatch:
        """Return bounded-region flow evidence with one SQL execution."""

        route_geojson = (
            direct_route_geometry.model_dump_json()
            if hasattr(direct_route_geometry, "model_dump_json")
            else json.dumps(direct_route_geometry, separators=(",", ":"))
        )
        parameters = {
            "origin_longitude": origin[0],
            "origin_latitude": origin[1],
            "destination_longitude": destination[0],
            "destination_latitude": destination[1],
            "route_geojson": route_geojson,
            "timezone_name": SETTINGS.app_timezone,
            "search_corridor_radius_m": WAYPOINT_SEARCH_CORRIDOR_RADIUS_M,
            "minimum_route_offset_m": MINIMUM_WAYPOINT_ROUTE_OFFSET_M,
            "minimum_endpoint_distance_m": MINIMUM_WAYPOINT_ENDPOINT_DISTANCE_M,
            "minimum_route_progress": MINIMUM_WAYPOINT_ROUTE_PROGRESS,
            "maximum_route_progress": MAXIMUM_WAYPOINT_ROUTE_PROGRESS,
            "geometric_detour_multiplier": (
                MAXIMUM_WAYPOINT_GEOMETRIC_DETOUR_MULTIPLIER
            ),
        }
        started = perf_counter()
        try:
            with self._connect() as connection:
                rows = tuple(
                    connection.execute(
                        _FIND_WAYPOINT_EVIDENCE,
                        parameters,
                    ).mappings()
                )
        except SQLAlchemyError:
            raise DatabaseQueryError(
                "Unable to discover pedestrian-flow waypoint evidence."
            ) from None
        database_elapsed_ms = (perf_counter() - started) * 1000.0

        snapshot = PedestrianFlowSnapshot(None, None, None, 0, None, None)
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

        evidence = tuple(
            WaypointSensorEvidence(
                longitude=float(row["candidate_longitude"]),
                latitude=float(row["candidate_latitude"]),
                distance_from_origin_meters=float(
                    row["distance_from_origin_meters"]
                ),
                distance_from_destination_meters=float(
                    row["distance_from_destination_meters"]
                ),
                distance_from_direct_route_meters=float(
                    row["distance_from_direct_route_meters"]
                ),
                estimated_geometric_detour_meters=float(
                    row["estimated_geometric_detour_meters"]
                ),
                projected_route_progress=float(
                    row["projected_route_progress"]
                ),
                sensor_flow=SensorPedestrianFlow(
                    location_id=int(row["location_id"]),
                    distance_meters=float(
                        row["distance_from_direct_route_meters"]
                    ),
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
                ),
            )
            for row in rows
        )
        return WaypointEvidenceBatch(
            evidence=evidence,
            snapshot=snapshot,
            database_elapsed_ms=database_elapsed_ms,
            sql_execution_count=1,
        )
