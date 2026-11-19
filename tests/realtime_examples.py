"""Small hand-made GTFS-Realtime feeds shared by the tests."""

from datetime import datetime, timezone

from google.transit import gtfs_realtime_pb2

FEED_TIME = datetime(2026, 11, 25, 16, 30, tzinfo=timezone.utc)


def posix(moment):
    """Turn a datetime into POSIX seconds, the time format GTFS-Realtime uses."""
    return int(moment.timestamp())


def make_trip_updates_feed(arrival_delay=120):
    """Build a TripUpdates feed with one running trip (two stops) and one cancelled trip."""
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.header.gtfs_realtime_version = "2.0"
    feed.header.timestamp = posix(FEED_TIME)

    running = feed.entity.add(id="1").trip_update
    running.trip.trip_id = "20261125-MI-2706"
    running.trip.route_id = "MI"
    running.trip.start_date = "20261125"
    first_stop = running.stop_time_update.add(stop_sequence=1, stop_id="ML")
    first_stop.departure.time = posix(datetime(2026, 11, 25, 11, 0, tzinfo=timezone.utc))
    first_stop.departure.delay = 0
    second_stop = running.stop_time_update.add(stop_sequence=2, stop_id="LS")
    second_stop.arrival.time = posix(datetime(2026, 11, 25, 11, 9, tzinfo=timezone.utc))
    second_stop.arrival.delay = arrival_delay
    skipped_stop = running.stop_time_update.add(stop_sequence=3, stop_id="ME")
    skipped_stop.schedule_relationship = (
        gtfs_realtime_pb2.TripUpdate.StopTimeUpdate.ScheduleRelationship.SKIPPED
    )

    cancelled = feed.entity.add(id="2").trip_update
    cancelled.trip.trip_id = "20261125-LW-1234"
    cancelled.trip.route_id = "LW"
    cancelled.trip.schedule_relationship = (
        gtfs_realtime_pb2.TripDescriptor.ScheduleRelationship.CANCELED
    )
    return feed


def make_vehicle_feed():
    """Build a VehiclePositions feed with one train."""
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.header.gtfs_realtime_version = "2.0"
    feed.header.timestamp = posix(FEED_TIME)
    vehicle = feed.entity.add(id="v1").vehicle
    vehicle.vehicle.id = "train-501"
    vehicle.trip.trip_id = "20261125-MI-2706"
    vehicle.trip.route_id = "MI"
    vehicle.position.latitude = 43.52
    vehicle.position.longitude = -79.88
    vehicle.position.speed = 22.5
    vehicle.timestamp = posix(FEED_TIME) - 30
    return feed
