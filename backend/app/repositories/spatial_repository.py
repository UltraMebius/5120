"""PostGIS geography discovery for point-level crowd evaluation."""

from contextlib import contextmanager
from collections.abc import Iterator

from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import SQLAlchemyError

from ..db.connection import get_database_engine
from ..db.exceptions import DatabaseQueryError
from ..models.spatial import (
    SpatialCurrentSnapshot,
    SpatialNeighbourhood,
    SpatialSensorCandidate,
)


_NEARBY_CANDIDATES = text(
    """
    WITH query_point AS (
        SELECT ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography
            AS geom
    )
    SELECT
        sl.location_id,
        sl.location_type,
        sl.status,
        a.data_state,
        a.current_15m_network_percentile,
        a.current_1h_local_historical_percentile,
        a.current_15m_window_start,
        a.current_15m_window_end,
        a.calculated_at,
        ST_Distance(sl.geom, query_point.geom) AS distance_m
    FROM sensor_location_current sl
    LEFT JOIN current_sensor_activity a USING (location_id)
    CROSS JOIN query_point
    WHERE ST_DWithin(sl.geom, query_point.geom, :maximum_radius_m)
    ORDER BY distance_m, sl.location_id
    """
)


_NEAREST_VALID_DISTANCE = text(
    """
    WITH query_point AS (
        SELECT ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography
            AS geom
    )
    SELECT ST_Distance(sl.geom, query_point.geom) AS distance_m
    FROM sensor_location_current sl
    JOIN current_sensor_activity a USING (location_id)
    CROSS JOIN query_point
    WHERE LOWER(BTRIM(sl.location_type)) = 'outdoor'
      AND UPPER(BTRIM(COALESCE(sl.status, ''))) = 'A'
      AND a.data_state = 'OK'
      AND a.current_15m_network_percentile IS NOT NULL
    ORDER BY sl.geom <-> query_point.geom, sl.location_id
    LIMIT 1
    """
)


_CURRENT_SNAPSHOT = text(
    """
    SELECT
        MIN(current_15m_window_start) AS source_window_start,
        MAX(current_15m_window_end) AS source_window_end,
        MAX(calculated_at) AS updated_at,
        COUNT(DISTINCT JSONB_BUILD_ARRAY(
            current_15m_window_start,
            current_15m_window_end
        )) AS window_variant_count
    FROM current_sensor_activity
    """
)


class SpatialRepository:
    """Return measured metre distances; apply no weighting in the repository."""

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

    def find_neighbourhood(
        self,
        *,
        longitude: float,
        latitude: float,
        maximum_radius_m: float,
    ) -> SpatialNeighbourhood:
        parameters = {
            "longitude": longitude,
            "latitude": latitude,
            "maximum_radius_m": maximum_radius_m,
        }
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    _NEARBY_CANDIDATES, parameters
                ).mappings()
                candidates = tuple(
                    SpatialSensorCandidate(
                        location_id=int(row["location_id"]),
                        location_type=str(row["location_type"]),
                        status=row["status"],
                        data_state=row["data_state"],
                        distance_m=float(row["distance_m"]),
                        current_15m_network_percentile=(
                            None
                            if row["current_15m_network_percentile"] is None
                            else float(row["current_15m_network_percentile"])
                        ),
                        current_1h_local_historical_percentile=(
                            None
                            if row[
                                "current_1h_local_historical_percentile"
                            ]
                            is None
                            else float(
                                row[
                                    "current_1h_local_historical_percentile"
                                ]
                            )
                        ),
                        source_window_start=row["current_15m_window_start"],
                        source_window_end=row["current_15m_window_end"],
                        calculated_at=row["calculated_at"],
                    )
                    for row in rows
                )
                nearest = connection.execute(
                    _NEAREST_VALID_DISTANCE, parameters
                ).scalar_one_or_none()
                snapshot_row = connection.execute(
                    _CURRENT_SNAPSHOT
                ).mappings().one()
        except SQLAlchemyError:
            raise DatabaseQueryError(
                "Unable to evaluate current sensor support with PostGIS."
            ) from None

        return SpatialNeighbourhood(
            candidates=candidates,
            nearest_valid_sensor_distance_m=(
                None if nearest is None else float(nearest)
            ),
            snapshot=SpatialCurrentSnapshot(
                source_window_start=snapshot_row["source_window_start"],
                source_window_end=snapshot_row["source_window_end"],
                updated_at=snapshot_row["updated_at"],
                window_variant_count=int(snapshot_row["window_variant_count"]),
            ),
        )
