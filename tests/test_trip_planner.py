"""Tests for trip_planner.py: picking journeys, time text, cutting a route's path,
and the journey search itself on a small made-up network.

The search tests run only when DATABASE_URL is set. They use TEMPORARY copies of the
schedule tables, and everything is rolled back at the end.
"""

import os
from datetime import date, timedelta

import pandas as pd
import pytest

import trip_planner
from db import get_connection

TRAVEL_DATE = date(2026, 11, 25)


def minutes(hours, mins):
    """A schedule time such as 7:05 as a timedelta."""
    return timedelta(hours=hours, minutes=mins)


def journey(trip_1, depart, arrive, trip_2=None):
    """One search result row with only the columns best_journeys looks at."""
    return {
        "trip_1": trip_1,
        "depart_1": depart,
        "arrive_1": arrive if trip_2 is None else depart + timedelta(minutes=10),
        "trip_2": trip_2,
        "arrive_2": arrive if trip_2 else pd.NaT,
    }


def test_best_journeys_drops_slower_options_and_sorts_by_arrival():
    journeys = pd.DataFrame([
        journey("A", minutes(7, 0), minutes(8, 0)),
        journey("B", minutes(7, 10), minutes(7, 50), trip_2="C"),  # leaves later, arrives earlier
        journey("D", minutes(7, 30), minutes(8, 30)),
    ])
    best = trip_planner.best_journeys(journeys)
    assert best["trip_1"].tolist() == ["B", "D"]
    assert best["changes"].tolist() == [1, 0]


def test_best_journeys_prefers_no_change_when_times_tie():
    journeys = pd.DataFrame([
        journey("A", minutes(7, 0), minutes(8, 0), trip_2="B"),
        journey("C", minutes(7, 0), minutes(8, 0)),
    ])
    best = trip_planner.best_journeys(journeys)
    assert best["trip_1"].tolist() == ["C"]


def test_clock_time_and_duration_text_handle_times_past_midnight():
    assert trip_planner.clock_time(minutes(25, 10)) == "01:10"
    assert trip_planner.clock_time(minutes(7, 5)) == "07:05"
    assert trip_planner.duration_text(minutes(1, 5)) == "1 h 05 min"
    assert trip_planner.duration_text(minutes(0, 42)) == "42 min"


def test_walk_minutes_rounds_up():
    assert trip_planner.walk_minutes(0) == 1
    assert trip_planner.walk_minutes(80) == 1
    assert trip_planner.walk_minutes(81) == 2


def test_cut_shape_keeps_only_the_part_ridden():
    # A straight path with points every 0.01 degrees of longitude.
    shape = pd.DataFrame({"latitude": [43.0] * 6, "longitude": [-79.5 + 0.01 * i for i in range(6)]})
    get_on = {"latitude": 43.0, "longitude": -79.489}    # nearest point 1
    get_off = {"latitude": 43.0, "longitude": -79.461}   # nearest point 4
    cut = trip_planner.cut_shape(shape, get_on, get_off)
    assert cut.index.tolist() == [1, 2, 3, 4]


# --- The SQL search on a small network --------------------------------------
#
#   Bus B1:   Home 07:00  ->  Mall Bus 07:20                      (stops 1 and 2)
#   Train T1: Mall GO 07:30  ->  Downtown 08:00                   (Mall Bus and Mall GO are ~110 m apart)
#   Train T2: Mall GO 07:24  ->  Downtown 07:50                   (too soon: a 2-min walk + 3 min means 07:25)
#   Bus D1:   Home 07:40  ->  Downtown 09:00                      (direct, but slow)
#   Bus X1:   Home 07:10  ->  Downtown 07:45  on another date     (must not appear)

NETWORK_SQL = """
CREATE TEMP TABLE routes (LIKE public.routes);
CREATE TEMP TABLE trips (LIKE public.trips);
CREATE TEMP TABLE stop_times (LIKE public.stop_times);
CREATE TEMP TABLE stops (LIKE public.stops);
CREATE TEMP TABLE calendar_dates (LIKE public.calendar_dates);

INSERT INTO stops (stop_id, stop_name, stop_lat, stop_lon) VALUES
    ('H', 'Home', 43.500, -79.800),
    ('MB', 'Mall Bus', 43.600, -79.700),
    ('MG', 'Mall GO', 43.601, -79.700),
    ('D', 'Downtown', 43.650, -79.380);

INSERT INTO routes (route_id, route_short_name, route_long_name, route_type) VALUES
    ('R-B', '21', 'Bus route', 3), ('R-T', 'MI', 'Train route', 2);

INSERT INTO calendar_dates (service_id, date, exception_type) VALUES
    ('TODAY', '2026-11-25', 1), ('OTHER', '2026-11-26', 1);

INSERT INTO trips (trip_id, route_id, service_id) VALUES
    ('B1', 'R-B', 'TODAY'), ('T1', 'R-T', 'TODAY'), ('T2', 'R-T', 'TODAY'),
    ('D1', 'R-B', 'TODAY'), ('X1', 'R-B', 'OTHER');

INSERT INTO stop_times (trip_id, stop_sequence, stop_id, arrival_time, departure_time, pickup_type) VALUES
    ('B1', 1, 'H',  '07:00', '07:00', 0), ('B1', 2, 'MB', '07:20', '07:20', 0),
    ('T1', 1, 'MG', '07:30', '07:30', 0), ('T1', 2, 'D',  '08:00', '08:00', 0),
    ('T2', 1, 'MG', '07:24', '07:24', 0), ('T2', 2, 'D',  '07:50', '07:50', 0),
    ('D1', 1, 'H',  '07:40', '07:40', 0), ('D1', 2, 'D',  '09:00', '09:00', 0),
    ('X1', 1, 'H',  '07:10', '07:10', 0), ('X1', 2, 'D',  '07:45', '07:45', 0);
"""


@pytest.fixture
def search():
    """A function that runs the journey search on the small network, then rolls back."""
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set")
    with get_connection() as connection:
        connection.execute(NETWORK_SQL)

        def run(from_name, to_name, leave_after):
            params = trip_planner.search_params(from_name, to_name, TRAVEL_DATE, leave_after)
            cursor = connection.execute(trip_planner.JOURNEYS_SQL, params)
            columns = [column.name for column in cursor.description]
            return pd.DataFrame(cursor.fetchall(), columns=columns)

        yield run
        connection.rollback()


def test_search_finds_direct_and_one_change_journeys(search):
    best = trip_planner.best_journeys(search("Home", "Downtown", "06:30"))
    # B1 then T1 (with a walk) arrives 08:00; the direct D1 arrives 09:00 but leaves later.
    assert best["trip_1"].tolist() == ["B1", "D1"]
    assert best.loc[0, "trip_2"] == "T1"
    assert 100 <= best.loc[0, "walk_metres"] <= 120
    assert best.loc[0, "route_2"] == "MI"


def test_search_skips_connections_too_tight_to_make(search):
    raw = search("Home", "Downtown", "06:30")
    # T2 leaves Mall GO 4 minutes after B1 arrives; the ~110 m walk (2 min) plus 3 min needs 5.
    assert "T2" not in raw["trip_2"].dropna().tolist()


def test_search_uses_only_trips_running_on_the_date(search):
    raw = search("Home", "Downtown", "06:30")
    assert "X1" not in raw["trip_1"].tolist()


def test_search_respects_leave_after_time(search):
    best = trip_planner.best_journeys(search("Home", "Downtown", "07:30"))
    assert best["trip_1"].tolist() == ["D1"]
