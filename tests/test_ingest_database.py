"""Database tests for ingest.py: storing a snapshot twice must not create duplicates.

These run only when DATABASE_URL is set. They create TEMPORARY copies of the live
tables, which PostgreSQL uses before the real ones, and roll everything back, so the
real data is never touched.
"""

import os
from datetime import timedelta

import pytest

from db import get_connection
from ingest import store_trip_updates, store_vehicle_positions
from realtime_examples import FEED_TIME, make_trip_updates_feed, make_vehicle_feed
from realtime_parse import trip_update_rows, vehicle_position_rows

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")


def temporary_schema_sql():
    """Return rt_schema.sql rewritten to create temporary tables instead of real ones."""
    with open("rt_schema.sql", encoding="utf-8") as file:
        sql = file.read()
    return sql.replace("CREATE TABLE IF NOT EXISTS", "CREATE TEMP TABLE")


@pytest.fixture
def cursor():
    """Give a test a cursor on temporary live-data tables, then throw everything away."""
    with get_connection() as connection:
        with connection.cursor() as test_cursor:
            test_cursor.execute(temporary_schema_sql())
            yield test_cursor
        connection.rollback()


def count_rows(cursor, table_name):
    """Return the number of rows in a table."""
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    return cursor.fetchone()[0]


def test_same_snapshot_twice_is_stored_once(cursor):
    """Re-running the same snapshot inserts nothing new."""
    rows = trip_update_rows(make_trip_updates_feed(), FEED_TIME)
    assert store_trip_updates(cursor, rows) == 4
    assert store_trip_updates(cursor, rows) == 0
    assert count_rows(cursor, "rt_trip_updates") == 4


def test_unchanged_prediction_in_a_later_snapshot_only_moves_last_seen(cursor):
    """A later snapshot with the same prediction updates last_seen_at instead of adding a row."""
    store_trip_updates(cursor, trip_update_rows(make_trip_updates_feed(), FEED_TIME))
    later_feed = make_trip_updates_feed()
    later_feed.header.timestamp += 300
    assert store_trip_updates(cursor, trip_update_rows(later_feed, FEED_TIME)) == 0

    cursor.execute("SELECT MIN(snapshot_time), MAX(last_seen_at) FROM rt_trip_updates")
    first_seen, last_seen = cursor.fetchone()
    assert first_seen == FEED_TIME
    assert last_seen == FEED_TIME + timedelta(seconds=300)


def test_changed_prediction_adds_one_row(cursor):
    """When only one stop's delay changes, exactly one new row is stored."""
    store_trip_updates(cursor, trip_update_rows(make_trip_updates_feed(arrival_delay=120), FEED_TIME))
    changed = trip_update_rows(make_trip_updates_feed(arrival_delay=240), FEED_TIME)
    assert store_trip_updates(cursor, changed) == 1
    assert count_rows(cursor, "rt_trip_updates") == 5


def test_vehicle_positions_are_stored_once(cursor):
    """The same vehicle report stored twice is kept once."""
    rows = vehicle_position_rows(make_vehicle_feed(), FEED_TIME)
    assert store_vehicle_positions(cursor, rows) == 1
    assert store_vehicle_positions(cursor, rows) == 0
    assert count_rows(cursor, "rt_vehicle_positions") == 1
