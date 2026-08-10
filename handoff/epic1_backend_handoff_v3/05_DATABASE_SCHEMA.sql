-- Epic 1 Crowd-Aware Walking Route Planning
-- Backend Schema V2
-- PostgreSQL + PostGIS
--
-- V2 changes:
-- - removes MAX/conservative crowd score as final Crowd Level
-- - separates Network Crowd Exposure from Local Condition
-- - adds day_type to hourly facts for indexed percentile lookups
-- - adds network_hour_daytype_baseline
-- - current sensor cache stores current live network exposure and separate 1h historical contexts
-- - spatial cache stores separate Crowd Exposure and Local Condition

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS sensor (
    location_id BIGINT PRIMARY KEY,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sensor_location_current (
    location_id BIGINT PRIMARY KEY REFERENCES sensor(location_id) ON DELETE CASCADE,
    sensor_description TEXT,
    sensor_name TEXT,
    installation_date DATE,
    note TEXT,
    location_type TEXT NOT NULL,
    status TEXT,
    direction_1_label TEXT,
    direction_2_label TEXT,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    geom GEOGRAPHY(POINT, 4326) NOT NULL,
    source_updated_at TIMESTAMPTZ,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (latitude BETWEEN -90 AND 90),
    CHECK (longitude BETWEEN -180 AND 180)
);

CREATE INDEX IF NOT EXISTS idx_sensor_location_current_geom
    ON sensor_location_current USING GIST (geom);

CREATE INDEX IF NOT EXISTS idx_sensor_location_current_type_status
    ON sensor_location_current(location_type, status);

CREATE TABLE IF NOT EXISTS pedestrian_hourly_count (
    location_id BIGINT NOT NULL REFERENCES sensor(location_id),
    sensing_date DATE NOT NULL,
    hour_day SMALLINT NOT NULL,
    day_type TEXT NOT NULL,
    source_id BIGINT,
    direction_1 BIGINT,
    direction_2 BIGINT,
    total_of_directions BIGINT NOT NULL,
    source_sensor_name TEXT,
    source_location_text TEXT,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (location_id, sensing_date, hour_day),
    CHECK (hour_day BETWEEN 0 AND 23),
    CHECK (day_type IN ('Weekday', 'Weekend')),
    CHECK (direction_1 IS NULL OR direction_1 >= 0),
    CHECK (direction_2 IS NULL OR direction_2 >= 0),
    CHECK (total_of_directions >= 0)
);

CREATE INDEX IF NOT EXISTS idx_hourly_date_hour
    ON pedestrian_hourly_count(sensing_date, hour_day);

CREATE INDEX IF NOT EXISTS idx_hourly_location_date
    ON pedestrian_hourly_count(location_id, sensing_date);

CREATE INDEX IF NOT EXISTS idx_hourly_local_percentile_lookup
    ON pedestrian_hourly_count(location_id, hour_day, day_type, total_of_directions);

CREATE INDEX IF NOT EXISTS idx_hourly_network_percentile_lookup
    ON pedestrian_hourly_count(hour_day, day_type, total_of_directions);

CREATE TABLE IF NOT EXISTS ingestion_run (
    ingestion_run_id BIGSERIAL PRIMARY KEY,
    source_name TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'RUNNING',
    rows_received BIGINT NOT NULL DEFAULT 0,
    rows_inserted BIGINT NOT NULL DEFAULT 0,
    rows_skipped_exact_duplicate BIGINT NOT NULL DEFAULT 0,
    conflict_groups_detected BIGINT NOT NULL DEFAULT 0,
    error_message TEXT,
    metadata JSONB
);

CREATE TABLE IF NOT EXISTS pedestrian_minute_observation_raw (
    minute_record_id BIGSERIAL PRIMARY KEY,
    location_id BIGINT NOT NULL REFERENCES sensor(location_id),
    source_sensing_datetime TIMESTAMPTZ NOT NULL,
    sensing_date_local DATE NOT NULL,
    sensing_time_local TIME NOT NULL,
    direction_1 BIGINT,
    direction_2 BIGINT,
    total_of_directions BIGINT NOT NULL,
    payload_hash CHAR(64) NOT NULL UNIQUE,
    ingestion_run_id BIGINT REFERENCES ingestion_run(ingestion_run_id),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (direction_1 IS NULL OR direction_1 >= 0),
    CHECK (direction_2 IS NULL OR direction_2 >= 0),
    CHECK (total_of_directions >= 0)
);

CREATE INDEX IF NOT EXISTS idx_minute_logical_key
    ON pedestrian_minute_observation_raw(location_id, source_sensing_datetime);

CREATE INDEX IF NOT EXISTS idx_minute_time
    ON pedestrian_minute_observation_raw(source_sensing_datetime);

CREATE OR REPLACE VIEW v_minute_conflict_groups AS
SELECT
    location_id,
    source_sensing_datetime,
    COUNT(*) AS record_count,
    COUNT(DISTINCT payload_hash) AS distinct_payload_count
FROM pedestrian_minute_observation_raw
GROUP BY location_id, source_sensing_datetime
HAVING COUNT(DISTINCT payload_hash) > 1;

CREATE OR REPLACE VIEW v_minute_unconflicted AS
SELECT r.*
FROM pedestrian_minute_observation_raw r
LEFT JOIN v_minute_conflict_groups c
    ON c.location_id = r.location_id
   AND c.source_sensing_datetime = r.source_sensing_datetime
WHERE c.location_id IS NULL;

CREATE TABLE IF NOT EXISTS sensor_hour_daytype_baseline (
    location_id BIGINT NOT NULL REFERENCES sensor(location_id),
    hour_day SMALLINT NOT NULL,
    day_type TEXT NOT NULL,
    observation_count BIGINT NOT NULL,
    mean_count DOUBLE PRECISION,
    median_count DOUBLE PRECISION,
    p10 DOUBLE PRECISION,
    p20 DOUBLE PRECISION,
    p25 DOUBLE PRECISION,
    p40 DOUBLE PRECISION,
    p50 DOUBLE PRECISION,
    p60 DOUBLE PRECISION,
    p75 DOUBLE PRECISION,
    p80 DOUBLE PRECISION,
    p90 DOUBLE PRECISION,
    p95 DOUBLE PRECISION,
    baseline_start_date DATE,
    baseline_end_date DATE,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (location_id, hour_day, day_type),
    CHECK (hour_day BETWEEN 0 AND 23),
    CHECK (day_type IN ('Weekday', 'Weekend'))
);

CREATE TABLE IF NOT EXISTS network_hour_daytype_baseline (
    hour_day SMALLINT NOT NULL,
    day_type TEXT NOT NULL,
    observation_count BIGINT NOT NULL,
    sensor_count BIGINT NOT NULL,
    mean_count DOUBLE PRECISION,
    median_count DOUBLE PRECISION,
    p10 DOUBLE PRECISION,
    p20 DOUBLE PRECISION,
    p25 DOUBLE PRECISION,
    p40 DOUBLE PRECISION,
    p50 DOUBLE PRECISION,
    p60 DOUBLE PRECISION,
    p75 DOUBLE PRECISION,
    p80 DOUBLE PRECISION,
    p90 DOUBLE PRECISION,
    p95 DOUBLE PRECISION,
    baseline_start_date DATE,
    baseline_end_date DATE,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (hour_day, day_type),
    CHECK (hour_day BETWEEN 0 AND 23),
    CHECK (day_type IN ('Weekday', 'Weekend'))
);

CREATE TABLE IF NOT EXISTS current_sensor_activity (
    location_id BIGINT PRIMARY KEY REFERENCES sensor(location_id),

    current_15m_window_start TIMESTAMPTZ,
    current_15m_window_end TIMESTAMPTZ,
    current_15m_observed_rows INTEGER,
    current_15m_count BIGINT,
    current_15m_network_percentile DOUBLE PRECISION,
    current_crowd_exposure_score DOUBLE PRECISION,
    current_crowd_level TEXT,

    comparison_hour_start TIMESTAMPTZ,
    current_1h_observed_rows INTEGER,
    current_1h_count BIGINT,
    current_1h_network_historical_percentile DOUBLE PRECISION,
    current_1h_local_historical_percentile DOUBLE PRECISION,
    current_local_condition TEXT,

    data_state TEXT NOT NULL DEFAULT 'NO_DATA',
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (
        current_crowd_level IS NULL OR
        current_crowd_level IN ('VERY_LOW','LOW','MODERATE','HIGH','VERY_HIGH')
    ),
    CHECK (
        current_local_condition IS NULL OR
        current_local_condition IN (
            'MUCH_QUIETER_THAN_USUAL',
            'QUIETER_THAN_USUAL',
            'TYPICAL',
            'BUSIER_THAN_USUAL',
            'MUCH_BUSIER_THAN_USUAL'
        )
    ),
    CHECK (
        data_state IN ('OK','AMBIGUOUS_NO_RECORD','STALE','CONFLICTED','NO_DATA')
    )
);

CREATE TABLE IF NOT EXISTS theme (
    theme_id BIGSERIAL PRIMARY KEY,
    theme_name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS sub_theme (
    sub_theme_id BIGSERIAL PRIMARY KEY,
    theme_id BIGINT NOT NULL REFERENCES theme(theme_id),
    sub_theme_name TEXT NOT NULL,
    UNIQUE(theme_id, sub_theme_name)
);

CREATE TABLE IF NOT EXISTS landmark (
    landmark_id BIGSERIAL PRIMARY KEY,
    sub_theme_id BIGINT NOT NULL REFERENCES sub_theme(sub_theme_id),
    feature_name TEXT NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    geom GEOGRAPHY(POINT, 4326) NOT NULL,
    source_coordinate_text TEXT,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (latitude BETWEEN -90 AND 90),
    CHECK (longitude BETWEEN -180 AND 180)
);

CREATE INDEX IF NOT EXISTS idx_landmark_geom
    ON landmark USING GIST (geom);

CREATE TABLE IF NOT EXISTS spatial_activity_cache (
    spatial_cache_id BIGSERIAL PRIMARY KEY,
    calculated_at TIMESTAMPTZ NOT NULL,
    point_latitude DOUBLE PRECISION NOT NULL,
    point_longitude DOUBLE PRECISION NOT NULL,
    point_geom GEOGRAPHY(POINT, 4326) NOT NULL,

    crowd_exposure_score DOUBLE PRECISION,
    crowd_level TEXT,

    local_condition_score DOUBLE PRECISION,
    local_condition TEXT,

    supporting_sensor_count INTEGER NOT NULL DEFAULT 0,
    nearest_sensor_distance_m DOUBLE PRECISION,
    supporting_score_stddev DOUBLE PRECISION,
    coverage_status TEXT NOT NULL,

    source_window_start TIMESTAMPTZ,
    source_window_end TIMESTAMPTZ,

    CHECK (
        crowd_level IS NULL OR
        crowd_level IN ('VERY_LOW','LOW','MODERATE','HIGH','VERY_HIGH')
    ),
    CHECK (
        local_condition IS NULL OR
        local_condition IN (
            'MUCH_QUIETER_THAN_USUAL',
            'QUIETER_THAN_USUAL',
            'TYPICAL',
            'BUSIER_THAN_USUAL',
            'MUCH_BUSIER_THAN_USUAL'
        )
    ),
    CHECK (
        coverage_status IN ('SUPPORTED','LIMITED','NO_DATA')
    )
);

CREATE INDEX IF NOT EXISTS idx_spatial_activity_cache_geom
    ON spatial_activity_cache USING GIST (point_geom);

CREATE INDEX IF NOT EXISTS idx_spatial_activity_cache_time
    ON spatial_activity_cache(calculated_at);

-- Example current point support query:
--
-- SELECT
--     s.location_id,
--     a.current_15m_network_percentile,
--     a.current_1h_local_historical_percentile,
--     ST_Distance(
--         s.geom,
--         ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
--     ) AS distance_m
-- FROM sensor_location_current s
-- JOIN current_sensor_activity a USING (location_id)
-- WHERE LOWER(s.location_type) = 'outdoor'
--   AND a.data_state = 'OK'
--   AND a.current_15m_network_percentile IS NOT NULL
--   AND ST_DWithin(
--       s.geom,
--       ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
--       300
--   );
