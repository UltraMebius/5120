# Latest ERD — Epic 1 Backend V2

```mermaid
erDiagram

    SENSOR {
        bigint location_id PK
        timestamptz first_seen_at
        timestamptz last_seen_at
    }

    SENSOR_LOCATION_CURRENT {
        bigint location_id PK,FK
        text sensor_description
        text sensor_name
        date installation_date
        text note
        text location_type
        text status
        text direction_1_label
        text direction_2_label
        double latitude
        double longitude
        geography geom
        timestamptz source_updated_at
    }

    PEDESTRIAN_HOURLY_COUNT {
        bigint location_id PK,FK
        date sensing_date PK
        smallint hour_day PK
        text day_type
        bigint source_id
        bigint direction_1
        bigint direction_2
        bigint total_of_directions
    }

    INGESTION_RUN {
        bigint ingestion_run_id PK
        text source_name
        timestamptz started_at
        timestamptz finished_at
        text status
        bigint rows_received
        bigint rows_inserted
        bigint conflict_groups_detected
    }

    PEDESTRIAN_MINUTE_OBSERVATION_RAW {
        bigint minute_record_id PK
        bigint location_id FK
        timestamptz source_sensing_datetime
        date sensing_date_local
        time sensing_time_local
        bigint direction_1
        bigint direction_2
        bigint total_of_directions
        char payload_hash UK
        bigint ingestion_run_id FK
        timestamptz ingested_at
    }

    SENSOR_HOUR_DAYTYPE_BASELINE {
        bigint location_id PK,FK
        smallint hour_day PK
        text day_type PK
        bigint observation_count
        double p25
        double p50
        double p75
        double p90
        date baseline_start_date
        date baseline_end_date
    }

    NETWORK_HOUR_DAYTYPE_BASELINE {
        smallint hour_day PK
        text day_type PK
        bigint observation_count
        bigint sensor_count
        double p25
        double p50
        double p75
        double p90
        date baseline_start_date
        date baseline_end_date
    }

    CURRENT_SENSOR_ACTIVITY {
        bigint location_id PK,FK
        timestamptz current_15m_window_start
        int current_15m_observed_rows
        bigint current_15m_count
        double current_15m_network_percentile
        double current_crowd_exposure_score
        text current_crowd_level
        timestamptz comparison_hour_start
        bigint current_1h_count
        double current_1h_network_historical_percentile
        double current_1h_local_historical_percentile
        text current_local_condition
        text data_state
    }

    THEME {
        bigint theme_id PK
        text theme_name UK
    }

    SUB_THEME {
        bigint sub_theme_id PK
        bigint theme_id FK
        text sub_theme_name
    }

    LANDMARK {
        bigint landmark_id PK
        bigint sub_theme_id FK
        text feature_name
        double latitude
        double longitude
        geography geom
    }

    SPATIAL_ACTIVITY_CACHE {
        bigint spatial_cache_id PK
        timestamptz calculated_at
        geography point_geom
        double crowd_exposure_score
        text crowd_level
        double local_condition_score
        text local_condition
        int supporting_sensor_count
        double nearest_sensor_distance_m
        double supporting_score_stddev
        text coverage_status
    }

    SENSOR ||--o| SENSOR_LOCATION_CURRENT : "has current metadata"
    SENSOR ||--o{ PEDESTRIAN_HOURLY_COUNT : "records hourly counts"
    SENSOR ||--o{ PEDESTRIAN_MINUTE_OBSERVATION_RAW : "records realtime minute rows"
    INGESTION_RUN ||--o{ PEDESTRIAN_MINUTE_OBSERVATION_RAW : "loads"
    SENSOR ||--o{ SENSOR_HOUR_DAYTYPE_BASELINE : "has local historical baseline"
    SENSOR ||--o| CURRENT_SENSOR_ACTIVITY : "has current derived metrics"
    THEME ||--o{ SUB_THEME : "contains"
    SUB_THEME ||--o{ LANDMARK : "classifies"
```

## V2 Design Notes

1. `CURRENT_SENSOR_ACTIVITY` no longer stores MAX/conservative Crowd Scores.
2. `current_15m_network_percentile` is the primary live Crowd Exposure input.
3. `current_1h_local_historical_percentile` is retained separately for Local Condition.
4. `NETWORK_HOUR_DAYTYPE_BASELINE` is added for network-level historical QA/context.
5. `LANDMARK_NEAREST_SENSOR` remains excluded from the core model because the current method uses all eligible Outdoor sensors within the 300 m support limit.
6. `PEDESTRIAN_MINUTE_OBSERVATION_RAW` still preserves conflicting rows using a surrogate PK plus payload hash.
7. `SENSOR_LOCATION_CURRENT` remains a current snapshot, not an invented historical-location dimension.
8. `SPATIAL_ACTIVITY_CACHE` stores Crowd Exposure and Local Condition separately.
