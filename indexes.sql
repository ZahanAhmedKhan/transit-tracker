-- Indexes that make the dashboard queries fast.
-- Run after loading the data:   psql -U postgres -d transit -f indexes.sql
-- An index works like the index at the back of a book: PostgreSQL looks up
-- the matching rows directly instead of reading the whole table.

CREATE INDEX IF NOT EXISTS stop_times_stop_id_idx ON stop_times (stop_id);
CREATE INDEX IF NOT EXISTS stop_times_trip_id_idx ON stop_times (trip_id);
CREATE INDEX IF NOT EXISTS trips_route_id_idx ON trips (route_id);
CREATE INDEX IF NOT EXISTS calendar_dates_date_idx ON calendar_dates (date);
