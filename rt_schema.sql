-- Tables for the live (GTFS-Realtime) data, Milestone 2 of Phase 2.
-- Run with:   python run_sql.py rt_schema.sql
-- Unlike schema.sql this file never deletes anything, so it is safe to run again.

-- One row per ingestion run of one feed, so failures and run times can be measured.
CREATE TABLE IF NOT EXISTS ingestion_runs (
    run_id          BIGSERIAL PRIMARY KEY,
    feed_name       TEXT NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL,
    finished_at     TIMESTAMPTZ,
    status          TEXT NOT NULL,          -- 'success' or 'failed'
    rows_fetched    INTEGER,
    rows_inserted   INTEGER,
    error_message   TEXT
);

-- Raw layer: one row per distinct stop-time prediction.
-- The same prediction repeated in later snapshots is stored once; last_seen_at records
-- the latest snapshot that still contained it, so the final observed arrival is the row
-- with the newest last_seen_at for each trip and stop.
CREATE TABLE IF NOT EXISTS rt_trip_updates (
    update_id            BIGSERIAL PRIMARY KEY,
    snapshot_time        TIMESTAMPTZ NOT NULL,  -- feed timestamp when first seen
    last_seen_at         TIMESTAMPTZ NOT NULL,  -- feed timestamp when last seen
    trip_id              TEXT NOT NULL,
    service_date         DATE,
    route_id             TEXT,
    stop_id              TEXT,                  -- NULL for a whole-trip row (e.g. cancelled)
    stop_sequence        INTEGER,
    arrival_time         TIMESTAMPTZ,           -- predicted, or actual once it has happened
    departure_time       TIMESTAMPTZ,
    arrival_delay        INTEGER,               -- seconds, if the feed gives it
    departure_delay      INTEGER,
    stop_relationship    TEXT,                  -- SCHEDULED, SKIPPED, NO_DATA ...
    trip_relationship    TEXT,                  -- SCHEDULED, CANCELED, ADDED ...
    CONSTRAINT rt_trip_updates_unique UNIQUE NULLS NOT DISTINCT (
        trip_id, service_date, stop_id, stop_sequence, arrival_time, departure_time,
        arrival_delay, departure_delay, stop_relationship, trip_relationship
    )
);

CREATE INDEX IF NOT EXISTS rt_trip_updates_trip_idx
    ON rt_trip_updates (trip_id, stop_sequence);
CREATE INDEX IF NOT EXISTS rt_trip_updates_snapshot_idx
    ON rt_trip_updates (snapshot_time);

-- Vehicle positions: one row per vehicle per position report.
CREATE TABLE IF NOT EXISTS rt_vehicle_positions (
    position_id      BIGSERIAL PRIMARY KEY,
    snapshot_time    TIMESTAMPTZ NOT NULL,
    vehicle_id       TEXT NOT NULL,
    position_time    TIMESTAMPTZ NOT NULL,   -- when the vehicle reported this position
    trip_id          TEXT,
    route_id         TEXT,
    latitude         DOUBLE PRECISION,
    longitude        DOUBLE PRECISION,
    bearing          REAL,
    speed            REAL,                   -- metres per second
    CONSTRAINT rt_vehicle_positions_unique UNIQUE (vehicle_id, position_time)
);

CREATE INDEX IF NOT EXISTS rt_vehicle_positions_snapshot_idx
    ON rt_vehicle_positions (snapshot_time);
