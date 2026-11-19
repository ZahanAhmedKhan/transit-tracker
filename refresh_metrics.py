"""Daily step: match live arrivals to the schedule, then clean up old raw data.

GitHub Actions runs this once a day, before the schedule is reloaded. It (re)builds
stop_arrivals for the last few service dates, which are still inside the schedule
window, and is safe to run again: rows are replaced, not duplicated.

Usage:  python refresh_metrics.py
"""

from datetime import timedelta

from db import get_connection

DAYS_TO_REFRESH = 3          # yesterday and the two days before it
RAW_DAYS_TO_KEEP = 30

# Scheduled arrival as a real moment in time: GTFS times count from "noon minus 12 hours"
# on the service date (midnight, except on the two days a year the clocks change), and the
# stop_times interval is added to that. So 24:35:00 on Nov 25 becomes 00:35 on Nov 26.
#
# The final update for each trip and stop is the one seen last (newest last_seen_at).
# Only stops whose arrival is backed by a recent update count as observed: an update
# last seen long before the predicted time was a forecast, not an arrival.
MATCH_OBSERVED_AND_SKIPPED_SQL = """
WITH final_updates AS (
    SELECT DISTINCT ON (trip_id, service_date, stop_sequence) *
    FROM rt_trip_updates
    WHERE service_date BETWEEN %(first_date)s AND %(last_date)s
      AND stop_sequence IS NOT NULL
    ORDER BY trip_id, service_date, stop_sequence, last_seen_at DESC, snapshot_time DESC
),
matched AS (
    SELECT
        final_updates.service_date,
        final_updates.trip_id,
        stop_times.stop_sequence,
        stop_times.stop_id,
        routes.route_short_name,
        routes.route_long_name AS route_name,
        final_updates.last_seen_at,
        final_updates.stop_relationship,
        (CAST(final_updates.service_date AS DATE) + TIME '12:00') AT TIME ZONE 'America/Toronto'
            - INTERVAL '12 hours'
            + COALESCE(stop_times.arrival_time, stop_times.departure_time) AS scheduled_arrival,
        final_updates.arrival_time,
        final_updates.departure_time,
        COALESCE(final_updates.arrival_delay, final_updates.departure_delay) AS feed_delay
    FROM final_updates
    JOIN stop_times
      ON stop_times.trip_id = final_updates.trip_id
     AND stop_times.stop_sequence = final_updates.stop_sequence
    JOIN trips ON trips.trip_id = stop_times.trip_id
    LEFT JOIN routes ON routes.route_id = trips.route_id
),
with_observed AS (
    SELECT
        matched.*,
        COALESCE(
            matched.arrival_time,
            matched.departure_time,
            matched.scheduled_arrival + make_interval(secs => matched.feed_delay)
        ) AS observed_arrival
    FROM matched
)
INSERT INTO stop_arrivals (service_date, trip_id, stop_sequence, stop_id, route_short_name,
                           route_name, scheduled_arrival, observed_arrival, delay_seconds, status)
SELECT
    service_date, trip_id, stop_sequence, stop_id, route_short_name, route_name,
    scheduled_arrival,
    CASE WHEN stop_relationship = 'SKIPPED' THEN NULL ELSE observed_arrival END,
    CASE WHEN stop_relationship = 'SKIPPED' THEN NULL
         ELSE ROUND(EXTRACT(EPOCH FROM observed_arrival - scheduled_arrival))::INTEGER END,
    CASE WHEN stop_relationship = 'SKIPPED' THEN 'skipped' ELSE 'observed' END
FROM with_observed
CROSS JOIN reliability_settings AS settings
WHERE stop_relationship = 'SKIPPED'
   OR (observed_arrival IS NOT NULL
       AND observed_arrival <= last_seen_at
                               + make_interval(mins => settings.max_prediction_gap_minutes::INTEGER))
ON CONFLICT (service_date, trip_id, stop_sequence) DO UPDATE SET
    stop_id = EXCLUDED.stop_id,
    route_short_name = EXCLUDED.route_short_name,
    route_name = EXCLUDED.route_name,
    scheduled_arrival = EXCLUDED.scheduled_arrival,
    observed_arrival = EXCLUDED.observed_arrival,
    delay_seconds = EXCLUDED.delay_seconds,
    status = EXCLUDED.status
"""

# A trip whose newest update says CANCELED counts as cancelled at every scheduled stop.
MATCH_CANCELLED_SQL = """
WITH latest_trip_status AS (
    SELECT DISTINCT ON (trip_id, service_date) trip_id, service_date, trip_relationship
    FROM rt_trip_updates
    WHERE service_date BETWEEN %(first_date)s AND %(last_date)s
    ORDER BY trip_id, service_date, last_seen_at DESC, snapshot_time DESC
)
INSERT INTO stop_arrivals (service_date, trip_id, stop_sequence, stop_id, route_short_name,
                           route_name, scheduled_arrival, observed_arrival, delay_seconds, status)
SELECT
    latest_trip_status.service_date,
    stop_times.trip_id,
    stop_times.stop_sequence,
    stop_times.stop_id,
    routes.route_short_name,
    routes.route_long_name,
    (CAST(latest_trip_status.service_date AS DATE) + TIME '12:00') AT TIME ZONE 'America/Toronto'
        - INTERVAL '12 hours'
        + COALESCE(stop_times.arrival_time, stop_times.departure_time),
    NULL,
    NULL,
    'cancelled'
FROM latest_trip_status
JOIN stop_times ON stop_times.trip_id = latest_trip_status.trip_id
JOIN trips ON trips.trip_id = stop_times.trip_id
LEFT JOIN routes ON routes.route_id = trips.route_id
WHERE latest_trip_status.trip_relationship = 'CANCELED'
ON CONFLICT (service_date, trip_id, stop_sequence) DO UPDATE SET
    observed_arrival = NULL,
    delay_seconds = NULL,
    status = 'cancelled'
"""

# Raw rows are deleted only for service dates that are old AND already summarized.
CLEANUP_TRIP_UPDATES_SQL = """
DELETE FROM rt_trip_updates
WHERE service_date < %(cutoff_date)s
  AND service_date <= (SELECT MAX(service_date) FROM stop_arrivals)
"""

CLEANUP_VEHICLE_POSITIONS_SQL = """
DELETE FROM rt_vehicle_positions
WHERE snapshot_time < %(cutoff_date)s
"""


def toronto_today(cursor):
    """Return today's date in Toronto, as the database sees it."""
    cursor.execute("SELECT (now() AT TIME ZONE 'America/Toronto')::DATE")
    return cursor.fetchone()[0]


def refresh_stop_arrivals(cursor, first_date, last_date):
    """Rebuild stop_arrivals for service dates first_date..last_date and return the row count."""
    dates = {"first_date": first_date, "last_date": last_date}
    cursor.execute(MATCH_OBSERVED_AND_SKIPPED_SQL, dates)
    cursor.execute(MATCH_CANCELLED_SQL, dates)
    cursor.execute(
        "SELECT COUNT(*) FROM stop_arrivals WHERE service_date BETWEEN %s AND %s",
        (first_date, last_date),
    )
    return cursor.fetchone()[0]


def clean_up_raw_data(cursor, today):
    """Delete raw live rows older than RAW_DAYS_TO_KEEP days and return how many were deleted."""
    cutoff = {"cutoff_date": today - timedelta(days=RAW_DAYS_TO_KEEP)}
    cursor.execute(CLEANUP_TRIP_UPDATES_SQL, cutoff)
    deleted = cursor.rowcount
    cursor.execute(CLEANUP_VEHICLE_POSITIONS_SQL, cutoff)
    return deleted + cursor.rowcount


def main():
    """Refresh the last few service dates and clean up, all in one transaction."""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            today = toronto_today(cursor)
            first_date = today - timedelta(days=DAYS_TO_REFRESH)
            last_date = today - timedelta(days=1)
            arrivals = refresh_stop_arrivals(cursor, first_date, last_date)
            print(f"stop_arrivals for {first_date} to {last_date}: {arrivals} rows")
            print("Old raw rows deleted:", clean_up_raw_data(cursor, today))


if __name__ == "__main__":
    main()
