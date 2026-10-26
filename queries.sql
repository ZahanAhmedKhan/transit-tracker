-- SQL queries for the GO Transit data (Milestone 5).
-- Run in pgAdmin's Query Tool on the transit database, or:
--   psql -U postgres -d transit -f queries.sql


-- 1. Milton line trains leaving Milton GO on weekday mornings.
--    service_id links a trip to the dates it runs (calendar_dates).
--    ISODOW: 1 = Monday ... 7 = Sunday, so 1-5 are weekdays.
--    direction_id 1 = towards Union Station (away from Milton).
SELECT
    calendar_dates.date,
    stop_times.departure_time,
    trips.trip_headsign,
    trips.trip_id
FROM stop_times
JOIN trips ON trips.trip_id = stop_times.trip_id
JOIN routes ON routes.route_id = trips.route_id
JOIN calendar_dates ON calendar_dates.service_id = trips.service_id
WHERE routes.route_short_name = 'MI'
  AND routes.route_type = 2
  AND stop_times.stop_id = 'ML'
  AND trips.direction_id = 1
  AND EXTRACT(ISODOW FROM calendar_dates.date) BETWEEN 1 AND 5
  AND stop_times.departure_time < INTERVAL '12 hours'
ORDER BY calendar_dates.date, stop_times.departure_time;


-- 2. Routes that serve Sheridan College (stop 00939).
--    DISTINCT keeps one row per route instead of one per stop time.
SELECT DISTINCT
    routes.route_short_name,
    routes.route_long_name
FROM stop_times
JOIN trips ON trips.trip_id = stop_times.trip_id
JOIN routes ON routes.route_id = trips.route_id
WHERE stop_times.stop_id = '00939'
ORDER BY routes.route_short_name;


-- 3. Number of trips per route over the whole schedule.
SELECT
    routes.route_short_name,
    routes.route_long_name,
    COUNT(trips.trip_id) AS trip_count
FROM routes
JOIN trips ON trips.route_id = routes.route_id
GROUP BY routes.route_short_name, routes.route_long_name
ORDER BY trip_count DESC;
