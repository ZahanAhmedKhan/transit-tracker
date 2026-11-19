"""Turn GTFS-Realtime feed messages into plain rows for the database.

These functions do not touch the network or the database, so the tests in
tests/test_realtime_parse.py can check them with small hand-made feeds.
"""

from datetime import datetime, timezone

from google.transit import gtfs_realtime_pb2

TripDescriptor = gtfs_realtime_pb2.TripDescriptor
StopTimeUpdate = gtfs_realtime_pb2.TripUpdate.StopTimeUpdate


def to_timestamp(posix_seconds):
    """Turn POSIX seconds from the feed into a UTC datetime (0 or missing means None)."""
    if not posix_seconds:
        return None
    return datetime.fromtimestamp(posix_seconds, tz=timezone.utc)


def snapshot_time(feed, fetched_at):
    """Return the feed's own timestamp, or the fetch time if the feed has none."""
    return to_timestamp(feed.header.timestamp) or fetched_at


def service_date(trip):
    """Return the trip's service date from start_date, or from a GO trip_id like 20261125-GT-3514."""
    for text in (trip.start_date, trip.trip_id[:8]):
        try:
            return datetime.strptime(text, "%Y%m%d").date()
        except ValueError:
            continue
    return None


def event_fields(stop_time_update, event_name):
    """Return (time, delay) for the arrival or departure of one stop-time update."""
    if not stop_time_update.HasField(event_name):
        return None, None
    event = getattr(stop_time_update, event_name)
    delay = event.delay if event.HasField("delay") else None
    return to_timestamp(event.time), delay


def stop_time_row(base_row, stop_time_update):
    """Build one row for one stop-time update of a trip."""
    arrival_time, arrival_delay = event_fields(stop_time_update, "arrival")
    departure_time, departure_delay = event_fields(stop_time_update, "departure")
    row = dict(base_row)
    row.update(
        stop_id=stop_time_update.stop_id or None,
        stop_sequence=(
            stop_time_update.stop_sequence if stop_time_update.HasField("stop_sequence") else None
        ),
        arrival_time=arrival_time,
        departure_time=departure_time,
        arrival_delay=arrival_delay,
        departure_delay=departure_delay,
        stop_relationship=StopTimeUpdate.ScheduleRelationship.Name(
            stop_time_update.schedule_relationship
        ),
    )
    return row


def whole_trip_row(base_row):
    """Build a row with no stop, for a trip update that has no stop-time updates (e.g. cancelled)."""
    row = dict(base_row)
    row.update(
        stop_id=None,
        stop_sequence=None,
        arrival_time=None,
        departure_time=None,
        arrival_delay=None,
        departure_delay=None,
        stop_relationship=None,
    )
    return row


def trip_update_rows(feed, fetched_at):
    """Return one row per stop-time update in a TripUpdates feed."""
    snapshot = snapshot_time(feed, fetched_at)
    rows = []
    for entity in feed.entity:
        if not entity.HasField("trip_update"):
            continue
        trip = entity.trip_update.trip
        base_row = {
            "snapshot_time": snapshot,
            "trip_id": trip.trip_id,
            "service_date": service_date(trip),
            "route_id": trip.route_id or None,
            "trip_relationship": TripDescriptor.ScheduleRelationship.Name(
                trip.schedule_relationship
            ),
        }
        stop_time_updates = entity.trip_update.stop_time_update
        if len(stop_time_updates) == 0:
            rows.append(whole_trip_row(base_row))
        for stop_time_update in stop_time_updates:
            rows.append(stop_time_row(base_row, stop_time_update))
    return rows


def vehicle_position_rows(feed, fetched_at):
    """Return one row per vehicle in a VehiclePositions feed."""
    snapshot = snapshot_time(feed, fetched_at)
    rows = []
    for entity in feed.entity:
        if not entity.HasField("vehicle"):
            continue
        vehicle = entity.vehicle
        position = vehicle.position
        rows.append(
            {
                "snapshot_time": snapshot,
                "vehicle_id": vehicle.vehicle.id or entity.id,
                "position_time": to_timestamp(vehicle.timestamp) or snapshot,
                "trip_id": vehicle.trip.trip_id or None,
                "route_id": vehicle.trip.route_id or None,
                "latitude": position.latitude if vehicle.HasField("position") else None,
                "longitude": position.longitude if vehicle.HasField("position") else None,
                "bearing": position.bearing if position.HasField("bearing") else None,
                "speed": position.speed if position.HasField("speed") else None,
            }
        )
    return rows


def parse_feed(content):
    """Parse the raw protobuf bytes of a GTFS-Realtime feed into a FeedMessage."""
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(content)
    return feed
