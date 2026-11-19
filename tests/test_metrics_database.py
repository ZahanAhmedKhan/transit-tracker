"""Tests for the matching logic in refresh_metrics.py and the views in metrics_schema.sql.

Runs only when DATABASE_URL is set. Every table and view is a TEMPORARY copy filled
with a few known examples, and everything is rolled back at the end.

All examples are on service date 2026-11-25, when Toronto is UTC-5, so
06:00 in the schedule is 11:00 UTC.
"""

import os
from datetime import date, datetime, timezone

import pytest

from db import get_connection
from refresh_metrics import clean_up_raw_data, refresh_stop_arrivals

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")

SERVICE_DATE = date(2026, 11, 25)

SCHEDULE_SQL = """
CREATE TEMP TABLE routes (LIKE public.routes);
CREATE TEMP TABLE trips (LIKE public.trips);
CREATE TEMP TABLE stop_times (LIKE public.stop_times);
CREATE TEMP TABLE stops (LIKE public.stops);

INSERT INTO routes (route_id, route_short_name, route_long_name, route_type)
VALUES ('R-MI', 'MI', 'Milton', 2), ('R-LW', 'LW', 'Lakeshore West', 2);

INSERT INTO trips (trip_id, route_id, service_id) VALUES
    ('MI-1', 'R-MI', '20261125'),     -- normal morning trip
    ('MI-2', 'R-MI', '20261125'),     -- arrives early
    ('LW-NIGHT', 'R-LW', '20261125'), -- runs past midnight
    ('LW-CXL', 'R-LW', '20261125');   -- cancelled

INSERT INTO stop_times (trip_id, stop_sequence, stop_id, arrival_time, departure_time) VALUES
    ('MI-1', 1, 'ML', '06:00:00', '06:00:00'),
    ('MI-1', 2, 'LS', '06:09:00', '06:09:00'),
    ('MI-1', 3, 'ME', '06:20:00', '06:20:00'),
    ('MI-1', 4, 'UN', '07:00:00', '07:00:00'),
    ('MI-2', 1, 'ML', '08:00:00', '08:00:00'),
    ('LW-NIGHT', 1, 'UN', '24:20:00', '24:20:00'),
    ('LW-NIGHT', 2, 'EX', '24:35:00', '24:35:00'),
    ('LW-CXL', 1, 'UN', '09:00:00', '09:00:00'),
    ('LW-CXL', 2, 'EX', '09:10:00', '09:10:00');
"""


def utc(day, hour, minute, second=0):
    """Make a UTC datetime on November `day`, 2026."""
    return datetime(2026, 11, day, hour, minute, second, tzinfo=timezone.utc)


def add_update(cursor, trip_id, stop_sequence, arrival, last_seen, relationship="SCHEDULED",
               trip_relationship="SCHEDULED"):
    """Insert one raw live update for the test service date."""
    cursor.execute(
        """
        INSERT INTO rt_trip_updates (snapshot_time, last_seen_at, trip_id, service_date,
                                     stop_sequence, arrival_time, stop_relationship,
                                     trip_relationship)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (last_seen, last_seen, trip_id, SERVICE_DATE, stop_sequence, arrival, relationship,
         trip_relationship),
    )


def add_examples(cursor):
    """Insert the known live updates used by every test."""
    add_update(cursor, "MI-1", 1, utc(25, 11, 0, 30), utc(25, 11, 0))   # 30 s late
    add_update(cursor, "MI-1", 2, utc(25, 11, 12), utc(25, 11, 5))      # first guess: 3 min late
    add_update(cursor, "MI-1", 2, utc(25, 11, 16), utc(25, 11, 16))     # final: 7 min late
    add_update(cursor, "MI-1", 3, None, utc(25, 11, 16), relationship="SKIPPED")
    add_update(cursor, "MI-1", 4, utc(25, 13, 30), utc(25, 11, 16))     # forecast only
    add_update(cursor, "MI-2", 1, utc(25, 12, 58), utc(25, 12, 58))     # 2 min early
    add_update(cursor, "LW-NIGHT", 2, utc(26, 5, 38), utc(26, 5, 38))   # 00:38 next day
    cursor.execute(
        """
        INSERT INTO rt_trip_updates (snapshot_time, last_seen_at, trip_id, service_date,
                                     trip_relationship)
        VALUES (%s, %s, 'LW-CXL', %s, 'CANCELED')
        """,
        (utc(25, 13, 0), utc(25, 13, 0), SERVICE_DATE),
    )


def temporary(sql):
    """Rewrite a schema file so it creates temporary tables and views."""
    return (
        sql.replace("CREATE TABLE IF NOT EXISTS", "CREATE TEMP TABLE")
        .replace("CREATE OR REPLACE VIEW", "CREATE TEMP VIEW")
    )


def read_file(path):
    """Return the text of a file in the repo."""
    with open(path, encoding="utf-8") as file:
        return file.read()


@pytest.fixture
def cursor():
    """Give a test a cursor on temporary tables holding the examples, already refreshed."""
    with get_connection() as connection:
        with connection.cursor() as test_cursor:
            test_cursor.execute(SCHEDULE_SQL)
            test_cursor.execute(temporary(read_file("rt_schema.sql")))
            test_cursor.execute(temporary(read_file("metrics_schema.sql")))
            add_examples(test_cursor)
            refresh_stop_arrivals(test_cursor, SERVICE_DATE, SERVICE_DATE)
            yield test_cursor
        connection.rollback()


def arrival(cursor, trip_id, stop_sequence):
    """Return (status, delay_seconds, is_on_time) for one trip and stop, or None."""
    cursor.execute(
        """
        SELECT status, delay_seconds, is_on_time FROM arrival_results
        WHERE trip_id = %s AND stop_sequence = %s
        """,
        (trip_id, stop_sequence),
    )
    return cursor.fetchone()


def test_small_delay_is_on_time(cursor):
    """30 seconds late is inside the 5-minute threshold."""
    assert arrival(cursor, "MI-1", 1) == ("observed", 30, True)


def test_last_update_seen_is_the_final_arrival(cursor):
    """Of two predictions for the same stop, the one seen last is used (7 min late, not 3)."""
    assert arrival(cursor, "MI-1", 2) == ("observed", 420, False)


def test_more_than_one_minute_early_is_not_on_time(cursor):
    """2 minutes early is outside the 1-minute early threshold."""
    assert arrival(cursor, "MI-2", 1) == ("observed", -120, False)


def test_trip_crossing_midnight(cursor):
    """24:35:00 on Nov 25 is 00:35 on Nov 26; arriving at 00:38 is 3 minutes late."""
    assert arrival(cursor, "LW-NIGHT", 2) == ("observed", 180, True)
    cursor.execute(
        "SELECT scheduled_arrival FROM stop_arrivals WHERE trip_id = 'LW-NIGHT' AND stop_sequence = 2"
    )
    assert cursor.fetchone()[0] == utc(26, 5, 35)


def test_skipped_stop_has_no_delay(cursor):
    """A skipped stop is stored as skipped with no delay."""
    assert arrival(cursor, "MI-1", 3) == ("skipped", None, False)


def test_forecast_far_ahead_is_not_counted(cursor):
    """A prediction last seen over two hours before the arrival is not an observed arrival."""
    assert arrival(cursor, "MI-1", 4) is None


def test_cancelled_trip_marks_every_scheduled_stop(cursor):
    """A cancelled trip with no stop updates is cancelled at both of its scheduled stops."""
    assert arrival(cursor, "LW-CXL", 1) == ("cancelled", None, False)
    assert arrival(cursor, "LW-CXL", 2) == ("cancelled", None, False)


def test_route_summary_excludes_skipped_and_cancelled_from_delays(cursor):
    """MI: delays of 0.5, 7 and -2 minutes; one on time; the skipped stop is counted apart."""
    cursor.execute(
        """
        SELECT observed_arrivals, on_time_rate, avg_delay_minutes, skipped_stops, cancelled_trips
        FROM reliability_by_route WHERE route_short_name = 'MI'
        """
    )
    observed, on_time_rate, avg_delay, skipped, cancelled = cursor.fetchone()
    assert observed == 3
    assert float(on_time_rate) == pytest.approx(1 / 3, abs=1e-4)
    assert float(avg_delay) == pytest.approx((0.5 + 7 - 2) / 3, abs=0.01)
    assert (skipped, cancelled) == (1, 0)


def test_overall_summary(cursor):
    """Overall: 4 trips, 4 observed arrivals, 2 on time, 1 cancelled trip."""
    cursor.execute(
        "SELECT trips_tracked, observed_arrivals, on_time_rate, cancelled_trips FROM reliability_overall"
    )
    trips, observed, on_time_rate, cancelled = cursor.fetchone()
    assert (trips, observed, cancelled) == (4, 4, 1)
    assert float(on_time_rate) == pytest.approx(0.5)


def test_hour_of_day_uses_toronto_time(cursor):
    """The 06:00 and 06:09 MI arrivals fall in hour 6, the past-midnight one in hour 0."""
    cursor.execute("SELECT hour_of_day, observed_arrivals FROM reliability_by_hour ORDER BY 1")
    hours = dict(cursor.fetchall())
    assert hours[6] == 2
    assert hours[0] == 1


def test_refresh_twice_gives_the_same_rows(cursor):
    """Running the refresh again replaces rows instead of adding duplicates."""
    cursor.execute("SELECT COUNT(*) FROM stop_arrivals")
    before = cursor.fetchone()[0]
    refresh_stop_arrivals(cursor, SERVICE_DATE, SERVICE_DATE)
    cursor.execute("SELECT COUNT(*) FROM stop_arrivals")
    assert cursor.fetchone()[0] == before


def test_cleanup_keeps_recent_and_unsummarized_rows(cursor):
    """Cleanup on Dec 1 deletes nothing: Nov 25 is less than 30 days old."""
    assert clean_up_raw_data(cursor, date(2026, 12, 1)) == 0
    assert clean_up_raw_data(cursor, date(2027, 1, 10)) == 8
