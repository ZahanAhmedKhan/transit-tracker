-- Tables for the GO Transit GTFS data (Milestones 2 and 4).
-- First create the database once:   CREATE DATABASE transit;
-- Then run this file:                psql -U postgres -d transit -f schema.sql
-- Warning: running this file again deletes the tables and all their rows.

DROP TABLE IF EXISTS stop_times;
DROP TABLE IF EXISTS trips;
DROP TABLE IF EXISTS calendar_dates;
DROP TABLE IF EXISTS stops;
DROP TABLE IF EXISTS routes;

CREATE TABLE stops (
    stop_id              TEXT PRIMARY KEY,
    stop_name            TEXT NOT NULL,
    stop_lat             DOUBLE PRECISION,
    stop_lon             DOUBLE PRECISION,
    zone_id              TEXT,
    stop_url             TEXT,
    location_type        INTEGER,
    parent_station       TEXT,
    wheelchair_boarding  INTEGER,
    stop_code            TEXT
);

CREATE TABLE routes (
    route_id             TEXT PRIMARY KEY,
    agency_id            TEXT,
    route_short_name     TEXT,
    route_long_name      TEXT,
    route_type           INTEGER,
    route_color          TEXT,
    route_text_color     TEXT
);

CREATE TABLE trips (
    trip_id                TEXT PRIMARY KEY,
    route_id               TEXT NOT NULL,
    service_id             TEXT NOT NULL,
    trip_headsign          TEXT,
    trip_short_name        TEXT,
    direction_id           INTEGER,
    block_id               TEXT,
    shape_id               TEXT,
    wheelchair_accessible  INTEGER,
    bikes_allowed          INTEGER,
    route_variant          TEXT
);

-- GO only publishes calendar_dates.txt: one row per service_id per date it runs.
CREATE TABLE calendar_dates (
    service_id      TEXT,
    date            DATE,
    exception_type  INTEGER,
    PRIMARY KEY (service_id, date)
);

-- GTFS times can go past 24:00:00 (e.g. 25:30:00 for a trip after midnight),
-- which the TIME type rejects, so they are stored as INTERVAL.
CREATE TABLE stop_times (
    trip_id         TEXT,
    stop_sequence   INTEGER,
    stop_id         TEXT NOT NULL,
    arrival_time    INTERVAL,
    departure_time  INTERVAL,
    pickup_type     INTEGER,
    drop_off_type   INTEGER,
    stop_headsign   TEXT,
    PRIMARY KEY (trip_id, stop_sequence)
);
