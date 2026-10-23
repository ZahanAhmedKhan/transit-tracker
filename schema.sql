-- Tables for the GO Transit GTFS data (Milestone 2).
-- First create the database once:   CREATE DATABASE transit_tracker;
-- Then run this file:                psql -U postgres -d transit_tracker -f schema.sql
-- Warning: running this file again deletes the tables and all their rows.

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
