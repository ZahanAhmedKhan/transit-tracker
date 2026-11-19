-- Reliability metrics, Milestone 3 of Phase 2. See docs/metrics.md for the definitions.
-- Run with:   python run_sql.py metrics_schema.sql
-- Safe to run again: tables are only created if missing and views are replaced.

-- The on-time thresholds, kept in one row so they can be changed without editing code:
--   UPDATE reliability_settings SET late_minutes = 3;
CREATE TABLE IF NOT EXISTS reliability_settings (
    id                          INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    early_minutes               NUMERIC NOT NULL,  -- arriving more than this early is not on time
    late_minutes                NUMERIC NOT NULL,  -- arriving more than this late is not on time
    max_prediction_gap_minutes  NUMERIC NOT NULL   -- see "observed arrival" in docs/metrics.md
);
INSERT INTO reliability_settings (id, early_minutes, late_minutes, max_prediction_gap_minutes)
VALUES (1, 1, 5, 15)
ON CONFLICT (id) DO NOTHING;

-- One row per scheduled stop of a trip that the live feed told us about: the final observed
-- arrival matched to the schedule. Filled by refresh_metrics.py and kept after the raw data
-- and the schedule window are cleaned up.
CREATE TABLE IF NOT EXISTS stop_arrivals (
    service_date        DATE NOT NULL,
    trip_id             TEXT NOT NULL,
    stop_sequence       INTEGER NOT NULL,
    stop_id             TEXT NOT NULL,
    route_short_name    TEXT,
    route_name          TEXT,
    scheduled_arrival   TIMESTAMPTZ NOT NULL,
    observed_arrival    TIMESTAMPTZ,              -- NULL when skipped or cancelled
    delay_seconds       INTEGER,                  -- observed minus scheduled
    status              TEXT NOT NULL,            -- 'observed', 'skipped' or 'cancelled'
    PRIMARY KEY (service_date, trip_id, stop_sequence)
);

-- Every arrival with its delay in minutes, on-time flag, local hour and day of week.
CREATE OR REPLACE VIEW arrival_results AS
SELECT
    stop_arrivals.*,
    stop_arrivals.delay_seconds / 60.0 AS delay_minutes,
    stop_arrivals.status = 'observed'
        AND stop_arrivals.delay_seconds >= -60 * settings.early_minutes
        AND stop_arrivals.delay_seconds <= 60 * settings.late_minutes AS is_on_time,
    EXTRACT(HOUR FROM stop_arrivals.scheduled_arrival AT TIME ZONE 'America/Toronto')::INTEGER
        AS hour_of_day,
    EXTRACT(ISODOW FROM stop_arrivals.service_date)::INTEGER AS day_of_week,  -- 1 = Monday
    TO_CHAR(stop_arrivals.service_date, 'FMDay') AS day_name
FROM stop_arrivals
CROSS JOIN reliability_settings AS settings;

-- Delay averages use observed arrivals only; skipped stops and cancelled trips are counted
-- in their own columns. Rates and delays are NULL when nothing was observed.
CREATE OR REPLACE VIEW reliability_overall AS
SELECT
    MIN(service_date) AS first_service_date,
    MAX(service_date) AS last_service_date,
    COUNT(DISTINCT (service_date, trip_id)) AS trips_tracked,
    COUNT(*) FILTER (WHERE status = 'observed') AS observed_arrivals,
    ROUND(AVG(is_on_time::INTEGER) FILTER (WHERE status = 'observed'), 4) AS on_time_rate,
    ROUND(AVG(delay_minutes) FILTER (WHERE status = 'observed'), 2) AS avg_delay_minutes,
    ROUND((PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY delay_minutes)
        FILTER (WHERE status = 'observed'))::NUMERIC, 2) AS p90_delay_minutes,
    COUNT(*) FILTER (WHERE status = 'skipped') AS skipped_stops,
    COUNT(DISTINCT (service_date, trip_id)) FILTER (WHERE status = 'cancelled') AS cancelled_trips
FROM arrival_results;

CREATE OR REPLACE VIEW reliability_by_route AS
SELECT
    route_short_name,
    route_name,
    COUNT(DISTINCT (service_date, trip_id)) AS trips_tracked,
    COUNT(*) FILTER (WHERE status = 'observed') AS observed_arrivals,
    ROUND(AVG(is_on_time::INTEGER) FILTER (WHERE status = 'observed'), 4) AS on_time_rate,
    ROUND(AVG(delay_minutes) FILTER (WHERE status = 'observed'), 2) AS avg_delay_minutes,
    ROUND((PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY delay_minutes)
        FILTER (WHERE status = 'observed'))::NUMERIC, 2) AS p90_delay_minutes,
    COUNT(*) FILTER (WHERE status = 'skipped') AS skipped_stops,
    COUNT(DISTINCT (service_date, trip_id)) FILTER (WHERE status = 'cancelled') AS cancelled_trips
FROM arrival_results
GROUP BY route_short_name, route_name;

CREATE OR REPLACE VIEW reliability_by_hour AS
SELECT
    hour_of_day,
    COUNT(*) FILTER (WHERE status = 'observed') AS observed_arrivals,
    ROUND(AVG(is_on_time::INTEGER) FILTER (WHERE status = 'observed'), 4) AS on_time_rate,
    ROUND(AVG(delay_minutes) FILTER (WHERE status = 'observed'), 2) AS avg_delay_minutes,
    ROUND((PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY delay_minutes)
        FILTER (WHERE status = 'observed'))::NUMERIC, 2) AS p90_delay_minutes,
    COUNT(*) FILTER (WHERE status = 'skipped') AS skipped_stops,
    COUNT(DISTINCT (service_date, trip_id)) FILTER (WHERE status = 'cancelled') AS cancelled_trips
FROM arrival_results
GROUP BY hour_of_day;

CREATE OR REPLACE VIEW reliability_by_day_of_week AS
SELECT
    day_of_week,
    day_name,
    COUNT(*) FILTER (WHERE status = 'observed') AS observed_arrivals,
    ROUND(AVG(is_on_time::INTEGER) FILTER (WHERE status = 'observed'), 4) AS on_time_rate,
    ROUND(AVG(delay_minutes) FILTER (WHERE status = 'observed'), 2) AS avg_delay_minutes,
    ROUND((PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY delay_minutes)
        FILTER (WHERE status = 'observed'))::NUMERIC, 2) AS p90_delay_minutes,
    COUNT(*) FILTER (WHERE status = 'skipped') AS skipped_stops,
    COUNT(DISTINCT (service_date, trip_id)) FILTER (WHERE status = 'cancelled') AS cancelled_trips
FROM arrival_results
GROUP BY day_of_week, day_name;

CREATE OR REPLACE VIEW reliability_by_stop AS
SELECT
    arrival_results.stop_id,
    stops.stop_name,
    stops.stop_lat,
    stops.stop_lon,
    COUNT(*) FILTER (WHERE status = 'observed') AS observed_arrivals,
    ROUND(AVG(is_on_time::INTEGER) FILTER (WHERE status = 'observed'), 4) AS on_time_rate,
    ROUND(AVG(delay_minutes) FILTER (WHERE status = 'observed'), 2) AS avg_delay_minutes,
    ROUND((PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY delay_minutes)
        FILTER (WHERE status = 'observed'))::NUMERIC, 2) AS p90_delay_minutes,
    COUNT(*) FILTER (WHERE status = 'skipped') AS skipped_stops,
    COUNT(DISTINCT (service_date, trip_id)) FILTER (WHERE status = 'cancelled') AS cancelled_trips
FROM arrival_results
LEFT JOIN stops ON stops.stop_id = arrival_results.stop_id
GROUP BY arrival_results.stop_id, stops.stop_name, stops.stop_lat, stops.stop_lon;
