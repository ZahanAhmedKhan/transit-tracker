"""Tests for realtime_parse.py: turning GTFS-Realtime feeds into rows."""

from datetime import date, datetime, timedelta, timezone

from google.transit import gtfs_realtime_pb2

from ingest import safe_error
from realtime_examples import FEED_TIME, make_trip_updates_feed, make_vehicle_feed
from realtime_parse import parse_feed, service_date, trip_update_rows, vehicle_position_rows


def rows_by_stop():
    """Parse the example feed and return its rows keyed by (trip_id, stop_sequence)."""
    rows = trip_update_rows(make_trip_updates_feed(), FEED_TIME)
    return {(row["trip_id"], row["stop_sequence"]): row for row in rows}


def test_one_row_per_stop_time_update_plus_one_for_the_cancelled_trip():
    """The running trip gives 3 rows (one per stop) and the cancelled trip gives 1."""
    rows = trip_update_rows(make_trip_updates_feed(), FEED_TIME)
    assert len(rows) == 4


def test_arrival_time_and_delay_are_read():
    """A stop with an arrival keeps its time (as UTC) and its delay in seconds."""
    row = rows_by_stop()[("20261125-MI-2706", 2)]
    assert row["stop_id"] == "LS"
    assert row["arrival_time"] == datetime(2026, 11, 25, 11, 9, tzinfo=timezone.utc)
    assert row["arrival_delay"] == 120
    assert row["departure_time"] is None
    assert row["stop_relationship"] == "SCHEDULED"


def test_skipped_stop_is_marked():
    """A skipped stop keeps the SKIPPED relationship and has no times."""
    row = rows_by_stop()[("20261125-MI-2706", 3)]
    assert row["stop_relationship"] == "SKIPPED"
    assert row["arrival_time"] is None


def test_cancelled_trip_gets_one_row_without_a_stop():
    """A cancelled trip with no stop updates is kept as one whole-trip row."""
    row = rows_by_stop()[("20261125-LW-1234", None)]
    assert row["trip_relationship"] == "CANCELED"
    assert row["stop_id"] is None


def test_snapshot_time_comes_from_the_feed_header():
    """Every row carries the feed's own timestamp, not the time it was fetched."""
    fetched_later = FEED_TIME + timedelta(minutes=3)
    rows = trip_update_rows(make_trip_updates_feed(), fetched_later)
    assert {row["snapshot_time"] for row in rows} == {FEED_TIME}


def test_service_date_falls_back_to_the_trip_id():
    """Without start_date, the date is read from a GO trip_id such as 20261125-LW-1234."""
    trip = gtfs_realtime_pb2.TripDescriptor(trip_id="20261125-LW-1234")
    assert service_date(trip) == date(2026, 11, 25)
    assert service_date(gtfs_realtime_pb2.TripDescriptor(trip_id="abc")) is None


def test_feed_survives_a_round_trip_through_bytes():
    """parse_feed reads the same protobuf bytes the API sends."""
    feed = parse_feed(make_trip_updates_feed().SerializeToString())
    assert len(trip_update_rows(feed, FEED_TIME)) == 4


def test_vehicle_position_row():
    """A vehicle report keeps its id, trip, coordinates and its own timestamp."""
    rows = vehicle_position_rows(make_vehicle_feed(), FEED_TIME)
    assert len(rows) == 1
    row = rows[0]
    assert row["vehicle_id"] == "train-501"
    assert row["trip_id"] == "20261125-MI-2706"
    assert abs(row["latitude"] - 43.52) < 1e-5
    assert row["position_time"] == FEED_TIME - timedelta(seconds=30)
    assert row["bearing"] is None


def test_error_messages_never_contain_the_api_key():
    """safe_error removes the key before an error is logged or printed."""
    error = ValueError("failed for https://example.com/feed?key=SECRET123")
    assert "SECRET123" not in safe_error(error, "SECRET123")
